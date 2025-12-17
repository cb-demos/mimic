"""API endpoints for tenant management."""

import logging

from fastapi import APIRouter, HTTPException, status

from mimic.environments import PRESET_TENANTS

from ..dependencies import ConfigDep
from ..error_handler import sanitize_error_message
from ..models import (
    AddPresetTenantRequest,
    AddPropertyRequest,
    AddTenantRequest,
    PresetTenantInfo,
    PresetTenantListResponse,
    PropertiesResponse,
    StatusResponse,
    TenantInfo,
    TenantListResponse,
    ValidateCredentialsRequest,
    ValidateCredentialsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/presets", response_model=PresetTenantListResponse)
async def list_preset_tenants(config: ConfigDep):
    """List all available preset tenants.

    Returns:
        List of preset tenants with their configurations and whether they're already added
    """
    configured_envs = config.list_tenants()
    presets = []

    for name, preset_config in PRESET_TENANTS.items():
        flag_api_type = "org" if preset_config.use_legacy_flags else "app"
        presets.append(
            PresetTenantInfo(
                name=name,
                url=preset_config.url,
                endpoint_id=preset_config.endpoint_id,
                description=preset_config.description,
                flag_api_type=flag_api_type,
                default_properties=preset_config.properties,
                is_configured=(name in configured_envs),
            )
        )

    return PresetTenantListResponse(presets=presets)


@router.post("/validate-credentials", response_model=ValidateCredentialsResponse)
async def validate_credentials(request: ValidateCredentialsRequest):
    """Validate CloudBees credentials before adding environment.

    Args:
        request: Validation request with PAT, org ID, and environment URL

    Returns:
        Validation result with organization name if valid
    """
    try:
        from mimic.unify import UnifyAPIClient

        # Create temporary client to validate credentials
        with UnifyAPIClient(
            base_url=request.environment_url, api_key=request.pat
        ) as client:
            success, error = client.validate_credentials(request.org_id)

            if success:
                # Try to fetch org name for better UX
                try:
                    org_data = client.get_organization(request.org_id)
                    # API response format: {"organization": {"displayName": "..."}}
                    org_info = org_data.get("organization", {})
                    org_name = org_info.get("displayName", "Unknown")
                    return ValidateCredentialsResponse(valid=True, org_name=org_name)
                except Exception:
                    # If we can't fetch org name, that's fine - credentials are still valid
                    return ValidateCredentialsResponse(valid=True)
            else:
                return ValidateCredentialsResponse(valid=False, error=error)
    except Exception as e:
        logger.error(f"Credential validation error: {e}")
        return ValidateCredentialsResponse(
            valid=False, error=sanitize_error_message(str(e))
        )


@router.post("/presets", response_model=StatusResponse)
async def add_preset_tenant(request: AddPresetTenantRequest, config: ConfigDep):
    """Add a preset tenant with credentials.

    Args:
        request: Preset environment configuration with PAT
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify it's a valid preset
    if request.name not in PRESET_TENANTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown preset tenant: {request.name}",
        )

    preset_config = PRESET_TENANTS[request.name]

    # Check if already configured
    existing_envs = config.list_tenants()
    if request.name in existing_envs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant '{request.name}' is already configured",
        )

    try:
        from mimic.unify import UnifyAPIClient

        # Validate credentials first
        with UnifyAPIClient(base_url=preset_config.url, api_key=request.pat) as client:
            success, error = client.validate_credentials(request.org_id)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error
                    or "Invalid CloudBees credentials for this environment",
                )

        # Merge preset properties with custom properties (custom overrides preset)
        properties = preset_config.properties.copy()
        properties.update(request.custom_properties)

        # Add the environment with proper configuration including all properties
        config.add_tenant(
            name=request.name,
            url=preset_config.url,
            pat=request.pat,
            endpoint_id=preset_config.endpoint_id,
            use_legacy_flags=preset_config.use_legacy_flags,
            properties=properties,
        )

        logger.info(f"Added preset tenant: {request.name}")
        return StatusResponse(
            status="success",
            message=f"Preset tenant '{request.name}' added successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add preset tenant {request.name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add preset tenant: {str(e)}",
        ) from e


@router.get("", response_model=TenantListResponse)
async def list_tenants(config: ConfigDep):
    """List all environments with their configuration.

    Returns:
        List of all environments (preset + custom) with current selection
    """
    current_env = config.get_current_tenant()
    tenant_names = config.list_tenants()
    preset_names = list(PRESET_TENANTS.keys())

    environments = []
    for tenant_name in tenant_names:
        url = config.get_tenant_url(tenant_name)
        endpoint_id = config.get_endpoint_id(tenant_name)
        properties = config.get_tenant_properties(tenant_name)

        # Determine flag API type
        is_preset = tenant_name in preset_names
        if is_preset:
            preset_config = PRESET_TENANTS[tenant_name]
            flag_api_type = "org" if preset_config.use_legacy_flags else "app"
        else:
            # For custom tenants, check use_legacy_flags setting
            use_legacy = config.get_tenant_uses_legacy_flags(tenant_name)
            flag_api_type = "org" if use_legacy else "app"

        environments.append(
            TenantInfo(
                name=tenant_name,
                url=url or "",
                endpoint_id=endpoint_id or "",
                is_current=(tenant_name == current_env),
                is_preset=is_preset,
                flag_api_type=flag_api_type,
                properties=properties,
            )
        )

    return TenantListResponse(tenants=environments, current=current_env)


@router.post("", response_model=StatusResponse)
async def add_tenant(request: AddTenantRequest, config: ConfigDep):
    """Add a custom tenant.

    Args:
        request: Environment configuration with optional PAT validation
        config: Config manager dependency

    Returns:
        Status message
    """
    try:
        # If PAT and org_id provided, validate credentials first
        if request.pat and request.org_id:
            from mimic.unify import UnifyAPIClient

            with UnifyAPIClient(base_url=request.url, api_key=request.pat) as client:
                success, error = client.validate_credentials(request.org_id)
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=error
                        or "Invalid CloudBees credentials for this environment",
                    )

        # Add the environment
        config.add_tenant(
            name=request.name,
            url=request.url,
            pat=request.pat or "",  # Store PAT if provided
            endpoint_id=request.endpoint_id,
            use_legacy_flags=request.use_legacy_flags,
        )

        logger.info(f"Added custom tenant: {request.name}")
        return StatusResponse(
            status="success", message=f"Tenant '{request.name}' added successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add environment {request.name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add environment: {str(e)}",
        ) from e


@router.delete("/{tenant_name}", response_model=StatusResponse)
async def remove_tenant(tenant_name: str, config: ConfigDep):
    """Remove an environment.

    Args:
        tenant_name: Environment name to remove
        config: Config manager dependency

    Returns:
        Status message
    """
    try:
        config.remove_tenant(tenant_name)
        logger.info(f"Removed environment: {tenant_name}")
        return StatusResponse(
            status="success", message=f"Tenant '{tenant_name}' removed successfully"
        )
    except Exception as e:
        logger.error(f"Failed to remove environment {tenant_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to remove environment: {str(e)}",
        ) from e


@router.patch("/{tenant_name}/select", response_model=StatusResponse)
async def select_tenant(tenant_name: str, config: ConfigDep):
    """Set an environment as the current environment.

    Args:
        tenant_name: Environment name to select
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify environment exists
    environments = config.list_tenants()
    if tenant_name not in environments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_name}' not found",
        )

    try:
        config.set_current_tenant(tenant_name)
        logger.info(f"Selected environment: {tenant_name}")
        return StatusResponse(
            status="success",
            message=f"Tenant '{tenant_name}' selected as current",
        )
    except Exception as e:
        logger.error(f"Failed to select environment {tenant_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to select environment: {str(e)}",
        ) from e


@router.get("/{tenant_name}/properties", response_model=PropertiesResponse)
async def get_tenant_properties(tenant_name: str, config: ConfigDep):
    """Get properties for an environment.

    Args:
        tenant_name: Environment name
        config: Config manager dependency

    Returns:
        Dictionary of environment properties
    """
    # Verify environment exists
    environments = config.list_tenants()
    if tenant_name not in environments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_name}' not found",
        )

    properties = config.get_tenant_properties(tenant_name)
    return PropertiesResponse(properties=properties)


@router.post("/{tenant_name}/properties", response_model=StatusResponse)
async def add_tenant_property(
    tenant_name: str, request: AddPropertyRequest, config: ConfigDep
):
    """Add or update an environment property.

    Args:
        tenant_name: Environment name
        request: Property key and value
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify environment exists
    environments = config.list_tenants()
    if tenant_name not in environments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_name}' not found",
        )

    try:
        config.set_tenant_property(tenant_name, request.key, request.value)
        logger.info(f"Set property {request.key} for environment {tenant_name}")
        return StatusResponse(
            status="success",
            message=f"Property '{request.key}' set for tenant '{tenant_name}'",
        )
    except Exception as e:
        logger.error(
            f"Failed to set property {request.key} for environment {tenant_name}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to set property: {str(e)}",
        ) from e


@router.delete(
    "/{tenant_name}/properties/{property_key}", response_model=StatusResponse
)
async def delete_tenant_property(
    tenant_name: str, property_key: str, config: ConfigDep
):
    """Delete an environment property.

    Args:
        tenant_name: Environment name
        property_key: Property key to delete
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify environment exists
    environments = config.list_tenants()
    if tenant_name not in environments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_name}' not found",
        )

    try:
        # Delete property by setting it to empty and removing from config
        properties = config.get_tenant_properties(tenant_name)
        if property_key in properties:
            del properties[property_key]
            # Save updated properties back
            for key, value in properties.items():
                config.set_tenant_property(tenant_name, key, value)
        logger.info(f"Deleted property {property_key} from environment {tenant_name}")
        return StatusResponse(
            status="success",
            message=f"Property '{property_key}' deleted from tenant '{tenant_name}'",
        )
    except Exception as e:
        logger.error(
            f"Failed to delete property {property_key} from environment {tenant_name}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete property: {str(e)}",
        ) from e
