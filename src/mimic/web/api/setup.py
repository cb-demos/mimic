"""API endpoints for initial setup wizard."""

import logging

from fastapi import APIRouter, HTTPException

from ...exceptions import KeyringUnavailableError
from ..dependencies import ConfigDep
from ..models import RunSetupRequest, RunSetupResponse, SetupStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(config: ConfigDep):
    """Check if initial setup is needed.

    Returns:
        Status indicating whether setup is required and what's missing
    """
    try:
        missing_config = []

        # Check GitHub credentials
        if not config.get_github_username():
            missing_config.append("github_username")
        if not config.get_github_pat():
            missing_config.append("github_token")

        # Check if any environment is configured
        current_env = config.get_current_tenant()
        if not current_env:
            missing_config.append("current_environment")
        else:
            # Check if current environment has CloudBees PAT
            if not config.get_cloudbees_pat(current_env):
                missing_config.append("cloudbees_token")

        needs_setup = len(missing_config) > 0

        return SetupStatusResponse(
            needs_setup=needs_setup, missing_config=missing_config
        )

    except KeyringUnavailableError as e:
        logger.error(f"Keyring unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Keyring backend is not available",
                "message": str(e),
                "instructions": e.instructions,
            },
        ) from e


@router.post("/run", response_model=RunSetupResponse)
async def run_setup(request: RunSetupRequest, config: ConfigDep):
    """Run initial setup with provided configuration.

    Args:
        request: Setup configuration (GitHub and CloudBees credentials)
        config: Config manager dependency

    Returns:
        Setup result
    """
    try:
        # Set GitHub credentials
        config.set_github_username(request.github_username)
        config.set_github_pat(request.github_token)
        logger.info(f"Set GitHub username: {request.github_username}")

        # Set current tenant
        tenants = config.list_tenants()
        if request.tenant not in tenants:
            return RunSetupResponse(
                success=False,
                message=f"Tenant '{request.tenant}' not found",
            )

        config.set_current_tenant(request.tenant)
        logger.info(f"Set current tenant: {request.tenant}")

        # Set CloudBees PAT for selected tenant
        config.set_cloudbees_pat(request.tenant, request.cloudbees_token)
        logger.info(f"Set CloudBees PAT for tenant: {request.tenant}")

        return RunSetupResponse(success=True, message="Setup completed successfully")

    except KeyringUnavailableError as e:
        logger.error(f"Keyring unavailable during setup: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Keyring backend is not available",
                "message": str(e),
                "instructions": e.instructions,
            },
        ) from e

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        return RunSetupResponse(success=False, message=f"Setup failed: {str(e)}")
