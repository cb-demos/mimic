"""Scenario pack management for loading scenarios from git repositories."""

import logging
import re
import subprocess
from pathlib import Path

from mimic.exceptions import ScenarioError

logger = logging.getLogger(__name__)


def is_git_url(location: str) -> bool:
    """Check if location is a valid Git URL.

    Args:
        location: Location string to check.

    Returns:
        True if the location is a Git URL, False otherwise.
    """
    git_patterns = [
        r"^https?://",  # HTTP(S)
        r"^git@",  # SSH (git@github.com:...)
        r"^ssh://",  # SSH (ssh://...)
        r"^git://",  # Git protocol
    ]
    return any(re.match(pattern, location) for pattern in git_patterns)


def is_local_path(location: str) -> bool:
    """Check if location is a local filesystem path.

    Args:
        location: Location string to check.

    Returns:
        True if the location is a local path, False otherwise.
    """
    # Check for file:// scheme
    if location.startswith("file://"):
        return True

    # Check for common path patterns
    if location.startswith(("/", "~", ".")):
        return True

    # Try to resolve as Path
    try:
        path = Path(location).expanduser().resolve()
        return path.exists()
    except (OSError, ValueError):
        return False


def normalize_local_path(location: str) -> str:
    """Normalize a local path to file:// scheme format.

    Args:
        location: Local path string.

    Returns:
        Normalized path with file:// scheme.
    """
    if location.startswith("file://"):
        return location

    # Expand and resolve the path
    path = Path(location).expanduser().resolve()
    return f"file://{path}"


def local_path_from_url(url: str) -> Path:
    """Extract local path from file:// URL.

    Args:
        url: URL with file:// scheme.

    Returns:
        Path object representing the local path.
    """
    if not url.startswith("file://"):
        raise ValueError(f"Not a file:// URL: {url}")

    path_str = url.replace("file://", "")
    return Path(path_str)


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

    def register_local_pack(self, name: str, local_path: str) -> Path:
        """Register a local scenario pack via symlink.

        Args:
            name: Name to use for the pack directory.
            local_path: Absolute path to the local scenario pack directory.

        Returns:
            Path to the symlink in the packs directory.

        Raises:
            ScenarioError: If pack already exists or local path is invalid.
        """
        pack_path = self.packs_dir / name

        # Check if pack already exists
        if pack_path.exists():
            raise ScenarioError(
                f"Pack '{name}' already exists at {pack_path}. "
                "Remove it first before adding a new pack with the same name."
            )

        # Validate local path
        local = Path(local_path).expanduser().resolve()
        if not local.exists():
            raise ScenarioError(f"Local path does not exist: {local}")

        if not local.is_dir():
            raise ScenarioError(f"Local path is not a directory: {local}")

        logger.info(f"Registering local scenario pack '{name}' from {local}")

        try:
            # Create symlink to local directory
            pack_path.symlink_to(local)
            logger.info(f"Successfully registered local pack '{name}'")
            return pack_path

        except (OSError, NotImplementedError) as e:
            # Symlinks may not be supported (e.g., Windows without developer mode)
            error_msg = (
                f"Failed to create symlink for pack '{name}': {e}. "
                "Symlinks may not be supported on your system."
            )
            logger.error(error_msg)
            raise ScenarioError(error_msg) from e

    def clone_pack(self, name: str, url: str, branch: str = "main") -> Path:
        """Clone a scenario pack from a git repository or register a local path.

        Args:
            name: Name to use for the pack directory.
            url: Git URL to clone from (supports HTTPS and SSH) or file:// URL for local paths.
            branch: Branch to checkout (default: main, ignored for local paths).

        Returns:
            Path to the cloned pack directory or symlink.

        Raises:
            ScenarioError: If operation fails or URL format is invalid.
        """
        # Detect if this is a local path
        if url.startswith("file://"):
            local_path = local_path_from_url(url)
            return self.register_local_pack(name, str(local_path))

        # Otherwise, treat as Git URL
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

    def update_pack(
        self,
        name: str,
        pr_number: int | None = None,
        head_branch: str | None = None,
        head_repo_url: str | None = None,
    ) -> None:
        """Update a scenario pack by pulling latest changes.

        For local packs (symlinks), this operation is a no-op since changes
        are instantly reflected through the symlink.

        Args:
            name: Name of the pack to update.
            pr_number: Optional PR number if pack is tracking a PR.
            head_branch: Optional branch name for PR.
            head_repo_url: Optional fork URL for PRs from forks.

        Raises:
            ScenarioError: If pack doesn't exist or git pull fails.
        """
        pack_path = self.packs_dir / name

        if not pack_path.exists():
            raise ScenarioError(
                f"Pack '{name}' not found at {pack_path}. "
                "Use clone_pack() to add it first."
            )

        # Check if this is a local pack (symlink)
        if pack_path.is_symlink():
            logger.info(
                f"Pack '{name}' is a local pack - changes are instantly reflected, no update needed"
            )
            return

        logger.info(f"Updating scenario pack '{name}'")

        try:
            # If tracking a PR, fetch from the appropriate source
            if pr_number and head_branch:
                if head_repo_url:
                    # PR from fork - fetch from fork into FETCH_HEAD
                    logger.info(f"Fetching latest from fork: {head_repo_url}")
                    subprocess.run(
                        ["git", "fetch", head_repo_url, head_branch],
                        cwd=pack_path,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    # Reset current branch to FETCH_HEAD
                    subprocess.run(
                        ["git", "reset", "--hard", "FETCH_HEAD"],
                        cwd=pack_path,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                else:
                    # PR from same repo - fetch PR ref into FETCH_HEAD
                    subprocess.run(
                        ["git", "fetch", "origin", f"pull/{pr_number}/head"],
                        cwd=pack_path,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    # Reset current branch to FETCH_HEAD
                    subprocess.run(
                        ["git", "reset", "--hard", "FETCH_HEAD"],
                        cwd=pack_path,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                logger.info(f"Successfully updated pack '{name}' from PR")
            else:
                # Regular branch - pull latest changes
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

        For local packs (symlinks), only the symlink is removed, not the original directory.
        For git packs, the entire directory is removed.

        Args:
            name: Name of the pack to remove.

        Raises:
            ScenarioError: If pack doesn't exist.
        """
        pack_path = self.packs_dir / name

        if not pack_path.exists():
            raise ScenarioError(f"Pack '{name}' not found at {pack_path}")

        logger.info(f"Removing scenario pack '{name}'")

        # Handle symlinks (local packs) differently
        if pack_path.is_symlink():
            pack_path.unlink()
            logger.info(f"Successfully removed local pack symlink '{name}'")
        else:
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

    def get_current_branch(self, name: str) -> str | None:
        """Get the current checked out branch for a pack.

        Args:
            name: Pack name.

        Returns:
            Current branch name or None if pack doesn't exist or is not a git repo.
        """
        pack_path = self.packs_dir / name
        if not pack_path.exists() or pack_path.is_symlink():
            return None

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=pack_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def get_current_commit(self, name: str) -> str | None:
        """Get the current commit SHA for a pack.

        Args:
            name: Pack name.

        Returns:
            Current commit SHA or None if pack doesn't exist or is not a git repo.
        """
        pack_path = self.packs_dir / name
        if not pack_path.exists() or pack_path.is_symlink():
            return None

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=pack_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def switch_branch(self, name: str, branch: str, force: bool = True) -> None:
        """Switch a pack to a different branch.

        Args:
            name: Pack name.
            branch: Target branch name.
            force: If True, discard local changes (default: True).

        Raises:
            ScenarioError: If pack doesn't exist, is a symlink, or git operations fail.
        """
        pack_path = self.packs_dir / name

        if not pack_path.exists():
            raise ScenarioError(f"Pack '{name}' not found at {pack_path}")

        if pack_path.is_symlink():
            raise ScenarioError(
                f"Pack '{name}' is a local pack (symlink). "
                "Branch switching is only available for git packs."
            )

        logger.info(f"Switching pack '{name}' to branch '{branch}'")

        try:
            # Fetch latest from remote
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=pack_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Switch to branch (force if requested)
            switch_cmd = ["git", "checkout"]
            if force:
                switch_cmd.append("-f")
            switch_cmd.append(branch)

            subprocess.run(
                switch_cmd,
                cwd=pack_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Pull latest changes
            subprocess.run(
                ["git", "pull", "origin", branch],
                cwd=pack_path,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(f"Successfully switched pack '{name}' to branch '{branch}'")

        except subprocess.CalledProcessError as e:
            error_msg = (
                f"Failed to switch pack '{name}' to branch '{branch}': {e.stderr}"
            )
            logger.error(error_msg)
            raise ScenarioError(error_msg) from e

    def checkout_pr(
        self,
        name: str,
        pr_number: int,
        head_branch: str,
        head_repo_url: str | None = None,
    ) -> None:
        """Check out a pull request branch for a pack.

        Args:
            name: Pack name.
            pr_number: Pull request number.
            head_branch: PR head branch name.
            head_repo_url: Optional fork repository URL (for PRs from forks).
                          If provided, fetches from fork instead of upstream.

        Raises:
            ScenarioError: If pack doesn't exist, is a symlink, or git operations fail.
        """
        pack_path = self.packs_dir / name

        if not pack_path.exists():
            raise ScenarioError(f"Pack '{name}' not found at {pack_path}")

        if pack_path.is_symlink():
            raise ScenarioError(
                f"Pack '{name}' is a local pack (symlink). "
                "PR checkout is only available for git packs."
            )

        logger.info(f"Checking out PR #{pr_number} for pack '{name}'")

        try:
            if head_repo_url:
                # PR is from a fork - fetch the branch from the fork repository
                logger.info(
                    f"Fetching branch '{head_branch}' from fork: {head_repo_url}"
                )
                subprocess.run(
                    ["git", "fetch", head_repo_url, head_branch],
                    cwd=pack_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            else:
                # PR is from the same repo - use the PR ref
                subprocess.run(
                    ["git", "fetch", "origin", f"pull/{pr_number}/head"],
                    cwd=pack_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )

            # Checkout the PR branch (force create/reset branch to FETCH_HEAD)
            subprocess.run(
                ["git", "checkout", "-B", head_branch, "FETCH_HEAD"],
                cwd=pack_path,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(f"Successfully checked out PR #{pr_number} for pack '{name}'")

        except subprocess.CalledProcessError as e:
            error_msg = (
                f"Failed to checkout PR #{pr_number} for pack '{name}': {e.stderr}"
            )
            logger.error(error_msg)
            raise ScenarioError(error_msg) from e
