"""Pre-flight check for GitHub App integration setup."""

import typer
from rich.console import Console

from ...scenarios import Scenario
from ...unify import UnifyAPIClient

console = Console()


def check_github_integration(
    scenario: Scenario,
    parameters: dict,
    env_url: str,
    cloudbees_pat: str,
    organization_id: str,
) -> None:
    """Check if GitHub organization has GitHub App integration in CloudBees.

    Only checks if scenario has repositories with target_org parameter.
    Validates the GitHub org is set up as a GitHub App integration.

    Args:
        scenario: The scenario being run
        parameters: Resolved parameters including target_org
        env_url: CloudBees Unify API URL
        cloudbees_pat: CloudBees Personal Access Token
        organization_id: CloudBees Organization ID

    Raises:
        typer.Exit: If GitHub org is not set up as an integration
    """
    # Skip if scenario has no repositories
    if not scenario.repositories:
        return

    # Skip if no target_org parameter (shouldn't happen for scenarios with repos, but be safe)
    target_org = parameters.get("target_org")
    if not target_org:
        return

    console.print("[bold]Checking GitHub App integration...[/bold]")

    # Fetch configured GitHub App integrations
    with UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat) as client:
        try:
            github_orgs = client.list_github_apps(organization_id)
        except Exception as e:
            console.print(f"[red]Error fetching GitHub App integrations:[/red] {e}")
            raise typer.Exit(1) from e

    # Check if target org is in the list
    if target_org in github_orgs:
        console.print(
            f"  [green]✓[/green] GitHub organization '{target_org}' is configured as a GitHub App integration"
        )
        console.print()
        return

    # Target org is NOT configured - display error and exit
    console.print()
    console.print(
        f"[red]✗ GitHub organization '{target_org}' is not set up as a GitHub App integration[/red]"
    )
    console.print()
    console.print("[yellow]To fix this:[/yellow]")
    console.print("  1. Go to your CloudBees organization integrations page")
    console.print(
        f"  2. Add a GitHub App integration for the '{target_org}' organization"
    )
    console.print("  3. Wait for the repository sync to complete")
    console.print("  4. Re-run this scenario")
    console.print()

    if github_orgs:
        console.print(
            f"[dim]Currently configured GitHub organizations: {', '.join(github_orgs)}[/dim]"
        )
        console.print()

    raise typer.Exit(1)
