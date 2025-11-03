"""Preview and dry-run functionality for the run command."""

import typer
from rich.console import Console

from ..display import display_scenario_preview

console = Console()


def handle_dry_run(
    config_manager,
    scenario,
    parameters: dict,
    current_env: str,
    expiration_label: str,
    organization_id: str,
):
    """Handle dry-run mode by displaying preview without executing.

    Args:
        config_manager: ConfigManager instance.
        scenario: Scenario object.
        parameters: Dictionary of parameter values.
        current_env: Current environment name.
        expiration_label: Human-readable expiration label.
        organization_id: CloudBees organization UUID.
    """
    from ...pipeline import CreationPipeline

    console.print(
        "[bold cyan]Dry run mode - no resources will be created[/bold cyan]\n"
    )

    # Validate and resolve scenario parameters
    processed_parameters = scenario.validate_input(parameters)
    # Get environment properties for template resolution
    env_properties = config_manager.get_environment_properties(current_env)
    # Inject runtime values
    runtime_values = {
        **processed_parameters,
        "organization_id": organization_id,
    }
    resolved_scenario = scenario.resolve_template_variables(
        runtime_values, env_properties
    )

    # Generate preview
    preview = CreationPipeline.preview_scenario(resolved_scenario)

    # Display preview
    display_scenario_preview(
        console,
        preview,
        scenario,
        current_env,
        expiration_label,
        is_dry_run=True,
    )


def show_preview_and_confirm(
    config_manager,
    scenario,
    parameters: dict,
    current_env: str,
    expiration_label: str,
    organization_id: str,
) -> bool:
    """Show preview and prompt for confirmation.

    Args:
        config_manager: ConfigManager instance.
        scenario: Scenario object.
        parameters: Dictionary of parameter values.
        current_env: Current environment name.
        expiration_label: Human-readable expiration label.
        organization_id: CloudBees organization UUID.

    Returns:
        True if user wants to proceed, False otherwise.
    """
    from ...pipeline import CreationPipeline

    console.print("[bold cyan]Preview - Resources to be created[/bold cyan]\n")

    # Validate and resolve scenario parameters
    processed_parameters = scenario.validate_input(parameters)
    # Get environment properties for template resolution
    env_properties = config_manager.get_environment_properties(current_env)
    # Inject runtime values
    runtime_values = {
        **processed_parameters,
        "organization_id": organization_id,
    }
    resolved_scenario = scenario.resolve_template_variables(
        runtime_values, env_properties
    )

    # Generate preview
    preview = CreationPipeline.preview_scenario(resolved_scenario)

    # Display preview with expiration info
    display_scenario_preview(console, preview, scenario, current_env, expiration_label)

    # Prompt for confirmation
    console.print()
    proceed = typer.confirm("Proceed with creation?", default=True)

    return proceed
