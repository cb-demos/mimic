"""Interactive TUI (Text User Interface) for Mimic."""

from datetime import datetime
from typing import Any

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from .cleanup_manager import CleanupManager
from .config_manager import ConfigManager
from .scenarios import initialize_scenarios_from_config
from .state_tracker import StateTracker


class WelcomeScreen(Screen):
    """Main welcome screen with navigation."""

    BINDINGS = [
        Binding("1", "push_screen('environments')", "Environments", show=False),
        Binding("2", "push_screen('scenarios')", "Scenarios", show=False),
        Binding("3", "push_screen('cleanup')", "Cleanup", show=False),
        Binding("e", "push_screen('environments')", "Environments"),
        Binding("s", "push_screen('scenarios')", "Scenarios"),
        Binding("c", "push_screen('cleanup')", "Cleanup"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_manager = ConfigManager()
        self.state_tracker = StateTracker()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static(
                "[bold cyan]Mimic - CloudBees Platform Scenario Tool[/bold cyan]\n\n"
                "Welcome to the Mimic TUI! Use the keybindings shown at the bottom to navigate.\n",
                id="welcome-text",
            ),
            Static("", id="stats-panel"),
            id="welcome-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.update_stats()
        # Check for expired sessions
        self.check_expired_sessions()
        # Check credentials
        self.check_credentials()

    def update_stats(self) -> None:
        """Update statistics panel."""
        stats_text = self._get_stats_text()
        stats_panel = self.query_one("#stats-panel", Static)
        stats_panel.update(stats_text)

    def check_expired_sessions(self) -> None:
        """Check for expired sessions and prompt for cleanup."""
        cleanup_manager = CleanupManager(self.config_manager, self.state_tracker)
        expired_sessions = cleanup_manager.check_expired_sessions()

        if expired_sessions:
            # Show notification in stats panel - append warning to stats
            stats_panel = self.query_one("#stats-panel", Static)
            # Re-generate stats with warning
            self.update_stats()
            # Get current text and append warning
            warning = f"\n\n[yellow]⚠️  {len(expired_sessions)} expired session(s) found![/yellow]\n[dim]Press 'c' to open Cleanup Manager[/dim]"
            # Update with stats + warning
            current_stats = self._get_stats_text()
            stats_panel.update(current_stats + warning)

    def check_credentials(self) -> None:
        """Check credentials validity (non-blocking)."""
        import asyncio

        from .gh import GitHubClient

        # Get current environment
        current_env = self.config_manager.get_current_environment()
        if not current_env:
            return  # No environment configured, skip validation

        # Check GitHub credentials (doesn't require org_id)
        github_pat = self.config_manager.get_github_pat()
        if not github_pat:
            return  # No GitHub PAT configured, skip validation

        github_client = GitHubClient(github_pat)
        try:
            success, error = asyncio.run(github_client.validate_credentials())
            if not success:
                # Show warning in stats panel
                stats_panel = self.query_one("#stats-panel", Static)
                current_stats = self._get_stats_text()
                warning = "\n\n[red]⚠️  GitHub credentials invalid![/red]\n[dim]Update with: mimic config github-token[/dim]"
                stats_panel.update(current_stats + warning)
        except Exception:
            # Silently fail - don't block TUI startup
            pass

    def _get_stats_text(self) -> str:
        """Get stats text without updating the panel."""
        # Get environment info
        current_env = self.config_manager.get_current_environment()
        env_count = len(self.config_manager.list_environments())

        # Get scenario info
        try:
            scenario_manager = initialize_scenarios_from_config()
            scenario_count = len(scenario_manager.list_scenarios())
        except Exception:
            scenario_count = 0

        # Get session info
        all_sessions = self.state_tracker.list_sessions(include_expired=True)
        expired_sessions = self.state_tracker.list_expired_sessions()
        active_count = len(all_sessions) - len(expired_sessions)

        return (
            "[bold]Quick Stats:[/bold]\n\n"
            f"• Current Environment: [cyan]{current_env or 'None'}[/cyan]\n"
            f"• Configured Environments: [cyan]{env_count}[/cyan]\n"
            f"• Available Scenarios: [cyan]{scenario_count}[/cyan]\n"
            f"• Active Sessions: [green]{active_count}[/green]\n"
            f"• Expired Sessions: [red]{len(expired_sessions)}[/red]"
        )

    def action_push_screen(self, screen_name: str) -> None:
        """Push a screen by name."""
        if screen_name == "environments":
            self.app.push_screen(EnvironmentManagerScreen())
        elif screen_name == "scenarios":
            self.app.push_screen(ScenarioBrowserScreen())
        elif screen_name == "cleanup":
            self.app.push_screen(CleanupManagerScreen())


class EnvironmentManagerScreen(Screen):
    """Screen for managing CloudBees environments."""

    BINDINGS = [
        Binding("a", "add_environment", "Add"),
        Binding("enter", "select_environment", "Select", show=False),
        Binding("s", "select_environment", "Select"),
        Binding("d", "delete_environment", "Delete"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_manager = ConfigManager()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static("[bold cyan]Environment Manager[/bold cyan]\n", id="env-title"),
            DataTable(id="env-table"),
            Horizontal(
                Button("Add Environment", id="btn-add-env", variant="primary"),
                Button("Select", id="btn-select-env", variant="success"),
                Button("Delete", id="btn-delete-env", variant="error"),
                Button("Back", id="btn-back", variant="default"),
                id="env-buttons",
            ),
            id="env-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.refresh_environments()

    def refresh_environments(self) -> None:
        """Refresh the environments table."""
        table = self.query_one("#env-table", DataTable)
        table.clear(columns=True)

        # Add columns
        table.add_column("Name", key="name")
        table.add_column("API URL", key="url")
        table.add_column("Endpoint ID", key="endpoint")
        table.add_column("Current", key="current")

        # Add rows
        environments = self.config_manager.list_environments()
        current_env = self.config_manager.get_current_environment()

        for name, config in environments.items():
            is_current = "✓" if name == current_env else ""
            table.add_row(
                name,
                config.get("url", ""),
                config.get("endpoint_id", "")[:20] + "...",
                is_current,
                key=name,
            )

        if table.row_count > 0:
            table.cursor_type = "row"

    @on(Button.Pressed, "#btn-add-env")
    def action_add_environment(self) -> None:
        """Open add environment dialog."""
        self.app.push_screen(AddEnvironmentDialog())

    @on(Button.Pressed, "#btn-select-env")
    def action_select_environment(self) -> None:
        """Select highlighted environment."""
        table = self.query_one("#env-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)
            env_name = str(row_key[0])
            self.config_manager.set_current_environment(env_name)
            self.app.notify(
                f"Environment '{env_name}' selected", severity="information"
            )
            self.refresh_environments()

    @on(Button.Pressed, "#btn-delete-env")
    def action_delete_environment(self) -> None:
        """Delete highlighted environment."""
        table = self.query_one("#env-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)
            env_name = str(row_key[0])
            self.app.push_screen(
                ConfirmDialog(
                    f"Delete environment '{env_name}'?",
                    "handle_delete_environment",
                    env_name,
                )
            )

    @on(Button.Pressed, "#btn-back")
    def action_back(self) -> None:
        """Go back to main screen."""
        self.app.pop_screen()

    def handle_add_environment(self, result: dict[str, str] | None) -> None:
        """Handle add environment dialog result."""
        if result:
            try:
                self.config_manager.add_environment(
                    result["name"],
                    result["url"],
                    result["pat"],
                    result["endpoint_id"],
                )
                self.app.notify(
                    f"Environment '{result['name']}' added successfully",
                    severity="information",
                )
                self.refresh_environments()
            except Exception as e:
                self.app.notify(f"Error adding environment: {e}", severity="error")

    def handle_delete_environment(self, env_name: str, confirmed: bool) -> None:
        """Handle delete environment confirmation."""
        if confirmed:
            try:
                self.config_manager.remove_environment(env_name)
                self.app.notify(
                    f"Environment '{env_name}' deleted", severity="information"
                )
                self.refresh_environments()
            except Exception as e:
                self.app.notify(f"Error deleting environment: {e}", severity="error")


class ScenarioBrowserScreen(Screen):
    """Screen for browsing and running scenarios."""

    BINDINGS = [
        Binding("enter", "run_scenario", "Run", show=False),
        Binding("r", "run_scenario", "Run"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scenario_manager = initialize_scenarios_from_config()
        self.config_manager = ConfigManager()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static("[bold cyan]Scenario Browser[/bold cyan]\n", id="scenario-title"),
            DataTable(id="scenario-table"),
            Horizontal(
                Button("Run Scenario", id="btn-run-scenario", variant="primary"),
                Button("Back", id="btn-back", variant="default"),
                id="scenario-buttons",
            ),
            id="scenario-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.refresh_scenarios()

    def refresh_scenarios(self) -> None:
        """Refresh the scenarios table."""
        table = self.query_one("#scenario-table", DataTable)
        table.clear(columns=True)

        # Add columns
        table.add_column("ID", key="id")
        table.add_column("Name", key="name")
        table.add_column("Summary", key="summary")
        table.add_column("Parameters", key="params")

        # Add rows
        try:
            scenarios = self.scenario_manager.list_scenarios()
            for scenario in scenarios:
                param_count = len(scenario.get("parameters", {}))
                param_text = f"{param_count} params" if param_count > 0 else "none"

                table.add_row(
                    scenario["id"],
                    scenario["name"],
                    scenario["summary"][:50] + "..."
                    if len(scenario["summary"]) > 50
                    else scenario["summary"],
                    param_text,
                    key=scenario["id"],
                )

            if table.row_count > 0:
                table.cursor_type = "row"
        except Exception as e:
            self.app.notify(f"Error loading scenarios: {e}", severity="error")

    @on(Button.Pressed, "#btn-run-scenario")
    def action_run_scenario(self) -> None:
        """Run the highlighted scenario."""
        table = self.query_one("#scenario-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)
            scenario_id = str(row_key[0])

            # Check if environment is configured
            current_env = self.config_manager.get_current_environment()
            if not current_env:
                self.app.notify(
                    "No environment configured. Please add an environment first.",
                    severity="error",
                )
                return

            # Load scenario and check for parameters
            scenario = self.scenario_manager.get_scenario(scenario_id)
            if not scenario:
                self.app.notify(f"Scenario '{scenario_id}' not found", severity="error")
                return

            # Push parameter collection screen
            self.app.push_screen(ScenarioParametersScreen(scenario))

    @on(Button.Pressed, "#btn-back")
    def action_back(self) -> None:
        """Go back to main screen."""
        self.app.pop_screen()

    def handle_run_scenario(
        self, scenario: Any, parameters: dict[str, Any] | None
    ) -> None:
        """Handle scenario execution after parameter collection."""
        if parameters is not None:
            # Check if preview mode is enabled
            preview_mode = parameters.get("_preview_mode", False)

            # Remove TUI-only parameters before passing to execution
            exec_params = {k: v for k, v in parameters.items() if k != "_preview_mode"}

            if preview_mode:
                # Push preview screen (preview screen will also need clean params)
                self.app.push_screen(ScenarioPreviewScreen(scenario, exec_params))
            else:
                # Push execution screen directly
                self.app.push_screen(ScenarioExecutionScreen(scenario, exec_params))


class ScenarioParametersScreen(Screen):
    """Screen for collecting scenario parameters."""

    BINDINGS = [
        Binding("escape", "cancel_parameters", "Cancel"),
    ]

    def __init__(self, scenario: Any, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scenario = scenario
        self.parameter_inputs: dict[str, Input | Checkbox | Select] = {}
        self.config_manager = ConfigManager()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static(
                f"Run Scenario: {self.scenario.name}",
                id="param-title",
            ),
            VerticalScroll(id="param-inputs"),
            Horizontal(
                Button("Run", id="btn-run", variant="primary"),
                Button("Cancel", id="btn-cancel", variant="default"),
                id="param-buttons",
            ),
            id="param-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        scroll = self.query_one("#param-inputs", VerticalScroll)

        # Get current environment for org caching
        current_env = self.config_manager.get_current_environment()

        # Add common inputs - Organization ID
        scroll.mount(Label("Organization ID:"))

        # Show cached orgs as Select with custom input option
        cached_orgs = self.config_manager.get_cached_orgs_for_env(current_env)
        if cached_orgs:
            # Build select options with org names
            org_options = [
                (f"{name} ({org_id[:8]}...)", org_id)
                for org_id, name in cached_orgs.items()
            ]

            org_id_select = Select(
                options=org_options, prompt="Select from recent", id="select-org-id"
            )
            scroll.mount(org_id_select)
            scroll.mount(Label("[dim]Or enter custom:[/dim]"))
            org_id_input = Input(
                placeholder="Enter new organization ID", id="input-org-id"
            )
            scroll.mount(org_id_input)
            # Store both widgets - Input takes precedence in handle_run
            self.parameter_inputs["_org_id_select"] = org_id_select
            self.parameter_inputs["_org_id"] = org_id_input
        else:
            org_id_input = Input(
                placeholder="CloudBees Organization ID", id="input-org-id"
            )
            scroll.mount(org_id_input)
            self.parameter_inputs["_org_id"] = org_id_input

        scroll.mount(Label("Expiration Days:"))

        # Get default expiration from config or recent values
        recent_expirations = self.config_manager.get_recent_values("expiration_days")
        default_expiration = str(
            self.config_manager.get_setting("default_expiration_days", 7)
        )

        if recent_expirations:
            # Build select options from recent values
            exp_options = [(days, days) for days in recent_expirations[:5]]

            expiration_select = Select(
                options=exp_options,
                prompt="Select from recent",
                id="select-expiration-days",
            )
            scroll.mount(expiration_select)
            scroll.mount(Label("[dim]Or enter custom:[/dim]"))
            expiration_input = Input(
                placeholder="Enter custom days",
                value=default_expiration,
                id="input-expiration-days",
            )
            scroll.mount(expiration_input)
            # Store both widgets - Input takes precedence
            self.parameter_inputs["_expiration_days_select"] = expiration_select
            self.parameter_inputs["_expiration_days"] = expiration_input
        else:
            expiration_input = Input(
                placeholder=default_expiration,
                value=default_expiration,
                id="input-expiration-days",
            )
            scroll.mount(expiration_input)
            self.parameter_inputs["_expiration_days"] = expiration_input

        scroll.mount(Label(""))  # Spacer
        preview_checkbox = Checkbox("Preview before running", id="checkbox-preview")
        scroll.mount(preview_checkbox)
        self.parameter_inputs["_preview_mode"] = preview_checkbox

        # Add scenario-specific parameters
        if self.scenario.parameter_schema:
            scroll.mount(Label("\n[bold]Scenario Parameters:[/bold]"))

            for prop_name, prop in self.scenario.parameter_schema.properties.items():
                is_required = prop_name in self.scenario.parameter_schema.required

                # Special handling for boolean parameters
                if prop.type == "boolean":
                    # Use Checkbox for boolean parameters
                    default_bool = prop.default if prop.default is not None else False
                    # Convert string defaults to boolean if needed
                    if isinstance(default_bool, str):
                        default_bool = default_bool.lower() in (
                            "true",
                            "yes",
                            "1",
                            "on",
                        )

                    checkbox_label = f"{prop_name}"
                    if prop.description:
                        checkbox_label += f" ({prop.description})"
                    if is_required:
                        checkbox_label += " *"

                    param_checkbox = Checkbox(
                        checkbox_label,
                        value=default_bool,
                        id=f"checkbox-param-{prop_name}",
                    )
                    scroll.mount(param_checkbox)
                    self.parameter_inputs[prop_name] = param_checkbox
                    continue

                # For non-boolean parameters, show a label
                label_text = f"{prop_name}"
                if prop.description:
                    label_text += f" ({prop.description})"
                if is_required:
                    label_text += " *"

                scroll.mount(Label(label_text))

                # Only cache specific parameters that are reusable across runs
                # Most parameters are unique per run (project names, repo names, etc.)
                cache_whitelist = {"target_org"}  # Add more here as needed

                # Check for recent values for whitelisted parameters only
                if prop_name == "target_org":
                    # Special handling for target_org (GitHub org)
                    recent_values = self.config_manager.get_recent_values("github_orgs")
                elif prop_name in cache_whitelist:
                    # Other whitelisted parameters
                    recent_values = self.config_manager.get_recent_values(
                        f"param_{prop_name}"
                    )
                else:
                    # Don't show recent values for non-whitelisted parameters
                    recent_values = []

                # Determine default value for Input
                if prop.default:
                    default_value = str(prop.default)
                else:
                    default_value = ""

                # Show Select with custom Input if we have recent values
                if recent_values:
                    # Build select options from recent values
                    param_options = [(val, val) for val in recent_values[:5]]

                    param_select = Select(
                        options=param_options,
                        prompt="Select from recent",
                        id=f"select-param-{prop_name}",
                    )
                    scroll.mount(param_select)
                    scroll.mount(Label("[dim]Or enter custom:[/dim]"))

                    placeholder = prop.placeholder or prop.default or ""
                    param_input = Input(
                        placeholder=f"Enter new {prop_name}",
                        value=default_value,
                        id=f"input-param-{prop_name}",
                    )
                    scroll.mount(param_input)
                    # Store both widgets - Input takes precedence
                    self.parameter_inputs[f"{prop_name}_select"] = param_select
                    self.parameter_inputs[prop_name] = param_input
                else:
                    placeholder = prop.placeholder or prop.default or ""
                    param_input = Input(
                        placeholder=str(placeholder),
                        value=default_value,
                        id=f"input-param-{prop_name}",
                    )
                    scroll.mount(param_input)
                    self.parameter_inputs[prop_name] = param_input

    @on(Button.Pressed, "#btn-run")
    def handle_run(self) -> None:
        """Handle run button press."""
        # Collect all parameter values
        parameters = {}

        # First pass: collect all non-select widget values
        for param_name, widget in self.parameter_inputs.items():
            # Skip _select widgets, we'll handle them separately
            if param_name.endswith("_select"):
                continue

            if isinstance(widget, Checkbox):
                parameters[param_name] = widget.value
            elif isinstance(widget, Input):
                if widget.value:
                    # Input value provided, use it
                    parameters[param_name] = widget.value
                else:
                    # No input value, check if there's a corresponding Select
                    select_key = f"{param_name}_select"
                    if select_key in self.parameter_inputs:
                        select_widget = self.parameter_inputs[select_key]
                        if (
                            isinstance(select_widget, Select)
                            and select_widget.value != Select.BLANK
                        ):
                            # Use Select value as fallback
                            parameters[param_name] = select_widget.value
            elif isinstance(widget, Select):
                # Standalone Select (no corresponding Input)
                if widget.value != Select.BLANK:
                    parameters[param_name] = widget.value

        # Validate required fields
        if self.scenario.parameter_schema:
            for prop_name in self.scenario.parameter_schema.required:
                # Check if parameter exists - for booleans, False is a valid value
                if prop_name not in parameters:
                    self.app.notify(
                        f"Please provide a value for required field: {prop_name}",
                        severity="error",
                    )
                    return
                # For non-boolean fields, also check for empty values
                prop = self.scenario.parameter_schema.properties.get(prop_name)
                if prop and prop.type != "boolean":
                    if not parameters[prop_name]:
                        self.app.notify(
                            f"Please provide a value for required field: {prop_name}",
                            severity="error",
                        )
                        return

        # Check for required common fields
        if "_org_id" not in parameters or not parameters["_org_id"]:
            self.app.notify("Please provide Organization ID", severity="error")
            return
        if "_expiration_days" not in parameters or not parameters["_expiration_days"]:
            self.app.notify("Please provide Expiration Days", severity="error")
            return

        # Cache the parameter values for future use
        # Cache expiration days
        if "_expiration_days" in parameters:
            self.config_manager.add_recent_value(
                "expiration_days", parameters["_expiration_days"]
            )

        # Cache org_id (will be handled in execution screen with name fetching)
        # Note: Org name fetching happens in ScenarioExecutionScreen after validation

        # Cache scenario-specific parameters (whitelist approach)
        # Only cache parameters that are reusable across runs
        cache_whitelist = {"target_org"}  # Add more here as needed

        if self.scenario.parameter_schema:
            for prop_name, prop in self.scenario.parameter_schema.properties.items():
                if prop_name in parameters:
                    # Skip boolean parameters - they don't need caching
                    if prop.type == "boolean":
                        continue
                    # Only cache whitelisted parameters
                    if prop_name not in cache_whitelist:
                        continue
                    # Special handling for target_org (GitHub org)
                    if prop_name == "target_org":
                        self.config_manager.add_recent_value(
                            "github_orgs", parameters[prop_name]
                        )
                    else:
                        self.config_manager.add_recent_value(
                            f"param_{prop_name}", parameters[prop_name]
                        )

        # Go back and trigger execution
        self.app.pop_screen()
        # Push execution screen from the scenario browser
        scenario_browser = self.app.screen_stack[-1]
        if hasattr(scenario_browser, "handle_run_scenario"):
            scenario_browser.handle_run_scenario(self.scenario, parameters)  # type: ignore[attr-defined]

    @on(Button.Pressed, "#btn-cancel")
    def handle_cancel(self) -> None:
        """Handle cancel button press."""
        self.app.pop_screen()

    def action_cancel_parameters(self) -> None:
        """Cancel with escape key."""
        self.app.pop_screen()


class ScenarioPreviewScreen(Screen):
    """Screen for previewing scenario resources before execution."""

    BINDINGS = [
        Binding("escape", "cancel_preview", "Back"),
    ]

    def __init__(self, scenario: Any, parameters: dict[str, Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scenario = scenario
        self.parameters = parameters
        self.config_manager = ConfigManager()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static(
                f"[bold cyan]Preview: {self.scenario.name}[/bold cyan]\n",
                id="preview-title",
            ),
            Static(
                "[yellow]Preview mode - no resources will be created[/yellow]\n",
                id="preview-warning",
            ),
            VerticalScroll(id="preview-content"),
            Horizontal(
                Button("Execute Scenario", id="btn-execute", variant="primary"),
                Button("Back", id="btn-back", variant="default"),
                id="preview-buttons",
            ),
            id="preview-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.display_preview()

    def display_preview(self) -> None:
        """Generate and display the scenario preview."""
        from .creation_pipeline import CreationPipeline

        content = self.query_one("#preview-content", VerticalScroll)

        try:
            # Get current environment
            current_env = self.config_manager.get_current_environment()

            # Validate and resolve scenario parameters (excluding special params)
            scenario_params = {
                k: v for k, v in self.parameters.items() if not k.startswith("_")
            }
            processed_parameters = self.scenario.validate_input(scenario_params)
            resolved_scenario = self.scenario.resolve_template_variables(
                processed_parameters
            )

            # Generate preview
            preview = CreationPipeline.preview_scenario(resolved_scenario)

            # Display environment info
            content.mount(
                Static(f"[dim]Environment:[/dim] [cyan]{current_env}[/cyan]\n")
            )

            # Display repositories
            if preview["repositories"]:
                content.mount(
                    Static(
                        f"[bold green]✓[/bold green] GitHub repositories ([cyan]{len(preview['repositories'])}[/cyan]):"
                    )
                )
                for repo in preview["repositories"]:
                    content.mount(
                        Static(
                            f"  • [white]{repo['name']}[/white] [dim](from {repo['source']})[/dim]"
                        )
                    )
                content.mount(Static(""))

            # Display components
            if preview["components"]:
                content.mount(
                    Static(
                        f"[bold green]✓[/bold green] CloudBees components ([cyan]{len(preview['components'])}[/cyan]):"
                    )
                )
                for component in preview["components"]:
                    content.mount(Static(f"  • [white]{component}[/white]"))
                content.mount(Static(""))

            # Display environments
            if preview["environments"]:
                content.mount(
                    Static(
                        f"[bold green]✓[/bold green] CloudBees environments ([cyan]{len(preview['environments'])}[/cyan]):"
                    )
                )
                for env in preview["environments"]:
                    content.mount(Static(f"  • [white]{env['name']}[/white]"))
                content.mount(Static(""))

            # Display applications
            if preview["applications"]:
                content.mount(
                    Static(
                        f"[bold green]✓[/bold green] CloudBees applications ([cyan]{len(preview['applications'])}[/cyan]):"
                    )
                )
                for app in preview["applications"]:
                    comp_count = len(app["components"])
                    env_count = len(app["environments"])
                    content.mount(
                        Static(
                            f"  • [white]{app['name']}[/white] [dim]({comp_count} components, {env_count} environments)[/dim]"
                        )
                    )
                content.mount(Static(""))

            # Display flags
            if preview["flags"]:
                total_flag_count = len(preview["flags"])
                total_env_count = sum(
                    len(flag["environments"]) for flag in preview["flags"]
                )
                content.mount(
                    Static(
                        f"[bold green]✓[/bold green] Feature flags ([cyan]{total_flag_count} flag{'s' if total_flag_count != 1 else ''}, {total_env_count} environment{'s' if total_env_count != 1 else ''}[/cyan]):"
                    )
                )
                for flag in preview["flags"]:
                    env_list = ", ".join(flag["environments"])
                    content.mount(
                        Static(
                            f"  • [white]{flag['name']}[/white] [dim]({flag['type']}, in: {env_list})[/dim]"
                        )
                    )
                content.mount(Static(""))

        except Exception as e:
            content.mount(Static(f"[red]Error generating preview: {e}[/red]"))

    @on(Button.Pressed, "#btn-execute")
    def handle_execute(self) -> None:
        """Handle execute button press."""
        # Remove the preview mode flag before execution
        exec_params = {k: v for k, v in self.parameters.items() if k != "_preview_mode"}

        # Go back and push execution screen
        self.app.pop_screen()
        self.app.push_screen(ScenarioExecutionScreen(self.scenario, exec_params))

    @on(Button.Pressed, "#btn-back")
    def handle_back(self) -> None:
        """Handle back button press."""
        self.app.pop_screen()

    def action_cancel_preview(self) -> None:
        """Cancel preview with escape key."""
        self.app.pop_screen()


class ScenarioExecutionScreen(Screen):
    """Screen for showing scenario execution progress."""

    BINDINGS = [
        Binding("escape", "cancel_execution", "Cancel"),
    ]

    def __init__(self, scenario: Any, parameters: dict[str, Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scenario = scenario
        self.parameters = parameters
        self.config_manager = ConfigManager()
        self.state_tracker = StateTracker()
        self._execution_running = False

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static(
                f"[bold cyan]Executing: {self.scenario.name}[/bold cyan]\n",
                id="exec-title",
            ),
            Static("", id="exec-status"),
            VerticalScroll(id="exec-log"),
            Horizontal(
                Button("Back to Scenarios", id="btn-back", variant="default"),
                id="exec-buttons",
            ),
            id="exec-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.run_scenario()

    @work(exclusive=True)
    async def run_scenario(self) -> None:
        """Execute the scenario."""
        from .creation_pipeline import CreationPipeline

        self._execution_running = True
        log = self.query_one("#exec-log", VerticalScroll)
        status = self.query_one("#exec-status", Static)

        try:
            # Extract special parameters
            org_id = self.parameters.pop("_org_id")
            expiration_days = int(self.parameters.pop("_expiration_days", "7"))

            # Generate session ID
            import uuid

            session_id = str(uuid.uuid4())[:8]

            # Get credentials
            current_env = self.config_manager.get_current_environment()
            if not current_env:
                status.update("[red]No environment configured[/red]")
                log.mount(Static("[red]Error: No environment configured[/red]"))
                self._execution_running = False
                return

            cloudbees_pat = self.config_manager.get_cloudbees_pat(current_env)
            github_pat = self.config_manager.get_github_pat()
            env_url = self.config_manager.get_environment_url(current_env)
            endpoint_id = self.config_manager.get_endpoint_id(current_env)

            if not cloudbees_pat or not github_pat or not env_url or not endpoint_id:
                status.update("[red]Missing credentials or environment config[/red]")
                log.mount(
                    Static(
                        "[red]Error: Missing credentials or environment configuration[/red]"
                    )
                )
                self._execution_running = False
                return

            # Fetch and cache org name if not already cached
            cached_org_name = self.config_manager.get_cached_org_name(
                org_id, current_env
            )
            if not cached_org_name:
                try:
                    from .unify import UnifyAPIClient

                    with UnifyAPIClient(
                        base_url=env_url, api_key=cloudbees_pat
                    ) as client:
                        org_data = client.get_organization(org_id)
                        org_info = org_data.get("organization", {})
                        org_name = org_info.get("displayName", "Unknown")
                        self.config_manager.cache_org_name(
                            org_id, org_name, current_env
                        )
                except Exception:
                    # Failed to fetch name, continue anyway
                    pass

            # Create session
            self.state_tracker.create_session(
                session_id=session_id,
                scenario_id=self.scenario.id,
                environment=current_env,
                expiration_days=expiration_days,
                metadata={
                    "parameters": self.parameters,
                },
            )

            status.update(f"[yellow]Running... (Session: {session_id})[/yellow]")
            log.mount(Static(f"Session ID: {session_id}"))
            log.mount(Static(f"Environment: {current_env}"))
            log.mount(Static(f"Expires in: {expiration_days} days\n"))

            # Get default GitHub username for repo invitations
            invitee_username = self.config_manager.get_github_username()

            # Create pipeline
            pipeline = CreationPipeline(
                organization_id=org_id,
                endpoint_id=endpoint_id,
                unify_pat=cloudbees_pat,
                unify_base_url=env_url,
                session_id=session_id,
                github_pat=github_pat,
                invitee_username=invitee_username,
            )

            # Execute scenario
            log.mount(Static("[bold]Executing scenario...[/bold]"))
            summary = await pipeline.execute_scenario(self.scenario, self.parameters)

            # Track resources
            for repo_data in summary.get("repositories", []):
                self.state_tracker.add_resource(
                    session_id=session_id,
                    resource_type="github_repo",
                    resource_id=repo_data.get("full_name", ""),
                    resource_name=repo_data.get("name", ""),
                    metadata=repo_data,
                )

            for component_name, component_data in pipeline.created_components.items():
                self.state_tracker.add_resource(
                    session_id=session_id,
                    resource_type="cloudbees_component",
                    resource_id=component_data.get("id", ""),
                    resource_name=component_name,
                    org_id=org_id,
                    metadata=component_data,
                )

            for env_name, env_data in pipeline.created_environments.items():
                self.state_tracker.add_resource(
                    session_id=session_id,
                    resource_type="cloudbees_environment",
                    resource_id=env_data.get("id", ""),
                    resource_name=env_name,
                    org_id=org_id,
                    metadata=env_data,
                )

            for app_name, app_data in pipeline.created_applications.items():
                self.state_tracker.add_resource(
                    session_id=session_id,
                    resource_type="cloudbees_application",
                    resource_id=app_data.get("id", ""),
                    resource_name=app_name,
                    org_id=org_id,
                    metadata=app_data,
                )

            # Show success
            status.update("[green]✓ Completed successfully![/green]")
            log.mount(
                Static("\n[bold green]✓ Scenario completed successfully![/bold green]")
            )
            log.mount(Static("\nResources created:"))
            log.mount(
                Static(f"  • Repositories: {len(summary.get('repositories', []))}")
            )
            log.mount(Static(f"  • Components: {len(pipeline.created_components)}"))
            log.mount(Static(f"  • Environments: {len(pipeline.created_environments)}"))
            log.mount(Static(f"  • Applications: {len(pipeline.created_applications)}"))
            log.mount(Static(f"  • Feature Flags: {len(pipeline.created_flags)}"))

        except Exception as e:
            status.update("[red]✗ Execution failed[/red]")
            log.mount(Static(f"\n[red]Error: {e}[/red]"))

        finally:
            self._execution_running = False

    @on(Button.Pressed, "#btn-back")
    def action_back(self) -> None:
        """Go back to scenarios screen."""
        if not self._execution_running:
            self.app.pop_screen()

    def action_cancel_execution(self) -> None:
        """Cancel execution."""
        if self._execution_running:
            self.app.notify("Cancellation not yet implemented", severity="warning")
        else:
            self.app.pop_screen()


class CleanupManagerScreen(Screen):
    """Screen for managing and cleaning up sessions."""

    BINDINGS = [
        Binding("enter", "delete_session", "Delete", show=False),
        Binding("d", "delete_session", "Delete"),
        Binding("e", "cleanup_expired", "Cleanup Expired"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_manager = ConfigManager()
        self.state_tracker = StateTracker()
        self.cleanup_manager = CleanupManager(self.config_manager, self.state_tracker)

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static("[bold cyan]Cleanup Manager[/bold cyan]\n", id="cleanup-title"),
            DataTable(id="cleanup-table"),
            Horizontal(
                Button("Delete Session", id="btn-delete-session", variant="error"),
                Button("Cleanup Expired", id="btn-cleanup-expired", variant="warning"),
                Button("Back", id="btn-back", variant="default"),
                id="cleanup-buttons",
            ),
            id="cleanup-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.refresh_sessions()

    def refresh_sessions(self) -> None:
        """Refresh the sessions table."""
        table = self.query_one("#cleanup-table", DataTable)
        table.clear(columns=True)

        # Add columns
        table.add_column("Session ID", key="session_id")
        table.add_column("Scenario", key="scenario")
        table.add_column("Environment", key="environment")
        table.add_column("Created", key="created")
        table.add_column("Expires", key="expires")
        table.add_column("Resources", key="resources")
        table.add_column("Status", key="status")

        # Add rows
        sessions = self.state_tracker.list_sessions(include_expired=True)
        now = datetime.now()

        for session in sessions:
            never_expires = session.expires_at is None
            is_expired = session.expires_at is not None and session.expires_at <= now

            if never_expires:
                status = "NEVER EXPIRES"
                status_style = "blue"
            elif is_expired:
                status = "EXPIRED"
                status_style = "red"
            else:
                status = "ACTIVE"
                status_style = "green"

            table.add_row(
                session.session_id,
                session.scenario_id,
                session.environment,
                session.created_at.strftime("%Y-%m-%d %H:%M"),
                "Never"
                if session.expires_at is None
                else session.expires_at.strftime("%Y-%m-%d %H:%M"),
                str(len(session.resources)),
                Text(status, style=status_style),
                key=session.session_id,
            )

        if table.row_count > 0:
            table.cursor_type = "row"

    @on(Button.Pressed, "#btn-delete-session")
    def action_delete_session(self) -> None:
        """Delete the highlighted session."""
        table = self.query_one("#cleanup-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)
            session_id = str(row_key[0])

            self.app.push_screen(
                ConfirmDialog(
                    f"Delete session '{session_id}' and all its resources?",
                    "handle_delete_session",
                    session_id,
                )
            )

    @on(Button.Pressed, "#btn-cleanup-expired")
    def action_cleanup_expired(self) -> None:
        """Clean up all expired sessions."""
        expired_sessions = self.cleanup_manager.check_expired_sessions()

        if not expired_sessions:
            self.app.notify("No expired sessions found", severity="information")
            return

        self.app.push_screen(
            ConfirmDialog(
                f"Delete {len(expired_sessions)} expired session(s) and all their resources?",
                "handle_cleanup_expired",
            )
        )

    @on(Button.Pressed, "#btn-back")
    def action_back(self) -> None:
        """Go back to main screen."""
        self.app.pop_screen()

    def handle_delete_session(self, session_id: str, confirmed: bool) -> None:
        """Handle delete session confirmation."""
        if confirmed:
            self.run_cleanup_session(session_id)

    def handle_cleanup_expired(self, confirmed: bool) -> None:
        """Handle cleanup expired confirmation."""
        if confirmed:
            self.run_cleanup_expired()

    @work(exclusive=True)
    async def run_cleanup_session(self, session_id: str) -> None:
        """Run cleanup for a specific session."""
        try:
            self.app.notify(
                f"Cleaning up session {session_id}...", severity="information"
            )
            results = await self.cleanup_manager.cleanup_session(
                session_id, dry_run=False
            )

            if results["errors"]:
                self.app.notify(
                    f"Cleanup completed with {len(results['errors'])} error(s)",
                    severity="warning",
                )
            else:
                self.app.notify(
                    "Cleanup completed successfully", severity="information"
                )

            self.refresh_sessions()
        except Exception as e:
            self.app.notify(f"Error during cleanup: {e}", severity="error")

    @work(exclusive=True)
    async def run_cleanup_expired(self) -> None:
        """Run cleanup for all expired sessions."""
        try:
            self.app.notify("Cleaning up expired sessions...", severity="information")
            results = await self.cleanup_manager.cleanup_expired_sessions(
                dry_run=False, auto_confirm=True
            )

            self.app.notify(
                f"Cleaned up {results['cleaned_sessions']} session(s)",
                severity="information",
            )
            self.refresh_sessions()
        except Exception as e:
            self.app.notify(f"Error during cleanup: {e}", severity="error")


class AddEnvironmentDialog(Screen):
    """Screen for adding an environment."""

    BINDINGS = [
        Binding("escape", "cancel_add", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static("Add Environment", id="add-env-title"),
            Label("Environment Name:"),
            Input(
                placeholder="prod, preprod, demo, or custom name", id="input-env-name"
            ),
            Label("API URL:"),
            Input(placeholder="https://api.cloudbees.io", id="input-env-url"),
            Label("Endpoint ID:"),
            Input(placeholder="Endpoint UUID", id="input-env-endpoint"),
            Label("CloudBees PAT:"),
            Input(
                placeholder="Personal Access Token", password=True, id="input-env-pat"
            ),
            Horizontal(
                Button("Add", id="btn-add", variant="primary"),
                Button("Cancel", id="btn-cancel", variant="default"),
                id="add-env-buttons",
            ),
            id="add-env-container",
        )
        yield Footer()

    @on(Button.Pressed, "#btn-add")
    def handle_add(self) -> None:
        """Handle add button press."""
        name_input = self.query_one("#input-env-name", Input)
        url_input = self.query_one("#input-env-url", Input)
        endpoint_input = self.query_one("#input-env-endpoint", Input)
        pat_input = self.query_one("#input-env-pat", Input)

        if not all(
            [name_input.value, url_input.value, endpoint_input.value, pat_input.value]
        ):
            self.app.notify("All fields are required", severity="error")
            return

        result = {
            "name": name_input.value,
            "url": url_input.value,
            "endpoint_id": endpoint_input.value,
            "pat": pat_input.value,
        }

        # Go back and trigger add
        self.app.pop_screen()
        env_manager = self.app.screen_stack[-1]
        if hasattr(env_manager, "handle_add_environment"):
            env_manager.handle_add_environment(result)  # type: ignore[attr-defined]

    @on(Button.Pressed, "#btn-cancel")
    def handle_cancel(self) -> None:
        """Handle cancel button press."""
        self.app.pop_screen()

    def action_cancel_add(self) -> None:
        """Cancel with escape key."""
        self.app.pop_screen()


class ConfirmDialog(Screen):
    """Confirmation screen."""

    BINDINGS = [
        Binding("escape", "confirm_no", "No", show=False),
        Binding("n", "confirm_no", "No", show=False),
        Binding("y", "confirm_yes", "Yes", show=False),
    ]

    def __init__(
        self, message: str, action_name: str, action_data: Any = None, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.message = message
        self.action_name = action_name
        self.action_data = action_data

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Container(
                Static(f"{self.message}", id="confirm-message"),
                Horizontal(
                    Button("Yes", id="btn-yes", variant="error"),
                    Button("No", id="btn-no", variant="default"),
                    id="confirm-buttons",
                ),
                id="confirm-content",
            ),
            id="confirm-container",
        )
        yield Footer()

    @on(Button.Pressed, "#btn-yes")
    def handle_yes(self) -> None:
        """Handle yes button press."""
        self.app.pop_screen()
        # Trigger the action on the previous screen
        previous_screen = self.app.screen_stack[-1]
        if hasattr(previous_screen, self.action_name):
            method = getattr(previous_screen, self.action_name)
            if self.action_data is not None:
                method(self.action_data, True)
            else:
                method(True)

    @on(Button.Pressed, "#btn-no")
    def handle_no(self) -> None:
        """Handle no button press."""
        self.app.pop_screen()

    def action_confirm_yes(self) -> None:
        """Confirm with yes via keyboard."""
        self.handle_yes()

    def action_confirm_no(self) -> None:
        """Confirm with no via keyboard."""
        self.handle_no()


class MimicTUI(App):
    """Main Mimic TUI application."""

    CSS = """
    /* Welcome screen */
    #welcome-container {
        width: 100%;
        height: 100%;
        padding: 1;
    }

    #welcome-text {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
        height: auto;
    }

    #stats-panel {
        width: 100%;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    /* Main container screens */
    #env-container, #scenario-container, #cleanup-container, #exec-container, #preview-container {
        width: 100%;
        height: 100%;
        padding: 1;
    }

    #env-title, #scenario-title, #cleanup-title, #exec-title, #preview-title {
        height: auto;
        margin-bottom: 1;
    }

    #preview-warning {
        height: auto;
        margin-bottom: 1;
    }

    #preview-content {
        height: 1fr;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    #preview-content Static {
        height: auto;
    }

    DataTable {
        height: 1fr;
        margin-bottom: 1;
    }

    /* Button rows */
    #env-buttons, #scenario-buttons, #cleanup-buttons, #exec-buttons, #preview-buttons {
        width: 100%;
        height: auto;
        dock: bottom;
    }

    #env-buttons Button, #scenario-buttons Button, #cleanup-buttons Button, #exec-buttons Button, #preview-buttons Button {
        height: 3;
        margin-right: 2;
    }

    /* Modal/Dialog screens - full page */
    #param-container, #add-env-container {
        width: 100%;
        height: 100%;
        padding: 2;
    }

    #confirm-container {
        width: 100%;
        height: 100%;
        padding: 2;
        align: center middle;
    }

    #confirm-content {
        width: 60;
        height: auto;
        padding: 2;
    }

    #param-title, #add-env-title {
        height: auto;
        margin-bottom: 1;
    }

    #confirm-message {
        height: auto;
        margin-bottom: 2;
        text-style: bold;
    }

    #param-inputs {
        height: auto;
        max-height: 1fr;
        margin-bottom: 1;
        padding: 1;
    }

    #param-inputs Label {
        height: auto;
        margin-top: 1;
    }

    #param-inputs Input {
        margin-bottom: 1;
    }

    #add-env-container Label {
        height: auto;
        margin-top: 1;
    }

    #add-env-container Input {
        margin-bottom: 1;
    }

    #param-buttons, #add-env-buttons, #confirm-buttons {
        width: 100%;
        height: auto;
        margin-top: 1;
        dock: bottom;
    }

    #param-buttons Button, #add-env-buttons Button, #confirm-buttons Button {
        height: 3;
        margin-right: 2;
    }

    /* Text sizing */
    Static {
        text-style: none;
    }

    /* Execution screen */
    #exec-log {
        height: 1fr;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    #exec-log Static {
        height: auto;
    }

    #exec-status {
        height: auto;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
    ]

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.theme = "gruvbox"
        self.push_screen(WelcomeScreen())


def run_tui() -> None:
    """Run the TUI application."""
    app = MimicTUI()
    app.run()


if __name__ == "__main__":
    run_tui()
