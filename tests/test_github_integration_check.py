"""Tests for GitHub App integration validation functionality."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from mimic.cli.run_helpers.github_integration_check import check_github_integration
from mimic.scenarios import RepositoryConfig, Scenario
from mimic.unify import UnifyAPIClient


class TestListGitHubApps:
    """Test UnifyAPIClient.list_github_apps() method."""

    def test_list_github_apps_success(self):
        """Test successful listing of GitHub App integrations."""
        client = UnifyAPIClient(base_url="https://api.example.com", api_key="test-key")

        # Mock response with GitHub App integrations
        mock_response = {
            "endpoints": [
                {
                    "id": "endpoint-1",
                    "name": "cloudbees-days",
                    "contributionId": "cb.github.github-app-endpoint-type",
                    "properties": [
                        {"name": "provider", "string": "github"},
                        {"name": "app_install_target_name", "string": "cloudbees-days"},
                    ],
                },
                {
                    "id": "endpoint-2",
                    "name": "cloudbees-test",
                    "contributionId": "cb.github.github-app-endpoint-type",
                    "properties": [
                        {"name": "provider", "string": "github"},
                        {"name": "app_install_target_name", "string": "cloudbees-test"},
                    ],
                },
                {
                    "id": "endpoint-3",
                    "name": "jenkins-controller",
                    "contributionId": "cb.cbci.cbci-jenkins-controller-endpoint-type",
                    "properties": [
                        {
                            "name": "controllerUrl",
                            "string": "https://jenkins.example.com",
                        }
                    ],
                },
            ]
        }

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_response

            github_orgs = client.list_github_apps("test-org-id")

            assert len(github_orgs) == 2
            assert "cloudbees-days" in github_orgs
            assert "cloudbees-test" in github_orgs
            assert "jenkins-controller" not in github_orgs

    def test_list_github_apps_empty(self):
        """Test listing when no GitHub App integrations exist."""
        client = UnifyAPIClient(base_url="https://api.example.com", api_key="test-key")

        mock_response = {"endpoints": []}

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_response

            github_orgs = client.list_github_apps("test-org-id")

            assert github_orgs == []

    def test_list_github_apps_only_non_github_endpoints(self):
        """Test filtering out non-GitHub endpoint types."""
        client = UnifyAPIClient(base_url="https://api.example.com", api_key="test-key")

        mock_response = {
            "endpoints": [
                {
                    "id": "endpoint-1",
                    "name": "jenkins",
                    "contributionId": "cb.cbci.cbci-jenkins-controller-endpoint-type",
                    "properties": [],
                },
                {
                    "id": "endpoint-2",
                    "name": "dev-env",
                    "contributionId": "cb.platform.environment",
                    "properties": [],
                },
            ]
        }

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_response

            github_orgs = client.list_github_apps("test-org-id")

            assert github_orgs == []

    def test_list_github_apps_missing_target_name(self):
        """Test handling GitHub App endpoints without target_name property."""
        client = UnifyAPIClient(base_url="https://api.example.com", api_key="test-key")

        mock_response = {
            "endpoints": [
                {
                    "id": "endpoint-1",
                    "name": "incomplete-app",
                    "contributionId": "cb.github.github-app-endpoint-type",
                    "properties": [
                        {"name": "provider", "string": "github"},
                        # Missing app_install_target_name
                    ],
                }
            ]
        }

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = mock_response

            github_orgs = client.list_github_apps("test-org-id")

            # Should not crash, just return empty list
            assert github_orgs == []


class TestCheckGitHubIntegration:
    """Test check_github_integration() helper function."""

    def test_check_succeeds_when_org_configured(self, capsys):
        """Test validation passes when GitHub org is configured."""
        scenario = Scenario(
            id="test-scenario",
            name="Test Scenario",
            summary="Test",
            repositories=[
                RepositoryConfig(
                    source="template/repo",
                    target_org="${target_org}",
                    repo_name_template="test-repo",
                )
            ],
        )

        parameters = {"target_org": "cloudbees-days"}

        with patch(
            "mimic.cli.run_helpers.github_integration_check.UnifyAPIClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_github_apps.return_value = [
                "cloudbees-days",
                "cloudbees-test",
            ]
            mock_client_class.return_value = mock_client

            # Should not raise an exception
            check_github_integration(
                scenario=scenario,
                parameters=parameters,
                env_url="https://api.example.com",
                cloudbees_pat="test-pat",
                organization_id="test-org-id",
            )

            mock_client.list_github_apps.assert_called_once_with("test-org-id")

    def test_check_fails_when_org_not_configured(self):
        """Test validation fails when GitHub org is not configured."""
        scenario = Scenario(
            id="test-scenario",
            name="Test Scenario",
            summary="Test",
            repositories=[
                RepositoryConfig(
                    source="template/repo",
                    target_org="${target_org}",
                    repo_name_template="test-repo",
                )
            ],
        )

        parameters = {"target_org": "unconfigured-org"}

        with patch(
            "mimic.cli.run_helpers.github_integration_check.UnifyAPIClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_github_apps.return_value = [
                "cloudbees-days",
                "cloudbees-test",
            ]
            mock_client_class.return_value = mock_client

            with pytest.raises(typer.Exit) as exc_info:
                check_github_integration(
                    scenario=scenario,
                    parameters=parameters,
                    env_url="https://api.example.com",
                    cloudbees_pat="test-pat",
                    organization_id="test-org-id",
                )

            assert exc_info.value.exit_code == 1

    def test_check_skips_when_no_repositories(self):
        """Test validation is skipped when scenario has no repositories."""
        scenario = Scenario(
            id="test-scenario",
            name="Test Scenario",
            summary="Test",
            repositories=[],  # No repositories
        )

        parameters = {"target_org": "any-org"}

        # Should not make any API calls
        with patch(
            "mimic.cli.run_helpers.github_integration_check.UnifyAPIClient"
        ) as mock_client_class:
            check_github_integration(
                scenario=scenario,
                parameters=parameters,
                env_url="https://api.example.com",
                cloudbees_pat="test-pat",
                organization_id="test-org-id",
            )

            # Client should never be instantiated
            mock_client_class.assert_not_called()

    def test_check_skips_when_no_target_org(self):
        """Test validation is skipped when no target_org parameter exists."""
        scenario = Scenario(
            id="test-scenario",
            name="Test Scenario",
            summary="Test",
            repositories=[
                RepositoryConfig(
                    source="template/repo",
                    target_org="${target_org}",
                    repo_name_template="test-repo",
                )
            ],
        )

        parameters = {}  # No target_org parameter

        # Should not make any API calls
        with patch(
            "mimic.cli.run_helpers.github_integration_check.UnifyAPIClient"
        ) as mock_client_class:
            check_github_integration(
                scenario=scenario,
                parameters=parameters,
                env_url="https://api.example.com",
                cloudbees_pat="test-pat",
                organization_id="test-org-id",
            )

            # Client should never be instantiated
            mock_client_class.assert_not_called()

    def test_check_handles_api_error(self):
        """Test validation handles API errors gracefully."""
        scenario = Scenario(
            id="test-scenario",
            name="Test Scenario",
            summary="Test",
            repositories=[
                RepositoryConfig(
                    source="template/repo",
                    target_org="${target_org}",
                    repo_name_template="test-repo",
                )
            ],
        )

        parameters = {"target_org": "cloudbees-days"}

        with patch(
            "mimic.cli.run_helpers.github_integration_check.UnifyAPIClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_github_apps.side_effect = Exception("API Error")
            mock_client_class.return_value = mock_client

            with pytest.raises(typer.Exit) as exc_info:
                check_github_integration(
                    scenario=scenario,
                    parameters=parameters,
                    env_url="https://api.example.com",
                    cloudbees_pat="test-pat",
                    organization_id="test-org-id",
                )

            assert exc_info.value.exit_code == 1
