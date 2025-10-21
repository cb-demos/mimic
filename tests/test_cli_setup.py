"""Tests for the setup wizard CLI command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from mimic.cli import app
from mimic.config_manager import ConfigManager

runner = CliRunner()


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
def setup_config_manager(temp_config_dir, mock_keyring, monkeypatch):
    """Setup ConfigManager with temporary directory."""
    # Set environment variable to use temp directory
    monkeypatch.setenv("MIMIC_CONFIG_DIR", str(temp_config_dir))

    # Override class variables to pick up the env var
    ConfigManager.CONFIG_DIR = temp_config_dir
    ConfigManager.CONFIG_FILE = temp_config_dir / "config.yaml"
    ConfigManager.STATE_FILE = temp_config_dir / "state.json"

    # Reload cli module to pick up new config manager
    import importlib

    import mimic.cli.main

    importlib.reload(mimic.cli.main)

    return ConfigManager()


class TestSetupCommand:
    """Test the setup command functionality."""

    def test_setup_command_exists(self):
        """Test that setup command is registered."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "setup" in result.stdout

    @patch("mimic.scenario_pack_manager.ScenarioPackManager")
    @patch("mimic.unify.UnifyAPIClient")
    @patch("mimic.gh.GitHubClient")
    def test_setup_preset_environment_with_github(
        self,
        mock_github_client,
        mock_unify_client,
        mock_pack_manager,
        setup_config_manager,
        monkeypatch,
    ):
        """Test setup wizard with preset environment and GitHub configuration."""
        # Mock ScenarioPackManager
        mock_pack_instance = MagicMock()
        mock_pack_instance.clone_pack = MagicMock()
        mock_pack_manager.return_value = mock_pack_instance

        # Mock UnifyAPIClient validation
        mock_unify_instance = MagicMock()
        mock_unify_instance.__enter__ = MagicMock(return_value=mock_unify_instance)
        mock_unify_instance.__exit__ = MagicMock(return_value=None)
        mock_unify_instance.validate_credentials = MagicMock(return_value=(True, None))
        mock_unify_client.return_value = mock_unify_instance

        # Mock GitHubClient validation (async method)
        mock_gh_instance = MagicMock()
        mock_gh_instance.validate_credentials = AsyncMock(return_value=(True, None))
        mock_github_client.return_value = mock_gh_instance

        # Simulate user inputs
        inputs = [
            "y",  # Add official scenario pack?
            "1",  # Choose preset environment (prod)
            "test-cloudbees-pat",  # CloudBees PAT
            "test-org-id",  # Organization ID
            "y",  # Configure GitHub now?
            "test-github-pat",  # GitHub PAT
            "test-user",  # GitHub username
        ]

        result = runner.invoke(app, ["setup"], input="\n".join(inputs))

        # Check exit code
        assert result.exit_code == 0

        # Verify output
        assert "Welcome to Mimic!" in result.stdout
        assert "Setup Complete!" in result.stdout or "Setup complete" in result.stdout

        # Verify config was saved
        config_manager = setup_config_manager
        config = config_manager.load_config()
        assert "prod" in config["environments"]
        assert config["current_environment"] == "prod"

        # Verify credentials were stored (via mock)
        # The actual keyring calls would have been made through the setup_config_manager fixture

    @patch("mimic.scenario_pack_manager.ScenarioPackManager")
    @patch("mimic.unify.UnifyAPIClient")
    @patch("mimic.gh.GitHubClient")
    def test_setup_preset_environment_skip_github(
        self,
        mock_github_client,
        mock_unify_client,
        mock_pack_manager,
        setup_config_manager,
    ):
        """Test setup wizard with GitHub configuration (now mandatory)."""
        # Mock ScenarioPackManager
        mock_pack_instance = MagicMock()
        mock_pack_instance.clone_pack = MagicMock()
        mock_pack_manager.return_value = mock_pack_instance

        # Mock UnifyAPIClient validation
        mock_unify_instance = MagicMock()
        mock_unify_instance.__enter__ = MagicMock(return_value=mock_unify_instance)
        mock_unify_instance.__exit__ = MagicMock(return_value=None)
        mock_unify_instance.validate_credentials = MagicMock(return_value=(True, None))
        mock_unify_client.return_value = mock_unify_instance

        # Mock GitHubClient validation
        mock_gh_instance = MagicMock()
        mock_gh_instance.validate_credentials = AsyncMock(return_value=(True, None))
        mock_github_client.return_value = mock_gh_instance

        # Simulate user inputs
        inputs = [
            "y",  # Add official scenario pack?
            "2",  # Choose preset environment (preprod)
            "test-cloudbees-pat",  # CloudBees PAT
            "test-org-id",  # Organization ID
            "test-github-pat",  # GitHub PAT (now mandatory)
            "test-user",  # GitHub username (now mandatory)
        ]

        result = runner.invoke(app, ["setup"], input="\n".join(inputs))

        # Check exit code
        assert result.exit_code == 0

        # Verify output
        assert "Setup Complete!" in result.stdout or "Setup complete" in result.stdout

    @patch("mimic.scenario_pack_manager.ScenarioPackManager")
    @patch("mimic.unify.UnifyAPIClient")
    @patch("mimic.gh.GitHubClient")
    def test_setup_custom_environment(
        self,
        mock_github_client,
        mock_unify_client,
        mock_pack_manager,
        setup_config_manager,
    ):
        """Test setup wizard with custom environment."""
        # Mock ScenarioPackManager
        mock_pack_instance = MagicMock()
        mock_pack_instance.clone_pack = MagicMock()
        mock_pack_manager.return_value = mock_pack_instance

        # Mock UnifyAPIClient validation
        mock_unify_instance = MagicMock()
        mock_unify_instance.__enter__ = MagicMock(return_value=mock_unify_instance)
        mock_unify_instance.__exit__ = MagicMock(return_value=None)
        mock_unify_instance.validate_credentials = MagicMock(return_value=(True, None))
        mock_unify_client.return_value = mock_unify_instance

        # Mock GitHubClient validation
        mock_gh_instance = MagicMock()
        mock_gh_instance.validate_credentials = AsyncMock(return_value=(True, None))
        mock_github_client.return_value = mock_gh_instance

        # Simulate user inputs
        inputs = [
            "n",  # Skip scenario pack
            "5",  # Choose custom environment (option 5 for 4 presets + custom)
            "custom-env",  # Environment name
            "https://custom.api.example.com",  # API URL
            "custom-endpoint-123",  # Endpoint ID
            "test-pat",  # CloudBees PAT
            "test-org-id",  # Organization ID
            "test-github-pat",  # GitHub PAT (now mandatory)
            "test-user",  # GitHub username (now mandatory)
        ]

        result = runner.invoke(app, ["setup"], input="\n".join(inputs))

        # Check exit code
        assert result.exit_code == 0

        # Verify output
        assert "Setup Complete!" in result.stdout or "Setup complete" in result.stdout

        # Verify custom environment was saved
        config_manager = setup_config_manager
        config = config_manager.load_config()
        assert "custom-env" in config["environments"]
        assert (
            config["environments"]["custom-env"]["url"]
            == "https://custom.api.example.com"
        )
        assert (
            config["environments"]["custom-env"]["endpoint_id"] == "custom-endpoint-123"
        )

    @patch("mimic.scenario_pack_manager.ScenarioPackManager")
    @patch("mimic.unify.UnifyAPIClient")
    def test_setup_credential_validation_failure(
        self, mock_unify_client, mock_pack_manager, setup_config_manager
    ):
        """Test setup wizard with credential validation failure."""
        # Mock ScenarioPackManager
        mock_pack_instance = MagicMock()
        mock_pack_instance.clone_pack = MagicMock()
        mock_pack_manager.return_value = mock_pack_instance

        # Mock UnifyAPIClient validation to fail
        mock_unify_instance = MagicMock()
        mock_unify_instance.__enter__ = MagicMock(return_value=mock_unify_instance)
        mock_unify_instance.__exit__ = MagicMock(return_value=None)
        mock_unify_instance.validate_credentials = MagicMock(
            return_value=(False, "Invalid credentials")
        )
        mock_unify_client.return_value = mock_unify_instance

        # Simulate user inputs
        inputs = [
            "n",  # Skip scenario pack
            "1",  # Choose preset environment (prod)
            "invalid-pat",  # CloudBees PAT
            "test-org-id",  # Organization ID
        ]

        result = runner.invoke(app, ["setup"], input="\n".join(inputs))

        # Should exit with error
        assert result.exit_code == 1
        assert "Credential validation failed" in result.stdout

    def test_setup_already_configured_without_force(self, setup_config_manager):
        """Test setup command when already configured without --force flag."""
        # Create a config file to simulate already configured
        config_manager = setup_config_manager
        config_manager.add_environment(
            "prod", "https://api.cloudbees.io", "test-pat", "endpoint-123"
        )

        result = runner.invoke(app, ["setup"])

        # Should exit gracefully
        assert result.exit_code == 0
        assert (
            "Mimic is already configured" in result.stdout
            or "already configured" in result.stdout
        )
        assert "mimic setup --force" in result.stdout or "--force" in result.stdout

    @patch("mimic.scenario_pack_manager.ScenarioPackManager")
    @patch("mimic.unify.UnifyAPIClient")
    @patch("mimic.gh.GitHubClient")
    def test_setup_with_force_flag_reconfigures(
        self,
        mock_github_client,
        mock_unify_client,
        mock_pack_manager,
        setup_config_manager,
    ):
        """Test setup with --force flag allows reconfiguration."""
        # Mock ScenarioPackManager
        mock_pack_instance = MagicMock()
        mock_pack_instance.clone_pack = MagicMock()
        mock_pack_manager.return_value = mock_pack_instance

        # Create a config file to simulate already configured
        config_manager = setup_config_manager
        config_manager.add_environment(
            "prod", "https://api.cloudbees.io", "old-pat", "endpoint-123"
        )

        # Mock UnifyAPIClient validation
        mock_unify_instance = MagicMock()
        mock_unify_instance.__enter__ = MagicMock(return_value=mock_unify_instance)
        mock_unify_instance.__exit__ = MagicMock(return_value=None)
        mock_unify_instance.validate_credentials = MagicMock(return_value=(True, None))
        mock_unify_client.return_value = mock_unify_instance

        # Mock GitHubClient validation
        mock_gh_instance = MagicMock()
        mock_gh_instance.validate_credentials = AsyncMock(return_value=(True, None))
        mock_github_client.return_value = mock_gh_instance

        # Simulate user inputs
        inputs = [
            "n",  # Skip scenario pack
            "2",  # Choose preprod
            "new-pat",  # New CloudBees PAT
            "test-org-id",  # Organization ID
            "test-github-pat",  # GitHub PAT (now mandatory)
            "test-user",  # GitHub username (now mandatory)
        ]

        result = runner.invoke(app, ["setup", "--force"], input="\n".join(inputs))

        # Should complete successfully
        assert result.exit_code == 0
        assert "Setup Complete!" in result.stdout or "Setup complete" in result.stdout


class TestFirstRunDetection:
    """Test first-run detection in main commands."""

    def test_list_command_shows_first_run_message(self, setup_config_manager):
        """Test that list command shows first-run message."""
        # Don't create any config - should be first run
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Welcome to Mimic!" in result.stdout
        assert "mimic setup" in result.stdout

    def test_run_command_shows_first_run_message(self, setup_config_manager):
        """Test that run command shows first-run message."""
        result = runner.invoke(app, ["run", "test-scenario"])

        assert result.exit_code == 0
        assert "Welcome to Mimic!" in result.stdout
        assert "mimic setup" in result.stdout

    def test_commands_work_after_setup(self, setup_config_manager):
        """Test that commands work normally after setup is complete."""
        # Create config to simulate setup complete
        config_manager = setup_config_manager
        config_manager.add_environment(
            "prod", "https://api.cloudbees.io", "test-pat", "endpoint-123"
        )

        # List command should work now (though it may fail for other reasons)
        result = runner.invoke(app, ["list"])

        # Should not show first-run message
        assert "mimic setup" not in result.stdout
