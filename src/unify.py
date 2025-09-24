"""
Minimal CloudBees Platform API client
Built from api-platform.json spec but only implementing what we need
"""

from typing import Any

import httpx

from .config import settings
from .exceptions import UnifyAPIError


class UnifyAPIClient:
    """Simple API client for CloudBees Platform API"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url or settings.UNIFY_API_HOST
        self.api_key = api_key  # No fallback to settings - PAT now required per-user

        # Set up headers
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.Client(
            base_url=self.base_url, headers=self.headers, timeout=30.0
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    def close(self):
        self.client.close()

    def _make_request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        """Make an HTTP request with error handling"""
        try:
            response = self.client.request(method, url, **kwargs)
            response.raise_for_status()

            # Handle empty responses
            if not response.content:
                return {}

            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code} error for {method} {url}"
            try:
                error_detail = e.response.json()
                if "message" in error_detail:
                    error_msg += f": {error_detail['message']}"
                elif "error" in error_detail:
                    error_msg += f": {error_detail['error']}"
            except Exception:
                error_msg += f": {e.response.text}"

            raise UnifyAPIError(
                error_msg, e.response.status_code, e.response.text
            ) from e
        except httpx.RequestError as e:
            raise UnifyAPIError(f"Request failed: {str(e)}") from e
        except Exception as e:
            raise UnifyAPIError(f"Unexpected error: {str(e)}") from e

    # Services API
    def list_services(self, org_id: str) -> dict[str, Any]:
        """List services for an organization"""
        return self._make_request("GET", f"/v1/resources/{org_id}/services")

    def create_service(
        self, org_id: str, service_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new service"""
        return self._make_request(
            "POST", f"/v1/organizations/{org_id}/services", json=service_data
        )

    def delete_service(self, org_id: str, service_id: str) -> None:
        """Delete a service"""
        self._make_request(
            "DELETE", f"/v1/organizations/{org_id}/services/{service_id}"
        )

    # Repositories API
    def list_repositories(self, org_id: str) -> dict[str, Any]:
        """List repositories for an organization"""
        return self._make_request("GET", f"/v1/resources/{org_id}/repositories")

    # Automations API
    def list_automations(self, org_id: str, service_id: str) -> dict[str, Any]:
        """List automations for a service"""
        return self._make_request(
            "GET", f"/v1/organizations/{org_id}/services/{service_id}/automations"
        )

    def get_automation_yaml(
        self, org_id: str, service_id: str, automation_id: str
    ) -> dict[str, Any]:
        """Get YAML content of an automation"""
        return self._make_request(
            "GET",
            f"/v1/organizations/{org_id}/services/{service_id}/automations/{automation_id}/yaml",
        )

    def update_automation(
        self,
        org_id: str,
        service_id: str,
        automation_id: str,
        yaml_content: str,
        commit_message: str,
        commit_sha: str | None = None,
    ) -> dict[str, Any]:
        """Update an automation"""
        data = {
            "yamlContent": yaml_content,
            "commitMessage": commit_message,
        }
        if commit_sha:
            data["commitSha"] = commit_sha

        return self._make_request(
            "PUT",
            f"/v1/organizations/{org_id}/services/{service_id}/automations/{automation_id}",
            json=data,
        )

    # Teams API
    def get_team(self, organization_id: str, team_id: str) -> dict[str, Any]:
        """Get team by ID"""
        return self._make_request(
            "GET", f"/v1/organizations/{organization_id}/teams/{team_id}"
        )

    # Environments API
    def create_environment(
        self, org_id: str, env_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new environment"""
        return self._make_request(
            "POST", f"/v1/resources/{org_id}/endpoints", json=env_data
        )

    def update_environment(
        self, org_id: str, env_id: str, env_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an environment"""
        return self._make_request(
            "PUT", f"/v1/resources/{org_id}/endpoints/{env_id}", json=env_data
        )

    def list_environments(self, org_id: str, page_length: int = 1000) -> dict[str, Any]:
        """List environments for an organization"""
        params = {
            "filter.contributionTypes": "cb.platform.environment",
            "parents": "true",
            "pagination.pageLength": page_length,
        }
        return self._make_request(
            "GET", f"/v1/resources/{org_id}/endpoints", params=params
        )

    def get_environment(self, org_id: str, env_id: str) -> dict[str, Any]:
        """Get a single environment by ID"""
        return self._make_request("GET", f"/v1/resources/{org_id}/endpoints/{env_id}")

    # Enhanced Services API
    def list_services_by_type(
        self, org_id: str, service_type: str | None = None
    ) -> dict[str, Any]:
        """List services filtered by type (COMPONENT or APPLICATION)"""
        params = {}
        if service_type:
            type_filter = (
                f"{service_type}_FILTER"
                if not service_type.endswith("_FILTER")
                else service_type
            )
            params["typeFilter"] = type_filter

        return self._make_request(
            "GET", f"/v1/organizations/{org_id}/services", params=params
        )

    def list_components(self, org_id: str) -> dict[str, Any]:
        """List all components for an organization"""
        return self.list_services_by_type(org_id, "COMPONENT")

    def list_applications(self, org_id: str) -> dict[str, Any]:
        """List all applications for an organization"""
        return self.list_services_by_type(org_id, "APPLICATION")

    def update_service(
        self, org_id: str, service_id: str, service_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a service (component or application)"""
        return self._make_request(
            "PUT",
            f"/v1/organizations/{org_id}/services/{service_id}",
            json=service_data,
        )

    # Feature Flags API
    def list_flags(self, app_id: str) -> dict[str, Any]:
        """List all feature flags for an application"""
        return self._make_request("GET", f"/v1/applications/{app_id}/flags")

    def create_feature_flag(
        self, app_id: str, flag_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new feature flag"""
        return self._make_request(
            "POST", f"/v1/applications/{app_id}/flags", json=flag_data
        )

    def enable_flag_in_environment(
        self, app_id: str, flag_id: str, env_id: str, enabled: bool = True
    ) -> dict[str, Any]:
        """Enable or disable a flag in a specific environment"""
        return self._make_request(
            "POST",
            f"/v1/applications/{app_id}/flags/{flag_id}/configuration/environments/{env_id}/configstate",
            json={"enabled": enabled},
        )

    def configure_flag_targeting(
        self, app_id: str, flag_id: str, env_id: str, config_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Configure flag targeting rules for an environment"""
        return self._make_request(
            "PATCH",
            f"/v1/applications/{app_id}/flags/{flag_id}/configuration/environments/{env_id}",
            json=config_data,
        )

    # Helper methods for common service operations
    def create_component(
        self,
        org_id: str,
        name: str,
        repository_url: str,
        endpoint_id: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Create a new component service"""
        service_data = {
            "service": {
                "name": name,
                "description": description,
                "endpointId": endpoint_id,
                "repositoryUrl": repository_url,
            }
        }
        return self.create_service(org_id, service_data)

    def create_application(
        self,
        org_id: str,
        name: str,
        description: str = "",
        repository_url: str = "",
        endpoint_id: str = "",
        default_branch: str = "",
        linked_component_ids: list[str] | None = None,
        linked_environment_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new application service"""
        # Create repositoryHref (without .git) if repository_url is provided
        repository_href = ""
        if repository_url and repository_url.endswith(".git"):
            repository_href = repository_url[:-4]  # Remove .git suffix

        service_data = {
            "service": {
                "name": name,
                "description": description,
                "repositoryUrl": repository_url,
                "repositoryHref": repository_href,
                "endpointId": endpoint_id,
                "defaultBranch": default_branch,
                "linkedComponentIds": linked_component_ids or [],
                "linkedEnvironmentIds": linked_environment_ids or [],
                "components": [],
                "environments": [],
                "organizationId": org_id,
                "serviceType": "APPLICATION",
            }
        }
        return self.create_service(org_id, service_data)

    def create_basic_environment(
        self,
        org_id: str,
        name: str,
        description: str = "",
        properties: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a basic environment with optional properties"""
        env_data = {
            "resourceId": org_id,
            "contributionId": "cb.configuration.basic-environment",
            "contributionType": "cb.platform.environment",
            "contributionTargets": ["cb.configuration.environments"],
            "name": name,
            "description": description,
            "properties": properties
            or [{"name": "approvers", "bool": False, "isSecret": False}],
        }
        return self.create_environment(org_id, env_data)

    def create_boolean_flag(
        self,
        app_id: str,
        name: str,
        description: str = "",
        is_permanent: bool = False,
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a boolean feature flag"""
        flag_data = {
            "name": name,
            "description": description,
            "flagType": "Boolean",
            "labels": labels or [],
            "isPermanent": is_permanent,
            "variants": ["true", "false"],
        }
        return self.create_feature_flag(app_id, flag_data)

    def get_environment_sdk_key(self, app_id: str, env_id: str) -> dict[str, Any]:
        """Get SDK key for an application environment"""
        return self._make_request(
            "GET", f"/v1/applications/{app_id}/environments/{env_id}/sdk-key"
        )

    # Organizations API
    def get_organization(self, org_id: str) -> dict[str, Any]:
        """Get organization details by ID"""
        return self._make_request("GET", f"/v1/organizations/{org_id}")
