import logging
from pathlib import Path
from typing import Set, Dict, Any, Optional

import toml
from sentence_transformers import SentenceTransformer

from .constants import DEFAULT_EMBEDDING_MODEL

# A set of known Gradle plugin aliases that don't have a 'name' or 'module' property
# and can be safely ignored to prevent spurious warnings.
IGNORED_CATALOG_ALIASES = frozenset(['android-gradleApiPlugin', 'compose-gradlePlugin'])


def _parse_version_catalog(catalog_path: Path) -> Set[str]:
    """
    Parses a Gradle Version Catalog (.toml) file to extract library names.

    Args:
        catalog_path: The absolute path to the .toml version catalog file.

    Returns:
        A set of dependency strings in the format "name:version" or "name".
    """
    dependencies: Set[str] = set()
    try:
        catalog = toml.load(catalog_path)
        versions = catalog.get('versions', {})
        libraries = catalog.get('libraries', {})

        for lib_alias, lib_data in libraries.items():
            name = None
            version = None

            if 'name' in lib_data:
                name = lib_data.get('name')
            elif 'module' in lib_data:
                # Format: module = "group:name"
                module_str = lib_data.get('module', '')
                if ':' in module_str:
                    name = module_str.split(':')[1]

            version_value = lib_data.get('version')
            if isinstance(version_value, str):
                version = version_value # Direct version: version = "1.2.3"
            elif isinstance(version_value, dict):
                # Referenced version: version.ref = "someVersion"
                version_ref = version_value.get('ref')
                if version_ref:
                    version = versions.get(version_ref)

            if name and version:
                dependencies.add(f"{name}:{version}")
            elif name:
                dependencies.add(name)
            else:
                if lib_alias not in IGNORED_CATALOG_ALIASES:
                    logging.warning(f"Could not determine name for alias '{lib_alias}' in '{catalog_path}'.")


    except FileNotFoundError:
        logging.warning(f"Version catalog file not found at '{catalog_path}'. Skipping.")
    except toml.TomlDecodeError as e:
        logging.warning(f"Could not parse TOML file '{catalog_path}': {e}. Skipping.")
    return dependencies


def generate_full_context(config: Dict[str, Any], catalog_path: Optional[Path]) -> Dict[str, Any]:
    """
    Generates the full, rich project context object from all configured sources.

    This includes manual configuration, parsed dependency files, and a generated
    semantic embedding of the entire context.

    Args:
        config: The application configuration dictionary.
        catalog_path: Optional path to the project's .toml version catalog file.

    Returns:
        A dictionary representing the full project context, including the embedding.
    """
    logging.info("=" * 80)
    logging.info("Context Generator: Building full project fingerprint...")
    logging.info("=" * 80)

    project_info = config.get('project_info', {})
    full_context = {
        "narrative": project_info.get('context', ''),
        "build_config": project_info.get('build_config', {}),
        "capabilities": project_info.get('capabilities', {}),
        "dependencies": set(project_info.get('dependency_sources', {}).get('manual_keywords', []))
    }

    dep_sources = project_info.get('dependency_sources', {})
    vc_config = dep_sources.get('version_catalog_file', {})
    if vc_config.get('enabled') and catalog_path is not None:
        logging.info(f"Parsing dependencies from version catalog: {catalog_path}")
        full_context["dependencies"].update(_parse_version_catalog(catalog_path))
    else:
        logging.info("Version catalog parsing is disabled or no path is configured.")

    # Generate the semantic embedding for the project context
    logging.info("Generating project context embedding...")
    narrative = full_context.get('narrative', '')
    dependencies_str = ' '.join(full_context.get('dependencies', set()))
    full_text_context = f"Project focus: {narrative}. Key technologies and libraries used: {dependencies_str}"

    model_name = config.get('ai_settings', {}).get('embedding_model', DEFAULT_EMBEDDING_MODEL)
    logging.info(f"Using embedding model: {model_name}")

    model = SentenceTransformer(model_name)
    context_embedding = model.encode(full_text_context)
    full_context['embedding'] = context_embedding
    logging.debug(f"Generated project embedding with shape: {context_embedding.shape}")

    logging.info("Context generation complete.")
    return full_context
