"""Integration tests for scenario loading behavior.

These tests verify that:
1. initialize_scenarios_from_config() excludes local test scenarios
2. Pack scenarios are loaded when configured
3. Explicit local loading still works for tests
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


class TestScenarioLoadingIntegration:
    """Test scenario loading from packs vs local directories."""

    @pytest.fixture
    def temp_scenarios_dir(self):
        """Create a temporary directory with test scenarios."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scenarios_dir = Path(tmpdir) / "scenarios"
            scenarios_dir.mkdir()

            # Create a test scenario
            scenario_data = {
                "id": "test-scenario",
                "name": "Test Scenario",
                "summary": "A test scenario",
                "repositories": [
                    {
                        "source": "org/repo",
                        "target_org": "test-org",
                        "repo_name_template": "test-repo",
                    }
                ],
            }

            with open(scenarios_dir / "test-scenario.yaml", "w") as f:
                yaml.dump(scenario_data, f)

            yield scenarios_dir

    @pytest.fixture
    def temp_pack_dir(self):
        """Create a temporary directory with pack scenarios."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "pack"
            pack_dir.mkdir()

            # Create a pack scenario
            scenario_data = {
                "id": "pack-scenario",
                "name": "Pack Scenario",
                "summary": "A scenario from a pack",
                "repositories": [
                    {
                        "source": "org/repo",
                        "target_org": "pack-org",
                        "repo_name_template": "pack-repo",
                    }
                ],
            }

            with open(pack_dir / "pack-scenario.yaml", "w") as f:
                yaml.dump(scenario_data, f)

            yield pack_dir

    def test_initialize_scenarios_excludes_local_scenarios(
        self, temp_scenarios_dir, temp_pack_dir
    ):
        """Test that initialize_scenarios_from_config() excludes local scenarios."""
        from mimic.config_manager import ConfigManager
        from mimic.scenario_pack_manager import ScenarioPackManager

        # Mock ConfigManager to return pack configuration
        with (
            patch("mimic.config_manager.ConfigManager") as mock_config_class,
            patch("mimic.scenario_pack_manager.ScenarioPackManager") as mock_pack_class,
        ):
            # Setup mocks
            mock_config = MagicMock(spec=ConfigManager)
            mock_config.list_scenario_packs.return_value = {
                "test-pack": {"enabled": True}
            }
            mock_config.packs_dir = temp_pack_dir.parent
            mock_config_class.return_value = mock_config

            mock_pack_manager = MagicMock(spec=ScenarioPackManager)
            mock_pack_manager.get_pack_path.return_value = temp_pack_dir
            mock_pack_class.return_value = mock_pack_manager

            # Import after patching
            from mimic.scenarios import initialize_scenarios_from_config

            # Initialize scenarios from config
            manager = initialize_scenarios_from_config()

            # Should load pack scenario
            scenario = manager.get_scenario("pack-scenario")
            assert scenario is not None
            assert scenario.pack_source == "test-pack"

            # Should NOT load local scenarios (local_dir=None)
            local_scenario = manager.get_scenario("test-scenario")
            assert local_scenario is None

    def test_explicit_local_loading_still_works(self, temp_scenarios_dir):
        """Test that explicit local loading still works for tests."""
        from mimic.scenarios import initialize_scenarios

        # Explicitly load from local directory
        manager = initialize_scenarios(local_dir=temp_scenarios_dir)

        # Should load local scenario
        scenario = manager.get_scenario("test-scenario")
        assert scenario is not None
        assert scenario.pack_source == "local"

    def test_pack_scenarios_loaded_from_config(self, temp_pack_dir):
        """Test that pack scenarios are properly loaded from config."""
        from mimic.config_manager import ConfigManager
        from mimic.scenario_pack_manager import ScenarioPackManager

        with (
            patch("mimic.config_manager.ConfigManager") as mock_config_class,
            patch("mimic.scenario_pack_manager.ScenarioPackManager") as mock_pack_class,
        ):
            # Setup mocks
            mock_config = MagicMock(spec=ConfigManager)
            mock_config.list_scenario_packs.return_value = {
                "official": {"enabled": True},
                "disabled-pack": {"enabled": False},
            }
            mock_config.packs_dir = temp_pack_dir.parent
            mock_config_class.return_value = mock_config

            mock_pack_manager = MagicMock(spec=ScenarioPackManager)
            # Only return path for enabled pack
            mock_pack_manager.get_pack_path.side_effect = (
                lambda name: temp_pack_dir if name == "official" else None
            )
            mock_pack_class.return_value = mock_pack_manager

            # Import after patching
            from mimic.scenarios import initialize_scenarios_from_config

            # Initialize scenarios
            manager = initialize_scenarios_from_config()

            # Should load from enabled pack
            scenario = manager.get_scenario("pack-scenario")
            assert scenario is not None
            assert scenario.pack_source == "official"

            # Verify get_pack_path was called only for enabled pack
            assert mock_pack_manager.get_pack_path.call_count == 1
            mock_pack_manager.get_pack_path.assert_called_with("official")

    def test_multiple_packs_loading(self, temp_pack_dir):
        """Test loading scenarios from multiple packs."""
        from mimic.config_manager import ConfigManager
        from mimic.scenario_pack_manager import ScenarioPackManager

        # Create second pack directory
        with tempfile.TemporaryDirectory() as tmpdir:
            pack2_dir = Path(tmpdir) / "pack2"
            pack2_dir.mkdir()

            scenario_data = {
                "id": "another-scenario",
                "name": "Another Scenario",
                "summary": "Another pack scenario",
                "repositories": [
                    {
                        "source": "org/repo2",
                        "target_org": "org2",
                        "repo_name_template": "repo2",
                    }
                ],
            }

            with open(pack2_dir / "another-scenario.yaml", "w") as f:
                yaml.dump(scenario_data, f)

            with (
                patch("mimic.config_manager.ConfigManager") as mock_config_class,
                patch(
                    "mimic.scenario_pack_manager.ScenarioPackManager"
                ) as mock_pack_class,
            ):
                # Setup mocks
                mock_config = MagicMock(spec=ConfigManager)
                mock_config.list_scenario_packs.return_value = {
                    "pack1": {"enabled": True},
                    "pack2": {"enabled": True},
                }
                mock_config.packs_dir = temp_pack_dir.parent
                mock_config_class.return_value = mock_config

                mock_pack_manager = MagicMock(spec=ScenarioPackManager)
                mock_pack_manager.get_pack_path.side_effect = lambda name: (
                    temp_pack_dir if name == "pack1" else pack2_dir
                )
                mock_pack_class.return_value = mock_pack_manager

                # Import after patching
                from mimic.scenarios import initialize_scenarios_from_config

                # Initialize scenarios
                manager = initialize_scenarios_from_config()

                # Should load from both packs
                scenario1 = manager.get_scenario("pack-scenario")
                assert scenario1 is not None
                assert scenario1.pack_source == "pack1"

                scenario2 = manager.get_scenario("another-scenario")
                assert scenario2 is not None
                assert scenario2.pack_source == "pack2"

    def test_scenario_manager_with_no_packs(self):
        """Test scenario loading when no packs are configured."""
        from mimic.config_manager import ConfigManager
        from mimic.scenario_pack_manager import ScenarioPackManager

        with (
            patch("mimic.config_manager.ConfigManager") as mock_config_class,
            patch("mimic.scenario_pack_manager.ScenarioPackManager") as mock_pack_class,
        ):
            # Setup mocks - no packs configured
            mock_config = MagicMock(spec=ConfigManager)
            mock_config.list_scenario_packs.return_value = {}
            mock_config.packs_dir = Path("/tmp/packs")
            mock_config_class.return_value = mock_config

            mock_pack_manager = MagicMock(spec=ScenarioPackManager)
            mock_pack_class.return_value = mock_pack_manager

            # Import after patching
            from mimic.scenarios import initialize_scenarios_from_config

            # Initialize scenarios
            manager = initialize_scenarios_from_config()

            # Should have no scenarios
            assert len(manager.scenarios) == 0
