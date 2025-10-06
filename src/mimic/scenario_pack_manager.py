"""Scenario pack management for loading scenarios from git repositories."""

import logging
import subprocess
from pathlib import Path

from mimic.exceptions import ScenarioError

logger = logging.getLogger(__name__)


class ScenarioPackManager:
    """Manages scenario packs from git repositories."""

    def __init__(self, packs_dir: Path):
        """Initialize the scenario pack manager.

        Args:
            packs_dir: Directory to store scenario packs.
        """
        self.packs_dir = packs_dir
        self._ensure_packs_dir()

    def _ensure_packs_dir(self) -> None:
        """Ensure the packs directory exists."""
        self.packs_dir.mkdir(parents=True, exist_ok=True)

    def clone_pack(self, name: str, url: str, branch: str = "main") -> Path:
        """Clone a scenario pack from a git repository.

        Args:
            name: Name to use for the pack directory.
            url: Git URL to clone from (supports HTTPS and SSH).
            branch: Branch to checkout (default: main).

        Returns:
            Path to the cloned pack directory.

        Raises:
            ScenarioError: If git clone fails.
        """
        pack_path = self.packs_dir / name

        # Check if pack already exists
        if pack_path.exists():
            raise ScenarioError(
                f"Pack '{name}' already exists at {pack_path}. "
                "Use update_pack() to update it or remove it first."
            )

        logger.info(f"Cloning scenario pack '{name}' from {url}")

        try:
            # Clone the repository
            result = subprocess.run(
                ["git", "clone", "--branch", branch, url, str(pack_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.debug(f"Git clone output: {result.stdout}")
            logger.info(f"Successfully cloned pack '{name}'")
            return pack_path

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to clone pack '{name}' from {url}: {e.stderr}"
            logger.error(error_msg)
            # Clean up partial clone if it exists
            if pack_path.exists():
                import shutil

                shutil.rmtree(pack_path)
            raise ScenarioError(error_msg) from e

    def update_pack(self, name: str) -> None:
        """Update a scenario pack by pulling latest changes.

        Args:
            name: Name of the pack to update.

        Raises:
            ScenarioError: If pack doesn't exist or git pull fails.
        """
        pack_path = self.packs_dir / name

        if not pack_path.exists():
            raise ScenarioError(
                f"Pack '{name}' not found at {pack_path}. "
                "Use clone_pack() to add it first."
            )

        logger.info(f"Updating scenario pack '{name}'")

        try:
            # Pull latest changes
            result = subprocess.run(
                ["git", "pull"],
                cwd=pack_path,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.debug(f"Git pull output: {result.stdout}")
            logger.info(f"Successfully updated pack '{name}'")

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to update pack '{name}': {e.stderr}"
            logger.error(error_msg)
            raise ScenarioError(error_msg) from e

    def remove_pack(self, name: str) -> None:
        """Remove a scenario pack.

        Args:
            name: Name of the pack to remove.

        Raises:
            ScenarioError: If pack doesn't exist.
        """
        pack_path = self.packs_dir / name

        if not pack_path.exists():
            raise ScenarioError(f"Pack '{name}' not found at {pack_path}")

        logger.info(f"Removing scenario pack '{name}'")

        import shutil

        shutil.rmtree(pack_path)
        logger.info(f"Successfully removed pack '{name}'")

    def get_pack_path(self, name: str) -> Path | None:
        """Get the path to a scenario pack.

        Args:
            name: Name of the pack.

        Returns:
            Path to the pack directory, or None if it doesn't exist.
        """
        pack_path = self.packs_dir / name
        return pack_path if pack_path.exists() else None

    def list_installed_packs(self) -> list[str]:
        """List all installed scenario packs.

        Returns:
            List of pack names (directory names in packs_dir).
        """
        if not self.packs_dir.exists():
            return []

        return [
            d.name
            for d in self.packs_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
