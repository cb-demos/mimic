"""Simple settings for Mimic CLI."""

from importlib.metadata import PackageNotFoundError, version


def get_version():
    """Get the current version of mimic."""
    try:
        return version("mimic")
    except PackageNotFoundError:
        # Fallback for development when package isn't installed
        return "dev"


# Application metadata
APP_NAME = "Mimic"
VERSION = get_version()

# Timing configuration for resource creation
REPO_BASIC_DELAY = 3  # Seconds to wait for basic repo availability

# Repository sync polling configuration
REPO_SYNC_INITIAL_INTERVAL = 5  # Initial interval between sync checks (seconds)
REPO_SYNC_MAX_INTERVAL = 30  # Maximum interval between sync checks (seconds)
REPO_SYNC_TIMEOUT = 300  # Maximum time to wait for repository sync (5 minutes)

# Retry configuration
MAX_RETRY_ATTEMPTS = 3  # Maximum retry attempts for component creation
RETRY_BACKOFF_BASE = 5  # Base seconds for exponential backoff on retries

# Default CloudBees endpoint ID (can be overridden in environment config)
DEFAULT_CLOUDBEES_ENDPOINT_ID = "9a3942be-0e86-415e-94c5-52512be1138d"

# Official scenario pack configuration
OFFICIAL_PACK_NAME = "official"
OFFICIAL_PACK_URL = "https://github.com/cb-demos/mimic-scenarios"
OFFICIAL_PACK_BRANCH = "main"
