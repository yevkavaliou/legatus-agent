import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Import the functions to be tested
from src.legatus_ai.tools import create_sql_query_tool, create_web_fetcher_tool


class TestTools(unittest.TestCase):

    @patch('src.legatus_ai.tools.aiohttp.ClientSession')
    def test_create_web_fetcher_tool(self, mock_client_session):
        """Tests the web content fetching tool created by the factory."""
        print("\nTesting create_web_fetcher_tool...")

        # --- ARRANGE ---
        # 1. Create the FINAL object: the mock response.
        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = AsyncMock(return_value="<html><body><p>Hello World</p></body></html>")

        # 2. Create the context manager that will produce the mock response.
        mock_response_cm = AsyncMock()
        mock_response_cm.__aenter__.return_value = mock_response

        # 3. Create the mock session object.
        mock_session = AsyncMock()

        mock_session.get = MagicMock(return_value=mock_response_cm)

        # 5. Configure the main patched class to produce the mock session
        #    when its context manager is entered.
        mock_client_session.return_value.__aenter__.return_value = mock_session

        # 6. Define a mock config for the factory
        mock_config = {
            "speculator_settings": {
                "user_agent": "TestAgent/1.0",
                "timeout": 10
            },
            "security": {"skip_ssl_verify": []}
        }

        # --- ACT ---
        web_fetcher_tool = create_web_fetcher_tool(mock_config)
        tool_coroutine = web_fetcher_tool.coroutine
        result = asyncio.run(tool_coroutine("http://example.com"))

        # --- ASSERT ---
        self.assertIn("Hello World", result)

        # Verify that the session's get method was called with configured values
        mock_session.get.assert_called_once()
        get_call_kwargs = mock_session.get.call_args.kwargs
        self.assertEqual(get_call_kwargs['headers']['User-Agent'], "TestAgent/1.0")
        self.assertEqual(get_call_kwargs['timeout'], 10)

    @patch('src.legatus_ai.tools.Path.is_file', return_value=True)
    @patch('src.legatus_ai.tools.SQLDatabase')
    @patch('src.legatus_ai.tools.QuerySQLDatabaseTool')
    def test_create_sql_query_tool_db_exists(self, mock_query_tool, mock_sql_db, mock_is_file):
        """
        Tests the creation of the SQL query tool when the database file exists.
        """
        print("\nTesting create_sql_query_tool (DB exists)...")

        # --- ARRANGE ---
        mock_db_path = Path("/mock/db.sqlite")
        # Get a reference to the *instance* that the mock class will create
        mock_tool_instance = mock_query_tool.return_value

        # --- ACT ---
        sql_tool = create_sql_query_tool(mock_db_path)

        # --- ASSERT ---
        # 1. Verify that the database connection and LangChain tool were initialized
        mock_sql_db.from_uri.assert_called_once_with(f"sqlite:///{mock_db_path}")
        mock_query_tool.assert_called_once()

        self.assertIn("execute a SQLite query", mock_tool_instance.description)

        # 3. Verify that the function returned the instance we expected
        self.assertEqual(sql_tool, mock_tool_instance)

    @patch('src.legatus_ai.tools.Path.is_file', return_value=False)
    def test_create_sql_query_tool_db_missing(self, mock_is_file):
        """
        Tests that a dummy tool is created if the database file is missing.
        """
        print("\nTesting create_sql_query_tool (DB missing)...")

        # --- ARRANGE ---
        mock_db_path = Path("/nonexistent/db.sqlite")

        # --- ACT ---
        dummy_tool = create_sql_query_tool(mock_db_path)

        # --- ASSERT ---
        # Verify the dummy tool has the correct name and a descriptive error
        self.assertEqual(dummy_tool.name, "articles_database_query")
        self.assertIn("Database file not found", dummy_tool.description)

        # Run the dummy tool's function to ensure it returns the error message
        error_message = dummy_tool.func()
        self.assertIn("Database file not found", error_message)


if __name__ == '__main__':
    unittest.main()
