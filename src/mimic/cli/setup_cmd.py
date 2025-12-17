"""Setup command for Mimic CLI."""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel

from ..config_manager import ConfigManager
from ..environments import list_preset_tenants
from ..settings import OFFICIAL_PACK_BRANCH, OFFICIAL_PACK_NAME, OFFICIAL_PACK_URL
from .tenant import prepare_tenant_config

# Shared instances
console = Console()


def setup(
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-run setup even if already configured"
    ),
):
    """Interactive first-run setup wizard.

    Guides you through complete Mimic configuration:
    - Adding your first CloudBees environment
    - Configuring GitHub credentials (required)
    - Setting up GitHub username for collaborator invites
    - Testing API access
    - Getting started with scenarios

    Can be re-run safely with --force to reconfigure.
    """
    from ..gh import GitHubClient
    from ..scenario_pack_manager import ScenarioPackManager
    from ..unify import UnifyAPIClient

    config_manager = ConfigManager()

    # Check if already configured (unless --force)
    if not force and not config_manager.is_first_run():
        current_env = config_manager.get_current_tenant()
        if current_env:
            console.print()
            console.print(
                Panel(
                    "[yellow]Mimic is already configured[/yellow]\n\n"
                    f"Current tenant: [cyan]{current_env}[/cyan]\n\n"
                    "To reconfigure, run: [dim]mimic setup --force[/dim]\n"
                    "To add another tenant: [dim]mimic tenant add <name>[/dim]",
                    title="Setup",
                    border_style="yellow",
                )
            )
            return

    console.print()
    console.print(
        Panel(
            "[bold cyan]Welcome to Mimic![/bold cyan]\n\n"
            "Mimic is a CloudBees Unify scenario orchestration tool.\n"
            "It helps you quickly create demo environments with:\n"
            "  • GitHub repositories from templates\n"
            "  • CloudBees components and environments\n"
            "  • Applications and feature flags\n\n"
            "This wizard will guide you through initial setup.",
            title="Setup Wizard",
            border_style="cyan",
        )
    )
    console.print()

    # Step 0: Scenario Pack Setup
    console.print("[bold cyan]Step 1: Scenario Pack[/bold cyan]\n")

    packs = config_manager.list_scenario_packs()
    if OFFICIAL_PACK_NAME in packs:
        console.print("[green]✓[/green] Official scenario pack already configured\n")
    else:
        console.print("Add official CloudBees scenario pack?\n")
        add_pack = typer.confirm(
            f"Add from {OFFICIAL_PACK_URL.replace('https://github.com/', 'github.com/')}",
            default=True,
        )

        if add_pack:
            try:
                console.print("\n[dim]Cloning scenario pack...[/dim]")
                config_manager.add_scenario_pack(
                    OFFICIAL_PACK_NAME,
                    OFFICIAL_PACK_URL,
                    OFFICIAL_PACK_BRANCH,
                    enabled=True,
                )

                pack_manager = ScenarioPackManager(config_manager.packs_dir)
                pack_manager.clone_pack(
                    OFFICIAL_PACK_NAME,
                    OFFICIAL_PACK_URL,
                    OFFICIAL_PACK_BRANCH,
                )

                console.print("[green]✓[/green] Scenario pack added\n")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Could not add scenario pack: {e}")
                console.print(
                    f"[dim]You can add it later with: mimic scenario-pack add {OFFICIAL_PACK_NAME} {OFFICIAL_PACK_URL}[/dim]\n"
                )
        else:
            console.print(
                f"[dim]Skipped. Add later with: mimic scenario-pack add {OFFICIAL_PACK_NAME} {OFFICIAL_PACK_URL}[/dim]\n"
            )

    # Step 1.5: Keyring Health Check
    console.print("[bold cyan]Checking keyring availability...[/bold cyan]")
    from ..keyring_health import test_keyring_available

    success, error_msg = test_keyring_available(timeout=3)
    if not success:
        console.print()
        console.print(
            Panel(
                f"[red]✗ Keyring backend is not available[/red]\n\n{error_msg}",
                title="Keyring Error",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    console.print("[green]✓[/green] Keyring backend is available\n")

    # Step 2: CloudBees Tenant Setup
    console.print("[bold cyan]Step 2: CloudBees Tenant[/bold cyan]\n")
    console.print("Choose a CloudBees Unify tenant to connect to:\n")

    # Show preset tenants
    presets = list_preset_tenants()
    console.print("[bold]Preset Tenants:[/bold]")
    for idx, (name, config) in enumerate(presets.items(), 1):
        console.print(f"  {idx}. [cyan]{name}[/cyan] - {config.description}")
    console.print(f"  {len(presets) + 1}. [cyan]custom[/cyan] - Custom tenant\n")

    # Prompt for tenant choice
    while True:
        choice = typer.prompt(f"Select tenant (1-{len(presets) + 1})", default="1")
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(presets) + 1:
                break
            console.print(
                f"[red]Invalid choice. Please enter 1-{len(presets) + 1}[/red]"
            )
        except ValueError:
            console.print("[red]Invalid choice. Please enter a number[/red]")

    console.print()

    # Get tenant details
    if choice_num <= len(presets):
        # Preset tenant
        preset_name = list(presets.keys())[choice_num - 1]
        env_name = preset_name
        env_url = None
        endpoint_id = None

        console.print(f"[bold]Selected:[/bold] {preset_name}")
    else:
        # Custom tenant
        env_name = typer.prompt("Tenant name")
        env_url = typer.prompt("API URL")
        endpoint_id = typer.prompt("Endpoint ID")

    # Prepare tenant configuration (validates and sets defaults)
    env_name, env_url, endpoint_id, env_properties, use_legacy_flags = (
        prepare_tenant_config(env_name, env_url, endpoint_id)
    )

    console.print(f"[dim]API URL: {env_url}[/dim]")
    console.print(f"[dim]Endpoint ID: {endpoint_id}[/dim]")
    if env_properties:
        console.print(f"[dim]Properties: {len(env_properties)} configured[/dim]")
    console.print()

    # Prompt for credentials
    console.print("[bold]CloudBees Unify Credentials:[/bold]")
    pat = typer.prompt("CloudBees Unify PAT", hide_input=True)
    org_id = typer.prompt("Organization ID (for validation)")
    console.print()

    # Validate CloudBees credentials
    console.print("[dim]Validating CloudBees credentials...[/dim]")
    try:
        with UnifyAPIClient(base_url=env_url, api_key=pat) as client:
            success, error = client.validate_credentials(org_id)
            if success:
                console.print("[green]✓[/green] CloudBees API access verified\n")
            else:
                console.print(
                    Panel(
                        f"[red]✗ Credential validation failed[/red]\n\n{error}",
                        title="Validation Error",
                        border_style="red",
                    )
                )
                raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(
            Panel(
                f"[red]✗ Error validating credentials[/red]\n\n{str(e)}",
                title="Error",
                border_style="red",
            )
        )
        raise typer.Exit(1) from e

    # Save tenant
    try:
        config_manager.add_tenant(
            name=env_name,
            url=env_url,
            pat=pat,
            endpoint_id=endpoint_id,
            properties=env_properties,
            use_legacy_flags=use_legacy_flags,
        )
        console.print(f"[green]✓[/green] Tenant '[cyan]{env_name}[/cyan]' saved\n")
    except Exception as e:
        from ..exceptions import KeyringUnavailableError

        if isinstance(e, KeyringUnavailableError):
            console.print()
            console.print(
                Panel(
                    f"[red]✗ Failed to save credentials[/red]\n\n{e.instructions}",
                    title="Keyring Error",
                    border_style="red",
                )
            )
        else:
            console.print(f"[red]Error saving tenant:[/red] {e}")
        raise typer.Exit(1) from e

    # Step 2: GitHub Setup
    console.print("[bold cyan]Step 3: GitHub Credentials[/bold cyan]\n")
    console.print(
        "Mimic uses GitHub to create repositories from templates.\n"
        "You'll need a GitHub Personal Access Token with 'repo' scope.\n"
    )
    console.print()

    github_configured = False
    github_username = ""
    console.print("[bold]GitHub Credentials:[/bold]")
    github_pat = typer.prompt("GitHub Personal Access Token", hide_input=True)
    console.print()

    # Validate GitHub credentials
    console.print("[dim]Validating GitHub credentials...[/dim]")
    github_client = GitHubClient(github_pat)
    try:
        success, error = asyncio.run(github_client.validate_credentials())
        if success:
            console.print("[green]✓[/green] GitHub API access verified\n")
            github_configured = True
        else:
            console.print(f"[yellow]⚠[/yellow] GitHub validation failed: {error}\n")
            save_anyway = typer.confirm("Save GitHub token anyway?", default=False)
            if save_anyway:
                github_configured = True
            else:
                console.print(
                    "[red]GitHub credentials are required to use Mimic.[/red]\n"
                )
                raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Error validating GitHub: {str(e)}\n")
        save_anyway = typer.confirm("Save GitHub token anyway?", default=False)
        if save_anyway:
            github_configured = True
        else:
            console.print("[red]GitHub credentials are required to use Mimic.[/red]\n")
            raise typer.Exit(1) from None

    if github_configured:
        try:
            config_manager.set_github_pat(github_pat)
            console.print("[green]✓[/green] GitHub token saved\n")
        except Exception as e:
            from ..exceptions import KeyringUnavailableError

            if isinstance(e, KeyringUnavailableError):
                console.print()
                console.print(
                    Panel(
                        f"[red]✗ Failed to save GitHub token[/red]\n\n{e.instructions}",
                        title="Keyring Error",
                        border_style="red",
                    )
                )
            else:
                console.print(f"[red]Error saving GitHub token:[/red] {e}")
            raise typer.Exit(1) from e

        # Prompt for GitHub username
        console.print("[bold]GitHub Username:[/bold]")
        console.print(
            "[dim]Username to invite as collaborator on created repositories[/dim]"
        )
        github_username = typer.prompt("GitHub username")
        config_manager.set_github_username(github_username.strip())
        console.print(
            f"[green]✓[/green] Default GitHub username set to '{github_username.strip()}'\n"
        )

    # Step 3: Success Summary
    console.print()
    console.print(
        Panel(
            "[bold green]✓ Setup Complete![/bold green]\n\n"
            "[bold]Configuration Summary:[/bold]\n"
            f"  • CloudBees Tenant: [cyan]{env_name}[/cyan]\n"
            f"  • GitHub: [green]Configured[/green]\n"
            f"  • GitHub Username: [cyan]{github_username.strip()}[/cyan]\n\n"
            "[bold]Next Steps:[/bold]\n"
            f"  1. List available scenarios: [dim]mimic list[/dim]\n"
            f"  2. Run a scenario: [dim]mimic run <scenario-id>[/dim]\n\n"
            "[dim]Configuration stored in ~/.mimic/config.yaml\n"
            "Credentials stored securely in OS keyring[/dim]",
            title="Setup Complete",
            border_style="green",
        )
    )
    console.print()
