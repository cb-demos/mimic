"""Configuration and credential management for Mimic."""

import logging
from typing import Any

import keyring
import yaml

from .exceptions import KeyringUnavailableError
from .keyring_health import get_keyring_setup_instructions
from .paths import get_config_dir

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration file and secure credential storage."""

    KEYRING_SERVICE = "mimic"
    CONFIG_DIR = get_config_dir()
    CONFIG_FILE = CONFIG_DIR / "config.yaml"
    STATE_FILE = CONFIG_DIR / "state.json"
    PACKS_DIR = CONFIG_DIR / "scenario_packs"

    def __init__(self):
        """Initialize the config manager."""
        self.config_dir = self.CONFIG_DIR
        self.config_file = self.CONFIG_FILE
        self.state_file = self.STATE_FILE
        self.packs_dir = self.PACKS_DIR
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure the config directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration dictionary, or default empty config if file doesn't exist.
        """
        if not self.config_file.exists():
            return self._get_default_config()

        with open(self.config_file) as f:
            config = yaml.safe_load(f) or self._get_default_config()

        # Run auto-migration to add missing fields
        config = self._migrate_config(config)

        return config

    def save_config(self, config: dict[str, Any]) -> None:
        """Save configuration to file.

        Args:
            config: Configuration dictionary to save.
        """
        with open(self.config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    def _migrate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Auto-migrate config to add missing fields from preset environments.

        This ensures existing users get new fields (like org_slug) populated automatically
        from preset definitions without needing to reconfigure.

        Args:
            config: Configuration dictionary to migrate

        Returns:
            Migrated configuration dictionary
        """
        from mimic.environments import PRESET_ENVIRONMENTS

        environments = config.get("environments", {})
        needs_save = False

        for env_name, env_config in environments.items():
            # Check if this environment is missing org_slug or ui_url
            if "org_slug" not in env_config or "ui_url" not in env_config:
                # Check if it matches a preset environment
                preset = PRESET_ENVIRONMENTS.get(env_name)
                if preset:
                    # Populate missing fields from preset
                    if "org_slug" not in env_config:
                        env_config["org_slug"] = preset.org_slug
                        needs_save = True
                    if "ui_url" not in env_config:
                        env_config["ui_url"] = preset.ui_url
                        needs_save = True

        # Save config if we made changes
        if needs_save:
            self.save_config(config)

        return config

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration structure."""
        return {
            "current_environment": None,
            "environments": {},
            "github": {"default_username": None},
            "settings": {"default_expiration_days": 7, "auto_cleanup_prompt": True},
            "scenario_packs": {},
            "recent_values": {
                "github_orgs": [],
                "cloudbees_orgs": {},  # env_name -> {org_id -> org_name} mapping
            },
        }

    # Environment management
    def add_environment(
        self,
        name: str,
        url: str,
        pat: str,
        endpoint_id: str,
        org_slug: str | None = None,
        ui_url: str | None = None,
        properties: dict[str, str] | None = None,
        use_legacy_flags: bool = False,
    ) -> None:
        """Add a new environment.

        Args:
            name: Environment name (e.g., 'prod', 'preprod', 'demo').
            url: CloudBees Unify API URL.
            pat: Personal Access Token (stored securely in keyring).
            endpoint_id: CloudBees endpoint ID for the environment.
            org_slug: Organization slug for UI URLs (e.g., 'cloudbees', 'demo').
            ui_url: Optional custom UI URL (if different from url without 'api.').
            properties: Optional custom properties for this environment.
            use_legacy_flags: Whether to use org-based flag API (True) or app-based (False).
        """
        config = self.load_config()

        # Add environment to config
        if "environments" not in config:
            config["environments"] = {}

        env_config: dict[str, Any] = {
            "url": url,
            "endpoint_id": endpoint_id,
            "use_legacy_flags": use_legacy_flags,
        }
        if org_slug:
            env_config["org_slug"] = org_slug
        if ui_url:
            env_config["ui_url"] = ui_url
        if properties:
            env_config["properties"] = properties

        config["environments"][name] = env_config

        # Set as current if no environment is selected
        if not config.get("current_environment"):
            config["current_environment"] = name

        # Save PAT to keyring
        self.set_cloudbees_pat(name, pat)

        # Save config
        self.save_config(config)

    def remove_environment(self, name: str) -> None:
        """Remove an environment.

        Args:
            name: Environment name to remove.
        """
        config = self.load_config()

        # Remove from config
        if "environments" in config and name in config["environments"]:
            del config["environments"][name]

        # Update current_environment if needed
        if config.get("current_environment") == name:
            remaining_envs = config.get("environments", {})
            config["current_environment"] = (
                next(iter(remaining_envs)) if remaining_envs else None
            )

        # Remove PAT from keyring
        self.delete_cloudbees_pat(name)

        # Save config
        self.save_config(config)

    def list_environments(self) -> dict[str, dict[str, str]]:
        """List all configured environments.

        Returns:
            Dictionary of environment names to their configuration.
        """
        config = self.load_config()
        return config.get("environments", {})

    def get_current_environment(self) -> str | None:
        """Get the currently selected environment name.

        Returns:
            Current environment name, or None if not set.
        """
        config = self.load_config()
        return config.get("current_environment")

    def set_current_environment(self, name: str) -> None:
        """Set the current environment.

        Args:
            name: Environment name to set as current.
        """
        config = self.load_config()
        config["current_environment"] = name
        self.save_config(config)

    def get_environment_url(self, name: str | None = None) -> str | None:
        """Get the API URL for an environment.

        Args:
            name: Environment name. If None, uses current environment.

        Returns:
            API URL, or None if environment not found.
        """
        if name is None:
            name = self.get_current_environment()

        if not name:
            return None

        config = self.load_config()
        env = config.get("environments", {}).get(name)
        return env.get("url") if env else None

    def get_environment_org_slug(self, name: str | None = None) -> str | None:
        """Get the organization slug for an environment.

        Args:
            name: Environment name. If None, uses current environment.

        Returns:
            Organization slug, or None if environment not found or not configured.
        """
        if name is None:
            name = self.get_current_environment()

        if not name:
            return None

        config = self.load_config()
        env = config.get("environments", {}).get(name)
        return env.get("org_slug") if env else None

    def get_environment_ui_url(self, name: str | None = None) -> str | None:
        """Get the UI URL for an environment.

        Args:
            name: Environment name. If None, uses current environment.

        Returns:
            Custom UI URL, or None if using default (API URL without 'api.' subdomain).
        """
        if name is None:
            name = self.get_current_environment()

        if not name:
            return None

        config = self.load_config()
        env = config.get("environments", {}).get(name)
        return env.get("ui_url") if env else None

    def get_endpoint_id(self, name: str | None = None) -> str | None:
        """Get the endpoint ID for an environment.

        Args:
            name: Environment name. If None, uses current environment.

        Returns:
            Endpoint ID, or None if environment not found.
        """
        if name is None:
            name = self.get_current_environment()

        if not name:
            return None

        config = self.load_config()
        env = config.get("environments", {}).get(name)
        return env.get("endpoint_id") if env else None

    def get_environment_properties(self, name: str | None = None) -> dict[str, str]:
        """Get all properties for an environment (built-in + custom).

        Built-in properties are automatically exposed:
        - UNIFY_API: The API URL for the environment
        - ENDPOINT_ID: The endpoint ID for the environment

        Args:
            name: Environment name. If None, uses current environment.

        Returns:
            Dictionary of property name to value. Returns empty dict if environment not found.
        """
        if name is None:
            name = self.get_current_environment()

        if not name:
            return {}

        config = self.load_config()
        env = config.get("environments", {}).get(name)

        if not env:
            return {}

        # Start with built-in properties
        properties = {
            "UNIFY_API": env.get("url", ""),
            "ENDPOINT_ID": env.get("endpoint_id", ""),
        }

        # Merge in custom properties (they can override built-ins if needed)
        custom_properties = env.get("properties", {})
        properties.update(custom_properties)

        return properties

    def get_environment_uses_legacy_flags(self, name: str | None = None) -> bool:
        """Check if an environment uses legacy (org-based) or new (app-based) flag API.

        Args:
            name: Environment name. If None, uses current environment.

        Returns:
            True if environment uses legacy org-based flag API, False for app-based API.
            Returns False if environment not found.
        """
        from mimic.environments import get_preset_environment

        if name is None:
            name = self.get_current_environment()

        if not name:
            return False

        # Check if it's a preset environment first
        preset = get_preset_environment(name)
        if preset:
            return preset.use_legacy_flags

        # Check custom environment configuration
        config = self.load_config()
        env = config.get("environments", {}).get(name)
        if env:
            return env.get("use_legacy_flags", False)

        return False

    def set_environment_property(self, name: str, key: str, value: str) -> None:
        """Set a custom property for an environment.

        Args:
            name: Environment name.
            key: Property key.
            value: Property value.
        """
        config = self.load_config()

        if "environments" not in config or name not in config["environments"]:
            raise ValueError(f"Environment '{name}' not found")

        # Ensure properties dict exists
        if "properties" not in config["environments"][name]:
            config["environments"][name]["properties"] = {}

        config["environments"][name]["properties"][key] = value
        self.save_config(config)

    def unset_environment_property(self, name: str, key: str) -> None:
        """Remove a custom property from an environment.

        Args:
            name: Environment name.
            key: Property key to remove.
        """
        config = self.load_config()

        if "environments" not in config or name not in config["environments"]:
            raise ValueError(f"Environment '{name}' not found")

        properties = config["environments"][name].get("properties", {})
        if key in properties:
            del properties[key]
            self.save_config(config)

    # Credential management (keyring)
    def set_cloudbees_pat(self, env_name: str, pat: str) -> None:
        """Store CloudBees PAT securely in keyring.

        Args:
            env_name: Environment name.
            pat: Personal Access Token.

        Raises:
            KeyringUnavailableError: If keyring backend is not available.
        """
        try:
            keyring.set_password(self.KEYRING_SERVICE, f"cloudbees:{env_name}", pat)
        except Exception as e:
            instructions = get_keyring_setup_instructions()
            raise KeyringUnavailableError(
                f"Failed to store CloudBees PAT in keyring: {e}",
                instructions=instructions,
            ) from e

    def get_cloudbees_pat(self, env_name: str | None = None) -> str | None:
        """Retrieve CloudBees PAT from keyring.

        Args:
            env_name: Environment name. If None, uses current environment.

        Returns:
            PAT, or None if not found.

        Raises:
            KeyringUnavailableError: If keyring backend is not available.
        """
        if env_name is None:
            env_name = self.get_current_environment()

        if not env_name:
            return None

        try:
            return keyring.get_password(self.KEYRING_SERVICE, f"cloudbees:{env_name}")
        except Exception as e:
            instructions = get_keyring_setup_instructions()
            raise KeyringUnavailableError(
                f"Failed to retrieve CloudBees PAT from keyring: {e}",
                instructions=instructions,
            ) from e

    def delete_cloudbees_pat(self, env_name: str) -> None:
        """Delete CloudBees PAT from keyring.

        Args:
            env_name: Environment name.
        """
        try:
            keyring.delete_password(self.KEYRING_SERVICE, f"cloudbees:{env_name}")
        except Exception:
            pass  # Already deleted or never existed

    def set_github_pat(self, pat: str) -> None:
        """Store GitHub PAT securely in keyring.

        Args:
            pat: GitHub Personal Access Token.

        Raises:
            KeyringUnavailableError: If keyring backend is not available.
        """
        try:
            keyring.set_password(self.KEYRING_SERVICE, "github", pat)
        except Exception as e:
            instructions = get_keyring_setup_instructions()
            raise KeyringUnavailableError(
                f"Failed to store GitHub PAT in keyring: {e}",
                instructions=instructions,
            ) from e

    def get_github_pat(self) -> str | None:
        """Retrieve GitHub PAT from keyring.

        Returns:
            PAT, or None if not found.

        Raises:
            KeyringUnavailableError: If keyring backend is not available.
        """
        try:
            return keyring.get_password(self.KEYRING_SERVICE, "github")
        except Exception as e:
            instructions = get_keyring_setup_instructions()
            raise KeyringUnavailableError(
                f"Failed to retrieve GitHub PAT from keyring: {e}",
                instructions=instructions,
            ) from e

    def delete_github_pat(self) -> None:
        """Delete GitHub PAT from keyring."""
        try:
            keyring.delete_password(self.KEYRING_SERVICE, "github")
        except Exception:
            pass  # Already deleted or never existed

    def set_github_username(self, username: str) -> None:
        """Store GitHub default username in config.

        Args:
            username: GitHub username.
        """
        config = self.load_config()
        if "github" not in config:
            config["github"] = {}
        config["github"]["default_username"] = username
        self.save_config(config)

    def get_github_username(self) -> str | None:
        """Retrieve GitHub default username from config.

        Returns:
            GitHub username, or None if not set.
        """
        config = self.load_config()
        return config.get("github", {}).get("default_username")

    # Settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value.

        Args:
            key: Setting key.
            default: Default value if setting not found.

        Returns:
            Setting value or default.
        """
        config = self.load_config()
        return config.get("settings", {}).get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value.

        Args:
            key: Setting key.
            value: Setting value.
        """
        config = self.load_config()
        if "settings" not in config:
            config["settings"] = {}
        config["settings"][key] = value
        self.save_config(config)

    # First-run detection
    def is_first_run(self) -> bool:
        """Check if this is the first run (no config file exists).

        Returns:
            True if config file doesn't exist, False otherwise.
        """
        return not self.config_file.exists()

    # Scenario pack management
    def add_scenario_pack(
        self, name: str, url: str, branch: str = "main", enabled: bool = True
    ) -> None:
        """Add a scenario pack configuration.

        Args:
            name: Pack name (used as directory name).
            url: Git URL to clone from.
            branch: Git branch to use (default: main).
            enabled: Whether the pack is enabled (default: True).
        """
        config = self.load_config()

        if "scenario_packs" not in config:
            config["scenario_packs"] = {}

        config["scenario_packs"][name] = {
            "url": url,
            "branch": branch,
            "enabled": enabled,
        }

        self.save_config(config)

    def remove_scenario_pack(self, name: str) -> None:
        """Remove a scenario pack configuration.

        Args:
            name: Pack name to remove.
        """
        config = self.load_config()

        if "scenario_packs" in config and name in config["scenario_packs"]:
            del config["scenario_packs"][name]
            self.save_config(config)

    def list_scenario_packs(self) -> dict[str, dict[str, Any]]:
        """List all configured scenario packs.

        Returns:
            Dictionary of pack names to their configuration.
        """
        config = self.load_config()
        return config.get("scenario_packs", {})

    def get_scenario_pack(self, name: str) -> dict[str, Any] | None:
        """Get configuration for a specific scenario pack.

        Args:
            name: Pack name.

        Returns:
            Pack configuration, or None if not found.
        """
        config = self.load_config()
        return config.get("scenario_packs", {}).get(name)

    def set_scenario_pack_enabled(self, name: str, enabled: bool) -> None:
        """Enable or disable a scenario pack.

        Args:
            name: Pack name.
            enabled: Whether to enable the pack.
        """
        config = self.load_config()

        if "scenario_packs" not in config or name not in config["scenario_packs"]:
            raise ValueError(f"Scenario pack '{name}' not found")

        config["scenario_packs"][name]["enabled"] = enabled
        self.save_config(config)

    # Recent values management
    def add_recent_value(self, category: str, value: str, max_items: int = 10) -> None:
        """Add a recently used value to a category.

        Args:
            category: Category name (e.g., 'github_orgs').
            value: Value to add.
            max_items: Maximum number of recent items to keep (default: 10).
        """
        config = self.load_config()

        if "recent_values" not in config:
            config["recent_values"] = {}

        if category not in config["recent_values"]:
            config["recent_values"][category] = []

        # Remove existing occurrence if present
        if value in config["recent_values"][category]:
            config["recent_values"][category].remove(value)

        # Add to front
        config["recent_values"][category].insert(0, value)

        # Trim to max items
        config["recent_values"][category] = config["recent_values"][category][
            :max_items
        ]

        self.save_config(config)

    def get_recent_values(self, category: str) -> list[str]:
        """Get recently used values from a category.

        Args:
            category: Category name (e.g., 'github_orgs').

        Returns:
            List of recent values (most recent first).
        """
        config = self.load_config()
        return config.get("recent_values", {}).get(category, [])

    def cache_org_name(
        self, org_id: str, org_name: str, env_name: str | None = None
    ) -> None:
        """Cache a CloudBees organization name by ID for a specific environment.

        Args:
            org_id: Organization UUID.
            org_name: Organization name.
            env_name: Environment name. If None, uses current environment.
        """
        if env_name is None:
            env_name = self.get_current_environment()

        if not env_name:
            # No environment set, can't cache
            return

        config = self.load_config()

        if "recent_values" not in config:
            config["recent_values"] = {}

        if "cloudbees_orgs" not in config["recent_values"]:
            config["recent_values"]["cloudbees_orgs"] = {}

        if env_name not in config["recent_values"]["cloudbees_orgs"]:
            config["recent_values"]["cloudbees_orgs"][env_name] = {}

        config["recent_values"]["cloudbees_orgs"][env_name][org_id] = org_name
        self.save_config(config)

    def get_cached_org_name(
        self, org_id: str, env_name: str | None = None
    ) -> str | None:
        """Get cached CloudBees organization name by ID for a specific environment.

        Args:
            org_id: Organization UUID.
            env_name: Environment name. If None, uses current environment.

        Returns:
            Organization name if cached, None otherwise.
        """
        if env_name is None:
            env_name = self.get_current_environment()

        if not env_name:
            return None

        config = self.load_config()
        return (
            config.get("recent_values", {})
            .get("cloudbees_orgs", {})
            .get(env_name, {})
            .get(org_id)
        )

    def get_cached_orgs_for_env(self, env_name: str | None = None) -> dict[str, str]:
        """Get all cached CloudBees organizations for a specific environment.

        Args:
            env_name: Environment name. If None, uses current environment.

        Returns:
            Dictionary mapping org_id -> org_name for the environment.
        """
        if env_name is None:
            env_name = self.get_current_environment()

        if not env_name:
            return {}

        config = self.load_config()
        return (
            config.get("recent_values", {}).get("cloudbees_orgs", {}).get(env_name, {})
        )

    def ensure_official_pack_exists(self) -> bool:
        """Ensure the official scenario pack is configured and installed.

        If the official pack doesn't exist in the config, it will be added automatically
        and cloned from the repository. Users can disable it later if they prefer.

        Returns:
            True if the official pack was added, False if it already existed.
        """
        from .scenario_pack_manager import ScenarioPackManager
        from .settings import (
            OFFICIAL_PACK_BRANCH,
            OFFICIAL_PACK_NAME,
            OFFICIAL_PACK_URL,
        )

        config = self.load_config()
        packs = config.get("scenario_packs", {})

        # Check if official pack already exists in config
        if OFFICIAL_PACK_NAME in packs:
            return False

        # Add the official pack to config
        self.add_scenario_pack(
            name=OFFICIAL_PACK_NAME,
            url=OFFICIAL_PACK_URL,
            branch=OFFICIAL_PACK_BRANCH,
            enabled=True,
        )

        # Also clone the pack so it's actually installed
        try:
            pack_manager = ScenarioPackManager(self.packs_dir)
            pack_manager.clone_pack(
                name=OFFICIAL_PACK_NAME,
                url=OFFICIAL_PACK_URL,
                branch=OFFICIAL_PACK_BRANCH,
            )
            logger.info(
                f"Successfully cloned official scenario pack from {OFFICIAL_PACK_URL}"
            )
        except Exception as e:
            # Non-fatal: config is already saved, user can manually clone later
            logger.warning(
                f"Failed to clone official scenario pack: {e}. "
                f"Run 'mimic scenario-pack update {OFFICIAL_PACK_NAME}' to install it."
            )

        return True
