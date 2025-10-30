"""Interactive prompts and selection for the run command."""

import questionary
import typer
from rich.console import Console

console = Console()


def select_scenario_interactive(scenario_manager):
    """Interactively select a scenario from available scenarios.

    Args:
        scenario_manager: ScenarioManager instance.

    Returns:
        Selected scenario ID.
    """
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

    return scenario_map[selection]


def handle_expiration_selection(
    config_manager, no_expiration: bool, expires_in_days: int | None
) -> tuple[int, str]:
    """Determine expiration days and label (interactive if not specified).

    Args:
        config_manager: ConfigManager instance.
        no_expiration: Whether resources never expire.
        expires_in_days: Number of days until expiration (or None).

    Returns:
        Tuple of (expiration_days, expiration_label).
    """
    if no_expiration:
        expiration_days = 0  # 0 means never expires
        expiration_label = "Never"
        return expiration_days, expiration_label

    if expires_in_days is not None:
        expiration_days = expires_in_days
        expiration_label = f"{expiration_days} days"
        return expiration_days, expiration_label

    # Interactive expiration selection
    default_expiration = config_manager.get_setting("default_expiration_days", 7)
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
    selected_value: str | None = None
    for label, value in expiration_options:
        if label == selected_expiration:
            selected_value = value
            break

    # selected_value should always be found since we're selecting from expiration_options
    if selected_value is None:
        # Fallback to default if somehow not found
        selected_value = str(default_expiration)

    if selected_value == "never":
        expiration_days = 0  # 0 means never expires
        expiration_label = "Never"
    elif selected_value == "custom":
        custom_days = typer.prompt("Enter custom expiration days", type=int)
        expiration_days = custom_days
        expiration_label = f"{expiration_days} days"
        # Cache the custom value
        config_manager.add_recent_value("expiration_days", str(custom_days))
    else:
        # At this point, selected_value is guaranteed to be a numeric string
        expiration_days = int(selected_value)
        expiration_label = f"{expiration_days} days"
        # Cache the selected value
        config_manager.add_recent_value("expiration_days", selected_value)

    console.print(f"Expiration: [yellow]{expiration_label}[/yellow]")

    return expiration_days, expiration_label
