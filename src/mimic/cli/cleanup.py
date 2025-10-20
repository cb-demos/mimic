"""Cleanup management commands for Mimic CLI."""

import asyncio
from datetime import datetime

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..cleanup_manager import CleanupManager
from ..config_manager import ConfigManager
from ..instance_repository import InstanceRepository

# Shared instances
console = Console()
config_manager = ConfigManager()

# Create the cleanup app with special configuration
cleanup_app = typer.Typer(
    help="Manage and cleanup scenario resources",
    invoke_without_command=True,
    no_args_is_help=False,
)


@cleanup_app.callback()
def cleanup_callback(ctx: typer.Context):
    """Default to interactive cleanup when no subcommand is provided."""
    # If a subcommand was invoked, don't run the default behavior
    if ctx.invoked_subcommand is not None:
        return

    # Otherwise, run the interactive cleanup
    cleanup_run(session_id=None, dry_run=False, force=False)


@cleanup_app.command("list")
def cleanup_list(
    show_expired_only: bool = typer.Option(
        False, "--expired-only", help="Show only expired sessions"
    ),
):
    """List all tracked sessions."""
    try:
        instance_repo = InstanceRepository()
        sessions = instance_repo.find_all(include_expired=True)

        if show_expired_only:
            now = datetime.now()
            sessions = [
                s for s in sessions if s.expires_at is not None and s.expires_at <= now
            ]

        if not sessions:
            message = (
                "No expired instances found"
                if show_expired_only
                else "No instances found"
            )
            console.print(
                Panel(
                    f"[yellow]{message}[/yellow]\n\n"
                    "Instances are created when you run scenarios with: [dim]mimic run <scenario-id>[/dim]",
                    title="Instances",
                    border_style="yellow",
                )
            )
            return

        # Create table
        table = Table(
            title=f"{'Expired ' if show_expired_only else ''}Tracked Instances",
            show_header=True,
            expand=True,
        )
        table.add_column("Run Name", style="bold cyan", no_wrap=True)
        table.add_column("Instance ID", style="dim", no_wrap=True)
        table.add_column("Scenario", style="white")
        table.add_column("Environment", style="dim")
        table.add_column("Created", style="dim")
        table.add_column("Expires", style="yellow")
        table.add_column("Resources", style="green", justify="right")
        table.add_column("Status", justify="center")

        now = datetime.now()
        for session in sessions:
            is_expired = session.expires_at is not None and session.expires_at <= now
            never_expires = session.expires_at is None

            if never_expires:
                status = "[blue]NEVER EXPIRES[/blue]"
            elif is_expired:
                status = "[red]EXPIRED[/red]"
            else:
                status = "[green]ACTIVE[/green]"

            # Count resources
            resource_count = (
                len(session.repositories)
                + len(session.components)
                + len(session.environments)
                + len(session.applications)
                + len(session.flags)
            )

            # Format dates
            created_str = session.created_at.strftime("%Y-%m-%d %H:%M")
            expires_str = (
                "Never"
                if session.expires_at is None
                else session.expires_at.strftime("%Y-%m-%d %H:%M")
            )

            # Get run name
            run_name = session.name

            table.add_row(
                run_name,
                session.id,
                session.scenario_id,
                session.environment,
                created_str,
                expires_str,
                str(resource_count),
                status,
            )

        console.print()
        console.print(table)
        console.print()

        # Show summary
        expired_count = sum(
            1 for s in sessions if s.expires_at is not None and s.expires_at <= now
        )
        never_expires_count = sum(1 for s in sessions if s.expires_at is None)
        active_count = len(sessions) - expired_count - never_expires_count

        console.print(
            f"[dim]Total: {len(sessions)} | Active: [green]{active_count}[/green] | Never Expires: [blue]{never_expires_count}[/blue] | Expired: [red]{expired_count}[/red][/dim]"
        )
        console.print()

        if expired_count > 0:
            console.print(
                "[dim]Clean up expired instances with:[/dim] mimic cleanup expired"
            )
            console.print()

    except Exception as e:
        console.print(f"[red]Error listing instances:[/red] {e}")
        raise typer.Exit(1) from e


# Alias for cleanup list command
cleanup_app.command("ls")(cleanup_list)


@cleanup_app.command("run")
def cleanup_run(
    session_id: str | None = typer.Argument(
        None,
        help="Instance ID or run name to clean up (interactive selection if omitted)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be cleaned without doing it"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Clean up resources for a specific instance.

    You can specify an instance by its ID or run name. If omitted, an interactive
    selector will allow you to choose from available instances.

    Examples:
        mimic cleanup run                       # Interactive instance selection
        mimic cleanup run my-app-abc123         # Clean up by run name
        mimic cleanup run a1b2c3d4               # Clean up by instance ID
        mimic cleanup run --dry-run             # Preview cleanup interactively
        mimic cleanup run my-app --dry-run      # Preview specific instance cleanup
    """
    try:
        instance_repo = InstanceRepository()

        # Interactive instance selection if not provided
        if not session_id:
            import questionary

            sessions = instance_repo.find_all(include_expired=True)
            if not sessions:
                console.print(
                    Panel(
                        "[yellow]No instances found[/yellow]\n\n"
                        "Instances are created when you run scenarios.\n"
                        "Create an instance with: [dim]mimic run <scenario-id>[/dim]",
                        title="Instances",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(0)

            # Build choices with session details
            choices = []
            session_map = {}
            now = datetime.now()

            for s in sessions:
                run_name = s.name
                is_expired = s.expires_at is not None and s.expires_at <= now
                status = (
                    "EXPIRED"
                    if is_expired
                    else ("ACTIVE" if s.expires_at else "NEVER EXPIRES")
                )
                resource_count = (
                    len(s.repositories)
                    + len(s.components)
                    + len(s.environments)
                    + len(s.applications)
                    + len(s.flags)
                )

                display = f"{run_name} ({s.id[:8]}) - {s.scenario_id} | {resource_count} resources | {status}"
                choices.append(display)
                session_map[display] = s.id

            console.print()
            selection = questionary.select(
                "Select an instance to clean up:",
                choices=choices,
                use_shortcuts=True,
                use_arrow_keys=True,
            ).ask()

            if not selection:
                # User cancelled
                raise typer.Exit(0)

            session_id = session_map[selection]
            console.print()

        # Type guard: session_id is guaranteed to be a string here
        # (either provided as argument or selected interactively)
        assert session_id is not None

        # Get session by ID or run name
        session = instance_repo.get_by_id(session_id) or instance_repo.get_by_name(
            session_id
        )

        if not session:
            console.print(f"[red]Error:[/red] Instance '{session_id}' not found")
            console.print("\n[dim]List instances with:[/dim] mimic cleanup list")
            raise typer.Exit(1)

        # Show instance details
        total_resources = (
            len(session.repositories)
            + len(session.components)
            + len(session.environments)
            + len(session.applications)
            + len(session.flags)
        )

        console.print()
        console.print(
            Panel(
                f"[bold]Instance:[/bold] {session.id}\n"
                f"[bold]Scenario:[/bold] {session.scenario_id}\n"
                f"[bold]Environment:[/bold] {session.environment}\n"
                f"[bold]Created:[/bold] {session.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"[bold]Expires:[/bold] {'Never' if session.expires_at is None else session.expires_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"[bold]Resources:[/bold] {total_resources}",
                title="Instance Details",
                border_style="cyan",
            )
        )
        console.print()

        # Show resources
        if total_resources > 0:
            console.print("[bold]Resources to clean up:[/bold]")
            for repo in session.repositories:
                console.print(f"  • github_repo: {repo.name}")
            for comp in session.components:
                console.print(f"  • cloudbees_component: {comp.name}")
            for env in session.environments:
                console.print(f"  • cloudbees_environment: {env.name}")
            for app in session.applications:
                console.print(f"  • cloudbees_application: {app.name}")
            for flag in session.flags:
                console.print(f"  • cloudbees_flag: {flag.name}")
            console.print()

        # Confirm unless --force or --dry-run
        if not force and not dry_run:
            confirm = typer.confirm(
                "Are you sure you want to delete these resources?", default=False
            )
            if not confirm:
                console.print("[dim]Cancelled[/dim]")
                raise typer.Exit(0)

        # Run cleanup
        cleanup_manager = CleanupManager(console=console)
        results = asyncio.run(
            cleanup_manager.cleanup_session(session_id, dry_run=dry_run)
        )

        # Show summary
        console.print()
        if dry_run:
            console.print(
                Panel(
                    f"[yellow]Dry run completed[/yellow]\n\n"
                    f"Would clean: {len(results['cleaned'])} resources\n"
                    f"Would skip: {len(results['skipped'])} resources\n"
                    f"Errors: {len(results['errors'])} resources",
                    title="Cleanup Summary (Dry Run)",
                    border_style="yellow",
                )
            )
        else:
            success = len(results["errors"]) == 0
            console.print(
                Panel(
                    f"[{'green' if success else 'yellow'}]Cleanup {'completed successfully' if success else 'completed with errors'}[/]\n\n"
                    f"Cleaned: {len(results['cleaned'])} resources\n"
                    f"Skipped: {len(results['skipped'])} resources\n"
                    f"Errors: {len(results['errors'])} resources",
                    title="Cleanup Summary",
                    border_style="green" if success else "yellow",
                )
            )

            if results["errors"]:
                console.print("\n[red]Errors:[/red]")
                for error in results["errors"]:
                    console.print(
                        f"  • {error['type']} ({error['id']}): {error['error']}"
                    )

    except Exception as e:
        console.print(f"\n[red]Error during cleanup:[/red] {e}")
        raise typer.Exit(1) from e


# Alias for cleanup run command
cleanup_app.command("rm")(cleanup_run)


@cleanup_app.command("expired")
def cleanup_expired(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be cleaned without doing it"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Clean up all expired instances."""
    try:
        cleanup_manager = CleanupManager(console=console)

        # Check for expired sessions
        expired_sessions = cleanup_manager.check_expired_sessions()

        if not expired_sessions:
            console.print(
                Panel(
                    "[green]No expired instances found[/green]\n\n"
                    "All tracked instances are still active.",
                    title="Cleanup",
                    border_style="green",
                )
            )
            return

        # Show expired sessions
        console.print()
        console.print(
            f"[yellow]Found {len(expired_sessions)} expired instance(s):[/yellow]\n"
        )

        for session in expired_sessions:
            total_resources = (
                len(session.repositories)
                + len(session.components)
                + len(session.environments)
                + len(session.applications)
                + len(session.flags)
            )
            console.print(
                f"  • {session.id} - {session.scenario_id} ({total_resources} resources)"
            )

        console.print()

        # Confirm unless --force or --dry-run
        if not force and not dry_run:
            confirm = typer.confirm(
                f"Clean up {len(expired_sessions)} expired instance(s)?", default=True
            )
            if not confirm:
                console.print("[dim]Cancelled[/dim]")
                raise typer.Exit(0)

        # Run cleanup
        console.print()
        results = asyncio.run(
            cleanup_manager.cleanup_expired_sessions(dry_run=dry_run, auto_confirm=True)
        )

        # Show summary
        console.print()
        if dry_run:
            console.print(
                Panel(
                    f"[yellow]Dry run completed[/yellow]\n\n"
                    f"Instances found: {results['total_sessions']}\n"
                    f"Would clean: {results['cleaned_sessions']} instances\n"
                    f"Errors: {results['failed_sessions']} instances",
                    title="Cleanup Summary (Dry Run)",
                    border_style="yellow",
                )
            )
        else:
            success = results["failed_sessions"] == 0
            console.print(
                Panel(
                    f"[{'green' if success else 'yellow'}]Cleanup {'completed successfully' if success else 'completed with errors'}[/]\n\n"
                    f"Instances cleaned: {results['cleaned_sessions']}/{results['total_sessions']}\n"
                    f"Failed: {results['failed_sessions']}",
                    title="Cleanup Summary",
                    border_style="green" if success else "yellow",
                )
            )

    except Exception as e:
        console.print(f"[red]Error during cleanup:[/red] {e}")
        raise typer.Exit(1) from e


# Alias for cleanup expired command
cleanup_app.command("exp")(cleanup_expired)
