"""Scenario execution and resource tracking for the run command."""

import asyncio
import uuid

from rich.console import Console

from ...utils import resolve_run_name
from ..display import display_success_summary

console = Console()


def execute_scenario(
    config_manager,
    scenario,
    parameters: dict,
    scenario_id: str,
    current_env: str,
    expiration_days: int,
    expiration_label: str,
    no_expiration: bool,
    organization_id: str,
    endpoint_id: str,
    cloudbees_pat: str,
    env_url: str,
    github_pat: str,
):
    """Execute the scenario and track resources in state.

    Args:
        config_manager: ConfigManager instance.
        scenario: Scenario object.
        parameters: Dictionary of parameter values.
        scenario_id: Scenario ID.
        current_env: Current environment name.
        expiration_days: Number of days until expiration.
        expiration_label: Human-readable expiration label.
        no_expiration: Whether resources never expire.
        organization_id: CloudBees Organization ID.
        endpoint_id: CloudBees endpoint ID.
        cloudbees_pat: CloudBees Personal Access Token.
        env_url: CloudBees Unify API URL.
        github_pat: GitHub Personal Access Token.
    """
    from ...pipeline import CreationPipeline
    from ...state_tracker import StateTracker

    # Generate session ID
    session_id = str(uuid.uuid4())[:8]

    # Resolve run name from scenario name_template
    run_name = resolve_run_name(scenario, parameters, session_id)

    # Create state tracker and session
    state_tracker = StateTracker()
    state_tracker.create_session(
        session_id=session_id,
        scenario_id=scenario_id,
        run_name=run_name,
        environment=current_env,
        expiration_days=expiration_days,
        metadata={
            "parameters": parameters,
            "no_expiration": no_expiration,
        },
    )

    # Create and run pipeline
    console.print("[bold green]Starting scenario execution...[/bold green]")
    console.print(f"[dim]Run Name: {run_name}[/dim]")
    console.print(f"[dim]Session ID: {session_id}[/dim]")
    console.print(f"[dim]Environment: {current_env}[/dim]")
    console.print()

    # Get default GitHub username for repo invitations
    invitee_username = config_manager.get_github_username()

    # Get environment properties
    env_properties = config_manager.get_environment_properties(current_env)

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

    # Execute scenario
    summary = asyncio.run(pipeline.execute_scenario(scenario, parameters))

    # Track resources in state
    # Add repositories
    for repo_data in summary.get("repositories", []):
        state_tracker.add_resource(
            session_id=session_id,
            resource_type="github_repo",
            resource_id=repo_data.get("full_name", ""),
            resource_name=repo_data.get("name", ""),
            metadata=repo_data,
        )

    # Add components
    for component_name, component_data in pipeline.created_components.items():
        state_tracker.add_resource(
            session_id=session_id,
            resource_type="cloudbees_component",
            resource_id=component_data.get("id", ""),
            resource_name=component_name,
            org_id=organization_id,
            metadata=component_data,
        )

    # Add environments
    for env_name, env_data in pipeline.created_environments.items():
        state_tracker.add_resource(
            session_id=session_id,
            resource_type="cloudbees_environment",
            resource_id=env_data.get("id", ""),
            resource_name=env_name,
            org_id=organization_id,
            metadata=env_data,
        )

    # Add applications
    for app_name, app_data in pipeline.created_applications.items():
        state_tracker.add_resource(
            session_id=session_id,
            resource_type="cloudbees_application",
            resource_id=app_data.get("id", ""),
            resource_name=app_name,
            org_id=organization_id,
            metadata=app_data,
        )

    # Build success message with resource details
    console.print()
    display_success_summary(
        console=console,
        session_id=session_id,
        run_name=run_name,
        environment=current_env,
        expiration_label=expiration_label,
        summary=summary,
        pipeline=pipeline,
    )
