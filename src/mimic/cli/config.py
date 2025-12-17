"""Configuration management commands for Mimic CLI."""

import typer
from prompt_toolkit import prompt as pt_prompt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..config_manager import ConfigManager
from ..input_helpers import select_or_new
from ..unify import create_client_from_config

# Shared instances
console = Console()
config_manager = ConfigManager()

# Create the config app
config_app = typer.Typer(
    help="Manage configuration settings",
    no_args_is_help=True,
)


@config_app.command("show")
def config_show():
    """Show current configuration."""
    config = config_manager.load_config()

    console.print()
    console.print("[bold]Current Configuration[/bold]")
    console.print()

    # GitHub settings
    console.print("[cyan]GitHub:[/cyan]")
    github_username = config_manager.get_github_username()
    has_github_token = config_manager.get_github_pat() is not None
    console.print(
        f"  Default username: [yellow]{github_username or 'Not set'}[/yellow]"
    )
    console.print(
        f"  Token configured: [{'green' if has_github_token else 'red'}]{'Yes' if has_github_token else 'No'}[/]"
    )
    console.print()

    # General settings
    console.print("[cyan]Settings:[/cyan]")
    settings = config.get("settings", {})
    console.print(
        f"  Default expiration days: [yellow]{settings.get('default_expiration_days', 7)}[/yellow]"
    )
    console.print(
        f"  Auto cleanup prompt: [yellow]{settings.get('auto_cleanup_prompt', True)}[/yellow]"
    )
    console.print()

    # Tenant summary
    current_env = config.get("current_tenant")
    env_count = len(config.get("tenants", {}))
    console.print("[cyan]Tenants:[/cyan]")
    console.print(f"  Total configured: [yellow]{env_count}[/yellow]")
    console.print(f"  Current: [yellow]{current_env or 'None'}[/yellow]")
    console.print()

    console.print("[dim]Use 'mimic config set <key> <value>' to change settings[/dim]")
    console.print("[dim]Use 'mimic tenant list' to see configured tenants[/dim]")
    console.print()


@config_app.command("set")
def config_set(
    key: str = typer.Argument(
        ...,
        help="Setting key (e.g., 'default_expiration_days', 'auto_cleanup_prompt', 'github_username')",
    ),
    value: str = typer.Argument(..., help="Setting value"),
):
    """Set a configuration value."""
    # Map of valid settings and their types
    valid_settings = {
        "default_expiration_days": int,
        "auto_cleanup_prompt": bool,
        "github_username": str,
    }

    if key not in valid_settings:
        console.print(f"[red]Error:[/red] Unknown setting '{key}'")
        console.print("\n[bold]Valid settings:[/bold]")
        for setting_key in valid_settings:
            console.print(f"  • {setting_key}")
        raise typer.Exit(1)

    # Convert value to appropriate type
    try:
        expected_type = valid_settings[key]
        if expected_type is bool:
            parsed_value = value.lower() in ("true", "yes", "1", "on")
        elif expected_type is int:
            parsed_value = int(value)
        else:
            parsed_value = value
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid value for {key}: {e}")
        raise typer.Exit(1) from e

    # Special handling for github_username
    if key == "github_username":
        # github_username is always a string based on valid_settings
        assert isinstance(parsed_value, str)
        config_manager.set_github_username(parsed_value)
    else:
        # General settings
        config_manager.set_setting(key, parsed_value)

    console.print(
        Panel(
            f"[green]✓[/green] Setting updated\n\n[dim]{key} = {parsed_value}[/dim]",
            title="Configuration",
            border_style="green",
        )
    )


@config_app.command("github-token")
def config_github_token():
    """Set GitHub Personal Access Token (stored securely in OS keyring)."""
    console.print()
    console.print("[bold]GitHub Personal Access Token[/bold]")
    console.print("[dim]This will be stored securely in your OS keyring[/dim]")
    console.print()

    token = typer.prompt("GitHub PAT", hide_input=True, confirmation_prompt=True)

    config_manager.set_github_pat(token)

    console.print()
    console.print(
        Panel(
            "[green]✓[/green] GitHub token stored securely in OS keyring",
            title="Success",
            border_style="green",
        )
    )


@config_app.command("properties")
def config_properties():
    """Browse properties and secrets for an organization."""
    console.print()
    console.print("[bold]Browse CloudBees Properties & Secrets[/bold]")
    console.print()

    # Get current tenant
    current_env = config_manager.get_current_tenant()
    if not current_env:
        console.print(
            "[red]Error:[/red] No tenant configured. Run 'mimic setup' first."
        )
        raise typer.Exit(1)

    console.print(f"[dim]Current tenant: {current_env}[/dim]")
    console.print()

    # Get list of recently used organizations for this tenant
    # cached_orgs maps org_id -> org_name
    cached_orgs = config_manager.get_cached_orgs_for_tenant(current_env)

    # Create reverse mapping: org_name -> org_id for display
    org_names_to_ids = {name: org_id for org_id, name in cached_orgs.items()}

    # Prepare choices (org names for display)
    choices = list(org_names_to_ids.keys()) if org_names_to_ids else []

    # Prompt for organization selection
    org_choice = select_or_new(
        "Select organization",
        choices=choices,
        new_option_label="[Enter new organization ID]",
        allow_skip=False,  # Don't allow skipping - this is required
    )

    # org_choice is guaranteed to be a string since allow_skip=False
    assert org_choice is not None

    # Handle new org input
    if org_choice == "[Enter new organization ID]":
        org_id = typer.prompt("Organization ID")
        # Optionally get org name
        org_name = typer.prompt("Organization name (optional)", default="")
        if org_name:
            config_manager.cache_org_name(org_id, org_name, current_env)
    else:
        # Use selected org from cache (org_choice is the org name, lookup the ID)
        org_id = org_names_to_ids[org_choice]

    console.print()
    console.print(f"[dim]Fetching properties for organization: {org_id}[/dim]")
    console.print()

    # Create Unify client and fetch properties
    try:
        with create_client_from_config(config_manager, current_env) as client:
            response = client.list_properties(org_id)
            properties = response.get("properties", [])

            if not properties:
                console.print(
                    "[yellow]No properties or secrets found for this organization.[/yellow]"
                )
                return

            # Create table for display
            table = Table(
                title=f"Properties & Secrets for {org_choice if org_choice != '[Enter new organization ID]' else org_id}",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Name", style="white", no_wrap=False)
            table.add_column("Type", style="magenta", width=8)
            table.add_column("Value", style="green")
            table.add_column("Source", style="blue", width=10)
            table.add_column("Protected", style="yellow", width=9)

            # Add rows
            for prop_item in properties:
                prop = prop_item.get("property", {})
                source = prop_item.get("source", "UNKNOWN")

                name = prop.get("name", "")
                is_secret = prop.get("isSecret", False)
                is_protected = prop.get("isProtected", False)
                value = prop.get("string", "")

                # Mask secret values (they come pre-masked as ***** from API)
                display_value = value if not is_secret else "[dim]•••••[/dim]"

                # Determine type
                prop_type = "Secret" if is_secret else "Property"

                # Format protected status
                protected_text = "Yes" if is_protected else "No"

                table.add_row(
                    name,
                    prop_type,
                    display_value,
                    source,
                    protected_text,
                )

            console.print(table)
            console.print()
            console.print(f"[dim]Total: {len(properties)} properties/secrets[/dim]")
            console.print()

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error fetching properties:[/red] {e}")
        raise typer.Exit(1) from e


@config_app.command("add-property")
def config_add_property():
    """Add a property or secret to an organization or component."""
    console.print()
    console.print("[bold]Add CloudBees Property or Secret[/bold]")
    console.print()

    # Get current tenant
    current_env = config_manager.get_current_tenant()
    if not current_env:
        console.print(
            "[red]Error:[/red] No tenant configured. Run 'mimic setup' first."
        )
        raise typer.Exit(1)

    console.print(f"[dim]Current tenant: {current_env}[/dim]")
    console.print()

    # Get list of recently used organizations for this tenant
    # cached_orgs maps org_id -> org_name
    cached_orgs = config_manager.get_cached_orgs_for_tenant(current_env)

    # Create reverse mapping: org_name -> org_id for display
    org_names_to_ids = {name: org_id for org_id, name in cached_orgs.items()}

    # Prepare choices (org names for display)
    choices = list(org_names_to_ids.keys()) if org_names_to_ids else []

    # Prompt for organization selection
    org_choice = select_or_new(
        "Select organization or component",
        choices=choices,
        new_option_label="[Enter new resource ID]",
        allow_skip=False,  # Don't allow skipping - this is required
    )

    # org_choice is guaranteed to be a string since allow_skip=False
    assert org_choice is not None

    # Handle new resource input
    if org_choice == "[Enter new resource ID]":
        resource_id = typer.prompt("Resource ID (org/suborg/component UUID)")
        # Optionally get resource name for caching
        resource_name = typer.prompt("Resource name (optional)", default="")
        if resource_name:
            config_manager.cache_org_name(resource_id, resource_name, current_env)
    else:
        # Use selected org from cache (org_choice is the org name, lookup the ID)
        resource_id = org_names_to_ids[org_choice]

    console.print()
    console.print(f"[dim]Resource ID: {resource_id}[/dim]")
    console.print()

    # Prompt for property details
    property_name = typer.prompt("Property name")

    # Ask if it's a secret
    is_secret = typer.confirm("Is this a secret? (will be masked in UI)", default=False)

    # Prompt for value (hide input if secret)
    if is_secret:
        console.print()
        console.print(f"[bold]Enter value for secret '{property_name}'[/bold]")
        console.print("[dim]Asterisks (*) will appear as you type[/dim]")
        property_value = pt_prompt("Value: ", is_password=True)

        # Show preview of characters for confirmation
        # Show ~20% of the value, with a minimum of 4 and maximum of 50 chars
        if len(property_value) > 0:
            preview_length = max(4, min(50, int(len(property_value) * 0.2)))
            console.print(
                f"First {preview_length} chars: [dim]{property_value[:preview_length]}...[/dim]"
            )
            console.print(f"Total length: [dim]{len(property_value)} characters[/dim]")
            if not typer.confirm("Is this correct?", default=True):
                console.print("[yellow]Cancelled.[/yellow]")
                return
    else:
        property_value = typer.prompt("Property value")

    # Optional description
    description = typer.prompt("Description (optional)", default="")

    # Ask if protected
    is_protected = typer.confirm(
        "Is this protected? (prevents modification)", default=False
    )

    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Name: [cyan]{property_name}[/cyan]")
    console.print(f"  Type: [magenta]{'Secret' if is_secret else 'Property'}[/magenta]")
    console.print(f"  Value: [green]{'•••••' if is_secret else property_value}[/green]")
    if description:
        console.print(f"  Description: [dim]{description}[/dim]")
    console.print(f"  Protected: [yellow]{'Yes' if is_protected else 'No'}[/yellow]")
    console.print()

    # Confirm before creating
    confirm = typer.confirm("Create this property?", default=True)
    if not confirm:
        console.print("[yellow]Cancelled.[/yellow]")
        return

    # Create the property
    try:
        with create_client_from_config(config_manager, current_env) as client:
            client.create_property(
                resource_id=resource_id,
                name=property_name,
                value=property_value,
                is_secret=is_secret,
                description=description,
                is_protected=is_protected,
            )

            console.print()
            console.print(
                Panel(
                    f"[green]✓[/green] {'Secret' if is_secret else 'Property'} '{property_name}' created successfully",
                    title="Success",
                    border_style="green",
                )
            )
            console.print()

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error creating property:[/red] {e}")
        raise typer.Exit(1) from e
