"""Main CLI application and core commands for Mimic."""

import typer
from rich.console import Console

from ..config_manager import ConfigManager
from .cleanup import cleanup_app
from .config import config_app
from .env import env_app
from .list_cmd import list_scenarios
from .run_cmd import run as run_scenario
from .scenario_pack import scenario_pack_app
from .setup_cmd import setup
from .ui_cmd import ui_app
from .upgrade_cmd import upgrade

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


@app.command()
def mcp():
    """Start the MCP (Model Context Protocol) stdio server."""
    from ..mcp import run_mcp_server

    run_mcp_server()
