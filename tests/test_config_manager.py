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
            "prod", "https://api.cloudbees.io", "pat1", "endpoint1"
        )
        config_manager.add_environment(
            "preprod", "https://preprod.api.cloudbees.io", "pat2", "endpoint2"
        )
        config_manager.add_environment(
            "demo", "https://demo.api.cloudbees.io", "pat3", "endpoint3"
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
            "prod", "https://api.cloudbees.io", "pat1", "endpoint1"
        )
        config_manager.add_environment(
            "demo", "https://demo.api.cloudbees.io", "pat2", "endpoint2"
        )

        config_manager.remove_environment("demo")

        environments = config_manager.list_environments()
        assert len(environments) == 1
        assert "demo" not in environments
        assert "prod" in environments

    def test_remove_current_environment_switches_to_another(self, config_manager):
        """Test that removing current environment switches to another."""
        config_manager.add_environment(
            "prod", "https://api.cloudbees.io", "pat1", "endpoint1"
        )
        config_manager.add_environment(
            "demo", "https://demo.api.cloudbees.io", "pat2", "endpoint2"
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
            "prod", "https://api.cloudbees.io", "pat1", "endpoint1"
        )

        config_manager.remove_environment("prod")

        assert config_manager.get_current_environment() is None
        assert len(config_manager.list_environments()) == 0

    def test_set_current_environment(self, config_manager):
        """Test switching current environment."""
        config_manager.add_environment(
            "prod", "https://api.cloudbees.io", "pat1", "endpoint1"
        )
        config_manager.add_environment(
            "demo", "https://demo.api.cloudbees.io", "pat2", "endpoint2"
        )

        config_manager.set_current_environment("demo")
        assert config_manager.get_current_environment() == "demo"

        config_manager.set_current_environment("prod")
        assert config_manager.get_current_environment() == "prod"

    def test_get_environment_url(self, config_manager):
        """Test retrieving environment URL."""
        config_manager.add_environment(
            "prod", "https://api.cloudbees.io", "pat1", "endpoint1"
        )
        config_manager.add_environment(
            "demo", "https://demo.api.cloudbees.io", "pat2", "endpoint2"
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
            "prod", "https://api.cloudbees.io", "pat1", "endpoint-prod-123"
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
            "prod", "https://api.cloudbees.io", "test-pat-123", "endpoint1"
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
            "prod", "https://api.cloudbees.io", "pat-prod", "endpoint1"
        )
        config_manager.add_environment(
            "demo", "https://demo.api.cloudbees.io", "pat-demo", "endpoint2"
        )

        config_manager.set_current_environment("demo")

        # Get PAT without specifying environment (should use current)
        pat = config_manager.get_cloudbees_pat()
        assert pat == "pat-demo"

    def test_delete_cloudbees_pat(self, config_manager, mock_keyring):
        """Test deleting CloudBees PAT from keyring."""
        config_manager.add_environment(
            "prod", "https://api.cloudbees.io", "test-pat", "endpoint1"
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
            "demo", "https://demo.api.cloudbees.io", "demo-pat", "endpoint1"
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
            "prod", "https://api.cloudbees.io", "pat", "endpoint1"
        )

        assert config_manager.config_file.exists()

    def test_config_persists_across_instances(self, config_manager, mock_keyring):
        """Test that config persists when creating new manager instance."""
        config_manager.add_environment(
            "prod", "https://api.cloudbees.io", "pat1", "endpoint1"
        )
        config_manager.add_environment(
            "demo", "https://demo.api.cloudbees.io", "pat2", "endpoint2"
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
            "prod", "https://api.cloudbees.io", "pat", "endpoint1"
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
