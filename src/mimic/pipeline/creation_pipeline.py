"""
CloudBees Unify Creation Pipeline
Orchestrates the setup of a complete scenario including repos, components, environments, flags, and applications.
"""

import logging
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
    ):
        self.organization_id = organization_id
        self.endpoint_id = endpoint_id
        self.unify_pat = unify_pat
        self.unify_base_url = unify_base_url
        self.session_id = session_id
        self.github_pat = github_pat
        self.invitee_username = invitee_username
        self.env_properties = env_properties or {}
        self.current_step = "initialization"

        # Initialize GitHub client
        github_client = GitHubClient(github_pat)

        # Initialize managers
        self.repo_manager = RepositoryManager(github_client, invitee_username)
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
        resolved_scenario = scenario.resolve_template_variables(
            processed_parameters, self.env_properties
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

                # Step 1: Create repositories
                self.current_step = "repository_creation"
                progress.update(
                    main_task, description="[cyan]Creating GitHub repositories..."
                )
                created_repositories = await self.repo_manager.create_repositories(
                    resolved_scenario.repositories, processed_parameters
                )
                completed_steps += 1
                progress.update(
                    main_task,
                    completed=completed_steps,
                    description=f"[green]✓[/green] Created {len(created_repositories)} repositories",
                )

                # Step 2: Create components
                self.current_step = "component_creation"
                component_repos = [
                    r for r in resolved_scenario.repositories if r.create_component
                ]
                if component_repos:
                    progress.update(
                        main_task, description="[cyan]Creating CloudBees components..."
                    )
                    created_components = await self.resource_manager.create_components(
                        resolved_scenario.repositories, created_repositories
                    )
                    completed_steps += 1
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description=f"[green]✓[/green] Created {len(created_components)} components",
                    )

                # Step 3: Define feature flags
                self.current_step = "flag_creation"
                if resolved_scenario.flags:
                    progress.update(
                        main_task, description="[cyan]Defining feature flags..."
                    )
                    await self.resource_manager.define_flags(resolved_scenario.flags)
                    completed_steps += 1
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description=f"[green]✓[/green] Defined {len(self.resource_manager.flag_definitions)} flags",
                    )

                # Step 4: Create environments
                self.current_step = "environment_creation"
                if resolved_scenario.environments:
                    progress.update(
                        main_task, description="[cyan]Creating environments..."
                    )
                    created_environments = (
                        await self.resource_manager.create_environments(
                            resolved_scenario.environments
                        )
                    )
                    completed_steps += 1
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description=f"[green]✓[/green] Created {len(created_environments)} environments",
                    )

                # Step 5: Create applications
                self.current_step = "application_creation"
                progress.update(main_task, description="[cyan]Creating applications...")
                created_applications = await self.resource_manager.create_applications(
                    resolved_scenario.applications
                )
                completed_steps += 1
                progress.update(
                    main_task,
                    completed=completed_steps,
                    description=f"[green]✓[/green] Created {len(created_applications)} applications",
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
                    await self.resource_manager.update_environments_with_fm_tokens(
                        resolved_scenario.environments
                    )
                    completed_steps += 1
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description="[green]✓[/green] SDK keys configured",
                    )

                # Step 6: Configure flags
                self.current_step = "flag_configuration"
                if resolved_scenario.flags:
                    progress.update(
                        main_task, description="[cyan]Configuring feature flags..."
                    )
                    await self.resource_manager.configure_flags_in_environments(
                        resolved_scenario
                    )
                    completed_steps += 1
                    progress.update(
                        main_task,
                        completed=completed_steps,
                        description="[green]✓[/green] Feature flags configured",
                    )

                self.current_step = "completed"
                progress.update(
                    main_task,
                    completed=total_steps,
                    description="[bold green]✓ Scenario completed successfully!",
                )

                summary = self._generate_summary()
                return summary

            except (GitHubError, UnifyAPIError) as e:
                logger.error(f"External API error during {self.current_step}: {e}")
                console.print(
                    f"\n[red]✗ Pipeline failed at {self.current_step}:[/red] {str(e)}"
                )
                raise PipelineError(
                    f"Pipeline failed at {self.current_step}: {str(e)}",
                    self.current_step,
                    {"scenario": scenario.name, "error_type": type(e).__name__},
                ) from e
            except Exception as e:
                logger.error(f"Unexpected error during {self.current_step}: {e}")
                console.print(
                    f"\n[red]✗ Unexpected error at {self.current_step}:[/red] {str(e)}"
                )
                raise PipelineError(
                    f"Unexpected error at {self.current_step}: {str(e)}",
                    self.current_step,
                    {"scenario": scenario.name, "error_type": type(e).__name__},
                ) from e

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
