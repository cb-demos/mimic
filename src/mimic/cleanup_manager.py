"""Resource cleanup management for Mimic instances."""

from typing import Any

from rich.console import Console

from .config_manager import ConfigManager
from .gh import GitHubClient
from .instance_repository import InstanceRepository
from .models import Instance
from .unify import UnifyAPIClient


class CleanupManager:
    """Manages cleanup of resources for Mimic instances."""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        instance_repository: InstanceRepository | None = None,
        console: Console | None = None,
    ):
        """
        Initialize the cleanup manager.

        Args:
            config_manager: ConfigManager instance. If None, creates a new one.
            instance_repository: InstanceRepository instance. If None, creates a new one.
            console: Rich Console for output. If None, creates a new one.
        """
        self.config_manager = config_manager or ConfigManager()
        self.instance_repository = instance_repository or InstanceRepository()
        self.console = console or Console()

    def get_cleanup_stats(self) -> dict[str, Any]:
        """
        Get cleanup statistics.

        Returns:
            Dictionary with counts of total, active, and expired instances
        """
        all_instances = self.instance_repository.find_all(include_expired=True)
        expired_instances = self.instance_repository.find_expired()

        return {
            "total_sessions": len(all_instances),
            "active_sessions": len(all_instances) - len(expired_instances),
            "expired_sessions": len(expired_instances),
        }

    def check_expired_sessions(self) -> list[Instance]:
        """
        Check for expired instances.

        Returns:
            List of expired Instance objects
        """
        return self.instance_repository.find_expired()

    async def cleanup_session(
        self, session_id: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Clean up all resources for a specific instance.

        Args:
            session_id: Instance ID to clean up
            dry_run: If True, only show what would be cleaned up without doing it

        Returns:
            Dictionary with cleanup results

        Raises:
            ValueError: If instance not found
        """
        instance = self.instance_repository.get_by_id(session_id)
        if not instance:
            raise ValueError(f"Instance {session_id} not found")

        results = {
            "session_id": session_id,
            "scenario_id": instance.scenario_id,
            "environment": instance.environment,
            "dry_run": dry_run,
            "cleaned": [],
            "errors": [],
            "skipped": [],
        }

        if dry_run:
            self.console.print(
                "\n[yellow]Dry run - no resources will be deleted[/yellow]"
            )

        # Get credentials
        github_pat = self.config_manager.get_github_pat()
        cloudbees_pat = self.config_manager.get_cloudbees_pat(instance.environment)
        env_url = self.config_manager.get_environment_url(instance.environment)

        if not cloudbees_pat or not env_url:
            self.console.print(
                f"[yellow]Warning:[/yellow] No credentials found for environment '{instance.environment}'. "
                "Skipping CloudBees resources."
            )

        # Initialize clients
        github_client = GitHubClient(github_pat) if github_pat else None
        cloudbees_client = (
            UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat)
            if cloudbees_pat and env_url
            else None
        )

        # Clean up resources in reverse order (to handle dependencies)
        # Skip flags - they're not safe to auto-cleanup
        for flag in instance.flags:
            results["skipped"].append(
                {
                    "type": "cloudbees_flag",
                    "id": flag.id,
                    "reason": "Flags are not safe to auto-cleanup",
                }
            )

        # Clean up applications
        for application in instance.applications:
            await self._cleanup_application(
                application, cloudbees_client, results, dry_run
            )

        # Clean up environments
        for environment in instance.environments:
            await self._cleanup_environment(
                environment, cloudbees_client, results, dry_run
            )

        # Clean up components
        for component in instance.components:
            await self._cleanup_component(component, cloudbees_client, results, dry_run)

        # Clean up GitHub repositories
        for repository in instance.repositories:
            await self._cleanup_github_repo(repository, github_client, results, dry_run)

        # Delete instance from repository if not dry run
        if not dry_run:
            self.instance_repository.delete(session_id)
            results["session_deleted"] = True

        # Close clients
        if cloudbees_client:
            cloudbees_client.close()

        return results

    async def _cleanup_github_repo(
        self, resource, github_client, results, dry_run: bool
    ):
        """Clean up a GitHub repository."""
        repo_name = resource.id  # Full repo name like "owner/repo"

        if not github_client:
            results["skipped"].append(
                {
                    "type": "github_repo",
                    "id": resource.id,
                    "reason": "No GitHub credentials configured",
                }
            )
            return

        try:
            if dry_run:
                self.console.print(
                    f"  [dim]Would delete GitHub repo:[/dim] {repo_name}"
                )
                results["cleaned"].append(
                    {"type": "github_repo", "id": resource.id, "dry_run": True}
                )
            else:
                success = await github_client.delete_repository(repo_name)
                if success:
                    self.console.print(
                        f"  [green]✓[/green] Deleted GitHub repo: {repo_name}"
                    )
                    results["cleaned"].append(
                        {"type": "github_repo", "id": resource.id}
                    )
                else:
                    results["errors"].append(
                        {
                            "type": "github_repo",
                            "id": resource.id,
                            "error": "Deletion failed",
                        }
                    )
        except Exception as e:
            self.console.print(
                f"  [red]✗[/red] Failed to delete GitHub repo {repo_name}: {e}"
            )
            results["errors"].append(
                {"type": "github_repo", "id": resource.id, "error": str(e)}
            )

    async def _cleanup_component(
        self, resource, cloudbees_client, results, dry_run: bool
    ):
        """Clean up a CloudBees component."""
        if not cloudbees_client:
            results["skipped"].append(
                {
                    "type": "cloudbees_component",
                    "id": resource.id,
                    "reason": "No CloudBees credentials configured",
                }
            )
            return

        try:
            if dry_run:
                self.console.print(
                    f"  [dim]Would delete component:[/dim] {resource.name} ({resource.id})"
                )
                results["cleaned"].append(
                    {"type": "cloudbees_component", "id": resource.id, "dry_run": True}
                )
            else:
                cloudbees_client.delete_component(resource.org_id, resource.id)
                self.console.print(
                    f"  [green]✓[/green] Deleted component: {resource.name}"
                )
                results["cleaned"].append(
                    {"type": "cloudbees_component", "id": resource.id}
                )
        except Exception as e:
            self.console.print(
                f"  [red]✗[/red] Failed to delete component {resource.name}: {e}"
            )
            results["errors"].append(
                {"type": "cloudbees_component", "id": resource.id, "error": str(e)}
            )

    async def _cleanup_environment(
        self, resource, cloudbees_client, results, dry_run: bool
    ):
        """Clean up a CloudBees environment."""
        if not cloudbees_client:
            results["skipped"].append(
                {
                    "type": "cloudbees_environment",
                    "id": resource.id,
                    "reason": "No CloudBees credentials configured",
                }
            )
            return

        try:
            if dry_run:
                self.console.print(
                    f"  [dim]Would delete environment:[/dim] {resource.name} ({resource.id})"
                )
                results["cleaned"].append(
                    {
                        "type": "cloudbees_environment",
                        "id": resource.id,
                        "dry_run": True,
                    }
                )
            else:
                cloudbees_client.delete_environment(resource.org_id, resource.id)
                self.console.print(
                    f"  [green]✓[/green] Deleted environment: {resource.name}"
                )
                results["cleaned"].append(
                    {"type": "cloudbees_environment", "id": resource.id}
                )
        except Exception as e:
            self.console.print(
                f"  [red]✗[/red] Failed to delete environment {resource.name}: {e}"
            )
            results["errors"].append(
                {"type": "cloudbees_environment", "id": resource.id, "error": str(e)}
            )

    async def _cleanup_application(
        self, resource, cloudbees_client, results, dry_run: bool
    ):
        """Clean up a CloudBees application (and its feature flags)."""
        if not cloudbees_client:
            results["skipped"].append(
                {
                    "type": "cloudbees_application",
                    "id": resource.id,
                    "reason": "No CloudBees credentials configured",
                }
            )
            return

        try:
            if dry_run:
                self.console.print(
                    f"  [dim]Would delete application:[/dim] {resource.name} ({resource.id})"
                )
                results["cleaned"].append(
                    {
                        "type": "cloudbees_application",
                        "id": resource.id,
                        "dry_run": True,
                    }
                )
            else:
                cloudbees_client.delete_application(resource.org_id, resource.id)
                self.console.print(
                    f"  [green]✓[/green] Deleted application: {resource.name}"
                )
                results["cleaned"].append(
                    {"type": "cloudbees_application", "id": resource.id}
                )
        except Exception as e:
            self.console.print(
                f"  [red]✗[/red] Failed to delete application {resource.name}: {e}"
            )
            results["errors"].append(
                {"type": "cloudbees_application", "id": resource.id, "error": str(e)}
            )

    async def cleanup_expired_sessions(
        self, dry_run: bool = False, auto_confirm: bool = False
    ) -> dict[str, Any]:
        """
        Clean up all expired instances.

        Args:
            dry_run: If True, only show what would be cleaned up
            auto_confirm: If True, skip confirmation prompt

        Returns:
            Dictionary with cleanup results for all instances
        """
        expired_instances = self.check_expired_sessions()

        if not expired_instances:
            return {
                "total_sessions": 0,
                "cleaned_sessions": 0,
                "failed_sessions": 0,
                "sessions": [],
            }

        results = {
            "total_sessions": len(expired_instances),
            "cleaned_sessions": 0,
            "failed_sessions": 0,
            "sessions": [],
        }

        if not auto_confirm and not dry_run:
            self.console.print(
                f"\n[yellow]Found {len(expired_instances)} expired instance(s)[/yellow]"
            )
            self.console.print()

        # Clean up each expired instance
        for instance in expired_instances:
            try:
                session_result = await self.cleanup_session(instance.id, dry_run)
                results["sessions"].append(session_result)

                if not session_result["errors"]:
                    results["cleaned_sessions"] += 1
                else:
                    results["failed_sessions"] += 1

            except Exception as e:
                self.console.print(
                    f"[red]Error cleaning up instance {instance.id}:[/red] {e}"
                )
                results["failed_sessions"] += 1
                results["sessions"].append(
                    {
                        "session_id": instance.id,
                        "error": str(e),
                    }
                )

        return results
