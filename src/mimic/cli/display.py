"""Display helper functions for CLI output."""

from typing import Any

from rich.console import Console
from rich.panel import Panel


def display_success_summary(
    console: Console,
    session_id: str,
    run_name: str,
    environment: str,
    expiration_label: str,
    summary: dict,
    pipeline: Any,
) -> None:
    """Display a detailed success summary with resource links."""

    # Build success message content
    lines = []
    lines.append("[bold green]✓ Scenario completed successfully![/bold green]\n")
    lines.append(f"Run Name: [bold cyan]{run_name}[/bold cyan]")
    lines.append(f"Instance ID: [dim]{session_id}[/dim]")
    lines.append(f"Environment: [cyan]{environment}[/cyan]")
    lines.append(f"Expires: [yellow]{expiration_label}[/yellow]\n")

    # Display repositories
    repositories = summary.get("repositories", [])
    if repositories:
        lines.append(f"[bold]GitHub Repositories ({len(repositories)}):[/bold]")
        for repo in repositories:
            repo_name = repo.get("name", "Unknown")
            repo_url = repo.get("html_url", "")
            if repo_url:
                lines.append(
                    f"  • [link={repo_url}]{repo_name}[/link] [dim]({repo_url})[/dim]"
                )
            else:
                lines.append(f"  • {repo_name}")
        lines.append("")

    # Display components
    if pipeline.created_components:
        lines.append(
            f"[bold]CloudBees Components ({len(pipeline.created_components)}):[/bold]"
        )
        for comp_name in pipeline.created_components.keys():
            lines.append(f"  • {comp_name}")
        lines.append("")

    # Display environments
    if pipeline.created_environments:
        lines.append(
            f"[bold]CloudBees Environments ({len(pipeline.created_environments)}):[/bold]"
        )
        for env_name in pipeline.created_environments.keys():
            lines.append(f"  • {env_name}")
        lines.append("")

    # Display applications
    if pipeline.created_applications:
        lines.append(
            f"[bold]CloudBees Applications ({len(pipeline.created_applications)}):[/bold]"
        )
        for app_name in pipeline.created_applications.keys():
            lines.append(f"  • {app_name}")
        lines.append("")

    # Display feature flags (grouped by application)
    if pipeline.created_flags:
        lines.append(f"[bold]Feature Flags ({len(pipeline.created_flags)}):[/bold]")
        for flag_name in pipeline.created_flags.keys():
            lines.append(f"  • {flag_name}")
        lines.append("")

    # Remove trailing empty line if present
    if lines and lines[-1] == "":
        lines.pop()

    # Display the panel
    console.print(
        Panel(
            "\n".join(lines),
            title="Success",
            border_style="green",
        )
    )


def display_scenario_preview(
    console: Console,
    preview: dict,
    scenario,
    environment: str,
    expiration_label: str = "Not specified",
    is_dry_run: bool = False,
) -> None:
    """Display a formatted preview of resources that will be created."""

    # Display header
    console.print(
        Panel(
            f"[bold]{scenario.name}[/bold]\n\n{scenario.summary}",
            title=f"Scenario: {scenario.id}",
            border_style="cyan",
        )
    )
    console.print()

    console.print(f"[dim]Environment:[/dim] [cyan]{environment}[/cyan]")
    console.print(f"[dim]Expiration:[/dim] [yellow]{expiration_label}[/yellow]\n")

    # Display repositories
    if preview["repositories"]:
        console.print(
            f"[bold green]✓[/bold green] GitHub repositories ([cyan]{len(preview['repositories'])}[/cyan]):"
        )
        for repo in preview["repositories"][:5]:  # Show first 5
            console.print(
                f"  • [white]{repo['name']}[/white] [dim](from {repo['source']})[/dim]"
            )
        if len(preview["repositories"]) > 5:
            console.print(
                f"  [dim]... and {len(preview['repositories']) - 5} more[/dim]"
            )
        console.print()

    # Display components
    if preview["components"]:
        console.print(
            f"[bold green]✓[/bold green] CloudBees components ([cyan]{len(preview['components'])}[/cyan]):"
        )
        for component in preview["components"][:5]:
            console.print(f"  • [white]{component}[/white]")
        if len(preview["components"]) > 5:
            console.print(f"  [dim]... and {len(preview['components']) - 5} more[/dim]")
        console.print()

    # Display environments
    if preview["environments"]:
        console.print(
            f"[bold green]✓[/bold green] CloudBees environments ([cyan]{len(preview['environments'])}[/cyan]):"
        )
        for env in preview["environments"]:
            console.print(f"  • [white]{env['name']}[/white]")
        console.print()

    # Display applications
    if preview["applications"]:
        console.print(
            f"[bold green]✓[/bold green] CloudBees applications ([cyan]{len(preview['applications'])}[/cyan]):"
        )
        for app in preview["applications"]:
            comp_count = len(app["components"])
            env_count = len(app["environments"])
            console.print(
                f"  • [white]{app['name']}[/white] [dim]({comp_count} components, {env_count} environments)[/dim]"
            )
        console.print()

    # Display flags
    if preview["flags"]:
        total_flag_count = len(preview["flags"])
        total_env_count = sum(len(flag["environments"]) for flag in preview["flags"])
        console.print(
            f"[bold green]✓[/bold green] Feature flags ([cyan]{total_flag_count} flag{'s' if total_flag_count != 1 else ''}, {total_env_count} environment{'s' if total_env_count != 1 else ''}[/cyan]):"
        )
        for flag in preview["flags"]:
            env_list = ", ".join(flag["environments"])
            console.print(
                f"  • [white]{flag['name']}[/white] [dim]({flag['type']}, in: {env_list})[/dim]"
            )
        console.print()

    # Only show dry-run instruction when actually in dry-run mode
    if is_dry_run:
        console.print(
            "[dim]To execute this scenario, run the command again without --dry-run[/dim]"
        )
        console.print()
