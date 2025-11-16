import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class ApplicationPaths:
    config: Path
    database: Path
    legatus_prompt: Path
    inquisitor_prompt: Path
    report_dir: Path
    version_catalog: Optional[Path]


def resolve_paths(project_root: Path) -> ApplicationPaths:
    """
    Resolves all application paths using an override-fallback strategy.

    It first checks for user-provided files in standard mount locations (e.g., /app/config.yaml).
    If a user file is not found, it falls back to a default, internal version.

    Args:
        project_root: The absolute path to the application's root.

    Returns:
        An ApplicationPaths object with all paths resolved.
    """
    user_config_path = project_root / "config.yaml"
    user_prompts_dir = project_root / "prompts"
    user_legatus_prompt = user_prompts_dir / "prompt_legatus.txt"
    user_inquisitor_prompt = user_prompts_dir / "prompt_inquisitor.txt"
    user_data_dir = project_root / "data"
    user_reports_dir = project_root / "reports"
    user_version_catalog = project_root / "project_data" / "libs.versions.toml"

    logging.info("Resolving application paths based on user mounts...")
    if user_config_path.is_file():
        logging.info(f"Found user-provided config at '{user_config_path}'.")
        config_path = user_config_path
    else:
        logging.info(f"User config not found. Using default config path in the root.")
        config_path = Path("config.yaml")

    if user_data_dir.is_dir():
        db_path = user_data_dir / "legatus_archive.db"
        logging.info(f"Found user-provided data dir at '{user_data_dir}'.")
    else:
        db_path = project_root / "data" / "legatus_archive.db"
        logging.info(f"User-provided data dir was not found, using default path for db '{db_path}'.")

    if Path(user_legatus_prompt).is_file():
        logging.info("Found user-provided prompts for Legatus.")
        legatus_prompt_path = user_legatus_prompt
    else:
        logging.info("Using default prompt for Legatus.")
        legatus_prompt_path = project_root / "src" / "legatus_ai" /"defaults" / "prompts" / "prompt_legatus.txt"

    if user_inquisitor_prompt.is_file():
        logging.info("Found user-provided prompts for Inquisitor.")
        inquisitor_prompt_path = user_inquisitor_prompt
    else:
        logging.info("Using default prompt for Inquisitor.")
        inquisitor_prompt_path = project_root / "src" / "legatus_ai" /"defaults" / "prompts" / "prompt_inquisitor.txt"

    if user_reports_dir.is_dir():
        logging.info(f"Found user-provided directory for reports at '{user_reports_dir}'.")
        reports_path = user_reports_dir
    else:
        reports_path = project_root / "reports"
        logging.info(f"Using default location for reports at '{reports_path}'.")

    if user_version_catalog.is_file():
        logging.info(f"Found .toml file for version catalog at '{user_version_catalog}'.")
        version_catalog_path = user_version_catalog
    else:
        logging.info(f"Version catalog file was not found, project context will miss this data.")
        version_catalog_path = None

    paths = ApplicationPaths(
        config=config_path,
        database=db_path,
        legatus_prompt=legatus_prompt_path,
        inquisitor_prompt=inquisitor_prompt_path,
        report_dir=reports_path,
        version_catalog=version_catalog_path
    )

    return paths
