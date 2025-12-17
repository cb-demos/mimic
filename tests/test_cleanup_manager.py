"""Tests for the cleanup manager."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mimic.cleanup_manager import CleanupManager
from src.mimic.instance_repository import InstanceRepository
from src.mimic.models import (
    CloudBeesApplication,
    CloudBeesComponent,
    CloudBeesEnvironment,
    GitHubRepository,
    Instance,
)


@pytest.fixture
def temp_state_file():
    """Create a temporary state file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        # Initialize with empty state
        import json

        json.dump({"instances": {}}, tmp)
        state_file = Path(tmp.name)
    yield state_file
    if state_file.exists():
        state_file.unlink()


@pytest.fixture
def instance_repository(temp_state_file):
    """Create an instance repository with temporary file."""
    return InstanceRepository(state_file=temp_state_file)


@pytest.fixture
def cleanup_manager(instance_repository):
    """Create a cleanup manager with mocked config."""
    with patch("src.mimic.cleanup_manager.ConfigManager") as mock_config_manager:
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get_github_pat.return_value = "test-github-token"
        mock_config.get_cloudbees_pat.return_value = "test-cloudbees-token"
        mock_config.get_tenant_url.return_value = "https://api.cloudbees.io"
        mock_config_manager.return_value = mock_config

        with patch("src.mimic.cleanup_manager.Console"):
            manager = CleanupManager(instance_repository=instance_repository)
            yield manager


def test_get_cleanup_stats_empty(cleanup_manager):
    """Test cleanup stats with no instances."""
    stats = cleanup_manager.get_cleanup_stats()

    assert stats["total_sessions"] == 0
    assert stats["active_sessions"] == 0
    assert stats["expired_sessions"] == 0


def test_get_cleanup_stats_with_sessions(cleanup_manager, instance_repository):
    """Test cleanup stats with active and expired instances."""
    now = datetime.now()

    # Create an active instance
    active_instance = Instance(
        id="active-1",
        scenario_id="test-scenario",
        name="test-run-active",
        tenant="prod",
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    instance_repository.save(active_instance)

    # Create an expired instance
    past_time = now - timedelta(days=1)
    expired_instance = Instance(
        id="expired-1",
        scenario_id="test-scenario",
        name="test-run-expired",
        tenant="prod",
        created_at=past_time,
        expires_at=past_time,  # Already expired
    )
    instance_repository.save(expired_instance)

    stats = cleanup_manager.get_cleanup_stats()

    assert stats["total_sessions"] == 2
    assert stats["active_sessions"] == 1
    assert stats["expired_sessions"] == 1


def test_check_expired_sessions(cleanup_manager, instance_repository):
    """Test checking for expired instances."""
    now = datetime.now()
    past_time = now - timedelta(days=1)

    expired_instance = Instance(
        id="expired-1",
        scenario_id="test-scenario",
        name="test-run-expired",
        tenant="prod",
        created_at=past_time,
        expires_at=past_time,
    )
    instance_repository.save(expired_instance)

    expired = cleanup_manager.check_expired_sessions()

    assert len(expired) == 1
    assert expired[0].id == "expired-1"


@pytest.mark.asyncio
async def test_cleanup_session_github_repo(cleanup_manager, instance_repository):
    """Test cleaning up an instance with a GitHub repository."""
    now = datetime.now()

    # Create instance with GitHub repo
    repo = GitHubRepository(
        id="owner/test-repo",
        name="test-repo",
        owner="owner",
        url="https://github.com/owner/test-repo",
        created_at=now,
    )

    instance = Instance(
        id="test-session",
        scenario_id="test-scenario",
        name="test-run",
        tenant="prod",
        created_at=now,
        expires_at=now + timedelta(days=7),
        repositories=[repo],
    )
    instance_repository.save(instance)

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

        # Verify instance was deleted
        assert instance_repository.get_by_id("test-session") is None


@pytest.mark.asyncio
async def test_cleanup_session_cloudbees_component(
    cleanup_manager, instance_repository
):
    """Test cleaning up an instance with a CloudBees component."""
    now = datetime.now()

    # Create instance with component
    component = CloudBeesComponent(
        id="comp-uuid",
        name="test-component",
        org_id="org-uuid",
        created_at=now,
    )

    instance = Instance(
        id="test-session",
        scenario_id="test-scenario",
        name="test-run",
        tenant="prod",
        created_at=now,
        expires_at=now + timedelta(days=7),
        components=[component],
    )
    instance_repository.save(instance)

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
async def test_cleanup_session_dry_run(cleanup_manager, instance_repository):
    """Test dry run mode doesn't delete resources."""
    now = datetime.now()

    # Create instance with repository
    repo = GitHubRepository(
        id="owner/test-repo",
        name="test-repo",
        owner="owner",
        url="https://github.com/owner/test-repo",
        created_at=now,
    )

    instance = Instance(
        id="test-session",
        scenario_id="test-scenario",
        name="test-run",
        tenant="prod",
        created_at=now,
        expires_at=now + timedelta(days=7),
        repositories=[repo],
    )
    instance_repository.save(instance)

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

        # Verify instance was NOT deleted
        assert instance_repository.get_by_id("test-session") is not None


@pytest.mark.asyncio
async def test_cleanup_session_with_errors(cleanup_manager, instance_repository):
    """Test cleanup handles errors gracefully."""
    now = datetime.now()

    # Create instance with repository
    repo = GitHubRepository(
        id="owner/test-repo",
        name="test-repo",
        owner="owner",
        url="https://github.com/owner/test-repo",
        created_at=now,
    )

    instance = Instance(
        id="test-session",
        scenario_id="test-scenario",
        name="test-run",
        tenant="prod",
        created_at=now,
        expires_at=now + timedelta(days=7),
        repositories=[repo],
    )
    instance_repository.save(instance)

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
async def test_cleanup_expired_sessions(cleanup_manager, instance_repository):
    """Test cleaning up multiple expired instances."""
    now = datetime.now()
    past_time = now - timedelta(days=1)

    for i in range(3):
        repo = GitHubRepository(
            id=f"owner/repo-{i}",
            name=f"repo-{i}",
            owner="owner",
            url=f"https://github.com/owner/repo-{i}",
            created_at=past_time,
        )

        instance = Instance(
            id=f"expired-{i}",
            scenario_id="test-scenario",
            name=f"test-run-{i}",
            tenant="prod",
            created_at=past_time,
            expires_at=past_time,
            repositories=[repo],
        )
        instance_repository.save(instance)

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

        # Verify all instances were deleted
        assert len(instance_repository.find_all()) == 0


@pytest.mark.asyncio
async def test_cleanup_session_not_found(cleanup_manager):
    """Test cleanup with non-existent instance."""
    with pytest.raises(ValueError, match="Instance .* not found"):
        await cleanup_manager.cleanup_session("nonexistent", dry_run=False)


@pytest.mark.asyncio
async def test_cleanup_multiple_resource_types(cleanup_manager, instance_repository):
    """Test cleaning up instance with multiple resource types."""
    now = datetime.now()

    # Create instance with various resources
    repo = GitHubRepository(
        id="owner/repo",
        name="repo",
        owner="owner",
        url="https://github.com/owner/repo",
        created_at=now,
    )

    component = CloudBeesComponent(
        id="comp-uuid",
        name="component",
        org_id="org-uuid",
        created_at=now,
    )

    environment = CloudBeesEnvironment(
        id="env-uuid",
        name="environment",
        org_id="org-uuid",
        created_at=now,
    )

    application = CloudBeesApplication(
        id="app-uuid",
        name="application",
        org_id="org-uuid",
        created_at=now,
    )

    instance = Instance(
        id="test-session",
        scenario_id="test-scenario",
        name="test-run",
        tenant="prod",
        created_at=now,
        expires_at=now + timedelta(days=7),
        repositories=[repo],
        components=[component],
        environments=[environment],
        applications=[application],
    )
    instance_repository.save(instance)

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


@pytest.mark.asyncio
async def test_cleanup_skips_feature_flags(cleanup_manager, instance_repository):
    """Test that feature flags are skipped during cleanup (many-to-many relationship)."""
    from src.mimic.models import CloudBeesFlag

    now = datetime.now()

    # Create instance with a feature flag
    flag = CloudBeesFlag(
        id="flag-uuid",
        name="test-flag",
        org_id="org-uuid",
        type="boolean",
        key="test_flag",
        created_at=now,
    )

    instance = Instance(
        id="test-session",
        scenario_id="test-scenario",
        name="test-run",
        tenant="prod",
        created_at=now,
        expires_at=now + timedelta(days=7),
        flags=[flag],
    )
    instance_repository.save(instance)

    # Mock UnifyAPIClient
    with patch("src.mimic.cleanup_manager.UnifyAPIClient") as mock_unify:
        mock_client = MagicMock()
        mock_unify.return_value = mock_client

        # Run cleanup
        results = await cleanup_manager.cleanup_session("test-session", dry_run=False)

        # Verify flag was skipped
        assert len(results["skipped"]) == 1
        assert results["skipped"][0]["type"] == "cloudbees_flag"
        assert results["skipped"][0]["id"] == "flag-uuid"
        assert "not safe to auto-cleanup" in results["skipped"][0]["reason"]

        # Verify no resources were cleaned (only skipped)
        assert len(results["cleaned"]) == 0
        assert len(results["errors"]) == 0

        # Verify instance was still deleted
        assert instance_repository.get_by_id("test-session") is None
