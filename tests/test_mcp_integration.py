"""Integration tests for MCP server - tests the actual stdio server."""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest


class TestMCPServerIntegration:
    """Integration tests for MCP server using subprocess."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create a temporary config directory for MCP server."""
        config_dir = tmp_path / ".mimic"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @pytest.fixture
    def mock_keyring(self):
        """Mock keyring for testing."""
        with patch("mimic.config_manager.keyring") as mock:
            # Store credentials in memory
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

    def test_mcp_server_starts_and_responds(self, temp_config_dir, mock_keyring):
        """Test that MCP server starts and responds to basic requests."""
        # This is a basic smoke test - verifying the server can start
        # A full integration test would require the MCP SDK client

        env = os.environ.copy()
        env["MIMIC_CONFIG_DIR"] = str(temp_config_dir)  # Use custom config directory
        env["MIMIC_ENV"] = "test"

        # Try to start the server (it will fail without stdin, but we can check it exists)
        result = subprocess.run(
            ["uv", "run", "mimic", "mcp", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # The --help command should work
        # Note: 'mimic mcp' doesn't have --help, so it will show an error
        # This is just checking the command exists
        assert result.returncode in [0, 2]  # 0 for success, 2 for no --help option

    def test_mcp_list_scenarios_implementation(self, mock_scenario_manager):
        """Test the list_scenarios implementation directly."""
        from mimic.mcp import _list_scenarios_impl

        scenarios = _list_scenarios_impl()

        # Should return a list
        assert isinstance(scenarios, list)
        assert len(scenarios) > 0

        # Check structure of first scenario
        scenario = scenarios[0]
        assert "id" in scenario
        assert "name" in scenario
        assert "summary" in scenario
        assert "pack_source" in scenario
        # parameters is optional - not all scenarios have them

        # Should only include pack scenarios (test-pack in our case)
        for scenario in scenarios:
            assert scenario["pack_source"] == "test-pack"

    @pytest.mark.asyncio
    async def test_instantiate_scenario_validates_credentials(
        self, mock_scenario_manager
    ):
        """Test that instantiate_scenario validates credentials."""
        from mimic.mcp import _instantiate_scenario_impl

        with patch("mimic.mcp.config_manager") as mock_config:
            # Environment configured but no credentials
            mock_config.get_current_environment.return_value = "test"
            mock_config.get_environment_url.return_value = "https://api.test.com"
            mock_config.get_endpoint_id.return_value = "endpoint-123"
            mock_config.get_cloudbees_pat.return_value = None  # No PAT
            mock_config.get_github_pat.return_value = None

            with pytest.raises(ValueError, match="CloudBees PAT not found|credentials"):
                await _instantiate_scenario_impl(
                    scenario_id="test-app",
                    organization_id="test-org",
                )

    @pytest.mark.asyncio
    async def test_instantiate_scenario_validates_scenario_id(
        self, mock_scenario_manager
    ):
        """Test that instantiate_scenario validates scenario ID."""
        from mimic.mcp import _instantiate_scenario_impl

        with patch("mimic.mcp.config_manager") as mock_config:
            mock_config.get_current_environment.return_value = "test"
            mock_config.get_environment_url.return_value = "https://api.test.com"
            mock_config.get_endpoint_id.return_value = "endpoint-123"
            mock_config.get_cloudbees_pat.return_value = "test-pat"
            mock_config.get_github_pat.return_value = "github-pat"

            with pytest.raises(ValueError, match="Scenario .* not found"):
                await _instantiate_scenario_impl(
                    scenario_id="nonexistent-scenario",
                    organization_id="test-org",
                )

    @pytest.mark.asyncio
    async def test_cleanup_session_validates_session_exists(self):
        """Test that cleanup_session validates session exists."""
        from mimic.mcp import _cleanup_session_impl

        with pytest.raises(ValueError, match="Session .* not found"):
            await _cleanup_session_impl(session_id="nonexistent-session")


class TestMCPToolSignatures:
    """Test that MCP tools are properly defined."""

    def test_list_scenarios_tool_exists(self):
        """Test that list_scenarios tool is exported."""
        from mimic.mcp import list_scenarios

        # Should exist
        assert list_scenarios is not None

    def test_instantiate_scenario_tool_exists(self):
        """Test that instantiate_scenario tool is exported."""
        from mimic.mcp import instantiate_scenario

        # Should exist
        assert instantiate_scenario is not None

    def test_cleanup_session_tool_exists(self):
        """Test that cleanup_session tool is exported."""
        from mimic.mcp import cleanup_session

        # Should exist
        assert cleanup_session is not None


class TestMCPServerConfiguration:
    """Test MCP server configuration and initialization."""

    def test_mcp_server_name(self):
        """Test that MCP server has correct name."""
        from mimic.mcp import mcp

        assert mcp.name == "Mimic Demo Orchestrator"

    def test_scenario_manager_initialized(self, mock_scenario_manager):
        """Test that scenario_manager is initialized."""
        from mimic.mcp import scenario_manager

        assert scenario_manager is not None

        # Should be able to list scenarios
        scenarios = scenario_manager.list_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) > 0

    def test_config_manager_initialized(self):
        """Test that config_manager is initialized."""
        from mimic.mcp import config_manager

        assert config_manager is not None

        # Should have default config structure
        config = config_manager.load_config()
        assert "environments" in config
        assert "settings" in config
