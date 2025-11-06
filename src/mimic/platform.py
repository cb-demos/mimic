"""Platform detection and WSL-specific utilities."""

import os
import shutil
from pathlib import Path


def is_wsl() -> bool:
    """
    Detect if running in Windows Subsystem for Linux (WSL).

    Returns:
        True if running in WSL, False otherwise.
    """
    try:
        # Check /proc/version for WSL indicators
        with open("/proc/version") as f:
            version = f.read().lower()
            if "microsoft" in version or "wsl" in version:
                return True
    except FileNotFoundError:
        pass

    # Fallback: check for WSL-specific interop file
    if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
        return True

    # Additional fallback: check environment variable
    if os.environ.get("WSL_DISTRO_NAME"):
        return True

    return False


def check_gnome_keyring_installed() -> bool:
    """
    Check if gnome-keyring is installed on the system.

    Returns:
        True if gnome-keyring is installed, False otherwise.
    """
    return shutil.which("gnome-keyring-daemon") is not None


def is_in_dbus_session() -> bool:
    """
    Check if the current process is running in a D-Bus session.

    Returns:
        True if in D-Bus session, False otherwise.
    """
    return os.environ.get("DBUS_SESSION_BUS_ADDRESS") is not None


def get_gnome_keyring_install_command() -> str:
    """
    Get the appropriate command to install gnome-keyring based on the distribution.

    Returns:
        Installation command string.
    """
    # Try to detect the distribution
    if Path("/etc/debian_version").exists():
        # Debian/Ubuntu
        return "sudo apt-get update && sudo apt-get install -y gnome-keyring"
    elif Path("/etc/redhat-release").exists():
        # RHEL/Fedora/CentOS
        return "sudo dnf install -y gnome-keyring"
    elif Path("/etc/arch-release").exists():
        # Arch Linux
        return "sudo pacman -S gnome-keyring"
    else:
        # Generic fallback
        return "sudo apt-get install -y gnome-keyring"
