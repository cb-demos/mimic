"""Entry point for running mimic as a module: python -m mimic"""

# IMPORTANT: ensure_wsl_environment() must be called BEFORE importing app
# This is because the app imports ConfigManager, which accesses the keyring
from mimic.cli.main import ensure_wsl_environment

ensure_wsl_environment()

from mimic.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
