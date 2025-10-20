"""Pre-defined CloudBees Unify environment configurations."""

from typing import NamedTuple


class EnvironmentConfig(NamedTuple):
    """CloudBees Unify environment configuration."""

    url: str
    endpoint_id: str
    description: str
    properties: dict[str, str] = {}
    use_legacy_flags: bool = False  # True for org-based flags (prod), False for app-based flags


# Pre-defined CloudBees Unify environments
PRESET_ENVIRONMENTS: dict[str, EnvironmentConfig] = {
    "prod": EnvironmentConfig(
        url="https://api.cloudbees.io",
        endpoint_id="9a3942be-0e86-415e-94c5-52512be1138d",
        description="CloudBees Unify Production",
        properties={
            "USE_VPC": "false",
            "FM_INSTANCE": "cloudbees.io",
        },
        use_legacy_flags=True,  # Prod uses org-based flag API
    ),
    "preprod": EnvironmentConfig(
        url="https://api.saas-preprod.beescloud.com",
        endpoint_id="8509888e-d27f-44fa-46a9-29bc76f5e790",
        description="CloudBees Unify Pre-Production",
        properties={
            "USE_VPC": "true",
            "FM_INSTANCE": "saas-preprod.beescloud.com",
        },
        use_legacy_flags=False,  # Preprod uses app-based flag API
    ),
    "demo": EnvironmentConfig(
        url="https://api.demo1.cloudbees.io",
        endpoint_id="f6e2a9c4-cc4a-4cbd-b1fc-102fa4572d2c",
        description="CloudBees Unify Demo",
        properties={
            "USE_VPC": "true",
            "FM_INSTANCE": "demo1.cloudbees.io",
        },
        use_legacy_flags=False,  # Demo uses app-based flag API
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
