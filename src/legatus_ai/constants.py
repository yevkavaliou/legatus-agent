# ===================================================================
#                      ENVIRONMENT VARIABLE KEYS
# ===================================================================
# The key for the GitHub API token in the .env file.
GITHUB_TOKEN_ENV_VAR = "GITHUB_TOKEN"


# ===================================================================
#                     DEFAULT CONFIGURATION VALUES
# ===================================================================
# These values are used as fallbacks if they are not specified in config.yaml.

# --- Vigil Settings ---
DEFAULT_EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
DEFAULT_SIMILARITY_THRESHOLD = 0.30

# --- Scout Settings ---
DEFAULT_SCOUT_USER_AGENT = "LegatusScout/1.0"
DEFAULT_SCOUT_TIMEOUT = 20  # seconds

# --- Speculator Settings ---
DEFAULT_SPECULATOR_USER_AGENT = "LegatusSpeculator/1.0"
DEFAULT_SPECULATOR_TIMEOUT = 30  # seconds
DEFAULT_CONCURRENCY_LIMIT = 5

# --- Notarius Settings ---
DEFAULT_REPORT_FORMAT = "csv"
