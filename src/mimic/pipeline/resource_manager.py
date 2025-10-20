"""
Resource management for CloudBees Unify operations.

Handles creation and configuration of CloudBees components, environments,
applications, and feature flags.
"""

import asyncio
import logging
from typing import Any

from mimic.exceptions import UnifyAPIError
from mimic.pipeline.retry_handler import RetryHandler
from mimic.scenarios import Scenario
from mimic.unify import UnifyAPIClient

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages CloudBees Unify resource operations for scenario execution."""

    def __init__(
        self,
        organization_id: str,
        endpoint_id: str,
        unify_base_url: str,
        unify_pat: str,
    ):
        """
        Initialize the resource manager.

        Args:
            organization_id: CloudBees organization ID
            endpoint_id: CloudBees endpoint ID
            unify_base_url: Base URL for CloudBees Unify API
            unify_pat: Personal access token for CloudBees Unify
        """
        self.organization_id = organization_id
        self.endpoint_id = endpoint_id
        self.unify_base_url = unify_base_url
        self.unify_pat = unify_pat

        self.created_components: dict[str, dict[str, Any]] = {}
        self.created_environments: dict[str, dict[str, Any]] = {}
        self.created_applications: dict[str, dict[str, Any]] = {}
        self.flag_definitions: dict[str, Any] = {}
        self.created_flags: dict[str, dict[str, Any]] = {}

    async def create_components(
        self, repositories: list, created_repositories: dict[str, dict]
    ) -> dict[str, dict[str, Any]]:
        """
        Create CloudBees components for repositories.

        Args:
            repositories: List of RepositoryConfig objects
            created_repositories: Dictionary of created repository data

        Returns:
            Dictionary mapping component names to created component data
        """
        print("\n🧩 Step 2: Creating components...")

        with UnifyAPIClient(
            base_url=self.unify_base_url, api_key=self.unify_pat
        ) as client:
            # Get existing components first
            existing_components_response = client.list_components(self.organization_id)
            existing_components = existing_components_response.get("service", [])

            for repo_config in repositories:
                if not repo_config.create_component:
                    continue

                repo_name = repo_config.repo_name_template
                target_org = repo_config.target_org
                repo_url = f"https://github.com/{target_org}/{repo_name}.git"

                # Check if component already exists
                existing_component = self._find_by_name(existing_components, repo_name)
                if existing_component:
                    print(
                        f"   ⏭️  Component {repo_name} already exists, skipping creation"
                    )
                    self.created_components[repo_name] = existing_component
                else:
                    print(f"   Creating component for {repo_name}...")

                    # Create component with retry logic for indexing delays
                    component_result = await self._create_component_with_retry(
                        client, repo_name, repo_url
                    )

                    self.created_components[repo_name] = component_result.get(
                        "service", {}
                    )
                    print(f"   ✅ Component created: {repo_name}")

        return self.created_components

    async def create_environments(
        self, environments: list
    ) -> dict[str, dict[str, Any]]:
        """
        Create CloudBees environments.

        Args:
            environments: List of EnvironmentConfig objects

        Returns:
            Dictionary mapping environment names to created environment data
        """
        print("\n🌍 Step 4: Creating environments...")

        with UnifyAPIClient(
            base_url=self.unify_base_url, api_key=self.unify_pat
        ) as client:
            # Get existing environments first
            existing_environments_response = client.list_environments(
                self.organization_id
            )
            existing_environments = existing_environments_response.get("endpoints", [])

            for env_config in environments:
                env_name = env_config.name

                # Check if environment already exists
                existing_environment = self._find_by_name(
                    existing_environments, env_name
                )
                if existing_environment:
                    print(
                        f"   ⏭️  Environment {env_name} already exists, skipping creation"
                    )
                    self.created_environments[env_name] = existing_environment
                else:
                    print(f"   Creating environment: {env_name}...")

                    # Build environment properties
                    properties = [
                        {"name": "approvers", "bool": False, "isSecret": False}
                    ]

                    # Add custom environment variables
                    for env_var in env_config.env:
                        properties.append(
                            {
                                "name": env_var.name,
                                "string": env_var.value,
                                "isSecret": False,
                            }
                        )

                    # Note: FM_TOKEN will be added later after applications are created

                    env_result = client.create_basic_environment(
                        org_id=self.organization_id,
                        name=env_name,
                        description=f"Environment for {env_name}",
                        properties=properties,
                    )

                    self.created_environments[env_name] = env_result
                    print(f"   ✅ Environment created: {env_name}")

        return self.created_environments

    async def create_applications(
        self, applications: list
    ) -> dict[str, dict[str, Any]]:
        """
        Create CloudBees applications linking components and environments.

        Args:
            applications: List of ApplicationConfig objects

        Returns:
            Dictionary mapping application names to created application data
        """
        print("\n📱 Step 5: Creating applications...")

        with UnifyAPIClient(
            base_url=self.unify_base_url, api_key=self.unify_pat
        ) as client:
            # Get existing applications first
            existing_applications_response = client.list_applications(
                self.organization_id
            )
            existing_applications = existing_applications_response.get("service", [])

            for app_config in applications:
                app_name = app_config.name
                is_shared = app_config.is_shared

                # Check if application already exists
                existing_application = self._find_by_name(
                    existing_applications, app_name
                )

                if existing_application:
                    if is_shared:
                        # Shared app exists - add new environments to it
                        print(
                            f"   🔗 Application {app_name} already exists (shared), adding environments"
                        )

                        # Get environment IDs to add
                        new_environment_ids = []
                        for env_name in app_config.environments:
                            if env_name in self.created_environments:
                                new_environment_ids.append(
                                    self.created_environments[env_name]["id"]
                                )

                        # Merge with existing environment IDs
                        existing_env_ids = existing_application.get("linkedEnvironmentIds", [])
                        all_environment_ids = list(set(existing_env_ids + new_environment_ids))

                        # Update the application with new environments (don't modify components)
                        update_data = {
                            "service": {
                                "id": existing_application["id"],
                                "name": existing_application["name"],
                                "description": existing_application.get("description", ""),
                                "repositoryUrl": existing_application.get("repositoryUrl", ""),
                                "repositoryHref": existing_application.get("repositoryHref", ""),
                                "endpointId": existing_application.get("endpointId", ""),
                                "defaultBranch": existing_application.get("defaultBranch", "main"),
                                "linkedComponentIds": existing_application.get("linkedComponentIds", []),
                                "linkedEnvironmentIds": all_environment_ids,
                                "components": existing_application.get("components", []),
                                "environments": existing_application.get("environments", []),
                                "organizationId": self.organization_id,
                                "serviceType": "APPLICATION",
                            }
                        }

                        client.update_service(
                            self.organization_id,
                            existing_application["id"],
                            update_data
                        )

                        self.created_applications[app_name] = existing_application
                        print(f"   ✅ Added {len(new_environment_ids)} environment(s) to shared application: {app_name}")
                    else:
                        # Non-shared app exists - skip creation
                        print(
                            f"   ⏭️  Application {app_name} already exists, skipping creation"
                        )
                        self.created_applications[app_name] = existing_application
                else:
                    # Application doesn't exist - create it
                    # Get component IDs
                    component_ids = []
                    for component_name in app_config.components:
                        if component_name in self.created_components:
                            component_ids.append(
                                self.created_components[component_name]["id"]
                            )

                    # Get environment IDs
                    environment_ids = []
                    for env_name in app_config.environments:
                        if env_name in self.created_environments:
                            environment_ids.append(
                                self.created_environments[env_name]["id"]
                            )

                    # Build repository URLs if repository is specified
                    repository_url = ""
                    endpoint_id = ""
                    default_branch = ""

                    if app_config.repository:
                        repository_url = (
                            f"https://github.com/{app_config.repository}.git"
                        )
                        endpoint_id = self.endpoint_id
                        default_branch = "main"

                    shared_indicator = " (shared)" if is_shared else ""
                    print(f"   Creating application: {app_name}{shared_indicator}")
                    print(f"     Components: {len(component_ids)}")
                    print(f"     Environments: {len(environment_ids)}")
                    if repository_url:
                        print(f"     Repository: {repository_url}")

                    app_result = client.create_application(
                        org_id=self.organization_id,
                        name=app_name,
                        description=f"Application for {app_name}",
                        repository_url=repository_url,
                        endpoint_id=endpoint_id,
                        default_branch=default_branch,
                        linked_component_ids=component_ids,
                        linked_environment_ids=environment_ids,
                    )

                    self.created_applications[app_name] = app_result.get("service", {})
                    print(f"   ✅ Application created: {app_name}")

        print("   Waiting for applications to be indexed...")
        await asyncio.sleep(2)

        return self.created_applications

    async def define_flags(self, flags: list) -> dict[str, Any]:
        """
        Store feature flag definitions (need app IDs first).

        Args:
            flags: List of FlagConfig objects

        Returns:
            Dictionary mapping flag names to flag definitions
        """
        print("\n🚩 Step 3: Storing feature flag definitions...")

        for flag_config in flags:
            flag_name = flag_config.name
            flag_type = flag_config.type

            print(f"   Planning flag: {flag_name} ({flag_type})")
            # Store definitions for later creation after applications exist
            self.flag_definitions[flag_name] = flag_config

        return self.flag_definitions

    async def update_environments_with_fm_tokens(
        self,
        environments: list,
        use_legacy_flags: bool,
        env_to_app_mapping: dict[str, str] | None = None
    ) -> None:
        """
        Update environments with FM_TOKEN SDK keys after applications are created.

        Args:
            environments: List of EnvironmentConfig objects
            use_legacy_flags: If True, use org-based API; if False, use app-based API
            env_to_app_mapping: Mapping of environment_name -> application_name (required for new API)
        """
        print("\n🔑 Step 5.5: Adding FM_TOKEN SDK keys to environments...")

        if not use_legacy_flags and not env_to_app_mapping:
            logger.warning(
                "env_to_app_mapping is required when use_legacy_flags=False, skipping FM_TOKEN update"
            )
            return

        with UnifyAPIClient(
            base_url=self.unify_base_url, api_key=self.unify_pat
        ) as client:
            for env_config in environments:
                if env_config.create_fm_token_var:
                    env_name = env_config.name

                    if env_name not in self.created_environments:
                        print(
                            f"   ⚠️  Environment {env_name} not found, skipping FM_TOKEN"
                        )
                        continue

                    env_data = self.created_environments[env_name]
                    env_id = env_data["id"]

                    try:
                        print(f"   Getting SDK key for environment: {env_name}")

                        # Choose API based on flag
                        if use_legacy_flags:
                            # Legacy org-based API
                            # Note: The 'app_id' parameter is actually the organization ID in legacy API
                            sdk_response = client.get_environment_sdk_key(
                                self.organization_id, env_id
                            )
                        else:
                            # New app-based API
                            app_name = env_to_app_mapping.get(env_name) if env_to_app_mapping else None
                            if not app_name:
                                print(
                                    f"   ⚠️  No application mapping found for environment {env_name}, skipping"
                                )
                                continue

                            if app_name not in self.created_applications:
                                print(
                                    f"   ⚠️  Application {app_name} not found for environment {env_name}, skipping"
                                )
                                continue

                            app_id = self.created_applications[app_name]["id"]
                            sdk_response = client.get_application_environment_sdk_key(
                                app_id, env_id
                            )

                        sdk_key = sdk_response.get("sdkKey")

                        if not sdk_key:
                            print(
                                f"   ⚠️  No SDK key returned for environment {env_name}"
                            )
                            continue

                        # Fetch full environment data (creation response might be incomplete)
                        if len(env_data.keys()) == 1:  # Only has 'id' key
                            print(f"   Fetching full environment data for: {env_name}")
                            env_response = client.get_environment(
                                self.organization_id, env_id
                            )
                            # Extract environment data from 'endpoint' wrapper if present
                            env_data = env_response.get("endpoint", env_response)
                            self.created_environments[env_name] = (
                                env_data  # Update cached data
                            )

                        # Get current environment properties and add FM_TOKEN
                        current_properties = env_data.get("properties", [])

                        # Check if FM_TOKEN already exists
                        fm_token_exists = any(
                            prop.get("name") == "FM_TOKEN"
                            for prop in current_properties
                        )

                        if not fm_token_exists:
                            # Add FM_TOKEN property
                            current_properties.append(
                                {
                                    "name": "FM_TOKEN",
                                    "string": sdk_key,
                                    "isSecret": False,
                                }
                            )

                            # Try to update environment with retry logic for concurrent modifications
                            await self._update_environment_with_retry(
                                client, env_name, env_id, env_data, current_properties
                            )
                            print(f"   ✅ Added FM_TOKEN to environment: {env_name}")
                        else:
                            print(
                                f"   ⏭️  FM_TOKEN already exists in environment: {env_name}"
                            )

                    except UnifyAPIError as e:
                        logger.error(
                            f"Failed to add FM_TOKEN to environment {env_name}: {e}"
                        )
                        # Don't raise - this is not critical for the pipeline
                    except Exception as e:
                        logger.error(
                            f"Unexpected error adding FM_TOKEN to environment {env_name}: {e}"
                        )
                        # Don't raise - this is not critical for the pipeline

    async def configure_flags_in_environments(
        self, resolved_scenario: Scenario
    ) -> None:
        """
        Create and configure flags across environments.

        Args:
            resolved_scenario: Scenario with resolved template variables
        """
        print("\n⚙️  Step 6: Creating and configuring flags...")

        with UnifyAPIClient(
            base_url=self.unify_base_url, api_key=self.unify_pat
        ) as client:
            # Create flags for each application
            for app_name, app_data in self.created_applications.items():
                app_id = app_data["id"]
                print(f"   Creating flags for application: {app_name}")

                # Get existing flags for this application
                existing_flags_response = client.list_flags(app_id)
                existing_flags = existing_flags_response.get("flags", [])

                for flag_name, _flag_config in self.flag_definitions.items():
                    # Check if flag already exists
                    existing_flag = self._find_by_name(existing_flags, flag_name)
                    if existing_flag:
                        print(
                            f"     ⏭️  Flag {flag_name} already exists, using existing"
                        )
                        flag_id = existing_flag["id"]
                        # Store the existing flag data
                        self.created_flags[flag_name] = existing_flag
                    else:
                        print(f"     Creating flag: {flag_name}")

                        # Create the flag and get its ID
                        flag_result = client.create_boolean_flag(
                            app_id=app_id,
                            name=flag_name,
                            description=f"Flag {flag_name} for {app_name}",
                        )
                        flag_id = flag_result.get("flag", {}).get("id")
                        # Store the created flag data
                        created_flag_data = flag_result.get("flag", {})
                        self.created_flags[flag_name] = created_flag_data

                    # Configure flag in each environment mentioned in the scenario
                    # (Always do this to refresh configuration, even if flag existed)
                    for env_config in resolved_scenario.environments:
                        if flag_name in env_config.flags:
                            env_name = env_config.name
                            if env_name in self.created_environments:
                                env_id = self.created_environments[env_name]["id"]
                                print(f"       Enabling in environment: {env_name}")

                                # Enable flag in this environment (set to false initially)
                                client.enable_flag_in_environment(
                                    app_id=app_id,
                                    flag_id=flag_id,
                                    env_id=env_id,
                                    enabled=False,
                                )

        print("   Flags configured across environments")

    async def _create_component_with_retry(
        self, client: UnifyAPIClient, repo_name: str, repo_url: str
    ) -> dict:
        """Create a component with retry logic for GitHub indexing delays."""

        async def create_operation() -> dict:
            return client.create_component(
                org_id=self.organization_id,
                name=repo_name,
                repository_url=repo_url,
                endpoint_id=self.endpoint_id,
                description=f"Component for {repo_name}",
            )

        return await RetryHandler.with_component_creation_retry(
            create_operation, repo_name
        )

    async def _update_environment_with_retry(
        self,
        client: UnifyAPIClient,
        env_name: str,
        env_id: str,
        env_data: dict,
        properties: list,
    ) -> None:
        """Update environment with retry logic for concurrent modification errors."""

        async def fetch_fresh_data() -> dict:
            env_response = client.get_environment(self.organization_id, env_id)
            return env_response.get("endpoint", env_response)

        async def update_operation(fresh_env_data: dict | None) -> None:
            data_to_use = fresh_env_data if fresh_env_data is not None else env_data

            # Build update data with current version
            update_data = {
                "resourceId": data_to_use.get("resourceId"),
                "contributionId": data_to_use.get("contributionId"),
                "contributionType": data_to_use.get("contributionType"),
                "contributionTargets": data_to_use.get("contributionTargets", []),
                "name": data_to_use.get("name", env_name),
                "description": data_to_use.get(
                    "description", f"Environment for {env_name}"
                ),
                "properties": properties,
                "version": data_to_use.get("version", 1),
            }

            # Add parentId if it exists
            if data_to_use.get("parentId"):
                update_data["parentId"] = data_to_use["parentId"]

            client.update_environment(self.organization_id, env_id, update_data)

        await RetryHandler.with_environment_update_retry(
            update_operation, fetch_fresh_data, env_name
        )

    @staticmethod
    def _find_by_name(items: list[dict], name: str, key: str = "name") -> dict | None:
        """Find an item in a list by its name field."""
        for item in items:
            if item.get(key) == name:
                return item
        return None
