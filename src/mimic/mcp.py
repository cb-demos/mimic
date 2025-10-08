"""stdio MCP server for Mimic application."""

import logging
import os
from typing import Any

from fastmcp import FastMCP

from .cleanup_manager import CleanupManager
from .config_manager import ConfigManager
from .creation_pipeline import CreationPipeline
from .exceptions import PipelineError, ValidationError
from .scenarios import initialize_scenarios_from_config

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = FastMCP("Mimic Demo Orchestrator")

# Initialize managers
config_manager = ConfigManager()
scenario_manager = initialize_scenarios_from_config()


def _list_scenarios_impl() -> list[dict[str, Any]]:
    """
    List all available scenarios with their parameter schemas.

    Returns:
        List of scenario dictionaries with id, name, summary, and parameter schema
    """
    return scenario_manager.list_scenarios()


@mcp.tool
def list_scenarios() -> list[dict[str, Any]]:
    """
    List all available scenarios with their parameter schemas.

    Returns:
        List of scenario dictionaries with id, name, summary, and parameter schema
    """
    return _list_scenarios_impl()


async def _instantiate_scenario_impl(
    scenario_id: str,
    organization_id: str,
    invitee_username: str | None = None,
    expires_in_days: int | None = 7,
    parameters: dict[str, Any] | None = None,
    environment: str | None = None,
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
        invitee_username: GitHub username to invite to repositories (optional)
        expires_in_days: Days until cleanup (1, 7, 14, 30, or None for never)
        parameters: Dictionary of ALL scenario parameters (required and optional)
        environment: CloudBees environment name (defaults to current environment)

    Environment Variables (required):
        MIMIC_CLOUDBEES_PAT: CloudBees API token (or configured in keyring)
        MIMIC_GITHUB_PAT: GitHub PAT (or configured in keyring)

    Returns:
        Dictionary with execution status and summary

    Raises:
        ValueError: If credentials are missing or invalid
        ValidationError: If scenario parameters are invalid
        PipelineError: If pipeline execution fails
    """
    # Get environment (use specified or current)
    env_name = environment or config_manager.get_current_environment()
    if not env_name:
        raise ValueError(
            "No environment specified and no current environment set. "
            "Set an environment with: mimic env select <name>"
        )

    # Get credentials from environment variables or keyring
    cloudbees_pat = os.getenv(
        "MIMIC_CLOUDBEES_PAT"
    ) or config_manager.get_cloudbees_pat(env_name)
    github_pat = os.getenv("MIMIC_GITHUB_PAT") or config_manager.get_github_pat()

    if not cloudbees_pat:
        raise ValueError(
            f"CloudBees PAT not found for environment '{env_name}'. "
            "Set via MIMIC_CLOUDBEES_PAT env var or configure with: mimic env add"
        )

    if not github_pat:
        raise ValueError(
            "GitHub PAT not found. "
            "Set via MIMIC_GITHUB_PAT env var or configure with: mimic env add"
        )

    # Get environment config
    env_url = config_manager.get_environment_url(env_name)
    endpoint_id = config_manager.get_endpoint_id(env_name)

    if not env_url or not endpoint_id:
        raise ValueError(
            f"Environment '{env_name}' configuration incomplete. "
            "Reconfigure with: mimic env add"
        )

    try:
        # Get scenario
        scenario = scenario_manager.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id}' not found")

        # Generate session ID
        import uuid

        session_id = f"{scenario_id}-{uuid.uuid4().hex[:8]}"

        # Get environment properties
        env_properties = config_manager.get_environment_properties(env_name)

        # Execute pipeline
        pipeline = CreationPipeline(
            organization_id=organization_id,
            endpoint_id=endpoint_id,
            unify_pat=cloudbees_pat,
            unify_base_url=env_url,
            session_id=session_id,
            github_pat=github_pat,
            invitee_username=invitee_username,
            env_properties=env_properties,
        )

        summary = await pipeline.execute_scenario(scenario, parameters or {})

        # Track resources in state
        from .state_tracker import StateTracker

        state_tracker = StateTracker()

        # Add session (None = never expires)
        state_tracker.create_session(
            session_id=session_id,
            scenario_id=scenario_id,
            environment=env_name,
            expiration_days=expires_in_days,
        )

        # Add repositories
        for repo_data in summary.get("repositories", []):
            state_tracker.add_resource(
                session_id=session_id,
                resource_type="github_repo",
                resource_id=repo_data.get("full_name", ""),
                resource_name=repo_data.get("name", ""),
                metadata=repo_data,
            )

        # Add CloudBees components
        for comp_data in summary.get("components", []):
            state_tracker.add_resource(
                session_id=session_id,
                resource_type="cloudbees_component",
                resource_id=comp_data.get("id", ""),
                resource_name=comp_data.get("name", ""),
                metadata=comp_data,
            )

        # Add CloudBees environments
        for env_data in summary.get("environments", []):
            state_tracker.add_resource(
                session_id=session_id,
                resource_type="cloudbees_environment",
                resource_id=env_data.get("id", ""),
                resource_name=env_data.get("name", ""),
                metadata=env_data,
            )

        # Add CloudBees applications
        for app_data in summary.get("applications", []):
            state_tracker.add_resource(
                session_id=session_id,
                resource_type="cloudbees_application",
                resource_id=app_data.get("id", ""),
                resource_name=app_data.get("name", ""),
                metadata=app_data,
            )

        # Add feature flags
        for flag_data in summary.get("flags", []):
            state_tracker.add_resource(
                session_id=session_id,
                resource_type="cloudbees_flag",
                resource_id=flag_data.get("id", ""),
                resource_name=flag_data.get("name", ""),
                metadata=flag_data,
            )

        return {
            "status": "success",
            "scenario_id": scenario_id,
            "environment": env_name,
            "session_id": session_id,
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


@mcp.tool
async def instantiate_scenario(
    scenario_id: str,
    organization_id: str,
    invitee_username: str | None = None,
    expires_in_days: int | None = 7,
    parameters: dict[str, Any] | None = None,
    environment: str | None = None,
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
        invitee_username: GitHub username to invite to repositories (optional)
        expires_in_days: Days until cleanup (1, 7, 14, 30, or None for never)
        parameters: Dictionary of ALL scenario parameters (required and optional)
        environment: CloudBees environment name (defaults to current environment)

    Environment Variables (required):
        MIMIC_CLOUDBEES_PAT: CloudBees API token (or configured in keyring)
        MIMIC_GITHUB_PAT: GitHub PAT (or configured in keyring)

    Returns:
        Dictionary with execution status and summary

    Raises:
        ValueError: If credentials are missing or invalid
        ValidationError: If scenario parameters are invalid
        PipelineError: If pipeline execution fails
    """
    return await _instantiate_scenario_impl(
        scenario_id=scenario_id,
        organization_id=organization_id,
        invitee_username=invitee_username,
        expires_in_days=expires_in_days,
        parameters=parameters,
        environment=environment,
    )


async def _cleanup_session_impl(
    session_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Clean up all resources for a specific session.

    This will:
    1. Delete GitHub repositories
    2. Delete CloudBees components
    3. Delete CloudBees applications
    4. Delete CloudBees environments
    5. Delete feature flags
    6. Remove session from state tracking

    Args:
        session_id: Session ID to clean up
        dry_run: If True, only show what would be cleaned up without doing it

    Returns:
        Dictionary with cleanup results including:
        - cleaned: List of successfully cleaned resources
        - errors: List of errors encountered
        - skipped: List of skipped resources

    Raises:
        ValueError: If session not found
    """
    cleanup_manager = CleanupManager(config_manager=config_manager)

    try:
        result = await cleanup_manager.cleanup_session(
            session_id=session_id,
            dry_run=dry_run,
        )
        return result
    except ValueError as e:
        logger.error(f"Session not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        raise ValueError(f"Cleanup failed: {str(e)}") from e


@mcp.tool
async def cleanup_session(
    session_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Clean up all resources for a specific session.

    This will:
    1. Delete GitHub repositories
    2. Delete CloudBees components
    3. Delete CloudBees applications
    4. Delete CloudBees environments
    5. Delete feature flags
    6. Remove session from state tracking

    Args:
        session_id: Session ID to clean up
        dry_run: If True, only show what would be cleaned up without doing it

    Returns:
        Dictionary with cleanup results including:
        - cleaned: List of successfully cleaned resources
        - errors: List of errors encountered
        - skipped: List of skipped resources

    Raises:
        ValueError: If session not found
    """
    return await _cleanup_session_impl(
        session_id=session_id,
        dry_run=dry_run,
    )


def run_mcp_server():
    """Run the MCP server in stdio mode."""
    logger.info("Starting Mimic MCP server in stdio mode")
    mcp.run()


if __name__ == "__main__":
    run_mcp_server()
