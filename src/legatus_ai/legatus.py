import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv
from langchain_core.runnables import Runnable
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage
from langchain_google_vertexai import ChatVertexAI
from langchain_ollama import ChatOllama

from .archivum import initialize_database, filter_new_articles, add_articles_to_archive
from .context_generator import generate_full_context
from .notarius import generate_report
from .speculator import run_speculator
from .constants import GITHUB_TOKEN_ENV_VAR
from .paths import resolve_paths
from .utils import get_project_root
from .vigil import filter_articles
from .scout import run_scout


class ConfigError(Exception):
    """Custom exception for configuration-related errors."""
    pass


def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Loads the main YAML config file.

    Args:
        config_path: Path to the configuration file.

    Returns:
        A dictionary containing the configuration.

    Raises:
        ConfigError: If the config file is not found or cannot be parsed.
    """
    if not config_path.is_file():
        error_msg = (
            f"FATAL: Configuration file '{config_path}' not found.\n"
            "This application is designed to run with a mounted config file.\n"
            "To run this agent, please follow these steps:\n"
            "  1. Create a 'config.yaml' file on your host machine.\n"
            "     (You can use 'config.yaml.example' as a template).\n"
            "  2. Run the Docker container with a volume mount, like this:\n"
            '     docker run --rm -it -v "$(pwd)/config.yaml:/app/config.yaml" legatus-agent'
        )
        logging.error("=" * 80)
        logging.error(error_msg)
        logging.error("=" * 80)
        raise ConfigError(error_msg)

    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        logging.error(f"Could not parse YAML configuration: {e}")
        raise ConfigError(f"YAML parsing error in {config_path}: {e}") from e


def initialize_ai_chain(config: Dict[str, Any], context_string: str, prompt_path: Path) -> Optional[Runnable]:
    """
    Initializes a single, pre-primed AI chain with the system prompt and context.

    Args:
        config: The application configuration dictionary.
        context_string: The JSON string representing the project context.
        prompt_path: Path to the user prompt template file.

    Returns:
        A LangChain Runnable object, or None if initialization fails.
    """
    ai_settings = config.get('ai_settings', {})
    legatus_config = ai_settings.get('legatus_agent')
    provider = legatus_config.get('provider')
    provider_config = ai_settings.get('providers', {}).get(provider, {})

    system_prompt = (
        "You are an expert AI assistant for an Android Tech Lead. "
        "Your goal is to analyze technical articles and provide a brutally honest, actionable assessment. "
        "You are pragmatic and laser-focused on the project's needs. "
        "Respond ONLY with a single, valid JSON object as requested.\n\n"
        "This is the context for the project you are assisting:"
        f"{context_string}"
    )

    llm: Optional[ChatOllama | ChatVertexAI] = None
    if provider == "google":
        model_name = provider_config.get('model', 'gemini-2.5-flash')
        project_id = provider_config.get('project_id')
        if not project_id:
            logging.warning(f"Google provider selected but 'project_id' is not configured.")
            return None
        llm = ChatVertexAI(
            project_id=project_id,
            model_name=model_name,
            temperature=legatus_config.get('temperature', 0.2),
            convert_system_message_to_human=True
        )
    elif provider == "ollama":
        llm = ChatOllama(
            model=legatus_config.get('model', 'llama3.1'),
            base_url=provider_config.get('base_url'),
            temperature=legatus_config.get('temperature', 0.2),
            format="json",
        )

    if not llm:
        logging.warning(f"AI provider '{provider}' is not configured correctly or is unsupported.")
        return None

    try:
        user_prompt_template = prompt_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logging.error(f"Critical prompt file not found at '{prompt_path}'.")
        return None

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        ("user", user_prompt_template)
    ])

    return prompt | llm | StrOutputParser()


def _log_summary(project_context: Dict, found_articles: List, relevant_articles: List, new_articles: List,
                 final_analyses: List):
    """Logs the final execution summary."""
    logging.info("=" * 80)
    logging.info("  Execution Summary")
    logging.info("=" * 80)
    logging.info(f"Project Dependencies Identified: {len(project_context.get('dependencies', []))}")
    logging.info(f"Potential Articles Found: {len(found_articles)}")
    logging.info(f"Relevant Articles (Vigilum Filter): {len(relevant_articles)}")
    logging.info(f"New Articles (Archive Check): {len(new_articles)}")
    logging.info(f"Final Analyses (Speculator): {len(final_analyses)}")

    if not final_analyses:
        logging.info("No new, relevant articles were found to analyze.")
        return

    logging.info("--- DETAILED ANALYSIS ---")
    sorted_analyses = sorted(
        final_analyses,
        key=lambda x: x.get('analysis', {}).get('criticality_score', 0),
        reverse=True
    )
    for report in sorted_analyses:
        analysis = report.get('analysis', {})
        title = report.get('title', 'N/A')
        link = report.get('link', '#')
        score = analysis.get('criticality_score', 'N/A')
        justification = analysis.get('justification', 'No justification provided.')
        summary = analysis.get('summary', 'No summary provided.')

        logging.info(f"\nTitle: {title}")
        logging.info(f"Link: {link}")
        logging.info(f"Criticality: {score}/5 - {justification}")
        logging.info(f"Summary: {summary}")
        logging.info("-" * 25)


def legatus_main():
    """Main orchestration function for the Legatus pipeline."""
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)-8s - %(name)-12s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    try:
        paths = resolve_paths(get_project_root())

        config = load_config(paths.config)
        initialize_database(paths.database)
    except Exception as e:
        logging.critical(f"Could not initialize the database. Exiting. Error: {e}")
        raise SystemExit(1) from e

    logging.info("Legatus: Starting AI Deps Analyst...")
    is_debug = config.get('debug', False)
    if is_debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug(">>> DEBUG MODE ENABLED <<<")

    # --- Stage 1: Context Generation ---
    project_context = generate_full_context(config, paths.version_catalog)
    context_for_llm = project_context.copy()
    context_for_llm.pop('embedding', None)
    context_for_prompt = json.dumps(context_for_llm, indent=2, default=list)
    logging.debug(f"Full Project Context:\n{context_for_prompt}")

    # --- Stage 2: Initialize Shared AI Chain ---
    ai_chain = initialize_ai_chain(config, context_for_prompt, paths.legatus_prompt)

    # --- Stage 3: Scout - Gather raw data ---
    github_token = os.getenv(GITHUB_TOKEN_ENV_VAR)
    found_articles = run_scout(config, github_token)

    # --- Stage 4: Vigilum - Filter by relevance ---
    relevant_articles = filter_articles(found_articles, project_context, config)

    # --- Stage 5: Archivum - Filter out already-reported articles
    new_relevant_articles = filter_new_articles(paths.database, relevant_articles)

    # --- Stage 6: Speculator - Perform deep analysis ---
    final_analyses = []
    if new_relevant_articles and ai_chain:
        final_analyses = run_speculator(new_relevant_articles, ai_chain, config)
    elif not ai_chain:
        logging.warning("AI chain not initialized, skipping LLM analysis.")

    if final_analyses:
        # --- Stage 7: Notarius - Generate and save the report
        generate_report(config, paths.report_dir, final_analyses)
        # --- Stage 8: Archivum - Save new analyses to memory
        add_articles_to_archive(paths.database, final_analyses)

    _log_summary(project_context, found_articles, relevant_articles, new_relevant_articles, final_analyses)


if __name__ == "__main__":
    legatus_main()
