"""Main CLI application and core commands for Mimic."""

import os
import shutil
import sys

import typer
from rich.console import Console

from ..config_manager import ConfigManager
from ..platform import (
    check_gnome_keyring_installed,
    get_gnome_keyring_install_command,
    is_in_dbus_session,
    is_wsl,
)
from .cleanup import cleanup_app
from .config import config_app
from .env import env_app
from .list_cmd import list_scenarios
from .run_cmd import run as run_scenario
from .scenario_pack import scenario_pack_app
from .setup_cmd import setup
from .ui_cmd import ui_app
from .upgrade_cmd import upgrade


def ensure_wsl_environment() -> None:
    """
    Ensure WSL has proper D-Bus session for keyring access.

    This function should be called BEFORE any imports that access the keyring.
    If running in WSL without a D-Bus session, it will re-execute the entire
    command inside dbus-run-session and never return.
    """
    # Only relevant for WSL
    if not is_wsl():
        return

    # Already in D-Bus session - nothing to do
    if is_in_dbus_session():
        return

    console = Console()

    # Check if gnome-keyring is installed
    if not check_gnome_keyring_installed():
        console.print(
            "\n[yellow]⚠  WSL detected: gnome-keyring is required for secure credential storage[/yellow]\n"
        )
        console.print(
            f"Please install it first:\n  {get_gnome_keyring_install_command()}\n"
        )
        sys.exit(1)

    # Check if dbus-run-session is available
    if not shutil.which("dbus-run-session"):
        console.print("\n[yellow]⚠  dbus-run-session not found[/yellow]\n")
        console.print("Please install dbus-x11:\n  sudo apt-get install -y dbus-x11\n")
        sys.exit(1)

    # Re-exec the current command inside dbus-run-session
    # This replaces the current process with a new one running in D-Bus context
    console.print("[dim]Starting in D-Bus session for WSL keyring support...[/dim]")
    args = ["dbus-run-session", "--", sys.executable, "-m", "mimic"] + sys.argv[1:]

    try:
        os.execvp("dbus-run-session", args)
    except OSError as e:
        console.print(f"\n[red]Failed to start D-Bus session: {e}[/red]\n")
        sys.exit(1)


# Create main Typer app
app = typer.Typer(
    name="mimic",
    help="CloudBees Unify scenario instantiation CLI tool",
    no_args_is_help=True,
)

# Shared instances
console = Console()
config_manager = ConfigManager()

# Register sub-applications
app.add_typer(env_app, name="env")
app.add_typer(config_app, name="config")
app.add_typer(cleanup_app, name="cleanup")
app.add_typer(cleanup_app, name="clean")  # Alias for cleanup
app.add_typer(scenario_pack_app, name="scenario-pack")
app.add_typer(scenario_pack_app, name="pack")  # Alias for scenario-pack
app.add_typer(ui_app, name="ui")

# Register list command and its alias
app.command("list")(list_scenarios)
app.command("ls")(list_scenarios)  # Alias for list

# Register run command
app.command("run")(run_scenario)

# Register upgrade command
app.command("upgrade")(upgrade)

# Register setup command
app.command("setup")(setup)
