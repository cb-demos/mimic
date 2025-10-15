"""Environment management commands for Mimic CLI."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..config_manager import ConfigManager
from ..environments import get_preset_environment, list_preset_environments

# Shared instances
console = Console()
config_manager = ConfigManager()

# Create the environment app
env_app = typer.Typer(help="Manage CloudBees Unify environments")


def prepare_environment_config(
    name: str,
    url: str | None = None,
    endpoint_id: str | None = None,
    custom_properties: dict[str, str] | None = None,
) -> tuple[str, str, str, dict[str, str]]:
    """Prepare environment configuration by resolving preset or custom settings.

    Args:
        name: Environment name (preset or custom).
        url: API URL (required for custom environments, optional for presets).
        endpoint_id: Endpoint ID (required for custom environments, optional for presets).
        custom_properties: Custom properties to merge with defaults.

    Returns:
        Tuple of (name, url, endpoint_id, properties).

    Raises:
        typer.Exit: If configuration is invalid.
    """
    custom_properties = custom_properties or {}

    # Check if this is a preset environment
    preset = get_preset_environment(name)

    if preset:
        # Using preset environment
        if url or endpoint_id:
            console.print(
                f"[yellow]Note:[/yellow] Using preset configuration for '{name}'. Ignoring --url and --endpoint-id options."
            )

        url = preset.url
        endpoint_id = preset.endpoint_id

        # Merge preset properties with custom properties (custom overrides preset)
        properties = preset.properties.copy()
        properties.update(custom_properties)
    else:
        # Custom environment - require url and endpoint_id
        if not url or not endpoint_id:
            console.print(
                f"[red]Error:[/red] Custom environment '{name}' requires --url and --endpoint-id"
            )
            console.print("\n[bold]Available preset environments:[/bold]")
            for preset_name, preset_config in list_preset_environments().items():
                console.print(
                    f"  • [cyan]{preset_name}[/cyan] - {preset_config.description}"
                )
            console.print(
                "\n[dim]Or add custom environment with: mimic env add <name> --url <url> --endpoint-id <id>[/dim]"
            )
            raise typer.Exit(1)

        # Start with default properties from prod preset
        prod_preset = get_preset_environment("prod")
        properties = prod_preset.properties.copy() if prod_preset else {}
        # Allow custom properties to override defaults
        properties.update(custom_properties)

    return name, url, endpoint_id, properties


@env_app.command("add")
def env_add(
    name: str = typer.Argument(
        ..., help="Environment name (preset: prod/preprod/demo or custom name)"
    ),
    url: str = typer.Option(
        None,
        "--url",
        help="CloudBees Unify API URL (required for custom environments)",
    ),
    endpoint_id: str = typer.Option(
        None,
        "--endpoint-id",
        help="CloudBees endpoint ID (required for custom environments)",
    ),
    property_list: list[str] = typer.Option(
        None,
        "--property",
        "-p",
        help="Custom property (KEY=VALUE, can be repeated)",
    ),
):
    """Add a new CloudBees Unify environment.

    Use preset environments (prod, preprod, demo) by just specifying the name,
    or add a custom environment by providing --url and --endpoint-id.

    Examples:
      mimic env add prod                                    # Add preset prod environment
      mimic env add custom --url https://api.example.com --endpoint-id abc-123
      mimic env add custom --url ... --endpoint-id ... --property USE_VPC=true --property FM_INSTANCE=custom.io
    """
    # Check if environment already exists
    environments = config_manager.list_environments()
    if name in environments:
        console.print(f"[red]Error:[/red] Environment '{name}' already exists")
        console.print(f"Use 'mimic env remove {name}' first to replace it")
        raise typer.Exit(1)

    # Parse custom properties from command line
    custom_properties = {}
    if property_list:
        for prop in property_list:
            if "=" not in prop:
                console.print(
                    f"[red]Error:[/red] Invalid property format '{prop}'. Use KEY=VALUE"
                )
                raise typer.Exit(1)
            key, value = prop.split("=", 1)
            custom_properties[key.strip()] = value.strip()

    # Prepare environment configuration
    name, url, endpoint_id, properties = prepare_environment_config(
        name, url, endpoint_id, custom_properties
    )

    # Display environment details
    preset = get_preset_environment(name)
    if preset:
        console.print(f"\n[bold]Adding preset environment:[/bold] {name}")
        console.print(f"[dim]Description:[/dim] {preset.description}")
    else:
        console.print(f"\n[bold]Adding custom environment:[/bold] {name}")

    console.print(f"[dim]API URL:[/dim] {url}")
    console.print(f"[dim]Endpoint ID:[/dim] {endpoint_id}")
    if properties:
        console.print("[dim]Properties:[/dim]")
        for key, value in properties.items():
            console.print(f"  • {key}: {value}")

    console.print()

    # Prompt for PAT securely
    pat = typer.prompt(
        "CloudBees Unify PAT",
        hide_input=True,
        confirmation_prompt=False,
    )

    # Validate credentials before saving
    console.print()
    console.print("[dim]Testing CloudBees API access...[/dim]")
    org_id = typer.prompt("Organization ID (for credential validation)")

    from ..unify import UnifyAPIClient

    try:
        # Create temporary client to validate credentials
        with UnifyAPIClient(base_url=url, api_key=pat) as client:
            success, error = client.validate_credentials(org_id)

            if not success:
                console.print()
                console.print(
                    Panel(
                        f"[red]✗ Credential validation failed[/red]\n\n"
                        f"Error: {error}\n\n"
                        f"[dim]Please check your PAT and organization ID and try again.[/dim]",
                        title="Validation Failed",
                        border_style="red",
                    )
                )
                raise typer.Exit(1)

        console.print("[green]✓[/green] CloudBees API access verified")
    except typer.Exit:
        raise
    except Exception as e:
        console.print()
        console.print(
            Panel(
                f"[red]✗ Error validating credentials[/red]\n\n{str(e)}",
                title="Validation Error",
                border_style="red",
            )
        )
        raise typer.Exit(1) from e

    # Add environment
    try:
        config_manager.add_environment(name, url, pat, endpoint_id, properties)
        console.print()

        # Build success message
        success_msg = (
            f"[green]✓[/green] Environment '{name}' added successfully\n\n"
            f"[dim]• API URL: {url}\n"
            f"• Endpoint ID: {endpoint_id}\n"
            f"• PAT stored securely in OS keyring\n"
        )
        if properties:
            success_msg += f"• Properties: {len(properties)} configured\n"
        success_msg += f"• Set as current environment: {config_manager.get_current_environment() == name}[/dim]"

        console.print(
            Panel(
                success_msg,
                title="Success",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Error adding environment:[/red] {e}")
        raise typer.Exit(1) from e


@env_app.command("list")
def env_list():
    """List all configured environments."""
    environments = config_manager.list_environments()
    current_env = config_manager.get_current_environment()

    if not environments:
        console.print(
            Panel(
                "[yellow]No environments configured[/yellow]\n\n"
                "Add a preset environment:\n"
                "[dim]mimic env add (prod|preprod|demo)[/dim]\n\n"
                "Or add a custom environment:\n"
                "[dim]mimic env add <name> --url <api-url> --endpoint-id <id>[/dim]",
                title="Environments",
                border_style="yellow",
            )
        )
        return

    # Create table
    table = Table(title="Configured Environments", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("API URL", style="white", no_wrap=False)
    table.add_column("Endpoint ID", style="dim", overflow="fold")
    table.add_column("Properties", style="yellow")
    table.add_column("Current", justify="center")

    for name, env_config in environments.items():
        is_current = "✓" if name == current_env else ""

        # Get custom properties (not built-in)
        properties = env_config.get("properties", {})
        prop_display = f"{len(properties)} set" if properties else "-"

        table.add_row(
            name,
            env_config.get("url", ""),
            env_config.get("endpoint_id", ""),
            prop_display,
            f"[green]{is_current}[/green]" if is_current else "",
        )

    console.print()
    console.print(table)
    console.print()

    if current_env:
        console.print(f"[dim]Current environment: [bold]{current_env}[/bold][/dim]")
    console.print()


@env_app.command("select")
def env_select(
    name: str = typer.Argument(..., help="Environment name to select"),
):
    """Select the current environment."""
    environments = config_manager.list_environments()

    if name not in environments:
        console.print(f"[red]Error:[/red] Environment '{name}' not found")
        console.print("\nAvailable environments:")
        for env_name in environments.keys():
            console.print(f"  • {env_name}")
        raise typer.Exit(1)

    config_manager.set_current_environment(name)
    env_url = config_manager.get_environment_url(name)

    console.print(
        Panel(
            f"[green]✓[/green] Current environment set to: [bold]{name}[/bold]\n\n"
            f"[dim]API URL: {env_url}[/dim]",
            title="Environment Selected",
            border_style="green",
        )
    )


@env_app.command("set-property")
def env_set_property(
    name: str = typer.Argument(..., help="Environment name"),
    key: str = typer.Argument(..., help="Property key"),
    value: str = typer.Argument(..., help="Property value"),
):
    """Set a custom property for an environment.

    Example:
      mimic env set-property demo USE_VPC true
    """
    environments = config_manager.list_environments()

    if name not in environments:
        console.print(f"[red]Error:[/red] Environment '{name}' not found")
        console.print("\nAvailable environments:")
        for env_name in environments.keys():
            console.print(f"  • {env_name}")
        raise typer.Exit(1)

    try:
        config_manager.set_environment_property(name, key, value)
        console.print(
            Panel(
                f"[green]✓[/green] Property set successfully\n\n"
                f"[dim]Environment: {name}\n"
                f"Property: {key} = {value}[/dim]",
                title="Property Updated",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Error setting property:[/red] {e}")
        raise typer.Exit(1) from e


@env_app.command("unset-property")
def env_unset_property(
    name: str = typer.Argument(..., help="Environment name"),
    key: str = typer.Argument(..., help="Property key"),
):
    """Remove a custom property from an environment.

    Example:
      mimic env unset-property demo USE_VPC
    """
    environments = config_manager.list_environments()

    if name not in environments:
        console.print(f"[red]Error:[/red] Environment '{name}' not found")
        console.print("\nAvailable environments:")
        for env_name in environments.keys():
            console.print(f"  • {env_name}")
        raise typer.Exit(1)

    try:
        config_manager.unset_environment_property(name, key)
        console.print(
            Panel(
                f"[green]✓[/green] Property removed successfully\n\n"
                f"[dim]Environment: {name}\n"
                f"Property: {key}[/dim]",
                title="Property Removed",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Error removing property:[/red] {e}")
        raise typer.Exit(1) from e


@env_app.command("remove")
def env_remove(
    name: str = typer.Argument(..., help="Environment name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Remove an environment."""
    environments = config_manager.list_environments()

    if name not in environments:
        console.print(f"[red]Error:[/red] Environment '{name}' not found")
        raise typer.Exit(1)

    # Confirm deletion unless --force is used
    if not force:
        env_url = config_manager.get_environment_url(name)
        console.print(
            f"\n[yellow]Warning:[/yellow] This will remove environment '[bold]{name}[/bold]'"
        )
        console.print(f"[dim]API URL: {env_url}[/dim]")
        console.print("[dim]The PAT will be deleted from OS keyring[/dim]\n")

        confirm = typer.confirm("Are you sure?", default=False)
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)

    # Remove environment
    try:
        was_current = config_manager.get_current_environment() == name
        config_manager.remove_environment(name)

        message = f"[green]✓[/green] Environment '[bold]{name}[/bold]' removed"
        if was_current:
            new_current = config_manager.get_current_environment()
            if new_current:
                message += f"\n\n[dim]Current environment set to: {new_current}[/dim]"
            else:
                message += "\n\n[yellow]No current environment set[/yellow]"

        console.print(Panel(message, title="Environment Removed", border_style="green"))
    except Exception as e:
        console.print(f"[red]Error removing environment:[/red] {e}")
        raise typer.Exit(1) from e
