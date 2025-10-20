"""API endpoints for configuration management."""

import logging

from fastapi import APIRouter

from ..dependencies import ConfigDep
from ..models import (
    CloudBeesConfigResponse,
    CloudBeesEnvCredentials,
    GitHubConfigResponse,
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
