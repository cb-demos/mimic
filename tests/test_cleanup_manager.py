"""Tests for the cleanup manager (CLI/TUI refactor)."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mimic.cleanup_manager import CleanupManager
from src.mimic.state_tracker import Resource, Session, StateTracker


@pytest.fixture
def temp_state_file():
    """Create a temporary state file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        # Initialize with empty state
        import json

        json.dump({"sessions": {}}, tmp)
        state_file = Path(tmp.name)
    yield state_file
    if state_file.exists():
        state_file.unlink()


@pytest.fixture
def state_tracker(temp_state_file):
    """Create a state tracker with temporary file."""
    return StateTracker(state_file=temp_state_file)


@pytest.fixture
def cleanup_manager(state_tracker):
    """Create a cleanup manager with mocked config."""
    with patch("src.mimic.cleanup_manager.ConfigManager") as mock_config_manager:
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get_github_pat.return_value = "test-github-token"
        mock_config.get_cloudbees_pat.return_value = "test-cloudbees-token"
        mock_config.get_environment_url.return_value = "https://api.cloudbees.io"
        mock_config_manager.return_value = mock_config

        with patch("src.mimic.cleanup_manager.Console"):
            manager = CleanupManager(state_tracker=state_tracker)
            yield manager


def test_get_cleanup_stats_empty(cleanup_manager, state_tracker):
    """Test cleanup stats with no sessions."""
    stats = cleanup_manager.get_cleanup_stats()

    assert stats["total_sessions"] == 0
    assert stats["active_sessions"] == 0
    assert stats["expired_sessions"] == 0


def test_get_cleanup_stats_with_sessions(cleanup_manager, state_tracker):
    """Test cleanup stats with active and expired sessions."""
    # Create an active session
    state_tracker.create_session(
        session_id="active-1",
        scenario_id="test-scenario",
        environment="prod",
        expiration_days=7,
    )

    # Create an expired session
    now = datetime.now()
    past_time = now - timedelta(days=1)
    expired_session = Session(
        session_id="expired-1",
        scenario_id="test-scenario",
        environment="prod",
        created_at=past_time,
        expires_at=past_time,  # Already expired
        resources=[],
    )

    state = state_tracker._load_state()
    state["sessions"]["expired-1"] = expired_session.model_dump(mode="json")
    state_tracker._save_state(state)

    stats = cleanup_manager.get_cleanup_stats()

    assert stats["total_sessions"] == 2
    assert stats["active_sessions"] == 1
    assert stats["expired_sessions"] == 1


def test_check_expired_sessions(cleanup_manager, state_tracker):
    """Test checking for expired sessions."""
    # Create expired session
    now = datetime.now()
    past_time = now - timedelta(days=1)
    expired_session = Session(
        session_id="expired-1",
        scenario_id="test-scenario",
        environment="prod",
        created_at=past_time,
        expires_at=past_time,
        resources=[],
    )

    state = state_tracker._load_state()
    state["sessions"]["expired-1"] = expired_session.model_dump(mode="json")
    state_tracker._save_state(state)

    expired = cleanup_manager.check_expired_sessions()

    assert len(expired) == 1
    assert expired[0].session_id == "expired-1"


@pytest.mark.asyncio
async def test_cleanup_session_github_repo(cleanup_manager, state_tracker):
    """Test cleaning up a session with a GitHub repository."""
    # Create session with GitHub repo
    _session = state_tracker.create_session(
        session_id="test-session",
        scenario_id="test-scenario",
        environment="prod",
        expiration_days=7,
    )

    state_tracker.add_resource(
        session_id="test-session",
        resource_type="github_repo",
        resource_id="owner/test-repo",
        resource_name="test-repo",
    )

    # Mock GitHub client
    with patch("src.mimic.cleanup_manager.GitHubClient") as mock_github:
        mock_client = AsyncMock()
        mock_github.return_value = mock_client
        mock_client.delete_repository.return_value = True

        # Run cleanup
        results = await cleanup_manager.cleanup_session("test-session", dry_run=False)

        # Verify results
        assert results["session_id"] == "test-session"
        assert len(results["cleaned"]) == 1
        assert results["cleaned"][0]["type"] == "github_repo"
        assert len(results["errors"]) == 0

        # Verify session was deleted
        assert state_tracker.get_session("test-session") is None


@pytest.mark.asyncio
async def test_cleanup_session_cloudbees_component(cleanup_manager, state_tracker):
    """Test cleaning up a session with a CloudBees component."""
    # Create session with component
    _session = state_tracker.create_session(
        session_id="test-session",
        scenario_id="test-scenario",
        environment="prod",
        expiration_days=7,
    )

    state_tracker.add_resource(
        session_id="test-session",
        resource_type="cloudbees_component",
        resource_id="comp-uuid",
        resource_name="test-component",
        org_id="org-uuid",
    )

    # Mock UnifyAPIClient
    with patch("src.mimic.cleanup_manager.UnifyAPIClient") as mock_unify:
        mock_client = MagicMock()
        mock_unify.return_value = mock_client
        mock_client.delete_component.return_value = None

        # Run cleanup
        results = await cleanup_manager.cleanup_session("test-session", dry_run=False)

        # Verify results
        assert results["session_id"] == "test-session"
        assert len(results["cleaned"]) == 1
        assert results["cleaned"][0]["type"] == "cloudbees_component"
        assert len(results["errors"]) == 0

        # Verify delete_component was called
        mock_client.delete_component.assert_called_once_with("org-uuid", "comp-uuid")


@pytest.mark.asyncio
async def test_cleanup_session_dry_run(cleanup_manager, state_tracker):
    """Test dry run mode doesn't delete resources."""
    # Create session
    _session = state_tracker.create_session(
        session_id="test-session",
        scenario_id="test-scenario",
        environment="prod",
        expiration_days=7,
    )

    state_tracker.add_resource(
        session_id="test-session",
        resource_type="github_repo",
        resource_id="owner/test-repo",
        resource_name="test-repo",
    )

    # Mock GitHub client
    with patch("src.mimic.cleanup_manager.GitHubClient") as mock_github:
        mock_client = AsyncMock()
        mock_github.return_value = mock_client

        # Run cleanup in dry run mode
        results = await cleanup_manager.cleanup_session("test-session", dry_run=True)

        # Verify results
        assert results["dry_run"] is True
        assert len(results["cleaned"]) == 1
        assert results["cleaned"][0]["dry_run"] is True

        # Verify delete was NOT called
        mock_client.delete_repository.assert_not_called()

        # Verify session was NOT deleted
        assert state_tracker.get_session("test-session") is not None


@pytest.mark.asyncio
async def test_cleanup_session_with_errors(cleanup_manager, state_tracker):
    """Test cleanup handles errors gracefully."""
    # Create session
    _session = state_tracker.create_session(
        session_id="test-session",
        scenario_id="test-scenario",
        environment="prod",
        expiration_days=7,
    )

    state_tracker.add_resource(
        session_id="test-session",
        resource_type="github_repo",
        resource_id="owner/test-repo",
        resource_name="test-repo",
    )

    # Mock GitHub client to raise error
    with patch("src.mimic.cleanup_manager.GitHubClient") as mock_github:
        mock_client = AsyncMock()
        mock_github.return_value = mock_client
        mock_client.delete_repository.side_effect = Exception("API Error")

        # Run cleanup
        results = await cleanup_manager.cleanup_session("test-session", dry_run=False)

        # Verify error was captured
        assert len(results["errors"]) == 1
        assert results["errors"][0]["type"] == "github_repo"
        assert "API Error" in results["errors"][0]["error"]


@pytest.mark.asyncio
async def test_cleanup_expired_sessions(cleanup_manager, state_tracker):
    """Test cleaning up multiple expired sessions."""
    # Create expired sessions
    now = datetime.now()
    past_time = now - timedelta(days=1)

    for i in range(3):
        expired_session = Session(
            session_id=f"expired-{i}",
            scenario_id="test-scenario",
            environment="prod",
            created_at=past_time,
            expires_at=past_time,
            resources=[
                Resource(
                    type="github_repo",
                    id=f"owner/repo-{i}",
                    name=f"repo-{i}",
                )
            ],
        )

        state = state_tracker._load_state()
        state["sessions"][f"expired-{i}"] = expired_session.model_dump(mode="json")
        state_tracker._save_state(state)

    # Mock GitHub client
    with patch("src.mimic.cleanup_manager.GitHubClient") as mock_github:
        mock_client = AsyncMock()
        mock_github.return_value = mock_client
        mock_client.delete_repository.return_value = True

        # Run cleanup
        results = await cleanup_manager.cleanup_expired_sessions(
            dry_run=False, auto_confirm=True
        )

        # Verify results
        assert results["total_sessions"] == 3
        assert results["cleaned_sessions"] == 3
        assert results["failed_sessions"] == 0

        # Verify all sessions were deleted
        assert len(state_tracker.list_sessions()) == 0


@pytest.mark.asyncio
async def test_cleanup_session_not_found(cleanup_manager):
    """Test cleanup with non-existent session."""
    with pytest.raises(ValueError, match="Session .* not found"):
        await cleanup_manager.cleanup_session("nonexistent", dry_run=False)


@pytest.mark.asyncio
async def test_cleanup_multiple_resource_types(cleanup_manager, state_tracker):
    """Test cleaning up session with multiple resource types."""
    # Create session with various resources
    _session = state_tracker.create_session(
        session_id="test-session",
        scenario_id="test-scenario",
        environment="prod",
        expiration_days=7,
    )

    # Add different resource types
    state_tracker.add_resource(
        session_id="test-session",
        resource_type="github_repo",
        resource_id="owner/repo",
        resource_name="repo",
    )

    state_tracker.add_resource(
        session_id="test-session",
        resource_type="cloudbees_component",
        resource_id="comp-uuid",
        resource_name="component",
        org_id="org-uuid",
    )

    state_tracker.add_resource(
        session_id="test-session",
        resource_type="cloudbees_environment",
        resource_id="env-uuid",
        resource_name="environment",
        org_id="org-uuid",
    )

    state_tracker.add_resource(
        session_id="test-session",
        resource_type="cloudbees_application",
        resource_id="app-uuid",
        resource_name="application",
        org_id="org-uuid",
    )

    # Mock clients
    with (
        patch("src.mimic.cleanup_manager.GitHubClient") as mock_github,
        patch("src.mimic.cleanup_manager.UnifyAPIClient") as mock_unify,
    ):
        mock_github_client = AsyncMock()
        mock_github.return_value = mock_github_client
        mock_github_client.delete_repository.return_value = True

        mock_unify_client = MagicMock()
        mock_unify.return_value = mock_unify_client

        # Run cleanup
        results = await cleanup_manager.cleanup_session("test-session", dry_run=False)

        # Verify all resources were cleaned
        assert len(results["cleaned"]) == 4

        # Verify all delete methods were called
        mock_github_client.delete_repository.assert_called_once()
        mock_unify_client.delete_component.assert_called_once()
        mock_unify_client.delete_environment.assert_called_once()
        mock_unify_client.delete_application.assert_called_once()
