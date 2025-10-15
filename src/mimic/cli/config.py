"""Configuration management commands for Mimic CLI."""

import typer
from rich.console import Console
from rich.panel import Panel

from ..config_manager import ConfigManager

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

    # Environment summary
    current_env = config.get("current_environment")
    env_count = len(config.get("environments", {}))
    console.print("[cyan]Environments:[/cyan]")
    console.print(f"  Total configured: [yellow]{env_count}[/yellow]")
    console.print(f"  Current: [yellow]{current_env or 'None'}[/yellow]")
    console.print()

    console.print("[dim]Use 'mimic config set <key> <value>' to change settings[/dim]")
    console.print("[dim]Use 'mimic env list' to see configured environments[/dim]")
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
