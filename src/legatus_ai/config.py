"""
Centralised, validated application configuration.

All YAML keys are parsed once at startup into a typed Pydantic model.
Modules import ``AppConfig`` instead of passing raw dictionaries around.
"""

import logging
from pathlib import Path
from typing import Annotated, List, Optional

import yaml
from pydantic import BaseModel, BeforeValidator, Field


def _none_to_list(v: object) -> object:
    """YAML keys with only comments parse as ``None``; coerce to ``[]``."""
    return v if v is not None else []


# A ``List[str]`` that silently treats ``None`` as an empty list.
# This covers YAML entries like ``skip_ssl_verify:\n  # - example.com``
# where the key exists but the value is ``None``.
StrList = Annotated[List[str], BeforeValidator(_none_to_list)]

from .constants import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_SCOUT_USER_AGENT,
    DEFAULT_SCOUT_TIMEOUT,
    DEFAULT_SPECULATOR_USER_AGENT,
    DEFAULT_SPECULATOR_TIMEOUT,
    DEFAULT_CONCURRENCY_LIMIT,
    DEFAULT_REPORT_FORMAT,
    DEFAULT_SIMILARITY_THRESHOLD,
)


# ── project_info ──────────────────────────────────────────────────────

class BuildConfig(BaseModel):
    minSdk: int = 24
    targetSdk: int = 34
    compileSdk: int = 34
    build_features: StrList = Field(default_factory=list)


class Capabilities(BaseModel):
    permissions: StrList = Field(default_factory=list)
    features: StrList = Field(default_factory=list)


class VersionCatalogFile(BaseModel):
    enabled: bool = False


class DependencySources(BaseModel):
    version_catalog_file: VersionCatalogFile = Field(default_factory=VersionCatalogFile)
    manual_keywords: StrList = Field(default_factory=list)


class ProjectInfo(BaseModel):
    context: str = ""
    build_config: BuildConfig = Field(default_factory=BuildConfig)
    capabilities: Capabilities = Field(default_factory=Capabilities)
    dependency_sources: DependencySources = Field(default_factory=DependencySources)


# ── data_sources ──────────────────────────────────────────────────────

class DataSources(BaseModel):
    rss_feeds: StrList = Field(default_factory=list)
    github_releases: StrList = Field(default_factory=list)


# ── analysis_rules ────────────────────────────────────────────────────

class AnalysisRules(BaseModel):
    lookback_period_hours: int = 24
    vigil_similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD


# ── ai_settings ───────────────────────────────────────────────────────

class AgentConfig(BaseModel):
    provider: str = "ollama"
    temperature: float = 0.2
    model: str = "llama3.1"


class GoogleProviderConfig(BaseModel):
    model: str = "gemini-2.5-flash"
    project_id: Optional[str] = None


class OllamaProviderConfig(BaseModel):
    base_url: Optional[str] = None


class Providers(BaseModel):
    google: GoogleProviderConfig = Field(default_factory=GoogleProviderConfig)
    ollama: OllamaProviderConfig = Field(default_factory=OllamaProviderConfig)


class AISettings(BaseModel):
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    legatus_agent: AgentConfig = Field(default_factory=AgentConfig)
    inquisitor_agent: AgentConfig = Field(default_factory=lambda: AgentConfig(temperature=0.0))
    providers: Providers = Field(default_factory=Providers)


# ── module settings ───────────────────────────────────────────────────

class ScoutSettings(BaseModel):
    user_agent: str = DEFAULT_SCOUT_USER_AGENT
    timeout: int = DEFAULT_SCOUT_TIMEOUT


class SpeculatorSettings(BaseModel):
    user_agent: str = DEFAULT_SPECULATOR_USER_AGENT
    timeout: int = DEFAULT_SPECULATOR_TIMEOUT
    concurrency_limit: int = DEFAULT_CONCURRENCY_LIMIT


class NotariusSettings(BaseModel):
    format: str = DEFAULT_REPORT_FORMAT


class SecuritySettings(BaseModel):
    skip_ssl_verify: StrList = Field(default_factory=list)


# ── root config ───────────────────────────────────────────────────────

class ConfigError(Exception):
    """Raised when the configuration file cannot be found or parsed."""


class AppConfig(BaseModel):
    """Top-level application configuration – mirrors ``config.yaml``."""

    debug: bool = False
    project_info: ProjectInfo = Field(default_factory=ProjectInfo)
    data_sources: DataSources = Field(default_factory=DataSources)
    analysis_rules: AnalysisRules = Field(default_factory=AnalysisRules)
    ai_settings: AISettings = Field(default_factory=AISettings)
    scout_settings: ScoutSettings = Field(default_factory=ScoutSettings)
    speculator_settings: SpeculatorSettings = Field(default_factory=SpeculatorSettings)
    notarius_settings: NotariusSettings = Field(default_factory=NotariusSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    @classmethod
    def from_yaml(cls, config_path: Path) -> "AppConfig":
        """Load, parse and **validate** the YAML configuration file.

        Raises:
            ConfigError: If the file is missing or contains invalid YAML.
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
            with open(config_path, "r") as f:
                raw = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logging.error(f"Could not parse YAML configuration: {e}")
            raise ConfigError(f"YAML parsing error in {config_path}: {e}") from e

        return cls.model_validate(raw)
