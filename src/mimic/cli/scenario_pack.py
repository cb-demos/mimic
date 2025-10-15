"""Scenario pack management commands for Mimic CLI."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..config_manager import ConfigManager
from ..scenario_pack_manager import ScenarioPackManager

# Shared instances
console = Console()
config_manager = ConfigManager()

# Create the scenario pack app
scenario_pack_app = typer.Typer(help="Manage scenario packs from git repositories")


@scenario_pack_app.command("add")
def pack_add(
    name: str = typer.Argument(..., help="Pack name (used as directory name)"),
    url: str = typer.Argument(..., help="Git URL (supports HTTPS and SSH)"),
    branch: str = typer.Option("main", "--branch", "-b", help="Git branch to use"),
):
    """Add a scenario pack from a git repository."""
    try:
        # Check if pack already exists in config
        existing_pack = config_manager.get_scenario_pack(name)
        if existing_pack:
            console.print(
                f"[red]Error:[/red] Pack '{name}' already exists in configuration"
            )
            console.print(
                f"Use 'mimic scenario-pack remove {name}' first to replace it"
            )
            raise typer.Exit(1)

        # Add pack to config
        config_manager.add_scenario_pack(name, url, branch, enabled=True)

        # Clone the pack
        console.print(f"\n[bold]Adding scenario pack:[/bold] {name}")
        console.print(f"[dim]Git URL:[/dim] {url}")
        console.print(f"[dim]Branch:[/dim] {branch}")
        console.print()

        pack_manager = ScenarioPackManager(config_manager.packs_dir)
        pack_path = pack_manager.clone_pack(name, url, branch)

        console.print()
        console.print(
            Panel(
                f"[green]✓[/green] Scenario pack '{name}' added successfully\n\n"
                f"[dim]• Cloned to: {pack_path}\n"
                f"• Enabled: Yes[/dim]",
                title="Success",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"\n[red]Error adding scenario pack:[/red] {e}")
        raise typer.Exit(1) from e


@scenario_pack_app.command("list")
def pack_list():
    """List all configured scenario packs."""
    packs = config_manager.list_scenario_packs()
    pack_manager = ScenarioPackManager(config_manager.packs_dir)

    if not packs:
        console.print(
            Panel(
                "[yellow]No scenario packs configured[/yellow]\n\n"
                "Add the official pack:\n"
                "[dim]mimic scenario-pack add official https://github.com/cb-demos/mimic-scenarios[/dim]\n\n"
                "Or add a custom pack:\n"
                "[dim]mimic scenario-pack add <name> <git-url>[/dim]",
                title="Scenario Packs",
                border_style="yellow",
            )
        )
        return

    # Create table
    table = Table(title="Configured Scenario Packs", show_header=True, expand=True)
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="white", overflow="fold")
    table.add_column("Branch", style="dim")
    table.add_column("Installed", justify="center")
    table.add_column("Enabled", justify="center")

    for name, pack_config in packs.items():
        is_installed = pack_manager.get_pack_path(name) is not None
        is_enabled = pack_config.get("enabled", True)

        table.add_row(
            name,
            pack_config.get("url", ""),
            pack_config.get("branch", "main"),
            "[green]✓[/green]" if is_installed else "[red]✗[/red]",
            "[green]✓[/green]" if is_enabled else "[dim]✗[/dim]",
        )

    console.print()
    console.print(table)
    console.print()

    console.print(
        "[dim]Update packs with:[/dim] mimic scenario-pack update [pack-name]"
    )
    console.print()


# Alias for pack list
scenario_pack_app.command("ls")(pack_list)


@scenario_pack_app.command("update")
def pack_update(
    name: str = typer.Argument(
        None, help="Pack name to update (updates all if not specified)"
    ),
):
    """Update scenario pack(s) by pulling latest changes."""
    try:
        pack_manager = ScenarioPackManager(config_manager.packs_dir)
        packs = config_manager.list_scenario_packs()

        if not packs:
            console.print("[yellow]No scenario packs configured[/yellow]")
            return

        # Determine which packs to update
        if name:
            if name not in packs:
                console.print(
                    f"[red]Error:[/red] Pack '{name}' not found in configuration"
                )
                raise typer.Exit(1)
            packs_to_update = {name: packs[name]}
        else:
            packs_to_update = packs

        console.print()
        console.print(
            f"[bold]Updating {len(packs_to_update)} scenario pack(s)...[/bold]"
        )
        console.print()

        success_count = 0
        for pack_name, pack_config in packs_to_update.items():
            try:
                # Check if pack is installed
                if not pack_manager.get_pack_path(pack_name):
                    console.print(
                        f"[yellow]⚠[/yellow] {pack_name}: Not installed, cloning..."
                    )
                    url = pack_config.get("url")
                    if not url:
                        console.print(
                            f"[red]✗[/red] {pack_name}: Missing URL in configuration"
                        )
                        continue
                    branch = pack_config.get("branch", "main")
                    pack_manager.clone_pack(pack_name, url, branch)
                    console.print(f"[green]✓[/green] {pack_name}: Cloned successfully")
                else:
                    pack_manager.update_pack(pack_name)
                    console.print(f"[green]✓[/green] {pack_name}: Updated successfully")

                success_count += 1

            except Exception as e:
                console.print(f"[red]✗[/red] {pack_name}: {e}")

        console.print()
        console.print(
            Panel(
                f"Updated {success_count}/{len(packs_to_update)} pack(s) successfully",
                title="Update Complete",
                border_style="green"
                if success_count == len(packs_to_update)
                else "yellow",
            )
        )

    except Exception as e:
        console.print(f"\n[red]Error updating scenario pack(s):[/red] {e}")
        raise typer.Exit(1) from e


@scenario_pack_app.command("remove")
def pack_remove(
    name: str = typer.Argument(..., help="Pack name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    keep_files: bool = typer.Option(
        False, "--keep-files", help="Remove from config but keep cloned files"
    ),
):
    """Remove a scenario pack."""
    try:
        # Check if pack exists
        pack_config = config_manager.get_scenario_pack(name)
        if not pack_config:
            console.print(f"[red]Error:[/red] Pack '{name}' not found in configuration")
            raise typer.Exit(1)

        # Confirm deletion unless --force is used
        if not force:
            console.print(
                f"\n[yellow]Warning:[/yellow] This will remove scenario pack '[bold]{name}[/bold]'"
            )
            console.print(f"[dim]URL: {pack_config.get('url')}[/dim]")
            if not keep_files:
                console.print("[dim]Cloned files will be deleted[/dim]")
            console.print()

            confirm = typer.confirm("Are you sure?", default=False)
            if not confirm:
                console.print("[dim]Cancelled[/dim]")
                raise typer.Exit(0)

        # Remove from config
        config_manager.remove_scenario_pack(name)

        # Remove cloned files unless --keep-files
        if not keep_files:
            pack_manager = ScenarioPackManager(config_manager.packs_dir)
            if pack_manager.get_pack_path(name):
                pack_manager.remove_pack(name)

        console.print(
            Panel(
                f"[green]✓[/green] Scenario pack '[bold]{name}[/bold]' removed",
                title="Pack Removed",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"\n[red]Error removing scenario pack:[/red] {e}")
        raise typer.Exit(1) from e


# Alias for pack remove
scenario_pack_app.command("rm")(pack_remove)


@scenario_pack_app.command("enable")
def pack_enable(name: str = typer.Argument(..., help="Pack name to enable")):
    """Enable a scenario pack."""
    try:
        config_manager.set_scenario_pack_enabled(name, True)
        console.print(
            Panel(
                f"[green]✓[/green] Scenario pack '[bold]{name}[/bold]' enabled",
                title="Pack Enabled",
                border_style="green",
            )
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@scenario_pack_app.command("disable")
def pack_disable(name: str = typer.Argument(..., help="Pack name to disable")):
    """Disable a scenario pack."""
    try:
        config_manager.set_scenario_pack_enabled(name, False)
        console.print(
            Panel(
                f"[yellow]Scenario pack '[bold]{name}[/bold]' disabled[/yellow]\n\n"
                "[dim]Scenarios from this pack will not be loaded[/dim]",
                title="Pack Disabled",
                border_style="yellow",
            )
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
