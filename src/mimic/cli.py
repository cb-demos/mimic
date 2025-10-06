"""Main CLI application for Mimic."""

from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config_manager import ConfigManager
from .environments import get_preset_environment, list_preset_environments
from .input_helpers import format_field_name, prompt_cloudbees_org, prompt_github_org

app = typer.Typer(
    name="mimic",
    help="CloudBees Platform scenario instantiation CLI/TUI tool",
    no_args_is_help=True,
)

console = Console()
config_manager = ConfigManager()

# Environment management commands
env_app = typer.Typer(help="Manage CloudBees Platform environments")
app.add_typer(env_app, name="env")

# Config management commands
config_app = typer.Typer(help="Manage configuration settings")
app.add_typer(config_app, name="config")

# Cleanup commands
cleanup_app = typer.Typer(help="Manage and cleanup scenario resources")
app.add_typer(cleanup_app, name="cleanup")
app.add_typer(cleanup_app, name="clean")  # Alias for cleanup

# Scenario pack commands
scenario_pack_app = typer.Typer(help="Manage scenario packs from git repositories")
app.add_typer(scenario_pack_app, name="scenario-pack")
app.add_typer(scenario_pack_app, name="pack")  # Alias for scenario-pack


@app.command("list")
def list_scenarios():
    """List available scenarios."""
    from .scenarios import initialize_scenarios_from_config

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
    import asyncio
    import json
    import uuid
    from pathlib import Path

    from .creation_pipeline import CreationPipeline
    from .scenarios import initialize_scenarios_from_config
    from .state_tracker import StateTracker

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
            from .cleanup_manager import CleanupManager

            cleanup_manager = CleanupManager(console=console)
            expired_sessions = cleanup_manager.check_expired_sessions()

            if expired_sessions:
                console.print()
                console.print(
                    f"[yellow]Found {len(expired_sessions)} expired session(s)[/yellow]"
                )

                # Show brief list
                for session in expired_sessions[:3]:  # Show max 3
                    console.print(f"  • {session.session_id} - {session.scenario_id}")

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

                    # Validate required
                    if is_required and not value:
                        console.print(f"[red]Error:[/red] {formatted_name} is required")
                        raise typer.Exit(1)

                    if (
                        value or not is_required
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

        # Validate CloudBees credentials
        from .gh import GitHubClient
        from .unify import UnifyAPIClient

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
            from .creation_pipeline import CreationPipeline

            console.print(
                "[bold cyan]Dry run mode - no resources will be created[/bold cyan]\n"
            )

            # Validate and resolve scenario parameters
            processed_parameters = scenario.validate_input(parameters)
            resolved_scenario = scenario.resolve_template_variables(
                processed_parameters
            )

            # Generate preview
            preview = CreationPipeline.preview_scenario(resolved_scenario)

            # Display preview
            _display_scenario_preview(
                preview, scenario, current_env, expiration_label, is_dry_run=True
            )

            return

        # Preview + confirmation (unless --yes flag is used)
        if not yes:
            from .creation_pipeline import CreationPipeline

            console.print("[bold cyan]Preview - Resources to be created[/bold cyan]\n")

            # Validate and resolve scenario parameters
            processed_parameters = scenario.validate_input(parameters)
            resolved_scenario = scenario.resolve_template_variables(
                processed_parameters
            )

            # Generate preview
            preview = CreationPipeline.preview_scenario(resolved_scenario)

            # Display preview with expiration info
            _display_scenario_preview(preview, scenario, current_env, expiration_label)

            # Prompt for confirmation
            console.print()
            proceed = typer.confirm("Proceed with creation?", default=True)

            if not proceed:
                console.print("[yellow]Cancelled by user[/yellow]")
                raise typer.Exit(0)

            console.print()

        # Generate session ID
        session_id = str(uuid.uuid4())[:8]

        # Create state tracker and session
        # (expiration_days and expiration_label already determined above)
        state_tracker = StateTracker()
        state_tracker.create_session(
            session_id=session_id,
            scenario_id=scenario_id,
            environment=current_env,
            expiration_days=expiration_days,
            metadata={
                "parameters": parameters,
                "no_expiration": no_expiration,
            },
        )

        # Create and run pipeline
        console.print("[bold green]Starting scenario execution...[/bold green]")
        console.print(f"[dim]Session ID: {session_id}[/dim]")
        console.print(f"[dim]Environment: {current_env}[/dim]")
        console.print()

        # Get default GitHub username for repo invitations
        invitee_username = config_manager.get_github_username()

        pipeline = CreationPipeline(
            organization_id=organization_id,
            endpoint_id=endpoint_id,
            unify_pat=cloudbees_pat,
            unify_base_url=env_url,
            session_id=session_id,
            github_pat=github_pat,
            invitee_username=invitee_username,
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
        _display_success_summary(
            session_id=session_id,
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


def _display_success_summary(
    session_id: str,
    environment: str,
    expiration_label: str,
    summary: dict,
    pipeline: Any,
) -> None:
    """Display a detailed success summary with resource links."""

    # Build success message content
    lines = []
    lines.append("[bold green]✓ Scenario completed successfully![/bold green]\n")
    lines.append(f"Session ID: [cyan]{session_id}[/cyan]")
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


def _display_scenario_preview(
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


@app.command()
def tui():
    """Launch the interactive TUI (Text User Interface)."""
    from .tui import run_tui

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

    run_tui()


@app.command()
def mcp():
    """Start the MCP (Model Context Protocol) stdio server."""
    from .mcp import run_mcp_server

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
    - Configuring GitHub credentials
    - Testing API access
    - Getting started with scenarios

    Can be re-run safely with --force to reconfigure.
    """
    import asyncio

    from .gh import GitHubClient
    from .unify import UnifyAPIClient

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
            "Mimic is a CloudBees Platform scenario orchestration tool.\n"
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
    from .scenario_pack_manager import ScenarioPackManager

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
    console.print("Choose a CloudBees Platform environment to connect to:\n")

    # Show preset environments
    from .environments import list_preset_environments

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
        preset_config = presets[preset_name]
        env_name = preset_name
        env_url = preset_config.url
        endpoint_id = preset_config.endpoint_id

        console.print(f"[bold]Selected:[/bold] {preset_name}")
        console.print(f"[dim]API URL: {env_url}[/dim]")
        console.print(f"[dim]Endpoint ID: {endpoint_id}[/dim]\n")
    else:
        # Custom environment
        env_name = typer.prompt("Environment name")
        env_url = typer.prompt("API URL")
        endpoint_id = typer.prompt("Endpoint ID")
        console.print()

    # Prompt for credentials
    console.print("[bold]CloudBees Platform Credentials:[/bold]")
    pat = typer.prompt("CloudBees Platform PAT", hide_input=True)
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
        config_manager.add_environment(env_name, env_url, pat, endpoint_id)
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

    skip_github = typer.confirm("Configure GitHub now?", default=True)
    console.print()

    github_configured = False
    if skip_github:
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
                        "[dim]Skipping GitHub setup. Configure later with: mimic config github-token[/dim]\n"
                    )
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Error validating GitHub: {str(e)}\n")
            save_anyway = typer.confirm("Save GitHub token anyway?", default=False)
            if save_anyway:
                github_configured = True

        if github_configured:
            config_manager.set_github_pat(github_pat)
            console.print("[green]✓[/green] GitHub token saved\n")

            # Prompt for GitHub username
            console.print("[bold]GitHub Username (optional):[/bold]")
            console.print(
                "[dim]Username to invite as collaborator on created repositories[/dim]"
            )
            github_username = typer.prompt(
                "GitHub username", default="", show_default=False
            )
            if github_username.strip():
                config_manager.set_github_username(github_username.strip())
                console.print(
                    f"[green]✓[/green] Default GitHub username set to '{github_username.strip()}'\n"
                )
            else:
                console.print(
                    "[dim]Skipped. Configure later with: mimic config set github_username <username>[/dim]\n"
                )
    else:
        console.print(
            "[dim]Skipping GitHub setup. Configure later with: mimic config github-token[/dim]\n"
        )

    # Step 3: Success Summary
    console.print()
    console.print(
        Panel(
            "[bold green]✓ Setup Complete![/bold green]\n\n"
            "[bold]Configuration Summary:[/bold]\n"
            f"  • CloudBees Environment: [cyan]{env_name}[/cyan]\n"
            f"  • GitHub: [{'green' if github_configured else 'yellow'}]{'Configured' if github_configured else 'Not configured'}[/]\n\n"
            "[bold]Next Steps:[/bold]\n"
            f"  1. List available scenarios: [dim]mimic list[/dim]\n"
            f"  2. Run a scenario: [dim]mimic run <scenario-id>[/dim]\n"
            f"  3. Launch interactive TUI: [dim]mimic tui[/dim]\n\n"
            "[dim]Configuration stored in ~/.mimic/config.yaml\n"
            "Credentials stored securely in OS keyring[/dim]",
            title="Setup Complete",
            border_style="green",
        )
    )
    console.print()


# Environment management commands
@env_app.command("add")
def env_add(
    name: str = typer.Argument(
        ..., help="Environment name (preset: prod/preprod/demo or custom name)"
    ),
    url: str = typer.Option(
        None,
        "--url",
        help="CloudBees Platform API URL (required for custom environments)",
    ),
    endpoint_id: str = typer.Option(
        None,
        "--endpoint-id",
        help="CloudBees endpoint ID (required for custom environments)",
    ),
):
    """Add a new CloudBees Platform environment.

    Use preset environments (prod, preprod, demo) by just specifying the name,
    or add a custom environment by providing --url and --endpoint-id.

    Examples:
      mimic env add prod                                    # Add preset prod environment
      mimic env add custom --url https://api.example.com --endpoint-id abc-123
    """
    # Check if environment already exists
    environments = config_manager.list_environments()
    if name in environments:
        console.print(f"[red]Error:[/red] Environment '{name}' already exists")
        console.print(f"Use 'mimic env remove {name}' first to replace it")
        raise typer.Exit(1)

    # Check if this is a preset environment
    preset = get_preset_environment(name)

    if preset:
        # Using preset environment
        if url or endpoint_id:
            console.print(
                "[yellow]Note:[/yellow] Using preset configuration for '{name}'. Ignoring --url and --endpoint-id options."
            )

        url = preset.url
        endpoint_id = preset.endpoint_id

        console.print(f"\n[bold]Adding preset environment:[/bold] {name}")
        console.print(f"[dim]Description:[/dim] {preset.description}")
        console.print(f"[dim]API URL:[/dim] {url}")
        console.print(f"[dim]Endpoint ID:[/dim] {endpoint_id}")
    else:
        # Custom environment - require url and endpoint_id
        if not url or not endpoint_id:
            console.print(
                f"[red]Error:[/red] Custom environment '{name}' requires --url and --endpoint-id"
            )
            console.print("\n[bold]Available preset environments:[/bold]")
            for preset_name, preset_config in list_preset_environments().items():
                console.print(
                    f"  • [cyan]{preset_name}[/cyan] - {preset_config.description}"
                )
            console.print(
                "\n[dim]Or add custom environment with: mimic env add <name> --url <url> --endpoint-id <id>[/dim]"
            )
            raise typer.Exit(1)

        console.print(f"\n[bold]Adding custom environment:[/bold] {name}")
        console.print(f"[dim]API URL:[/dim] {url}")
        console.print(f"[dim]Endpoint ID:[/dim] {endpoint_id}")

    console.print()

    # Prompt for PAT securely
    pat = typer.prompt(
        "CloudBees Platform PAT",
        hide_input=True,
        confirmation_prompt=False,
    )

    # Validate credentials before saving
    console.print()
    console.print("[dim]Testing CloudBees API access...[/dim]")
    org_id = typer.prompt("Organization ID (for credential validation)")

    from .unify import UnifyAPIClient

    try:
        # Create temporary client to validate credentials
        with UnifyAPIClient(base_url=url, api_key=pat) as client:
            success, error = client.validate_credentials(org_id)

            if not success:
                console.print()
                console.print(
                    Panel(
                        f"[red]✗ Credential validation failed[/red]\n\n"
                        f"Error: {error}\n\n"
                        f"[dim]Please check your PAT and organization ID and try again.[/dim]",
                        title="Validation Failed",
                        border_style="red",
                    )
                )
                raise typer.Exit(1)

        console.print("[green]✓[/green] CloudBees API access verified")
    except typer.Exit:
        raise
    except Exception as e:
        console.print()
        console.print(
            Panel(
                f"[red]✗ Error validating credentials[/red]\n\n{str(e)}",
                title="Validation Error",
                border_style="red",
            )
        )
        raise typer.Exit(1) from e

    # Add environment
    try:
        config_manager.add_environment(name, url, pat, endpoint_id)
        console.print()
        console.print(
            Panel(
                f"[green]✓[/green] Environment '{name}' added successfully\n\n"
                f"[dim]• API URL: {url}\n"
                f"• Endpoint ID: {endpoint_id}\n"
                f"• PAT stored securely in OS keyring\n"
                f"• Set as current environment: {config_manager.get_current_environment() == name}[/dim]",
                title="Success",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Error adding environment:[/red] {e}")
        raise typer.Exit(1) from e


@env_app.command("list")
def env_list():
    """List all configured environments."""
    environments = config_manager.list_environments()
    current_env = config_manager.get_current_environment()

    if not environments:
        console.print(
            Panel(
                "[yellow]No environments configured[/yellow]\n\n"
                "Add a preset environment:\n"
                "[dim]mimic env add (prod|preprod|demo)[/dim]\n\n"
                "Or add a custom environment:\n"
                "[dim]mimic env add <name> --url <api-url> --endpoint-id <id>[/dim]",
                title="Environments",
                border_style="yellow",
            )
        )
        return

    # Create table
    table = Table(title="Configured Environments", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("API URL", style="white", no_wrap=False)
    table.add_column("Endpoint ID", style="dim", overflow="fold")
    table.add_column("Current", justify="center")

    for name, env_config in environments.items():
        is_current = "✓" if name == current_env else ""
        table.add_row(
            name,
            env_config.get("url", ""),
            env_config.get("endpoint_id", ""),
            f"[green]{is_current}[/green]" if is_current else "",
        )

    console.print()
    console.print(table)
    console.print()

    if current_env:
        console.print(f"[dim]Current environment: [bold]{current_env}[/bold][/dim]")
    console.print()


@env_app.command("select")
def env_select(
    name: str = typer.Argument(..., help="Environment name to select"),
):
    """Select the current environment."""
    environments = config_manager.list_environments()

    if name not in environments:
        console.print(f"[red]Error:[/red] Environment '{name}' not found")
        console.print("\nAvailable environments:")
        for env_name in environments.keys():
            console.print(f"  • {env_name}")
        raise typer.Exit(1)

    config_manager.set_current_environment(name)
    env_url = config_manager.get_environment_url(name)

    console.print(
        Panel(
            f"[green]✓[/green] Current environment set to: [bold]{name}[/bold]\n\n"
            f"[dim]API URL: {env_url}[/dim]",
            title="Environment Selected",
            border_style="green",
        )
    )


@env_app.command("remove")
def env_remove(
    name: str = typer.Argument(..., help="Environment name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Remove an environment."""
    environments = config_manager.list_environments()

    if name not in environments:
        console.print(f"[red]Error:[/red] Environment '{name}' not found")
        raise typer.Exit(1)

    # Confirm deletion unless --force is used
    if not force:
        env_url = config_manager.get_environment_url(name)
        console.print(
            f"\n[yellow]Warning:[/yellow] This will remove environment '[bold]{name}[/bold]'"
        )
        console.print(f"[dim]API URL: {env_url}[/dim]")
        console.print("[dim]The PAT will be deleted from OS keyring[/dim]\n")

        confirm = typer.confirm("Are you sure?", default=False)
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)

    # Remove environment
    try:
        was_current = config_manager.get_current_environment() == name
        config_manager.remove_environment(name)

        message = f"[green]✓[/green] Environment '[bold]{name}[/bold]' removed"
        if was_current:
            new_current = config_manager.get_current_environment()
            if new_current:
                message += f"\n\n[dim]Current environment set to: {new_current}[/dim]"
            else:
                message += "\n\n[yellow]No current environment set[/yellow]"

        console.print(Panel(message, title="Environment Removed", border_style="green"))
    except Exception as e:
        console.print(f"[red]Error removing environment:[/red] {e}")
        raise typer.Exit(1) from e


# Config management commands
@config_app.command("show")
def config_show():
    """Show current configuration."""
    config = config_manager.load_config()

    console.print()
    console.print("[bold]Current Configuration[/bold]")
    console.print()

    # GitHub settings
    console.print("[cyan]GitHub:[/cyan]")
    github_username = config_manager.get_github_username()
    has_github_token = config_manager.get_github_pat() is not None
    console.print(
        f"  Default username: [yellow]{github_username or 'Not set'}[/yellow]"
    )
    console.print(
        f"  Token configured: [{'green' if has_github_token else 'red'}]{'Yes' if has_github_token else 'No'}[/]"
    )
    console.print()

    # General settings
    console.print("[cyan]Settings:[/cyan]")
    settings = config.get("settings", {})
    console.print(
        f"  Default expiration days: [yellow]{settings.get('default_expiration_days', 7)}[/yellow]"
    )
    console.print(
        f"  Auto cleanup prompt: [yellow]{settings.get('auto_cleanup_prompt', True)}[/yellow]"
    )
    console.print()

    # Environment summary
    current_env = config.get("current_environment")
    env_count = len(config.get("environments", {}))
    console.print("[cyan]Environments:[/cyan]")
    console.print(f"  Total configured: [yellow]{env_count}[/yellow]")
    console.print(f"  Current: [yellow]{current_env or 'None'}[/yellow]")
    console.print()

    console.print("[dim]Use 'mimic config set <key> <value>' to change settings[/dim]")
    console.print("[dim]Use 'mimic env list' to see configured environments[/dim]")
    console.print()


@config_app.command("set")
def config_set(
    key: str = typer.Argument(
        ...,
        help="Setting key (e.g., 'default_expiration_days', 'auto_cleanup_prompt', 'github_username')",
    ),
    value: str = typer.Argument(..., help="Setting value"),
):
    """Set a configuration value."""
    # Map of valid settings and their types
    valid_settings = {
        "default_expiration_days": int,
        "auto_cleanup_prompt": bool,
        "github_username": str,
    }

    if key not in valid_settings:
        console.print(f"[red]Error:[/red] Unknown setting '{key}'")
        console.print("\n[bold]Valid settings:[/bold]")
        for setting_key in valid_settings:
            console.print(f"  • {setting_key}")
        raise typer.Exit(1)

    # Convert value to appropriate type
    try:
        expected_type = valid_settings[key]
        if expected_type is bool:
            parsed_value = value.lower() in ("true", "yes", "1", "on")
        elif expected_type is int:
            parsed_value = int(value)
        else:
            parsed_value = value
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid value for {key}: {e}")
        raise typer.Exit(1) from e

    # Special handling for github_username
    if key == "github_username":
        # github_username is always a string based on valid_settings
        assert isinstance(parsed_value, str)
        config_manager.set_github_username(parsed_value)
    else:
        # General settings
        config_manager.set_setting(key, parsed_value)

    console.print(
        Panel(
            f"[green]✓[/green] Setting updated\n\n[dim]{key} = {parsed_value}[/dim]",
            title="Configuration",
            border_style="green",
        )
    )


@config_app.command("github-token")
def config_github_token():
    """Set GitHub Personal Access Token (stored securely in OS keyring)."""
    console.print()
    console.print("[bold]GitHub Personal Access Token[/bold]")
    console.print("[dim]This will be stored securely in your OS keyring[/dim]")
    console.print()

    token = typer.prompt("GitHub PAT", hide_input=True, confirmation_prompt=True)

    config_manager.set_github_pat(token)

    console.print()
    console.print(
        Panel(
            "[green]✓[/green] GitHub token stored securely in OS keyring",
            title="Success",
            border_style="green",
        )
    )


# Cleanup commands
@cleanup_app.command("list")
def cleanup_list(
    show_expired_only: bool = typer.Option(
        False, "--expired-only", help="Show only expired sessions"
    ),
):
    """List all tracked sessions."""
    from datetime import datetime

    from .state_tracker import StateTracker

    try:
        state_tracker = StateTracker()
        sessions = state_tracker.list_sessions(include_expired=True)

        if show_expired_only:
            now = datetime.now()
            sessions = [
                s for s in sessions if s.expires_at is not None and s.expires_at <= now
            ]

        if not sessions:
            message = (
                "No expired sessions found"
                if show_expired_only
                else "No sessions found"
            )
            console.print(
                Panel(
                    f"[yellow]{message}[/yellow]\n\n"
                    "Sessions are created when you run scenarios with: [dim]mimic run <scenario-id>[/dim]",
                    title="Sessions",
                    border_style="yellow",
                )
            )
            return

        # Create table
        table = Table(
            title=f"{'Expired ' if show_expired_only else ''}Tracked Sessions",
            show_header=True,
            expand=True,
        )
        table.add_column("Session ID", style="cyan", no_wrap=True)
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
            resource_count = len(session.resources)

            # Format dates
            created_str = session.created_at.strftime("%Y-%m-%d %H:%M")
            expires_str = (
                "Never"
                if session.expires_at is None
                else session.expires_at.strftime("%Y-%m-%d %H:%M")
            )

            table.add_row(
                session.session_id,
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
                "[dim]Clean up expired sessions with:[/dim] mimic cleanup expired"
            )
            console.print()

    except Exception as e:
        console.print(f"[red]Error listing sessions:[/red] {e}")
        raise typer.Exit(1) from e


# Alias for cleanup list command
cleanup_app.command("ls")(cleanup_list)


@cleanup_app.command("run")
def cleanup_run(
    session_id: str = typer.Argument(..., help="Session ID to clean up"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be cleaned without doing it"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Clean up resources for a specific session."""
    import asyncio

    from .cleanup_manager import CleanupManager
    from .state_tracker import StateTracker

    try:
        state_tracker = StateTracker()
        session = state_tracker.get_session(session_id)

        if not session:
            console.print(f"[red]Error:[/red] Session '{session_id}' not found")
            console.print("\n[dim]List sessions with:[/dim] mimic cleanup list")
            raise typer.Exit(1)

        # Show session details
        console.print()
        console.print(
            Panel(
                f"[bold]Session:[/bold] {session.session_id}\n"
                f"[bold]Scenario:[/bold] {session.scenario_id}\n"
                f"[bold]Environment:[/bold] {session.environment}\n"
                f"[bold]Created:[/bold] {session.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"[bold]Expires:[/bold] {'Never' if session.expires_at is None else session.expires_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"[bold]Resources:[/bold] {len(session.resources)}",
                title="Session Details",
                border_style="cyan",
            )
        )
        console.print()

        # Show resources
        if session.resources:
            console.print("[bold]Resources to clean up:[/bold]")
            for resource in session.resources:
                console.print(f"  • {resource.type}: {resource.name}")
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
    """Clean up all expired sessions."""
    import asyncio

    from .cleanup_manager import CleanupManager

    try:
        cleanup_manager = CleanupManager(console=console)

        # Check for expired sessions
        expired_sessions = cleanup_manager.check_expired_sessions()

        if not expired_sessions:
            console.print(
                Panel(
                    "[green]No expired sessions found[/green]\n\n"
                    "All tracked sessions are still active.",
                    title="Cleanup",
                    border_style="green",
                )
            )
            return

        # Show expired sessions
        console.print()
        console.print(
            f"[yellow]Found {len(expired_sessions)} expired session(s):[/yellow]\n"
        )

        for session in expired_sessions:
            console.print(
                f"  • {session.session_id} - {session.scenario_id} ({len(session.resources)} resources)"
            )

        console.print()

        # Confirm unless --force or --dry-run
        if not force and not dry_run:
            confirm = typer.confirm(
                f"Clean up {len(expired_sessions)} expired session(s)?", default=True
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
                    f"Sessions found: {results['total_sessions']}\n"
                    f"Would clean: {results['cleaned_sessions']} sessions\n"
                    f"Errors: {results['failed_sessions']} sessions",
                    title="Cleanup Summary (Dry Run)",
                    border_style="yellow",
                )
            )
        else:
            success = results["failed_sessions"] == 0
            console.print(
                Panel(
                    f"[{'green' if success else 'yellow'}]Cleanup {'completed successfully' if success else 'completed with errors'}[/]\n\n"
                    f"Sessions cleaned: {results['cleaned_sessions']}/{results['total_sessions']}\n"
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


# Scenario pack commands
@scenario_pack_app.command("add")
def pack_add(
    name: str = typer.Argument(..., help="Pack name (used as directory name)"),
    url: str = typer.Argument(..., help="Git URL (supports HTTPS and SSH)"),
    branch: str = typer.Option("main", "--branch", "-b", help="Git branch to use"),
):
    """Add a scenario pack from a git repository."""
    from .scenario_pack_manager import ScenarioPackManager

    try:
        # Check if pack already exists in config
        existing_pack = config_manager.get_scenario_pack(name)
        if existing_pack:
            console.print(
                f"[red]Error:[/red] Pack '{name}' already exists in configuration"
            )
            console.print(
                f"Use 'mimic scenario-pack remove {name}' first to replace it"
            )
            raise typer.Exit(1)

        # Add pack to config
        config_manager.add_scenario_pack(name, url, branch, enabled=True)

        # Clone the pack
        console.print(f"\n[bold]Adding scenario pack:[/bold] {name}")
        console.print(f"[dim]Git URL:[/dim] {url}")
        console.print(f"[dim]Branch:[/dim] {branch}")
        console.print()

        pack_manager = ScenarioPackManager(config_manager.packs_dir)
        pack_path = pack_manager.clone_pack(name, url, branch)

        console.print()
        console.print(
            Panel(
                f"[green]✓[/green] Scenario pack '{name}' added successfully\n\n"
                f"[dim]• Cloned to: {pack_path}\n"
                f"• Enabled: Yes[/dim]",
                title="Success",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"\n[red]Error adding scenario pack:[/red] {e}")
        raise typer.Exit(1) from e


@scenario_pack_app.command("list")
def pack_list():
    """List all configured scenario packs."""
    from .scenario_pack_manager import ScenarioPackManager

    packs = config_manager.list_scenario_packs()
    pack_manager = ScenarioPackManager(config_manager.packs_dir)

    if not packs:
        console.print(
            Panel(
                "[yellow]No scenario packs configured[/yellow]\n\n"
                "Add the official pack:\n"
                "[dim]mimic scenario-pack add official https://github.com/cb-demos/mimic-scenarios[/dim]\n\n"
                "Or add a custom pack:\n"
                "[dim]mimic scenario-pack add <name> <git-url>[/dim]",
                title="Scenario Packs",
                border_style="yellow",
            )
        )
        return

    # Create table
    table = Table(title="Configured Scenario Packs", show_header=True, expand=True)
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="white", overflow="fold")
    table.add_column("Branch", style="dim")
    table.add_column("Installed", justify="center")
    table.add_column("Enabled", justify="center")

    for name, pack_config in packs.items():
        is_installed = pack_manager.get_pack_path(name) is not None
        is_enabled = pack_config.get("enabled", True)

        table.add_row(
            name,
            pack_config.get("url", ""),
            pack_config.get("branch", "main"),
            "[green]✓[/green]" if is_installed else "[red]✗[/red]",
            "[green]✓[/green]" if is_enabled else "[dim]✗[/dim]",
        )

    console.print()
    console.print(table)
    console.print()

    console.print(
        "[dim]Update packs with:[/dim] mimic scenario-pack update [pack-name]"
    )
    console.print()


# Alias for pack list
scenario_pack_app.command("ls")(pack_list)


@scenario_pack_app.command("update")
def pack_update(
    name: str = typer.Argument(
        None, help="Pack name to update (updates all if not specified)"
    ),
):
    """Update scenario pack(s) by pulling latest changes."""
    from .scenario_pack_manager import ScenarioPackManager

    try:
        pack_manager = ScenarioPackManager(config_manager.packs_dir)
        packs = config_manager.list_scenario_packs()

        if not packs:
            console.print("[yellow]No scenario packs configured[/yellow]")
            return

        # Determine which packs to update
        if name:
            if name not in packs:
                console.print(
                    f"[red]Error:[/red] Pack '{name}' not found in configuration"
                )
                raise typer.Exit(1)
            packs_to_update = {name: packs[name]}
        else:
            packs_to_update = packs

        console.print()
        console.print(
            f"[bold]Updating {len(packs_to_update)} scenario pack(s)...[/bold]"
        )
        console.print()

        success_count = 0
        for pack_name, pack_config in packs_to_update.items():
            try:
                # Check if pack is installed
                if not pack_manager.get_pack_path(pack_name):
                    console.print(
                        f"[yellow]✗[/yellow] {pack_name}: Not installed, cloning..."
                    )
                    url = pack_config.get("url")
                    if not url:
                        console.print(
                            f"[red]✗[/red] {pack_name}: Missing URL in configuration"
                        )
                        continue
                    branch = pack_config.get("branch", "main")
                    pack_manager.clone_pack(pack_name, url, branch)
                    console.print(f"[green]✓[/green] {pack_name}: Cloned successfully")
                else:
                    pack_manager.update_pack(pack_name)
                    console.print(f"[green]✓[/green] {pack_name}: Updated successfully")

                success_count += 1

            except Exception as e:
                console.print(f"[red]✗[/red] {pack_name}: {e}")

        console.print()
        console.print(
            Panel(
                f"Updated {success_count}/{len(packs_to_update)} pack(s) successfully",
                title="Update Complete",
                border_style="green"
                if success_count == len(packs_to_update)
                else "yellow",
            )
        )

    except Exception as e:
        console.print(f"\n[red]Error updating scenario pack(s):[/red] {e}")
        raise typer.Exit(1) from e


@scenario_pack_app.command("remove")
def pack_remove(
    name: str = typer.Argument(..., help="Pack name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    keep_files: bool = typer.Option(
        False, "--keep-files", help="Remove from config but keep cloned files"
    ),
):
    """Remove a scenario pack."""
    from .scenario_pack_manager import ScenarioPackManager

    try:
        # Check if pack exists
        pack_config = config_manager.get_scenario_pack(name)
        if not pack_config:
            console.print(f"[red]Error:[/red] Pack '{name}' not found in configuration")
            raise typer.Exit(1)

        # Confirm deletion unless --force is used
        if not force:
            console.print(
                f"\n[yellow]Warning:[/yellow] This will remove scenario pack '[bold]{name}[/bold]'"
            )
            console.print(f"[dim]URL: {pack_config.get('url')}[/dim]")
            if not keep_files:
                console.print("[dim]Cloned files will be deleted[/dim]")
            console.print()

            confirm = typer.confirm("Are you sure?", default=False)
            if not confirm:
                console.print("[dim]Cancelled[/dim]")
                raise typer.Exit(0)

        # Remove from config
        config_manager.remove_scenario_pack(name)

        # Remove cloned files unless --keep-files
        if not keep_files:
            pack_manager = ScenarioPackManager(config_manager.packs_dir)
            if pack_manager.get_pack_path(name):
                pack_manager.remove_pack(name)

        console.print(
            Panel(
                f"[green]✓[/green] Scenario pack '[bold]{name}[/bold]' removed",
                title="Pack Removed",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"\n[red]Error removing scenario pack:[/red] {e}")
        raise typer.Exit(1) from e


# Alias for pack remove
scenario_pack_app.command("rm")(pack_remove)


@scenario_pack_app.command("enable")
def pack_enable(name: str = typer.Argument(..., help="Pack name to enable")):
    """Enable a scenario pack."""
    try:
        config_manager.set_scenario_pack_enabled(name, True)
        console.print(
            Panel(
                f"[green]✓[/green] Scenario pack '[bold]{name}[/bold]' enabled",
                title="Pack Enabled",
                border_style="green",
            )
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@scenario_pack_app.command("disable")
def pack_disable(name: str = typer.Argument(..., help="Pack name to disable")):
    """Disable a scenario pack."""
    try:
        config_manager.set_scenario_pack_enabled(name, False)
        console.print(
            Panel(
                f"[yellow]Scenario pack '[bold]{name}[/bold]' disabled[/yellow]\n\n"
                "[dim]Scenarios from this pack will not be loaded[/dim]",
                title="Pack Disabled",
                border_style="yellow",
            )
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
