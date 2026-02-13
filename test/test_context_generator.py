import unittest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the function to be tested
from src.legatus_ai.context_generator import generate_full_context
from src.legatus_ai.constants import DEFAULT_EMBEDDING_MODEL

# Import AppConfig to build typed mock configs
from src.legatus_ai.config import AppConfig


class TestContextGenerator(unittest.TestCase):

    # Patch the functions where they are *used* (in the context_generator module)
    @patch('src.legatus_ai.context_generator.SentenceTransformer')
    @patch('src.legatus_ai.context_generator._parse_version_catalog')
    def test_generate_full_context_with_catalog(self, mock_parse_vc, mock_sentence_transformer):
        """
        Tests that the main context generator correctly assembles data
        from the config and the version catalog parser when it is enabled.
        """
        print("\nTesting full context generation (with version catalog)...")

        # --- ARRANGE ---
        # 1. Define mock outputs for the patched functions.
        mock_parse_vc.return_value = {"retrofit:2.9.0", "compose-ui:1.6.0"}

        mock_model_instance = MagicMock()
        dummy_embedding = np.array([0.1, 0.2, 0.3])
        mock_model_instance.encode.return_value = dummy_embedding
        mock_sentence_transformer.return_value = mock_model_instance

        # 2. Create a typed config.
        mock_config = AppConfig.model_validate({
            "project_info": {
                "context": "This is a test project.",
                "build_config": {"minSdk": 24, "targetSdk": 34},
                "capabilities": {"permissions": ["android.permission.INTERNET"]},
                "dependency_sources": {
                    "version_catalog_file": {"enabled": True},
                    "manual_keywords": ["gradle"]
                }
            },
            "ai_settings": {
                "embedding_model": "mock-embedding-model"
            }
        })

        # 3. Define the mock path that will be passed to the function.
        mock_catalog_path = Path("/mock/project/libs.versions.toml")

        # --- ACT ---
        # Call the function with the new, correct signature.
        result_context = generate_full_context(mock_config, mock_catalog_path)

        # --- ASSERT ---
        # Verify that the parser was called with the correct Path object.
        mock_parse_vc.assert_called_once_with(mock_catalog_path)

        # Verify the narrative and structured data from the config.
        self.assertEqual(result_context['narrative'], "This is a test project.")
        self.assertEqual(result_context['build_config']['minSdk'], 24)
        self.assertIn("android.permission.INTERNET", result_context['capabilities']['permissions'])

        # Verify that dependencies from all sources are present.
        final_deps = result_context['dependencies']
        self.assertIn("retrofit:2.9.0", final_deps)  # From mocked parser
        self.assertIn("compose-ui:1.6.0", final_deps)  # From mocked parser
        self.assertIn("gradle", final_deps)  # From manual keywords

        # Verify the embedding model was initialized and used correctly.
        mock_sentence_transformer.assert_called_once_with("mock-embedding-model")
        mock_model_instance.encode.assert_called_once()
        self.assertIn('embedding', result_context)
        self.assertTrue(np.array_equal(result_context['embedding'], dummy_embedding))

    @patch('src.legatus_ai.context_generator.SentenceTransformer')
    @patch('src.legatus_ai.context_generator._parse_version_catalog')
    def test_generate_full_context_without_catalog(self, mock_parse_vc, mock_sentence_transformer):
        """
        Tests that the version catalog parser is NOT called if the catalog_path is None.
        """
        print("\nTesting full context generation (without version catalog)...")

        # --- ARRANGE ---
        mock_model_instance = MagicMock()
        mock_model_instance.encode.return_value = np.array([0.1, 0.2, 0.3])
        mock_sentence_transformer.return_value = mock_model_instance

        # Config where version catalog is enabled, but we will pass a None path
        mock_config = AppConfig.model_validate({
            "project_info": {
                "context": "A simple project.",
                "dependency_sources": {
                    "version_catalog_file": {"enabled": True},
                    "manual_keywords": ["gradle"]
                }
            },
            "ai_settings": {}  # Use default embedding model
        })

        # --- ACT ---
        # Call the function, explicitly passing None for the catalog_path.
        result_context = generate_full_context(mock_config, None)

        # --- ASSERT ---
        mock_parse_vc.assert_not_called()

        # Verify that only manual keywords are in the dependencies.
        self.assertEqual(result_context['dependencies'], {"gradle"})

        # Verify the default embedding model was used.
        mock_sentence_transformer.assert_called_once_with(DEFAULT_EMBEDDING_MODEL)


if __name__ == '__main__':
    unittest.main()
