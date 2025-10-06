"""Resource cleanup management for Mimic sessions."""

from typing import Any

from rich.console import Console

from .config_manager import ConfigManager
from .gh import GitHubClient
from .state_tracker import Session, StateTracker
from .unify import UnifyAPIClient


class CleanupManager:
    """Manages cleanup of resources for Mimic sessions."""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        state_tracker: StateTracker | None = None,
        console: Console | None = None,
    ):
        """
        Initialize the cleanup manager.

        Args:
            config_manager: ConfigManager instance. If None, creates a new one.
            state_tracker: StateTracker instance. If None, creates a new one.
            console: Rich Console for output. If None, creates a new one.
        """
        self.config_manager = config_manager or ConfigManager()
        self.state_tracker = state_tracker or StateTracker()
        self.console = console or Console()

    def get_cleanup_stats(self) -> dict[str, Any]:
        """
        Get cleanup statistics.

        Returns:
            Dictionary with counts of total, active, and expired sessions
        """
        all_sessions = self.state_tracker.list_sessions(include_expired=True)
        expired_sessions = self.state_tracker.list_expired_sessions()

        return {
            "total_sessions": len(all_sessions),
            "active_sessions": len(all_sessions) - len(expired_sessions),
            "expired_sessions": len(expired_sessions),
        }

    def check_expired_sessions(self) -> list[Session]:
        """
        Check for expired sessions.

        Returns:
            List of expired Session objects
        """
        return self.state_tracker.list_expired_sessions()

    async def cleanup_session(
        self, session_id: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Clean up all resources for a specific session.

        Args:
            session_id: Session ID to clean up
            dry_run: If True, only show what would be cleaned up without doing it

        Returns:
            Dictionary with cleanup results

        Raises:
            ValueError: If session not found
        """
        session = self.state_tracker.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        results = {
            "session_id": session_id,
            "scenario_id": session.scenario_id,
            "environment": session.environment,
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
        cloudbees_pat = self.config_manager.get_cloudbees_pat(session.environment)
        env_url = self.config_manager.get_environment_url(session.environment)

        if not cloudbees_pat or not env_url:
            self.console.print(
                f"[yellow]Warning:[/yellow] No credentials found for environment '{session.environment}'. "
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
        resources_by_type = {
            "cloudbees_application": [],
            "cloudbees_environment": [],
            "cloudbees_component": [],
            "github_repo": [],
        }

        # Group resources by type
        for resource in session.resources:
            if resource.type in resources_by_type:
                resources_by_type[resource.type].append(resource)
            elif resource.type == "cloudbees_flag":
                results["skipped"].append(
                    {
                        "type": "cloudbees_flag",
                        "id": resource.id,
                        "reason": "Flags are not safe to auto-cleanup",
                    }
                )

        # Clean up applications
        for resource in resources_by_type["cloudbees_application"]:
            await self._cleanup_application(
                resource, cloudbees_client, results, dry_run
            )

        # Clean up environments
        for resource in resources_by_type["cloudbees_environment"]:
            await self._cleanup_environment(
                resource, cloudbees_client, results, dry_run
            )

        # Clean up components
        for resource in resources_by_type["cloudbees_component"]:
            await self._cleanup_component(resource, cloudbees_client, results, dry_run)

        # Clean up GitHub repositories
        for resource in resources_by_type["github_repo"]:
            await self._cleanup_github_repo(resource, github_client, results, dry_run)

        # Delete session from state if not dry run
        if not dry_run:
            self.state_tracker.delete_session(session_id)
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
        Clean up all expired sessions.

        Args:
            dry_run: If True, only show what would be cleaned up
            auto_confirm: If True, skip confirmation prompt

        Returns:
            Dictionary with cleanup results for all sessions
        """
        expired_sessions = self.check_expired_sessions()

        if not expired_sessions:
            return {
                "total_sessions": 0,
                "cleaned_sessions": 0,
                "failed_sessions": 0,
                "sessions": [],
            }

        results = {
            "total_sessions": len(expired_sessions),
            "cleaned_sessions": 0,
            "failed_sessions": 0,
            "sessions": [],
        }

        if not auto_confirm and not dry_run:
            self.console.print(
                f"\n[yellow]Found {len(expired_sessions)} expired session(s)[/yellow]"
            )
            self.console.print()

        # Clean up each expired session
        for session in expired_sessions:
            try:
                session_result = await self.cleanup_session(session.session_id, dry_run)
                results["sessions"].append(session_result)

                if not session_result["errors"]:
                    results["cleaned_sessions"] += 1
                else:
                    results["failed_sessions"] += 1

            except Exception as e:
                self.console.print(
                    f"[red]Error cleaning up session {session.session_id}:[/red] {e}"
                )
                results["failed_sessions"] += 1
                results["sessions"].append(
                    {
                        "session_id": session.session_id,
                        "error": str(e),
                    }
                )

        return results
