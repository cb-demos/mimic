"""API endpoints for version checking and upgrades."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..dependencies import ConfigDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/version", tags=["version"])

# Cache for GitHub API responses (5 minute TTL)
_github_cache: dict[str, tuple[dict, datetime]] = {}
CACHE_TTL = timedelta(minutes=5)

GITHUB_REPO_OWNER = "cb-demos"
GITHUB_REPO_NAME = "mimic"
GITHUB_BRANCH = "main"


class VersionInfo(BaseModel):
    """Current version information."""

    version: str
    commit: str | None
    commit_short: str | None
    build_timestamp: str | None


class UpdateCheckResponse(BaseModel):
    """Update availability check response."""

    update_available: bool
    current_commit: str | None
    current_commit_short: str | None
    latest_commit: str | None
    latest_commit_short: str | None
    latest_commit_url: str | None
    message: str


class UpgradeResponse(BaseModel):
    """Upgrade operation response."""

    status: str
    message: str
    output: str | None = None


def _get_version_info() -> VersionInfo:
    """Load version information from version.json.

    Returns:
        VersionInfo object with current version data

    Raises:
        HTTPException: If version.json cannot be read
    """
    version_file = Path(__file__).parent.parent.parent / "version.json"

    if not version_file.exists():
        # Fallback if version.json doesn't exist (dev environment)
        logger.warning("version.json not found, using fallback version info")
        return VersionInfo(
            version="dev",
            commit=None,
            commit_short=None,
            build_timestamp=None,
        )

    try:
        with open(version_file) as f:
            data = json.load(f)
            return VersionInfo(
                version=data.get("version", "unknown"),
                commit=data.get("commit"),
                commit_short=data.get("commit_short"),
                build_timestamp=data.get("build_timestamp"),
            )
    except Exception as e:
        logger.error(f"Failed to read version.json: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read version information: {str(e)}",
        ) from e


async def _get_latest_commit_from_github() -> dict:
    """Fetch second-to-latest commit from GitHub API with caching.

    We fetch latest-1 because version.json is generated in pre-commit hook,
    so it contains the previous commit's SHA, not the current one.

    Returns:
        Dict with commit information from GitHub API (second-to-latest commit)

    Raises:
        HTTPException: If GitHub API request fails
    """
    cache_key = f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/{GITHUB_BRANCH}"

    # Check cache
    if cache_key in _github_cache:
        cached_data, cached_time = _github_cache[cache_key]
        if datetime.now(UTC) - cached_time < CACHE_TTL:
            logger.debug("Using cached GitHub API response")
            return cached_data

    # Fetch recent commits from GitHub (get 2 commits, return the second one)
    url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/commits"
    params = {"sha": GITHUB_BRANCH, "per_page": 2}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10.0,
            )
            response.raise_for_status()
            commits = response.json()

            if len(commits) < 2:
                # If there's only one commit, use it (edge case for new repos)
                data = commits[0] if commits else None
            else:
                # Use the second-to-latest commit (latest-1)
                data = commits[1]

            if not data:
                raise Exception("No commits found in repository")

            # Cache the result
            _github_cache[cache_key] = (data, datetime.now(UTC))

            return data

    except httpx.HTTPStatusError as e:
        logger.error(f"GitHub API request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch latest version from GitHub: {e.response.status_code}",
        ) from e
    except Exception as e:
        logger.error(f"Failed to fetch from GitHub: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to check for updates: {str(e)}",
        ) from e


@router.get("", response_model=VersionInfo)
async def get_version():
    """Get current version information.

    Returns:
        Current version, commit, and build timestamp
    """
    return _get_version_info()


@router.get("/check", response_model=UpdateCheckResponse)
async def check_for_updates():
    """Check if an update is available.

    Compares current commit with latest commit on GitHub main branch.
    Only considers it an update if the GitHub commit is newer.

    Returns:
        Update availability status with commit information
    """
    # Get current version info
    version_info = _get_version_info()

    # If we don't have a commit SHA, we can't check for updates
    if not version_info.commit:
        return UpdateCheckResponse(
            update_available=False,
            current_commit=None,
            current_commit_short=None,
            latest_commit=None,
            latest_commit_short=None,
            latest_commit_url=None,
            message="Cannot check for updates: version information unavailable",
        )

    try:
        # Fetch latest commit from GitHub
        github_data = await _get_latest_commit_from_github()
        latest_commit = github_data["sha"]
        latest_commit_short = latest_commit[:7]
        latest_commit_url = github_data["html_url"]

        # Parse timestamps to compare
        update_available = False
        if latest_commit != version_info.commit:
            # Commits are different, check if GitHub's is newer
            try:
                # GitHub commit date is in commit.committer.date
                github_commit_date_str = github_data["commit"]["committer"]["date"]
                github_commit_date = datetime.fromisoformat(
                    github_commit_date_str.replace("Z", "+00:00")
                )

                # Parse our build timestamp
                if version_info.build_timestamp:
                    current_build_date = datetime.fromisoformat(
                        version_info.build_timestamp
                    )

                    # Only show update if GitHub commit is newer
                    update_available = github_commit_date > current_build_date
                else:
                    # No timestamp, fall back to commit comparison
                    update_available = True

            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse commit dates: {e}")
                # If we can't parse dates, fall back to commit comparison
                update_available = True

        if update_available:
            message = (
                f"Update available: {version_info.commit_short} → {latest_commit_short}"
            )
        else:
            message = "You are running the latest version"

        return UpdateCheckResponse(
            update_available=update_available,
            current_commit=version_info.commit,
            current_commit_short=version_info.commit_short,
            latest_commit=latest_commit,
            latest_commit_short=latest_commit_short,
            latest_commit_url=latest_commit_url,
            message=message,
        )

    except HTTPException:
        # Re-raise HTTP exceptions from GitHub fetch
        raise
    except Exception as e:
        logger.error(f"Unexpected error checking for updates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check for updates: {str(e)}",
        ) from e


@router.post("/upgrade", response_model=UpgradeResponse)
async def upgrade(config: ConfigDep):
    """Upgrade Mimic and all scenario packs.

    This runs the equivalent of `mimic upgrade` command:
    1. Upgrades the Mimic tool itself using 'uv tool upgrade mimic'
    2. Updates all configured scenario packs by pulling latest changes

    Returns:
        Status and output of the upgrade operation
    """
    from mimic.scenario_pack_manager import ScenarioPackManager

    output_lines = []

    # Step 1: Upgrade Mimic tool
    output_lines.append("Upgrading Mimic tool...")

    try:
        result = await asyncio.create_subprocess_exec(
            "uv",
            "tool",
            "upgrade",
            "mimic",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await result.communicate()

        if result.returncode == 0:
            output_lines.append("✓ Mimic tool upgraded successfully")
            if stdout:
                output_lines.append(stdout.decode().strip())
        else:
            output_lines.append(
                f"⚠ Failed to upgrade Mimic tool: {stderr.decode().strip()}"
            )

    except FileNotFoundError:
        output_lines.append("⚠ 'uv' command not found. Cannot upgrade Mimic.")
    except Exception as e:
        output_lines.append(f"⚠ Error upgrading Mimic: {str(e)}")

    # Step 2: Update scenario packs
    output_lines.append("\nUpdating scenario packs...")

    try:
        pack_manager = ScenarioPackManager(config.packs_dir)
        packs = config.list_scenario_packs()

        if not packs:
            output_lines.append("No scenario packs configured")
        else:
            output_lines.append(f"Found {len(packs)} pack(s) to update\n")

            success_count = 0
            for pack_name, pack_config in packs.items():
                try:
                    # Check if pack is installed
                    if not pack_manager.get_pack_path(pack_name):
                        output_lines.append(f"⚠ {pack_name}: Not installed, cloning...")
                        url = pack_config.get("url")
                        if not url:
                            output_lines.append(
                                f"✗ {pack_name}: Missing URL in configuration"
                            )
                            continue
                        branch = pack_config.get("branch", "main")
                        pack_manager.clone_pack(pack_name, url, branch)
                        output_lines.append(f"✓ {pack_name}: Cloned successfully")
                    else:
                        pack_manager.update_pack(pack_name)
                        output_lines.append(f"✓ {pack_name}: Updated successfully")

                    success_count += 1

                except Exception as e:
                    output_lines.append(f"✗ {pack_name}: {str(e)}")

            output_lines.append(
                f"\nUpdated {success_count}/{len(packs)} pack(s) successfully"
            )

    except Exception as e:
        output_lines.append(f"Error updating scenario packs: {str(e)}")

    output_text = "\n".join(output_lines)

    return UpgradeResponse(
        status="success",
        message="Upgrade complete! Please restart the Mimic UI server to use the new version.",
        output=output_text,
    )
