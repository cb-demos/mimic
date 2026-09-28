"""Resource cleanup management for Mimic instances."""

from typing import Any

from rich.console import Console

from .config_manager import ConfigManager
from .gh import GitHubClient
from .instance_repository import InstanceRepository
from .models import Instance
from .unify import UnifyAPIClient

# Reasons a tracked resource is kept (never deleted) by cleanup.
KEEP_REASON_FLAG = "Flags are not safe to auto-cleanup (shared across environments)"
KEEP_REASON_PREEXISTING = "Existed before this run"
KEEP_REASON_SHARED_APP = "Application is marked as shared and won't be deleted"
KEEP_REASON_SHARED_APP_IN_USE = (
    "Shared application is still used by other environments or components"
)

# Conditional outcomes: decided at cleanup time by a live check (see
# CleanupManager._cleanup_shared_application). Listed as "kept" until then.
CONDITIONAL_SHARED_APP = (
    "Shared application created by this run: deleted only if nothing else "
    "is still attached (checked at cleanup)"
)
CONDITIONAL_FLAG = "Removed with its application if that application is deleted"
CONDITIONAL_REASONS = frozenset({CONDITIONAL_SHARED_APP, CONDITIONAL_FLAG})

REMOVED_WITH_APPLICATION = "Removed with its application"


def _flag_parent_application(instance: Instance | None) -> Any:
    """The application a run's flags belong to, when it is unambiguous.

    mimic tracks flags by name without their application, so flags are tied
    to an application only when the run has exactly one.
    """
    if instance is not None and len(instance.applications) == 1:
        return instance.applications[0]
    return None


def keep_reason(
    resource_type: str, resource: Any, instance: Instance | None = None
) -> str | None:
    """Return why cleanup keeps this resource, or None if cleanup deletes it.

    This is the single source of truth used by cleanup itself and by the UI
    (instance list and cleanup preview), so what is shown matches what happens.
    Reasons in CONDITIONAL_REASONS mean "decided by a live check at cleanup".

    Args:
        resource_type: One of "github_repo", "cloudbees_component",
            "cloudbees_environment", "cloudbees_application", "cloudbees_flag"
        resource: The resource model from an Instance
        instance: The owning Instance (needed to classify flags)
    """
    if getattr(resource, "existed", False):
        return KEEP_REASON_PREEXISTING
    if resource_type == "cloudbees_flag":
        parent = _flag_parent_application(instance)
        if parent is None:
            return KEEP_REASON_FLAG
        parent_reason = keep_reason("cloudbees_application", parent)
        if parent_reason is None:
            return None  # the application is deleted, and its flags with it
        if parent_reason == CONDITIONAL_SHARED_APP:
            return CONDITIONAL_FLAG
        return KEEP_REASON_FLAG
    if resource_type == "cloudbees_application" and getattr(
        resource, "is_shared", False
    ):
        # Not pre-existing, so this run created it
        return CONDITIONAL_SHARED_APP
    return None


def is_conditional(reason: str | None) -> bool:
    """True if the outcome is decided by a live check at cleanup time."""
    return reason in CONDITIONAL_REASONS


def summarize_results(results: dict[str, Any]) -> dict[str, int]:
    """Count the outcomes of a ``cleanup_session`` result.

    Returns:
        {"deleted", "already_gone", "kept", "failed"}. On a dry run "deleted"
        means "would delete".
    """
    cleaned = results.get("cleaned", [])
    already_gone = sum(1 for c in cleaned if c.get("already_gone"))
    return {
        "deleted": len(cleaned) - already_gone,
        "already_gone": already_gone,
        "kept": len(results.get("skipped", [])),
        "failed": len(results.get("errors", [])),
    }


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
            Dictionary with cleanup results. "cleaned" items that were already
            removed outside mimic carry ``already_gone: True``.

        Raises:
            ValueError: If instance not found
        """
        instance = self.instance_repository.get_by_id(session_id)
        if not instance:
            raise ValueError(f"Instance {session_id} not found")

        results = {
            "session_id": session_id,
            "scenario_id": instance.scenario_id,
            "tenant": instance.tenant,
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
        cloudbees_pat = self.config_manager.get_cloudbees_pat(instance.tenant)
        env_url = self.config_manager.get_tenant_url(instance.tenant)

        if not cloudbees_pat or not env_url:
            self.console.print(
                f"[yellow]Warning:[/yellow] No credentials found for environment '{instance.tenant}'. "
                "Skipping CloudBees resources."
            )

        # Initialize clients
        github_client = GitHubClient(github_pat) if github_pat else None
        cloudbees_client = (
            UnifyAPIClient(base_url=env_url, api_key=cloudbees_pat)
            if cloudbees_pat and env_url
            else None
        )

        # Clean up resources in reverse order (to handle dependencies).
        # Pre-existing resources are kept. Shared applications this run created
        # are handled last, once this run's environments/components are gone.
        deferred_shared_apps = []
        removed_app_ids: set[str] = set()

        for application in instance.applications:
            reason = keep_reason("cloudbees_application", application, instance)
            if reason == CONDITIONAL_SHARED_APP:
                deferred_shared_apps.append(application)
                continue
            if self._skip_if_kept(application, "cloudbees_application", results):
                continue
            if await self._cleanup_application(
                application, cloudbees_client, results, dry_run
            ):
                removed_app_ids.add(application.id)

        for environment in instance.environments:
            if self._skip_if_kept(environment, "cloudbees_environment", results):
                continue
            await self._cleanup_environment(
                environment, cloudbees_client, results, dry_run
            )

        for component in instance.components:
            if self._skip_if_kept(component, "cloudbees_component", results):
                continue
            await self._cleanup_component(component, cloudbees_client, results, dry_run)

        for repository in instance.repositories:
            if self._skip_if_kept(repository, "github_repo", results):
                continue
            await self._cleanup_github_repo(repository, github_client, results, dry_run)

        for application in deferred_shared_apps:
            if await self._cleanup_shared_application(
                application, instance, cloudbees_client, results, dry_run
            ):
                removed_app_ids.add(application.id)

        # Flags have no delete call; they are removed with their application.
        parent = _flag_parent_application(instance)
        for flag in instance.flags:
            reason = keep_reason("cloudbees_flag", flag, instance)
            if reason is None or is_conditional(reason):
                if parent is not None and parent.id in removed_app_ids:
                    self._record_removed_with_application(results, flag, dry_run)
                    continue
                # The application was kept (in use, failed, or no credentials)
                reason = KEEP_REASON_FLAG
            self.console.print(f"  [dim]⏭️  Keeping cloudbees_flag:[/dim] {flag.name}")
            results["skipped"].append(
                {
                    "type": "cloudbees_flag",
                    "id": flag.id,
                    "name": flag.name,
                    "reason": reason,
                }
            )

        # Delete instance from repository if not dry run
        if not dry_run:
            self.instance_repository.delete(session_id)
            results["session_deleted"] = True

        # Close clients
        if cloudbees_client:
            cloudbees_client.close()

        return results

    def _skip_if_kept(
        self, resource: Any, resource_type: str, results: dict[str, Any]
    ) -> bool:
        """Record and skip a resource that cleanup must keep.

        Returns:
            True if the resource was skipped.
        """
        reason = keep_reason(resource_type, resource)
        if reason is None:
            return False
        label = getattr(resource, "name", None) or resource.id
        if reason == KEEP_REASON_PREEXISTING:
            self.console.print(
                f"  [dim]⏭️  Skipping pre-existing {resource_type}:[/dim] {label}"
            )
        else:
            self.console.print(f"  [dim]⏭️  Keeping {resource_type}:[/dim] {label}")
        results["skipped"].append(
            {
                "type": resource_type,
                "id": resource.id,
                "name": getattr(resource, "name", ""),
                "reason": reason,
            }
        )
        return True

    def _record_removed_with_application(
        self, results: dict[str, Any], flag: Any, dry_run: bool
    ) -> None:
        verb = "Would be removed" if dry_run else "Removed"
        self.console.print(
            f"  [dim]{verb} with its application:[/dim] flag {flag.name}"
        )
        item = {
            "type": "cloudbees_flag",
            "id": flag.id,
            "name": flag.name,
            "message": REMOVED_WITH_APPLICATION,
        }
        if dry_run:
            item["dry_run"] = True
        results["cleaned"].append(item)

    async def _cleanup_shared_application(
        self,
        resource: Any,
        instance: Instance,
        cloudbees_client: Any,
        results: dict[str, Any],
        dry_run: bool,
    ) -> bool:
        """Delete a shared application this run created, but only if unused.

        Live-checks the application's linked environments and components. If
        anything other than this run's own environments/components is still
        attached (for example another SE's run), the application is kept.

        Returns:
            True if the application was deleted (or would be, on a dry run),
            or was already gone.
        """
        if not cloudbees_client:
            self._record_no_credentials(
                results, "cloudbees_application", resource, "CloudBees"
            )
            return False

        def keep(reason: str) -> bool:
            self.console.print(
                f"  [dim]⏭️  Keeping cloudbees_application:[/dim] {resource.name}"
            )
            results["skipped"].append(
                {
                    "type": "cloudbees_application",
                    "id": resource.id,
                    "name": resource.name,
                    "reason": reason,
                }
            )
            return False

        try:
            apps = cloudbees_client.list_applications(resource.org_id).get(
                "service", []
            )
        except Exception as e:
            return keep(
                f"Could not check whether the shared application is still in use: {e}"
            )

        current = next((a for a in apps if a.get("id") == resource.id), None)
        label = f"application: {resource.name}"
        if current is None:
            self._record_deleted(
                results, "cloudbees_application", resource, label, deleted=False
            )
            return True

        own_ids = {e.id for e in instance.environments} | {
            c.id for c in instance.components
        }
        linked = list(current.get("linkedEnvironmentIds") or []) + list(
            current.get("linkedComponentIds") or []
        )
        others = [x for x in linked if x not in own_ids]
        if others:
            return keep(f"{KEEP_REASON_SHARED_APP_IN_USE} ({len(others)} attached)")

        return await self._delete_application(
            resource, cloudbees_client, results, dry_run
        )

    def _record_deleted(
        self,
        results: dict[str, Any],
        resource_type: str,
        resource: Any,
        label: str,
        deleted: bool | None,
    ) -> None:
        """Record a completed delete. ``deleted is False`` means it was already gone."""
        already_gone = deleted is False
        if already_gone:
            self.console.print(
                f"  [dim]–  Already gone (removed outside mimic):[/dim] {label}"
            )
        else:
            self.console.print(f"  [green]✓[/green] Deleted {label}")
        item = {"type": resource_type, "id": resource.id, "name": resource.name}
        if already_gone:
            item["already_gone"] = True
        results["cleaned"].append(item)

    def _record_dry_run(
        self, results: dict[str, Any], resource_type: str, resource: Any, label: str
    ) -> None:
        self.console.print(f"  [dim]Would delete {label}[/dim]")
        results["cleaned"].append(
            {
                "type": resource_type,
                "id": resource.id,
                "name": resource.name,
                "dry_run": True,
            }
        )

    def _record_error(
        self,
        results: dict[str, Any],
        resource_type: str,
        resource: Any,
        label: str,
        error: str,
    ) -> None:
        self.console.print(f"  [red]✗[/red] Failed to delete {label}: {error}")
        results["errors"].append(
            {
                "type": resource_type,
                "id": resource.id,
                "name": resource.name,
                "error": error,
            }
        )

    def _record_no_credentials(
        self, results: dict[str, Any], resource_type: str, resource: Any, which: str
    ) -> None:
        results["skipped"].append(
            {
                "type": resource_type,
                "id": resource.id,
                "name": resource.name,
                "reason": f"No {which} credentials configured",
            }
        )

    async def _cleanup_github_repo(
        self, resource, github_client, results, dry_run: bool
    ):
        """Clean up a GitHub repository."""
        repo_name = resource.id  # Full repo name like "owner/repo"
        label = f"GitHub repo: {repo_name}"

        if not github_client:
            self._record_no_credentials(results, "github_repo", resource, "GitHub")
            return

        try:
            if dry_run:
                self._record_dry_run(results, "github_repo", resource, label)
            else:
                deleted = await github_client.delete_repository(repo_name)
                self._record_deleted(results, "github_repo", resource, label, deleted)
        except Exception as e:
            self._record_error(results, "github_repo", resource, label, str(e))

    async def _cleanup_component(
        self, resource, cloudbees_client, results, dry_run: bool
    ):
        """Clean up a CloudBees component."""
        label = f"component: {resource.name}"

        if not cloudbees_client:
            self._record_no_credentials(
                results, "cloudbees_component", resource, "CloudBees"
            )
            return

        try:
            if dry_run:
                self._record_dry_run(results, "cloudbees_component", resource, label)
            else:
                deleted = cloudbees_client.delete_component(
                    resource.org_id, resource.id
                )
                self._record_deleted(
                    results, "cloudbees_component", resource, label, deleted
                )
        except Exception as e:
            self._record_error(results, "cloudbees_component", resource, label, str(e))

    async def _cleanup_environment(
        self, resource, cloudbees_client, results, dry_run: bool
    ):
        """Clean up a CloudBees environment."""
        label = f"environment: {resource.name}"

        if not cloudbees_client:
            self._record_no_credentials(
                results, "cloudbees_environment", resource, "CloudBees"
            )
            return

        try:
            if dry_run:
                self._record_dry_run(results, "cloudbees_environment", resource, label)
            else:
                deleted = cloudbees_client.delete_environment(
                    resource.org_id, resource.id
                )
                self._record_deleted(
                    results, "cloudbees_environment", resource, label, deleted
                )
        except Exception as e:
            self._record_error(
                results, "cloudbees_environment", resource, label, str(e)
            )

    async def _cleanup_application(
        self, resource, cloudbees_client, results, dry_run: bool
    ) -> bool:
        """Clean up a (non-shared) CloudBees application.

        Returns:
            True if deleted, would be deleted (dry run) or already gone.
        """
        if not cloudbees_client:
            self._record_no_credentials(
                results, "cloudbees_application", resource, "CloudBees"
            )
            return False

        # Defensive: shared applications go through _cleanup_shared_application
        if resource.is_shared:
            self._skip_if_kept(resource, "cloudbees_application", results)
            return False

        return await self._delete_application(
            resource, cloudbees_client, results, dry_run
        )

    async def _delete_application(
        self, resource, cloudbees_client, results, dry_run: bool
    ) -> bool:
        label = f"application: {resource.name}"
        try:
            if dry_run:
                self._record_dry_run(results, "cloudbees_application", resource, label)
            else:
                deleted = cloudbees_client.delete_application(
                    resource.org_id, resource.id
                )
                self._record_deleted(
                    results, "cloudbees_application", resource, label, deleted
                )
            return True
        except Exception as e:
            self._record_error(
                results, "cloudbees_application", resource, label, str(e)
            )
            return False

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
