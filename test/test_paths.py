import unittest
from pathlib import Path
from unittest.mock import patch

# Import the function and dataclass to be tested
from src.legatus_ai.paths import resolve_paths, ApplicationPaths


class TestPaths(unittest.TestCase):

    def setUp(self):
        """Define a mock project root for all tests."""
        self.mock_project_root = Path("/mock/app")

    @patch('src.legatus_ai.paths.Path.is_dir')
    @patch('src.legatus_ai.paths.Path.is_file')
    def test_paths_when_user_files_exist(self, mock_is_file, mock_is_dir):
        """
        Tests that paths resolve to user-provided locations when they exist.
        """
        print("\nTesting path resolution (user overrides exist)...")

        mock_is_file.return_value = True
        mock_is_dir.return_value = True

        paths = resolve_paths(self.mock_project_root)

        self.assertEqual(paths.config, self.mock_project_root / "config.yaml")
        self.assertEqual(paths.database, self.mock_project_root / "data" / "legatus_archive.db")
        self.assertEqual(paths.legatus_prompt, self.mock_project_root / "prompts" / "prompt_legatus.txt")
        self.assertEqual(paths.inquisitor_prompt, self.mock_project_root / "prompts" / "prompt_inquisitor.txt")
        self.assertEqual(paths.report_dir, self.mock_project_root / "reports")
        self.assertEqual(paths.version_catalog, self.mock_project_root / "project_data" / "libs.versions.toml")

    @patch('src.legatus_ai.paths.Path.is_dir')
    @patch('src.legatus_ai.paths.Path.is_file')
    def test_paths_when_user_files_are_missing(self, mock_is_file, mock_is_dir):
        """
        Tests that paths resolve to internal fallback locations when user files are missing.
        """
        print("\nTesting path resolution (fallbacks)...")

        mock_is_file.return_value = False
        mock_is_dir.return_value = False

        paths = resolve_paths(self.mock_project_root)

        self.assertEqual(paths.config, Path("config.yaml"))
        self.assertEqual(paths.database, self.mock_project_root / "data" / "legatus_archive.db")
        self.assertEqual(paths.legatus_prompt,
                         self.mock_project_root / "src/legatus_ai/defaults/prompts/prompt_legatus.txt")
        self.assertEqual(paths.inquisitor_prompt,
                         self.mock_project_root / "src/legatus_ai/defaults/prompts/prompt_inquisitor.txt")
        self.assertEqual(paths.report_dir, self.mock_project_root / "reports")
        self.assertIsNone(paths.version_catalog)

    @patch('src.legatus_ai.paths.Path.is_dir')
    @patch('src.legatus_ai.paths.Path.is_file')
    def test_paths_mixed_scenario(self, mock_is_file, mock_is_dir):
        """
        Tests a mixed scenario where some user files exist and some do not.
        """
        print("\nTesting path resolution (mixed user/default)...")

        # --- ARRANGE ---
        # The mock will return the next item from this list each time it's called.
        # The order must match the order of calls in the resolve_paths function.
        mock_is_file.side_effect = [
            True,  # 1. user_config_path.is_file() -> True (user config exists)
            True,  # 2. user_legatus_prompt.is_file() -> True (user prompt exists)
            False,  # 3. user_inquisitor_prompt.is_file() -> False (fallback)
            False  # 4. user_version_catalog.is_file() -> False (fallback)
        ]

        # is_dir is called for data and reports directories.
        # Let's say neither exists.
        mock_is_dir.side_effect = [
            False,  # 1. user_data_dir.is_dir() -> False (fallback)
            False  # 2. user_reports_dir.is_dir() -> False (fallback)
        ]

        # --- ACT ---
        paths = resolve_paths(self.mock_project_root)

        # --- ASSERT ---
        # Verify the paths match our simulated scenario.
        self.assertEqual(paths.config, self.mock_project_root / "config.yaml")  # User override
        self.assertEqual(paths.legatus_prompt,
                         self.mock_project_root / "prompts" / "prompt_legatus.txt")  # User override

        self.assertEqual(paths.database, self.mock_project_root / "data" / "legatus_archive.db")  # Fallback
        self.assertEqual(paths.inquisitor_prompt,
                         self.mock_project_root / "src/legatus_ai/defaults/prompts/prompt_inquisitor.txt")  # Fallback
        self.assertEqual(paths.report_dir, self.mock_project_root / "reports")  # Fallback
        self.assertIsNone(paths.version_catalog)  # Fallback


if __name__ == '__main__':
    unittest.main()
