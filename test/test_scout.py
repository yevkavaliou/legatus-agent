import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

# Import the functions to be tested
from src.legatus_ai.scout import _extract_summary, run_scout_async, fetch_from_rss_async


# We use a standard TestCase for the synchronous function _extract_summary
class TestScoutUtilities(unittest.TestCase):
    def test_extract_summary_priority(self):
        """Tests that the summary extraction prefers content > summary > description."""
        print("\nTesting summary extraction logic...")
        entry1 = SimpleNamespace(
            summary="This is the summary.",
            description="This is the description.",
            content=[SimpleNamespace(value="<p>This is <b>HTML</b> content.</p>")]
        )
        self.assertEqual(_extract_summary(entry1), "This is HTML content.")
        # ... (other test cases for summary extraction)


# We use IsolatedAsyncioTestCase for testing the async functions
class TestScoutAsyncOperations(unittest.IsolatedAsyncioTestCase):

    @patch('src.legatus_ai.scout.asyncio.get_running_loop')
    async def test_fetch_from_rss_async_success(self, mock_get_running_loop):
        """
        Tests the async RSS fetching function on a successful run.
        """
        print("\nTesting RSS fetching logic (successful run)...")

        # --- ARRANGE ---
        # 1. Mock the final parsed feed object
        mock_feed = MagicMock()
        mock_feed.bozo = 0
        mock_entry = SimpleNamespace(
            title="New Article", link="/new-post",
            published_parsed=(datetime.now(timezone.utc) - timedelta(hours=1)).timetuple(),
            summary="Article summary here.",
            tags=[SimpleNamespace(term="Kotlin")]
        )
        mock_feed.entries = [mock_entry]

        # 2. Mock the executor to return the parsed feed
        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_feed)
        mock_get_running_loop.return_value = mock_loop

        mock_session = MagicMock()

        # Create the mock response object that the context manager will yield.
        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value="dummy rss content")
        mock_response.raise_for_status.return_value = None

        # Create the async context manager mock.
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_response

        # Configure the synchronous .get() method to return our context manager.
        mock_session.get.return_value = mock_context_manager

        # 4. Define the config
        mock_config = {"analysis_rules": {"lookback_period_hours": 24}}

        # --- ACT ---
        articles = await fetch_from_rss_async(mock_session, mock_config, 'http://fake-feed.com/rss')

        # --- ASSERT ---
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['title'], 'New Article')
        mock_loop.run_in_executor.assert_called_once()

    @patch('src.legatus_ai.scout.SOURCE_FETCHER_MAP', new_callable=dict)
    async def test_run_scout_orchestrator_async(self, mock_fetcher_map):
        """
        Tests the async Scout orchestrator directly.
        """
        print("\nTesting Scout's async orchestrator...")

        # --- ARRANGE ---
        mock_rss_fetcher = AsyncMock(return_value=[{'title': 'RSS Article'}])
        mock_github_fetcher = AsyncMock(return_value=[{'title': 'GitHub Release'}])
        mock_fetcher_map["rss_feeds"] = mock_rss_fetcher
        mock_fetcher_map["github_releases"] = mock_github_fetcher

        mock_config = {
            "data_sources": {
                "rss_feeds": ["http://rss-url.com/feed"],
                "github_releases": ["owner/repo"]
            }
        }

        # --- ACT ---
        results = await run_scout_async(mock_config, "dummy_token")

        # --- ASSERT ---
        self.assertEqual(len(results), 2)

        mock_rss_fetcher.assert_called_once()
        self.assertEqual(mock_rss_fetcher.call_args.args[1], mock_config)
        self.assertEqual(mock_rss_fetcher.call_args.args[2], "http://rss-url.com/feed")

        mock_github_fetcher.assert_called_once()
        self.assertEqual(mock_github_fetcher.call_args.args[1], mock_config)
        self.assertEqual(mock_github_fetcher.call_args.args[2], "owner/repo")


if __name__ == '__main__':
    unittest.main()
