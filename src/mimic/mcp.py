"""stdio MCP server for Mimic application."""

import logging
import os
from typing import Any

from fastmcp import FastMCP

from .cleanup_manager import CleanupManager
from .config_manager import ConfigManager
from .exceptions import PipelineError, ValidationError
from .instance_repository import InstanceRepository
from .pipeline import CreationPipeline
from .scenarios import initialize_scenarios_from_config
from .utils import resolve_run_name

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = FastMCP("Mimic Demo Orchestrator")

# Initialize managers
config_manager = ConfigManager()
scenario_manager = initialize_scenarios_from_config()


# Internal helper functions for testing
# These contain the actual logic and can be called directly in tests
def _list_scenarios_impl() -> list[dict[str, Any]]:
    """Internal: List all available scenarios."""
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
    """Internal: Execute a complete scenario using the Creation Pipeline."""
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
        from datetime import datetime, timedelta

        session_id = f"{scenario_id}-{uuid.uuid4().hex[:8]}"

        # Resolve instance name from scenario name_template
        instance_name = resolve_run_name(scenario, parameters or {}, session_id)

        # Calculate expiration datetime
        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

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
            scenario_id=scenario_id,
            instance_name=instance_name,
            environment=env_name,
            expires_at=expires_at,
        )

        summary = await pipeline.execute_scenario(scenario, parameters or {})

        # Save Instance to repository
        instance = summary.get("instance")
        if instance:
            repo = InstanceRepository()
            repo.save(instance)

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
    """Internal: Clean up all resources for a specific instance."""
    cleanup_manager = CleanupManager(config_manager=config_manager)

    try:
        result = await cleanup_manager.cleanup_session(
            session_id=session_id,
            dry_run=dry_run,
        )
        return result
    except ValueError as e:
        logger.error(f"Instance not found: {e}")
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
    Clean up all resources for a specific instance.

    This will:
    1. Delete GitHub repositories
    2. Delete CloudBees components
    3. Delete CloudBees applications
    4. Delete CloudBees environments
    5. Delete feature flags
    6. Remove instance from state tracking

    Args:
        session_id: Instance ID to clean up (parameter name kept for API compatibility)
        dry_run: If True, only show what would be cleaned up without doing it

    Returns:
        Dictionary with cleanup results including:
        - cleaned: List of successfully cleaned resources
        - errors: List of errors encountered
        - skipped: List of skipped resources

    Raises:
        ValueError: If instance not found
    """
    return await _cleanup_session_impl(session_id=session_id, dry_run=dry_run)


def run_mcp_server():
    """Run the MCP server in stdio mode."""
    import sys

    from .keyring_health import test_keyring_available

    # Check keyring availability before starting server
    logger.info("Checking keyring availability...")
    success, error_msg = test_keyring_available(timeout=3)
    if not success:
        logger.error("Keyring backend is not available")
        print("Error: Keyring backend is not available\n", file=sys.stderr)
        print(error_msg, file=sys.stderr)
        print(
            "\nThe MCP server requires a functioning keyring to store credentials securely.",
            file=sys.stderr,
        )
        print(
            "Please fix the keyring setup before starting the MCP server.",
            file=sys.stderr,
        )
        sys.exit(1)

    logger.info("Keyring backend is available")
    logger.info("Starting Mimic MCP server in stdio mode")
    mcp.run()


if __name__ == "__main__":
    run_mcp_server()
