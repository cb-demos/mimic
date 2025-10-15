"""
Minimal CloudBees Unify API client
Built from api-platform.json spec but only implementing what we need
"""

from typing import Any

import httpx

from mimic.config_manager import ConfigManager
from mimic.exceptions import UnifyAPIError


class UnifyAPIClient:
    """Simple API client for CloudBees Unify API"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        # For CLI, base_url should be provided from environment config
        # If not provided, raise error (no default URL in refactored architecture)
        if not base_url:
            raise ValueError(
                "base_url is required - get it from environment configuration"
            )
        self.base_url = base_url
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

    def validate_credentials(self, org_id: str) -> tuple[bool, str | None]:
        """Validate CloudBees credentials by making a lightweight API call.

        Args:
            org_id: Organization ID to test access

        Returns:
            Tuple of (success: bool, error_message: str | None)
            - (True, None) if credentials are valid
            - (False, error_message) if credentials are invalid or there's an error
        """
        try:
            # Use get_organization as a lightweight test
            self.get_organization(org_id)
            return (True, None)
        except UnifyAPIError as e:
            if e.status_code in [401, 403]:
                return (False, "Invalid CloudBees credentials")
            elif e.status_code == 404:
                return (False, f"Organization '{org_id}' not found or no access")
            else:
                return (False, f"CloudBees API error: {str(e)}")
        except Exception as e:
            return (False, f"Error validating CloudBees credentials: {str(e)}")

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

    # Teams API
    def get_team(self, organization_id: str, team_id: str) -> dict[str, Any]:
        """Get team by ID"""
        return self._make_request(
            "GET", f"/v1/organizations/{organization_id}/teams/{team_id}"
        )

    # Runs API
    def list_runs(
        self, org_id: str, service_id: str, page_length: int = 50
    ) -> dict[str, Any]:
        """List workflow runs for a service/component"""
        params = {"pagination.pageLength": page_length}
        return self._make_request(
            "GET",
            f"/v1/organizations/{org_id}/services/{service_id}/runs",
            params=params,
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

    # Properties API
    def list_properties(
        self, resource_id: str, page_length: int = 1000
    ) -> dict[str, Any]:
        """List properties for a resource (organization, sub-org, or component).

        Args:
            resource_id: The resource ID (org ID, sub-org ID, or component ID)
            page_length: Number of properties to return per page

        Returns:
            Dictionary containing properties list and pagination info
        """
        params = {"pagination.pageLength": page_length}
        return self._make_request(
            "GET", f"/v1/resources/{resource_id}/extended-properties", params=params
        )

    def update_properties(
        self, resource_id: str, properties: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Create or update properties for a resource (organization, sub-org, or component).

        Args:
            resource_id: The resource ID (org ID, sub-org ID, or component ID)
            properties: List of property objects with structure:
                {
                    "name": str,
                    "description": str (optional),
                    "isSecret": bool,
                    "isProtected": bool (optional),
                    "string": str  # or "bool", "int", etc.
                }

        Returns:
            Empty dict on success (200 response)
        """
        return self._make_request(
            "PUT",
            f"/v1/resources/{resource_id}/properties",
            json={"properties": properties},
        )

    def create_property(
        self,
        resource_id: str,
        name: str,
        value: str,
        is_secret: bool = False,
        description: str = "",
        is_protected: bool = False,
    ) -> dict[str, Any]:
        """Create or update a single property on a resource.

        Args:
            resource_id: The resource ID (org ID, sub-org ID, or component ID)
            name: Property name
            value: Property value
            is_secret: Whether this is a secret (masked in UI)
            description: Optional description
            is_protected: Whether property is protected from modification

        Returns:
            Empty dict on success (200 response)
        """
        property_data = {
            "name": name,
            "description": description,
            "isSecret": is_secret,
            "isProtected": is_protected,
            "string": value,
        }
        return self.update_properties(resource_id, [property_data])

    def get_property_by_name(self, resource_id: str, property_name: str) -> dict | None:
        """Get a specific property by name from a resource.

        Args:
            resource_id: The resource ID (org ID, sub-org ID, or component ID)
            property_name: Name of the property to retrieve

        Returns:
            Property data if found, None otherwise
        """
        response = self.list_properties(resource_id)
        properties = response.get("properties", [])

        for prop_item in properties:
            prop = prop_item.get("property", {})
            if prop.get("name") == property_name:
                return prop

        return None

    # Delete/Cleanup Methods
    def delete_component(self, org_id: str, component_id: str) -> None:
        """Delete a CloudBees component using the component UUID directly"""
        try:
            # Components are deleted using the direct resource UUID
            self._make_request("DELETE", f"/v1/resources/{component_id}", json={})
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                # Component not found - consider this success for cleanup purposes
                return
            raise

    def delete_environment(self, org_id: str, env_id: str) -> None:
        """Delete a CloudBees environment"""
        try:
            # Environments are deleted via the resources/endpoints pattern
            self._make_request(
                "DELETE", f"/v1/resources/{org_id}/endpoints/{env_id}", json={}
            )
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                # Environment not found - consider this success for cleanup purposes
                return
            raise

    def delete_application(self, org_id: str, app_id: str) -> None:
        """Delete a CloudBees application (which is a service)"""
        try:
            # Applications are deleted as services - use existing delete_service method
            self.delete_service(org_id, app_id)
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                # Application not found - consider this success for cleanup purposes
                return
            raise


def create_client_from_config(
    config_manager: ConfigManager | None = None, env_name: str | None = None
) -> UnifyAPIClient:
    """Create a UnifyAPIClient from configuration.

    Args:
        config_manager: ConfigManager instance. If None, creates a new one.
        env_name: Environment name to use. If None, uses current environment.

    Returns:
        Configured UnifyAPIClient instance.

    Raises:
        ValueError: If no environment is configured or PAT is not found.
    """
    if config_manager is None:
        config_manager = ConfigManager()

    # Get environment name
    if env_name is None:
        env_name = config_manager.get_current_environment()

    if not env_name:
        raise ValueError(
            "No environment configured. Add one with: mimic env add <name> --url <url>"
        )

    # Get environment URL and PAT
    base_url = config_manager.get_environment_url(env_name)
    if not base_url:
        raise ValueError(f"Environment '{env_name}' not found in configuration")

    api_key = config_manager.get_cloudbees_pat(env_name)
    if not api_key:
        raise ValueError(
            f"No PAT found for environment '{env_name}'. "
            "Re-add the environment with: mimic env add {env_name} --url {base_url}"
        )

    return UnifyAPIClient(base_url=base_url, api_key=api_key)
