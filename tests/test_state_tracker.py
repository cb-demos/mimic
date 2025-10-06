"""Tests for StateTracker - session and resource tracking."""

from datetime import datetime, timedelta

import pytest

from mimic.state_tracker import Resource, Session, StateTracker


@pytest.fixture
def temp_state_file(tmp_path):
    """Create a temporary state file for testing."""
    state_file = tmp_path / "state.json"
    return state_file


@pytest.fixture
def state_tracker(temp_state_file):
    """Create a StateTracker instance with temporary state file."""
    return StateTracker(state_file=temp_state_file)


class TestStateTrackerInitialization:
    """Test StateTracker initialization."""

    def test_creates_state_file_on_init(self, temp_state_file):
        """Test that state file is created on initialization."""
        assert not temp_state_file.exists()

        _ = StateTracker(state_file=temp_state_file)

        assert temp_state_file.exists()

    def test_creates_parent_directory(self, tmp_path):
        """Test that parent directory is created if it doesn't exist."""
        state_file = tmp_path / "nested" / "dir" / "state.json"
        assert not state_file.parent.exists()

        _ = StateTracker(state_file=state_file)

        assert state_file.parent.exists()
        assert state_file.exists()

    def test_loads_existing_state_file(self, state_tracker, temp_state_file):
        """Test that existing state file is loaded correctly."""
        # Create a session
        state_tracker.create_session("test-123", "hackers-app", "prod")

        # Create new tracker pointing to same file
        tracker2 = StateTracker(state_file=temp_state_file)

        # Should load existing session
        session = tracker2.get_session("test-123")
        assert session is not None
        assert session.session_id == "test-123"


class TestSessionCreation:
    """Test session creation and management."""

    def test_create_session_basic(self, state_tracker):
        """Test creating a basic session."""
        session = state_tracker.create_session(
            session_id="test-session-1",
            scenario_id="hackers-app",
            environment="prod",
        )

        assert session.session_id == "test-session-1"
        assert session.scenario_id == "hackers-app"
        assert session.environment == "prod"
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.expires_at, datetime)
        assert len(session.resources) == 0
        assert session.metadata == {}

    def test_session_expiration_default(self, state_tracker):
        """Test that sessions have default 7-day expiration."""
        before = datetime.now()
        session = state_tracker.create_session("test-123", "scenario-1", "prod")
        after = datetime.now()

        # Expiration should be ~7 days from now
        expected_min = before + timedelta(days=7)
        expected_max = after + timedelta(days=7)

        assert expected_min <= session.expires_at <= expected_max

    def test_session_expiration_custom(self, state_tracker):
        """Test creating session with custom expiration."""
        before = datetime.now()
        session = state_tracker.create_session(
            "test-123", "scenario-1", "prod", expiration_days=14
        )
        after = datetime.now()

        # Expiration should be ~14 days from now
        expected_min = before + timedelta(days=14)
        expected_max = after + timedelta(days=14)

        assert expected_min <= session.expires_at <= expected_max

    def test_session_never_expires(self, state_tracker):
        """Test creating session with no expiration (None)."""
        session = state_tracker.create_session(
            "test-123", "scenario-1", "prod", expiration_days=None
        )

        # Should have no expiration
        assert session.expires_at is None

    def test_create_session_with_metadata(self, state_tracker):
        """Test creating session with custom metadata."""
        metadata = {
            "user": "testuser",
            "purpose": "demo",
            "custom_field": "value",
        }

        session = state_tracker.create_session(
            "test-123", "scenario-1", "prod", metadata=metadata
        )

        assert session.metadata == metadata

    def test_session_persists_to_file(self, state_tracker, temp_state_file):
        """Test that created session is saved to state file."""
        state_tracker.create_session("test-123", "scenario-1", "prod")

        # Read file directly
        import json

        with open(temp_state_file) as f:
            state = json.load(f)

        assert "sessions" in state
        assert "test-123" in state["sessions"]
        assert state["sessions"]["test-123"]["scenario_id"] == "scenario-1"


class TestResourceTracking:
    """Test resource tracking within sessions."""

    def test_add_resource_to_session(self, state_tracker):
        """Test adding a resource to a session."""
        state_tracker.create_session("session-1", "hackers-app", "prod")

        state_tracker.add_resource(
            session_id="session-1",
            resource_type="github_repo",
            resource_id="org/repo-name",
            resource_name="repo-name",
        )

        session = state_tracker.get_session("session-1")
        assert len(session.resources) == 1
        assert session.resources[0].type == "github_repo"
        assert session.resources[0].id == "org/repo-name"
        assert session.resources[0].name == "repo-name"

    def test_add_multiple_resources(self, state_tracker):
        """Test adding multiple resources to a session."""
        state_tracker.create_session("session-1", "hackers-app", "prod")

        state_tracker.add_resource("session-1", "github_repo", "org/repo-1", "repo-1")
        state_tracker.add_resource(
            "session-1",
            "cloudbees_component",
            "component-uuid",
            "component-name",
            org_id="org-uuid",
        )
        state_tracker.add_resource(
            "session-1",
            "cloudbees_environment",
            "env-uuid",
            "env-name",
            org_id="org-uuid",
        )

        session = state_tracker.get_session("session-1")
        assert len(session.resources) == 3

        # Verify resource types
        resource_types = [r.type for r in session.resources]
        assert "github_repo" in resource_types
        assert "cloudbees_component" in resource_types
        assert "cloudbees_environment" in resource_types

    def test_add_resource_with_metadata(self, state_tracker):
        """Test adding resource with custom metadata."""
        state_tracker.create_session("session-1", "scenario-1", "prod")

        metadata = {
            "visibility": "public",
            "template": "template-repo",
        }

        state_tracker.add_resource(
            "session-1",
            "github_repo",
            "org/repo",
            "repo",
            metadata=metadata,
        )

        session = state_tracker.get_session("session-1")
        assert session.resources[0].metadata == metadata

    def test_add_resource_with_org_id(self, state_tracker):
        """Test adding CloudBees resource with organization ID."""
        state_tracker.create_session("session-1", "scenario-1", "prod")

        state_tracker.add_resource(
            "session-1",
            "cloudbees_component",
            "component-123",
            "my-component",
            org_id="org-456",
        )

        session = state_tracker.get_session("session-1")
        assert session.resources[0].org_id == "org-456"

    def test_add_resource_to_nonexistent_session_raises_error(self, state_tracker):
        """Test that adding resource to nonexistent session raises error."""
        with pytest.raises(ValueError, match="Session .* not found"):
            state_tracker.add_resource(
                "nonexistent",
                "github_repo",
                "org/repo",
                "repo",
            )


class TestSessionRetrieval:
    """Test session retrieval operations."""

    def test_get_session_by_id(self, state_tracker):
        """Test retrieving a session by ID."""
        state_tracker.create_session("session-1", "scenario-1", "prod")
        state_tracker.create_session("session-2", "scenario-2", "demo")

        session = state_tracker.get_session("session-1")
        assert session.session_id == "session-1"
        assert session.scenario_id == "scenario-1"

    def test_get_nonexistent_session_returns_none(self, state_tracker):
        """Test that getting nonexistent session returns None."""
        session = state_tracker.get_session("nonexistent")
        assert session is None

    def test_list_sessions_empty(self, state_tracker):
        """Test listing sessions when none exist."""
        sessions = state_tracker.list_sessions()
        assert sessions == []

    def test_list_sessions(self, state_tracker):
        """Test listing all sessions."""
        state_tracker.create_session("session-1", "scenario-1", "prod")
        state_tracker.create_session("session-2", "scenario-2", "demo")
        state_tracker.create_session("session-3", "scenario-3", "preprod")

        sessions = state_tracker.list_sessions()
        assert len(sessions) == 3

        session_ids = [s.session_id for s in sessions]
        assert "session-1" in session_ids
        assert "session-2" in session_ids
        assert "session-3" in session_ids

    def test_list_sessions_sorted_by_creation_newest_first(self, state_tracker):
        """Test that sessions are sorted by creation date, newest first."""
        import time

        # Create sessions with slight delay
        state_tracker.create_session("session-1", "scenario-1", "prod")
        time.sleep(0.01)
        state_tracker.create_session("session-2", "scenario-2", "prod")
        time.sleep(0.01)
        state_tracker.create_session("session-3", "scenario-3", "prod")

        sessions = state_tracker.list_sessions()

        # Newest should be first
        assert sessions[0].session_id == "session-3"
        assert sessions[1].session_id == "session-2"
        assert sessions[2].session_id == "session-1"

    def test_list_sessions_exclude_expired(self, state_tracker):
        """Test listing sessions excluding expired ones."""
        # Create active session (7 days)
        state_tracker.create_session("active", "scenario-1", "prod", expiration_days=7)

        # Create session that never expires
        state_tracker.create_session(
            "never-expires", "scenario-3", "prod", expiration_days=None
        )

        # Create expired session (0 days - expires immediately)
        state_tracker.create_session("expired", "scenario-2", "prod", expiration_days=0)

        # Give it a moment to actually be expired
        import time

        time.sleep(0.01)

        # List only active sessions
        sessions = state_tracker.list_sessions(include_expired=False)

        session_ids = [s.session_id for s in sessions]
        assert "active" in session_ids
        assert (
            "never-expires" in session_ids
        )  # Never expires sessions are always active
        assert "expired" not in session_ids

    def test_list_expired_sessions(self, state_tracker):
        """Test listing only expired sessions."""
        import time

        # Create active session
        state_tracker.create_session("active", "scenario-1", "prod", expiration_days=7)

        # Create session that never expires
        state_tracker.create_session(
            "never-expires", "scenario-4", "prod", expiration_days=None
        )

        # Create expired session
        state_tracker.create_session(
            "expired-1", "scenario-2", "prod", expiration_days=0
        )
        time.sleep(0.01)
        state_tracker.create_session(
            "expired-2", "scenario-3", "prod", expiration_days=0
        )
        time.sleep(0.01)

        expired = state_tracker.list_expired_sessions()
        expired_ids = [s.session_id for s in expired]

        assert len(expired) == 2
        assert "expired-1" in expired_ids
        assert "expired-2" in expired_ids
        assert "active" not in expired_ids
        assert (
            "never-expires" not in expired_ids
        )  # Never expires sessions are never expired


class TestSessionDeletion:
    """Test session deletion."""

    def test_delete_session(self, state_tracker):
        """Test deleting a session."""
        state_tracker.create_session("session-1", "scenario-1", "prod")
        state_tracker.create_session("session-2", "scenario-2", "prod")

        # Verify both exist
        assert state_tracker.get_session("session-1") is not None
        assert state_tracker.get_session("session-2") is not None

        # Delete one
        state_tracker.delete_session("session-1")

        # Verify deletion
        assert state_tracker.get_session("session-1") is None
        assert state_tracker.get_session("session-2") is not None

    def test_delete_session_with_resources(self, state_tracker):
        """Test deleting a session that has resources."""
        state_tracker.create_session("session-1", "scenario-1", "prod")
        state_tracker.add_resource("session-1", "github_repo", "org/repo", "repo")

        state_tracker.delete_session("session-1")

        assert state_tracker.get_session("session-1") is None

    def test_delete_nonexistent_session_raises_error(self, state_tracker):
        """Test that deleting nonexistent session raises error."""
        with pytest.raises(ValueError, match="Session .* not found"):
            state_tracker.delete_session("nonexistent")

    def test_delete_persists_to_file(self, state_tracker, temp_state_file):
        """Test that session deletion is persisted to file."""
        state_tracker.create_session("session-1", "scenario-1", "prod")
        state_tracker.delete_session("session-1")

        # Create new tracker pointing to same file
        tracker2 = StateTracker(state_file=temp_state_file)

        # Session should not exist
        assert tracker2.get_session("session-1") is None


class TestSessionMetadata:
    """Test session metadata management."""

    def test_update_session_metadata(self, state_tracker):
        """Test updating session metadata."""
        state_tracker.create_session("session-1", "scenario-1", "prod")

        metadata = {
            "status": "completed",
            "notes": "Demo was successful",
        }

        state_tracker.update_session_metadata("session-1", metadata)

        session = state_tracker.get_session("session-1")
        assert session.metadata["status"] == "completed"
        assert session.metadata["notes"] == "Demo was successful"

    def test_update_metadata_merges_with_existing(self, state_tracker):
        """Test that updating metadata merges with existing metadata."""
        initial_metadata = {"user": "testuser", "version": "1.0"}
        state_tracker.create_session(
            "session-1", "scenario-1", "prod", metadata=initial_metadata
        )

        # Update with additional metadata
        state_tracker.update_session_metadata("session-1", {"status": "completed"})

        session = state_tracker.get_session("session-1")
        assert session.metadata["user"] == "testuser"  # Original
        assert session.metadata["version"] == "1.0"  # Original
        assert session.metadata["status"] == "completed"  # New

    def test_update_nonexistent_session_metadata_raises_error(self, state_tracker):
        """Test that updating nonexistent session metadata raises error."""
        with pytest.raises(ValueError, match="Session .* not found"):
            state_tracker.update_session_metadata("nonexistent", {"key": "value"})


class TestResourceModel:
    """Test Resource model."""

    def test_resource_creation_minimal(self):
        """Test creating a resource with minimal fields."""
        resource = Resource(
            type="github_repo",
            id="org/repo",
            name="repo",
        )

        assert resource.type == "github_repo"
        assert resource.id == "org/repo"
        assert resource.name == "repo"
        assert resource.org_id is None
        assert resource.metadata == {}

    def test_resource_creation_full(self):
        """Test creating a resource with all fields."""
        metadata = {"visibility": "public"}
        resource = Resource(
            type="cloudbees_component",
            id="component-123",
            name="my-component",
            org_id="org-456",
            metadata=metadata,
        )

        assert resource.type == "cloudbees_component"
        assert resource.id == "component-123"
        assert resource.name == "my-component"
        assert resource.org_id == "org-456"
        assert resource.metadata == metadata


class TestSessionModel:
    """Test Session model."""

    def test_session_creation(self):
        """Test creating a session model."""
        now = datetime.now()
        expires = now + timedelta(days=7)

        session = Session(
            session_id="test-123",
            scenario_id="hackers-app",
            environment="prod",
            created_at=now,
            expires_at=expires,
        )

        assert session.session_id == "test-123"
        assert session.scenario_id == "hackers-app"
        assert session.environment == "prod"
        assert session.created_at == now
        assert session.expires_at == expires
        assert session.resources == []
        assert session.metadata == {}

    def test_session_with_resources(self):
        """Test creating a session with resources."""
        now = datetime.now()
        expires = now + timedelta(days=7)

        resources = [
            Resource(type="github_repo", id="org/repo", name="repo"),
            Resource(
                type="cloudbees_component",
                id="component-123",
                name="component",
                org_id="org-456",
            ),
        ]

        session = Session(
            session_id="test-123",
            scenario_id="hackers-app",
            environment="prod",
            created_at=now,
            expires_at=expires,
            resources=resources,
        )

        assert len(session.resources) == 2
        assert session.resources[0].type == "github_repo"
        assert session.resources[1].type == "cloudbees_component"
