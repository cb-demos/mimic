"""HTTP MCP server for Mimic application."""

import logging
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from src.auth import get_auth_service
from src.exceptions import PipelineError, ValidationError
from src.scenario_service import ScenarioService

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = FastMCP("Mimic Demo Orchestrator")


@mcp.tool
def list_scenarios() -> list[dict[str, Any]]:
    """List all available scenarios with their parameter schemas."""
    service = ScenarioService()
    return service.list_scenarios()


@mcp.tool
async def instantiate_scenario(
    scenario_id: str,
    organization_id: str,
    invitee_username: str | None = None,
    expires_in_days: int | None = 7,
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
        invitee_username: GitHub username to invite (defaults to GITHUB_USERNAME env var)
        expires_in_days: Days until cleanup (1, 7, 14, 30, or None for never)
        parameters: Dictionary of ALL scenario parameters (required and optional)

    Headers (passed by MCP client):
        EMAIL: User's email address (required)
        UNIFY_API_KEY: CloudBees API token (required)
        GITHUB_TOKEN: Custom GitHub PAT (optional, defaults to service account)
        GITHUB_USERNAME: User's GitHub username (optional, used as default invitee)

    Returns:
        Dictionary with execution status and summary
    """
    # Extract credentials from headers (MCP passes these through)
    headers = get_http_headers()
    email = headers.get("EMAIL") or headers.get("email")
    unify_pat = headers.get("UNIFY_API_KEY") or headers.get("unify_api_key")
    github_pat = headers.get("GITHUB_TOKEN") or headers.get("github_token")
    github_username = headers.get("GITHUB_USERNAME") or headers.get("github_username")

    # Validate required credentials
    if not email:
        raise ValueError("EMAIL header is required for MCP mode")
    if not unify_pat:
        raise ValueError("UNIFY_API_KEY header is required for MCP mode")

    # Validate CloudBees email domain
    if not email.strip().lower().endswith("@cloudbees.com"):
        raise ValueError("Only CloudBees email addresses are allowed")

    email = email.lower().strip()

    # Store PATs in database on first use
    auth_service = get_auth_service()
    try:
        await auth_service.store_user_tokens(
            email=email, unify_pat=unify_pat, github_pat=github_pat
        )
        if github_pat:
            logger.info(f"Stored custom GitHub PAT for {email}")
        else:
            logger.info(f"Using default service account GitHub PAT for {email}")
    except Exception as e:
        logger.error(f"Failed to store PATs for {email}: {e}")
        # Continue anyway - the service might still work

    # Use GITHUB_USERNAME as default invitee if not specified
    final_invitee = invitee_username or github_username

    try:
        # Execute scenario
        service = ScenarioService()
        result = await service.execute_scenario(
            scenario_id=scenario_id,
            organization_id=organization_id,
            unify_pat=unify_pat,
            email=email,
            invitee_username=final_invitee,
            parameters=parameters,
            expires_in_days=expires_in_days,
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
