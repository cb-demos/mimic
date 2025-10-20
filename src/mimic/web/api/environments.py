"""API endpoints for environment management."""

import logging

from fastapi import APIRouter, HTTPException, status

from mimic.environments import PRESET_ENVIRONMENTS

from ..dependencies import ConfigDep
from ..models import (
    AddEnvironmentRequest,
    AddPropertyRequest,
    EnvironmentInfo,
    EnvironmentListResponse,
    PropertiesResponse,
    StatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/environments", tags=["environments"])


@router.get("", response_model=EnvironmentListResponse)
async def list_environments(config: ConfigDep):
    """List all environments with their configuration.

    Returns:
        List of all environments (preset + custom) with current selection
    """
    current_env = config.get_current_environment()
    env_names = config.list_environments()
    preset_names = list(PRESET_ENVIRONMENTS.keys())

    environments = []
    for env_name in env_names:
        url = config.get_environment_url(env_name)
        endpoint_id = config.get_endpoint_id(env_name)
        properties = config.get_environment_properties(env_name)

        environments.append(
            EnvironmentInfo(
                name=env_name,
                url=url or "",
                endpoint_id=endpoint_id or "",
                is_current=(env_name == current_env),
                is_preset=(env_name in preset_names),
                properties=properties,
            )
        )

    return EnvironmentListResponse(environments=environments, current=current_env)


@router.post("", response_model=StatusResponse)
async def add_environment(request: AddEnvironmentRequest, config: ConfigDep):
    """Add a custom environment.

    Args:
        request: Environment configuration
        config: Config manager dependency

    Returns:
        Status message
    """
    try:
        # Note: add_environment requires PAT, but we're not setting it here
        # Users should configure the PAT separately via the config endpoints
        config.add_environment(
            name=request.name,
            url=request.url,
            pat="",  # Will be set separately via /api/config/cloudbees/token
            endpoint_id=request.endpoint_id,
        )
        logger.info(f"Added custom environment: {request.name}")
        return StatusResponse(
            status="success", message=f"Environment '{request.name}' added successfully"
        )
    except Exception as e:
        logger.error(f"Failed to add environment {request.name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add environment: {str(e)}",
        ) from e


@router.delete("/{env_name}", response_model=StatusResponse)
async def remove_environment(env_name: str, config: ConfigDep):
    """Remove a custom environment.

    Preset environments cannot be removed.

    Args:
        env_name: Environment name to remove
        config: Config manager dependency

    Returns:
        Status message
    """
    # Check if it's a preset environment
    if env_name in PRESET_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove preset environments",
        )

    try:
        config.remove_environment(env_name)
        logger.info(f"Removed environment: {env_name}")
        return StatusResponse(
            status="success", message=f"Environment '{env_name}' removed successfully"
        )
    except Exception as e:
        logger.error(f"Failed to remove environment {env_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to remove environment: {str(e)}",
        ) from e


@router.patch("/{env_name}/select", response_model=StatusResponse)
async def select_environment(env_name: str, config: ConfigDep):
    """Set an environment as the current environment.

    Args:
        env_name: Environment name to select
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify environment exists
    environments = config.list_environments()
    if env_name not in environments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment '{env_name}' not found",
        )

    try:
        config.set_current_environment(env_name)
        logger.info(f"Selected environment: {env_name}")
        return StatusResponse(
            status="success",
            message=f"Environment '{env_name}' selected as current",
        )
    except Exception as e:
        logger.error(f"Failed to select environment {env_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to select environment: {str(e)}",
        ) from e


@router.get("/{env_name}/properties", response_model=PropertiesResponse)
async def get_environment_properties(env_name: str, config: ConfigDep):
    """Get properties for an environment.

    Args:
        env_name: Environment name
        config: Config manager dependency

    Returns:
        Dictionary of environment properties
    """
    # Verify environment exists
    environments = config.list_environments()
    if env_name not in environments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment '{env_name}' not found",
        )

    properties = config.get_environment_properties(env_name)
    return PropertiesResponse(properties=properties)


@router.post("/{env_name}/properties", response_model=StatusResponse)
async def add_environment_property(
    env_name: str, request: AddPropertyRequest, config: ConfigDep
):
    """Add or update an environment property.

    Args:
        env_name: Environment name
        request: Property key and value
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify environment exists
    environments = config.list_environments()
    if env_name not in environments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment '{env_name}' not found",
        )

    try:
        config.set_environment_property(env_name, request.key, request.value)
        logger.info(f"Set property {request.key} for environment {env_name}")
        return StatusResponse(
            status="success",
            message=f"Property '{request.key}' set for environment '{env_name}'",
        )
    except Exception as e:
        logger.error(
            f"Failed to set property {request.key} for environment {env_name}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to set property: {str(e)}",
        ) from e


@router.delete("/{env_name}/properties/{property_key}", response_model=StatusResponse)
async def delete_environment_property(
    env_name: str, property_key: str, config: ConfigDep
):
    """Delete an environment property.

    Args:
        env_name: Environment name
        property_key: Property key to delete
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify environment exists
    environments = config.list_environments()
    if env_name not in environments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment '{env_name}' not found",
        )

    try:
        # Delete property by setting it to empty and removing from config
        properties = config.get_environment_properties(env_name)
        if property_key in properties:
            del properties[property_key]
            # Save updated properties back
            for key, value in properties.items():
                config.set_environment_property(env_name, key, value)
        logger.info(f"Deleted property {property_key} from environment {env_name}")
        return StatusResponse(
            status="success",
            message=f"Property '{property_key}' deleted from environment '{env_name}'",
        )
    except Exception as e:
        logger.error(
            f"Failed to delete property {property_key} from environment {env_name}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete property: {str(e)}",
        ) from e
