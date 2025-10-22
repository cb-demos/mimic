"""Pre-defined CloudBees Unify environment configurations."""

from typing import NamedTuple


class EnvironmentConfig(NamedTuple):
    """CloudBees Unify environment configuration."""

    url: str
    endpoint_id: str
    description: str
    org_slug: str  # Organization slug in UI URLs (e.g., "cloudbees", "demo", "unify-golden-demos")
    ui_url: str | None = (
        None  # Optional custom UI URL (if different from url without "api.")
    )
    properties: dict[str, str] = {}
    use_legacy_flags: bool = (
        False  # True for org-based flags (prod), False for app-based flags
    )


# Pre-defined CloudBees Unify environments
PRESET_ENVIRONMENTS: dict[str, EnvironmentConfig] = {
    "prod": EnvironmentConfig(
        url="https://api.cloudbees.io",
        endpoint_id="9a3942be-0e86-415e-94c5-52512be1138d",
        description="CloudBees Unify Production",
        org_slug="cloudbees",
        ui_url=None,
        properties={
            "USE_VPC": "false",
            "FM_INSTANCE": "cloudbees.io",
        },
        use_legacy_flags=True,
    ),
    "preprod": EnvironmentConfig(
        url="https://api.saas-preprod.beescloud.com",
        endpoint_id="8509888e-d27f-44fa-46a9-29bc76f5e790",
        description="CloudBees Unify Pre-Production",
        org_slug="cloudbees-preprod",
        ui_url=None,
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
        org_slug="demo",
        ui_url="https://ui.demo1.cloudbees.io",
        properties={
            "USE_VPC": "true",
            "FM_INSTANCE": "demo1.cloudbees.io",
        },
        use_legacy_flags=False,  # Demo uses app-based flag API
    ),
    "golden": EnvironmentConfig(
        url="https://api.cloudbees.io",
        endpoint_id="5848f60a-077d-438b-acad-842b64686797",
        description="SE Golden Demo Env",
        org_slug="unify-golden-demos",
        ui_url=None,
        properties={
            "USE_VPC": "false",
            "FM_INSTANCE": "cloudbees.io",
        },
        use_legacy_flags=False,
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
