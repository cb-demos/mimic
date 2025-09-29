from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import settings


def test_api_root(client: TestClient):
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Mimic API"}


@patch("src.main.ScenarioService")
def test_ui_root(mock_service_class, client: TestClient):
    # Mock the scenario service
    mock_service = MagicMock()
    mock_service.list_scenarios.return_value = [
        {"id": "test-scenario", "name": "Test Scenario"}
    ]
    mock_scenario = MagicMock()
    mock_scenario.id = "test-scenario"
    mock_scenario.name = "Test Scenario"
    mock_scenario.summary = "Test description"
    mock_scenario.details = None
    mock_scenario.repositories = []
    mock_scenario.applications = []
    mock_scenario.environments = []
    mock_scenario.wip = False
    mock_scenario.parameter_schema = None
    mock_service.get_scenario.return_value = mock_scenario
    mock_service_class.return_value = mock_service

    # Mock asset_hashes in the template globals
    from src.main import templates

    templates.env.globals["asset_hashes"] = {"style.css": "mocked_hash"}

    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CloudBees Scenario Manager" in response.text


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == settings.APP_NAME
    assert data["version"] == settings.VERSION


@pytest.mark.asyncio
async def test_async_health_check(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"


@patch("src.main.ScenarioService")
@patch("src.main.get_auth_service")
def test_instantiate_scenario_with_expiration(
    mock_auth_service_func, mock_service_class, client: TestClient
):
    """Test scenario instantiation with expiration parameter."""

    # Mock the auth service
    mock_auth = AsyncMock()
    mock_auth.get_pat_by_token.return_value = "test-pat"
    mock_auth_service_func.return_value = mock_auth

    # Mock the scenario service
    mock_service = AsyncMock()
    mock_service.start_scenario_execution.return_value = "test-session-id"
    mock_service_class.return_value = mock_service

    # Test request with expiration
    request_data = {
        "organization_id": "test-org-id",
        "email": "test@cloudbees.com",
        "auth_token": "123",
        "invitee_username": "testuser",
        "parameters": {"app_name": "test-app"},
        "expires_in_days": 14,
    }

    response = client.post("/instantiate/test-scenario", json=request_data)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "started"
    assert result["scenario_id"] == "test-scenario"
    assert result["session_id"] == "test-session-id"

    # Verify the service was called with the expiration parameter
    mock_service.start_scenario_execution.assert_called_once_with(
        scenario_id="test-scenario",
        organization_id="test-org-id",
        unify_pat="test-pat",
        email="test@cloudbees.com",
        invitee_username="testuser",
        parameters={"app_name": "test-app"},
        expires_in_days=14,
    )


@patch("src.main.ScenarioService")
@patch("src.main.get_auth_service")
def test_instantiate_scenario_without_expiration(
    mock_auth_service_func, mock_service_class, client: TestClient
):
    """Test scenario instantiation without expiration parameter (default behavior)."""

    # Mock the auth service
    mock_auth = AsyncMock()
    mock_auth.get_pat_by_token.return_value = "test-pat"
    mock_auth_service_func.return_value = mock_auth

    # Mock the scenario service
    mock_service = AsyncMock()
    mock_service.start_scenario_execution.return_value = "test-session-id-2"
    mock_service_class.return_value = mock_service

    # Test request without expiration (should use default 7 days)
    request_data = {
        "organization_id": "test-org-id",
        "email": "test@cloudbees.com",
        "auth_token": "456",
        "parameters": {"app_name": "test-app"},
    }

    response = client.post("/instantiate/test-scenario", json=request_data)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "started"
    assert result["scenario_id"] == "test-scenario"
    assert result["session_id"] == "test-session-id-2"

    # Verify the service was called with the default expiration (7 days)
    mock_service.start_scenario_execution.assert_called_once_with(
        scenario_id="test-scenario",
        organization_id="test-org-id",
        unify_pat="test-pat",
        email="test@cloudbees.com",
        invitee_username=None,  # Default value
        parameters={"app_name": "test-app"},
        expires_in_days=7,  # Default value
    )


# Admin endpoint security tests
@patch("src.main.get_auth_service")
@patch("src.main.get_scheduler")
def test_cleanup_status_requires_authentication(
    mock_scheduler_func, mock_auth_service_func, client: TestClient
):
    """Test that cleanup status endpoint requires authentication."""
    # Test without X-User-Email header
    response = client.get("/api/cleanup/status")
    assert response.status_code == 400
    assert "X-User-Email header is required" in response.json()["detail"]


@patch("src.main.get_auth_service")
@patch("src.main.get_scheduler")
def test_cleanup_status_with_valid_auth(
    mock_scheduler_func, mock_auth_service_func, client: TestClient
):
    """Test cleanup status endpoint with valid authentication."""
    # Mock auth service
    mock_auth = AsyncMock()
    mock_auth.get_pat.return_value = "test-pat"
    mock_auth_service_func.return_value = mock_auth

    # Mock scheduler
    mock_scheduler = MagicMock()
    mock_scheduler.get_job_status.return_value = {
        "scheduler_running": True,
        "job_running": False,
        "next_run_time": "2025-09-25T20:00:00",
    }
    mock_scheduler_func.return_value = mock_scheduler

    response = client.get(
        "/api/cleanup/status", headers={"X-User-Email": "test@cloudbees.com"}
    )
    assert response.status_code == 200

    result = response.json()
    assert result["scheduler_running"]
    assert not result["job_running"]


@patch("src.main.get_auth_service")
@patch("src.main.get_scheduler")
def test_cleanup_status_with_invalid_auth(
    mock_scheduler_func, mock_auth_service_func, client: TestClient
):
    """Test cleanup status endpoint with invalid authentication."""
    # Mock auth service to raise exception
    mock_auth = AsyncMock()
    mock_auth.get_pat.side_effect = Exception("Invalid PAT")
    mock_auth_service_func.return_value = mock_auth

    response = client.get(
        "/api/cleanup/status", headers={"X-User-Email": "invalid@example.com"}
    )
    assert response.status_code == 401
    assert "Invalid user authentication" in response.json()["detail"]


@patch("src.main.get_auth_service")
@patch("src.main.get_scheduler")
def test_cleanup_trigger_requires_authentication(
    mock_scheduler_func, mock_auth_service_func, client: TestClient
):
    """Test that cleanup trigger endpoint requires authentication."""
    # Test without X-User-Email header
    response = client.post("/api/cleanup/trigger")
    assert response.status_code == 400
    assert "X-User-Email header is required" in response.json()["detail"]


@patch("src.main.get_auth_service")
@patch("src.main.get_scheduler")
def test_cleanup_trigger_with_valid_auth(
    mock_scheduler_func, mock_auth_service_func, client: TestClient
):
    """Test cleanup trigger endpoint with valid authentication."""
    # Mock auth service
    mock_auth = AsyncMock()
    mock_auth.get_pat.return_value = "test-pat"
    mock_auth_service_func.return_value = mock_auth

    # Mock scheduler
    mock_scheduler = AsyncMock()
    mock_scheduler.trigger_cleanup_now.return_value = {
        "status": "success",
        "message": "Cleanup triggered",
        "result": {"total_resources": 0},
    }
    mock_scheduler_func.return_value = mock_scheduler

    response = client.post(
        "/api/cleanup/trigger", headers={"X-User-Email": "test@cloudbees.com"}
    )
    assert response.status_code == 200

    result = response.json()
    assert result["status"] == "success"
    mock_scheduler.trigger_cleanup_now.assert_called_once()


@patch("src.main.get_auth_service")
@patch("src.main.get_scheduler")
def test_cleanup_trigger_with_invalid_auth(
    mock_scheduler_func, mock_auth_service_func, client: TestClient
):
    """Test cleanup trigger endpoint with invalid authentication."""
    # Mock auth service to raise exception
    mock_auth = AsyncMock()
    mock_auth.get_pat.side_effect = Exception("Invalid PAT")
    mock_auth_service_func.return_value = mock_auth

    response = client.post(
        "/api/cleanup/trigger", headers={"X-User-Email": "invalid@example.com"}
    )
    assert response.status_code == 401
    assert "Invalid user authentication" in response.json()["detail"]
