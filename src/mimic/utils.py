import re
from typing import Any


def apply_replacements(content: str, replacements: dict[str, str]) -> str:
    """
    Apply a dictionary of find/replace operations to a string.

    Args:
        content: The original string content
        replacements: Dictionary where keys are strings to find and values are replacements

    Returns:
        The modified string with all replacements applied
    """
    result = content
    for find_str, replace_str in replacements.items():
        result = result.replace(find_str, replace_str)
    return result


def resolve_run_name(scenario: Any, parameters: dict[str, Any], session_id: str) -> str:
    """
    Resolve the run name from scenario name_template.

    Args:
        scenario: The scenario object with optional name_template field
        parameters: Parameter values provided by user
        session_id: Session ID for fallback

    Returns:
        Resolved run name
    """
    # Use name_template if provided, otherwise default to scenario_id-session_id
    template = (
        scenario.name_template
        if hasattr(scenario, "name_template") and scenario.name_template
        else "${scenario_id}-${session_id}"
    )

    # Create values dict with scenario_id and session_id included
    values = parameters.copy()
    values["scenario_id"] = scenario.id
    values["session_id"] = session_id

    # Pattern to match ${variable_name}
    pattern = re.compile(r"\$\{([^}]+)\}")

    def replacer(match):
        var_name = match.group(1)
        if var_name not in values:
            # Fallback to session_id if variable not found
            return session_id
        return str(values[var_name])

    try:
        return pattern.sub(replacer, template)
    except Exception:
        # If resolution fails, fall back to session_id
        return session_id
