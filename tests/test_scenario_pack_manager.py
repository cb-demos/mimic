"""Tests for ScenarioPackManager - local and git pack management."""

from pathlib import Path

import pytest

from mimic.exceptions import ScenarioError
from mimic.scenario_pack_manager import (
    ScenarioPackManager,
    is_git_url,
    is_local_path,
    local_path_from_url,
    normalize_local_path,
)


@pytest.fixture
def temp_packs_dir(tmp_path):
    """Create a temporary packs directory for testing."""
    packs_dir = tmp_path / "scenario_packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    return packs_dir


@pytest.fixture
def temp_local_pack(tmp_path):
    """Create a temporary local scenario pack directory."""
    local_pack = tmp_path / "my_local_pack"
    local_pack.mkdir(parents=True, exist_ok=True)
    # Create a dummy scenario file
    (local_pack / "scenario.yaml").write_text("id: test\nname: Test Scenario")
    return local_pack


@pytest.fixture
def pack_manager(temp_packs_dir):
    """Create a ScenarioPackManager instance with temporary directory."""
    return ScenarioPackManager(temp_packs_dir)


class TestPathDetectionHelpers:
    """Test path detection helper functions."""

    def test_is_git_url_https(self):
        """Test detection of HTTPS Git URLs."""
        assert is_git_url("https://github.com/user/repo.git") is True
        assert is_git_url("http://github.com/user/repo.git") is True

    def test_is_git_url_ssh(self):
        """Test detection of SSH Git URLs."""
        assert is_git_url("git@github.com:user/repo.git") is True
        assert is_git_url("ssh://git@github.com/user/repo.git") is True

    def test_is_git_url_git_protocol(self):
        """Test detection of git:// protocol URLs."""
        assert is_git_url("git://github.com/user/repo.git") is True

    def test_is_git_url_false(self):
        """Test that non-Git URLs return False."""
        assert is_git_url("/path/to/local") is False
        assert is_git_url("~/path/to/local") is False
        assert is_git_url("file:///path/to/local") is False

    def test_is_local_path_absolute(self):
        """Test detection of absolute paths."""
        assert is_local_path("/Users/me/scenarios") is True

    def test_is_local_path_home(self):
        """Test detection of home directory paths."""
        assert is_local_path("~/scenarios") is True

    def test_is_local_path_relative(self):
        """Test detection of relative paths."""
        assert is_local_path("./scenarios") is True
        assert is_local_path("../scenarios") is True

    def test_is_local_path_file_scheme(self):
        """Test detection of file:// scheme URLs."""
        assert is_local_path("file:///Users/me/scenarios") is True

    def test_is_local_path_false(self):
        """Test that Git URLs return False."""
        assert is_local_path("https://github.com/user/repo.git") is False
        assert is_local_path("git@github.com:user/repo.git") is False

    def test_normalize_local_path_absolute(self):
        """Test normalization of absolute paths."""
        result = normalize_local_path("/Users/me/scenarios")
        assert result.startswith("file://")
        assert "Users/me/scenarios" in result

    def test_normalize_local_path_home(self):
        """Test normalization of home directory paths."""
        result = normalize_local_path("~/scenarios")
        assert result.startswith("file://")
        # Should expand ~ to actual home directory
        assert "~" not in result

    def test_normalize_local_path_already_normalized(self):
        """Test that already normalized paths remain unchanged."""
        url = "file:///Users/me/scenarios"
        result = normalize_local_path(url)
        assert result == url

    def test_local_path_from_url(self):
        """Test extraction of local path from file:// URL."""
        url = "file:///Users/me/scenarios"
        result = local_path_from_url(url)
        assert isinstance(result, Path)
        assert str(result) == "/Users/me/scenarios"

    def test_local_path_from_url_invalid(self):
        """Test that non-file:// URLs raise ValueError."""
        with pytest.raises(ValueError, match="Not a file:// URL"):
            local_path_from_url("https://github.com/user/repo.git")


class TestLocalPackRegistration:
    """Test local pack registration functionality."""

    def test_register_local_pack_creates_symlink(
        self, pack_manager, temp_local_pack, temp_packs_dir
    ):
        """Test that registering a local pack creates a symlink."""
        pack_name = "test_pack"
        pack_path = pack_manager.register_local_pack(pack_name, str(temp_local_pack))

        # Verify symlink was created
        assert pack_path.exists()
        assert pack_path.is_symlink()
        assert pack_path.resolve() == temp_local_pack.resolve()

        # Verify we can read through the symlink
        scenario_file = pack_path / "scenario.yaml"
        assert scenario_file.exists()
        assert "Test Scenario" in scenario_file.read_text()

    def test_register_local_pack_already_exists(
        self, pack_manager, temp_local_pack, temp_packs_dir
    ):
        """Test that registering a pack with existing name raises error."""
        pack_name = "test_pack"
        pack_manager.register_local_pack(pack_name, str(temp_local_pack))

        with pytest.raises(ScenarioError, match="already exists"):
            pack_manager.register_local_pack(pack_name, str(temp_local_pack))

    def test_register_local_pack_nonexistent_path(self, pack_manager):
        """Test that registering nonexistent path raises error."""
        with pytest.raises(ScenarioError, match="does not exist"):
            pack_manager.register_local_pack("test_pack", "/nonexistent/path")

    def test_register_local_pack_file_not_directory(
        self, pack_manager, temp_local_pack
    ):
        """Test that registering a file (not directory) raises error."""
        file_path = temp_local_pack / "somefile.txt"
        file_path.write_text("test")

        with pytest.raises(ScenarioError, match="not a directory"):
            pack_manager.register_local_pack("test_pack", str(file_path))


class TestClonePackWithLocalPath:
    """Test clone_pack with local paths."""

    def test_clone_pack_with_file_scheme(
        self, pack_manager, temp_local_pack, temp_packs_dir
    ):
        """Test cloning with file:// scheme URL."""
        file_url = f"file://{temp_local_pack}"
        pack_path = pack_manager.clone_pack("test_pack", file_url)

        assert pack_path.exists()
        assert pack_path.is_symlink()
        assert pack_path.resolve() == temp_local_pack.resolve()

    def test_clone_pack_detects_local_path(
        self, pack_manager, temp_local_pack, temp_packs_dir
    ):
        """Test that clone_pack properly routes local paths to register_local_pack."""
        # Use file:// scheme
        file_url = normalize_local_path(str(temp_local_pack))
        pack_path = pack_manager.clone_pack("test_pack", file_url)

        # Should create symlink, not clone
        assert pack_path.is_symlink()


class TestUpdatePackWithLocalPath:
    """Test update_pack with local packs."""

    def test_update_pack_local_is_noop(
        self, pack_manager, temp_local_pack, temp_packs_dir
    ):
        """Test that updating a local pack is a no-op."""
        # Register local pack
        file_url = f"file://{temp_local_pack}"
        pack_manager.clone_pack("test_pack", file_url)

        # Update should not fail and should be a no-op
        pack_manager.update_pack("test_pack")

        # Pack should still be a symlink
        pack_path = temp_packs_dir / "test_pack"
        assert pack_path.is_symlink()


class TestRemovePackWithLocalPath:
    """Test remove_pack with local packs."""

    def test_remove_local_pack_only_removes_symlink(
        self, pack_manager, temp_local_pack, temp_packs_dir
    ):
        """Test that removing a local pack only removes symlink, not original."""
        # Register local pack
        file_url = f"file://{temp_local_pack}"
        pack_manager.clone_pack("test_pack", file_url)

        # Remove pack
        pack_manager.remove_pack("test_pack")

        # Symlink should be gone
        pack_path = temp_packs_dir / "test_pack"
        assert not pack_path.exists()

        # But original directory should still exist
        assert temp_local_pack.exists()
        assert (temp_local_pack / "scenario.yaml").exists()


class TestGetPackPath:
    """Test get_pack_path with local packs."""

    def test_get_pack_path_local_pack(
        self, pack_manager, temp_local_pack, temp_packs_dir
    ):
        """Test getting path for a local pack."""
        file_url = f"file://{temp_local_pack}"
        pack_manager.clone_pack("test_pack", file_url)

        pack_path = pack_manager.get_pack_path("test_pack")
        assert pack_path is not None
        assert pack_path.exists()
        assert pack_path.is_symlink()

    def test_list_installed_packs_includes_local(
        self, pack_manager, temp_local_pack, temp_packs_dir
    ):
        """Test that list_installed_packs includes local packs."""
        file_url = f"file://{temp_local_pack}"
        pack_manager.clone_pack("test_pack", file_url)

        packs = pack_manager.list_installed_packs()
        assert "test_pack" in packs
