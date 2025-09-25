"""Tests for cleanup API endpoints."""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.database import Database
from src.main import app
from src.security import SecurePATManager


@pytest.fixture
def test_key():
    """Generate a test encryption key."""
    return SecurePATManager.generate_key()


@pytest.fixture
async def test_db_with_data(test_key):
    """Create test database with sample data."""
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Set up environment with test key
        with patch.dict(os.environ, {"PAT_ENCRYPTION_KEY": test_key}):
            # Create database
            db = Database(db_path)
            await db.initialize()

            # Create test user
            await db.create_user("test@cloudbees.com", "Test User")

            # Store encrypted PATs
            pat_manager = SecurePATManager()
            encrypted_unify_pat = pat_manager.encrypt("test-unify-pat")
            await db.store_pat("test@cloudbees.com", encrypted_unify_pat, "cloudbees")

            # Create test sessions
            await db.create_session(
                "session1",
                "test@cloudbees.com",
                "test-scenario",
                parameters={"param1": "value1"},
            )
            await db.create_session(
                "session2",
                "test@cloudbees.com",
                "another-scenario",
                parameters={"param2": "value2"},
            )

            # Create test resources
            await db.register_resource(
                "resource1",
                "session1",
                "github_repo",
                "Test Repo 1",
                "github",
                "owner/repo1",
            )
            await db.register_resource(
                "resource2",
                "session1",
                "cloudbees_component",
                "Test Component",
                "cloudbees",
                "comp-uuid",
            )
            await db.register_resource(
                "resource3",
                "session2",
                "github_repo",
                "Test Repo 2",
                "github",
                "owner/repo2",
            )

            yield db

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def mock_auth_service():
    """Create a mock auth service."""
    auth_service = AsyncMock()
    auth_service.get_working_pat = AsyncMock(return_value="test-unify-pat")
    return auth_service


@pytest.mark.asyncio
async def test_list_my_sessions_success(test_db_with_data, client):
    """Test successful session listing."""
    with (
        patch("src.main.get_database", return_value=test_db_with_data),
        patch("src.main.get_auth_service", return_value=mock_auth_service()),
    ):
        response = client.get(
            "/api/my/sessions", headers={"X-User-Email": "test@cloudbees.com"}
        )

        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 2

        # Check session 1
        session1 = next(s for s in sessions if s["id"] == "session1")
        assert session1["scenario_id"] == "test-scenario"
        assert session1["resource_count"] == 2  # 2 resources in session1
        assert session1["parameters"] == {"param1": "value1"}

        # Check session 2
        session2 = next(s for s in sessions if s["id"] == "session2")
        assert session2["scenario_id"] == "another-scenario"
        assert session2["resource_count"] == 1  # 1 resource in session2


@pytest.mark.asyncio
async def test_list_my_sessions_invalid_email():
    """Test session listing with invalid email."""
    client = TestClient(app)
    response = client.get(
        "/api/my/sessions", headers={"X-User-Email": "invalid@gmail.com"}
    )

    assert response.status_code == 400
    assert "Only CloudBees email addresses are allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_my_sessions_missing_header():
    """Test session listing with missing email header."""
    client = TestClient(app)
    response = client.get("/api/my/sessions")

    assert response.status_code == 400
    assert "X-User-Email header is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_my_sessions_unauthenticated():
    """Test session listing when user has no valid PAT."""
    with patch("src.main.get_auth_service") as mock_get_auth:
        mock_auth = AsyncMock()
        mock_auth.get_working_pat = AsyncMock(side_effect=Exception("No valid PAT"))
        mock_get_auth.return_value = mock_auth

        client = TestClient(app)
        response = client.get(
            "/api/my/sessions", headers={"X-User-Email": "test@cloudbees.com"}
        )

        assert response.status_code == 500  # Should be handled by @handle_auth_errors


@pytest.mark.asyncio
async def test_list_session_resources_success(test_db_with_data, client):
    """Test successful resource listing for a session."""
    with (
        patch("src.main.get_database", return_value=test_db_with_data),
        patch("src.main.get_auth_service", return_value=mock_auth_service()),
    ):
        response = client.get(
            "/api/sessions/session1/resources",
            headers={"X-User-Email": "test@cloudbees.com"},
        )

        assert response.status_code == 200
        resources = response.json()
        assert len(resources) == 2

        # Check resources
        repo_resource = next(
            r for r in resources if r["resource_type"] == "github_repo"
        )
        assert repo_resource["resource_name"] == "Test Repo 1"
        assert repo_resource["platform"] == "github"
        assert repo_resource["status"] == "active"

        component_resource = next(
            r for r in resources if r["resource_type"] == "cloudbees_component"
        )
        assert component_resource["resource_name"] == "Test Component"
        assert component_resource["platform"] == "cloudbees"


@pytest.mark.asyncio
async def test_list_session_resources_not_found(test_db_with_data, client):
    """Test resource listing for non-existent session."""
    with (
        patch("src.main.get_database", return_value=test_db_with_data),
        patch("src.main.get_auth_service", return_value=mock_auth_service()),
    ):
        response = client.get(
            "/api/sessions/nonexistent/resources",
            headers={"X-User-Email": "test@cloudbees.com"},
        )

        assert response.status_code == 404
        assert "not found or not owned" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_session_resources_wrong_owner(test_db_with_data, client):
    """Test resource listing with wrong owner email."""
    with (
        patch("src.main.get_database", return_value=test_db_with_data),
        patch("src.main.get_auth_service", return_value=mock_auth_service()),
    ):
        response = client.get(
            "/api/sessions/session1/resources",
            headers={"X-User-Email": "other@cloudbees.com"},
        )

        assert response.status_code == 404
        assert "not found or not owned" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cleanup_session_success(test_db_with_data, client):
    """Test successful session cleanup."""
    # Mock cleanup service
    mock_cleanup_service = AsyncMock()
    mock_cleanup_result = {
        "session_id": "session1",
        "total_resources": 2,
        "successful": 2,
        "failed": 0,
        "errors": [],
    }
    mock_cleanup_service.cleanup_session = AsyncMock(return_value=mock_cleanup_result)

    with (
        patch("src.main.get_database", return_value=test_db_with_data),
        patch("src.main.get_auth_service", return_value=mock_auth_service()),
        patch("src.main.get_cleanup_service", return_value=mock_cleanup_service),
    ):
        response = client.delete(
            "/api/sessions/session1", headers={"X-User-Email": "test@cloudbees.com"}
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["session_id"] == "session1"
        assert result["total_resources"] == 2
        assert result["successful"] == 2
        assert result["failed"] == 0
        assert result["errors"] == []

        # Verify cleanup service was called
        mock_cleanup_service.cleanup_session.assert_called_once_with(
            "session1", "test@cloudbees.com"
        )


@pytest.mark.asyncio
async def test_cleanup_session_partial_failure(test_db_with_data, client):
    """Test session cleanup with some failures."""
    # Mock cleanup service with partial failure
    mock_cleanup_service = AsyncMock()
    mock_cleanup_result = {
        "session_id": "session1",
        "total_resources": 2,
        "successful": 1,
        "failed": 1,
        "errors": ["Failed to delete resource2: API error"],
    }
    mock_cleanup_service.cleanup_session = AsyncMock(return_value=mock_cleanup_result)

    with (
        patch("src.main.get_database", return_value=test_db_with_data),
        patch("src.main.get_auth_service", return_value=mock_auth_service()),
        patch("src.main.get_cleanup_service", return_value=mock_cleanup_service),
    ):
        response = client.delete(
            "/api/sessions/session1", headers={"X-User-Email": "test@cloudbees.com"}
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is False  # Should be false when there are failures
        assert result["failed"] == 1
        assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_cleanup_session_not_found(test_db_with_data, client):
    """Test cleanup for non-existent session."""
    mock_cleanup_service = AsyncMock()
    mock_cleanup_service.cleanup_session = AsyncMock(
        side_effect=ValueError(
            "Session nonexistent not found or not owned by test@cloudbees.com"
        )
    )

    with (
        patch("src.main.get_database", return_value=test_db_with_data),
        patch("src.main.get_auth_service", return_value=mock_auth_service()),
        patch("src.main.get_cleanup_service", return_value=mock_cleanup_service),
    ):
        response = client.delete(
            "/api/sessions/nonexistent", headers={"X-User-Email": "test@cloudbees.com"}
        )

        assert response.status_code == 404
        assert "not found or not owned" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cleanup_session_invalid_email():
    """Test cleanup with invalid email."""
    client = TestClient(app)
    response = client.delete(
        "/api/sessions/session1", headers={"X-User-Email": "invalid@gmail.com"}
    )

    assert response.status_code == 400
    assert "Only CloudBees email addresses are allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_endpoints_require_authentication():
    """Test that all cleanup API endpoints require valid authentication."""
    from src.security import NoValidPATFoundError

    mock_auth_service = AsyncMock()
    mock_auth_service.get_working_pat = AsyncMock(
        side_effect=NoValidPATFoundError("No valid PAT found")
    )

    with patch("src.main.get_auth_service", return_value=mock_auth_service):
        client = TestClient(app)

        # Test all endpoints
        endpoints = [
            ("GET", "/api/my/sessions"),
            ("GET", "/api/sessions/session1/resources"),
            ("DELETE", "/api/sessions/session1"),
        ]

        headers = {"X-User-Email": "test@cloudbees.com"}
        for method, url in endpoints:
            response = getattr(client, method.lower())(url, headers=headers)
            assert response.status_code == 401
            assert "No valid CloudBees PAT found" in response.json()["detail"]
