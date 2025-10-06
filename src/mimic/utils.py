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
