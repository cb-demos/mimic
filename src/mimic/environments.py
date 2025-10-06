"""Pre-defined CloudBees Unify environment configurations."""

from typing import NamedTuple


class EnvironmentConfig(NamedTuple):
    """CloudBees Unify environment configuration."""

    url: str
    endpoint_id: str
    description: str


# Pre-defined CloudBees Unify environments
PRESET_ENVIRONMENTS: dict[str, EnvironmentConfig] = {
    "prod": EnvironmentConfig(
        url="https://api.cloudbees.io",
        endpoint_id="9a3942be-0e86-415e-94c5-52512be1138d",
        description="CloudBees Unify Production",
    ),
    "preprod": EnvironmentConfig(
        url="https://api.saas-preprod.beescloud.com",
        endpoint_id="8509888e-d27f-44fa-46a9-29bc76f5e790",
        description="CloudBees Unify Pre-Production",
    ),
    "demo": EnvironmentConfig(
        url="https://api.demo1.cloudbees.io",
        endpoint_id="1f58a757-6e0d-4715-accc-1e3b035fa0c3",
        description="CloudBees Unify Demo",
    ),
}


def get_preset_environment(name: str) -> EnvironmentConfig | None:
    """Get a preset environment configuration by name.

    Args:
        name: Environment name (prod, preprod, demo).

    Returns:
        EnvironmentConfig if found, None otherwise.
    """
    return PRESET_ENVIRONMENTS.get(name.lower())


def list_preset_environments() -> dict[str, EnvironmentConfig]:
    """Get all preset environment configurations.

    Returns:
        Dictionary of preset environment names to their configs.
    """
    return PRESET_ENVIRONMENTS.copy()
