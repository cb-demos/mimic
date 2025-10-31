"""
Repository management for GitHub operations.

Handles creation, modification, and collaboration management for GitHub repositories.
"""

import asyncio
import logging
from typing import Any

from mimic import settings
from mimic.gh import GitHubClient
from mimic.pipeline.retry_handler import RetryHandler
from mimic.unify import UnifyAPIClient

logger = logging.getLogger(__name__)


class RepositoryManager:
    """Manages GitHub repository operations for scenario execution."""

    def __init__(
        self,
        github_client: GitHubClient,
        invitee_username: str | None = None,
        organization_id: str | None = None,
        unify_base_url: str | None = None,
        unify_pat: str | None = None,
        event_callback: Any | None = None,
    ):
        """
        Initialize the repository manager.

        Args:
            github_client: GitHubClient instance for API operations
            invitee_username: Optional GitHub username to invite as collaborator
            organization_id: Optional CloudBees organization ID for repository sync polling
            unify_base_url: Optional CloudBees Unify API base URL
            unify_pat: Optional CloudBees Unify API personal access token
            event_callback: Optional callback for emitting SSE progress events
        """
        self.github = github_client
        self.invitee_username = invitee_username
        self.organization_id = organization_id
        self.unify_base_url = unify_base_url
        self.unify_pat = unify_pat
        self.event_callback = event_callback
        self.created_repositories: dict[str, dict[str, Any]] = {}

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event if callback is configured.

        Args:
            event_type: Type of event (e.g., "repo_create_start", "task_progress")
            data: Event data dictionary
        """
        if self.event_callback:
            try:
                await self.event_callback({"event": event_type, "data": data})
            except Exception as e:
                logger.error(f"Error emitting event {event_type}: {e}")

    async def create_repositories(
        self,
        repositories: list,
        parameters: dict[str, str],
    ) -> dict[str, dict[str, Any]]:
        """
        Create GitHub repositories from templates with content replacements.

        Args:
            repositories: List of RepositoryConfig objects
            parameters: Template parameters for conditional operations

        Returns:
            Dictionary mapping repo names to created repository data
        """
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
                await self._emit_event(
                    "task_progress",
                    {
                        "task_id": "repositories",
                        "message": f"Repository {target_org}/{repo_name} already exists, skipping",
                    },
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
                await self._emit_event(
                    "task_progress",
                    {
                        "task_id": "repositories",
                        "message": f"Creating {target_org}/{repo_name} from {repo_config.source}...",
                    },
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
                await self._emit_event(
                    "task_progress",
                    {
                        "task_id": "repositories",
                        "message": f"Repository created: {target_org}/{repo_name}",
                        "url": new_repo.get("html_url", ""),
                    },
                )

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
            # If CloudBees credentials are available, use intelligent polling
            if self.organization_id and self.unify_base_url and self.unify_pat:
                # Build list of repository URLs that need to be synced
                repo_urls = []
                for repo_data in self.created_repositories.values():
                    # Only wait for newly created repos, not existing ones
                    if not repo_data.get("existed", False):
                        # Construct the .git URL format expected by CloudBees
                        full_name = repo_data.get("full_name", "")
                        if full_name:
                            repo_url = f"https://github.com/{full_name}.git"
                            repo_urls.append(repo_url)

                if repo_urls:
                    # Use intelligent polling to wait for CloudBees to sync repositories
                    with UnifyAPIClient(
                        base_url=self.unify_base_url, api_key=self.unify_pat
                    ) as unify_client:
                        await RetryHandler.wait_for_repository_sync(
                            unify_client,
                            self.organization_id,
                            repo_urls,
                            self.event_callback,
                        )
                else:
                    print("   ⏭️  All repositories already existed, no sync needed")
            else:
                # Fallback to basic delay if CloudBees credentials not available
                print(
                    f"   ⏸️  Waiting {settings.REPO_BASIC_DELAY}s for repositories to be ready..."
                )
                await asyncio.sleep(settings.REPO_BASIC_DELAY)
        else:
            print(
                f"   Waiting {settings.REPO_BASIC_DELAY}s for repositories to be ready..."
            )
            await asyncio.sleep(settings.REPO_BASIC_DELAY)

        return self.created_repositories

    async def _apply_file_replacements(
        self, owner: str, repo: str, file_path: str, replacements: dict[str, str]
    ):
        """Apply content replacements to a file in the repository."""
        print(f"     Applying replacements to {file_path}...")
        await self._emit_event(
            "task_progress",
            {
                "task_id": "repositories",
                "message": f"Applying replacements to {file_path} in {owner}/{repo}...",
            },
        )

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
            await self._emit_event(
                "task_progress",
                {
                    "task_id": "repositories",
                    "message": f"Updated {file_path} in {owner}/{repo}",
                },
            )
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
