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
REPO_TO_COMPONENT_DELAY = 15  # Seconds for GitHub indexing before creating components
MAX_RETRY_ATTEMPTS = 3  # Maximum retry attempts for component creation
RETRY_BACKOFF_BASE = 5  # Base seconds for exponential backoff on retries

# Default CloudBees endpoint ID (can be overridden in environment config)
DEFAULT_CLOUDBEES_ENDPOINT_ID = "9a3942be-0e86-415e-94c5-52512be1138d"
