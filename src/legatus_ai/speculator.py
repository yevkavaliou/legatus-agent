import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional

import aiohttp
import trafilatura
from aiohttp import ClientSession
from google.auth.aio.transport import aiohttp
from langchain_core.runnables import Runnable

from .config import AppConfig
from .utils import should_verify_ssl_for_url

# A simple type alias for clarity
Article = Dict[str, Any]
AnalysisResult = Dict[str, Any]


async def _fetch_and_parse_article_content_async(session: ClientSession, url: str, config: AppConfig) -> Optional[
    str]:
    """
    Asynchronously fetches and parses the main textual content of an article.

    Args:
        session: The aiohttp ClientSession to use for the request.
        url: The URL of the article to fetch.
        config: The validated application configuration.

    Returns:
        The cleaned text content of the article as a string, or None on failure.
    """
    spec_cfg = config.speculator_settings
    headers = {'User-Agent': spec_cfg.user_agent}
    ssl_context = should_verify_ssl_for_url(url, config.security.skip_ssl_verify)

    try:
        async with session.get(url, headers=headers, ssl=ssl_context, timeout=spec_cfg.timeout) as response:
            response.raise_for_status()
            html_content = await response.text()

            loop = asyncio.get_running_loop()
            text_content = await loop.run_in_executor(None, lambda: trafilatura.extract(html_content))
            return text_content or None
    except asyncio.TimeoutError:
        logging.error(f"Timeout while fetching article content from {url}.")
    except aiohttp.ClientError as e:
        logging.error(f"Network error fetching article content from {url}. Reason: {e}")
    except Exception as e:
        logging.error(f"Unexpected error fetching article content from {url}. Reason: {e}")
    return None


def _parse_llm_json_response(raw_response: str, article_title: str) -> Optional[Dict[str, Any]]:
    """
    Cleans and parses a JSON string from an LLM response.

    Handles responses that may be wrapped in markdown code fences.

    Args:
        raw_response: The raw string output from the LLM.
        article_title: The title of the article, for logging purposes.

    Returns:
        A parsed dictionary, or None if parsing fails.
    """

    # Regex to find a JSON object within markdown ```json ... ``` blocks or as a standalone object.
    match = re.search(r'```json\s*(\{.*?\})\s*```|(\{.*?\})', raw_response, re.DOTALL)
    if not match:
        logging.error(f"No valid JSON object found in LLM response for '{article_title}'. Response: {raw_response}")
        return None

    # Prioritize the content of a json block if present, otherwise take the standalone json
    json_string = match.group(1) if match.group(1) else match.group(2)

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        logging.error(
            f"Failed to parse JSON from LLM for '{article_title}'. Error: {e}\nInvalid JSON string: {json_string}")
        return None


async def _analyze_single_article(
        session: ClientSession,
        article: Article,
        ai_chain: Runnable,
        config: AppConfig,
        semaphore: asyncio.Semaphore,
) -> Optional[AnalysisResult]:
    """
    Analyzes a single article by fetching its content and invoking the AI chain.
    Uses a semaphore to limit concurrency.
    """
    async with semaphore:
        logging.info(f"Analyzing article: '{article.get('title', 'Untitled')}'")
        full_text = await _fetch_and_parse_article_content_async(session, article['link'], config)
        if not full_text:
            logging.warning(f"Skipping analysis for '{article['title']}' due to content fetch failure.")
            return None

        logging.debug(f"Fetched content for '{article['title']}' (first 200 chars): {full_text[:200]}...")

        try:
            prompt_data = {
                "title": article.get('title', ''),
                "summary": article.get('summary', ''),
                "article_text": full_text,
            }
            raw_response = await ai_chain.ainvoke(prompt_data)
            logging.debug(f"Raw LLM Response for '{article['title']}':\n---\n{raw_response}\n---")

            parsed_json = _parse_llm_json_response(raw_response, article['title'])
            if parsed_json and parsed_json.get('is_relevant'):
                return {"title": article['title'], "link": article['link'], "analysis": parsed_json}
            else:
                logging.info(f"LLM determined '{article['title']}' is not relevant. Discarding.")
                return None

        except Exception as e:
            # This catches errors from ainvoke (e.g., API key issues, network problems)
            logging.error(f"Error during AI analysis for '{article['title']}'. Reason: {e}")
            return None


async def run_speculator_async(
        articles: List[Article],
        ai_chain: Runnable,
        config: AppConfig
) -> List[AnalysisResult]:
    """
    Asynchronously analyzes a list of relevant articles to produce summaries and scores.
    Controls concurrency to avoid overwhelming services.
    """
    logging.info("=" * 80)
    logging.info("Speculator Module: Concurrently analyzing relevant articles...")
    logging.info("=" * 80)

    concurrency_limit = config.speculator_settings.concurrency_limit
    semaphore = asyncio.Semaphore(concurrency_limit)

    async with ClientSession() as session:
        tasks = [
            _analyze_single_article(session, article, ai_chain, config, semaphore)
            for article in articles
        ]
        results = await asyncio.gather(*tasks)

    # Filter out any None results from failed analyses
    final_analyses = [res for res in results if res is not None]
    logging.info(f"Speculator finished. Produced {len(final_analyses)} final analyses from {len(articles)} candidates.")
    return final_analyses


def run_speculator(articles: List[Article], ai_chain: Runnable, config: AppConfig) -> List[AnalysisResult]:
    """Synchronous wrapper to run the async speculator function."""
    # Ensure ai_chain is a Runnable, as the old version had 'Any'
    if not isinstance(ai_chain, Runnable):
        logging.error("Speculator received an invalid AI chain object. Cannot proceed.")
        return []
    return asyncio.run(run_speculator_async(articles, ai_chain, config))
