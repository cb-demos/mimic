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
    mock_scenario.description = "Test description"
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
    mock_auth.get_pat.return_value = "test-pat"
    mock_auth_service_func.return_value = mock_auth

    # Mock the scenario service
    mock_service = AsyncMock()
    mock_service.execute_scenario.return_value = {
        "status": "success",
        "message": "Scenario executed successfully",
        "scenario_id": "test-scenario",
        "summary": {"created_resources": 3},
    }
    mock_service_class.return_value = mock_service

    # Test request with expiration
    request_data = {
        "organization_id": "test-org-id",
        "email": "test@cloudbees.com",
        "invitee_username": "testuser",
        "parameters": {"app_name": "test-app"},
        "expires_in_days": 14,
    }

    response = client.post("/instantiate/test-scenario", json=request_data)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"

    # Verify the service was called with the expiration parameter
    mock_service.execute_scenario.assert_called_once_with(
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
    mock_auth.get_pat.return_value = "test-pat"
    mock_auth_service_func.return_value = mock_auth

    # Mock the scenario service
    mock_service = AsyncMock()
    mock_service.execute_scenario.return_value = {
        "status": "success",
        "message": "Scenario executed successfully",
        "scenario_id": "test-scenario",
        "summary": {"created_resources": 2},
    }
    mock_service_class.return_value = mock_service

    # Test request without expiration (should use default 7 days)
    request_data = {
        "organization_id": "test-org-id",
        "email": "test@cloudbees.com",
        "parameters": {"app_name": "test-app"},
    }

    response = client.post("/instantiate/test-scenario", json=request_data)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"

    # Verify the service was called with the default expiration (7 days)
    mock_service.execute_scenario.assert_called_once_with(
        scenario_id="test-scenario",
        organization_id="test-org-id",
        unify_pat="test-pat",
        email="test@cloudbees.com",
        invitee_username=None,  # Default value
        parameters={"app_name": "test-app"},
        expires_in_days=7,  # Default value
    )
