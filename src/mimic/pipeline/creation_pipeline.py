"""
CloudBees Unify Creation Pipeline
Orchestrates the setup of a complete scenario including repos, components, environments, flags, and applications.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from mimic.exceptions import GitHubError, PipelineError, UnifyAPIError
from mimic.gh import GitHubClient
from mimic.models import (
    CloudBeesApplication,
    CloudBeesComponent,
    CloudBeesEnvironment,
    CloudBeesFlag,
    EnvironmentVariable,
    GitHubRepository,
    Instance,
)
from mimic.pipeline.repository_manager import RepositoryManager
from mimic.pipeline.resource_manager import ResourceManager
from mimic.scenarios import Scenario

logger = logging.getLogger(__name__)
console = Console()


class CreationPipeline:
    """Orchestrates the creation of a complete CloudBees scenario."""

    def __init__(
        self,
        organization_id: str,
        endpoint_id: str,
        unify_pat: str,
        unify_base_url: str,
        session_id: str,
        github_pat: str,
        invitee_username: str | None = None,
        env_properties: dict[str, str] | None = None,
        # New parameters for Instance creation
        scenario_id: str | None = None,
        instance_name: str | None = None,
        tenant: str | None = None,
        expires_at: datetime | None = None,
        use_legacy_flags: bool = False,
        # Optional callback for progress events (used by web UI)
        event_callback: Any | None = None,
        # Optional callback to persist partial state after each step
        # (e.g. InstanceRepository().save) so failed runs can be cleaned up.
        on_checkpoint: Callable[[Instance], None] | None = None,
    ):
        self.on_checkpoint = on_checkpoint
        self.organization_id = organization_id
        self.endpoint_id = endpoint_id
        self.unify_pat = unify_pat
        self.unify_base_url = unify_base_url
        self.session_id = session_id
        self.github_pat = github_pat
        self.invitee_username = invitee_username
        self.env_properties = env_properties or {}
        self.current_step = "initialization"
        self.use_legacy_flags = use_legacy_flags
        self.event_callback = event_callback

        # Instance metadata
        self.scenario_id = scenario_id
        self.instance_name = instance_name or session_id
        self.tenant = tenant
        self.expires_at = expires_at
        self.created_at = datetime.now()

        # Initialize GitHub client
        github_client = GitHubClient(github_pat)

        # Initialize managers
        self.repo_manager = RepositoryManager(
            github_client,
            invitee_username,
            organization_id,
            unify_base_url,
            unify_pat,
            event_callback,
        )
        self.resource_manager = ResourceManager(
            organization_id, endpoint_id, unify_base_url, unify_pat
        )

    # Properties to expose manager state for backward compatibility
    @property
    def created_repositories(self) -> dict[str, dict[str, Any]]:
        """Access created repositories from the repository manager."""
        return self.repo_manager.created_repositories

    @property
    def created_components(self) -> dict[str, dict[str, Any]]:
        """Access created components from the resource manager."""
        return self.resource_manager.created_components

    @property
    def created_environments(self) -> dict[str, dict[str, Any]]:
        """Access created environments from the resource manager."""
        return self.resource_manager.created_environments

    @property
    def created_applications(self) -> dict[str, dict[str, Any]]:
        """Access created applications from the resource manager."""
        return self.resource_manager.created_applications

    @property
    def created_flags(self) -> dict[str, dict[str, Any]]:
        """Access created flags from the resource manager."""
        return self.resource_manager.created_flags

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event if callback is configured.

        Args:
            event_type: Type of event (e.g., "task_start", "task_progress")
            data: Event data dictionary
        """
        if self.event_callback:
            try:
                await self.event_callback({"event": event_type, "data": data})
            except Exception as e:
                logger.error(f"Error emitting event {event_type}: {e}")

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
        console.print(f"\n[bold cyan]🚀 Starting scenario:[/bold cyan] {scenario.name}")
        console.print(f"[dim]📝 {scenario.summary}[/dim]")
        console.print()

        # Validate and resolve template variables
        processed_parameters = scenario.validate_input(parameters)

        # Inject runtime values that should be available in templates
        runtime_values = {
            **processed_parameters,
            "organization_id": self.organization_id,
        }

        resolved_scenario = scenario.resolve_template_variables(
            runtime_values, self.env_properties
        )

        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            try:
                # Calculate total steps
                total_steps = 2  # repos + apps
                if any(r.create_component for r in resolved_scenario.repositories):
                    total_steps += 1
                if resolved_scenario.flags:
                    total_steps += 2  # flag creation + configuration
                if resolved_scenario.environments:
                    total_steps += 1
                    if any(
                        e.create_fm_token_var for e in resolved_scenario.environments
                    ):
                        total_steps += 1

                main_task = progress.add_task(
                    "[cyan]Executing scenario...", total=total_steps
                )
                completed_steps = 0

                # Record the run before creating anything so a crash mid-step
                # still leaves a cleanup-able entry in state.
                self._checkpoint(resolved_scenario, "in_progress")

                # Step 1: Create repositories
                self.current_step = "repository_creation"
                await self._emit_event(
                    "task_start",
                    {
                        "task_id": "repositories",
                        "description": "Creating GitHub repositories",
                        "total": len(resolved_scenario.repositories),
                    },
                )
                progress.update(
                    main_task, description="[cyan]Creating GitHub repositories..."
                )
                created_repositories = await self.repo_manager.create_repositories(
                    resolved_scenario.repositories, processed_parameters
                )
                completed_steps += 1
                self._checkpoint(resolved_scenario, "in_progress")
                progress.update(
                    main_task,
                    completed=completed_steps,
                    description="[green]✓[/green] "
                    + self._outcome_message(
                        len(created_repositories),
                        sum(
                            1 for r in created_repositories.values() if r.get("existed")
                        ),
                        "repository",
                        "repositories",
                    ),
                )
                await self._emit_event(
                    "task_complete",
                    {
                        "task_id": "repositories",
                        "success": True,
                        **self._outcome_event(
                            len(created_repositories),
                            sum(
                                1
                                for r in created_repositories.values()
                                if r.get("existed")
                            ),
                            "repository",
                            "repositories",
                        ),
                    },
                )

                # Step 2: Create components
                self.current_step = "component_creation"
                component_repos = [
                    r for r in resolved_scenario.repositories if r.create_component
                ]
                if component_repos:
                    await self._emit_event(
                        "task_start",
                        {
                            "task_id": "components",
                            "description": "Creating CloudBees components",
                            "total": len(component_repos),
                        },
                    )
                    progress.update(
                        main_task, description="[cyan]Creating CloudBees components..."
                    )
                    created_components = await self.resource_manager.create_components(
                        resolved_scenario.repositories, created_repositories
                    )
                    completed_steps += 1
                    self._checkpoint(resolved_scenario, "in_progress")
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description="[green]✓[/green] "
                        + self._outcome_message(
                            len(created_components),
                            len(self.resource_manager.preexisting_components),
                            "component",
                            "components",
                        ),
                    )
                    await self._emit_event(
                        "task_complete",
                        {
                            "task_id": "components",
                            "success": True,
                            **self._outcome_event(
                                len(created_components),
                                len(self.resource_manager.preexisting_components),
                                "component",
                                "components",
                            ),
                        },
                    )

                # Step 3: Define feature flags
                self.current_step = "flag_creation"
                if resolved_scenario.flags:
                    await self._emit_event(
                        "task_start",
                        {
                            "task_id": "flags",
                            "description": "Defining feature flags",
                            "total": len(resolved_scenario.flags),
                        },
                    )
                    progress.update(
                        main_task, description="[cyan]Defining feature flags..."
                    )
                    await self.resource_manager.define_flags(resolved_scenario.flags)
                    completed_steps += 1
                    self._checkpoint(resolved_scenario, "in_progress")
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description="[green]✓[/green] " + self._planned_flags_message(),
                    )
                    await self._emit_event(
                        "task_complete",
                        {
                            "task_id": "flags",
                            "success": True,
                            "message": self._planned_flags_message(),
                        },
                    )

                # Step 4: Create environments
                self.current_step = "environment_creation"
                if resolved_scenario.environments:
                    await self._emit_event(
                        "task_start",
                        {
                            "task_id": "environments",
                            "description": "Creating environments",
                            "total": len(resolved_scenario.environments),
                        },
                    )
                    progress.update(
                        main_task, description="[cyan]Creating environments..."
                    )
                    created_environments = (
                        await self.resource_manager.create_environments(
                            resolved_scenario.environments
                        )
                    )
                    completed_steps += 1
                    self._checkpoint(resolved_scenario, "in_progress")
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description="[green]✓[/green] "
                        + self._outcome_message(
                            len(created_environments),
                            len(self.resource_manager.preexisting_environments),
                            "environment",
                            "environments",
                        ),
                    )
                    await self._emit_event(
                        "task_complete",
                        {
                            "task_id": "environments",
                            "success": True,
                            **self._outcome_event(
                                len(created_environments),
                                len(self.resource_manager.preexisting_environments),
                                "environment",
                                "environments",
                            ),
                        },
                    )

                # Step 5: Create applications
                self.current_step = "application_creation"
                await self._emit_event(
                    "task_start",
                    {
                        "task_id": "applications",
                        "description": "Creating applications",
                        "total": len(resolved_scenario.applications),
                    },
                )
                progress.update(main_task, description="[cyan]Creating applications...")
                created_applications = await self.resource_manager.create_applications(
                    resolved_scenario.applications
                )
                completed_steps += 1
                self._checkpoint(resolved_scenario, "in_progress")
                progress.update(
                    main_task,
                    completed=completed_steps,
                    description="[green]✓[/green] "
                    + self._outcome_message(
                        len(created_applications),
                        len(self.resource_manager.preexisting_applications),
                        "application",
                        "applications",
                    ),
                )
                await self._emit_event(
                    "task_complete",
                    {
                        "task_id": "applications",
                        "success": True,
                        **self._outcome_event(
                            len(created_applications),
                            len(self.resource_manager.preexisting_applications),
                            "application",
                            "applications",
                        ),
                    },
                )

                # Step 5.5: Update environments with FM_TOKEN
                self.current_step = "environment_fm_token_update"
                fm_envs = [
                    e for e in resolved_scenario.environments if e.create_fm_token_var
                ]
                if fm_envs:
                    progress.update(
                        main_task,
                        description="[cyan]Adding SDK keys to environments...",
                    )

                    # Build mapping of environment_name -> application_name
                    env_to_app_mapping = {}
                    for app_config in resolved_scenario.applications:
                        for env_name in app_config.environments:
                            env_to_app_mapping[env_name] = app_config.name

                    await self.resource_manager.update_environments_with_fm_tokens(
                        resolved_scenario.environments,
                        self.use_legacy_flags,
                        env_to_app_mapping,
                    )
                    completed_steps += 1
                    self._checkpoint(resolved_scenario, "in_progress")
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description="[green]✓[/green] SDK keys configured",
                    )

                # Step 6: Configure flags
                self.current_step = "flag_configuration"
                if resolved_scenario.flags:
                    await self._emit_event(
                        "task_start",
                        {
                            "task_id": "flag_configuration",
                            "description": "Configuring feature flags",
                            "total": len(resolved_scenario.flags),
                        },
                    )
                    progress.update(
                        main_task, description="[cyan]Configuring feature flags..."
                    )
                    await self.resource_manager.configure_flags_in_environments(
                        resolved_scenario
                    )
                    completed_steps += 1
                    self._checkpoint(resolved_scenario, "in_progress")
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description="[green]✓[/green] "
                        + self._flag_config_event()["message"],
                    )
                    await self._emit_event(
                        "task_complete",
                        {
                            "task_id": "flag_configuration",
                            "success": True,
                            **self._flag_config_event(),
                        },
                    )
                    # Flags can only be looked up once applications exist, so the
                    # "Defining feature flags" step learns here whether its flags
                    # already existed. Re-emit it so the UI can mark it Pre-existing.
                    await self._emit_event(
                        "task_complete",
                        {
                            "task_id": "flags",
                            "success": True,
                            **self._defined_flags_event(),
                        },
                    )

                self.current_step = "completed"
                progress.update(
                    main_task,
                    completed=total_steps,
                    description="[bold green]✓ Scenario completed successfully!",
                )

                # Build Instance object with structured resources
                instance = self._build_instance(resolved_scenario, status="complete")

                summary = self._generate_summary()
                # Keep Instance object for persistence, will be converted to dict for SSE
                summary["instance"] = instance
                return summary

            except (GitHubError, UnifyAPIError) as e:
                self._checkpoint(resolved_scenario, "failed")
                logger.error(f"External API error during {self.current_step}: {e}")
                console.print(
                    f"\n[red]✗ Pipeline failed at {self.current_step}:[/red] {str(e)}"
                )
                # Emit error event for SSE clients
                await self._emit_event(
                    "task_error",
                    {
                        "task_id": self.current_step,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise PipelineError(
                    f"Pipeline failed at {self.current_step}: {str(e)}",
                    self.current_step,
                    {"scenario": scenario.name, "error_type": type(e).__name__},
                ) from e
            except Exception as e:
                self._checkpoint(resolved_scenario, "failed")
                logger.error(f"Unexpected error during {self.current_step}: {e}")
                console.print(
                    f"\n[red]✗ Unexpected error at {self.current_step}:[/red] {str(e)}"
                )
                # Emit error event for SSE clients
                await self._emit_event(
                    "task_error",
                    {
                        "task_id": self.current_step,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise PipelineError(
                    f"Unexpected error at {self.current_step}: {str(e)}",
                    self.current_step,
                    {"scenario": scenario.name, "error_type": type(e).__name__},
                ) from e
            except BaseException:
                # KeyboardInterrupt / asyncio.CancelledError: keep what was created
                self._checkpoint(resolved_scenario, "failed")
                raise

    def _generate_summary(self) -> dict[str, Any]:
        """Generate a summary of what was created."""
        return {
            "components": list(self.resource_manager.created_components.values()),
            "environments": list(self.resource_manager.created_environments.values()),
            "flags": list(self.resource_manager.created_flags.values()),
            "applications": list(self.resource_manager.created_applications.values()),
            "repositories": list(self.repo_manager.created_repositories.values()),
            "success": True,
        }

    @staticmethod
    def _outcome_message(total: int, reused: int, singular: str, plural: str) -> str:
        """Describe a step's outcome, separating new resources from reused ones.

        Examples: "Created 2 components", "Reused 1 existing repository",
        "Created 1 environment, reused 1 existing".
        """
        created = total - reused

        def noun(n: int) -> str:
            return singular if n == 1 else plural

        if reused == 0:
            return f"Created {created} {noun(created)}"
        if created == 0:
            return f"Reused {reused} existing {noun(reused)}"
        return f"Created {created} {noun(created)}, reused {reused} existing"

    @classmethod
    def _outcome_event(
        cls, total: int, reused: int, singular: str, plural: str
    ) -> dict[str, Any]:
        """task_complete event fields for a create step.

        ``all_preexisting`` is True when the step reused resources and created
        nothing new; the web UI shows it as "Pre-existing" instead of "Complete".
        """
        return {
            "message": cls._outcome_message(total, reused, singular, plural),
            "all_preexisting": total > 0 and reused == total,
        }

    def _planned_flags_message(self) -> str:
        """Step 3 only plans flags in memory; nothing is created yet."""
        n = len(self.resource_manager.flag_definitions)
        noun = "flag" if n == 1 else "flags"
        return f"Planned {n} {noun} (created or reused in the flag configuration step)"

    def _defined_flags_event(self) -> dict[str, Any]:
        """Final task_complete fields for the flag-definition step.

        Sent after flag configuration, once it is known which flags existed.
        """
        rm = self.resource_manager
        event = self._outcome_event(
            len(rm.created_flags), len(rm.preexisting_flags), "flag", "flags"
        )
        planned = len(rm.flag_definitions)
        noun = "flag" if planned == 1 else "flags"
        outcome = event["message"]
        event["message"] = (
            f"Planned {planned} {noun}: {outcome[0].lower()}{outcome[1:]}"
        )
        return event

    def _flag_config_event(self) -> dict[str, Any]:
        """task_complete fields for flag configuration (create/reuse + env settings)."""
        rm = self.resource_manager
        event = self._outcome_event(
            len(rm.created_flags), len(rm.preexisting_flags), "flag", "flags"
        )
        updates = rm.flag_environment_updates
        if updates:
            noun = "environment setting" if updates == 1 else "environment settings"
            event["message"] += f"; applied {updates} {noun} (flag set off)"
        preserved = rm.flag_environment_preserved
        if preserved:
            noun = "environment setting" if preserved == 1 else "environment settings"
            event["message"] += f"; left {preserved} existing {noun} unchanged"
        return event

    def _checkpoint(self, resolved_scenario: Scenario, status: str) -> None:
        """Persist the resources created so far via ``on_checkpoint``.

        Never raises: a failure to save state must not abort (or mask the
        original error of) a run.
        """
        if not self.on_checkpoint:
            return
        try:
            self.on_checkpoint(self._build_instance(resolved_scenario, status=status))
        except Exception as e:
            logger.error(f"Failed to checkpoint instance {self.session_id}: {e}")

    def _build_instance(
        self, resolved_scenario: Scenario, status: str = "complete"
    ) -> Instance:
        """Build an Instance object from created resources.

        Args:
            resolved_scenario: The scenario with resolved template variables
            status: "in_progress", "failed" or "complete"
        """
        # Convert repositories
        repositories = []
        for repo_data in self.repo_manager.created_repositories.values():
            full_name = repo_data.get("full_name", "")
            repo = GitHubRepository(
                id=full_name,
                name=repo_data.get("name", ""),
                owner=full_name.split("/", 1)[0] if "/" in full_name else "",
                url=repo_data.get("html_url", ""),
                created_at=self.created_at,
                existed=bool(repo_data.get("existed", False)),
            )
            repositories.append(repo)

        # Convert components
        components = []
        for name, comp_data in self.resource_manager.created_components.items():
            # Find linked repository URL
            repo_url = None
            if name in self.repo_manager.created_repositories:
                repo_url = self.repo_manager.created_repositories[name].get(
                    "html_url", ""
                )

            component = CloudBeesComponent(
                id=comp_data.get("id", ""),
                name=name,
                org_id=self.organization_id,
                repository_url=repo_url,
                created_at=self.created_at,
                existed=name in self.resource_manager.preexisting_components,
            )
            components.append(component)

        # Convert flags
        flags = []
        for name, flag_data in self.resource_manager.created_flags.items():
            flag = CloudBeesFlag(
                id=flag_data.get("id", ""),
                name=name,
                org_id=self.organization_id,
                type=flag_data.get("type", "boolean"),
                key=flag_data.get("key", name),
                created_at=self.created_at,
                existed=name in self.resource_manager.preexisting_flags,
            )
            flags.append(flag)

        # Convert environments
        environments = []
        for name, env_data in self.resource_manager.created_environments.items():
            # Convert properties to EnvironmentVariable objects
            variables = []
            for prop in env_data.get("properties", []):
                var = EnvironmentVariable(
                    name=prop.get("name", ""),
                    value=prop.get("value", ""),
                    is_secret=prop.get("isSecret", False),
                )
                variables.append(var)

            # Find flags associated with this environment
            flag_ids = []
            for flag_data in self.resource_manager.created_flags.values():
                # This is a simplified approach - in reality we'd need to track
                # which flags were configured for which environments
                flag_ids.append(flag_data.get("id", ""))

            environment = CloudBeesEnvironment(
                id=env_data.get("id", ""),
                name=name,
                org_id=self.organization_id,
                variables=variables,
                flag_ids=flag_ids,
                created_at=self.created_at,
                existed=name in self.resource_manager.preexisting_environments,
            )
            environments.append(environment)

        # Convert applications
        applications = []
        for name, app_data in self.resource_manager.created_applications.items():
            # Get component IDs
            component_ids = []
            for comp in components:
                if comp.id in app_data.get("components", []):
                    component_ids.append(comp.id)

            # Get environment IDs
            environment_ids = []
            for env in environments:
                if env.id in app_data.get("environments", []):
                    environment_ids.append(env.id)

            # Find if this application is marked as shared in the scenario
            is_shared = False
            for app_config in resolved_scenario.applications:
                if app_config.name == name:
                    is_shared = app_config.is_shared
                    break

            application = CloudBeesApplication(
                id=app_data.get("id", ""),
                name=name,
                org_id=self.organization_id,
                repository_url=app_data.get("repositoryUrl", ""),
                component_ids=component_ids,
                environment_ids=environment_ids,
                is_shared=is_shared,
                created_at=self.created_at,
                existed=name in self.resource_manager.preexisting_applications,
            )
            applications.append(application)

        # Create and return Instance
        return Instance(
            id=self.session_id,
            scenario_id=self.scenario_id or "unknown",
            name=self.instance_name,
            tenant=self.tenant or "unknown",
            created_at=self.created_at,
            expires_at=self.expires_at,
            status=status,
            repositories=repositories,
            components=components,
            environments=environments,
            flags=flags,
            applications=applications,
        )

    @staticmethod
    def preview_scenario(scenario: Scenario) -> dict[str, Any]:
        """
        Generate a preview of what resources will be created by a scenario.

        Args:
            scenario: The resolved Scenario to preview (must have template variables resolved)

        Returns:
            Dictionary with preview information about resources to be created
        """
        preview: dict[str, Any] = {
            "repositories": [],
            "components": [],
            "environments": [],
            "applications": [],
            "flags": [],
        }

        # Preview repositories
        for repo_config in scenario.repositories:
            repo_name = repo_config.repo_name_template
            target_org = repo_config.target_org
            source = repo_config.source

            preview["repositories"].append(
                {"name": repo_name, "org": target_org, "source": source}
            )

            # Track components that will be created from repos
            if repo_config.create_component:
                preview["components"].append(repo_name)

        # Preview environments
        for env_config in scenario.environments:
            env_vars = [var.name for var in env_config.env]
            preview["environments"].append(
                {"name": env_config.name, "env_vars": env_vars}
            )

        # Preview applications
        for app_config in scenario.applications:
            preview["applications"].append(
                {
                    "name": app_config.name,
                    "components": app_config.components,
                    "environments": app_config.environments,
                }
            )

        # Preview flags
        for flag_config in scenario.flags:
            # Collect which environments this flag will be configured in
            flag_environments = []
            for env_config in scenario.environments:
                if flag_config.name in env_config.flags:
                    flag_environments.append(env_config.name)

            preview["flags"].append(
                {
                    "name": flag_config.name,
                    "type": flag_config.type,
                    "environments": flag_environments,
                }
            )

        return preview
