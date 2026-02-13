import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Callable

from .config import AppConfig

# A simple type alias for clarity
AnalysisResult = Dict[str, Any]


def _write_csv_report(output_path: Path, analysis_results: List[AnalysisResult]):
    """Writes the analysis results to a CSV file."""
    headers = [
        "Title",
        "Link",
        "Criticality",
        "Justification",
        "Summary",
        "Reported_At_UTC"
    ]
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            for report in analysis_results:
                analysis = report.get('analysis', {})
                writer.writerow({
                    "Title": report.get('title', 'N/A'),
                    "Link": report.get('link', '#'),
                    "Criticality": analysis.get('criticality_score', 'N/A'),
                    "Justification": analysis.get('justification', 'No justification provided.'),
                    "Summary": analysis.get('summary', 'No summary provided.'),
                    "Reported_At_UTC": datetime.now(timezone.utc).isoformat()
                })
        logging.info(f"Successfully generated CSV report at: {output_path}")
    except IOError as e:
        logging.error(f"Failed to write CSV report to {output_path}. Reason: {e}")


def _write_json_report(output_path: Path, analysis_results: List[AnalysisResult]):
    """Writes the analysis results to a JSON file."""
    # Add a top-level metadata key for context
    report_data = {
        "report_generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "article_count": len(analysis_results),
        "analyses": analysis_results
    }
    try:
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(report_data, jsonfile, indent=2)
        logging.info(f"Successfully generated JSON report at: {output_path}")
    except IOError as e:
        logging.error(f"Failed to write JSON report to {output_path}. Reason: {e}")


_REPORT_WRITERS: Dict[str, Callable[[Path, List[AnalysisResult]], None]] = {
    "csv": _write_csv_report,
    "json": _write_json_report,
}


def generate_report(config: AppConfig, output_path: Path, analysis_results: List[AnalysisResult]):
    """
    Generates a user-facing report from the analysis results.

    Sorts the results by criticality and uses the format and path specified
    in the configuration.

    Args:
        config: The validated application configuration.
        output_path: The output path for reports.
        analysis_results: A list of analysis dictionaries from the Speculator.
    """
    if not analysis_results:
        logging.info("No analysis results to report. Skipping report generation.")
        return

    report_format = config.notarius_settings.format.lower()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    final_report_path = (output_path / f"legatus_report_{timestamp}.{report_format}").resolve()

    # Ensure the parent directory for the report exists
    try:
        final_report_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logging.error(f"Could not create directory for report at '{output_path.parent}'. Error: {e}")
        return

    # Sort results by criticality, highest first, for a more readable report
    sorted_results = sorted(
        analysis_results,
        key=lambda x: x.get('analysis', {}).get('criticality_score', 0),
        reverse=True
    )

    logging.info(f"Generating '{report_format}' report for {len(sorted_results)} articles...")

    if writer_func := _REPORT_WRITERS.get(report_format):
        writer_func(final_report_path, sorted_results)
    else:
        logging.error(
            f"Unknown report format '{report_format}' specified in config. "
            f"Available formats are: {list(_REPORT_WRITERS.keys())}"
        )
