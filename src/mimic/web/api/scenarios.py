"""API endpoints for scenario management and execution."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
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
    RunScenarioRequest,
    RunScenarioResponse,
    ScenarioDetailResponse,
    ScenarioListResponse,
    ValidateParametersRequest,
    ValidateParametersResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


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
):
    """Get detailed information about a specific scenario.

    Args:
        scenario_id: The scenario ID to retrieve

    Returns:
        Scenario details including parameter schema
    """
    scenario = scenarios.get_scenario(scenario_id)
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
):
    """Validate parameters for a scenario without running it.

    Args:
        scenario_id: The scenario ID
        request: Parameters to validate

    Returns:
        Validation result with any errors
    """
    scenario = scenarios.get_scenario(scenario_id)
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


@router.post("/{scenario_id}/run", response_model=RunScenarioResponse)
async def run_scenario(
    scenario_id: str,
    request: RunScenarioRequest,
    background_tasks: BackgroundTasks,
    scenarios: ScenarioDep,
    config: ConfigDep,
    github_creds: GitHubCredentialsDep,
    cloudbees_creds: CloudBeesCredentialsDep,
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

    Returns:
        Session ID and status for tracking execution
    """
    scenario = scenarios.get_scenario(scenario_id)
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
    if request.ttl_days is not None:
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
                    yield {
                        "event": event["event"],
                        "data": json.dumps(event["data"]),
                    }

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
