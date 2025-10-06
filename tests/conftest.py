"""Pytest configuration and fixtures for Mimic tests."""

import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture(scope="session")
def test_scenario_pack():
    """Create a temporary scenario pack for testing.

    This creates realistic test scenarios that can be used by MCP and other tests.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = Path(tmpdir) / "test-pack"
        pack_dir.mkdir()

        # Create a realistic test scenario
        scenario_data = {
            "id": "test-app",
            "name": "Test Application",
            "summary": "A test application scenario for integration tests",
            "details": "This is a comprehensive test scenario with all features",
            "repositories": [
                {
                    "source": "test-org/test-template",
                    "target_org": "${github_org}",
                    "repo_name_template": "test-app-${timestamp}",
                    "create_component": True,
                }
            ],
            "applications": [
                {
                    "name": "Test App",
                    "components": ["test-app-${timestamp}"],
                    "environments": ["dev", "prod"],
                }
            ],
            "environments": [
                {
                    "name": "dev",
                    "env": [{"name": "ENV", "value": "development"}],
                    "flags": ["feature-flag"],
                },
                {
                    "name": "prod",
                    "env": [{"name": "ENV", "value": "production"}],
                    "flags": ["feature-flag"],
                },
            ],
            "flags": [{"name": "feature-flag", "type": "boolean"}],
            "parameter_schema": {
                "properties": {
                    "github_org": {
                        "type": "string",
                        "description": "GitHub organization",
                        "pattern": "^[a-zA-Z0-9-]+$",
                    },
                    "timestamp": {
                        "type": "string",
                        "description": "Unique timestamp",
                    },
                },
                "required": ["github_org", "timestamp"],
            },
        }

        with open(pack_dir / "test-app.yaml", "w") as f:
            yaml.dump(scenario_data, f)

        # Create another simpler scenario
        simple_scenario = {
            "id": "simple-demo",
            "name": "Simple Demo",
            "summary": "A simple demo scenario",
            "repositories": [
                {
                    "source": "test-org/simple-template",
                    "target_org": "test-org",
                    "repo_name_template": "simple-demo",
                }
            ],
        }

        with open(pack_dir / "simple-demo.yaml", "w") as f:
            yaml.dump(simple_scenario, f)

        yield pack_dir


@pytest.fixture
def mock_scenario_manager(test_scenario_pack, monkeypatch):
    """Mock scenario manager to use test scenarios.

    This fixture patches the config and pack managers to return our test pack,
    then reinitializes the scenario manager in mcp.py with test data.
    """
    from mimic.config_manager import ConfigManager
    from mimic.scenario_pack_manager import ScenarioPackManager
    from mimic.scenarios import initialize_scenarios

    # Patch the config manager methods
    monkeypatch.setattr(
        ConfigManager,
        "list_scenario_packs",
        lambda self: {"test-pack": {"enabled": True}},
    )
    monkeypatch.setattr(
        ScenarioPackManager, "get_pack_path", lambda self, name: test_scenario_pack
    )

    # Reinitialize the scenario manager in mcp module with test pack
    test_manager = initialize_scenarios(
        scenarios_dirs=[(test_scenario_pack, "test-pack")], local_dir=None
    )

    # Patch mcp module's scenario_manager
    import mimic.mcp

    original_manager = mimic.mcp.scenario_manager
    mimic.mcp.scenario_manager = test_manager

    yield test_manager

    # Restore original
    mimic.mcp.scenario_manager = original_manager
