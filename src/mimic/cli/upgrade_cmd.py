"""Upgrade command for Mimic CLI."""

import subprocess

from rich.console import Console
from rich.panel import Panel

from ..config_manager import ConfigManager

# Shared instances
console = Console()


def upgrade():
    """Upgrade Mimic and all scenario packs to the latest versions.

    This command:
    1. Upgrades the Mimic tool itself using 'uv tool upgrade mimic'
    2. Updates all configured scenario packs by pulling latest changes

    Example:
        mimic upgrade
    """
    from ..scenario_pack_manager import ScenarioPackManager

    config_manager = ConfigManager()

    console.print()
    console.print(
        Panel(
            "[bold cyan]Upgrading Mimic[/bold cyan]\n\n"
            "This will:\n"
            "  1. Upgrade the Mimic tool itself\n"
            "  2. Update all scenario packs",
            title="Upgrade",
            border_style="cyan",
        )
    )
    console.print()

    # Step 1: Upgrade Mimic tool
    console.print("[bold]Step 1/2: Upgrading Mimic tool...[/bold]")

    try:
        result = subprocess.run(
            ["uv", "tool", "upgrade", "mimic"],
            capture_output=True,
            text=True,
            check=True,
        )
        console.print("[green]✓[/green] Mimic tool upgraded successfully")
        if result.stdout.strip():
            console.print(f"[dim]{result.stdout.strip()}[/dim]")
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]⚠[/yellow] Failed to upgrade Mimic tool: {e.stderr}")
        console.print("[dim]Continuing with scenario pack updates...[/dim]")
    except FileNotFoundError:
        console.print(
            "[yellow]⚠[/yellow] 'uv' command not found. Please install uv first."
        )
        console.print("[dim]Continuing with scenario pack updates...[/dim]")

    console.print()

    # Step 2: Update scenario packs
    console.print("[bold]Step 2/2: Updating scenario packs...[/bold]")

    try:
        pack_manager = ScenarioPackManager(config_manager.packs_dir)
        packs = config_manager.list_scenario_packs()

        if not packs:
            console.print("[yellow]No scenario packs configured[/yellow]")
            console.print(
                "[dim]Add packs with: mimic scenario-pack add <name> <url>[/dim]"
            )
        else:
            console.print(f"[dim]Found {len(packs)} pack(s) to update[/dim]")
            console.print()

            success_count = 0
            for pack_name, pack_config in packs.items():
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
                        console.print(
                            f"[green]✓[/green] {pack_name}: Cloned successfully"
                        )
                    else:
                        pack_manager.update_pack(pack_name)
                        console.print(
                            f"[green]✓[/green] {pack_name}: Updated successfully"
                        )

                    success_count += 1

                except Exception as e:
                    console.print(f"[red]✗[/red] {pack_name}: {e}")

            console.print()
            console.print(
                f"[dim]Updated {success_count}/{len(packs)} pack(s) successfully[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error updating scenario packs:[/red] {e}")

    # Final summary
    console.print()
    console.print(
        Panel(
            "[green]✓[/green] Upgrade complete!\n\n"
            "[dim]Mimic and scenario packs are up to date[/dim]",
            title="Success",
            border_style="green",
        )
    )
    console.print()
