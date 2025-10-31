"""
Retry handling utilities for API operations.

Provides centralized retry logic with exponential backoff for handling
transient failures like GitHub indexing delays and concurrent modifications.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from mimic import settings
from mimic.exceptions import UnifyAPIError

logger = logging.getLogger(__name__)


class RetryHandler:
    """Handles retry logic for API operations with exponential backoff."""

    @staticmethod
    async def with_component_creation_retry(
        operation: Callable[[], Awaitable[dict]],
        repo_name: str,
    ) -> dict:
        """
        Retry component creation with exponential backoff for GitHub indexing delays.

        Args:
            operation: Async callable that performs the component creation
            repo_name: Name of the repository (for logging)

        Returns:
            Result from the operation

        Raises:
            UnifyAPIError: If all retry attempts fail
        """
        for attempt in range(settings.MAX_RETRY_ATTEMPTS):
            try:
                return await operation()
            except UnifyAPIError as e:
                is_last_attempt = attempt == settings.MAX_RETRY_ATTEMPTS - 1

                # Check if error is related to repository not being indexed
                error_msg = str(e).lower()
                is_indexing_error = any(
                    keyword in error_msg
                    for keyword in [
                        "repository not found",
                        "repo not found",
                        "not indexed",
                        "repository does not exist",
                        "invalid repository",
                    ]
                )

                if is_indexing_error and not is_last_attempt:
                    wait_time = settings.RETRY_BACKOFF_BASE * (2**attempt)
                    print(
                        f"     Repository not indexed yet (attempt {attempt + 1}/{settings.MAX_RETRY_ATTEMPTS}), retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Re-raise if not an indexing error or if this is the last attempt
                    raise

        # Should never reach here, but just in case
        raise UnifyAPIError(
            f"Failed to create component {repo_name} after {settings.MAX_RETRY_ATTEMPTS} attempts"
        )

    @staticmethod
    async def with_environment_update_retry(
        operation: Callable[[dict[str, Any] | None], Awaitable[None]],
        fetch_fresh_data: Callable[[], Awaitable[dict]],
        env_name: str,
    ) -> None:
        """
        Retry environment update with exponential backoff for concurrent modifications.

        Args:
            operation: Async callable that performs the update, takes env_data dict
            fetch_fresh_data: Async callable that fetches fresh environment data
            env_name: Name of the environment (for logging)

        Raises:
            UnifyAPIError: If all retry attempts fail
        """
        env_data: dict[str, Any] | None = None

        for attempt in range(settings.MAX_RETRY_ATTEMPTS):
            try:
                # If this is a retry, fetch fresh environment data
                if attempt > 0:
                    print(
                        f"     Retrying environment update (attempt {attempt + 1}/{settings.MAX_RETRY_ATTEMPTS})..."
                    )
                    env_data = await fetch_fresh_data()

                await operation(env_data)
                return  # Success

            except UnifyAPIError as e:
                is_last_attempt = attempt == settings.MAX_RETRY_ATTEMPTS - 1
                error_msg = str(e).lower()
                is_concurrent_error = "concurrent modification" in error_msg

                if is_concurrent_error and not is_last_attempt:
                    wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    print(
                        f"     Concurrent modification detected, retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Re-raise if not a concurrent error or if this is the last attempt
                    raise

        # Should never reach here
        raise UnifyAPIError(
            f"Failed to update environment {env_name} after {settings.MAX_RETRY_ATTEMPTS} attempts"
        )

    @staticmethod
    async def wait_for_repository_sync(
        unify_client: Any,  # UnifyAPIClient
        org_id: str,
        repo_urls: list[str],
        event_callback: Any | None = None,
    ) -> None:
        """
        Wait for repositories to be synced to CloudBees Unify using intelligent polling.

        Polls the CloudBees API to check if repositories have been indexed and are available
        for component creation. Uses exponential backoff to avoid spamming the server.

        Args:
            unify_client: UnifyAPIClient instance for making API calls
            org_id: CloudBees organization ID
            repo_urls: List of repository URLs to wait for (e.g., "https://github.com/org/repo.git")
            event_callback: Optional callback for emitting SSE progress events

        Raises:
            UnifyAPIError: If repositories are not synced within the timeout period
        """
        if not repo_urls:
            return  # Nothing to wait for

        # Helper to emit events
        async def emit_event(event_type: str, data: dict[str, Any]) -> None:
            if event_callback:
                try:
                    await event_callback({"event": event_type, "data": data})
                except Exception as e:
                    logger.error(f"Error emitting event {event_type}: {e}")

        print(
            f"   ⏳ Waiting for {len(repo_urls)} repository(ies) to sync to CloudBees..."
        )
        await emit_event(
            "task_progress",
            {
                "task_id": "repositories",
                "message": f"Waiting for {len(repo_urls)} repository(ies) to sync to CloudBees...",
                "repo_count": len(repo_urls),
            },
        )

        start_time = asyncio.get_event_loop().time()
        interval = settings.REPO_SYNC_INITIAL_INTERVAL
        attempts = 0

        # Normalize repo URLs for comparison (handle both with and without .git suffix)
        def normalize_url(url: str) -> str:
            """Normalize URL for comparison by removing .git suffix if present."""
            return url.rstrip("/").removesuffix(".git")

        normalized_target_urls = {normalize_url(url) for url in repo_urls}

        while True:
            attempts += 1
            elapsed = asyncio.get_event_loop().time() - start_time

            # Check if we've exceeded the timeout
            if elapsed >= settings.REPO_SYNC_TIMEOUT:
                raise UnifyAPIError(
                    f"Timeout waiting for repositories to sync after {elapsed:.1f}s. "
                    f"Repositories may not be visible to CloudBees yet. "
                    f"You can try running the scenario again or check your GitHub connection."
                )

            try:
                # Query CloudBees for list of repositories
                response = unify_client.list_repositories(org_id)
                synced_repos = response.get("repository", [])

                # Extract URLs from synced repos and normalize them
                synced_urls = {
                    normalize_url(repo.get("url", "")) for repo in synced_repos
                }

                # Check if all target repositories are now synced
                missing_repos = normalized_target_urls - synced_urls

                if not missing_repos:
                    print(
                        f"   ✅ All repositories synced after {elapsed:.1f}s ({attempts} checks)"
                    )
                    await emit_event(
                        "task_progress",
                        {
                            "task_id": "repositories",
                            "message": f"All repositories synced after {elapsed:.1f}s",
                        },
                    )
                    return

                # Calculate next wait time with exponential backoff (capped)
                next_interval = min(interval, settings.REPO_SYNC_MAX_INTERVAL)
                remaining_time = settings.REPO_SYNC_TIMEOUT - elapsed

                # Extract repo names from URLs for better display
                missing_repo_names = [
                    url.split("/")[-1].replace(".git", "") for url in missing_repos
                ]
                sync_message = (
                    f"Waiting for {len(missing_repos)} repo(s) to sync... "
                    f"(checking again in {next_interval}s, {remaining_time:.0f}s remaining)"
                )
                print(f"     {sync_message}")
                await emit_event(
                    "task_progress",
                    {
                        "task_id": "repositories",
                        "message": sync_message,
                        "missing_repos": missing_repo_names,
                        "remaining_time": int(remaining_time),
                    },
                )

                await asyncio.sleep(next_interval)

                # Exponential backoff: double the interval for next time
                interval = min(interval * 2, settings.REPO_SYNC_MAX_INTERVAL)

            except UnifyAPIError as e:
                # If we get an API error, log it but continue retrying
                # (unless we're out of time, which is checked at the top of the loop)
                logger.warning(
                    f"API error while checking repository sync: {e}. Will retry..."
                )
                await asyncio.sleep(settings.REPO_SYNC_INITIAL_INTERVAL)
            except Exception as e:
                # Unexpected error - log and continue
                logger.error(f"Unexpected error checking repository sync: {e}")
                await asyncio.sleep(settings.REPO_SYNC_INITIAL_INTERVAL)
