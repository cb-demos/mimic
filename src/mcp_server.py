from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel

from src.config import settings
from src.creation_pipeline import CreationPipeline
from src.scenarios import get_scenario_manager


class InstantiateScenarioRequest(BaseModel):
    scenario_id: str
    organization_id: str
    invitee_username: str | None = None
    parameters: dict[str, Any] | None = None


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
    project_name: str | None = None,
    target_org: str | None = None,
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
        project_name: Name for the project (used in repo/component names)
        target_org: GitHub organization where repositories will be created

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

    # Build parameters dict from individual parameters
    parameters = {}
    if project_name:
        parameters["project_name"] = project_name
    if target_org:
        parameters["target_org"] = target_org

    # Validate input parameters
    scenario.validate_input(parameters)

    # Create and execute pipeline
    pipeline = CreationPipeline(
        organization_id=organization_id,
        endpoint_id=settings.CLOUDBEES_ENDPOINT_ID,
        invitee_username=invitee_username,
        unify_pat=settings.UNIFY_API_KEY,
    )

    # Execute the complete scenario
    try:
        summary = await pipeline.execute_scenario(scenario, parameters)

        return {
            "status": "success",
            "message": "Scenario executed successfully",
            "scenario_id": scenario_id,
            "organization_id": organization_id,
            "invitee_username": invitee_username,
            "project_name": project_name,
            "target_org": target_org,
            "summary": summary,
        }

    except Exception as e:
        raise ValueError(f"Pipeline execution failed: {str(e)}") from e
