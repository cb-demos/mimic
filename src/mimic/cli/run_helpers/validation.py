"""Credential validation for the run command."""

import asyncio

from rich.console import Console

console = Console()


def validate_credentials(
    env_url: str, cloudbees_pat: str, organization_id: str, github_pat: str
) -> tuple[bool, bool]:
    """Validate CloudBees and GitHub credentials.

    Args:
        env_url: CloudBees Unify API URL.
        cloudbees_pat: CloudBees Personal Access Token.
        organization_id: CloudBees Organization ID.
        github_pat: GitHub Personal Access Token.

    Returns:
        Tuple of (cloudbees_valid, github_valid) booleans.
    """
    from ...gh import GitHubClient
    from ...unify import UnifyAPIClient

    console.print("[bold]Checking credentials...[/bold]")

    cloudbees_valid = False
    github_valid = False

    try:
        with UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat) as client:
            success, error = client.validate_credentials(organization_id)
            if success:
                console.print("  [green]✓[/green] CloudBees API")
                cloudbees_valid = True
            else:
                console.print(f"  [red]✗[/red] CloudBees API: {error}")
    except Exception as e:
        console.print(f"  [red]✗[/red] CloudBees API: {str(e)}")

    # Validate GitHub credentials
    github_client = GitHubClient(github_pat)
    try:
        success, error = asyncio.run(github_client.validate_credentials())
        if success:
            console.print("  [green]✓[/green] GitHub API")
            github_valid = True
        else:
            console.print(f"  [red]✗[/red] GitHub API: {error}")
    except Exception as e:
        console.print(f"  [red]✗[/red] GitHub API: {str(e)}")

    return cloudbees_valid, github_valid
