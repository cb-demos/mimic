"""API endpoints for version checking and upgrades."""

import asyncio
import base64
import logging
import tomllib
from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..dependencies import ConfigDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/version", tags=["version"])

# Cache for GitHub API responses (5 minute TTL)
_github_cache: dict[str, tuple[str, datetime]] = {}
CACHE_TTL = timedelta(minutes=5)

GITHUB_REPO_OWNER = "cb-demos"
GITHUB_REPO_NAME = "mimic"
GITHUB_BRANCH = "main"


class VersionInfo(BaseModel):
    """Current version information."""

    version: str


class UpdateCheckResponse(BaseModel):
    """Update availability check response."""

    update_available: bool
    current_version: str
    latest_version: str | None
    message: str


class UpgradeResponse(BaseModel):
    """Upgrade operation response."""

    status: str
    message: str
    output: str | None = None


def _get_current_version() -> str:
    """Get current installed version from package metadata.

    Returns:
        Version string (e.g., "2025.11.5.1") or "dev" if not installed

    Raises:
        HTTPException: If version cannot be determined
    """
    try:
        return version("mimic")
    except PackageNotFoundError:
        # Not installed as a package (dev environment)
        logger.warning("Package not installed, using dev version")
        return "dev"


def _parse_calver(version_str: str) -> tuple[int, int, int, int]:
    """Parse CalVer string into comparable tuple.

    Args:
        version_str: Version string in format YYYY.M.D.BUILD

    Returns:
        Tuple of (year, month, day, build) as integers

    Raises:
        ValueError: If version string is not in CalVer format
    """
    parts = version_str.split(".")
    if len(parts) != 4:
        raise ValueError(f"Invalid CalVer format: {version_str}")

    try:
        year, month, day, build = (int(p) for p in parts)
        return (year, month, day, build)
    except ValueError as e:
        raise ValueError(f"Invalid CalVer format: {version_str} ({e})") from e


def _compare_versions(current: str, latest: str) -> bool:
    """Compare two CalVer version strings.

    Args:
        current: Current version string
        latest: Latest version string

    Returns:
        True if latest > current, False otherwise
    """
    if current == "dev":
        # Dev version is always considered outdated
        return True

    try:
        current_tuple = _parse_calver(current)
    except ValueError as e:
        logger.warning(f"Invalid current version format: {e}")
        return False

    try:
        latest_tuple = _parse_calver(latest)
    except ValueError as e:
        logger.error(f"Invalid latest version from GitHub: {e}")
        # This is concerning - log error but don't claim update available
        return False

    return latest_tuple > current_tuple


async def _get_latest_version_from_github() -> str:
    """Fetch latest version from GitHub's pyproject.toml with caching.

    Returns:
        Version string from GitHub's main branch pyproject.toml

    Raises:
        HTTPException: If GitHub API request fails or version can't be parsed
    """
    cache_key = f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/{GITHUB_BRANCH}/pyproject.toml"

    # Check cache
    if cache_key in _github_cache:
        cached_version, cached_time = _github_cache[cache_key]
        if datetime.now(UTC) - cached_time < CACHE_TTL:
            logger.debug("Using cached GitHub version")
            return cached_version

    # Fetch pyproject.toml from GitHub
    url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/pyproject.toml"
    params = {"ref": GITHUB_BRANCH}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            # GitHub returns base64-encoded content
            content_b64 = data.get("content")
            if not content_b64:
                raise ValueError("No content in GitHub API response")

            # Decode and parse TOML
            content = base64.b64decode(content_b64).decode("utf-8")
            pyproject_data = tomllib.loads(content)

            # Extract version
            version_str = pyproject_data.get("project", {}).get("version")
            if not version_str:
                raise ValueError("No version field found in pyproject.toml")

            # Cache the result
            _github_cache[cache_key] = (version_str, datetime.now(UTC))

            return version_str

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            # Likely rate limited
            logger.warning(f"GitHub API rate limit hit: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub API rate limit exceeded. Please try again in a few minutes.",
            ) from e

        logger.error(f"GitHub API request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch latest version from GitHub: {e.response.status_code}",
        ) from e
    except Exception as e:
        logger.error(f"Failed to fetch version from GitHub: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to check for updates: {str(e)}",
        ) from e


@router.get("", response_model=VersionInfo)
async def get_version():
    """Get current version information.

    Returns:
        Current version string
    """
    return VersionInfo(version=_get_current_version())


@router.get("/check", response_model=UpdateCheckResponse)
async def check_for_updates():
    """Check if an update is available.

    Compares current version with latest version from GitHub's pyproject.toml
    using CalVer format (YYYY.M.D.BUILD).

    Returns:
        Update availability status with version information
    """
    # Get current version
    current_version = _get_current_version()

    try:
        # Fetch latest version from GitHub
        latest_version = await _get_latest_version_from_github()

        # Compare versions
        update_available = _compare_versions(current_version, latest_version)

        if update_available:
            message = f"Update available: {current_version} → {latest_version}"
        else:
            message = "You are running the latest version"

        return UpdateCheckResponse(
            update_available=update_available,
            current_version=current_version,
            latest_version=latest_version,
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
