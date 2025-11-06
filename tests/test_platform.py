"""Tests for platform detection utilities."""

import os
from pathlib import Path
from unittest.mock import mock_open, patch

from mimic.platform import (
    check_gnome_keyring_installed,
    get_gnome_keyring_install_command,
    is_in_dbus_session,
    is_wsl,
)


class TestWSLDetection:
    """Tests for WSL detection logic."""

    def test_is_wsl_detects_via_proc_version_microsoft(self):
        """Test WSL detection via /proc/version with 'microsoft'."""
        mock_content = "Linux version 4.4.0-19041-Microsoft (Microsoft@Microsoft.com)"
        with patch("builtins.open", mock_open(read_data=mock_content)):
            assert is_wsl() is True

    def test_is_wsl_detects_via_proc_version_wsl(self):
        """Test WSL detection via /proc/version with 'wsl'."""
        mock_content = "Linux version 5.10.16.3-WSL2-kernel (WSL@example.com)"
        with patch("builtins.open", mock_open(read_data=mock_content)):
            assert is_wsl() is True

    def test_is_wsl_detects_via_interop_file(self):
        """Test WSL detection via WSLInterop file."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("os.path.exists", return_value=True):
                assert is_wsl() is True

    def test_is_wsl_detects_via_env_variable(self):
        """Test WSL detection via WSL_DISTRO_NAME environment variable."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("os.path.exists", return_value=False):
                with patch.dict(os.environ, {"WSL_DISTRO_NAME": "Ubuntu"}):
                    assert is_wsl() is True

    def test_is_wsl_returns_false_on_non_wsl(self):
        """Test that is_wsl returns False on non-WSL systems."""
        mock_content = "Linux version 5.15.0-generic (ubuntu@ubuntu.com)"
        with patch("builtins.open", mock_open(read_data=mock_content)):
            with patch("os.path.exists", return_value=False):
                with patch.dict(os.environ, {}, clear=True):
                    assert is_wsl() is False

    def test_is_wsl_handles_missing_proc_version(self):
        """Test WSL detection when /proc/version doesn't exist."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("os.path.exists", return_value=False):
                with patch.dict(os.environ, {}, clear=True):
                    assert is_wsl() is False


class TestGnomeKeyringDetection:
    """Tests for gnome-keyring installation detection."""

    def test_check_gnome_keyring_installed_returns_true(self):
        """Test that check returns True when gnome-keyring-daemon exists."""
        with patch("shutil.which", return_value="/usr/bin/gnome-keyring-daemon"):
            assert check_gnome_keyring_installed() is True

    def test_check_gnome_keyring_installed_returns_false(self):
        """Test that check returns False when gnome-keyring-daemon doesn't exist."""
        with patch("shutil.which", return_value=None):
            assert check_gnome_keyring_installed() is False


class TestDBusSessionDetection:
    """Tests for D-Bus session detection."""

    def test_is_in_dbus_session_returns_true_when_env_set(self):
        """Test that is_in_dbus_session returns True when env var is set."""
        with patch.dict(
            os.environ, {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/tmp/dbus-123"}
        ):
            assert is_in_dbus_session() is True

    def test_is_in_dbus_session_returns_false_when_env_not_set(self):
        """Test that is_in_dbus_session returns False when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_in_dbus_session() is False


class TestGnomeKeyringInstallCommand:
    """Tests for get_gnome_keyring_install_command."""

    def test_returns_debian_command_for_debian(self):
        """Test returns apt-get command for Debian/Ubuntu."""

        def path_exists_mock(self):
            return str(self) == "/etc/debian_version"

        with patch.object(Path, "exists", path_exists_mock):
            result = get_gnome_keyring_install_command()
            assert "apt-get" in result
            assert "gnome-keyring" in result

    def test_returns_dnf_command_for_redhat(self):
        """Test returns dnf command for RHEL/Fedora."""

        def path_exists_mock(self):
            return str(self) == "/etc/redhat-release"

        with patch.object(Path, "exists", path_exists_mock):
            result = get_gnome_keyring_install_command()
            assert "dnf" in result
            assert "gnome-keyring" in result

    def test_returns_pacman_command_for_arch(self):
        """Test returns pacman command for Arch Linux."""

        def path_exists_mock(self):
            return str(self) == "/etc/arch-release"

        with patch.object(Path, "exists", path_exists_mock):
            result = get_gnome_keyring_install_command()
            assert "pacman" in result
            assert "gnome-keyring" in result

    def test_returns_fallback_command_for_unknown(self):
        """Test returns apt-get fallback for unknown distributions."""
        with patch.object(Path, "exists", return_value=False):
            result = get_gnome_keyring_install_command()
            assert "apt-get" in result
            assert "gnome-keyring" in result
