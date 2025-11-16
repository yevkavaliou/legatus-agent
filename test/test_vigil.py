import unittest
from unittest.mock import patch, MagicMock
import torch
import numpy as np

# Import the function to be tested
from src.legatus_ai.vigil import filter_articles


class TestVigil(unittest.TestCase):

    def setUp(self):
        """Reset the model cache before each test to ensure isolation."""
        # We need to patch the global cache variable in the vigil module
        self.cache_patcher = patch('src.legatus_ai.vigil._model_cache', None)
        self.cache_patcher.start()

    def tearDown(self):
        """Stop the patcher."""
        self.cache_patcher.stop()

    @patch('src.legatus_ai.vigil.util.cos_sim')
    @patch('src.legatus_ai.vigil.SentenceTransformer')
    def test_filter_articles_semantically(self, mock_sentence_transformer, mock_cos_sim):
        """Tests Vigil's semantic filtering based on a configurable threshold."""
        print("\nTesting Vigil semantic filtering...")

        # --- ARRANGE ---
        mock_model_instance = MagicMock()
        mock_model_instance.encode.return_value = torch.tensor([])  # Return a tensor
        mock_sentence_transformer.return_value = mock_model_instance

        # Scores: [Relevant, Irrelevant, Also Relevant]
        mock_scores = torch.tensor([[0.8, 0.2, 0.5]])
        mock_cos_sim.return_value = mock_scores

        articles = [
            {'title': 'Relevant Article', 'link': 'http://a.com', 'summary': '...'},
            {'title': 'Irrelevant Article', 'link': 'http://b.com', 'summary': '...'},
            {'title': 'Also Relevant Article', 'link': 'http://c.com', 'summary': '...'}
        ]
        mock_context = {"embedding": np.array([0.1, 0.2])}  # Use a real numpy array

        # Define a mock config that sets the threshold to 0.4
        mock_config = {
            "analysis_rules": {
                "vigil_similarity_threshold": 0.4
            },
            "ai_settings": {
                "embedding_model": "mock-model-name"
            }
        }

        # --- ACT ---
        # Call the function with the new, correct signature
        filtered = filter_articles(articles, mock_context, mock_config)

        # --- ASSERT ---
        # Verify the correct, configurable model name was used
        mock_sentence_transformer.assert_called_once_with("mock-model-name")
        mock_model_instance.encode.assert_called_once()

        # Verify cosine similarity was called correctly
        self.assertEqual(mock_cos_sim.call_count, 1)

        # With a threshold of 0.4, two articles should pass (0.8 and 0.5)
        self.assertEqual(len(filtered), 2)
        kept_titles = {a['title'] for a in filtered}
        self.assertIn('Relevant Article', kept_titles)
        self.assertIn('Also Relevant Article', kept_titles)
        self.assertNotIn('Irrelevant Article', kept_titles)

        # Verify the relevance score was added to the article
        self.assertAlmostEqual(filtered[0]['relevance_score'], 0.8, places=5)

    @patch('src.legatus_ai.vigil._get_embedding_model')  # Mock the whole model loader
    def test_deduplication_logic(self, mock_get_model):
        """Tests that duplicate articles (by link) are removed."""
        print("\nTesting Vigil deduplication logic...")

        # --- ARRANGE ---
        # Mock the model and similarity calculation to focus only on deduplication
        mock_cos_sim_patcher = patch('src.legatus_ai.vigil.util.cos_sim')
        mock_cos_sim = mock_cos_sim_patcher.start()
        # Pretend all articles are highly relevant
        mock_cos_sim.return_value = torch.tensor([[0.9, 0.9, 0.9]])

        # Article list with a duplicate link
        articles = [
            {'title': 'Article A', 'link': 'http://a.com', 'summary': 'First instance'},
            {'title': 'Article B', 'link': 'http://b.com', 'summary': 'Unique'},
            {'title': 'Article A Duplicate', 'link': 'http://a.com', 'summary': 'Second instance'}
        ]
        mock_context = {"embedding": np.array([0.1, 0.2])}
        mock_config = {"analysis_rules": {"vigil_similarity_threshold": 0.5}}

        # --- ACT ---
        filtered = filter_articles(articles, mock_context, mock_config)

        # --- ASSERT ---
        self.assertEqual(len(filtered), 2)  # Should keep A and B, discard the duplicate A

        # Verify that the *first* instance of the duplicated article was kept
        kept_links = {a['link']: a for a in filtered}
        self.assertEqual(kept_links['http://a.com']['summary'], 'First instance')

        mock_cos_sim_patcher.stop()


if __name__ == '__main__':
    unittest.main()
