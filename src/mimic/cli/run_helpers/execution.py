"""Scenario execution and resource tracking for the run command."""

import asyncio
import uuid
from datetime import timedelta

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
    from datetime import datetime

    from ...instance_repository import InstanceRepository
    from ...pipeline import CreationPipeline

    # Generate session ID
    session_id = str(uuid.uuid4())[:8]

    # Resolve run name from scenario name_template
    run_name = resolve_run_name(scenario, parameters, session_id)

    # Calculate expiration datetime
    now = datetime.now()
    expires_at = None if no_expiration else now + timedelta(days=expiration_days)

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

    # Check if environment uses legacy flags API
    use_legacy_flags = config_manager.get_environment_uses_legacy_flags(current_env)

    pipeline = CreationPipeline(
        organization_id=organization_id,
        endpoint_id=endpoint_id,
        unify_pat=cloudbees_pat,
        unify_base_url=env_url,
        session_id=session_id,
        github_pat=github_pat,
        invitee_username=invitee_username,
        env_properties=env_properties,
        # New parameters for Instance creation
        scenario_id=scenario_id,
        instance_name=run_name,
        environment=current_env,
        expires_at=expires_at,
        use_legacy_flags=use_legacy_flags,
    )

    # Execute scenario
    summary = asyncio.run(pipeline.execute_scenario(scenario, parameters))

    # Save Instance to repository
    instance = summary.get("instance")
    if instance:
        repo = InstanceRepository()
        repo.save(instance)

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
