"""stdio MCP server for Mimic application."""

import logging
import os
from typing import Any

from fastmcp import Context, FastMCP

from .cleanup_manager import CleanupManager
from .config_manager import ConfigManager
from .exceptions import PipelineError, ValidationError
from .instance_repository import InstanceRepository
from .pipeline import CreationPipeline
from .scenarios import initialize_scenarios_from_config
from .unify import UnifyAPIClient
from .utils import resolve_run_name

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = FastMCP("Mimic Demo Orchestrator")

# Initialize managers
config_manager = ConfigManager()
scenario_manager = initialize_scenarios_from_config()


# Elicitation helper functions for progressive user interaction
async def _elicit_organization(
    ctx: Context, env_name: str, env_url: str, cloudbees_pat: str
) -> str:
    """Elicit CloudBees organization ID with cached names.

    Args:
        ctx: FastMCP context for elicitation
        env_name: Environment name
        env_url: CloudBees API URL
        cloudbees_pat: CloudBees PAT for API access

    Returns:
        Selected or entered organization ID
    """
    cached_orgs = config_manager.get_cached_orgs_for_env(env_name)

    if not cached_orgs:
        # No cached orgs, prompt for ID
        result = await ctx.elicit(
            "Please enter your CloudBees Organization ID (UUID format):",
            response_type=str,
        )

        if result.action != "accept":
            raise ValueError("Organization selection cancelled by user")

        org_id = str(result.data).strip()

        # Try to fetch and cache the org name
        try:
            with UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat) as client:
                org_data = client.get_organization(org_id)
                org_info = org_data.get("organization", {})
                org_name = org_info.get("displayName", "Unknown")
                config_manager.cache_org_name(org_id, org_name, env_name)
                logger.info(f"Cached organization: {org_name}")
        except Exception as e:
            logger.warning(f"Failed to fetch organization name: {e}")

        return org_id

    # Build choices with cached names
    choices = []
    org_id_map = {}

    for org_id, org_name in cached_orgs.items():
        display_text = f"{org_name} ({org_id[:8]}...)"
        choices.append(display_text)
        org_id_map[display_text] = org_id

    choices.append("Enter new organization ID...")

    result = await ctx.elicit(
        "Select your CloudBees Organization:",
        response_type=choices,
    )

    if result.action != "accept":
        raise ValueError("Organization selection cancelled by user")

    selection = str(result.data)

    if selection == "Enter new organization ID...":
        # User wants to enter new ID
        result = await ctx.elicit(
            "Please enter your CloudBees Organization ID (UUID format):",
            response_type=str,
        )

        if result.action != "accept":
            raise ValueError("Organization selection cancelled by user")

        org_id = str(result.data).strip()

        # Try to fetch and cache the org name
        try:
            with UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat) as client:
                org_data = client.get_organization(org_id)
                org_info = org_data.get("organization", {})
                org_name = org_info.get("displayName", "Unknown")
                config_manager.cache_org_name(org_id, org_name, env_name)
                logger.info(f"Cached organization: {org_name}")
        except Exception as e:
            logger.warning(f"Failed to fetch organization name: {e}")

        return org_id
    else:
        # User selected from cached list
        return org_id_map[selection]


async def _elicit_scenario(ctx: Context, scenario_id: str | None) -> str:
    """Elicit scenario selection if not provided.

    Args:
        ctx: FastMCP context for elicitation
        scenario_id: Scenario ID if already provided

    Returns:
        Selected scenario ID
    """
    if scenario_id:
        return scenario_id

    scenarios = scenario_manager.list_scenarios()
    if not scenarios:
        raise ValueError("No scenarios available")

    # Build choices with scenario name and summary
    choices = []
    scenario_map = {}

    for s in scenarios:
        display = f"{s['name']} ({s['id']})"
        if s.get("summary"):
            display += f" - {s['summary']}"
        choices.append(display)
        scenario_map[display] = s["id"]

    result = await ctx.elicit(
        "Select a scenario to run:",
        response_type=choices,
    )

    if result.action != "accept":
        raise ValueError("Scenario selection cancelled by user")

    return scenario_map[str(result.data)]


async def _elicit_expiration(ctx: Context, expires_in_days: int | None) -> int:
    """Elicit expiration days if not provided.

    Args:
        ctx: FastMCP context for elicitation
        expires_in_days: Expiration days if already provided

    Returns:
        Selected expiration days
    """
    if expires_in_days is not None:
        return expires_in_days

    # Get recent values
    recent_expirations = config_manager.get_recent_values("expiration_days")
    default_expiration = config_manager.get_setting("default_expiration_days", 7)

    # Build expiration options
    choices = []
    value_map = {}

    # Add recent values first (deduplicated)
    seen = set()
    for exp_val in recent_expirations:
        try:
            exp_int = int(exp_val)
            if exp_int not in seen and exp_int > 0:
                label = f"{exp_int} days"
                choices.append(label)
                value_map[label] = exp_int
                seen.add(exp_int)
        except (ValueError, TypeError):
            pass

    # Add default if not already in list
    if default_expiration not in seen:
        label = f"{default_expiration} days (default)"
        choices.append(label)
        value_map[label] = default_expiration
        seen.add(default_expiration)

    # Add common options if not in list
    for common in [1, 7, 14, 30]:
        if common not in seen:
            label = f"{common} days"
            choices.append(label)
            value_map[label] = common

    # Add "never" option
    choices.append("Never expires")
    value_map["Never expires"] = 365 * 10  # 10 years

    # Add custom option
    choices.append("Custom...")

    result = await ctx.elicit(
        "How long should the resources exist before cleanup?",
        response_type=choices,
    )

    if result.action != "accept":
        raise ValueError("Expiration selection cancelled by user")

    selection = str(result.data)

    if selection == "Custom...":
        # Prompt for custom days
        result = await ctx.elicit(
            "Enter custom expiration days:",
            response_type=int,
        )

        if result.action != "accept":
            raise ValueError("Expiration selection cancelled by user")

        custom_days = int(result.data)
        config_manager.add_recent_value("expiration_days", str(custom_days))
        return custom_days
    else:
        # Use mapped value
        days = value_map[selection]
        if days != 365 * 10:  # Don't cache "never"
            config_manager.add_recent_value("expiration_days", str(days))
        return days


async def _elicit_parameters(
    ctx: Context, scenario: Any, provided_parameters: dict[str, Any] | None
) -> dict[str, Any]:
    """Elicit scenario parameters interactively.

    Args:
        ctx: FastMCP context for elicitation
        scenario: Scenario object with parameter_schema
        provided_parameters: Parameters already provided

    Returns:
        Complete dictionary of parameter values
    """
    parameters = provided_parameters.copy() if provided_parameters else {}

    if not scenario.parameter_schema:
        return parameters

    # Iterate through required parameters first, then optional
    for prop_name, prop in scenario.parameter_schema.properties.items():
        is_required = prop_name in scenario.parameter_schema.required

        # Skip if already provided
        if prop_name in parameters:
            continue

        # Build prompt text
        prompt_text = prop_name.replace("_", " ").title()
        if prop.description:
            prompt_text = f"{prop_name.replace('_', ' ').title()}: {prop.description}"

        if not is_required:
            prompt_text += " (optional - type 'skip' to skip)"

        # Elicit based on type
        try:
            if prop.type == "boolean":
                result = await ctx.elicit(
                    prompt_text,
                    response_type=["Yes", "No"],
                )

                if result.action != "accept":
                    if is_required:
                        raise ValueError(
                            f"Required parameter '{prop_name}' cancelled by user"
                        )
                    continue

                parameters[prop_name] = str(result.data) == "Yes"

            elif prop.enum:
                result = await ctx.elicit(
                    prompt_text,
                    response_type=prop.enum,
                )

                if result.action != "accept":
                    if is_required:
                        raise ValueError(
                            f"Required parameter '{prop_name}' cancelled by user"
                        )
                    continue

                parameters[prop_name] = str(result.data)

            elif prop.type == "integer":
                result = await ctx.elicit(
                    prompt_text,
                    response_type=int,
                )

                if result.action != "accept":
                    if is_required:
                        raise ValueError(
                            f"Required parameter '{prop_name}' cancelled by user"
                        )
                    continue

                parameters[prop_name] = int(result.data)

            else:
                # String type
                # Special handling for GitHub org parameter
                if prop_name == "target_org":
                    recent_orgs = config_manager.get_recent_values("github_orgs")
                    if recent_orgs:
                        choices = recent_orgs + ["Enter new organization..."]
                        result = await ctx.elicit(
                            prompt_text,
                            response_type=choices,
                        )

                        if result.action != "accept":
                            if is_required:
                                raise ValueError(
                                    f"Required parameter '{prop_name}' cancelled by user"
                                )
                            continue

                        if str(result.data) == "Enter new organization...":
                            result = await ctx.elicit(
                                "Enter GitHub organization name:",
                                response_type=str,
                            )

                            if result.action != "accept":
                                if is_required:
                                    raise ValueError(
                                        f"Required parameter '{prop_name}' cancelled by user"
                                    )
                                continue

                            value = str(result.data).strip()
                            if value:
                                config_manager.add_recent_value("github_orgs", value)
                                parameters[prop_name] = value
                        else:
                            parameters[prop_name] = str(result.data)
                    else:
                        result = await ctx.elicit(
                            prompt_text,
                            response_type=str,
                        )

                        if result.action != "accept":
                            if is_required:
                                raise ValueError(
                                    f"Required parameter '{prop_name}' cancelled by user"
                                )
                            continue

                        value = str(result.data).strip()
                        if value:
                            config_manager.add_recent_value("github_orgs", value)
                            parameters[prop_name] = value
                else:
                    result = await ctx.elicit(
                        prompt_text,
                        response_type=str,
                    )

                    if result.action != "accept":
                        if is_required:
                            raise ValueError(
                                f"Required parameter '{prop_name}' cancelled by user"
                            )
                        continue

                    value = str(result.data).strip()
                    if value and value.lower() != "skip":
                        parameters[prop_name] = value

            # Validate the parameter
            scenario.validate_single_parameter(prop_name, parameters.get(prop_name))

        except ValidationError as e:
            logger.error(f"Validation error for parameter '{prop_name}': {e}")
            if is_required:
                raise ValueError(f"Invalid value for '{prop_name}': {str(e)}") from e

    return parameters


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
    ctx: Context,
    scenario_id: str | None = None,
    organization_id: str | None = None,
    invitee_username: str | None = None,
    expires_in_days: int | None = None,
    parameters: dict[str, Any] | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """
    Execute a complete scenario using the Creation Pipeline.

    This tool supports two modes:
    1. **Full automation**: Provide all parameters upfront for non-interactive execution
    2. **Interactive**: Omit parameters to be guided through selection with multi-turn prompts

    The tool will:
    1. Create repositories from templates with content replacements
    2. Create CloudBees components for repos that need them
    3. Create feature flags
    4. Create environments
    5. Create applications linking components and environments
    6. Configure flags across environments

    Args:
        ctx: FastMCP context for elicitation (provided automatically)
        scenario_id: The ID of the scenario to execute (optional - will prompt if not provided)
        organization_id: CloudBees Unify organization UUID (optional - will prompt with cached orgs)
        invitee_username: GitHub username to invite to repositories (optional)
        expires_in_days: Days until cleanup (optional - will prompt with recent values)
        parameters: Dictionary of scenario parameters (optional - will prompt for missing ones)
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

    # Use elicitation for missing parameters
    try:
        # Elicit organization if not provided
        if not organization_id:
            organization_id = await _elicit_organization(
                ctx, env_name, env_url, cloudbees_pat
            )

        # Elicit scenario if not provided
        scenario_id_resolved = await _elicit_scenario(ctx, scenario_id)

        # Get the scenario object
        scenario = scenario_manager.get_scenario(scenario_id_resolved)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id_resolved}' not found")

        # Elicit expiration if not provided
        expires_in_days_resolved = await _elicit_expiration(ctx, expires_in_days)

        # Elicit parameters if any are missing
        parameters_resolved = await _elicit_parameters(ctx, scenario, parameters)

        # Now execute with all resolved parameters
        return await _instantiate_scenario_impl(
            scenario_id=scenario_id_resolved,
            organization_id=organization_id,
            invitee_username=invitee_username,
            expires_in_days=expires_in_days_resolved,
            parameters=parameters_resolved,
            environment=env_name,
        )

    except ValueError as e:
        logger.error(f"Elicitation or validation error: {e}")
        raise


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
