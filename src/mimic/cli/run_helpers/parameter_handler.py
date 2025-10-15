"""Parameter parsing and collection for the run command."""

import json
from pathlib import Path

import typer
from rich.console import Console

from ...exceptions import ValidationError
from ...input_helpers import format_field_name, prompt_github_org

console = Console()


def parse_parameters(
    param_file: str | None, set_params: list[str] | None
) -> dict[str, str]:
    """Parse parameters from JSON file and --set flags.

    Args:
        param_file: Path to JSON parameter file.
        set_params: List of "key=value" strings from --set flags.

    Returns:
        Dictionary of parameter names to values.
    """
    provided_parameters = {}

    # Load from JSON file if provided
    if param_file:
        try:
            file_path = Path(param_file)
            if not file_path.exists():
                console.print(
                    f"[red]Error:[/red] Parameter file not found: {param_file}"
                )
                raise typer.Exit(1)

            with open(file_path) as f:
                file_params = json.load(f)

            if not isinstance(file_params, dict):
                console.print(
                    f"[red]Error:[/red] Parameter file must contain a JSON object (got {type(file_params).__name__})"
                )
                raise typer.Exit(1)

            provided_parameters.update(file_params)
            console.print(
                f"[dim]Loaded {len(file_params)} parameter(s) from {param_file}[/dim]"
            )
        except json.JSONDecodeError as e:
            console.print(f"[red]Error:[/red] Invalid JSON in parameter file: {e}")
            raise typer.Exit(1) from e

    # Parse --set flags (these override file parameters)
    if set_params:
        for param in set_params:
            if "=" not in param:
                console.print(
                    f"[red]Error:[/red] Invalid --set format: '{param}'. Use: --set name=value"
                )
                raise typer.Exit(1)

            key, value = param.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                console.print("[red]Error:[/red] Parameter name cannot be empty")
                raise typer.Exit(1)

            provided_parameters[key] = value

        console.print(f"[dim]Set {len(set_params)} parameter(s) from --set flags[/dim]")

    return provided_parameters


def collect_parameters(scenario, provided_parameters: dict) -> dict:
    """Collect parameters by merging provided parameters with interactive prompts.

    Args:
        scenario: Scenario object with parameter_schema.
        provided_parameters: Parameters already provided via file or --set flags.

    Returns:
        Complete dictionary of parameter values.
    """
    parameters = provided_parameters.copy()

    if scenario.parameter_schema:
        # Determine if we need to prompt for any parameters
        missing_params = []
        for prop_name, prop in scenario.parameter_schema.properties.items():
            is_required = prop_name in scenario.parameter_schema.required

            # Check if parameter is missing or empty
            if prop_name not in parameters or (
                is_required and not str(parameters.get(prop_name, "")).strip()
            ):
                missing_params.append((prop_name, prop, is_required))

        # Convert string boolean values in provided parameters to actual booleans
        for prop_name, prop in scenario.parameter_schema.properties.items():
            if prop.type == "boolean" and prop_name in parameters:
                value = parameters[prop_name]
                if isinstance(value, str):
                    if value.lower() in ("true", "yes", "1", "on"):
                        parameters[prop_name] = True
                    elif value.lower() in ("false", "no", "0", "off", ""):
                        parameters[prop_name] = False

        # If there are missing parameters, prompt for them
        if missing_params:
            for prop_name, prop, is_required in missing_params:
                # Format field name nicely
                formatted_name = format_field_name(prop_name)

                # Build prompt text
                if prop.description:
                    prompt_text = f"{formatted_name}: {prop.description}"
                else:
                    prompt_text = formatted_name

                # Add optional indicator
                if not is_required:
                    prompt_text += " [optional]"

                # Retry loop for validation
                value = None
                while True:
                    try:
                        # Special handling for GitHub org parameter
                        if prop_name == "target_org":
                            value = prompt_github_org(
                                description=prompt_text,
                                required=is_required,
                            )
                        # Prompt based on type
                        elif prop.type == "boolean":
                            value = typer.confirm(
                                prompt_text, default=prop.default or False
                            )
                        elif prop.enum:
                            # For enum, use questionary for better UX
                            import questionary

                            value = questionary.select(
                                prompt_text,
                                choices=prop.enum,
                                default=prop.default or prop.enum[0],
                            ).ask()
                        else:
                            # Regular text prompt
                            default_val = prop.default or ""
                            value = typer.prompt(
                                prompt_text,
                                default=default_val,
                                show_default=bool(prop.default),
                            )

                        # Validate the parameter immediately
                        if value or is_required or value == 0 or value is False:
                            scenario.validate_single_parameter(prop_name, value)

                        # If we get here, validation passed
                        break

                    except ValidationError as e:
                        # Show validation error and re-prompt
                        console.print(f"[red]✗ {str(e)}[/red]")
                        if not is_required:
                            # For optional fields, allow them to skip on error
                            skip = typer.confirm(
                                "Skip this optional parameter?", default=True
                            )
                            if skip:
                                value = None
                                break
                        # Otherwise, loop and re-prompt

                # Add the validated value
                if (
                    value or not is_required or value == 0 or value is False
                ):  # Add value (or empty string for optional params)
                    parameters[prop_name] = value

            console.print()
        elif provided_parameters:
            # All parameters provided, show confirmation
            for key, value in parameters.items():
                console.print(f"  • {key}: [yellow]{value}[/yellow]")
            console.print()

    return parameters
