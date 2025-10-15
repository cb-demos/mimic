"""Run command for Mimic CLI."""

import typer
from rich.console import Console
from rich.panel import Panel

from ..config_manager import ConfigManager
from ..input_helpers import prompt_cloudbees_org
from .run_helpers import (
    collect_parameters,
    execute_scenario,
    handle_dry_run,
    handle_expiration_selection,
    handle_opportunistic_cleanup,
    parse_parameters,
    select_scenario_interactive,
    show_preview_and_confirm,
    validate_credentials,
)

# Shared instances
console = Console()


def run(
    scenario_id: str = typer.Argument(
        None, help="Scenario ID to run (interactive selection if omitted)"
    ),
    expires_in_days: int = typer.Option(
        None,
        "--expires-in",
        "--expiration-days",
        help="Days until resources expire (overrides config default)",
    ),
    no_expiration: bool = typer.Option(
        False, "--no-expiration", help="Resources never expire"
    ),
    org_id: str = typer.Option(
        None, "--org-id", help="CloudBees Organization ID (skips prompt)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview resources without creating them"
    ),
    set_params: list[str] = typer.Option(
        None,
        "--set",
        help="Set parameter value (format: name=value, repeatable, overrides file)",
    ),
    param_file: str = typer.Option(
        None,
        "-f",
        "--file",
        help="Load parameters from JSON file",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip all confirmation prompts (use with caution)",
    ),
):
    """Run a scenario with interactive parameter prompts or non-interactive mode.

    Examples:
        # Interactive mode
        mimic run                  # Interactive scenario selection
        mimic run hackers-app
        mimic run hackers-app --expires-in 1
        mimic run hackers-app --no-expiration
        mimic run hackers-app --org-id abc-123

        # Non-interactive mode (automation/CI-CD)
        mimic run hackers-app --set project_name=demo --set target_org=acme
        mimic run hackers-app -f params.json
        mimic run hackers-app -f params.json --set project_name=override
        mimic run hackers-app -f params.json --yes
    """
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
        # Validate expiration flags
        if no_expiration and expires_in_days is not None:
            console.print(
                "[red]Error:[/red] Cannot use both --no-expiration and --expires-in"
            )
            raise typer.Exit(1)

        # Parse parameters from --set flags and JSON file
        provided_parameters = parse_parameters(param_file, set_params)

        # Opportunistic cleanup check (before proceeding with scenario execution)
        # Skip if --yes flag is used
        handle_opportunistic_cleanup(config_manager, yes)

        # Check if environment is configured
        current_env = config_manager.get_current_environment()
        if not current_env:
            console.print(
                Panel(
                    "[red]No environment configured[/red]\n\n"
                    "Add an environment first:\n"
                    "[dim]mimic env add (prod|preprod|demo)[/dim]",
                    title="Configuration Required",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

        # Load scenarios
        scenario_manager = initialize_scenarios_from_config()

        # Interactive scenario selection if not provided
        if not scenario_id:
            scenario_id = select_scenario_interactive(scenario_manager)

        scenario = scenario_manager.get_scenario(scenario_id)

        if not scenario:
            console.print(f"[red]Error:[/red] Scenario '{scenario_id}' not found")
            console.print("\n[dim]List available scenarios with:[/dim] mimic list")
            raise typer.Exit(1)

        # Show scenario info
        console.print()
        # Use details if available, fallback to summary
        description = scenario.details if scenario.details else scenario.summary
        console.print(
            Panel(
                f"[bold]{scenario.name}[/bold]\n\n{description}",
                title=f"Scenario: {scenario.id}",
                border_style="cyan",
            )
        )
        console.print()

        # Show target environment immediately
        console.print(f"Target Environment: [cyan]{current_env}[/cyan]")
        console.print()

        # Get credentials
        cloudbees_pat = config_manager.get_cloudbees_pat(current_env)
        if not cloudbees_pat:
            console.print(
                f"[red]Error:[/red] No PAT found for environment '{current_env}'"
            )
            console.print(
                f"[dim]Re-add the environment with:[/dim] mimic env add {current_env}"
            )
            raise typer.Exit(1)

        github_pat = config_manager.get_github_pat()
        if not github_pat:
            console.print()
            console.print(
                "[yellow]GitHub PAT not configured.[/yellow] Please enter it now:"
            )
            github_pat = typer.prompt("GitHub Personal Access Token", hide_input=True)
            config_manager.set_github_pat(github_pat)
            console.print("[dim]GitHub PAT saved securely in OS keyring[/dim]\n")

        # Get environment details
        env_url = config_manager.get_environment_url(current_env)
        endpoint_id = config_manager.get_endpoint_id(current_env)

        if not env_url or not endpoint_id:
            console.print(
                f"[red]Error:[/red] Environment '{current_env}' is missing configuration"
            )
            console.print(
                f"[dim]Re-add the environment with:[/dim] mimic env add {current_env}"
            )
            raise typer.Exit(1)

        # Prompt for organization ID if not provided
        if not org_id:
            organization_id = prompt_cloudbees_org(
                env_url=env_url,
                cloudbees_pat=cloudbees_pat,
                env_name=current_env,
                description="CloudBees Organization",
            )
        else:
            organization_id = org_id
            # Try to show cached org name if available
            cached_name = config_manager.get_cached_org_name(org_id, current_env)
            if cached_name:
                console.print(
                    f"Organization: [yellow]{cached_name}[/yellow] ({org_id[:8]}...) [dim](from --org-id flag)[/dim]"
                )
            else:
                console.print(
                    f"Organization ID: [yellow]{organization_id}[/yellow] [dim](from --org-id flag)[/dim]"
                )

        # Determine expiration (prompt if not specified via flags)
        expiration_days, expiration_label = handle_expiration_selection(
            config_manager, no_expiration, expires_in_days
        )

        console.print()

        # Collect parameters (merge provided parameters with interactive prompts)
        parameters = collect_parameters(scenario, provided_parameters)

        # Validate credentials before starting scenario execution
        cloudbees_valid, github_valid = validate_credentials(
            env_url, cloudbees_pat, organization_id, github_pat
        )

        # Abort if any validation failed
        if not cloudbees_valid or not github_valid:
            console.print()
            console.print(
                Panel(
                    "[red]Credential validation failed[/red]\n\n"
                    "Please check your credentials and try again:\n"
                    "• CloudBees: mimic env add <name>\n"
                    "• GitHub: mimic config github-token",
                    title="Error",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

        console.print()

        # Handle dry-run mode
        if dry_run:
            handle_dry_run(
                config_manager, scenario, parameters, current_env, expiration_label
            )
            return

        # Preview + confirmation (unless --yes flag is used)
        if not yes:
            proceed = show_preview_and_confirm(
                config_manager, scenario, parameters, current_env, expiration_label
            )
            if not proceed:
                console.print("[yellow]Cancelled by user[/yellow]")
                raise typer.Exit(0)

            console.print()

        # Execute scenario
        execute_scenario(
            config_manager=config_manager,
            scenario=scenario,
            parameters=parameters,
            scenario_id=scenario_id,
            current_env=current_env,
            expiration_days=expiration_days,
            expiration_label=expiration_label,
            no_expiration=no_expiration,
            organization_id=organization_id,
            endpoint_id=endpoint_id,
            cloudbees_pat=cloudbees_pat,
            env_url=env_url,
            github_pat=github_pat,
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        raise typer.Exit(0) from None
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
