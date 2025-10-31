"""API endpoints for scenario management and execution."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from mimic.exceptions import ValidationError
from mimic.instance_repository import InstanceRepository
from mimic.pipeline import CreationPipeline
from mimic.utils import resolve_run_name

from ..dependencies import (
    CloudBeesCredentialsDep,
    ConfigDep,
    GitHubCredentialsDep,
    ScenarioDep,
)
from ..events import broadcaster
from ..models import (
    CheckPropertiesRequest,
    CheckPropertiesResponse,
    CreatePropertyRequest,
    PropertyInfo,
    RunScenarioRequest,
    RunScenarioResponse,
    ScenarioDetailResponse,
    ScenarioListResponse,
    ScenarioPreviewRequest,
    ScenarioPreviewResponse,
    StatusResponse,
    ValidateParametersRequest,
    ValidateParametersResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _safe_json_serialize(data: Any) -> str:
    """Safely serialize data to JSON, handling Pydantic models and datetime objects.

    Args:
        data: Data to serialize (may contain Pydantic models, datetime, etc.)

    Returns:
        JSON string representation of the data
    """

    def default_serializer(obj):
        """Custom serializer for non-standard JSON types."""
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(data, default=default_serializer)


@router.get("", response_model=ScenarioListResponse)
async def list_scenarios(
    scenarios: ScenarioDep,
    config: ConfigDep,
):
    """List all available scenarios.

    Returns:
        List of scenarios with their parameter schemas
    """
    scenario_list = scenarios.list_scenarios()
    # TODO: Add get_wip_scenarios_enabled method to ConfigManager
    # For now, assume WIP scenarios are enabled if any are present
    wip_enabled = any(s.get("wip", False) for s in scenario_list)

    return ScenarioListResponse(scenarios=scenario_list, wip_enabled=wip_enabled)


@router.get("/{scenario_id}", response_model=ScenarioDetailResponse)
async def get_scenario(
    scenario_id: str,
    scenarios: ScenarioDep,
    pack_source: str | None = None,
):
    """Get detailed information about a specific scenario.

    Args:
        scenario_id: The scenario ID to retrieve
        pack_source: Optional pack name to disambiguate scenarios with same ID

    Returns:
        Scenario details including parameter schema
    """
    scenario = scenarios.get_scenario(scenario_id, pack_source)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )

    # Convert scenario to dict for response
    scenario_dict = {
        "id": scenario.id,
        "name": scenario.name,
        "summary": scenario.summary,
        "details": scenario.details,
        "wip": scenario.wip,
        "pack_source": scenario.pack_source,
        "scenario_pack": scenario.pack_source,  # For frontend compatibility
        "parameter_schema": (
            scenario.parameter_schema.model_dump()
            if scenario.parameter_schema
            else None
        ),
        "required_properties": scenario.required_properties,
        "required_secrets": scenario.required_secrets,
    }

    return ScenarioDetailResponse(scenario=scenario_dict)


@router.post("/{scenario_id}/validate", response_model=ValidateParametersResponse)
async def validate_parameters(
    scenario_id: str,
    request: ValidateParametersRequest,
    scenarios: ScenarioDep,
    pack_source: str | None = None,
):
    """Validate parameters for a scenario without running it.

    Args:
        scenario_id: The scenario ID
        request: Parameters to validate
        pack_source: Optional pack name to disambiguate scenarios with same ID

    Returns:
        Validation result with any errors
    """
    scenario = scenarios.get_scenario(scenario_id, pack_source)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )

    try:
        # Validate parameters using scenario's validation logic
        scenario.validate_input(request.parameters)
        return ValidateParametersResponse(valid=True, errors=[])
    except ValidationError as e:
        return ValidateParametersResponse(valid=False, errors=[str(e)])


@router.post("/{scenario_id}/check-properties", response_model=CheckPropertiesResponse)
async def check_properties(
    scenario_id: str,
    request: CheckPropertiesRequest,
    scenarios: ScenarioDep,
    cloudbees_creds: CloudBeesCredentialsDep,
    pack_source: str | None = None,
):
    """Check if required properties/secrets exist for a scenario.

    Args:
        scenario_id: The scenario ID
        request: Request with organization_id
        scenarios: Scenario manager dependency
        cloudbees_creds: CloudBees credentials dependency
        pack_source: Optional pack name to disambiguate scenarios with same ID

    Returns:
        List of required and missing properties/secrets
    """
    from mimic.unify import UnifyAPIClient

    scenario = scenarios.get_scenario(scenario_id, pack_source)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )

    # Extract CloudBees credentials
    _, cloudbees_pat, cloudbees_url, _ = cloudbees_creds

    try:
        # Fetch existing properties from the organization
        with UnifyAPIClient(base_url=cloudbees_url, api_key=cloudbees_pat) as client:
            response = client.list_properties(request.organization_id)
            existing_properties = response.get("properties", [])

            # Build a set of existing property names
            existing_names = {
                prop.get("property", {}).get("name")
                for prop in existing_properties
                if prop.get("property", {}).get("name")
            }

        # Check required properties
        required_properties = scenario.required_properties or []
        required_secrets = scenario.required_secrets or []

        missing_properties = [
            name for name in required_properties if name not in existing_names
        ]
        missing_secrets = [
            name for name in required_secrets if name not in existing_names
        ]

        # Build list of all properties with their status
        all_properties = []
        for name in required_properties:
            all_properties.append(
                PropertyInfo(name=name, type="property", exists=name in existing_names)
            )
        for name in required_secrets:
            all_properties.append(
                PropertyInfo(name=name, type="secret", exists=name in existing_names)
            )

        return CheckPropertiesResponse(
            required_properties=required_properties,
            required_secrets=required_secrets,
            missing_properties=missing_properties,
            missing_secrets=missing_secrets,
            all_properties=all_properties,
        )

    except Exception as e:
        logger.error(f"Failed to check properties for scenario {scenario_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to check properties: {str(e)}",
        ) from e


@router.post("/properties/create", response_model=StatusResponse)
async def create_property(
    request: CreatePropertyRequest,
    cloudbees_creds: CloudBeesCredentialsDep,
):
    """Create a property or secret in a CloudBees organization.

    Args:
        request: Request with property details
        cloudbees_creds: CloudBees credentials dependency

    Returns:
        Status message
    """
    from mimic.unify import UnifyAPIClient

    # Extract CloudBees credentials
    _, cloudbees_pat, cloudbees_url, _ = cloudbees_creds

    try:
        with UnifyAPIClient(base_url=cloudbees_url, api_key=cloudbees_pat) as client:
            client.create_property(
                resource_id=request.organization_id,
                name=request.name,
                value=request.value,
                is_secret=request.is_secret,
            )

        property_type = "secret" if request.is_secret else "property"
        logger.info(
            f"Created {property_type} '{request.name}' in org {request.organization_id}"
        )

        return StatusResponse(
            status="success",
            message=f"{'Secret' if request.is_secret else 'Property'} '{request.name}' created successfully",
        )

    except Exception as e:
        logger.error(f"Failed to create property '{request.name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create property: {str(e)}",
        ) from e


@router.post("/{scenario_id}/preview", response_model=ScenarioPreviewResponse)
async def preview_scenario(
    scenario_id: str,
    request: ScenarioPreviewRequest,
    scenarios: ScenarioDep,
    config: ConfigDep,
    pack_source: str | None = None,
):
    """Generate a preview of what will be created for a scenario.

    Args:
        scenario_id: The scenario ID
        request: Request with parameters
        scenarios: Scenario manager dependency
        config: Config manager dependency
        pack_source: Optional pack name to disambiguate scenarios with same ID

    Returns:
        Preview of resources that will be created
    """
    scenario = scenarios.get_scenario(scenario_id, pack_source)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )

    try:
        # Validate parameters
        validated_params = scenario.validate_input(request.parameters)

        # Get environment properties for template resolution
        current_env = config.get_current_environment()
        if not current_env:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No environment configured",
            )

        env_properties = config.get_environment_properties(current_env)

        # Resolve template variables
        resolved_scenario = scenario.resolve_template_variables(
            validated_params, env_properties
        )

        # Generate preview
        preview = CreationPipeline.preview_scenario(resolved_scenario)

        return ScenarioPreviewResponse(preview=preview)

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameters: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Failed to generate preview for scenario {scenario_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate preview: {str(e)}",
        ) from e


@router.post("/{scenario_id}/run", response_model=RunScenarioResponse)
async def run_scenario(
    scenario_id: str,
    request: RunScenarioRequest,
    background_tasks: BackgroundTasks,
    scenarios: ScenarioDep,
    config: ConfigDep,
    github_creds: GitHubCredentialsDep,
    cloudbees_creds: CloudBeesCredentialsDep,
    pack_source: str | None = None,
):
    """Execute a scenario with the provided parameters.

    This starts the scenario execution in the background and returns immediately
    with a session_id. Clients can connect to /api/progress/{session_id} to
    receive real-time progress updates via SSE.

    Args:
        scenario_id: The scenario ID to execute
        request: Execution parameters
        background_tasks: FastAPI background tasks
        scenarios: Scenario manager dependency
        config: Config manager dependency
        github_creds: GitHub credentials dependency
        cloudbees_creds: CloudBees credentials dependency
        pack_source: Optional pack name to disambiguate scenarios with same ID

    Returns:
        Session ID and status for tracking execution
    """
    scenario = scenarios.get_scenario(scenario_id, pack_source)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found",
        )

    # Validate parameters
    try:
        validated_params = scenario.validate_input(request.parameters)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameters: {str(e)}",
        ) from e

    # Generate session ID
    session_id = f"{scenario_id}-{uuid.uuid4().hex[:8]}"

    # Calculate expiration
    expires_at = None
    if request.ttl_days is not None and request.ttl_days > 0:
        expires_at = datetime.now() + timedelta(days=request.ttl_days)

    # Resolve instance name
    instance_name = resolve_run_name(scenario, validated_params, session_id)

    # Extract credentials and environment info
    github_username, github_pat = github_creds
    env_name, cloudbees_pat, cloudbees_url, endpoint_id = cloudbees_creds

    # Get environment properties
    env_properties = config.get_environment_properties(env_name)

    # Get organization ID from request
    organization_id = request.organization_id

    # Start execution in background
    background_tasks.add_task(
        _execute_scenario_background,
        session_id=session_id,
        scenario_id=scenario_id,
        instance_name=instance_name,
        scenario=scenario,
        parameters=validated_params,
        organization_id=organization_id,
        endpoint_id=endpoint_id,
        cloudbees_pat=cloudbees_pat,
        cloudbees_url=cloudbees_url,
        github_pat=github_pat,
        invitee_username=request.invitee_username,
        env_properties=env_properties,
        env_name=env_name,
        expires_at=expires_at,
        dry_run=request.dry_run,
    )

    logger.info(f"Started scenario execution: {session_id}")

    return RunScenarioResponse(
        session_id=session_id,
        status="running",
        message=f"Scenario '{scenario.name}' execution started",
    )


@router.get("/progress/{session_id}")
async def get_progress(session_id: str):
    """Stream real-time progress updates for a scenario execution via SSE.

    Args:
        session_id: The session ID to monitor

    Returns:
        EventSourceResponse with progress events
    """

    async def event_generator():
        """Generate SSE events from the broadcaster."""
        queue = await broadcaster.subscribe(session_id)
        try:
            while True:
                # Wait for events with a timeout to allow periodic checks
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # Serialize the entire event object (with both "event" and "data" fields)
                    # as the SSE data payload. This allows the frontend to use onmessage
                    # instead of needing separate listeners for each event type.
                    yield {"data": _safe_json_serialize(event)}

                    # Check if this is the final event
                    if event["event"] in ["scenario_complete", "scenario_error"]:
                        break

                except TimeoutError:
                    # Send keepalive comment
                    yield {"comment": "keepalive"}
                    continue

        except asyncio.CancelledError:
            logger.debug(f"SSE connection cancelled for session {session_id}")
        finally:
            await broadcaster.unsubscribe(session_id, queue)

    return EventSourceResponse(event_generator())


async def _execute_scenario_background(
    session_id: str,
    scenario_id: str,
    instance_name: str,
    scenario,
    parameters: dict,
    organization_id: str,
    endpoint_id: str,
    cloudbees_pat: str,
    cloudbees_url: str,
    github_pat: str,
    invitee_username: str | None,
    env_properties: dict,
    env_name: str,
    expires_at: datetime | None,
    dry_run: bool,
):
    """Execute a scenario in the background with progress events.

    This function runs the CreationPipeline and emits events to the broadcaster
    so connected SSE clients can receive real-time progress updates.
    """

    async def emit_event(event: dict):
        """Callback for pipeline to emit events."""
        await broadcaster.broadcast(session_id, event)

    try:
        # Emit initial event
        await emit_event(
            {
                "event": "scenario_start",
                "data": {
                    "session_id": session_id,
                    "scenario_id": scenario_id,
                    "instance_name": instance_name,
                },
            }
        )

        if dry_run:
            # Dry run: just preview
            await emit_event(
                {
                    "event": "task_start",
                    "data": {
                        "task_id": "preview",
                        "description": "Generating preview",
                        "total": 1,
                    },
                }
            )

            # Resolve template variables for preview
            resolved_scenario = scenario.resolve_template_variables(
                parameters, env_properties
            )
            preview = CreationPipeline.preview_scenario(resolved_scenario)

            await emit_event(
                {
                    "event": "task_complete",
                    "data": {
                        "task_id": "preview",
                        "success": True,
                        "message": "Preview generated",
                    },
                }
            )

            await emit_event(
                {
                    "event": "scenario_complete",
                    "data": {
                        "session_id": session_id,
                        "instance_name": instance_name,
                        "dry_run": True,
                        "preview": preview,
                    },
                }
            )
        else:
            # Real execution
            pipeline = CreationPipeline(
                organization_id=organization_id,
                endpoint_id=endpoint_id,
                unify_pat=cloudbees_pat,
                unify_base_url=cloudbees_url,
                session_id=session_id,
                github_pat=github_pat,
                invitee_username=invitee_username,
                env_properties=env_properties,
                scenario_id=scenario_id,
                instance_name=instance_name,
                environment=env_name,
                expires_at=expires_at,
                event_callback=emit_event,  # Pass callback for progress events
            )

            summary = await pipeline.execute_scenario(scenario, parameters)

            # Save instance
            instance = summary.get("instance")
            if instance:
                repo = InstanceRepository()
                repo.save(instance)

            await emit_event(
                {
                    "event": "scenario_complete",
                    "data": {
                        "session_id": session_id,
                        "instance_name": instance_name,
                        "summary": summary,
                    },
                }
            )

    except Exception as e:
        logger.error(f"Error executing scenario {scenario_id}: {e}", exc_info=True)
        await emit_event(
            {
                "event": "scenario_error",
                "data": {
                    "session_id": session_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            }
        )
    finally:
        # Clean up event buffers after scenario completes (give clients time to receive final events)
        await asyncio.sleep(5)
        await broadcaster.clear_session(session_id)
