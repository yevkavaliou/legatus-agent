import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Callable, Coroutine, Optional
from urllib.parse import urljoin

import aiohttp
import feedparser
from aiohttp import ClientSession
from bs4 import BeautifulSoup

from .config import AppConfig
from .constants import DEFAULT_SCOUT_TIMEOUT
from .utils import should_verify_ssl_for_url

# A simple type alias for clarity
Article = Dict[str, Any]

def _extract_summary(entry) -> str:
    """
    Intelligently extracts a summary from an RSS feed entry.

    Tries in order: entry.content, entry.summary, entry.description.
    Strips HTML from content and truncates it.
    """
    if hasattr(entry, 'content') and entry.content:
        try:
            html_content = entry.content[0].value
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text(separator=' ', strip=True)
            if text_content:
                # Truncate to reasonable length
                return (text_content[:400] + '...') if len(text_content) > 400 else text_content
        except (IndexError, KeyError, TypeError, AttributeError):
            pass # Fall through

    if hasattr(entry, 'summary') and entry.summary:
        return entry.summary

    if hasattr(entry, 'description') and entry.description:
        return entry.description

    return ""

async def fetch_from_rss_async(client: ClientSession, config: AppConfig, source_url: str) -> List[Article]:
    """Asynchronously fetches and filters recent articles from a single RSS feed."""
    logging.info(f"Scanning RSS feed: {source_url}")
    found_articles: List[Article] = []

    lookback_hours = config.analysis_rules.lookback_period_hours
    timeout = config.scout_settings.timeout
    skip_ssl_domains = config.security.skip_ssl_verify

    ssl_context = should_verify_ssl_for_url(source_url, skip_ssl_domains)

    try:
        async with (client.get(source_url, ssl=ssl_context, timeout=timeout) as response):
            response.raise_for_status()
            feed_content = await response.text()

            # feedparser can be slow, run it in an executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            feed = await loop.run_in_executor(None, lambda: feedparser.parse(feed_content))

            if feed.bozo:
                raise Exception(f"Malformed feed: {getattr(feed, 'bozo_exception', 'Unknown parsing error')}")

            # Calculate the cutoff time for recent articles
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

            for entry in feed.entries:
                published_time_utc = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_time_utc = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                if published_time_utc and published_time_utc >= cutoff_time:
                    tags_list = getattr(entry, 'tags', [])
                    tags = [tag.term.lower() for tag in tags_list if hasattr(tag, 'term')]
                    article = {
                        "title": entry.title,
                        "link": urljoin(source_url, entry.link),
                        "published": published_time_utc.isoformat(),
                        "summary": _extract_summary(entry),
                        "tags": tags,
                        "source": "RSS"
                    }
                    found_articles.append(article)

            logging.info(f"Found {len(found_articles)} new articles for {source_url}.")
            return found_articles

    except asyncio.TimeoutError:
        logging.error(f"Timeout while fetching RSS feed {source_url}.")
    except aiohttp.ClientError as e:
        logging.error(f"Network error processing RSS feed {source_url}. Reason: {e}")
    except Exception as e:
        logging.error(f"Could not process RSS feed {source_url}. Reason: {e}")
    return []


async def fetch_from_github_releases_async(client: ClientSession, config: AppConfig, repo: str) -> List[Article]:
    """Asynchronously fetches recent releases from a GitHub repository."""
    logging.info(f"Scanning GitHub Releases for repo: {repo}")
    found_articles: List[Article] = []

    lookback_hours = config.analysis_rules.lookback_period_hours

    api_url = f"https://api.github.com/repos/{repo}/releases"
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    try:
        async with client.get(api_url, timeout=DEFAULT_SCOUT_TIMEOUT) as response:
            response.raise_for_status()
            releases = await response.json()

            for release in releases:
                # Ensure published_at exists and is a valid ISO 8601 string
                if not (published_at_str := release.get('published_at')):
                    continue

                published_time = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))

                if published_time >= cutoff_time:
                    article = {
                        "title": f"GitHub Release: {release.get('name') or release.get('tag_name', 'N/A')}",
                        "link": release.get('html_url', '#'),
                        "published": published_time.isoformat(),
                        "summary": (release.get('body', 'No release notes.') or "")[:800] + '...',
                        "tags": ["github", "release", repo.split('/')[-1]],
                        "source": "GitHub Release"
                    }
                    found_articles.append(article)

            logging.info(f"Found {len(found_articles)} new releases from {repo}.")
            return found_articles

    except asyncio.TimeoutError:
        logging.error(f"Timeout while fetching GitHub releases for {repo}.")
    except aiohttp.ClientError as e:
        logging.error(f"Network error processing GitHub releases for {repo}. Reason: {e}")
    except Exception as e:
        logging.error(f"Could not process GitHub releases for {repo}. Reason: {e}")
    return []


# Map config keys to their corresponding async fetcher functions
SOURCE_FETCHER_MAP: Dict[str, Callable[[ClientSession, AppConfig, str], Coroutine[Any, Any, List[Article]]]] = {
    "rss_feeds": fetch_from_rss_async,
    "github_releases": fetch_from_github_releases_async,
}


async def run_scout_async(config: AppConfig, github_token: Optional[str]) -> List[Article]:
    """Asynchronously runs the full scouting process based on the configuration."""
    logging.info("=" * 80)
    logging.info("Scout Module: Concurrently searching for new articles...")
    logging.info("=" * 80)

    headers = {'User-Agent': config.scout_settings.user_agent}
    if github_token:
        headers['Authorization'] = f"token {github_token}"
        logging.info("Using GitHub token for API requests.")
    else:
        logging.warning("No GitHub token provided. API requests may be rate-limited.")

    all_articles: List[Article] = []
    data_sources = config.data_sources.model_dump()

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = []
        for source_type, sources_list in data_sources.items():
            if fetcher_func := SOURCE_FETCHER_MAP.get(source_type):
                for source_item in sources_list:
                    tasks.append(fetcher_func(session, config, source_item))
            else:
                logging.warning(f"Unknown data source type '{source_type}' in config. Skipping.")

        results_from_all_sources = await asyncio.gather(*tasks)

    for article_list in results_from_all_sources:
        all_articles.extend(article_list)

    logging.info(f"Scout finished. Total articles/links found: {len(all_articles)}")
    return all_articles

def run_scout(config: AppConfig, github_token: Optional[str] = None) -> List[Article]:
    """Synchronous wrapper to run the async scout function."""
    return asyncio.run(run_scout_async(config, github_token=github_token))
