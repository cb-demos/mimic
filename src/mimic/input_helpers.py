"""Helper functions for interactive CLI input prompts."""

import questionary
import typer
from rich.console import Console

from .config_manager import ConfigManager
from .unify import UnifyAPIClient

console = Console()


def format_field_name(field_name: str) -> str:
    """Convert snake_case field name to human-readable format.

    Args:
        field_name: Snake case field name (e.g., 'project_name')

    Returns:
        Formatted field name (e.g., 'Project name')

    Examples:
        >>> format_field_name('project_name')
        'Project name'
        >>> format_field_name('target_org')
        'Target org'
        >>> format_field_name('custom_environment')
        'Custom environment'
    """
    # Split on underscores and capitalize first word only
    words = field_name.split("_")
    if words:
        words[0] = words[0].capitalize()
    return " ".join(words)


def select_or_new(
    prompt: str,
    choices: list[str],
    new_option_label: str = "Enter new value...",
    allow_skip: bool = False,
) -> str | None:
    """Present a fuzzy-searchable select list with option to enter new value.

    Args:
        prompt: Prompt text to display
        choices: List of existing choices
        new_option_label: Label for the "enter new" option
        allow_skip: If True, allow skipping (returns None)

    Returns:
        Selected value or newly entered value, or None if skipped
    """
    if not choices:
        # No recent values, just prompt for new
        if allow_skip:
            value = typer.prompt(prompt, default="")
            return value if value else None
        return typer.prompt(prompt)

    # Add special options
    options = choices.copy()
    options.append(new_option_label)
    if allow_skip:
        options.append("Skip (leave empty)")

    # Use questionary for fuzzy-searchable select
    selection = questionary.select(
        prompt,
        choices=options,
        use_shortcuts=True,
        use_arrow_keys=True,
    ).ask()

    # Handle selection
    if selection == new_option_label:
        # User wants to enter new value
        if allow_skip:
            value = typer.prompt("Enter value", default="")
            return value if value else None
        return typer.prompt("Enter value")
    elif allow_skip and selection == "Skip (leave empty)":
        return None
    else:
        return selection


def prompt_github_org(
    description: str = "GitHub organization",
    required: bool = True,
) -> str | None:
    """Prompt for GitHub organization with recent values selection.

    Args:
        description: Description text for the prompt
        required: Whether the value is required

    Returns:
        Selected or entered GitHub org name, or None if optional and skipped
    """
    config_manager = ConfigManager()
    recent_orgs = config_manager.get_recent_values("github_orgs")

    prompt_text = format_field_name("target_org")
    if description and description != "GitHub organization":
        prompt_text = description

    value = select_or_new(
        prompt_text,
        recent_orgs,
        new_option_label="Enter new organization...",
        allow_skip=not required,
    )

    # Cache the value if provided
    if value:
        config_manager.add_recent_value("github_orgs", value)

    return value


def prompt_cloudbees_org(
    env_url: str,
    cloudbees_pat: str,
    env_name: str,
    description: str = "CloudBees Organization",
) -> str:
    """Prompt for CloudBees organization ID with cached names.

    Fetches organization names from API on first use and caches them
    for better UX (shows "Acme Corp (uuid)" instead of just UUID).

    Args:
        env_url: CloudBees Unify API URL
        cloudbees_pat: CloudBees PAT for API access
        env_name: Environment name (for environment-specific caching)
        description: Description text for the prompt

    Returns:
        Selected or entered organization UUID
    """
    config_manager = ConfigManager()
    cached_orgs = config_manager.get_cached_orgs_for_tenant(env_name)

    if not cached_orgs:
        # No cached orgs, just prompt for ID
        org_id = typer.prompt(description)

        # Try to fetch and cache the org name
        try:
            with UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat) as client:
                org_data = client.get_organization(org_id)
                # API response format: {"organization": {"displayName": "..."}}
                org_info = org_data.get("organization", {})
                org_name = org_info.get("displayName", "Unknown")
                config_manager.cache_org_name(org_id, org_name, env_name)
                console.print(f"[dim]Cached organization: {org_name}[/dim]")
        except Exception:
            # Failed to fetch name, continue anyway
            pass

        return org_id

    # Build choices with cached names
    choices = []
    org_id_map = {}  # Display text -> org_id mapping

    for org_id, org_name in cached_orgs.items():
        display_text = f"{org_name} ({org_id[:8]}...)"
        choices.append(display_text)
        org_id_map[display_text] = org_id

    # Use questionary for selection
    options = choices + ["Enter new organization ID..."]
    selection = questionary.select(
        description,
        choices=options,
        use_shortcuts=True,
        use_arrow_keys=True,
    ).ask()

    if selection == "Enter new organization ID...":
        # User wants to enter new ID
        org_id = typer.prompt("CloudBees Organization ID")

        # Try to fetch and cache the org name
        try:
            with UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat) as client:
                org_data = client.get_organization(org_id)
                # API response format: {"organization": {"displayName": "..."}}
                org_info = org_data.get("organization", {})
                org_name = org_info.get("displayName", "Unknown")
                config_manager.cache_org_name(org_id, org_name, env_name)
                console.print(f"[dim]Cached organization: {org_name}[/dim]")
        except Exception:
            # Failed to fetch name, continue anyway
            pass

        return org_id
    else:
        # User selected from cached list
        return org_id_map[selection]
