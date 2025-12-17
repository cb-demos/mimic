"""Tenant management commands for Mimic CLI."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..config_manager import ConfigManager
from ..environments import get_preset_tenant, list_preset_tenants

# Shared instances
console = Console()
config_manager = ConfigManager()

# Create the tenant app
tenant_app = typer.Typer(
    help="Manage CloudBees Unify tenants",
    no_args_is_help=True,
)


def prepare_tenant_config(
    name: str,
    url: str | None = None,
    endpoint_id: str | None = None,
    custom_properties: dict[str, str] | None = None,
    use_legacy_flags: bool | None = None,
) -> tuple[str, str, str, dict[str, str], bool]:
    """Prepare tenant configuration by resolving preset or custom settings.

    Args:
        name: Tenant name (preset or custom).
        url: API URL (required for custom tenants, optional for presets).
        endpoint_id: Endpoint ID (required for custom tenants, optional for presets).
        custom_properties: Custom properties to merge with defaults.
        use_legacy_flags: Whether to use legacy org-based flag API (None = use preset/default).

    Returns:
        Tuple of (name, url, endpoint_id, properties, use_legacy_flags).

    Raises:
        typer.Exit: If configuration is invalid.
    """
    custom_properties = custom_properties or {}

    # Check if this is a preset tenant
    preset = get_preset_tenant(name)

    if preset:
        # Using preset tenant
        if url or endpoint_id:
            console.print(
                f"[yellow]Note:[/yellow] Using preset configuration for '{name}'. Ignoring --url and --endpoint-id options."
            )

        url = preset.url
        endpoint_id = preset.endpoint_id

        # Use preset's use_legacy_flags if not explicitly provided
        if use_legacy_flags is None:
            use_legacy_flags = preset.use_legacy_flags

        # Merge preset properties with custom properties (custom overrides preset)
        properties = preset.properties.copy()
        properties.update(custom_properties)
    else:
        # Custom tenant - require url and endpoint_id
        if not url or not endpoint_id:
            console.print(
                f"[red]Error:[/red] Custom tenant '{name}' requires --url and --endpoint-id"
            )
            console.print("\n[bold]Available preset tenants:[/bold]")
            for preset_name, preset_config in list_preset_tenants().items():
                console.print(
                    f"  • [cyan]{preset_name}[/cyan] - {preset_config.description}"
                )
            console.print(
                "\n[dim]Or add custom tenant with: mimic tenant add <name> --url <url> --endpoint-id <id>[/dim]"
            )
            raise typer.Exit(1)

        # Default to new app-based flag API for custom tenants
        if use_legacy_flags is None:
            use_legacy_flags = False

        # Start with default properties from prod preset
        prod_preset = get_preset_tenant("prod")
        properties = prod_preset.properties.copy() if prod_preset else {}
        # Allow custom properties to override defaults
        properties.update(custom_properties)

    return name, url, endpoint_id, properties, use_legacy_flags


@tenant_app.command("add")
def tenant_add(
    name: str | None = typer.Argument(
        None,
        help="Tenant name (preset: prod/preprod/demo or custom name, interactive selection if omitted)",
    ),
    url: str = typer.Option(
        None,
        "--url",
        help="CloudBees Unify API URL (required for custom tenants)",
    ),
    endpoint_id: str = typer.Option(
        None,
        "--endpoint-id",
        help="CloudBees endpoint ID (required for custom tenants)",
    ),
    property_list: list[str] = typer.Option(
        None,
        "--property",
        "-p",
        help="Custom property (KEY=VALUE, can be repeated)",
    ),
    use_legacy_flags: bool | None = typer.Option(
        None,
        "--use-legacy-flags/--no-legacy-flags",
        help="Use org-based flag API (True) or app-based flag API (False). Defaults to preset value or False.",
    ),
):
    """Add a new CloudBees Unify tenant.

    Use preset tenants (prod, preprod, demo) by just specifying the name,
    or add a custom tenant by providing --url and --endpoint-id.

    Examples:
      mimic tenant add                                         # Interactive selection
      mimic tenant add prod                                    # Add preset prod tenant
      mimic tenant add custom --url https://api.example.com --endpoint-id abc-123
      mimic tenant add custom --url ... --endpoint-id ... --property USE_VPC=true --property FM_INSTANCE=custom.io
    """
    tenants = config_manager.list_tenants()

    # Interactive tenant selection if not provided
    if not name:
        import questionary

        # Get available preset tenants that aren't already configured
        all_presets = list_preset_tenants()
        available_presets = {
            name: config for name, config in all_presets.items() if name not in tenants
        }

        if not available_presets:
            console.print(
                Panel(
                    "[yellow]All preset tenants are already configured[/yellow]\n\n"
                    "You can add a custom tenant by providing a name:\n"
                    "[dim]mimic tenant add <name> --url <url> --endpoint-id <id>[/dim]\n\n"
                    "Or list configured tenants:\n"
                    "[dim]mimic tenant list[/dim]",
                    title="Tenants",
                    border_style="yellow",
                )
            )
            raise typer.Exit(0)

        # Build choices with preset details + custom option
        choices = []
        preset_map = {}

        for preset_name, preset_config in available_presets.items():
            display = f"{preset_name} - {preset_config.description}"
            choices.append(display)
            preset_map[display] = preset_name

        # Add custom option
        custom_option = "Custom tenant..."
        choices.append(custom_option)

        console.print()
        selection = questionary.select(
            "Select a tenant to add:",
            choices=choices,
            use_shortcuts=True,
            use_arrow_keys=True,
        ).ask()

        if not selection:
            # User cancelled
            raise typer.Exit(0)

        if selection == custom_option:
            # Custom tenant - prompt for details
            console.print()
            name = typer.prompt("Tenant name")
            if not url:
                url = typer.prompt("API URL")
            if not endpoint_id:
                endpoint_id = typer.prompt("Endpoint ID")
        else:
            # Preset tenant selected
            name = preset_map[selection]

        console.print()

    # Type guard: name is guaranteed to be a string here
    # (either provided as argument or selected interactively)
    assert name is not None

    # Check if tenant already exists
    if name in tenants:
        console.print(f"[red]Error:[/red] Tenant '{name}' already exists")
        console.print(f"Use 'mimic tenant remove {name}' first to replace it")
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

    # Prepare tenant configuration
    name, url, endpoint_id, properties, resolved_use_legacy_flags = (
        prepare_tenant_config(
            name, url, endpoint_id, custom_properties, use_legacy_flags
        )
    )

    # Display tenant details
    preset = get_preset_tenant(name)
    if preset:
        console.print(f"\n[bold]Adding preset tenant:[/bold] {name}")
        console.print(f"[dim]Description:[/dim] {preset.description}")
    else:
        console.print(f"\n[bold]Adding custom tenant:[/bold] {name}")

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

    # Add tenant
    try:
        config_manager.add_tenant(
            name=name,
            url=url,
            pat=pat,
            endpoint_id=endpoint_id,
            properties=properties,
            use_legacy_flags=resolved_use_legacy_flags,
        )
        console.print()

        # Build success message
        success_msg = (
            f"[green]✓[/green] Tenant '{name}' added successfully\n\n"
            f"[dim]• API URL: {url}\n"
            f"• Endpoint ID: {endpoint_id}\n"
            f"• PAT stored securely in OS keyring\n"
        )
        if properties:
            success_msg += f"• Properties: {len(properties)} configured\n"
        success_msg += f"• Set as current tenant: {config_manager.get_current_tenant() == name}[/dim]"

        console.print(
            Panel(
                success_msg,
                title="Success",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Error adding tenant:[/red] {e}")
        raise typer.Exit(1) from e


@tenant_app.command("list")
def tenant_list():
    """List all configured tenants."""
    tenants = config_manager.list_tenants()
    current_tenant = config_manager.get_current_tenant()

    if not tenants:
        console.print(
            Panel(
                "[yellow]No tenants configured[/yellow]\n\n"
                "Add a preset tenant:\n"
                "[dim]mimic tenant add (prod|preprod|demo)[/dim]\n\n"
                "Or add a custom tenant:\n"
                "[dim]mimic tenant add <name> --url <api-url> --endpoint-id <id>[/dim]",
                title="Tenants",
                border_style="yellow",
            )
        )
        return

    # Create table
    table = Table(title="Configured Tenants", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("API URL", style="white", no_wrap=False)
    table.add_column("Endpoint ID", style="dim", overflow="fold")
    table.add_column("Flag API", style="magenta")
    table.add_column("Properties", style="yellow")
    table.add_column("Current", justify="center")

    for name, tenant_config in tenants.items():
        is_current = "✓" if name == current_tenant else ""

        # Get flag API type
        uses_legacy = config_manager.get_tenant_uses_legacy_flags(name)
        flag_api_display = "org-based" if uses_legacy else "app-based"

        # Get custom properties (not built-in)
        properties = tenant_config.get("properties", {})
        prop_display = f"{len(properties)} set" if properties else "-"

        table.add_row(
            name,
            tenant_config.get("url", ""),
            tenant_config.get("endpoint_id", ""),
            flag_api_display,
            prop_display,
            f"[green]{is_current}[/green]" if is_current else "",
        )

    console.print()
    console.print(table)
    console.print()

    if current_tenant:
        console.print(f"[dim]Current tenant: [bold]{current_tenant}[/bold][/dim]")
    console.print()


@tenant_app.command("select")
def tenant_select(
    name: str | None = typer.Argument(
        None, help="Tenant name to select (interactive selection if omitted)"
    ),
):
    """Select the current tenant.

    Examples:
        mimic tenant select            # Interactive selection
        mimic tenant select prod       # Select prod tenant directly
    """
    tenants = config_manager.list_tenants()

    if not tenants:
        console.print(
            Panel(
                "[yellow]No tenants configured[/yellow]\n\n"
                "Add a tenant first:\n"
                "[dim]mimic tenant add (prod|preprod|demo)[/dim]",
                title="Tenants",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)

    # Interactive tenant selection if not provided
    if not name:
        import questionary

        current_tenant = config_manager.get_current_tenant()

        # Build choices with tenant details
        choices = []
        tenant_map = {}

        for tenant_name, tenant_config in tenants.items():
            tenant_url = tenant_config.get("url", "")
            is_current = tenant_name == current_tenant
            current_indicator = " [CURRENT]" if is_current else ""

            display = f"{tenant_name}{current_indicator} - {tenant_url}"
            choices.append(display)
            tenant_map[display] = tenant_name

        console.print()
        selection = questionary.select(
            "Select a tenant:",
            choices=choices,
            use_shortcuts=True,
            use_arrow_keys=True,
        ).ask()

        if not selection:
            # User cancelled
            raise typer.Exit(0)

        name = tenant_map[selection]
        console.print()

    if name not in tenants:
        console.print(f"[red]Error:[/red] Tenant '{name}' not found")
        console.print("\nAvailable tenants:")
        for tenant_name in tenants.keys():
            console.print(f"  • {tenant_name}")
        raise typer.Exit(1)

    config_manager.set_current_tenant(name)
    tenant_url = config_manager.get_tenant_url(name)

    console.print(
        Panel(
            f"[green]✓[/green] Current tenant set to: [bold]{name}[/bold]\n\n"
            f"[dim]API URL: {tenant_url}[/dim]",
            title="Tenant Selected",
            border_style="green",
        )
    )


@tenant_app.command("set-property")
def tenant_set_property(
    name: str = typer.Argument(..., help="Tenant name"),
    key: str = typer.Argument(..., help="Property key"),
    value: str = typer.Argument(..., help="Property value"),
):
    """Set a custom property for a tenant.

    Example:
      mimic tenant set-property demo USE_VPC true
    """
    tenants = config_manager.list_tenants()

    if name not in tenants:
        console.print(f"[red]Error:[/red] Tenant '{name}' not found")
        console.print("\nAvailable tenants:")
        for tenant_name in tenants.keys():
            console.print(f"  • {tenant_name}")
        raise typer.Exit(1)

    try:
        config_manager.set_tenant_property(name, key, value)
        console.print(
            Panel(
                f"[green]✓[/green] Property set successfully\n\n"
                f"[dim]Tenant: {name}\n"
                f"Property: {key} = {value}[/dim]",
                title="Property Updated",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Error setting property:[/red] {e}")
        raise typer.Exit(1) from e


@tenant_app.command("unset-property")
def tenant_unset_property(
    name: str = typer.Argument(..., help="Tenant name"),
    key: str = typer.Argument(..., help="Property key"),
):
    """Remove a custom property from a tenant.

    Example:
      mimic tenant unset-property demo USE_VPC
    """
    tenants = config_manager.list_tenants()

    if name not in tenants:
        console.print(f"[red]Error:[/red] Tenant '{name}' not found")
        console.print("\nAvailable tenants:")
        for tenant_name in tenants.keys():
            console.print(f"  • {tenant_name}")
        raise typer.Exit(1)

    try:
        config_manager.unset_tenant_property(name, key)
        console.print(
            Panel(
                f"[green]✓[/green] Property removed successfully\n\n"
                f"[dim]Tenant: {name}\n"
                f"Property: {key}[/dim]",
                title="Property Removed",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Error removing property:[/red] {e}")
        raise typer.Exit(1) from e


@tenant_app.command("remove")
def tenant_remove(
    name: str = typer.Argument(..., help="Tenant name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Remove a tenant."""
    tenants = config_manager.list_tenants()

    if name not in tenants:
        console.print(f"[red]Error:[/red] Tenant '{name}' not found")
        raise typer.Exit(1)

    # Confirm deletion unless --force is used
    if not force:
        tenant_url = config_manager.get_tenant_url(name)
        console.print(
            f"\n[yellow]Warning:[/yellow] This will remove tenant '[bold]{name}[/bold]'"
        )
        console.print(f"[dim]API URL: {tenant_url}[/dim]")
        console.print("[dim]The PAT will be deleted from OS keyring[/dim]\n")

        confirm = typer.confirm("Are you sure?", default=False)
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)

    # Remove tenant
    try:
        was_current = config_manager.get_current_tenant() == name
        config_manager.remove_tenant(name)

        message = f"[green]✓[/green] Tenant '[bold]{name}[/bold]' removed"
        if was_current:
            new_current = config_manager.get_current_tenant()
            if new_current:
                message += f"\n\n[dim]Current tenant set to: {new_current}[/dim]"
            else:
                message += "\n\n[yellow]No current tenant set[/yellow]"

        console.print(Panel(message, title="Tenant Removed", border_style="green"))
    except Exception as e:
        console.print(f"[red]Error removing tenant:[/red] {e}")
        raise typer.Exit(1) from e
