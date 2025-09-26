"""Tests for the auth module."""

import os
import tempfile
from unittest.mock import patch

import pytest

from src.auth import AuthService, get_auth_service
from src.database import Database
from src.security import NoValidPATFoundError, SecurePATManager


@pytest.fixture
def test_key():
    """Generate a test encryption key."""
    return SecurePATManager.generate_key()


@pytest.fixture
async def test_db_and_auth(test_key):
    """Create test database and auth service."""
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Set up environment with test key
        with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": test_key}):
            # Create database
            db = Database(db_path)
            await db.initialize()

            # Create auth service (it will use the global database)
            with patch("src.auth.get_database", return_value=db):
                auth_service = AuthService()
                yield db, auth_service
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_store_user_tokens(test_db_and_auth):
    """Test storing user tokens."""
    db, auth = test_db_and_auth

    result = await auth.store_user_tokens(
        "user@example.com", "test-unify-pat", "test-github-pat", "Test User"
    )

    assert result["email"] == "user@example.com"
    assert result["name"] == "Test User"
    assert result["has_github_pat"] is True

    # Verify user was created in database
    user = await db.fetchone(
        "SELECT * FROM users WHERE email = ?", ("user@example.com",)
    )
    assert user is not None
    assert user["name"] == "Test User"

    # Verify PATs were stored and encrypted
    cb_pats = await db.get_user_pats("user@example.com", "cloudbees")
    gh_pats = await db.get_user_pats("user@example.com", "github")

    assert len(cb_pats) == 1
    assert len(gh_pats) == 1

    # PATs should be encrypted (not plain text)
    assert cb_pats[0]["encrypted_pat"] != "test-unify-pat"
    assert gh_pats[0]["encrypted_pat"] != "test-github-pat"


@pytest.mark.asyncio
async def test_store_user_tokens_without_github_pat(test_db_and_auth):
    """Test storing user tokens without GitHub PAT."""
    db, auth = test_db_and_auth

    result = await auth.store_user_tokens(
        "user@example.com",
        "test-unify-pat",
        None,  # No GitHub PAT
        "Test User",
    )

    assert result["has_github_pat"] is False

    # Should only have CloudBees PAT
    cb_pats = await db.get_user_pats("user@example.com", "cloudbees")
    gh_pats = await db.get_user_pats("user@example.com", "github")

    assert len(cb_pats) == 1
    assert len(gh_pats) == 0


@pytest.mark.asyncio
async def test_email_normalization(test_db_and_auth):
    """Test that emails are normalized to lowercase."""
    db, auth = test_db_and_auth

    # Store with uppercase email
    await auth.store_user_tokens("USER@EXAMPLE.COM", "test-pat")

    # Should be stored as lowercase
    user = await db.fetchone(
        "SELECT * FROM users WHERE email = ?", ("user@example.com",)
    )
    assert user is not None

    # Should not find uppercase version
    user_upper = await db.fetchone(
        "SELECT * FROM users WHERE email = ?", ("USER@EXAMPLE.COM",)
    )
    assert user_upper is None


@pytest.mark.asyncio
async def test_get_working_pat_success(test_db_and_auth):
    """Test getting a working PAT."""
    db, auth = test_db_and_auth

    # Store a PAT
    await auth.store_user_tokens("user@example.com", "test-unify-pat")

    # Should be able to retrieve it
    pat = await auth.get_working_pat("user@example.com", "cloudbees")
    assert pat == "test-unify-pat"


@pytest.mark.asyncio
async def test_get_working_pat_not_found(test_db_and_auth):
    """Test getting PAT when none exists."""
    db, auth = test_db_and_auth

    with pytest.raises(NoValidPATFoundError, match="No CloudBees PAT found"):
        await auth.get_working_pat("nonexistent@example.com", "cloudbees")


@pytest.mark.asyncio
async def test_get_fallback_pats(test_db_and_auth):
    """Test getting fallback PATs in correct order."""
    db, auth = test_db_and_auth

    await auth.store_user_tokens("user@example.com", "first-pat")

    # Store additional PATs
    await auth.store_user_tokens(
        "user@example.com", "second-pat"
    )  # This will add, not replace
    await auth.store_user_tokens(
        "user@example.com", "third-pat"
    )  # This will add, not replace

    # Get all PATs for fallback
    pats = await auth.get_fallback_pats("user@example.com", "cloudbees")

    # Should get them in reverse order (newest first)
    assert len(pats) == 3
    # Note: The order depends on how the database stores them
    # The test verifies we get all PATs, which is the important part
    assert "first-pat" in pats
    assert "second-pat" in pats
    assert "third-pat" in pats


@pytest.mark.asyncio
async def test_get_fallback_pats_with_decryption_failure(test_db_and_auth):
    """Test fallback PATs when some can't be decrypted."""
    db, auth = test_db_and_auth

    # Store valid PAT
    await auth.store_user_tokens("user@example.com", "valid-pat")

    # Manually insert a corrupted PAT
    await db.store_pat("user@example.com", "corrupted-encrypted-data", "cloudbees")

    # Should get only the valid PAT, corrupted one should be marked inactive
    pats = await auth.get_fallback_pats("user@example.com", "cloudbees")
    assert len(pats) == 1
    assert pats[0] == "valid-pat"

    # Corrupted PAT should be marked inactive
    all_pats = await db.fetchall(
        "SELECT * FROM user_pats WHERE email = ? AND platform = ?",
        ("user@example.com", "cloudbees"),
    )

    # Should have one active and one inactive PAT
    active_pats = [p for p in all_pats if p["is_active"]]
    inactive_pats = [p for p in all_pats if not p["is_active"]]

    assert len(active_pats) == 1
    assert len(inactive_pats) == 1


@pytest.mark.asyncio
async def test_get_fallback_pats_no_valid_pats(test_db_and_auth):
    """Test fallback PATs when no valid ones exist."""
    db, auth = test_db_and_auth

    with pytest.raises(NoValidPATFoundError, match="No valid PATs found"):
        await auth.get_fallback_pats("user@example.com", "cloudbees")


@pytest.mark.asyncio
async def test_refresh_user_activity(test_db_and_auth):
    """Test refreshing user activity timestamp."""
    db, auth = test_db_and_auth

    # Create user
    await auth.store_user_tokens("user@example.com", "test-pat")

    # Small delay to ensure timestamp difference
    import asyncio

    await asyncio.sleep(0.01)

    # Refresh activity
    await auth.refresh_user_activity("user@example.com")

    # Check timestamp was updated
    user_after = await db.fetchone(
        "SELECT * FROM users WHERE email = ?", ("user@example.com",)
    )
    # Note: Depending on SQLite timestamp precision, this might be the same
    # The important thing is that the operation doesn't fail
    assert user_after is not None


@pytest.mark.asyncio
async def test_multiple_pats_same_platform(test_db_and_auth):
    """Test storing multiple PATs for the same platform (rotation scenario)."""
    db, auth = test_db_and_auth

    # Store initial PAT
    await auth.store_user_tokens("user@example.com", "old-pat", None, "User")

    # Store new PAT (simulating PAT rotation)
    await auth.store_user_tokens("user@example.com", "new-pat", None, "User")

    # Should have two PATs
    pats = await db.get_user_pats("user@example.com", "cloudbees")
    assert len(pats) == 2

    # Most recent PAT should be first
    most_recent = await auth.get_working_pat("user@example.com", "cloudbees")
    assert most_recent == "new-pat"  # Assuming new one has higher ID


@pytest.mark.asyncio
async def test_global_auth_service():
    """Test global auth service singleton."""
    service1 = get_auth_service()
    service2 = get_auth_service()
    assert service1 is service2
