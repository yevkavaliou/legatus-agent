import unittest
import textwrap
from pathlib import Path
from unittest.mock import patch, mock_open

from pydantic import ValidationError

from src.legatus_ai.config import (
    AppConfig,
    ConfigError,
    AISettings,
    AgentConfig,
    AnalysisRules,
    ScoutSettings,
    SpeculatorSettings,
    NotariusSettings,
    SecuritySettings,
    ProjectInfo,
    DataSources,
)
from src.legatus_ai.constants import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_SCOUT_USER_AGENT,
    DEFAULT_SCOUT_TIMEOUT,
    DEFAULT_SPECULATOR_USER_AGENT,
    DEFAULT_SPECULATOR_TIMEOUT,
    DEFAULT_CONCURRENCY_LIMIT,
    DEFAULT_REPORT_FORMAT,
    DEFAULT_SIMILARITY_THRESHOLD,
)


# ---------------------------------------------------------------------------
# A minimal valid YAML config that exercises every top-level section.
# ---------------------------------------------------------------------------
FULL_YAML = textwrap.dedent("""\
    debug: true
    project_info:
      context: "An Android app"
      build_config:
        minSdk: 21
        targetSdk: 35
        compileSdk: 35
        build_features:
          - "compose"
      capabilities:
        permissions:
          - "android.permission.INTERNET"
        features:
          - "android.hardware.camera"
      dependency_sources:
        version_catalog_file:
          enabled: true
        manual_keywords:
          - "gradle"
          - "kotlin"
    data_sources:
      rss_feeds:
        - "https://blog.example.com/feed"
      github_releases:
        - "owner/repo"
    analysis_rules:
      lookback_period_hours: 48
      vigil_similarity_threshold: 0.45
    ai_settings:
      embedding_model: "all-mpnet-base-v2"
      legatus_agent:
        provider: "google"
        temperature: 0.3
        model: "gemini-pro"
      inquisitor_agent:
        provider: "ollama"
        temperature: 0.0
        model: "mistral"
      providers:
        google:
          model: "gemini-2.5-flash"
          project_id: "my-project-123"
        ollama:
          base_url: "http://localhost:11434"
    scout_settings:
      user_agent: "TestScout/1.0"
      timeout: 15
    speculator_settings:
      user_agent: "TestSpeculator/1.0"
      timeout: 25
      concurrency_limit: 3
    notarius_settings:
      format: "json"
    security:
      skip_ssl_verify:
        - "insecure.example.com"
""")


class TestAppConfigDefaults(unittest.TestCase):
    """Ensure every field falls back to the correct default when YAML is empty."""

    def test_empty_dict_produces_all_defaults(self):
        """An empty YAML file (parsed as {}) should still yield a valid config."""
        print("\nTesting AppConfig with empty dict...")
        cfg = AppConfig.model_validate({})

        self.assertFalse(cfg.debug)
        self.assertEqual(cfg.project_info.context, "")
        self.assertEqual(cfg.data_sources.rss_feeds, [])
        self.assertEqual(cfg.data_sources.github_releases, [])
        self.assertEqual(cfg.analysis_rules.lookback_period_hours, 24)
        self.assertAlmostEqual(
            cfg.analysis_rules.vigil_similarity_threshold, DEFAULT_SIMILARITY_THRESHOLD
        )
        self.assertEqual(cfg.ai_settings.embedding_model, DEFAULT_EMBEDDING_MODEL)
        self.assertEqual(cfg.scout_settings.user_agent, DEFAULT_SCOUT_USER_AGENT)
        self.assertEqual(cfg.scout_settings.timeout, DEFAULT_SCOUT_TIMEOUT)
        self.assertEqual(cfg.speculator_settings.user_agent, DEFAULT_SPECULATOR_USER_AGENT)
        self.assertEqual(cfg.speculator_settings.timeout, DEFAULT_SPECULATOR_TIMEOUT)
        self.assertEqual(cfg.speculator_settings.concurrency_limit, DEFAULT_CONCURRENCY_LIMIT)
        self.assertEqual(cfg.notarius_settings.format, DEFAULT_REPORT_FORMAT)
        self.assertEqual(cfg.security.skip_ssl_verify, [])

    def test_default_agent_temperatures(self):
        """Legatus defaults to 0.2; Inquisitor defaults to 0.0."""
        print("\nTesting default agent temperatures...")
        cfg = AppConfig.model_validate({})
        self.assertAlmostEqual(cfg.ai_settings.legatus_agent.temperature, 0.2)
        self.assertAlmostEqual(cfg.ai_settings.inquisitor_agent.temperature, 0.0)

    def test_default_provider_values(self):
        """Provider sub-models should have the expected defaults."""
        print("\nTesting default provider values...")
        cfg = AppConfig.model_validate({})
        self.assertEqual(cfg.ai_settings.providers.google.model, "gemini-2.5-flash")
        self.assertIsNone(cfg.ai_settings.providers.google.project_id)
        self.assertIsNone(cfg.ai_settings.providers.ollama.base_url)


class TestAppConfigFullParse(unittest.TestCase):
    """Verify that a fully-populated YAML is parsed into the correct typed structure."""

    @patch("builtins.open", mock_open(read_data=FULL_YAML))
    @patch("src.legatus_ai.config.Path.is_file", return_value=True)
    def test_from_yaml_parses_all_sections(self, _mock_is_file):
        """from_yaml should populate every nested field correctly."""
        print("\nTesting from_yaml with full config...")
        cfg = AppConfig.from_yaml(Path("/mock/config.yaml"))

        # Root
        self.assertTrue(cfg.debug)

        # project_info
        self.assertEqual(cfg.project_info.context, "An Android app")
        self.assertEqual(cfg.project_info.build_config.minSdk, 21)
        self.assertEqual(cfg.project_info.build_config.targetSdk, 35)
        self.assertEqual(cfg.project_info.build_config.build_features, ["compose"])
        self.assertTrue(cfg.project_info.dependency_sources.version_catalog_file.enabled)
        self.assertIn("gradle", cfg.project_info.dependency_sources.manual_keywords)

        # data_sources
        self.assertEqual(cfg.data_sources.rss_feeds, ["https://blog.example.com/feed"])
        self.assertEqual(cfg.data_sources.github_releases, ["owner/repo"])

        # analysis_rules
        self.assertEqual(cfg.analysis_rules.lookback_period_hours, 48)
        self.assertAlmostEqual(cfg.analysis_rules.vigil_similarity_threshold, 0.45)

        # ai_settings
        self.assertEqual(cfg.ai_settings.embedding_model, "all-mpnet-base-v2")
        self.assertEqual(cfg.ai_settings.legatus_agent.provider, "google")
        self.assertAlmostEqual(cfg.ai_settings.legatus_agent.temperature, 0.3)
        self.assertEqual(cfg.ai_settings.inquisitor_agent.model, "mistral")
        self.assertEqual(cfg.ai_settings.providers.google.project_id, "my-project-123")
        self.assertEqual(cfg.ai_settings.providers.ollama.base_url, "http://localhost:11434")

        # module settings
        self.assertEqual(cfg.scout_settings.user_agent, "TestScout/1.0")
        self.assertEqual(cfg.scout_settings.timeout, 15)
        self.assertEqual(cfg.speculator_settings.concurrency_limit, 3)
        self.assertEqual(cfg.notarius_settings.format, "json")

        # security
        self.assertEqual(cfg.security.skip_ssl_verify, ["insecure.example.com"])


class TestAppConfigPartialYaml(unittest.TestCase):
    """Verify that a partially-populated YAML merges correctly with defaults."""

    def test_partial_config_fills_defaults(self):
        """Only override what is specified; the rest should be default."""
        print("\nTesting partial config...")
        cfg = AppConfig.model_validate({
            "debug": True,
            "analysis_rules": {"lookback_period_hours": 168},
        })

        self.assertTrue(cfg.debug)
        self.assertEqual(cfg.analysis_rules.lookback_period_hours, 168)
        # The threshold should still be the default
        self.assertAlmostEqual(
            cfg.analysis_rules.vigil_similarity_threshold, DEFAULT_SIMILARITY_THRESHOLD
        )
        # Entirely absent sections should be fully defaulted
        self.assertEqual(cfg.scout_settings.timeout, DEFAULT_SCOUT_TIMEOUT)
        self.assertEqual(cfg.ai_settings.legatus_agent.model, "llama3.1")

    def test_extra_keys_are_ignored(self):
        """Unknown YAML keys should not cause validation errors."""
        print("\nTesting extra keys are ignored...")
        cfg = AppConfig.model_validate({
            "unknown_future_key": "hello",
            "debug": True,
        })
        self.assertTrue(cfg.debug)


class TestAppConfigFromYamlErrors(unittest.TestCase):
    """Test error paths: missing file, bad YAML, and invalid types."""

    def test_missing_file_raises_config_error(self):
        """from_yaml should raise ConfigError when the file does not exist."""
        print("\nTesting ConfigError for missing file...")
        with self.assertRaises(ConfigError) as ctx:
            AppConfig.from_yaml(Path("/does/not/exist/config.yaml"))
        self.assertIn("not found", str(ctx.exception))

    @patch("builtins.open", mock_open(read_data=": bad: yaml: [[["))
    @patch("src.legatus_ai.config.Path.is_file", return_value=True)
    def test_malformed_yaml_raises_config_error(self, _mock_is_file):
        """from_yaml should raise ConfigError for unparseable YAML."""
        print("\nTesting ConfigError for malformed YAML...")
        with self.assertRaises(ConfigError) as ctx:
            AppConfig.from_yaml(Path("/mock/config.yaml"))
        self.assertIn("YAML parsing error", str(ctx.exception))

    @patch("builtins.open", mock_open(read_data="debug: 'not_a_bool_but_coerced'\n"))
    @patch("src.legatus_ai.config.Path.is_file", return_value=True)
    def test_wrong_type_for_nested_int_raises_validation_error(self, _mock_is_file):
        """Pydantic should reject a string where an int is expected."""
        print("\nTesting ValidationError for wrong nested type...")
        yaml_with_bad_type = textwrap.dedent("""\
            analysis_rules:
              lookback_period_hours: "not_a_number"
        """)
        with patch("builtins.open", mock_open(read_data=yaml_with_bad_type)):
            with self.assertRaises(ValidationError):
                AppConfig.from_yaml(Path("/mock/config.yaml"))

    @patch("builtins.open", mock_open(read_data=""))
    @patch("src.legatus_ai.config.Path.is_file", return_value=True)
    def test_empty_file_produces_defaults(self, _mock_is_file):
        """An empty YAML file (safe_load returns None) should yield all defaults."""
        print("\nTesting empty YAML file...")
        cfg = AppConfig.from_yaml(Path("/mock/config.yaml"))
        self.assertFalse(cfg.debug)
        self.assertEqual(cfg.scout_settings.timeout, DEFAULT_SCOUT_TIMEOUT)


class TestAppConfigFromExampleFile(unittest.TestCase):
    """Load the real config.yaml.example and verify it parses without errors."""

    def test_example_config_parses_successfully(self):
        """The shipped config.yaml.example should be valid and parseable."""
        print("\nTesting config.yaml.example parses...")
        example_path = Path(__file__).resolve().parent.parent / "config.yaml.example"
        if not example_path.is_file():
            self.skipTest(f"config.yaml.example not found at {example_path}")

        cfg = AppConfig.from_yaml(example_path)

        # Spot-check a few values from the example file
        self.assertFalse(cfg.debug)
        self.assertEqual(cfg.analysis_rules.lookback_period_hours, 72)
        self.assertEqual(cfg.ai_settings.legatus_agent.provider, "ollama")
        self.assertEqual(cfg.ai_settings.providers.google.project_id, "YOUR_GCP_PROJECT_ID_HERE")
        self.assertTrue(len(cfg.data_sources.rss_feeds) > 0)
        self.assertTrue(cfg.project_info.dependency_sources.version_catalog_file.enabled)


class TestSubModelsDirect(unittest.TestCase):
    """Test individual sub-models in isolation."""

    def test_agent_config_defaults(self):
        """AgentConfig should have sensible standalone defaults."""
        print("\nTesting AgentConfig defaults...")
        ac = AgentConfig()
        self.assertEqual(ac.provider, "ollama")
        self.assertEqual(ac.model, "llama3.1")
        self.assertAlmostEqual(ac.temperature, 0.2)

    def test_scout_settings_override(self):
        """ScoutSettings should accept overrides."""
        print("\nTesting ScoutSettings override...")
        ss = ScoutSettings(user_agent="CustomAgent/2.0", timeout=60)
        self.assertEqual(ss.user_agent, "CustomAgent/2.0")
        self.assertEqual(ss.timeout, 60)

    def test_speculator_settings_defaults(self):
        """SpeculatorSettings should use constants as defaults."""
        print("\nTesting SpeculatorSettings defaults...")
        sp = SpeculatorSettings()
        self.assertEqual(sp.user_agent, DEFAULT_SPECULATOR_USER_AGENT)
        self.assertEqual(sp.timeout, DEFAULT_SPECULATOR_TIMEOUT)
        self.assertEqual(sp.concurrency_limit, DEFAULT_CONCURRENCY_LIMIT)

    def test_security_settings_empty_list(self):
        """SecuritySettings should default to an empty skip list."""
        print("\nTesting SecuritySettings defaults...")
        sec = SecuritySettings()
        self.assertEqual(sec.skip_ssl_verify, [])

    def test_data_sources_model_dump(self):
        """DataSources.model_dump() should return a plain dict for iteration."""
        print("\nTesting DataSources model_dump...")
        ds = DataSources(rss_feeds=["https://a.com/feed"], github_releases=["owner/repo"])
        dumped = ds.model_dump()
        self.assertIsInstance(dumped, dict)
        self.assertIn("rss_feeds", dumped)
        self.assertIn("github_releases", dumped)
        self.assertEqual(dumped["rss_feeds"], ["https://a.com/feed"])


if __name__ == '__main__':
    unittest.main()
