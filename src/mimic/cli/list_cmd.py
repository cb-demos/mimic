"""List command for Mimic CLI."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..config_manager import ConfigManager

# Shared instances
console = Console()


def list_scenarios():
    """List available scenarios."""
    from ..scenarios import initialize_scenarios_from_config

    config_manager = ConfigManager()

    # Check for first run
    if config_manager.is_first_run():
        console.print()
        console.print(
            Panel(
                "[yellow]Welcome to Mimic![/yellow]\n\n"
                "It looks like this is your first time running Mimic.\n\n"
                "Run the setup wizard to get started:\n"
                "[dim]mimic setup[/dim]",
                title="First Run",
                border_style="yellow",
            )
        )
        console.print()
        raise typer.Exit(0)

    try:
        # Initialize scenario manager from config
        scenario_manager = initialize_scenarios_from_config()

        # Get all scenarios
        scenarios = scenario_manager.list_scenarios()

        if not scenarios:
            console.print(
                Panel(
                    "[yellow]No scenarios found[/yellow]\n\n"
                    "Check that the scenarios/ directory exists and contains YAML files.",
                    title="Scenarios",
                    border_style="yellow",
                )
            )
            return

        # Create table
        table = Table(title="Available Scenarios", show_header=True, expand=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="bold white")
        table.add_column("Summary", style="dim", overflow="fold")
        table.add_column("Source", style="magenta", no_wrap=True)
        table.add_column("Parameters", style="yellow", no_wrap=True)

        for scenario in scenarios:
            param_count = (
                len(scenario.get("parameters", {})) if scenario.get("parameters") else 0
            )
            param_text = f"{param_count} params" if param_count > 0 else "none"
            pack_source = scenario.get("pack_source", "unknown")

            table.add_row(
                scenario["id"],
                scenario["name"],
                scenario["summary"],
                pack_source,
                param_text,
            )

        console.print()
        console.print(table)
        console.print()

        # Show example usage
        console.print("[dim]Run a scenario with:[/dim] mimic run <scenario-id>")
        console.print()

    except Exception as e:
        console.print(f"[red]Error loading scenarios:[/red] {e}")
        raise typer.Exit(1) from e
