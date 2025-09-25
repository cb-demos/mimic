"""Security utilities for PAT encryption and management."""

import base64
import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class NoValidPATFoundError(Exception):
    """Raised when no working PAT can be found for a user."""

    pass


class SecurePATManager:
    """Manages secure encryption and decryption of Personal Access Tokens."""

    def __init__(self):
        """Initialize the PAT manager with encryption key from environment."""
        key = os.environ.get("PAT_ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "PAT_ENCRYPTION_KEY is not set in the environment. "
                'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )

        try:
            # Key should already be base64-encoded in environment variable
            self.cipher = Fernet(key.encode("ascii"))
        except Exception as e:
            raise ValueError(f"Invalid PAT_ENCRYPTION_KEY format: {e}") from e

    def encrypt(self, pat: str) -> str:
        """Encrypt a PAT for secure storage.

        Args:
            pat: The plain text PAT to encrypt

        Returns:
            Base64-encoded encrypted PAT safe for database storage
        """
        if not pat:
            raise ValueError("PAT cannot be empty")

        try:
            encrypted_bytes = self.cipher.encrypt(pat.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt PAT: {e}")
            raise ValueError("Failed to encrypt PAT") from e

    def decrypt(self, encrypted_pat: str) -> str:
        """Decrypt a PAT for use.

        Args:
            encrypted_pat: Base64-encoded encrypted PAT from database

        Returns:
            The decrypted plain text PAT
        """
        if not encrypted_pat:
            raise ValueError("Encrypted PAT cannot be empty")

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_pat.encode())
            return self.cipher.decrypt(encrypted_bytes).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt PAT: {e}")
            raise ValueError(
                "Failed to decrypt PAT - key may have changed or PAT corrupted"
            ) from e

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key.

        Returns:
            A base64-encoded Fernet key suitable for PAT_ENCRYPTION_KEY
        """
        return Fernet.generate_key().decode()


# Global PAT manager instance
_pat_manager: SecurePATManager | None = None


def get_pat_manager() -> SecurePATManager:
    """Get the global PAT manager instance."""
    global _pat_manager
    if _pat_manager is None:
        _pat_manager = SecurePATManager()
    return _pat_manager


def validate_encryption_key() -> bool:
    """Validate that the encryption key is properly configured.

    Returns:
        True if the key is valid and can encrypt/decrypt
    """
    try:
        # Create a fresh manager instance to avoid global state issues
        manager = SecurePATManager()
        # Test encrypt/decrypt cycle
        test_data = "test-pat-validation"
        encrypted = manager.encrypt(test_data)
        decrypted = manager.decrypt(encrypted)
        return decrypted == test_data
    except Exception as e:
        logger.error(f"Encryption key validation failed: {e}")
        return False
