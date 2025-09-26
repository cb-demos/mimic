"""
CloudBees Unify Creation Pipeline
Orchestrates the setup of a complete scenario including repos, components, environments, flags, and applications.
"""

import asyncio
import logging
from typing import Any

from .config import settings
from .database import get_database
from .exceptions import GitHubError, PipelineError, UnifyAPIError
from .gh import GitHubClient
from .progress_tracker import ProgressStep, get_progress_tracker
from .scenarios import Scenario
from .unify import UnifyAPIClient

logger = logging.getLogger(__name__)


class CreationPipeline:
    """Orchestrates the creation of a complete CloudBees scenario."""

    def __init__(
        self,
        organization_id: str,
        endpoint_id: str,
        unify_pat: str,
        session_id: str,
        email: str,
        github_pat: str,
        invitee_username: str | None = None,
    ):
        self.organization_id = organization_id
        self.endpoint_id = endpoint_id
        self.unify_pat = unify_pat
        self.session_id = session_id
        self.email = email
        self.github_pat = github_pat
        self.invitee_username = invitee_username
        self.created_components = {}  # name -> component_data
        self.created_environments = {}  # name -> env_data
        self.created_flags = {}  # name -> flag_data
        self.created_applications = {}  # name -> app_data
        self.created_repositories = {}  # name -> repo_data
        self.current_step = "initialization"
        self.progress_tracker = None

        # Initialize database, GitHub client, and progress tracker
        self.db = get_database()
        self.github = GitHubClient(github_pat)
        self.progress_tracker = get_progress_tracker(session_id)

    async def execute_scenario(
        self, scenario: Scenario, parameters: dict[str, str]
    ) -> dict[str, Any]:
        """
        Execute a complete scenario setup.

        Args:
            scenario: The Scenario object to execute
            parameters: Values for template variables (project_name, target_org, etc.)

        Returns:
            Summary of what was created
        """
        print(f"🚀 Starting scenario: {scenario.name}")
        print(f"📝 Description: {scenario.description}")
        print("=" * 60)

        # Start progress tracking
        if self.progress_tracker:
            await self.progress_tracker.start_step(
                ProgressStep.INITIALIZATION,
                f"Starting scenario: {scenario.name}"
            )

        # Validate and resolve template variables
        processed_parameters = scenario.validate_input(parameters)
        resolved_scenario = scenario.resolve_template_variables(processed_parameters)

        try:
            # Complete initialization
            if self.progress_tracker:
                await self.progress_tracker.complete_step(
                    ProgressStep.INITIALIZATION,
                    "Scenario validation complete"
                )

            # Step 1: Create repositories (with content replacements)
            self.current_step = "repository_creation"
            if self.progress_tracker:
                await self.progress_tracker.start_step(
                    ProgressStep.REPOSITORY_CREATION,
                    "Creating GitHub repositories from templates"
                )
            await self._create_repositories(
                resolved_scenario.repositories, processed_parameters
            )
            if self.progress_tracker:
                await self.progress_tracker.complete_step(
                    ProgressStep.REPOSITORY_CREATION,
                    f"Created {len(self.created_repositories)} repositories"
                )

            # Step 2: Create components for repos that need them
            self.current_step = "component_creation"
            component_repos = [r for r in resolved_scenario.repositories if r.create_component]
            if component_repos:
                if self.progress_tracker:
                    await self.progress_tracker.start_step(
                        ProgressStep.COMPONENT_CREATION,
                        f"Creating {len(component_repos)} CloudBees components"
                    )
                await self._create_components(resolved_scenario.repositories)
                if self.progress_tracker:
                    await self.progress_tracker.complete_step(
                        ProgressStep.COMPONENT_CREATION,
                        f"Created {len(self.created_components)} components"
                    )

            # Step 3: Create feature flags (store for later - need app IDs first)
            self.current_step = "flag_creation"
            if resolved_scenario.flags:
                if self.progress_tracker:
                    await self.progress_tracker.start_step(
                        ProgressStep.FLAG_CREATION,
                        f"Planning {len(resolved_scenario.flags)} feature flags"
                    )
                await self._create_flags(resolved_scenario.flags)
                if self.progress_tracker:
                    await self.progress_tracker.complete_step(
                        ProgressStep.FLAG_CREATION,
                        f"Defined {len(self.created_flags)} feature flags"
                    )

            # Step 4: Create environments
            self.current_step = "environment_creation"
            if self.progress_tracker:
                await self.progress_tracker.start_step(
                    ProgressStep.ENVIRONMENT_CREATION,
                    f"Creating {len(resolved_scenario.environments)} environments"
                )
            await self._create_environments(resolved_scenario.environments)
            if self.progress_tracker:
                await self.progress_tracker.complete_step(
                    ProgressStep.ENVIRONMENT_CREATION,
                    f"Created {len(self.created_environments)} environments"
                )

            # Step 5: Create applications (linking components and environments)
            self.current_step = "application_creation"
            if self.progress_tracker:
                await self.progress_tracker.start_step(
                    ProgressStep.APPLICATION_CREATION,
                    f"Creating {len(resolved_scenario.applications)} applications"
                )
            await self._create_applications(resolved_scenario.applications)
            if self.progress_tracker:
                await self.progress_tracker.complete_step(
                    ProgressStep.APPLICATION_CREATION,
                    f"Created {len(self.created_applications)} applications"
                )

            # Step 5.5: Update environments with FM_TOKEN SDK keys
            self.current_step = "environment_fm_token_update"
            fm_envs = [e for e in resolved_scenario.environments if e.create_fm_token_var]
            if fm_envs:
                if self.progress_tracker:
                    await self.progress_tracker.start_step(
                        ProgressStep.ENVIRONMENT_FM_TOKEN_UPDATE,
                        f"Adding SDK keys to {len(fm_envs)} environments"
                    )
                await self._update_environments_with_fm_tokens(
                    resolved_scenario.environments
                )
                if self.progress_tracker:
                    await self.progress_tracker.complete_step(
                        ProgressStep.ENVIRONMENT_FM_TOKEN_UPDATE,
                        "SDK keys configured"
                    )

            # Step 6: Configure flags across environments (set to off initially)
            self.current_step = "flag_configuration"
            if resolved_scenario.flags:
                if self.progress_tracker:
                    await self.progress_tracker.start_step(
                        ProgressStep.FLAG_CONFIGURATION,
                        "Configuring feature flags across environments"
                    )
                await self._configure_flags_in_environments(resolved_scenario)
                if self.progress_tracker:
                    await self.progress_tracker.complete_step(
                        ProgressStep.FLAG_CONFIGURATION,
                        "Feature flags configured across all environments"
                    )

            self.current_step = "completed"
            summary = self._generate_summary()

            # Complete scenario
            if self.progress_tracker:
                await self.progress_tracker.complete_scenario(
                    "🎉 Scenario executed successfully!",
                    summary
                )

            return summary

        except (GitHubError, UnifyAPIError) as e:
            logger.error(f"External API error during {self.current_step}: {e}")
            if self.progress_tracker:
                await self.progress_tracker.fail_scenario(
                    f"Pipeline failed at {self.current_step}: {str(e)}",
                    {"scenario": scenario.name, "error_type": type(e).__name__, "step": self.current_step}
                )
            raise PipelineError(
                f"Pipeline failed at {self.current_step}: {str(e)}",
                self.current_step,
                {"scenario": scenario.name, "error_type": type(e).__name__},
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during {self.current_step}: {e}")
            if self.progress_tracker:
                await self.progress_tracker.fail_scenario(
                    f"Unexpected error at {self.current_step}: {str(e)}",
                    {"scenario": scenario.name, "error_type": type(e).__name__, "step": self.current_step}
                )
            raise PipelineError(
                f"Unexpected error at {self.current_step}: {str(e)}",
                self.current_step,
                {"scenario": scenario.name, "error_type": type(e).__name__},
            ) from e

    async def _create_repositories(self, repositories, parameters):
        """Step 1: Create GitHub repositories from templates with content replacements."""
        print("\n📁 Step 1: Creating repositories...")

        for repo_config in repositories:
            source_parts = repo_config.source.split("/")
            if len(source_parts) != 2:
                raise ValueError(f"Invalid source format: {repo_config.source}")

            template_org, template_repo = source_parts
            repo_name = repo_config.repo_name_template
            target_org = repo_config.target_org

            # Check if repository already exists
            if await self.github.repo_exists(target_org, repo_name):
                print(
                    f"   ⏭️  Repository {target_org}/{repo_name} already exists, skipping creation"
                )
                # Still track existing repo for summary
                self.created_repositories[repo_name] = {
                    "name": repo_name,
                    "full_name": f"{target_org}/{repo_name}",
                    "html_url": f"https://github.com/{target_org}/{repo_name}",
                    "existed": True,
                }
            else:
                print(
                    f"   Creating {target_org}/{repo_name} from {repo_config.source}..."
                )

                # Create repo from template
                new_repo = await self.github.create_repo_from_template(
                    template_owner=template_org,
                    template_repo=template_repo,
                    owner=target_org,
                    name=repo_name,
                    description=f"Created from {repo_config.source}",
                )

                print(f"   ✅ Repository created: {new_repo['html_url']}")

                # Track created repo for summary
                self.created_repositories[repo_name] = {
                    "name": new_repo.get("name", repo_name),
                    "full_name": new_repo.get("full_name", f"{target_org}/{repo_name}"),
                    "html_url": new_repo.get(
                        "html_url", f"https://github.com/{target_org}/{repo_name}"
                    ),
                    "existed": False,
                }

                # Wait for repo to be ready
                await asyncio.sleep(3)

            # Register repository in the session for cleanup tracking (all repos, new or existing)
            await self._register_resource_safe(
                resource_id=f"{target_org}/{repo_name}",  # Use GitHub full_name format
                resource_type="github_repo",
                resource_name=repo_name,
                platform="github",
                resource_ref=f"{target_org}/{repo_name}",
                metadata={"target_org": target_org, "repo_name": repo_name},
            )

            # Apply content replacements to specified files
            for file_path in repo_config.files_to_modify:
                await self._apply_file_replacements(
                    target_org, repo_name, file_path, repo_config.replacements
                )

            # Apply conditional file operations
            await self._apply_conditional_file_operations(
                target_org,
                repo_name,
                repo_config.conditional_file_operations,
                parameters,
            )

            # Invite collaborator if specified
            if self.invitee_username:
                await self._invite_collaborator(
                    target_org, repo_name, self.invitee_username
                )

        # Smart delay based on whether we need component creation
        needs_component_creation = any(repo.create_component for repo in repositories)
        if needs_component_creation:
            print(f"   Waiting {settings.REPO_TO_COMPONENT_DELAY}s for GitHub to index repositories before creating components...")
            await asyncio.sleep(settings.REPO_TO_COMPONENT_DELAY)
        else:
            print(f"   Waiting {settings.REPO_BASIC_DELAY}s for repositories to be ready...")
            await asyncio.sleep(settings.REPO_BASIC_DELAY)

    async def _create_components(self, repositories):
        """Step 2: Create CloudBees components for repos that need them."""
        print("\n🧩 Step 2: Creating components...")

        with UnifyAPIClient(api_key=self.unify_pat) as client:
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

                # Register component in the session for cleanup tracking (all components, new or existing)
                component_data = self.created_components[repo_name]
                await self._register_resource_safe(
                    resource_id=component_data["id"],  # Use actual CloudBees UUID
                    resource_type="cloudbees_component",
                    resource_name=repo_name,
                    platform="cloudbees",
                    resource_ref=component_data.get("id", ""),
                    metadata={"org_id": self.organization_id, "repo_name": repo_name},
                )

        # No additional delay needed - timing handled in repository step

    async def _create_flags(self, flags):
        """Step 3: Store feature flag definitions (need app IDs first)."""
        print("\n🚩 Step 3: Storing feature flag definitions...")

        for flag_config in flags:
            flag_name = flag_config.name
            flag_type = flag_config.type

            print(f"   Planning flag: {flag_name} ({flag_type})")
            # Store for later creation after applications exist
            self.created_flags[flag_name] = flag_config

    async def _create_environments(self, environments):
        """Step 4: Create CloudBees environments."""
        print("\n🌍 Step 4: Creating environments...")

        with UnifyAPIClient(api_key=self.unify_pat) as client:
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

                # Register environment in the session for cleanup tracking (all environments, new or existing)
                env_data = self.created_environments[env_name]
                await self._register_resource_safe(
                    resource_id=env_data["id"],  # Use actual CloudBees environment UUID
                    resource_type="cloudbees_environment",
                    resource_name=env_name,
                    platform="cloudbees",
                    resource_ref=env_data.get("id", ""),
                    metadata={"org_id": self.organization_id, "env_name": env_name},
                )

    async def _update_environments_with_fm_tokens(self, environments):
        """Step 5.5: Update environments with FM_TOKEN SDK keys after applications are created."""
        print("\n🔑 Step 5.5: Adding FM_TOKEN SDK keys to environments...")

        with UnifyAPIClient(api_key=self.unify_pat) as client:
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
                        # Note: The 'app_id' parameter in this API is actually the organization ID
                        sdk_response = client.get_environment_sdk_key(
                            self.organization_id, env_id
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

    async def _configure_flags_in_environments(self, resolved_scenario):
        """Step 6: Create and configure flags across environments."""
        print("\n⚙️  Step 6: Creating and configuring flags...")

        with UnifyAPIClient(api_key=self.unify_pat) as client:
            # Create flags for each application
            for app_name, app_data in self.created_applications.items():
                app_id = app_data["id"]
                print(f"   Creating flags for application: {app_name}")

                # Get existing flags for this application
                existing_flags_response = client.list_flags(app_id)
                existing_flags = existing_flags_response.get("flags", [])

                for flag_name, _flag_config in self.created_flags.items():
                    # Check if flag already exists
                    existing_flag = self._find_by_name(existing_flags, flag_name)
                    if existing_flag:
                        print(
                            f"     ⏭️  Flag {flag_name} already exists, using existing"
                        )
                        flag_id = existing_flag["id"]
                    else:
                        print(f"     Creating flag: {flag_name}")

                        # Create the flag and get its ID
                        flag_result = client.create_boolean_flag(
                            app_id=app_id,
                            name=flag_name,
                            description=f"Flag {flag_name} for {app_name}",
                        )
                        flag_id = flag_result.get("flag", {}).get("id")

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
        for attempt in range(settings.MAX_RETRY_ATTEMPTS):
            try:
                return client.create_component(
                    org_id=self.organization_id,
                    name=repo_name,
                    repository_url=repo_url,
                    endpoint_id=self.endpoint_id,
                    description=f"Component for {repo_name}",
                )
            except UnifyAPIError as e:
                is_last_attempt = attempt == settings.MAX_RETRY_ATTEMPTS - 1

                # Check if error is related to repository not being indexed
                error_msg = str(e).lower()
                is_indexing_error = any(keyword in error_msg for keyword in [
                    "repository not found", "repo not found", "not indexed",
                    "repository does not exist", "invalid repository"
                ])

                if is_indexing_error and not is_last_attempt:
                    wait_time = settings.RETRY_BACKOFF_BASE * (2 ** attempt)
                    print(f"     Repository not indexed yet (attempt {attempt + 1}/{settings.MAX_RETRY_ATTEMPTS}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    # Re-raise if not an indexing error or if this is the last attempt
                    raise

        # Should never reach here, but just in case
        raise UnifyAPIError(f"Failed to create component {repo_name} after {settings.MAX_RETRY_ATTEMPTS} attempts")

    async def _update_environment_with_retry(
        self, client: UnifyAPIClient, env_name: str, env_id: str, env_data: dict, properties: list
    ) -> None:
        """Update environment with retry logic for concurrent modification errors."""
        for attempt in range(settings.MAX_RETRY_ATTEMPTS):
            try:
                # If this is a retry, fetch fresh environment data
                if attempt > 0:
                    print(f"     Retrying environment update (attempt {attempt + 1}/{settings.MAX_RETRY_ATTEMPTS})...")
                    env_response = client.get_environment(self.organization_id, env_id)
                    env_data = env_response.get("endpoint", env_response)

                # Build update data with current version
                update_data = {
                    "resourceId": env_data.get("resourceId"),
                    "contributionId": env_data.get("contributionId"),
                    "contributionType": env_data.get("contributionType"),
                    "contributionTargets": env_data.get("contributionTargets", []),
                    "name": env_data.get("name", env_name),
                    "description": env_data.get("description", f"Environment for {env_name}"),
                    "properties": properties,
                    "version": env_data.get("version", 1),
                }

                # Add parentId if it exists
                if env_data.get("parentId"):
                    update_data["parentId"] = env_data["parentId"]

                client.update_environment(self.organization_id, env_id, update_data)
                return  # Success

            except UnifyAPIError as e:
                is_last_attempt = attempt == settings.MAX_RETRY_ATTEMPTS - 1
                error_msg = str(e).lower()
                is_concurrent_error = "concurrent modification" in error_msg

                if is_concurrent_error and not is_last_attempt:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"     Concurrent modification detected, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    # Re-raise if not a concurrent error or if this is the last attempt
                    raise

        # Should never reach here
        raise UnifyAPIError(f"Failed to update environment {env_name} after {settings.MAX_RETRY_ATTEMPTS} attempts")

    async def _create_applications(self, applications):
        """Step 5: Create CloudBees applications linking components and environments."""
        print("\n📱 Step 5: Creating applications...")

        with UnifyAPIClient(api_key=self.unify_pat) as client:
            # Get existing applications first
            existing_applications_response = client.list_applications(
                self.organization_id
            )
            existing_applications = existing_applications_response.get("service", [])

            for app_config in applications:
                app_name = app_config.name

                # Check if application already exists
                existing_application = self._find_by_name(
                    existing_applications, app_name
                )
                if existing_application:
                    print(
                        f"   ⏭️  Application {app_name} already exists, skipping creation"
                    )
                    self.created_applications[app_name] = existing_application
                else:
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
                    if app_config.repository:
                        repository_url = (
                            f"https://github.com/{app_config.repository}.git"
                        )

                    print(f"   Creating application: {app_name}")
                    print(f"     Components: {len(component_ids)}")
                    print(f"     Environments: {len(environment_ids)}")
                    if repository_url:
                        print(f"     Repository: {repository_url}")

                    app_result = client.create_application(
                        org_id=self.organization_id,
                        name=app_name,
                        description=f"Application for {app_name}",
                        repository_url=repository_url,
                        endpoint_id=self.endpoint_id,
                        default_branch="main",
                        linked_component_ids=component_ids,
                        linked_environment_ids=environment_ids,
                    )

                    self.created_applications[app_name] = app_result.get("service", {})
                    print(f"   ✅ Application created: {app_name}")

                # Register application in the session for cleanup tracking (all applications, new or existing)
                app_data = self.created_applications[app_name]
                await self._register_resource_safe(
                    resource_id=app_data["id"],  # Use actual CloudBees application UUID
                    resource_type="cloudbees_application",
                    resource_name=app_name,
                    platform="cloudbees",
                    resource_ref=app_data.get("id", ""),
                    metadata={"org_id": self.organization_id, "app_name": app_name},
                )

        print("   Waiting for applications to be indexed...")
        await asyncio.sleep(2)

    async def _apply_file_replacements(
        self, owner: str, repo: str, file_path: str, replacements: dict[str, str]
    ):
        """Apply content replacements to a file in the repository."""
        print(f"     Applying replacements to {file_path}...")

        # Get file content from GitHub
        file_data = await self.github.get_file_in_repo(owner, repo, file_path)
        if not file_data:
            print(f"     Warning: File {file_path} not found")
            return

        original_content = file_data.get("decoded_content", "")

        # Apply replacements
        modified_content = original_content
        for find_str, replace_str in replacements.items():
            modified_content = modified_content.replace(find_str, replace_str)

        # Only update if content actually changed
        if modified_content != original_content:
            await self.github.replace_file(
                owner=owner,
                repo=repo,
                path=file_path,
                content=modified_content,
                message=f"Apply scenario replacements to {file_path}",
                sha=file_data["sha"],
            )
            print(f"     ✅ Updated {file_path}")
        else:
            print(f"     No changes needed for {file_path}")

    async def _apply_conditional_file_operations(
        self,
        owner: str,
        repo: str,
        conditional_operations: list,
        parameters: dict[str, Any],
    ):
        """Apply conditional file operations (move/copy files based on parameters)."""
        for operation in conditional_operations:
            condition_param = operation.condition_parameter
            condition_value = parameters.get(condition_param, False)

            # Determine which operations to perform
            operations_to_apply = (
                operation.when_true if condition_value else operation.when_false
            )

            if not operations_to_apply:
                continue

            print(
                f"     Applying conditional file operations (condition: {condition_param}={condition_value})..."
            )

            for source_path, destination_path in operations_to_apply.items():
                await self._move_file_in_repo(
                    owner, repo, source_path, destination_path
                )

    async def _move_file_in_repo(
        self, owner: str, repo: str, source_path: str, destination_path: str
    ):
        """Move a file from source_path to destination_path in the repository."""
        print(f"       Moving {source_path} -> {destination_path}...")

        # Get source file content
        source_file_data = await self.github.get_file_in_repo(owner, repo, source_path)
        if not source_file_data:
            print(f"       Warning: Source file {source_path} not found")
            return

        # Create destination file
        await self.github.create_file(
            owner=owner,
            repo=repo,
            path=destination_path,
            content=source_file_data["decoded_content"],
            message=f"Move {source_path} to {destination_path}",
        )

        # Delete source file
        await self.github.delete_file(
            owner=owner,
            repo=repo,
            path=source_path,
            message=f"Remove {source_path} after move to {destination_path}",
            sha=source_file_data["sha"],
        )

        print(f"       ✅ Moved {source_path} to {destination_path}")

    def _find_by_name(
        self, items: list[dict], name: str, key: str = "name"
    ) -> dict | None:
        """Find an item in a list by its name field."""
        for item in items:
            if item.get(key) == name:
                return item
        return None

    async def _invite_collaborator(self, owner: str, repo: str, username: str):
        """Invite a GitHub user as collaborator to a repository with idempotency."""
        print(f"     Checking collaboration status for {username}...")

        # Check if user is already a collaborator
        is_collaborator = await self.github.check_user_collaboration(
            owner, repo, username
        )
        if is_collaborator:
            print(f"     ⏭️  {username} is already a collaborator on {owner}/{repo}")
        else:
            print(f"     Inviting {username} as admin collaborator...")
            success = await self.github.invite_collaborator(
                owner, repo, username, "admin"
            )
            if success:
                print(f"     ✅ {username} invited as collaborator to {owner}/{repo}")
            else:
                print(f"     ❌ Failed to invite {username} to {owner}/{repo}")

    async def _register_resource_safe(
        self,
        resource_id: str,
        resource_type: str,
        resource_name: str,
        platform: str,
        resource_ref: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Safely register a resource, retrying on failure."""
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                await self.db.register_resource(
                    resource_id=resource_id,
                    session_id=self.session_id,
                    resource_type=resource_type,
                    resource_name=resource_name,
                    platform=platform,
                    resource_ref=resource_ref,
                    metadata=metadata,
                )
                logger.info(
                    f"Registered {resource_type} '{resource_name}' to session {self.session_id}"
                )
                return  # Success
            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed to register "
                    f"{resource_type} '{resource_name}': {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"All {max_retries} attempts failed to register "
                        f"{resource_type} '{resource_name}'. This resource may be orphaned."
                    )
                    # Continue execution - resource registration failure shouldn't break the pipeline

    def _generate_summary(self) -> dict[str, Any]:
        """Generate a summary of what was created."""
        return {
            "components": list(self.created_components.keys()),
            "environments": list(self.created_environments.keys()),
            "flags": list(self.created_flags.keys()),
            "applications": list(self.created_applications.keys()),
            "repositories": list(self.created_repositories.values()),
            "success": True,
        }
