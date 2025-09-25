"""Tests for the security module."""

import os
from unittest.mock import patch

import pytest

from src.security import SecurePATManager, validate_encryption_key


@pytest.fixture
def test_key():
    """Generate a test encryption key."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


@pytest.fixture
def pat_manager(test_key):
    """Create a PAT manager with test key."""
    with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": test_key}):
        return SecurePATManager()


def test_pat_manager_initialization_with_valid_key(test_key):
    """Test PAT manager initializes correctly with valid key."""
    with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": test_key}):
        manager = SecurePATManager()
        assert manager.cipher is not None


def test_pat_manager_initialization_without_key():
    """Test PAT manager raises error when key is missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="PAT_ENCRYPTION_KEY is not set"):
            SecurePATManager()


def test_pat_manager_initialization_with_invalid_key():
    """Test PAT manager raises error with invalid key format."""
    with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": "invalid-key"}):
        with pytest.raises(ValueError, match="Invalid PAT_ENCRYPTION_KEY format"):
            SecurePATManager()


def test_encrypt_decrypt_cycle(pat_manager):
    """Test that encryption and decryption work correctly."""
    test_pat = "test-pat-12345"

    # Encrypt
    encrypted = pat_manager.encrypt(test_pat)
    assert encrypted != test_pat
    assert isinstance(encrypted, str)

    # Decrypt
    decrypted = pat_manager.decrypt(encrypted)
    assert decrypted == test_pat


def test_encrypt_empty_pat(pat_manager):
    """Test that encrypting empty PAT raises error."""
    with pytest.raises(ValueError, match="PAT cannot be empty"):
        pat_manager.encrypt("")


def test_decrypt_empty_pat(pat_manager):
    """Test that decrypting empty PAT raises error."""
    with pytest.raises(ValueError, match="Encrypted PAT cannot be empty"):
        pat_manager.decrypt("")


def test_decrypt_invalid_data(pat_manager):
    """Test that decrypting invalid data raises error."""
    with pytest.raises(ValueError, match="Failed to decrypt PAT"):
        pat_manager.decrypt("invalid-encrypted-data")


def test_encrypt_different_pats_produce_different_results(pat_manager):
    """Test that encrypting different PATs produces different encrypted values."""
    pat1 = "pat-one"
    pat2 = "pat-two"

    encrypted1 = pat_manager.encrypt(pat1)
    encrypted2 = pat_manager.encrypt(pat2)

    assert encrypted1 != encrypted2


def test_encrypt_same_pat_produces_different_results(pat_manager):
    """Test that encrypting the same PAT multiple times produces different results (nonce)."""
    test_pat = "test-pat-12345"

    encrypted1 = pat_manager.encrypt(test_pat)
    encrypted2 = pat_manager.encrypt(test_pat)

    # Should be different due to nonce
    assert encrypted1 != encrypted2

    # But both should decrypt to the same value
    assert pat_manager.decrypt(encrypted1) == test_pat
    assert pat_manager.decrypt(encrypted2) == test_pat


def test_decrypt_with_wrong_key():
    """Test that decryption fails with wrong key."""
    from cryptography.fernet import Fernet

    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()

    # Encrypt with first key
    with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": key1}):
        manager1 = SecurePATManager()
        encrypted = manager1.encrypt("test-pat")

    # Try to decrypt with second key
    with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": key2}):
        manager2 = SecurePATManager()
        with pytest.raises(ValueError, match="Failed to decrypt PAT"):
            manager2.decrypt(encrypted)


def test_generate_key():
    """Test key generation."""
    key = SecurePATManager.generate_key()
    assert isinstance(key, str)
    assert len(key) > 0

    # Should be able to create a Fernet cipher with the generated key
    from cryptography.fernet import Fernet

    cipher = Fernet(key.encode("ascii"))
    assert cipher is not None


def test_validate_encryption_key_success(test_key):
    """Test encryption key validation with valid key."""
    with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": test_key}):
        assert validate_encryption_key() is True


def test_validate_encryption_key_failure():
    """Test encryption key validation with invalid key."""
    with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": "invalid-key"}):
        assert validate_encryption_key() is False


def test_validate_encryption_key_missing():
    """Test encryption key validation with missing key."""
    with patch.dict(os.environ, {}, clear=True):
        assert validate_encryption_key() is False


def test_global_pat_manager_singleton():
    """Test that get_pat_manager returns the same instance."""
    from src.security import get_pat_manager

    with patch.dict(
        os.environ, {"PAT_ENCRYPTION_KEY": SecurePATManager.generate_key()}
    ):
        manager1 = get_pat_manager()
        manager2 = get_pat_manager()
        assert manager1 is manager2


def test_unicode_pat_handling(pat_manager):
    """Test handling of unicode characters in PATs."""
    unicode_pat = "test-pat-with-émojis-🔑"

    encrypted = pat_manager.encrypt(unicode_pat)
    decrypted = pat_manager.decrypt(encrypted)

    assert decrypted == unicode_pat


def test_long_pat_handling(pat_manager):
    """Test handling of very long PATs."""
    long_pat = "a" * 1000  # 1000 character PAT

    encrypted = pat_manager.encrypt(long_pat)
    decrypted = pat_manager.decrypt(encrypted)

    assert decrypted == long_pat


def test_base64_encoding_safety(pat_manager):
    """Test that encrypted output is safe for database storage."""
    test_pat = "test-pat-with-special-chars!@#$%^&*()"

    encrypted = pat_manager.encrypt(test_pat)

    # Should be URL-safe base64 (no + or / characters)
    assert "+" not in encrypted
    assert "/" not in encrypted

    # Should be able to store and retrieve from "database" (simulate with dict)
    fake_db = {"encrypted_pat": encrypted}
    retrieved = fake_db["encrypted_pat"]

    decrypted = pat_manager.decrypt(retrieved)
    assert decrypted == test_pat
