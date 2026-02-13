import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the function we are testing
from src.legatus_ai.legatus import legatus_main

# Import AppConfig to build typed mock configs
from src.legatus_ai.config import AppConfig

# To help with type hinting our mocks
from src.legatus_ai.paths import ApplicationPaths


class TestLegatusOrchestration(unittest.TestCase):

    # The patch order is reversed from the argument order.
    # The innermost function call to patch is the rightmost argument.
    @patch('src.legatus_ai.legatus.load_dotenv')
    @patch('src.legatus_ai.legatus.logging.basicConfig')
    @patch('src.legatus_ai.legatus.resolve_paths')
    @patch('src.legatus_ai.config.AppConfig.from_yaml')
    @patch('src.legatus_ai.legatus.initialize_database')
    @patch('src.legatus_ai.legatus.generate_full_context')
    @patch('src.legatus_ai.legatus.initialize_ai_chain')
    @patch('src.legatus_ai.legatus.os.getenv')
    @patch('src.legatus_ai.legatus.run_scout')
    @patch('src.legatus_ai.legatus.filter_articles')
    @patch('src.legatus_ai.legatus.filter_new_articles')
    @patch('src.legatus_ai.legatus.run_speculator')
    @patch('src.legatus_ai.legatus.generate_report')
    @patch('src.legatus_ai.legatus.add_articles_to_archive')
    def test_legatus_full_run_with_new_articles(
            self, mock_add_archive, mock_gen_report, mock_speculator,
            mock_filter_new, mock_filter_articles, mock_scout, mock_getenv,
            mock_init_chain, mock_gen_context, mock_init_db, mock_from_yaml,
            mock_resolve_paths, mock_logging, mock_dotenv
    ):
        """
        Tests the full orchestration of legatus.py when new articles are found and analyzed.
        """
        print("\nTesting Legatus orchestration (full run)...")

        # --- ARRANGE ---
        # 1. Create a typed config that matches the expected structure.
        mock_config = AppConfig.model_validate({
            'debug': False,
            'ai_settings': {
                'legatus_agent': {
                    'provider': 'ollama',
                    'model': 'mock-model',
                    'temperature': 0.1
                },
                'providers': {
                    'ollama': {'base_url': 'http://mock-url'},
                    'google': {'project_id': 'mock-project'}
                }
            }
        })
        mock_from_yaml.return_value = mock_config

        # 2. Mock the core paths returned by resolve_paths
        mock_paths = ApplicationPaths(
            config=Path("/mock/app/config.yaml"),
            database=Path("/mock/app/data/mock_db.sqlite"),
            legatus_prompt=Path("/mock/app/prompts/legatus.txt"),
            inquisitor_prompt=Path("/mock/app/prompts/inquisitor.txt"),
            report_dir=Path("/mock/app/reports"),
            version_catalog=Path("/mock/app/project/libs.versions.toml")
        )
        mock_resolve_paths.return_value = mock_paths

        # 3. Mock the return values for each stage of the pipeline
        mock_getenv.return_value = "dummy_github_token"
        mock_gen_context.return_value = {'dependencies': {'dep1'}, 'embedding': 'mock_embedding'}
        mock_init_chain.return_value = MagicMock()  # A mock runnable chain
        mock_scout.return_value = [{'title': 'Article from Scout'}]
        mock_filter_articles.return_value = [{'title': 'Article from Vigil'}]
        mock_filter_new.return_value = [{'title': 'New Article from Archivum'}]
        mock_speculator.return_value = [{'title': 'Final Analysis'}]

        # --- ACT ---
        legatus_main()

        # --- ASSERT ---
        # Verify initialization
        mock_resolve_paths.assert_called_once()
        mock_from_yaml.assert_called_once_with(mock_paths.config)
        mock_init_db.assert_called_once_with(mock_paths.database)

        # Verify context and AI chain setup
        mock_gen_context.assert_called_once_with(mock_config, mock_paths.version_catalog)
        mock_init_chain.assert_called_once()

        # Verify pipeline stages are called with correct data
        mock_scout.assert_called_once_with(mock_config, "dummy_github_token")
        mock_filter_articles.assert_called_once_with(
            mock_scout.return_value,
            mock_gen_context.return_value,
            mock_config
        )
        mock_filter_new.assert_called_once_with(mock_paths.database, mock_filter_articles.return_value)
        mock_speculator.assert_called_once_with(
            mock_filter_new.return_value,
            mock_init_chain.return_value,
            mock_config
        )

        # Verify final reporting and archiving stages
        mock_gen_report.assert_called_once_with(mock_config, mock_paths.report_dir, mock_speculator.return_value)
        mock_add_archive.assert_called_once_with(mock_paths.database, mock_speculator.return_value)


if __name__ == '__main__':
    unittest.main()
