import logging
from typing import Any

from fastmcp import FastMCP

from src.config import settings
from src.exceptions import PipelineError, ValidationError
from src.scenario_service import ScenarioService

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = FastMCP("Mimic")


@mcp.tool
def list_scenarios() -> list[dict[str, Any]]:
    """List all available scenarios with their parameter schemas."""
    service = ScenarioService()
    return service.list_scenarios()


@mcp.tool
async def instantiate_scenario(
    scenario_id: str,
    organization_id: str,
    email: str,
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
        email: User's CloudBees email address (required, for session tracking and cleanup)
        invitee_username: Optional GitHub username to invite to the organization
        parameters: Dictionary of scenario parameters (both required and optional)

    Returns:
        Dictionary with execution status and summary
    """
    # Validate required environment variables for MCP mode first
    if not settings.UNIFY_API_KEY:
        raise ValueError("UNIFY_API_KEY environment variable is required for MCP mode")

    if not settings.GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is required")

    service = ScenarioService()

    try:
        result = await service.execute_scenario(
            scenario_id=scenario_id,
            organization_id=organization_id,
            unify_pat=settings.UNIFY_API_KEY,
            email=email,
            invitee_username=invitee_username,
            parameters=parameters,
        )
        return result

    except ValidationError as e:
        logger.error(f"Validation error in MCP scenario instantiation: {e}")
        raise ValueError(f"Invalid parameters: {str(e)}") from e
    except PipelineError as e:
        logger.error(f"Pipeline error in MCP scenario {scenario_id}: {e}")
        raise ValueError(f"Pipeline execution failed at {e.step}: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error in MCP scenario {scenario_id}: {e}")
        raise ValueError(f"Pipeline execution failed: {str(e)}") from e
