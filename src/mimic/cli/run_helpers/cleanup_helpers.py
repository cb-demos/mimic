"""Cleanup helper functions for the run command."""

import asyncio

import typer
from rich.console import Console

console = Console()


def handle_opportunistic_cleanup(config_manager, skip_prompt: bool):
    """Check for expired instances and optionally clean them up.

    Args:
        config_manager: ConfigManager instance.
        skip_prompt: Whether to skip the cleanup prompt (e.g., when --yes flag is used).
    """
    auto_cleanup_prompt = config_manager.get_setting("auto_cleanup_prompt", True)
    if auto_cleanup_prompt and not skip_prompt:
        from ...cleanup_manager import CleanupManager

        cleanup_manager = CleanupManager(console=console)
        expired_sessions = cleanup_manager.check_expired_sessions()

        if expired_sessions:
            console.print()
            console.print(
                f"[yellow]Found {len(expired_sessions)} expired instance(s)[/yellow]"
            )

            # Show brief list
            for session in expired_sessions[:3]:  # Show max 3
                run_name = getattr(session, "name", session.id)
                console.print(f"  • {run_name} - {session.scenario_id}")

            if len(expired_sessions) > 3:
                console.print(f"  • ... and {len(expired_sessions) - 3} more")

            console.print()

            # Prompt to clean up
            cleanup_now = typer.confirm(
                "Clean up expired instances before proceeding?", default=True
            )

            if cleanup_now:
                console.print()
                results = asyncio.run(
                    cleanup_manager.cleanup_expired_sessions(
                        dry_run=False, auto_confirm=True
                    )
                )
                console.print(
                    f"[green]✓[/green] Cleaned up {results['cleaned_sessions']} instance(s)\n"
                )
            else:
                console.print(
                    "[dim]Skipping cleanup. You can clean up later with: mimic cleanup expired[/dim]\n"
                )
