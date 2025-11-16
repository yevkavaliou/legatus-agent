import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

import aiohttp
import trafilatura
from langchain_community.tools import QuerySQLDatabaseTool
from langchain_community.utilities import SQLDatabase
from langchain_core.tools import Tool

from .constants import DEFAULT_SPECULATOR_USER_AGENT, DEFAULT_SPECULATOR_TIMEOUT
from .utils import should_verify_ssl_for_url


def create_web_fetcher_tool(config: Dict[str, Any]) -> Tool:
    """
    Factory function that creates the web article content fetching tool.

    This pattern allows the tool's logic to access the application's runtime
    configuration for settings like user-agent, timeout, and SSL verification.

    Args:
        config: The application's configuration dictionary.

    Returns:
        A configured LangChain Tool for fetching web content.
    """
    speculator_config = config.get('speculator_settings', {})
    user_agent = speculator_config.get('user_agent', DEFAULT_SPECULATOR_USER_AGENT)
    timeout = speculator_config.get('timeout', DEFAULT_SPECULATOR_TIMEOUT)
    skip_ssl_domains = config.get('security', {}).get('skip_ssl_verify', [])

    async def _fetch_article_content_logic(url: str) -> str:
        """
        Asynchronously fetches and extracts the main text content from an article's URL.

        This coroutine is the underlying implementation for the fetch_web_article_content tool.

        Args:
            url: The URL of the article to fetch.

        Returns:
            The cleaned text content of the article, or an error message string on failure.
        """
        logging.info(f"Fetching article content from URL: {url}")
        headers = {'User-Agent':user_agent}
        ssl_context = should_verify_ssl_for_url(url, skip_ssl_domains)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=timeout, ssl=ssl_context) as response:
                    response.raise_for_status()
                    html_content = await response.text()

                    loop = asyncio.get_running_loop()
                    text_content = await loop.run_in_executor(
                        None, lambda: trafilatura.extract(html_content, include_comments=False, include_tables=False)
                    )

                    if text_content:
                        return text_content
                    else:
                        logging.warning(f"trafilatura could not extract content from {url}")
                        return "Content could not be extracted from the page. It might be a video, a PDF, or a JavaScript-heavy site."

        except asyncio.TimeoutError:
            logging.error(f"Timeout while fetching content from {url}.")
            return f"Error: The request to the URL '{url}' timed out."
        except aiohttp.ClientError as e:
            logging.error(f"Network error fetching content from {url}. Reason: {e}")
            return f"Error: A network error occurred while fetching the URL: {e}"
        except Exception as e:
            logging.error(f"Unexpected error fetching content from {url}. Reason: {e}", exc_info=True)
            return f"Error: An unexpected error occurred: {e}"

    return Tool(
        name="fetch_web_article_content",
        func=None,
        coroutine=_fetch_article_content_logic,
        description=(
            "Use this tool to get the full, cleaned text content of an article from its URL. "
            "This is useful ONLY when you have a specific URL and need to read the full text content of that article. "
            "It is for reading web pages. DO NOT use this tool to query the database of archived articles. "
            "The input MUST be a valid URL string."
        ),
    )



def create_sql_query_tool(db_path: Path) -> Tool:
    """
    Creates a tool for querying the articles database.

    This function now directly accepts the database path, making it decoupled
    from the application's configuration.

    Args:
        db_path: The absolute path to the SQLite database file.

    Returns:
        A LangChain Tool configured to query the specified database.
    """
    logging.info(f"Initializing SQL Query Tool for database at: {db_path}")

    if not db_path.is_file():
        # This error will be passed to the LLM if it tries to use the tool.
        error_message = (
            f"Database file not found at the configured path: {db_path}. "
            "Please ensure the Legatus agent has run successfully to create the database."
        )
        logging.error(error_message)

        # A dummy tool that returns an error, so the agent can report the problem.
        def dummy_func(*args: Any, **kwargs: Any) -> str:
            return error_message

        return Tool(
            name="articles_database_query",
            func=dummy_func,
            description=f"This tool is currently disabled. {error_message}"
        )

    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    sql_tool = QuerySQLDatabaseTool(db=db)

    sql_tool.description = (
        "Use this tool to execute a SQLite query against the articles database. "
        "Input MUST be a single, valid SQLite query. "
        "The database schema is: CREATE TABLE articles("
        "link (TEXT, PRIMARY KEY), title (TEXT), criticality_score (INTEGER), reported_at (TIMESTAMP). "
        "Example: To find the title of the most critical article, input:"        
        'SELECT title FROM articles ORDER BY criticality_score DESC LIMIT 1'
    )
    sql_tool.name = "articles_database_query"
    return sql_tool
