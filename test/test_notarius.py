# In test_notarius.py

import unittest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from src.legatus_ai.notarius import generate_report


class TestNotarius(unittest.TestCase):

    def setUp(self):
        self.mock_analysis_results = [
            {'title': 'Article B', 'analysis': {'criticality_score': 5}},
            {'title': 'Article A', 'analysis': {'criticality_score': 3}},
        ]
        self.mock_output_dir = Path("/mock/reports")

    # Patch the two filesystem interactions of the main function
    @patch('src.legatus_ai.notarius.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_report_writes_csv(self, mock_file_open, mock_mkdir):
        """
        Tests that generate_report correctly creates a CSV file.
        """
        print("\nTesting Notarius CSV report generation...")

        mock_config = {"notarius_settings": {"format": "csv"}}

        # Use a with statement to patch the DictWriter for this test
        with patch("src.legatus_ai.notarius.csv.DictWriter") as mock_csv_writer:
            mock_writer_instance = MagicMock()
            mock_csv_writer.return_value = mock_writer_instance

            # --- ACT ---
            generate_report(mock_config, self.mock_output_dir, self.mock_analysis_results)

            # --- ASSERT ---
            # 1. Verify the directory was created
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

            # 2. Verify the file was opened for writing
            mock_file_open.assert_called_once()
            opened_filepath = mock_file_open.call_args.args[0]
            self.assertTrue(opened_filepath.name.endswith('.csv'))

            # 3. Verify the CSV writer was used correctly
            mock_writer_instance.writeheader.assert_called_once()
            self.assertEqual(mock_writer_instance.writerow.call_count, 2)

            # 4. Verify data was sorted correctly before writing
            first_row_data = mock_writer_instance.writerow.call_args_list[0].args[0]
            self.assertEqual(first_row_data['Title'], 'Article B')

    @patch('src.legatus_ai.notarius.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_report_writes_json(self, mock_file_open, mock_mkdir):
        """
        Tests that generate_report correctly creates a JSON file.
        """
        print("\nTesting Notarius JSON report generation...")

        mock_config = {"notarius_settings": {"format": "json"}}

        with patch("src.legatus_ai.notarius.json.dump") as mock_json_dump:
            # --- ACT ---
            generate_report(mock_config, self.mock_output_dir, self.mock_analysis_results)

            # --- ASSERT ---
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_file_open.assert_called_once()
            opened_filepath = mock_file_open.call_args.args[0]
            self.assertTrue(opened_filepath.name.endswith('.json'))

            # Verify json.dump was called with sorted data
            mock_json_dump.assert_called_once()
            dump_args = mock_json_dump.call_args.args[0]
            self.assertEqual(dump_args['analyses'][0]['title'], 'Article B')

    # This test needs no file system patches as it should exit early
    def test_generate_report_handles_empty_results(self):
        """
        Tests that no file operations occur if the analysis results are empty.
        """
        print("\nTesting Notarius with empty results...")

        mock_config = {"notarius_settings": {"format": "csv"}}

        with patch('src.legatus_ai.notarius.Path.mkdir') as mock_mkdir, \
                patch('builtins.open') as mock_file_open:
            generate_report(mock_config, self.mock_output_dir, [])

            mock_mkdir.assert_not_called()
            mock_file_open.assert_not_called()


if __name__ == '__main__':
    unittest.main()
