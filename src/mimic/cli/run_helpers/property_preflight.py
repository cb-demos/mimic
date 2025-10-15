"""Pre-flight check for required properties and secrets."""

import typer
from prompt_toolkit import prompt as pt_prompt
from rich.console import Console
from rich.table import Table

from ...scenarios import Scenario
from ...unify import UnifyAPIClient

console = Console()


def _prompt_secret(prompt_text: str) -> str:
    """Prompt for a secret value with asterisk feedback and preview confirmation.

    Shows asterisks as you type. Shows first few characters for confirmation.

    Args:
        prompt_text: The prompt text to display

    Returns:
        The secret value entered by the user

    Raises:
        typer.Exit: If user rejects the preview
    """
    console.print(f"[bold]{prompt_text}[/bold]")
    console.print("[dim]Asterisks (*) will appear as you type[/dim]")
    value = pt_prompt("Value: ", is_password=True)

    # Show preview of characters for confirmation
    # Show ~20% of the value, with a minimum of 4 and maximum of 50 chars
    if len(value) > 0:
        preview_length = max(4, min(50, int(len(value) * 0.2)))
        console.print(
            f"First {preview_length} chars: [dim]{value[:preview_length]}...[/dim]"
        )
        console.print(f"Total length: [dim]{len(value)} characters[/dim]")
        if not typer.confirm("Is this correct?", default=True):
            raise typer.Exit(1)

    return value


def check_required_properties(
    scenario: Scenario,
    env_url: str,
    cloudbees_pat: str,
    organization_id: str,
) -> None:
    """Check if required properties and secrets exist, prompt to create if missing.

    Args:
        scenario: The scenario being run
        env_url: CloudBees Unify API URL
        cloudbees_pat: CloudBees Personal Access Token
        organization_id: CloudBees Organization ID

    Raises:
        typer.Exit: If user chooses to abort
    """
    # Check if scenario has any required properties or secrets
    if not scenario.required_properties and not scenario.required_secrets:
        return  # Nothing to check

    console.print("[bold]Checking required properties and secrets...[/bold]")
    console.print()

    # Fetch existing properties from the organization
    with UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat) as client:
        try:
            response = client.list_properties(organization_id)
            existing_properties = response.get("properties", [])

            # Build a set of existing property names
            existing_names = {
                prop.get("property", {}).get("name")
                for prop in existing_properties
                if prop.get("property", {}).get("name")
            }

        except Exception as e:
            console.print(f"[red]Error fetching properties:[/red] {e}")
            raise typer.Exit(1) from e

    # Check required properties
    missing_properties = [
        name for name in scenario.required_properties if name not in existing_names
    ]

    # Check required secrets
    missing_secrets = [
        name for name in scenario.required_secrets if name not in existing_names
    ]

    # If everything exists, we're done
    if not missing_properties and not missing_secrets:
        console.print(
            f"  [green]✓[/green] All required properties and secrets exist ({len(scenario.required_properties) + len(scenario.required_secrets)} total)"
        )
        console.print()
        return

    # Display what's missing
    console.print("[yellow]Missing properties/secrets:[/yellow]")
    console.print()

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="white")
    table.add_column("Type", style="magenta")

    for name in missing_properties:
        table.add_row(name, "Property")

    for name in missing_secrets:
        table.add_row(name, "Secret")

    console.print(table)
    console.print()

    # Ask if user wants to create them now
    create_now = typer.confirm("Would you like to create these now?", default=True)

    if not create_now:
        console.print()
        console.print("[yellow]Skipping property creation.[/yellow]")
        console.print(
            "[dim]You can create them later with:[/dim] mimic config add-property"
        )
        console.print()
        return

    # Create missing properties interactively
    with UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat) as client:
        # Create properties
        for prop_name in missing_properties:
            console.print()
            console.print(f"[bold]Creating property: {prop_name}[/bold]")
            value = typer.prompt(f"Value for {prop_name}")

            try:
                client.create_property(
                    resource_id=organization_id,
                    name=prop_name,
                    value=value,
                    is_secret=False,
                )
                console.print(f"  [green]✓[/green] Property '{prop_name}' created")
            except Exception as e:
                console.print(f"  [red]✗[/red] Failed to create '{prop_name}': {e}")
                raise typer.Exit(1) from e

        # Create secrets
        for secret_name in missing_secrets:
            console.print()
            value = _prompt_secret(f"Value for {secret_name}")

            try:
                client.create_property(
                    resource_id=organization_id,
                    name=secret_name,
                    value=value,
                    is_secret=True,
                )
                console.print(f"  [green]✓[/green] Secret '{secret_name}' created")
            except Exception as e:
                console.print(f"  [red]✗[/red] Failed to create '{secret_name}': {e}")
                raise typer.Exit(1) from e

    console.print()
    console.print(
        "[green]✓[/green] All required properties and secrets are now configured"
    )
    console.print()
