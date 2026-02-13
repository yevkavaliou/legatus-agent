import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Import the function to be tested
from src.legatus_ai.inquisitor import inquisitor_main

# Import AppConfig to build typed mock configs
from src.legatus_ai.config import AppConfig

# To help with type hinting our mocks
from src.legatus_ai.paths import ApplicationPaths


class TestInquisitor(unittest.TestCase):

    # Patch the high-level functions that inquisitor_main orchestrates
    @patch('src.legatus_ai.inquisitor.interactive_loop', new_callable=AsyncMock)
    @patch('src.legatus_ai.inquisitor.assemble_agent')
    @patch('src.legatus_ai.inquisitor.initialize_llm')
    @patch('src.legatus_ai.config.AppConfig.from_yaml')
    @patch('src.legatus_ai.inquisitor.resolve_paths')
    @patch('src.legatus_ai.inquisitor.load_dotenv')
    def test_inquisitor_main_orchestration(
            self, mock_dotenv, mock_resolve_paths, mock_from_yaml,
            mock_init_llm, mock_assemble_agent, mock_interactive_loop
    ):
        """
        Tests the main orchestration and setup of the Inquisitor agent.
        """
        print("\nTesting Inquisitor main orchestration...")

        # --- ARRANGE ---
        # 1. Mock the return values for the setup functions
        mock_paths = ApplicationPaths(
            config=Path("/mock/config.yaml"),
            database=Path("/mock/data/db.sqlite"),
            legatus_prompt=Path("..."),
            inquisitor_prompt=Path("..."),
            report_dir=Path("..."),
            version_catalog=None
        )
        mock_resolve_paths.return_value = mock_paths

        mock_config = AppConfig.model_validate({"debug": True})
        mock_from_yaml.return_value = mock_config

        mock_llm = MagicMock(name="MockLLM")
        mock_init_llm.return_value = mock_llm

        mock_agent_executor = MagicMock(name="MockAgentExecutor")
        mock_assemble_agent.return_value = mock_agent_executor

        # --- ACT ---
        inquisitor_main()

        # --- ASSERT ---
        # 1. Verify that the setup functions were called in order and with the correct arguments
        mock_dotenv.assert_called_once()
        mock_resolve_paths.assert_called_once()
        mock_from_yaml.assert_called_once_with(mock_paths.config)
        mock_init_llm.assert_called_once_with(mock_config)
        mock_assemble_agent.assert_called_once_with(mock_llm, mock_config, mock_paths)

        # 2. Verify that the main interactive loop was started with the fully assembled agent
        mock_interactive_loop.assert_called_once()
        # Check that the first argument passed to the loop was our agent executor
        self.assertEqual(mock_interactive_loop.call_args.args[0], mock_agent_executor)

    @patch('src.legatus_ai.inquisitor.resolve_paths')
    @patch('src.legatus_ai.config.AppConfig.from_yaml')
    @patch('src.legatus_ai.inquisitor.logging')
    @patch('src.legatus_ai.inquisitor.Console')
    def test_inquisitor_setup_failure(
            self, mock_console, mock_logging, mock_from_yaml, mock_resolve_paths
    ):
        """
        Tests that a critical error is logged and printed if setup fails.
        """
        print("\nTesting Inquisitor setup failure handling...")

        # --- ARRANGE ---
        # Simulate a failure during config loading
        error_message = "Test config error"
        mock_from_yaml.side_effect = ValueError(error_message)

        # Mock the paths to allow the test to get to the failing part
        mock_paths = ApplicationPaths(config=Path("/mock/config.yaml"), database=Path("..."),
                                      legatus_prompt=Path("..."), inquisitor_prompt=Path("..."),
                                      report_dir=Path("..."), version_catalog=None)
        mock_resolve_paths.return_value = mock_paths

        # --- ACT ---
        inquisitor_main()

        # --- ASSERT ---
        # Verify that a critical error was logged
        mock_logging.critical.assert_called()
        # Verify that a fatal error message was printed to the console for the user
        mock_console.return_value.print.assert_called()
        # Check that the error message contains the word "FATAL"
        self.assertIn("FATAL", mock_console.return_value.print.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
