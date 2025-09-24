import logging
from typing import Any

from fastmcp import FastMCP

from src.config import settings
from src.creation_pipeline import CreationPipeline
from src.exceptions import PipelineError, ValidationError
from src.scenarios import get_scenario_manager

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = FastMCP("Mimic")


@mcp.tool
def list_scenarios() -> list[dict[str, Any]]:
    """List all available scenarios with their parameter schemas."""
    manager = get_scenario_manager()
    return manager.list_scenarios()


@mcp.tool
async def instantiate_scenario(
    scenario_id: str,
    organization_id: str,
    invitee_username: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute a complete scenario using the Creation Pipeline.

    This will:
    1. Create repositories from templates with content replacements
    2. Create CloudBees components for repos that need them
    3. Create feature flags
    4. Create environments
    5. Create applications linking components and environments
    6. Configure flags across environments

    Args:
        scenario_id: The ID of the scenario to execute (e.g., 'hackers-app')
        organization_id: CloudBees Unify organization UUID (get from organization info)
        invitee_username: Optional GitHub username to invite to the organization
        parameters: Dictionary of scenario parameters (both required and optional)

    Returns:
        Dictionary with execution status and summary
    """
    manager = get_scenario_manager()
    scenario = manager.get_scenario(scenario_id)

    if not scenario:
        raise ValueError(f"Scenario '{scenario_id}' not found")

    # Validate required environment variables for MCP mode first
    if not settings.UNIFY_API_KEY:
        raise ValueError("UNIFY_API_KEY environment variable is required for MCP mode")

    if not settings.GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is required")

    # Use the parameters from the request (or empty dict if None)
    scenario_parameters = parameters or {}

    # Validate and preprocess input parameters
    processed_parameters = scenario.validate_input(scenario_parameters)

    # Create and execute pipeline
    pipeline = CreationPipeline(
        organization_id=organization_id,
        endpoint_id=settings.CLOUDBEES_ENDPOINT_ID,
        invitee_username=invitee_username,
        unify_pat=settings.UNIFY_API_KEY,
    )

    # Execute the complete scenario
    try:
        summary = await pipeline.execute_scenario(scenario, processed_parameters)

        return {
            "status": "success",
            "message": "Scenario executed successfully",
            "scenario_id": scenario_id,
            "organization_id": organization_id,
            "invitee_username": invitee_username,
            "parameters": processed_parameters,
            "summary": summary,
        }

    except ValidationError as e:
        logger.error(f"Validation error in MCP scenario instantiation: {e}")
        raise ValueError(f"Invalid parameters: {str(e)}") from e
    except PipelineError as e:
        logger.error(f"Pipeline error in MCP scenario {scenario_id}: {e}")
        raise ValueError(f"Pipeline execution failed at {e.step}: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error in MCP scenario {scenario_id}: {e}")
        raise ValueError(f"Pipeline execution failed: {str(e)}") from e
