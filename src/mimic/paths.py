"""Path utilities for Mimic configuration and state files."""

import os
from pathlib import Path


def get_config_dir() -> Path:
    """Get config directory from environment or default.

    Checks MIMIC_CONFIG_DIR environment variable first, falls back to ~/.mimic

    Returns:
        Path to configuration directory.
    """
    if config_dir := os.environ.get("MIMIC_CONFIG_DIR"):
        return Path(config_dir)
    return Path.home() / ".mimic"
