import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch

# Import the functions to be tested
from src.legatus_ai.archivum import add_articles_to_archive, filter_new_articles, initialize_database

# Define a mock path for the database. The value doesn't matter as it will be mocked.
MOCK_DB_PATH = Path("/mock/db.sqlite")


class TestArchivum(unittest.TestCase):

    def setUp(self):
        """
        Set up a clean, in-memory database connection before each test.
        The table schema will be created within the test method itself.
        """
        self.conn = sqlite3.connect(":memory:")

    def tearDown(self):
        """Close the database connection after each test to clean up resources."""
        self.conn.close()

    @patch('src.legatus_ai.archivum.get_db_connection')
    def test_add_and_filter_articles(self, mock_get_connection):
        """
        Tests that articles can be added and the filtering logic correctly
        identifies new vs. existing articles.
        """
        print("\nTesting Archivum add and filter logic...")

        # --- ARRANGE ---
        # 1. Configure the mock to return our real, in-memory connection.
        mock_get_connection.return_value = self.conn

        #    This ensures the CREATE TABLE statement runs on self.conn.
        initialize_database(MOCK_DB_PATH)

        # 3. Define test data
        initial_analyses = [
            {'link': 'http://a.com', 'title': 'Article A', 'analysis': {'criticality_score': 3}},
            {'link': 'http://b.com', 'title': 'Article B', 'analysis': {'criticality_score': 5}}
        ]
        candidate_articles = [
            {'link': 'http://a.com', 'title': 'Article A'},
            {'link': 'http://c.com', 'title': 'Article C'}
        ]

        # --- ACT & ASSERT (Part 1: Adding) ---
        add_articles_to_archive(MOCK_DB_PATH, initial_analyses)

        # Verify the data was inserted correctly using our direct connection.
        # This will now work because the 'articles' table exists in self.conn.
        cursor = self.conn.cursor()
        cursor.execute("SELECT link, criticality_score FROM articles ORDER BY link")
        results = cursor.fetchall()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], ('http://a.com', 3))
        self.assertEqual(results[1], ('http://b.com', 5))

        # --- ACT & ASSERT (Part 2: Filtering) ---
        new_articles = filter_new_articles(MOCK_DB_PATH, candidate_articles)

        # Verify that only the new article was returned
        self.assertEqual(len(new_articles), 1)
        self.assertEqual(new_articles[0]['link'], 'http://c.com')

        # Verify that the mock was called as expected.
        # It's called once by initialize_database, once by add_articles_to_archive,
        # and once by filter_new_articles.
        self.assertEqual(mock_get_connection.call_count, 3)


if __name__ == '__main__':
    unittest.main()
