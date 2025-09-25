"""Tests for the cleanup module with PAT fallback logic."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.auth import AuthService
from src.cleanup import CleanupService, get_cleanup_service
from src.database import Database
from src.security import NoValidPATFoundError, SecurePATManager
from src.unify import UnifyAPIError


@pytest.fixture
def test_key():
    """Generate a test encryption key."""
    return SecurePATManager.generate_key()


@pytest.fixture
async def test_db_and_services(test_key):
    """Create test database and services."""
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Set up environment with test key
        with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": test_key}):
            # Create database
            db = Database(db_path)
            await db.initialize()

            # Create services with patched database
            with (
                patch("src.auth.get_database", return_value=db),
                patch("src.cleanup.get_database", return_value=db),
                patch("src.cleanup.get_auth_service") as mock_get_auth,
            ):
                auth_service = AuthService()
                cleanup_service = CleanupService()
                # Make cleanup service use our test auth service
                mock_get_auth.return_value = auth_service
                cleanup_service.auth = auth_service
                yield db, auth_service, cleanup_service
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_github_pat_fallback_success_on_second_try(test_db_and_services):
    """Test GitHub PAT fallback - first PAT fails, second succeeds."""
    db, auth, cleanup = test_db_and_services

    # Set up user with multiple GitHub PATs
    await auth.store_user_tokens("user@example.com", "unify-pat", "old-github-pat")
    await auth.store_user_tokens("user@example.com", "unify-pat", "new-github-pat")

    # Create session and resource
    await db.create_session("session1", "user@example.com", "test-scenario")
    await db.register_resource(
        "res1", "session1", "github_repo", "Test Repo", "github", "owner/repo"
    )

    # Mock GitHub client - first PAT fails, second succeeds
    with patch("src.cleanup.GitHubClient") as mock_github_client:
        mock_client_instance = AsyncMock()
        mock_github_client.return_value = mock_client_instance

        # First call fails with 401, second call succeeds
        async def side_effect(*args, **kwargs):
            if mock_client_instance.delete_repository.call_count == 1:
                raise Exception("401 Unauthorized")
            # Second call succeeds (returns None)
            return None

        mock_client_instance.delete_repository.side_effect = side_effect

        # Execute cleanup
        await cleanup.cleanup_single_resource("res1", "user@example.com")

        # Should have called delete_repository twice (fallback worked)
        assert mock_client_instance.delete_repository.call_count == 2
        mock_client_instance.delete_repository.assert_any_call("owner/repo")


@pytest.mark.asyncio
async def test_cloudbees_pat_fallback_all_fail(test_db_and_services):
    """Test CloudBees PAT fallback - all PATs fail."""
    db, auth, cleanup = test_db_and_services

    # Set up user with multiple CloudBees PATs
    await auth.store_user_tokens("user@example.com", "old-unify-pat")
    await auth.store_user_tokens("user@example.com", "new-unify-pat")

    # Create session and resource
    await db.create_session("session1", "user@example.com", "test-scenario")
    metadata = {"org_id": "test-org"}
    await db.register_resource(
        "res1",
        "session1",
        "cloudbees_component",
        "Test Component",
        "cloudbees",
        "comp-uuid",
        metadata,
    )

    # Mock UnifyAPIClient - all PATs fail
    with patch("src.cleanup.UnifyAPIClient") as mock_unify_client:
        mock_context_manager = MagicMock()
        mock_unify_client.return_value.__enter__.return_value = mock_context_manager
        mock_unify_client.return_value.__exit__.return_value = None

        # All calls fail with different errors
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise UnifyAPIError("403 Forbidden")
            else:
                raise UnifyAPIError("401 Unauthorized")

        mock_context_manager.delete_component.side_effect = side_effect

        # Should raise NoValidPATFoundError after all PATs fail
        with pytest.raises(NoValidPATFoundError, match="All PATs failed"):
            await cleanup.cleanup_single_resource("res1", "user@example.com")

        # Should have tried both PATs
        assert mock_context_manager.delete_component.call_count == 2


@pytest.mark.asyncio
async def test_cloudbees_pat_fallback_not_found_is_graceful(test_db_and_services):
    """Test CloudBees PAT fallback - 404 Not Found is handled gracefully."""
    db, auth, cleanup = test_db_and_services

    # Set up user with PAT
    await auth.store_user_tokens("user@example.com", "unify-pat")

    # Create session and resource
    await db.create_session("session1", "user@example.com", "test-scenario")
    metadata = {"org_id": "test-org"}
    await db.register_resource(
        "res1",
        "session1",
        "cloudbees_environment",
        "Test Env",
        "cloudbees",
        "env-uuid",
        metadata,
    )

    # Mock UnifyAPIClient - returns 404
    with patch("src.cleanup.UnifyAPIClient") as mock_unify_client:
        mock_context_manager = MagicMock()
        mock_unify_client.return_value.__enter__.return_value = mock_context_manager
        mock_unify_client.return_value.__exit__.return_value = None

        # First PAT returns 404 (resource already deleted)
        def side_effect(*args, **kwargs):
            raise UnifyAPIError("404 Not Found")

        mock_context_manager.delete_environment.side_effect = side_effect

        # Should complete successfully without error
        await cleanup.cleanup_single_resource("res1", "user@example.com")

        # Should have only tried once (404 is handled gracefully)
        assert mock_context_manager.delete_environment.call_count == 1


@pytest.mark.asyncio
async def test_cleanup_session_with_mixed_results(test_db_and_services):
    """Test cleaning up a session with both successful and failed resources."""
    db, auth, cleanup = test_db_and_services

    # Set up user
    await auth.store_user_tokens("user@example.com", "unify-pat", "github-pat")

    # Create session with multiple resources
    await db.create_session("session1", "user@example.com", "test-scenario")

    # GitHub resource (will succeed)
    await db.register_resource(
        "github_res",
        "session1",
        "github_repo",
        "Success Repo",
        "github",
        "owner/success",
    )

    # CloudBees resource (will fail)
    metadata = {"org_id": "test-org"}
    await db.register_resource(
        "cb_res",
        "session1",
        "cloudbees_component",
        "Fail Component",
        "cloudbees",
        "fail-uuid",
        metadata,
    )

    # Mock both services
    with (
        patch("src.cleanup.GitHubClient") as mock_github,
        patch("src.cleanup.UnifyAPIClient") as mock_unify,
    ):
        # GitHub succeeds
        mock_github_instance = AsyncMock()
        mock_github.return_value = mock_github_instance

        async def github_side_effect(*args, **kwargs):
            return None  # Success

        mock_github_instance.delete_repository.side_effect = github_side_effect

        # CloudBees fails
        mock_unify_context = MagicMock()
        mock_unify.return_value.__enter__.return_value = mock_unify_context
        mock_unify.return_value.__exit__.return_value = None

        def unify_side_effect(*args, **kwargs):
            raise UnifyAPIError("500 Server Error")

        mock_unify_context.delete_component.side_effect = unify_side_effect

        # Execute session cleanup
        result = await cleanup.cleanup_session("session1", "user@example.com")

        # Verify results
        assert result["session_id"] == "session1"
        assert result["total_resources"] == 2
        assert result["successful"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1

        # Check database states
        github_resource = await db.fetchone(
            "SELECT * FROM resources WHERE id = ?", ("github_res",)
        )
        cb_resource = await db.fetchone(
            "SELECT * FROM resources WHERE id = ?", ("cb_res",)
        )

        assert github_resource["status"] == "deleted"
        assert cb_resource["status"] == "failed"


@pytest.mark.asyncio
async def test_process_pending_deletions_with_no_valid_pat(test_db_and_services):
    """Test processing pending deletions when user has no valid PATs."""
    db, auth, cleanup = test_db_and_services

    # Create user but don't store any PATs
    await db.create_user("user@example.com")

    # Create expired session
    from datetime import datetime, timedelta

    past_time = (datetime.now() - timedelta(days=1)).isoformat()
    await db.create_session(
        "expired_session", "user@example.com", "test-scenario", past_time
    )
    await db.register_resource(
        "orphaned_res",
        "expired_session",
        "github_repo",
        "Orphaned Repo",
        "github",
        "owner/orphaned",
    )

    # Mark resources for deletion (stage 1)
    marked_count = await cleanup.mark_expired_resources()
    assert marked_count == 1

    # Process pending deletions (stage 2)
    result = await cleanup.process_pending_deletions()

    # Should fail due to no PATs
    assert result["total_resources"] == 1
    assert result["successful"] == 0
    assert result["failed"] == 0
    assert result["no_valid_pat"] == 1

    # Resource should be marked as failed
    resource = await db.fetchone(
        "SELECT * FROM resources WHERE id = ?", ("orphaned_res",)
    )
    assert resource["status"] == "failed"


@pytest.mark.asyncio
async def test_unknown_platform_error(test_db_and_services):
    """Test cleanup with unknown platform raises NoValidPATFoundError."""
    db, auth, cleanup = test_db_and_services

    # Set up user with valid cloudbees PAT
    await auth.store_user_tokens("user@example.com", "some-pat")

    # Create session and resource with unknown platform
    await db.create_session("session1", "user@example.com", "test-scenario")
    await db.register_resource(
        "bad_res",
        "session1",
        "unknown_resource",
        "Bad Resource",
        "unknown_platform",
        "bad-id",
    )

    # Should raise NoValidPATFoundError because no PATs exist for unknown platform
    with pytest.raises(NoValidPATFoundError, match="No PATs found.*unknown_platform"):
        await cleanup.cleanup_single_resource("bad_res", "user@example.com")


@pytest.mark.asyncio
async def test_cleanup_session_ownership_validation(test_db_and_services):
    """Test that users can only clean up their own sessions."""
    db, auth, cleanup = test_db_and_services

    # Set up two users
    await auth.store_user_tokens("user1@example.com", "pat1")
    await auth.store_user_tokens("user2@example.com", "pat2")

    # User1 creates a session
    await db.create_session("user1_session", "user1@example.com", "test-scenario")

    # User2 tries to clean up User1's session
    with pytest.raises(ValueError, match="not found or not owned by user2@example.com"):
        await cleanup.cleanup_session("user1_session", "user2@example.com")


@pytest.mark.asyncio
async def test_global_cleanup_service():
    """Test global cleanup service singleton."""
    service1 = get_cleanup_service()
    service2 = get_cleanup_service()
    assert service1 is service2


@pytest.mark.asyncio
async def test_missing_metadata_for_cloudbees_resource(test_db_and_services):
    """Test CloudBees resource cleanup fails gracefully when metadata is missing."""
    db, auth, cleanup = test_db_and_services

    # Set up user
    await auth.store_user_tokens("user@example.com", "unify-pat")

    # Create session and resource WITHOUT metadata
    await db.create_session("session1", "user@example.com", "test-scenario")
    await db.register_resource(
        "bad_res",
        "session1",
        "cloudbees_component",
        "Bad Component",
        "cloudbees",
        "comp-uuid",
        # No metadata provided
    )

    # Should fail with metadata error (wrapped in NoValidPATFoundError)
    with pytest.raises(NoValidPATFoundError, match="All PATs failed.*Missing org_id"):
        await cleanup.cleanup_single_resource("bad_res", "user@example.com")
