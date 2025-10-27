"""Keyring health check utilities for detecting keyring backend availability."""

import multiprocessing
import platform


def _test_keyring_operation() -> None:
    """Test keyring operation in subprocess.

    This runs in a separate process so it can be terminated if it hangs.
    Raises exception if keyring is not available.
    """
    import keyring

    # Try a simple set/get/delete operation
    test_service = "mimic-health-check"
    test_username = "test"
    test_password = "test123"

    try:
        # Test set
        keyring.set_password(test_service, test_username, test_password)

        # Test get
        retrieved = keyring.get_password(test_service, test_username)
        if retrieved != test_password:
            raise RuntimeError("Keyring returned incorrect password")

        # Test delete
        keyring.delete_password(test_service, test_username)

    except Exception as e:
        raise RuntimeError(f"Keyring operation failed: {e}") from e


def test_keyring_available(timeout: int = 3) -> tuple[bool, str | None]:
    """Test if keyring is available and functioning.

    Uses multiprocessing to test keyring operations with a timeout.
    Unlike threading, processes can actually be terminated if they hang.

    Args:
        timeout: Maximum seconds to wait for keyring test (default: 3)

    Returns:
        Tuple of (success, error_message). If success is False, error_message
        contains platform-specific setup instructions.
    """
    # Create a process to test keyring
    process = multiprocessing.Process(target=_test_keyring_operation)
    process.start()

    # Wait for the process to complete with timeout
    process.join(timeout=timeout)

    if process.is_alive():
        # Process is still running - it hung
        process.terminate()
        process.join(timeout=1)  # Wait for termination
        if process.is_alive():
            process.kill()  # Force kill if terminate didn't work

        return False, _format_timeout_error(timeout)

    # Check exit code
    if process.exitcode != 0:
        return False, _format_error()

    return True, None


def _format_timeout_error(timeout: int) -> str:
    """Format error message for timeout."""
    instructions = get_keyring_setup_instructions()
    return (
        f"Keyring operation timed out after {timeout} seconds.\n"
        f"This usually means no keyring backend is available or D-Bus is not configured.\n\n"
        f"{instructions}"
    )


def _format_error() -> str:
    """Format error message for general keyring failure."""
    instructions = get_keyring_setup_instructions()
    return f"Keyring backend is not available or not functioning.\n\n{instructions}"


def get_keyring_setup_instructions() -> str:
    """Get platform-specific instructions for setting up keyring backend.

    Returns:
        Multi-line string with setup instructions for the current platform.
    """
    system = platform.system()

    if system == "Linux":
        return """Mimic requires a system keyring to securely store credentials.

On Ubuntu/Debian, install a keyring backend:

  # GNOME Keyring (recommended for GNOME/Ubuntu desktops)
  sudo apt-get install gnome-keyring

  # KWallet (recommended for KDE desktops)
  sudo apt-get install kwalletmanager

For headless/SSH sessions, you need a D-Bus session:

  # Run mimic within a D-Bus session
  dbus-run-session -- bash
  mimic setup

  # Or start gnome-keyring daemon manually
  eval $(gnome-keyring-daemon --start)
  export SSH_AUTH_SOCK

After installing a keyring backend, log out and log back in, or start
a new shell session with D-Bus configured.

For more information:
  https://github.com/jaraco/keyring#third-party-backends
"""
    elif system == "Darwin":
        return """Keyring backend issue detected on macOS.

macOS should use the native Keychain backend automatically.
This error is unexpected.

Possible solutions:
  1. Ensure you're running a recent version of Python
  2. Try reinstalling Mimic: uv tool uninstall mimic && uv tool install mimic
  3. Check if there are Keychain access permission issues

If the problem persists, please file an issue with details about your setup.
"""
    elif system == "Windows":
        return """Keyring backend issue detected on Windows.

Windows should use the native Windows Credential Manager automatically.
This error is unexpected.

Possible solutions:
  1. Ensure you're running a recent version of Python
  2. Try reinstalling Mimic
  3. Check if Windows Credential Manager is functioning

If the problem persists, please file an issue with details about your setup.
"""
    else:
        return """Keyring backend issue detected.

Mimic requires a system keyring to securely store credentials.
Please ensure your system has a compatible keyring backend installed.

For more information:
  https://github.com/jaraco/keyring
"""
