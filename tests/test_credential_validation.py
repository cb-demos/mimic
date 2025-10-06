"""Tests for credential validation functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mimic.exceptions import UnifyAPIError
from mimic.gh import GitHubClient
from mimic.unify import UnifyAPIClient


class TestGitHubCredentialValidation:
    """Test GitHub credential validation."""

    @pytest.mark.asyncio
    async def test_validate_credentials_success(self):
        """Test successful GitHub credential validation."""
        client = GitHubClient("test-token")

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            success, error = await client.validate_credentials()

            assert success is True
            assert error is None
            mock_request.assert_called_once_with("GET", "/user")

    @pytest.mark.asyncio
    async def test_validate_credentials_invalid_401(self):
        """Test GitHub credential validation with 401 error."""
        client = GitHubClient("invalid-token")

        # Mock 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            success, error = await client.validate_credentials()

            assert success is False
            assert error == "Invalid GitHub credentials"

    @pytest.mark.asyncio
    async def test_validate_credentials_invalid_403(self):
        """Test GitHub credential validation with 403 error."""
        client = GitHubClient("invalid-token")

        # Mock 403 response
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            success, error = await client.validate_credentials()

            assert success is False
            assert error == "Invalid GitHub credentials"

    @pytest.mark.asyncio
    async def test_validate_credentials_network_error(self):
        """Test GitHub credential validation with network error."""
        client = GitHubClient("test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.RequestError("Network error")

            success, error = await client.validate_credentials()

            assert success is False
            assert "Network error connecting to GitHub" in error

    @pytest.mark.asyncio
    async def test_validate_credentials_unexpected_status(self):
        """Test GitHub credential validation with unexpected status code."""
        client = GitHubClient("test-token")

        # Mock 500 response
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            success, error = await client.validate_credentials()

            assert success is False
            assert "unexpected status: 500" in error


class TestCloudBeesCredentialValidation:
    """Test CloudBees credential validation."""

    def test_validate_credentials_success(self):
        """Test successful CloudBees credential validation."""
        client = UnifyAPIClient(base_url="https://api.example.com", api_key="test-key")

        # Mock successful get_organization call
        with patch.object(client, "get_organization") as mock_get_org:
            mock_get_org.return_value = {"id": "test-org", "name": "Test Org"}

            success, error = client.validate_credentials("test-org")

            assert success is True
            assert error is None
            mock_get_org.assert_called_once_with("test-org")

    def test_validate_credentials_invalid_401(self):
        """Test CloudBees credential validation with 401 error."""
        client = UnifyAPIClient(
            base_url="https://api.example.com", api_key="invalid-key"
        )

        # Mock 401 error
        with patch.object(client, "get_organization") as mock_get_org:
            mock_get_org.side_effect = UnifyAPIError("Unauthorized", status_code=401)

            success, error = client.validate_credentials("test-org")

            assert success is False
            assert error == "Invalid CloudBees credentials"

    def test_validate_credentials_invalid_403(self):
        """Test CloudBees credential validation with 403 error."""
        client = UnifyAPIClient(
            base_url="https://api.example.com", api_key="invalid-key"
        )

        # Mock 403 error
        with patch.object(client, "get_organization") as mock_get_org:
            mock_get_org.side_effect = UnifyAPIError("Forbidden", status_code=403)

            success, error = client.validate_credentials("test-org")

            assert success is False
            assert error == "Invalid CloudBees credentials"

    def test_validate_credentials_org_not_found(self):
        """Test CloudBees credential validation with 404 error (org not found)."""
        client = UnifyAPIClient(base_url="https://api.example.com", api_key="test-key")

        # Mock 404 error
        with patch.object(client, "get_organization") as mock_get_org:
            mock_get_org.side_effect = UnifyAPIError("Not Found", status_code=404)

            success, error = client.validate_credentials("invalid-org")

            assert success is False
            assert "not found or no access" in error

    def test_validate_credentials_api_error(self):
        """Test CloudBees credential validation with other API error."""
        client = UnifyAPIClient(base_url="https://api.example.com", api_key="test-key")

        # Mock 500 error
        with patch.object(client, "get_organization") as mock_get_org:
            mock_get_org.side_effect = UnifyAPIError(
                "Internal Server Error", status_code=500
            )

            success, error = client.validate_credentials("test-org")

            assert success is False
            assert "CloudBees API error" in error

    def test_validate_credentials_generic_exception(self):
        """Test CloudBees credential validation with generic exception."""
        client = UnifyAPIClient(base_url="https://api.example.com", api_key="test-key")

        # Mock generic exception
        with patch.object(client, "get_organization") as mock_get_org:
            mock_get_org.side_effect = Exception("Connection timeout")

            success, error = client.validate_credentials("test-org")

            assert success is False
            assert "Error validating CloudBees credentials" in error
