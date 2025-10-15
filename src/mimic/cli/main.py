"""Main CLI application and core commands for Mimic."""

import asyncio
import json
import subprocess
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..config_manager import ConfigManager
from ..environments import list_preset_environments
from ..exceptions import ValidationError
from ..input_helpers import format_field_name, prompt_cloudbees_org, prompt_github_org
from ..utils import resolve_run_name
from .cleanup import cleanup_app
from .config import config_app
from .display import display_scenario_preview, display_success_summary
from .env import env_app, prepare_environment_config
from .scenario_pack import scenario_pack_app

# Create main Typer app
app = typer.Typer(
    name="mimic",
    help="CloudBees Unify scenario instantiation CLI tool",
    no_args_is_help=True,
)

# Shared instances
console = Console()
config_manager = ConfigManager()

# Register sub-applications
app.add_typer(env_app, name="env")
app.add_typer(config_app, name="config")
app.add_typer(cleanup_app, name="cleanup")
app.add_typer(cleanup_app, name="clean")  # Alias for cleanup
app.add_typer(scenario_pack_app, name="scenario-pack")
app.add_typer(scenario_pack_app, name="pack")  # Alias for scenario-pack


@app.command("list")
def list_scenarios():
    """List available scenarios."""
    from ..scenarios import initialize_scenarios_from_config

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
        # Initialize scenario manager from config
        scenario_manager = initialize_scenarios_from_config()

        # Get all scenarios
        scenarios = scenario_manager.list_scenarios()

        if not scenarios:
            console.print(
                Panel(
                    "[yellow]No scenarios found[/yellow]\n\n"
                    "Check that the scenarios/ directory exists and contains YAML files.",
                    title="Scenarios",
                    border_style="yellow",
                )
            )
            return

        # Create table
        table = Table(title="Available Scenarios", show_header=True, expand=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="bold white")
        table.add_column("Summary", style="dim", overflow="fold")
        table.add_column("Source", style="magenta", no_wrap=True)
        table.add_column("Parameters", style="yellow", no_wrap=True)

        for scenario in scenarios:
            param_count = (
                len(scenario.get("parameters", {})) if scenario.get("parameters") else 0
            )
            param_text = f"{param_count} params" if param_count > 0 else "none"
            pack_source = scenario.get("pack_source", "unknown")

            table.add_row(
                scenario["id"],
                scenario["name"],
                scenario["summary"],
                pack_source,
                param_text,
            )

        console.print()
        console.print(table)
        console.print()

        # Show example usage
        console.print("[dim]Run a scenario with:[/dim] mimic run <scenario-id>")
        console.print()

    except Exception as e:
        console.print(f"[red]Error loading scenarios:[/red] {e}")
        raise typer.Exit(1) from e


# Alias for list command
app.command("ls")(list_scenarios)


@app.command()
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
    from ..gh import GitHubClient
    from ..pipeline import CreationPipeline
    from ..scenarios import initialize_scenarios_from_config
    from ..state_tracker import StateTracker
    from ..unify import UnifyAPIClient

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
        provided_parameters = {}

        # Load from JSON file if provided
        if param_file:
            try:
                file_path = Path(param_file)
                if not file_path.exists():
                    console.print(
                        f"[red]Error:[/red] Parameter file not found: {param_file}"
                    )
                    raise typer.Exit(1)

                with open(file_path) as f:
                    file_params = json.load(f)

                if not isinstance(file_params, dict):
                    console.print(
                        f"[red]Error:[/red] Parameter file must contain a JSON object (got {type(file_params).__name__})"
                    )
                    raise typer.Exit(1)

                provided_parameters.update(file_params)
                console.print(
                    f"[dim]Loaded {len(file_params)} parameter(s) from {param_file}[/dim]"
                )
            except json.JSONDecodeError as e:
                console.print(f"[red]Error:[/red] Invalid JSON in parameter file: {e}")
                raise typer.Exit(1) from e

        # Parse --set flags (these override file parameters)
        if set_params:
            for param in set_params:
                if "=" not in param:
                    console.print(
                        f"[red]Error:[/red] Invalid --set format: '{param}'. Use: --set name=value"
                    )
                    raise typer.Exit(1)

                key, value = param.split("=", 1)
                key = key.strip()
                value = value.strip()

                if not key:
                    console.print("[red]Error:[/red] Parameter name cannot be empty")
                    raise typer.Exit(1)

                provided_parameters[key] = value

            console.print(
                f"[dim]Set {len(set_params)} parameter(s) from --set flags[/dim]"
            )

        # Opportunistic cleanup check (before proceeding with scenario execution)
        # Skip if --yes flag is used
        auto_cleanup_prompt = config_manager.get_setting("auto_cleanup_prompt", True)
        if auto_cleanup_prompt and not yes:
            from ..cleanup_manager import CleanupManager

            cleanup_manager = CleanupManager(console=console)
            expired_sessions = cleanup_manager.check_expired_sessions()

            if expired_sessions:
                console.print()
                console.print(
                    f"[yellow]Found {len(expired_sessions)} expired session(s)[/yellow]"
                )

                # Show brief list
                for session in expired_sessions[:3]:  # Show max 3
                    run_name = getattr(session, "run_name", session.session_id)
                    console.print(f"  • {run_name} - {session.scenario_id}")

                if len(expired_sessions) > 3:
                    console.print(f"  • ... and {len(expired_sessions) - 3} more")

                console.print()

                # Prompt to clean up
                cleanup_now = typer.confirm(
                    "Clean up expired sessions before proceeding?", default=True
                )

                if cleanup_now:
                    console.print()
                    results = asyncio.run(
                        cleanup_manager.cleanup_expired_sessions(
                            dry_run=False, auto_confirm=True
                        )
                    )
                    console.print(
                        f"[green]✓[/green] Cleaned up {results['cleaned_sessions']} session(s)\n"
                    )
                else:
                    console.print(
                        "[dim]Skipping cleanup. You can clean up later with: mimic cleanup expired[/dim]\n"
                    )

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
            import questionary

            scenarios = scenario_manager.list_scenarios()
            if not scenarios:
                console.print("[red]Error:[/red] No scenarios available")
                console.print("\n[dim]Add a scenario pack with:[/dim] mimic pack add")
                raise typer.Exit(1)

            # Build choices with scenario name and summary
            choices = []
            scenario_map = {}
            for s in scenarios:
                display = f"{s['name']} ({s['id']})"
                if s.get("summary"):
                    display += f" - {s['summary']}"
                choices.append(display)
                scenario_map[display] = s["id"]

            console.print()
            selection = questionary.select(
                "Select a scenario to run:",
                choices=choices,
                use_shortcuts=True,
                use_arrow_keys=True,
            ).ask()

            if not selection:
                # User cancelled
                raise typer.Exit(0)

            scenario_id = scenario_map[selection]
            console.print()

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

        # Collect parameters (merge provided parameters with interactive prompts)
        parameters = provided_parameters.copy()

        if scenario.parameter_schema:
            # Determine if we need to prompt for any parameters
            missing_params = []
            for prop_name, prop in scenario.parameter_schema.properties.items():
                is_required = prop_name in scenario.parameter_schema.required

                # Check if parameter is missing or empty
                if prop_name not in parameters or (
                    is_required and not str(parameters.get(prop_name, "")).strip()
                ):
                    missing_params.append((prop_name, prop, is_required))

            # Convert string boolean values in provided parameters to actual booleans
            for prop_name, prop in scenario.parameter_schema.properties.items():
                if prop.type == "boolean" and prop_name in parameters:
                    value = parameters[prop_name]
                    if isinstance(value, str):
                        if value.lower() in ("true", "yes", "1", "on"):
                            parameters[prop_name] = True
                        elif value.lower() in ("false", "no", "0", "off", ""):
                            parameters[prop_name] = False

            # If there are missing parameters, prompt for them
            if missing_params:
                console.print("[bold]Required Parameters:[/bold]\n")

                for prop_name, prop, is_required in missing_params:
                    # Format field name nicely
                    formatted_name = format_field_name(prop_name)

                    # Build prompt text
                    if prop.description:
                        prompt_text = f"{formatted_name}: {prop.description}"
                    else:
                        prompt_text = formatted_name

                    # Add optional indicator
                    if not is_required:
                        prompt_text += " [optional]"

                    # Retry loop for validation
                    value = None
                    while True:
                        try:
                            # Special handling for GitHub org parameter
                            if prop_name == "target_org":
                                value = prompt_github_org(
                                    description=prompt_text,
                                    required=is_required,
                                )
                            # Prompt based on type
                            elif prop.type == "boolean":
                                value = typer.confirm(
                                    prompt_text, default=prop.default or False
                                )
                            elif prop.enum:
                                # For enum, use questionary for better UX
                                import questionary

                                value = questionary.select(
                                    prompt_text,
                                    choices=prop.enum,
                                    default=prop.default or prop.enum[0],
                                ).ask()
                            else:
                                # Regular text prompt
                                default_val = prop.default or ""
                                value = typer.prompt(
                                    prompt_text,
                                    default=default_val,
                                    show_default=bool(prop.default),
                                )

                            # Validate the parameter immediately
                            if value or is_required or value == 0 or value is False:
                                scenario.validate_single_parameter(prop_name, value)

                            # If we get here, validation passed
                            break

                        except ValidationError as e:
                            # Show validation error and re-prompt
                            console.print(f"[red]✗ {str(e)}[/red]")
                            if not is_required:
                                # For optional fields, allow them to skip on error
                                skip = typer.confirm(
                                    "Skip this optional parameter?", default=True
                                )
                                if skip:
                                    value = None
                                    break
                            # Otherwise, loop and re-prompt

                    # Add the validated value
                    if (
                        value or not is_required or value == 0 or value is False
                    ):  # Add value (or empty string for optional params)
                        parameters[prop_name] = value

                console.print()
            elif provided_parameters:
                # All parameters provided, show confirmation
                console.print("[bold]Using provided parameters:[/bold]\n")
                for key, value in parameters.items():
                    console.print(f"  • {key}: [yellow]{value}[/yellow]")
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
        console.print("[bold]Execution Details:[/bold]\n")
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
        if no_expiration:
            expiration_days = 365 * 10  # 10 years (effectively never expires)
            expiration_label = "Never"
        elif expires_in_days is not None:
            expiration_days = expires_in_days
            expiration_label = f"{expiration_days} days"
        else:
            # Interactive expiration selection
            import questionary

            default_expiration = config_manager.get_setting(
                "default_expiration_days", 7
            )
            recent_expirations = config_manager.get_recent_values("expiration_days")

            # Build expiration options
            expiration_options = []

            # Add recent values first (deduplicated)
            seen = set()
            for exp_val in recent_expirations:
                try:
                    exp_int = int(exp_val)
                    if exp_int not in seen and exp_int > 0:
                        expiration_options.append((f"{exp_int} days", str(exp_int)))
                        seen.add(exp_int)
                except (ValueError, TypeError):
                    pass

            # Add default if not already in list
            if default_expiration not in seen:
                expiration_options.append(
                    (f"{default_expiration} days (default)", str(default_expiration))
                )
                seen.add(default_expiration)

            # Add common options if not in list
            for common in [1, 7, 14, 30]:
                if common not in seen:
                    expiration_options.append((f"{common} days", str(common)))

            # Add "never" option
            expiration_options.append(("Never expires", "never"))

            # Add custom option
            expiration_options.append(("Custom...", "custom"))

            console.print()
            selected_expiration = questionary.select(
                "Expiration:",
                choices=[opt[0] for opt in expiration_options],
                default=expiration_options[0][0]
                if expiration_options
                else f"{default_expiration} days (default)",
            ).ask()

            if not selected_expiration:
                # User cancelled
                raise typer.Exit(0)

            # Find the selected value
            selected_value = None
            for label, value in expiration_options:
                if label == selected_expiration:
                    selected_value = value
                    break

            if selected_value == "never":
                expiration_days = 365 * 10
                expiration_label = "Never"
                no_expiration = True
            elif selected_value == "custom":
                custom_days = typer.prompt("Enter custom expiration days", type=int)
                expiration_days = custom_days
                expiration_label = f"{expiration_days} days"
                # Cache the custom value
                config_manager.add_recent_value("expiration_days", str(custom_days))
            else:
                expiration_days = int(selected_value)
                expiration_label = f"{expiration_days} days"
                # Cache the selected value
                config_manager.add_recent_value("expiration_days", selected_value)

            console.print(f"Expiration: [yellow]{expiration_label}[/yellow]")

        console.print()

        # Validate credentials before starting scenario execution
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
            console.print(
                "[bold cyan]Dry run mode - no resources will be created[/bold cyan]\n"
            )

            # Validate and resolve scenario parameters
            processed_parameters = scenario.validate_input(parameters)
            # Get environment properties for template resolution
            env_properties = config_manager.get_environment_properties(current_env)
            resolved_scenario = scenario.resolve_template_variables(
                processed_parameters, env_properties
            )

            # Generate preview
            preview = CreationPipeline.preview_scenario(resolved_scenario)

            # Display preview
            display_scenario_preview(
                console,
                preview,
                scenario,
                current_env,
                expiration_label,
                is_dry_run=True,
            )

            return

        # Preview + confirmation (unless --yes flag is used)
        if not yes:
            console.print("[bold cyan]Preview - Resources to be created[/bold cyan]\n")

            # Validate and resolve scenario parameters
            processed_parameters = scenario.validate_input(parameters)
            # Get environment properties for template resolution
            env_properties = config_manager.get_environment_properties(current_env)
            resolved_scenario = scenario.resolve_template_variables(
                processed_parameters, env_properties
            )

            # Generate preview
            preview = CreationPipeline.preview_scenario(resolved_scenario)

            # Display preview with expiration info
            display_scenario_preview(
                console, preview, scenario, current_env, expiration_label
            )

            # Prompt for confirmation
            console.print()
            proceed = typer.confirm("Proceed with creation?", default=True)

            if not proceed:
                console.print("[yellow]Cancelled by user[/yellow]")
                raise typer.Exit(0)

            console.print()

        # Generate session ID
        session_id = str(uuid.uuid4())[:8]

        # Resolve run name from scenario name_template
        run_name = resolve_run_name(scenario, parameters, session_id)

        # Create state tracker and session
        state_tracker = StateTracker()
        state_tracker.create_session(
            session_id=session_id,
            scenario_id=scenario_id,
            run_name=run_name,
            environment=current_env,
            expiration_days=expiration_days,
            metadata={
                "parameters": parameters,
                "no_expiration": no_expiration,
            },
        )

        # Create and run pipeline
        console.print("[bold green]Starting scenario execution...[/bold green]")
        console.print(f"[dim]Run Name: {run_name}[/dim]")
        console.print(f"[dim]Session ID: {session_id}[/dim]")
        console.print(f"[dim]Environment: {current_env}[/dim]")
        console.print()

        # Get default GitHub username for repo invitations
        invitee_username = config_manager.get_github_username()

        # Get environment properties
        env_properties = config_manager.get_environment_properties(current_env)

        pipeline = CreationPipeline(
            organization_id=organization_id,
            endpoint_id=endpoint_id,
            unify_pat=cloudbees_pat,
            unify_base_url=env_url,
            session_id=session_id,
            github_pat=github_pat,
            invitee_username=invitee_username,
            env_properties=env_properties,
        )

        # Execute scenario
        summary = asyncio.run(pipeline.execute_scenario(scenario, parameters))

        # Track resources in state
        # Add repositories
        for repo_data in summary.get("repositories", []):
            state_tracker.add_resource(
                session_id=session_id,
                resource_type="github_repo",
                resource_id=repo_data.get("full_name", ""),
                resource_name=repo_data.get("name", ""),
                metadata=repo_data,
            )

        # Add components
        for component_name, component_data in pipeline.created_components.items():
            state_tracker.add_resource(
                session_id=session_id,
                resource_type="cloudbees_component",
                resource_id=component_data.get("id", ""),
                resource_name=component_name,
                org_id=organization_id,
                metadata=component_data,
            )

        # Add environments
        for env_name, env_data in pipeline.created_environments.items():
            state_tracker.add_resource(
                session_id=session_id,
                resource_type="cloudbees_environment",
                resource_id=env_data.get("id", ""),
                resource_name=env_name,
                org_id=organization_id,
                metadata=env_data,
            )

        # Add applications
        for app_name, app_data in pipeline.created_applications.items():
            state_tracker.add_resource(
                session_id=session_id,
                resource_type="cloudbees_application",
                resource_id=app_data.get("id", ""),
                resource_name=app_name,
                org_id=organization_id,
                metadata=app_data,
            )

        # Build success message with resource details
        console.print()
        display_success_summary(
            console=console,
            session_id=session_id,
            run_name=run_name,
            environment=current_env,
            expiration_label=expiration_label,
            summary=summary,
            pipeline=pipeline,
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        raise typer.Exit(0) from None
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def upgrade():
    """Upgrade Mimic and all scenario packs to the latest versions.

    This command:
    1. Upgrades the Mimic tool itself using 'uv tool upgrade mimic'
    2. Updates all configured scenario packs by pulling latest changes

    Example:
        mimic upgrade
    """
    from ..scenario_pack_manager import ScenarioPackManager

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


@app.command()
def mcp():
    """Start the MCP (Model Context Protocol) stdio server."""
    from ..mcp import run_mcp_server

    run_mcp_server()


@app.command()
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

    # Check if already configured (unless --force)
    if not force and not config_manager.is_first_run():
        current_env = config_manager.get_current_environment()
        if current_env:
            console.print()
            console.print(
                Panel(
                    "[yellow]Mimic is already configured[/yellow]\n\n"
                    f"Current environment: [cyan]{current_env}[/cyan]\n\n"
                    "To reconfigure, run: [dim]mimic setup --force[/dim]\n"
                    "To add another environment: [dim]mimic env add <name>[/dim]",
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
    if "official" in packs:
        console.print("[green]✓[/green] Official scenario pack already configured\n")
    else:
        console.print("Add official CloudBees scenario pack?\n")
        add_pack = typer.confirm(
            "Add from github.com/cb-demos/mimic-scenarios", default=True
        )

        if add_pack:
            try:
                console.print("\n[dim]Cloning scenario pack...[/dim]")
                config_manager.add_scenario_pack(
                    "official",
                    "https://github.com/cb-demos/mimic-scenarios",
                    "main",
                    enabled=True,
                )

                pack_manager = ScenarioPackManager(config_manager.packs_dir)
                pack_manager.clone_pack(
                    "official",
                    "https://github.com/cb-demos/mimic-scenarios",
                    "main",
                )

                console.print("[green]✓[/green] Scenario pack added\n")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Could not add scenario pack: {e}")
                console.print(
                    "[dim]You can add it later with: mimic scenario-pack add official https://github.com/cb-demos/mimic-scenarios[/dim]\n"
                )
        else:
            console.print(
                "[dim]Skipped. Add later with: mimic scenario-pack add official https://github.com/cb-demos/mimic-scenarios[/dim]\n"
            )

    # Step 1: CloudBees Environment Setup
    console.print("[bold cyan]Step 2: CloudBees Environment[/bold cyan]\n")
    console.print("Choose a CloudBees Unify environment to connect to:\n")

    # Show preset environments
    presets = list_preset_environments()
    console.print("[bold]Preset Environments:[/bold]")
    for idx, (name, config) in enumerate(presets.items(), 1):
        console.print(f"  {idx}. [cyan]{name}[/cyan] - {config.description}")
    console.print(f"  {len(presets) + 1}. [cyan]custom[/cyan] - Custom environment\n")

    # Prompt for environment choice
    while True:
        choice = typer.prompt(f"Select environment (1-{len(presets) + 1})", default="1")
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

    # Get environment details
    if choice_num <= len(presets):
        # Preset environment
        preset_name = list(presets.keys())[choice_num - 1]
        env_name = preset_name
        env_url = None
        endpoint_id = None

        console.print(f"[bold]Selected:[/bold] {preset_name}")
    else:
        # Custom environment
        env_name = typer.prompt("Environment name")
        env_url = typer.prompt("API URL")
        endpoint_id = typer.prompt("Endpoint ID")

    # Prepare environment configuration (validates and sets defaults)
    env_name, env_url, endpoint_id, env_properties = prepare_environment_config(
        env_name, env_url, endpoint_id
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

    # Save environment
    try:
        config_manager.add_environment(
            env_name, env_url, pat, endpoint_id, env_properties
        )
        console.print(f"[green]✓[/green] Environment '[cyan]{env_name}[/cyan]' saved\n")
    except Exception as e:
        console.print(f"[red]Error saving environment:[/red] {e}")
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
        config_manager.set_github_pat(github_pat)
        console.print("[green]✓[/green] GitHub token saved\n")

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
            f"  • CloudBees Environment: [cyan]{env_name}[/cyan]\n"
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
