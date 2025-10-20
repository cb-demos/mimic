"""FastAPI dependency injection for shared components."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status

from mimic.config_manager import ConfigManager
from mimic.scenarios import ScenarioManager, initialize_scenarios_from_config

logger = logging.getLogger(__name__)


def get_config_manager() -> ConfigManager:
    """Get a ConfigManager instance.

    Returns:
        ConfigManager instance for accessing configuration
    """
    return ConfigManager()


def get_scenario_manager() -> ScenarioManager:
    """Get a ScenarioManager instance.

    Returns:
        ScenarioManager instance for accessing scenarios
    """
    return initialize_scenarios_from_config()


def require_github_credentials(
    config: Annotated[ConfigManager, Depends(get_config_manager)]
) -> tuple[str, str]:
    """Require GitHub credentials to be configured.

    Args:
        config: ConfigManager dependency

    Returns:
        Tuple of (username, pat)

    Raises:
        HTTPException: If GitHub credentials are not configured
    """
    username = config.get_github_username()
    pat = config.get_github_pat()

    if not username or not pat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub credentials not configured. Please configure via /api/config/github",
        )

    return username, pat


def require_cloudbees_credentials(
    config: Annotated[ConfigManager, Depends(get_config_manager)]
) -> tuple[str, str, str, str]:
    """Require CloudBees credentials for current environment.

    Args:
        config: ConfigManager dependency

    Returns:
        Tuple of (environment_name, cloudbees_pat, url, endpoint_id)

    Raises:
        HTTPException: If CloudBees credentials or environment not configured
    """
    env_name = config.get_current_environment()
    if not env_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No environment selected. Please select an environment via /api/environments/{env}/select",
        )

    pat = config.get_cloudbees_pat(env_name)
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"CloudBees credentials not configured for environment '{env_name}'",
        )

    url = config.get_environment_url(env_name)
    endpoint_id = config.get_endpoint_id(env_name)

    if not url or not endpoint_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Environment '{env_name}' configuration incomplete",
        )

    return env_name, pat, url, endpoint_id


# Type aliases for cleaner endpoint signatures
ConfigDep = Annotated[ConfigManager, Depends(get_config_manager)]
ScenarioDep = Annotated[ScenarioManager, Depends(get_scenario_manager)]
GitHubCredentialsDep = Annotated[tuple[str, str], Depends(require_github_credentials)]
CloudBeesCredentialsDep = Annotated[
    tuple[str, str, str, str], Depends(require_cloudbees_credentials)
]
