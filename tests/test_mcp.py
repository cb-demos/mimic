"""Tests for MCP (Model Context Protocol) stdio server."""

import pytest

from mimic.mcp import (
    _cleanup_session_impl,
    _instantiate_scenario_impl,
    _list_scenarios_impl,
    mcp,
)


class TestMCPServer:
    """Test MCP server functionality."""

    def test_mcp_instance_exists(self):
        """Test that MCP server instance is created."""
        assert mcp is not None
        assert mcp.name == "Mimic Demo Orchestrator"

    async def test_list_scenarios_returns_data(self):
        """Test list_scenarios tool returns scenario data."""
        scenarios = _list_scenarios_impl()

        assert isinstance(scenarios, list)
        assert len(scenarios) > 0

        # Check first scenario structure
        scenario = scenarios[0]
        assert "id" in scenario
        assert "name" in scenario
        assert "summary" in scenario
        assert "pack_source" in scenario
        # parameters is optional - not all scenarios have them

    async def test_list_scenarios_structure(self):
        """Test list_scenarios returns properly structured data."""
        scenarios = _list_scenarios_impl()

        for scenario in scenarios:
            # Required fields
            assert isinstance(scenario["id"], str)
            assert isinstance(scenario["name"], str)
            assert isinstance(scenario["summary"], str)
            assert isinstance(scenario["pack_source"], str)

            # Parameters should be a dict if present (optional)
            if "parameters" in scenario:
                assert isinstance(scenario["parameters"], dict)

    async def test_instantiate_scenario_missing_environment(self, monkeypatch):
        """Test instantiate_scenario raises error when no environment is set."""
        from mimic.config_manager import ConfigManager

        # Mock config manager to return None for current environment
        def mock_get_current(self):
            return None

        monkeypatch.setattr(ConfigManager, "get_current_environment", mock_get_current)

        # Use a scenario that actually exists (hackers-app is loaded by default)
        with pytest.raises(ValueError) as exc_info:
            await _instantiate_scenario_impl(
                scenario_id="hackers-app",
                organization_id="org-123",
            )

        assert "No environment specified" in str(exc_info.value)

    async def test_instantiate_scenario_missing_credentials(
        self, tmp_path, monkeypatch
    ):
        """Test instantiate_scenario raises error when credentials are missing."""
        from mimic.config_manager import ConfigManager

        # Create temporary config directory
        config_dir = tmp_path / ".mimic"
        config_dir.mkdir()

        # Set environment variable and override class variables
        monkeypatch.setenv("MIMIC_CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(ConfigManager, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(ConfigManager, "CONFIG_FILE", config_dir / "config.yaml")
        monkeypatch.setattr(ConfigManager, "STATE_FILE", config_dir / "state.json")

        # Create a config with an environment but no credentials
        config_manager = ConfigManager()
        config_manager.save_config(
            {
                "current_environment": "test",
                "environments": {
                    "test": {
                        "url": "https://test.api.cloudbees.io",
                        "endpoint_id": "test-endpoint",
                    }
                },
            }
        )

        with pytest.raises(ValueError) as exc_info:
            await _instantiate_scenario_impl(
                scenario_id="test-scenario",
                organization_id="org-123",
                environment="test",
            )

        assert "CloudBees PAT not found" in str(exc_info.value)

    async def test_instantiate_scenario_invalid_scenario(self, monkeypatch):
        """Test instantiate_scenario raises error for invalid scenario."""
        # Mock environment variables for credentials
        monkeypatch.setenv("MIMIC_CLOUDBEES_PAT", "fake-pat")
        monkeypatch.setenv("MIMIC_GITHUB_PAT", "fake-github-pat")

        from mimic.config_manager import ConfigManager

        # Mock config manager to return test environment
        def mock_get_current(self):
            return "test"

        def mock_get_url(self, name=None):
            return "https://test.api.cloudbees.io"

        def mock_get_endpoint(self, name=None):
            return "test-endpoint"

        monkeypatch.setattr(ConfigManager, "get_current_environment", mock_get_current)
        monkeypatch.setattr(ConfigManager, "get_environment_url", mock_get_url)
        monkeypatch.setattr(ConfigManager, "get_endpoint_id", mock_get_endpoint)

        with pytest.raises(ValueError) as exc_info:
            await _instantiate_scenario_impl(
                scenario_id="nonexistent-scenario",
                organization_id="org-123",
            )

        assert "not found" in str(exc_info.value)

    async def test_cleanup_session_not_found(self):
        """Test cleanup_session raises error for nonexistent session."""
        with pytest.raises(ValueError) as exc_info:
            await _cleanup_session_impl(session_id="nonexistent-session")

        assert "not found" in str(exc_info.value)


class TestMCPTools:
    """Test individual MCP tool functions."""

    def test_list_scenarios_tool_signature(self):
        """Test list_scenarios tool has correct signature."""
        import inspect

        sig = inspect.signature(_list_scenarios_impl)
        assert len(sig.parameters) == 0  # No parameters
        assert sig.return_annotation != inspect.Signature.empty  # Has return type

    def test_instantiate_scenario_tool_signature(self):
        """Test instantiate_scenario tool has correct signature."""
        import inspect

        sig = inspect.signature(_instantiate_scenario_impl)

        # Check required parameters
        assert "scenario_id" in sig.parameters
        assert "organization_id" in sig.parameters

        # Check optional parameters
        assert "invitee_username" in sig.parameters
        assert "expires_in_days" in sig.parameters
        assert "parameters" in sig.parameters
        assert "environment" in sig.parameters

        # Check return type
        assert sig.return_annotation != inspect.Signature.empty

    def test_cleanup_session_tool_signature(self):
        """Test cleanup_session tool has correct signature."""
        import inspect

        sig = inspect.signature(_cleanup_session_impl)

        # Check required parameters
        assert "session_id" in sig.parameters

        # Check optional parameters
        assert "dry_run" in sig.parameters

        # Check return type
        assert sig.return_annotation != inspect.Signature.empty
