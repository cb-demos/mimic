"""Tests for the database module."""

import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from src.database import Database


@pytest.fixture
async def test_db():
    """Create a test database instance with temporary file."""
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = Database(db_path)
        await db.initialize()
        yield db
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_database_initialization(test_db):
    """Test that database initializes with correct schema."""
    db = test_db

    # Check that tables exist by inserting test data
    await db.create_user("test@example.com", "Test User")

    # Verify user was created
    user = await db.fetchone(
        "SELECT * FROM users WHERE email = ?", ("test@example.com",)
    )
    assert user is not None
    assert user["email"] == "test@example.com"
    assert user["name"] == "Test User"


@pytest.mark.asyncio
async def test_create_and_update_user(test_db):
    """Test user creation and updates."""
    db = test_db

    # Create user
    await db.create_user("user@example.com", "Initial Name")

    user = await db.fetchone(
        "SELECT * FROM users WHERE email = ?", ("user@example.com",)
    )
    assert user["email"] == "user@example.com"
    assert user["name"] == "Initial Name"

    # Update user (should update name and last_active)
    await db.create_user("user@example.com", "Updated Name")

    updated_user = await db.fetchone(
        "SELECT * FROM users WHERE email = ?", ("user@example.com",)
    )
    assert updated_user["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_pat_storage_and_retrieval(test_db):
    """Test storing and retrieving PATs."""
    db = test_db

    # Create user first
    await db.create_user("user@example.com")

    # Store CloudBees PAT
    pat_id = await db.store_pat("user@example.com", "encrypted_cb_pat", "cloudbees")
    assert pat_id is not None

    # Store GitHub PAT
    await db.store_pat("user@example.com", "encrypted_gh_pat", "github")

    # Retrieve CloudBees PATs
    cb_pats = await db.get_user_pats("user@example.com", "cloudbees")
    assert len(cb_pats) == 1
    assert cb_pats[0]["encrypted_pat"] == "encrypted_cb_pat"
    assert cb_pats[0]["platform"] == "cloudbees"
    assert cb_pats[0]["is_active"] == 1  # SQLite returns 1 for TRUE

    # Retrieve GitHub PATs
    gh_pats = await db.get_user_pats("user@example.com", "github")
    assert len(gh_pats) == 1
    assert gh_pats[0]["encrypted_pat"] == "encrypted_gh_pat"


@pytest.mark.asyncio
async def test_pat_ordering(test_db):
    """Test that PATs are returned in correct order (newest first by ID)."""
    db = test_db

    await db.create_user("user@example.com")

    # Store multiple PATs - they should be ordered by creation (ID is auto-increment)
    pat1_id = await db.store_pat("user@example.com", "pat1", "cloudbees")
    pat2_id = await db.store_pat("user@example.com", "pat2", "cloudbees")
    pat3_id = await db.store_pat("user@example.com", "pat3", "cloudbees")

    # Verify IDs are increasing
    assert pat2_id > pat1_id
    assert pat3_id > pat2_id

    pats = await db.get_user_pats("user@example.com", "cloudbees")
    assert len(pats) == 3

    # Should be ordered by creation timestamp DESC, which should correlate with ID DESC
    # Check that we have all the expected PATs
    pat_values = [pat["encrypted_pat"] for pat in pats]
    assert "pat1" in pat_values
    assert "pat2" in pat_values
    assert "pat3" in pat_values

    # Check IDs are in descending order (newest first)
    pat_ids = [pat["id"] for pat in pats]
    assert pat_ids == sorted(pat_ids, reverse=True)


@pytest.mark.asyncio
async def test_mark_pat_inactive(test_db):
    """Test marking PATs as inactive."""
    db = test_db

    await db.create_user("user@example.com")
    pat_id = await db.store_pat("user@example.com", "test_pat", "cloudbees")

    # Mark as inactive
    await db.mark_pat_inactive(pat_id)

    # Should not appear in active PATs
    pats = await db.get_user_pats("user@example.com", "cloudbees")
    assert len(pats) == 0


@pytest.mark.asyncio
async def test_session_management(test_db):
    """Test creating and retrieving sessions."""
    db = test_db

    await db.create_user("user@example.com")

    # Create session with parameters
    session_params = {"param1": "value1", "param2": 123}
    expires_at = (datetime.now() + timedelta(days=7)).isoformat()

    await db.create_session(
        "session123", "user@example.com", "test-scenario", expires_at, session_params
    )

    # Retrieve user sessions
    sessions = await db.get_user_sessions("user@example.com")
    assert len(sessions) == 1

    session = sessions[0]
    assert session["id"] == "session123"
    assert session["email"] == "user@example.com"
    assert session["scenario_id"] == "test-scenario"
    assert session["expires_at"] == expires_at

    # Check parameters were stored as JSON
    stored_params = json.loads(session["parameters"])
    assert stored_params == session_params


@pytest.mark.asyncio
async def test_resource_registration(test_db):
    """Test registering resources to sessions."""
    db = test_db

    await db.create_user("user@example.com")
    await db.create_session("session123", "user@example.com", "test-scenario")

    # Register a resource
    metadata = {"org_id": "test-org", "extra": "data"}
    await db.register_resource(
        "resource123",
        "session123",
        "github_repo",
        "Test Repo",
        "github",
        "owner/repo",
        metadata,
    )

    # Get session resources
    resources = await db.get_session_resources("session123")
    assert len(resources) == 1

    resource = resources[0]
    assert resource["id"] == "resource123"
    assert resource["session_id"] == "session123"
    assert resource["resource_type"] == "github_repo"
    assert resource["resource_name"] == "Test Repo"
    assert resource["platform"] == "github"
    assert resource["resource_id"] == "owner/repo"
    assert resource["status"] == "active"

    # Check metadata
    stored_metadata = json.loads(resource["metadata"])
    assert stored_metadata == metadata


@pytest.mark.asyncio
async def test_user_sessions_with_resource_count(test_db):
    """Test that user sessions include resource counts."""
    db = test_db

    await db.create_user("user@example.com")
    await db.create_session("session1", "user@example.com", "scenario1")
    await db.create_session("session2", "user@example.com", "scenario2")

    # Add resources to first session
    await db.register_resource(
        "res1", "session1", "github_repo", "Repo 1", "github", "owner/repo1"
    )
    await db.register_resource(
        "res2", "session1", "github_repo", "Repo 2", "github", "owner/repo2"
    )

    # Second session has no resources

    sessions = await db.get_user_sessions("user@example.com")
    assert len(sessions) == 2

    # Find sessions by ID (order might vary)
    session1 = next(s for s in sessions if s["id"] == "session1")
    session2 = next(s for s in sessions if s["id"] == "session2")

    assert session1["resource_count"] == 2
    assert session2["resource_count"] == 0


@pytest.mark.asyncio
async def test_cleanup_workflow(test_db):
    """Test the two-stage cleanup workflow."""
    db = test_db

    await db.create_user("user@example.com")

    # Create expired and non-expired sessions
    past_time = (datetime.now() - timedelta(days=1)).isoformat()
    future_time = (datetime.now() + timedelta(days=1)).isoformat()

    await db.create_session(
        "expired_session", "user@example.com", "scenario1", past_time
    )
    await db.create_session(
        "active_session", "user@example.com", "scenario2", future_time
    )

    # Add resources to both
    await db.register_resource(
        "exp_res",
        "expired_session",
        "github_repo",
        "Expired Repo",
        "github",
        "owner/expired",
    )
    await db.register_resource(
        "act_res",
        "active_session",
        "github_repo",
        "Active Repo",
        "github",
        "owner/active",
    )

    # Stage 1: Mark expired resources
    marked_count = await db.mark_resources_for_deletion()
    assert marked_count == 1

    # Stage 2: Get resources pending deletion
    pending = await db.get_resources_pending_deletion()
    assert len(pending) == 1
    assert pending[0]["id"] == "exp_res"
    assert pending[0]["status"] == "delete_pending"
    assert pending[0]["email"] == "user@example.com"

    # Mark as deleted
    await db.mark_resource_deleted("exp_res")

    # Should no longer be pending
    pending_after = await db.get_resources_pending_deletion()
    assert len(pending_after) == 0

    # Active resource should still be active
    active_resources = await db.get_session_resources("active_session")
    assert len(active_resources) == 1
    assert active_resources[0]["status"] == "active"


@pytest.mark.asyncio
async def test_mark_resource_failed(test_db):
    """Test marking resources as failed."""
    db = test_db

    await db.create_user("user@example.com")
    await db.create_session("session1", "user@example.com", "scenario1")
    await db.register_resource(
        "res1", "session1", "github_repo", "Repo", "github", "owner/repo"
    )

    # Mark as failed
    await db.mark_resource_failed("res1")

    # Check status changed
    resource = await db.fetchone("SELECT * FROM resources WHERE id = ?", ("res1",))
    assert resource["status"] == "failed"


@pytest.mark.asyncio
async def test_database_wal_mode():
    """Test that database is initialized with WAL mode."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = Database(db_path)
        await db.initialize()

        # Check WAL mode is enabled
        async with db.connection() as conn:
            cursor = await conn.execute("PRAGMA journal_mode")
            result = await cursor.fetchone()
            assert result[0].upper() == "WAL"

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
