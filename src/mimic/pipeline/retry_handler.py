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
