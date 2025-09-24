from unittest.mock import MagicMock, patch

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
