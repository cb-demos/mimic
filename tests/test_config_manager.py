"""Tests for ConfigManager - environment and credential management."""

from unittest.mock import MagicMock, patch

import pytest

from mimic.config_manager import ConfigManager


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory for testing."""
    config_dir = tmp_path / ".mimic"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def mock_keyring():
    """Mock keyring for testing credential storage."""
    with patch("mimic.config_manager.keyring") as mock:
        # Store credentials in memory for testing
        storage = {}

        def set_password(service, username, password):
            storage[f"{service}:{username}"] = password

        def get_password(service, username):
            return storage.get(f"{service}:{username}")

        def delete_password(service, username):
            key = f"{service}:{username}"
            if key in storage:
                del storage[key]

        mock.set_password = MagicMock(side_effect=set_password)
        mock.get_password = MagicMock(side_effect=get_password)
        mock.delete_password = MagicMock(side_effect=delete_password)

        yield mock


@pytest.fixture
def config_manager(temp_config_dir, mock_keyring, monkeypatch):
    """Create a ConfigManager instance with temporary config directory."""
    # Set environment variable to use temp directory
    monkeypatch.setenv("MIMIC_CONFIG_DIR", str(temp_config_dir))

    # Override class variables to pick up the env var
    # (Class variables are evaluated at import time, so we need to override them)
    ConfigManager.CONFIG_DIR = temp_config_dir
    ConfigManager.CONFIG_FILE = temp_config_dir / "config.yaml"
    ConfigManager.STATE_FILE = temp_config_dir / "state.json"

    manager = ConfigManager()
    return manager


class TestConfigManagerInitialization:
    """Test ConfigManager initialization and default behavior."""

    def test_ensures_config_directory_exists(self, config_manager, temp_config_dir):
        """Test that config directory is created on init."""
        assert temp_config_dir.exists()
        assert temp_config_dir.is_dir()

    def test_default_config_structure(self, config_manager):
        """Test default configuration structure."""
        config = config_manager.load_config()

        assert config["current_environment"] is None
        assert config["environments"] == {}
        assert config["github"]["default_username"] is None
        assert config["settings"]["default_expiration_days"] == 7
        assert config["settings"]["auto_cleanup_prompt"] is True

    def test_load_nonexistent_config_returns_default(self, config_manager):
        """Test loading config when file doesn't exist returns defaults."""
        # Config file shouldn't exist yet
        assert not config_manager.config_file.exists()

        config = config_manager.load_config()
        assert config["environments"] == {}


class TestEnvironmentManagement:
    """Test environment CRUD operations."""

    def test_add_environment(self, config_manager):
        """Test adding a new environment."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="test-pat-123",
            endpoint_id="endpoint-abc-123",
        )

        config = config_manager.load_config()
        assert "prod" in config["environments"]
        assert config["environments"]["prod"]["url"] == "https://api.cloudbees.io"
        assert config["environments"]["prod"]["endpoint_id"] == "endpoint-abc-123"

        # Should be set as current environment (first one added)
        assert config["current_environment"] == "prod"

    def test_add_multiple_environments(self, config_manager):
        """Test adding multiple environments."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat1",
            endpoint_id="endpoint1",
        )
        config_manager.add_environment(
            name="preprod",
            url="https://preprod.api.cloudbees.io",
            pat="pat2",
            endpoint_id="endpoint2",
        )
        config_manager.add_environment(
            name="demo",
            url="https://demo.api.cloudbees.io",
            pat="pat3",
            endpoint_id="endpoint3",
        )

        environments = config_manager.list_environments()
        assert len(environments) == 3
        assert "prod" in environments
        assert "preprod" in environments
        assert "demo" in environments

        # Current should still be first one added
        assert config_manager.get_current_environment() == "prod"

    def test_remove_environment(self, config_manager):
        """Test removing an environment."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat1",
            endpoint_id="endpoint1",
        )
        config_manager.add_environment(
            name="demo",
            url="https://demo.api.cloudbees.io",
            pat="pat2",
            endpoint_id="endpoint2",
        )

        config_manager.remove_environment("demo")

        environments = config_manager.list_environments()
        assert len(environments) == 1
        assert "demo" not in environments
        assert "prod" in environments

    def test_remove_current_environment_switches_to_another(self, config_manager):
        """Test that removing current environment switches to another."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat1",
            endpoint_id="endpoint1",
        )
        config_manager.add_environment(
            name="demo",
            url="https://demo.api.cloudbees.io",
            pat="pat2",
            endpoint_id="endpoint2",
        )

        # Current should be "prod" (first added)
        assert config_manager.get_current_environment() == "prod"

        # Remove current environment
        config_manager.remove_environment("prod")

        # Should switch to remaining environment
        assert config_manager.get_current_environment() == "demo"

    def test_remove_last_environment_sets_current_to_none(self, config_manager):
        """Test that removing the last environment sets current to None."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat1",
            endpoint_id="endpoint1",
        )

        config_manager.remove_environment("prod")

        assert config_manager.get_current_environment() is None
        assert len(config_manager.list_environments()) == 0

    def test_set_current_environment(self, config_manager):
        """Test switching current environment."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat1",
            endpoint_id="endpoint1",
        )
        config_manager.add_environment(
            name="demo",
            url="https://demo.api.cloudbees.io",
            pat="pat2",
            endpoint_id="endpoint2",
        )

        config_manager.set_current_environment("demo")
        assert config_manager.get_current_environment() == "demo"

        config_manager.set_current_environment("prod")
        assert config_manager.get_current_environment() == "prod"

    def test_get_environment_url(self, config_manager):
        """Test retrieving environment URL."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat1",
            endpoint_id="endpoint1",
        )
        config_manager.add_environment(
            name="demo",
            url="https://demo.api.cloudbees.io",
            pat="pat2",
            endpoint_id="endpoint2",
        )

        # Get specific environment URL
        assert config_manager.get_environment_url("prod") == "https://api.cloudbees.io"
        assert (
            config_manager.get_environment_url("demo")
            == "https://demo.api.cloudbees.io"
        )

        # Get current environment URL (should be prod)
        assert config_manager.get_environment_url() == "https://api.cloudbees.io"

    def test_get_endpoint_id(self, config_manager):
        """Test retrieving endpoint ID."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat1",
            endpoint_id="endpoint-prod-123",
        )

        assert config_manager.get_endpoint_id("prod") == "endpoint-prod-123"
        assert config_manager.get_endpoint_id() == "endpoint-prod-123"  # Current

    def test_get_environment_url_returns_none_for_nonexistent(self, config_manager):
        """Test that getting URL for nonexistent environment returns None."""
        assert config_manager.get_environment_url("nonexistent") is None
        assert config_manager.get_environment_url() is None  # No current environment


class TestCredentialManagement:
    """Test keyring integration for secure credential storage."""

    def test_store_and_retrieve_cloudbees_pat(self, config_manager, mock_keyring):
        """Test storing and retrieving CloudBees PAT."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="test-pat-123",
            endpoint_id="endpoint1",
        )

        # Verify keyring was called to store the PAT
        mock_keyring.set_password.assert_called_with(
            "mimic", "cloudbees:prod", "test-pat-123"
        )

        # Retrieve the PAT
        pat = config_manager.get_cloudbees_pat("prod")
        assert pat == "test-pat-123"

    def test_get_cloudbees_pat_for_current_environment(self, config_manager):
        """Test retrieving PAT for current environment."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat-prod",
            endpoint_id="endpoint1",
        )
        config_manager.add_environment(
            name="demo",
            url="https://demo.api.cloudbees.io",
            pat="pat-demo",
            endpoint_id="endpoint2",
        )

        config_manager.set_current_environment("demo")

        # Get PAT without specifying environment (should use current)
        pat = config_manager.get_cloudbees_pat()
        assert pat == "pat-demo"

    def test_delete_cloudbees_pat(self, config_manager, mock_keyring):
        """Test deleting CloudBees PAT from keyring."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="test-pat",
            endpoint_id="endpoint1",
        )

        # Delete the PAT
        config_manager.delete_cloudbees_pat("prod")

        # Verify keyring delete was called
        mock_keyring.delete_password.assert_called_with("mimic", "cloudbees:prod")

        # PAT should be gone
        assert config_manager.get_cloudbees_pat("prod") is None

    def test_remove_environment_deletes_pat(self, config_manager, mock_keyring):
        """Test that removing environment also deletes its PAT."""
        config_manager.add_environment(
            name="demo",
            url="https://demo.api.cloudbees.io",
            pat="demo-pat",
            endpoint_id="endpoint1",
        )

        config_manager.remove_environment("demo")

        # Verify PAT was deleted from keyring
        mock_keyring.delete_password.assert_called_with("mimic", "cloudbees:demo")

    def test_github_pat_storage(self, config_manager, mock_keyring):
        """Test storing and retrieving GitHub PAT."""
        config_manager.set_github_pat("github-pat-xyz")

        mock_keyring.set_password.assert_called_with(
            "mimic", "github", "github-pat-xyz"
        )

        pat = config_manager.get_github_pat()
        assert pat == "github-pat-xyz"

    def test_delete_github_pat(self, config_manager, mock_keyring):
        """Test deleting GitHub PAT."""
        config_manager.set_github_pat("github-pat")
        config_manager.delete_github_pat()

        mock_keyring.delete_password.assert_called_with("mimic", "github")
        assert config_manager.get_github_pat() is None


class TestSettingsManagement:
    """Test settings management."""

    def test_get_default_settings(self, config_manager):
        """Test retrieving default settings."""
        assert config_manager.get_setting("default_expiration_days") == 7
        assert config_manager.get_setting("auto_cleanup_prompt") is True

    def test_get_setting_with_default(self, config_manager):
        """Test getting setting that doesn't exist returns default."""
        assert (
            config_manager.get_setting("nonexistent", "default_value")
            == "default_value"
        )

    def test_set_setting(self, config_manager):
        """Test setting a value."""
        config_manager.set_setting("default_expiration_days", 14)
        assert config_manager.get_setting("default_expiration_days") == 14

        config_manager.set_setting("auto_cleanup_prompt", False)
        assert config_manager.get_setting("auto_cleanup_prompt") is False

    def test_settings_persist_across_loads(self, config_manager):
        """Test that settings persist when config is reloaded."""
        config_manager.set_setting("default_expiration_days", 30)

        # Create a new manager instance pointing to same config
        manager2 = ConfigManager()
        manager2.config_dir = config_manager.config_dir
        manager2.config_file = config_manager.config_file
        manager2.state_file = config_manager.state_file

        assert manager2.get_setting("default_expiration_days") == 30


class TestConfigPersistence:
    """Test configuration file persistence."""

    def test_config_file_created_on_save(self, config_manager):
        """Test that config file is created when environment is added."""
        assert not config_manager.config_file.exists()

        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat",
            endpoint_id="endpoint1",
        )

        assert config_manager.config_file.exists()

    def test_config_persists_across_instances(self, config_manager, mock_keyring):
        """Test that config persists when creating new manager instance."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat1",
            endpoint_id="endpoint1",
        )
        config_manager.add_environment(
            name="demo",
            url="https://demo.api.cloudbees.io",
            pat="pat2",
            endpoint_id="endpoint2",
        )

        # Create new manager pointing to same directory
        manager2 = ConfigManager()
        manager2.config_dir = config_manager.config_dir
        manager2.config_file = config_manager.config_file
        manager2.state_file = config_manager.state_file

        environments = manager2.list_environments()
        assert len(environments) == 2
        assert "prod" in environments
        assert "demo" in environments
        assert manager2.get_current_environment() == "prod"

    def test_empty_config_file_returns_defaults(self, config_manager, temp_config_dir):
        """Test that empty config file returns default config."""
        # Create empty config file
        config_manager.config_file.write_text("")

        config = config_manager.load_config()
        assert config["environments"] == {}
        assert config["current_environment"] is None


class TestFirstRunDetection:
    """Test first-run detection functionality."""

    def test_is_first_run_returns_true_when_no_config_file(self, config_manager):
        """Test that is_first_run returns True when config file doesn't exist."""
        # Config file shouldn't exist yet
        assert not config_manager.config_file.exists()

        # Should be first run
        assert config_manager.is_first_run() is True

    def test_is_first_run_returns_false_after_config_created(self, config_manager):
        """Test that is_first_run returns False after config is created."""
        # Create config by adding environment
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat",
            endpoint_id="endpoint1",
        )

        # Config file should now exist
        assert config_manager.config_file.exists()

        # Should no longer be first run
        assert config_manager.is_first_run() is False

    def test_is_first_run_returns_false_with_empty_config_file(self, config_manager):
        """Test that is_first_run returns False even with empty config file."""
        # Create empty config file
        config_manager.config_file.write_text("")

        # File exists, so not first run
        assert config_manager.is_first_run() is False


class TestRecentValuesManagement:
    """Test recent values caching functionality."""

    def test_add_recent_value(self, config_manager):
        """Test adding a recent value to a category."""
        config_manager.add_recent_value("github_orgs", "acme-corp")

        recent = config_manager.get_recent_values("github_orgs")
        assert recent == ["acme-corp"]

    def test_add_multiple_recent_values(self, config_manager):
        """Test adding multiple recent values."""
        config_manager.add_recent_value("github_orgs", "acme-corp")
        config_manager.add_recent_value("github_orgs", "example-org")
        config_manager.add_recent_value("github_orgs", "test-org")

        recent = config_manager.get_recent_values("github_orgs")
        # Should be in MRU order (most recent first)
        assert recent == ["test-org", "example-org", "acme-corp"]

    def test_recent_value_mru_order(self, config_manager):
        """Test that re-adding a value moves it to front (MRU)."""
        config_manager.add_recent_value("github_orgs", "acme-corp")
        config_manager.add_recent_value("github_orgs", "example-org")
        config_manager.add_recent_value("github_orgs", "test-org")

        # Re-add acme-corp, should move to front
        config_manager.add_recent_value("github_orgs", "acme-corp")

        recent = config_manager.get_recent_values("github_orgs")
        assert recent == ["acme-corp", "test-org", "example-org"]

    def test_recent_values_max_items(self, config_manager):
        """Test that recent values are limited to max_items."""
        # Add 12 items with max of 10
        for i in range(12):
            config_manager.add_recent_value("github_orgs", f"org-{i}", max_items=10)

        recent = config_manager.get_recent_values("github_orgs")
        # Should only keep the 10 most recent
        assert len(recent) == 10
        assert recent[0] == "org-11"  # Most recent
        assert recent[-1] == "org-2"  # 10th most recent

    def test_get_recent_values_empty(self, config_manager):
        """Test getting recent values from empty category."""
        recent = config_manager.get_recent_values("nonexistent_category")
        assert recent == []

    def test_cache_org_name(self, config_manager):
        """Test caching CloudBees organization name."""
        # Set up environment first
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat",
            endpoint_id="endpoint1",
        )

        config_manager.cache_org_name("abc-123-def", "Acme Corporation", "prod")

        name = config_manager.get_cached_org_name("abc-123-def", "prod")
        assert name == "Acme Corporation"

    def test_cache_multiple_org_names(self, config_manager):
        """Test caching multiple organization names."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat",
            endpoint_id="endpoint1",
        )

        config_manager.cache_org_name("abc-123-def", "Acme Corporation", "prod")
        config_manager.cache_org_name("xyz-789-ghi", "Example Inc", "prod")
        config_manager.cache_org_name("def-456-jkl", "Test Ltd", "prod")

        assert (
            config_manager.get_cached_org_name("abc-123-def", "prod")
            == "Acme Corporation"
        )
        assert (
            config_manager.get_cached_org_name("xyz-789-ghi", "prod") == "Example Inc"
        )
        assert config_manager.get_cached_org_name("def-456-jkl", "prod") == "Test Ltd"

    def test_get_cached_org_name_nonexistent(self, config_manager):
        """Test getting cached org name that doesn't exist."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat",
            endpoint_id="endpoint1",
        )

        name = config_manager.get_cached_org_name("nonexistent-id", "prod")
        assert name is None

    def test_cache_org_name_overwrites_existing(self, config_manager):
        """Test that caching org name overwrites existing entry."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat",
            endpoint_id="endpoint1",
        )

        config_manager.cache_org_name("abc-123-def", "Old Name", "prod")
        config_manager.cache_org_name("abc-123-def", "New Name", "prod")

        name = config_manager.get_cached_org_name("abc-123-def", "prod")
        assert name == "New Name"

    def test_cache_org_name_environment_specific(self, config_manager):
        """Test that cached org names are environment-specific."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat1",
            endpoint_id="endpoint1",
        )
        config_manager.add_environment(
            name="demo",
            url="https://demo.api.cloudbees.io",
            pat="pat2",
            endpoint_id="endpoint2",
        )

        # Same org ID, different names in different environments
        config_manager.cache_org_name("abc-123", "Prod Org", "prod")
        config_manager.cache_org_name("abc-123", "Demo Org", "demo")

        # Should get different names for different environments
        assert config_manager.get_cached_org_name("abc-123", "prod") == "Prod Org"
        assert config_manager.get_cached_org_name("abc-123", "demo") == "Demo Org"

    def test_get_cached_orgs_for_env(self, config_manager):
        """Test getting all cached orgs for an environment."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat",
            endpoint_id="endpoint1",
        )

        config_manager.cache_org_name("abc-123", "Acme Corp", "prod")
        config_manager.cache_org_name("xyz-789", "Example Inc", "prod")

        cached_orgs = config_manager.get_cached_orgs_for_env("prod")
        assert cached_orgs == {
            "abc-123": "Acme Corp",
            "xyz-789": "Example Inc",
        }

    def test_get_cached_orgs_for_env_empty(self, config_manager):
        """Test getting cached orgs for environment with no cached orgs."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat",
            endpoint_id="endpoint1",
        )

        cached_orgs = config_manager.get_cached_orgs_for_env("prod")
        assert cached_orgs == {}

    def test_recent_values_persist(self, config_manager):
        """Test that recent values persist across config loads."""
        config_manager.add_environment(
            name="prod",
            url="https://api.cloudbees.io",
            pat="pat",
            endpoint_id="endpoint1",
        )
        config_manager.add_recent_value("github_orgs", "acme-corp")
        config_manager.cache_org_name("abc-123", "Acme Corp", "prod")

        # Create new manager pointing to same config
        manager2 = ConfigManager()
        manager2.config_dir = config_manager.config_dir
        manager2.config_file = config_manager.config_file
        manager2.state_file = config_manager.state_file

        recent = manager2.get_recent_values("github_orgs")
        assert recent == ["acme-corp"]

        cached_name = manager2.get_cached_org_name("abc-123", "prod")
        assert cached_name == "Acme Corp"


class TestEnvironmentPropertiesManagement:
    """Test environment properties functionality."""

    @pytest.fixture
    def env_config_manager(self, temp_config_dir, mock_keyring, monkeypatch):
        """Create ConfigManager with temporary directory and mocked keyring."""
        monkeypatch.setenv("MIMIC_CONFIG_DIR", str(temp_config_dir))

        ConfigManager.CONFIG_DIR = temp_config_dir
        ConfigManager.CONFIG_FILE = temp_config_dir / "config.yaml"
        ConfigManager.STATE_FILE = temp_config_dir / "state.json"

        return ConfigManager()

    def test_add_environment_with_properties(self, env_config_manager):
        """Test adding environment with custom properties."""
        properties = {"USE_VPC": "true", "FM_INSTANCE": "demo1.cloudbees.io"}

        env_config_manager.add_environment(
            name="demo",
            url="https://api.demo1.cloudbees.io",
            pat="test-pat",
            endpoint_id="endpoint-123",
            properties=properties,
        )

        # Verify properties were saved
        config = env_config_manager.load_config()
        assert "properties" in config["environments"]["demo"]
        assert config["environments"]["demo"]["properties"] == properties

    def test_get_environment_properties_built_in(self, env_config_manager):
        """Test that built-in properties are automatically exposed."""
        env_config_manager.add_environment(
            name="demo",
            url="https://api.demo1.cloudbees.io",
            pat="test-pat",
            endpoint_id="endpoint-123",
        )

        props = env_config_manager.get_environment_properties("demo")

        # Built-in properties should be present
        assert "UNIFY_API" in props
        assert props["UNIFY_API"] == "https://api.demo1.cloudbees.io"
        assert "ENDPOINT_ID" in props
        assert props["ENDPOINT_ID"] == "endpoint-123"

    def test_get_environment_properties_custom(self, env_config_manager):
        """Test getting custom environment properties."""
        custom_props = {"USE_VPC": "true", "FM_INSTANCE": "demo1.cloudbees.io"}

        env_config_manager.add_environment(
            name="demo",
            url="https://api.demo1.cloudbees.io",
            pat="test-pat",
            endpoint_id="endpoint-123",
            properties=custom_props,
        )

        props = env_config_manager.get_environment_properties("demo")

        # Should have both built-in and custom properties
        assert props["UNIFY_API"] == "https://api.demo1.cloudbees.io"
        assert props["ENDPOINT_ID"] == "endpoint-123"
        assert props["USE_VPC"] == "true"
        assert props["FM_INSTANCE"] == "demo1.cloudbees.io"

    def test_set_environment_property(self, env_config_manager):
        """Test setting a property on an existing environment."""
        env_config_manager.add_environment(
            name="demo",
            url="https://api.demo1.cloudbees.io",
            pat="test-pat",
            endpoint_id="endpoint-123",
        )

        env_config_manager.set_environment_property(
            "demo", "CUSTOM_KEY", "custom_value"
        )

        props = env_config_manager.get_environment_properties("demo")
        assert props["CUSTOM_KEY"] == "custom_value"

    def test_set_environment_property_on_nonexistent_environment(
        self, env_config_manager
    ):
        """Test that setting property on nonexistent environment raises error."""
        with pytest.raises(ValueError, match="Environment 'nonexistent' not found"):
            env_config_manager.set_environment_property("nonexistent", "KEY", "value")

    def test_unset_environment_property(self, env_config_manager):
        """Test removing a property from an environment."""
        custom_props = {"USE_VPC": "true", "FM_INSTANCE": "demo1.cloudbees.io"}

        env_config_manager.add_environment(
            name="demo",
            url="https://api.demo1.cloudbees.io",
            pat="test-pat",
            endpoint_id="endpoint-123",
            properties=custom_props,
        )

        # Verify property exists
        props = env_config_manager.get_environment_properties("demo")
        assert "USE_VPC" in props

        # Remove it
        env_config_manager.unset_environment_property("demo", "USE_VPC")

        # Verify it's gone
        props = env_config_manager.get_environment_properties("demo")
        assert "USE_VPC" not in props
        # But other properties remain
        assert "FM_INSTANCE" in props

    def test_unset_environment_property_on_nonexistent_environment(
        self, env_config_manager
    ):
        """Test that unsetting property on nonexistent environment raises error."""
        with pytest.raises(ValueError, match="Environment 'nonexistent' not found"):
            env_config_manager.unset_environment_property("nonexistent", "KEY")

    def test_get_environment_properties_empty_when_no_environment(
        self, env_config_manager
    ):
        """Test that getting properties for nonexistent env returns empty dict."""
        props = env_config_manager.get_environment_properties("nonexistent")
        assert props == {}

    def test_get_environment_properties_current_environment(self, env_config_manager):
        """Test getting properties for current environment (None parameter)."""
        custom_props = {"USE_VPC": "true"}

        env_config_manager.add_environment(
            name="demo",
            url="https://api.demo1.cloudbees.io",
            pat="test-pat",
            endpoint_id="endpoint-123",
            properties=custom_props,
        )
        env_config_manager.set_current_environment("demo")

        # Get properties without specifying environment name
        props = env_config_manager.get_environment_properties()
        assert props["USE_VPC"] == "true"
        assert props["UNIFY_API"] == "https://api.demo1.cloudbees.io"

    def test_environment_properties_persist_across_loads(self, env_config_manager):
        """Test that properties persist when config is reloaded."""
        custom_props = {"USE_VPC": "true", "FM_INSTANCE": "demo1.cloudbees.io"}

        env_config_manager.add_environment(
            name="demo",
            url="https://api.demo1.cloudbees.io",
            pat="test-pat",
            endpoint_id="endpoint-123",
            properties=custom_props,
        )

        # Create new manager instance pointing to same config
        manager2 = ConfigManager()
        manager2.CONFIG_DIR = env_config_manager.CONFIG_DIR
        manager2.CONFIG_FILE = env_config_manager.CONFIG_FILE

        # Properties should still be there
        props = manager2.get_environment_properties("demo")
        assert props["USE_VPC"] == "true"
        assert props["FM_INSTANCE"] == "demo1.cloudbees.io"
