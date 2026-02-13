import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Import the function to be tested AND the class we need to spec
from src.legatus_ai.speculator import run_speculator
from langchain_core.runnables import Runnable

# Import AppConfig to build typed mock configs
from src.legatus_ai.config import AppConfig


class TestSpeculator(unittest.TestCase):

    @patch('src.legatus_ai.speculator._analyze_single_article', new_callable=AsyncMock)
    def test_run_speculator_orchestrator(self, mock_analyze_single):
        """
        Tests that the run_speculator orchestrator correctly gathers results
        from its worker function and filters out failures (None results).
        """
        print("\nTesting Speculator's orchestration logic...")

        # --- ARRANGE ---
        mock_ai_chain = MagicMock(spec=Runnable)

        # 2. Define the return values for our mocked worker function.
        mock_success_result = {
            "title": "Relevant Article",
            "link": "http://a.com",
            "analysis": {"summary": "Relevant summary."}
        }
        mock_analyze_single.side_effect = [
            mock_success_result,
            None
        ]

        # 3. Define the input articles and the typed config.
        articles = [
            {'title': 'Relevant Article', 'link': 'http://a.com', 'summary': 'Summary 1'},
            {'title': 'Irrelevant Article', 'link': 'http://b.com', 'summary': 'Summary 2'}
        ]
        mock_config = AppConfig.model_validate({
            "speculator_settings": {
                "concurrency_limit": 1
            }
        })

        # --- ACT ---
        results = run_speculator(articles, mock_ai_chain, mock_config)

        # --- ASSERT ---
        # 1. Verify that the final list contains only the successful result.
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "Relevant Article")
        self.assertEqual(results[0]['analysis']['summary'], "Relevant summary.")

        # 2. Verify that the worker function was called for each article.
        self.assertEqual(mock_analyze_single.call_count, 2)

        # 3. Check the arguments of the first call to the worker.
        first_call_args = mock_analyze_single.call_args_list[0].args
        self.assertEqual(first_call_args[1], articles[0])
        self.assertEqual(first_call_args[2], mock_ai_chain)
        self.assertEqual(first_call_args[3], mock_config)


if __name__ == '__main__':
    unittest.main()
