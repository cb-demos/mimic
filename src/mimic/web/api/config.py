"""API endpoints for configuration management."""

import logging

from fastapi import APIRouter, HTTPException, status

from mimic.unify import UnifyAPIClient

from ..dependencies import CloudBeesCredentialsDep, ConfigDep
from ..models import (
    AddRecentValueRequest,
    CachedOrg,
    CachedOrgsResponse,
    CloudBeesConfigResponse,
    CloudBeesEnvCredentials,
    FetchOrgNameRequest,
    FetchOrgNameResponse,
    GitHubConfigResponse,
    RecentValuesResponse,
    SetCloudBeesTokenRequest,
    SetGitHubTokenRequest,
    SetGitHubUsernameRequest,
    StatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["configuration"])


@router.get("/github", response_model=GitHubConfigResponse)
async def get_github_config(config: ConfigDep):
    """Get GitHub configuration status.

    Returns:
        GitHub username and token status
    """
    username = config.get_github_username()
    has_token = config.get_github_pat() is not None

    return GitHubConfigResponse(username=username, has_token=has_token)


@router.post("/github/token", response_model=StatusResponse)
async def set_github_token(request: SetGitHubTokenRequest, config: ConfigDep):
    """Set GitHub personal access token.

    The token is stored securely in the OS keyring.

    Args:
        request: Request with GitHub token
        config: Config manager dependency

    Returns:
        Status message
    """
    try:
        config.set_github_pat(request.token)
        logger.info("GitHub PAT updated via web API")
        return StatusResponse(status="success", message="GitHub token saved securely")
    except Exception as e:
        logger.error(f"Failed to save GitHub token: {e}")
        return StatusResponse(
            status="error", message=f"Failed to save token: {str(e)}"
        )


@router.post("/github/username", response_model=StatusResponse)
async def set_github_username(request: SetGitHubUsernameRequest, config: ConfigDep):
    """Set GitHub username.

    Args:
        request: Request with GitHub username
        config: Config manager dependency

    Returns:
        Status message
    """
    try:
        config.set_github_username(request.username)
        logger.info(f"GitHub username set to: {request.username}")
        return StatusResponse(
            status="success", message="GitHub username saved successfully"
        )
    except Exception as e:
        logger.error(f"Failed to save GitHub username: {e}")
        return StatusResponse(
            status="error", message=f"Failed to save username: {str(e)}"
        )


@router.get("/cloudbees", response_model=CloudBeesConfigResponse)
async def get_cloudbees_config(config: ConfigDep):
    """Get CloudBees configuration status for all environments.

    Returns:
        List of environments with their credential status
    """
    environments = config.list_environments()
    env_credentials = []

    for env_name in environments:
        has_token = config.get_cloudbees_pat(env_name) is not None
        env_credentials.append(
            CloudBeesEnvCredentials(name=env_name, has_token=has_token)
        )

    return CloudBeesConfigResponse(environments=env_credentials)


@router.post("/cloudbees/token", response_model=StatusResponse)
async def set_cloudbees_token(request: SetCloudBeesTokenRequest, config: ConfigDep):
    """Set CloudBees personal access token for an environment.

    The token is stored securely in the OS keyring.

    Args:
        request: Request with environment name and CloudBees token
        config: Config manager dependency

    Returns:
        Status message
    """
    try:
        # Verify environment exists
        environments = config.list_environments()
        if request.environment not in environments:
            return StatusResponse(
                status="error",
                message=f"Environment '{request.environment}' not found",
            )

        config.set_cloudbees_pat(request.environment, request.token)
        logger.info(f"CloudBees PAT updated for environment: {request.environment}")
        return StatusResponse(
            status="success",
            message=f"CloudBees token saved securely for {request.environment}",
        )
    except Exception as e:
        logger.error(
            f"Failed to save CloudBees token for {request.environment}: {e}"
        )
        return StatusResponse(
            status="error", message=f"Failed to save token: {str(e)}"
        )


@router.get("/recent/{category}", response_model=RecentValuesResponse)
async def get_recent_values(category: str, config: ConfigDep):
    """Get recent values for a category.

    Args:
        category: Category name (e.g., 'github_orgs', 'expiration_days')
        config: Config manager dependency

    Returns:
        Recent values for the category
    """
    values = config.get_recent_values(category)
    return RecentValuesResponse(category=category, values=values)


@router.post("/recent/{category}", response_model=StatusResponse)
async def add_recent_value(
    category: str, request: AddRecentValueRequest, config: ConfigDep
):
    """Add a value to recent values for a category.

    Args:
        category: Category name (e.g., 'github_orgs', 'expiration_days')
        request: Request with value to add
        config: Config manager dependency

    Returns:
        Status message
    """
    try:
        config.add_recent_value(category, request.value)
        logger.info(f"Added recent value '{request.value}' to category '{category}'")
        return StatusResponse(status="success", message="Recent value saved")
    except Exception as e:
        logger.error(f"Failed to save recent value: {e}")
        return StatusResponse(status="error", message=f"Failed to save: {str(e)}")


@router.get("/cloudbees-orgs", response_model=CachedOrgsResponse)
async def get_cached_orgs(config: ConfigDep):
    """Get cached CloudBees organizations for the current environment.

    Returns:
        List of cached organizations with ID and display name
    """
    current_env = config.get_current_environment()
    if not current_env:
        return CachedOrgsResponse(orgs=[])

    # Get cached orgs as dict[org_id -> org_name]
    cached_orgs_dict = config.get_cached_orgs_for_env(current_env)

    # Convert to list of CachedOrg objects
    orgs = [
        CachedOrg(org_id=org_id, display_name=org_name)
        for org_id, org_name in cached_orgs_dict.items()
    ]

    return CachedOrgsResponse(orgs=orgs)


@router.post("/cloudbees-orgs/fetch", response_model=FetchOrgNameResponse)
async def fetch_org_name(
    request: FetchOrgNameRequest,
    config: ConfigDep,
    cloudbees_creds: CloudBeesCredentialsDep,
):
    """Fetch organization name from CloudBees API and cache it.

    Args:
        request: Request with org_id
        config: Config manager dependency
        cloudbees_creds: CloudBees credentials dependency

    Returns:
        Organization ID and display name
    """
    env_name, cloudbees_pat, cloudbees_url, _ = cloudbees_creds

    try:
        # Fetch org name from API
        with UnifyAPIClient(base_url=cloudbees_url, api_key=cloudbees_pat) as client:
            org_data = client.get_organization(request.org_id)
            # API response format: {"organization": {"displayName": "..."}}
            org_info = org_data.get("organization", {})
            org_name = org_info.get("displayName", "Unknown")

        # Cache the org name
        config.cache_org_name(request.org_id, org_name, env_name)
        logger.info(f"Cached organization: {org_name} ({request.org_id})")

        return FetchOrgNameResponse(org_id=request.org_id, display_name=org_name)

    except Exception as e:
        logger.error(f"Failed to fetch org name for {request.org_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch organization name: {str(e)}",
        ) from e
