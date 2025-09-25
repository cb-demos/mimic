"""Resource cleanup services with PAT fallback strategy."""

import logging
from typing import Any

from src.auth import get_auth_service
from src.database import get_database
from src.gh import GitHubClient
from src.security import NoValidPATFoundError
from src.unify import UnifyAPIClient, UnifyAPIError

logger = logging.getLogger(__name__)


class CleanupService:
    """Handles resource cleanup with robust PAT fallback."""

    def __init__(self):
        self.db = get_database()
        self.auth = get_auth_service()

    async def cleanup_single_resource(self, resource_id: str, user_email: str) -> None:
        """Clean up a single resource using fallback PAT strategy.

        Args:
            resource_id: The resource ID to clean up
            user_email: The email of the user who owns the resource

        Raises:
            NoValidPATFoundError: If no working PAT can be found
            Exception: If cleanup fails for other reasons
        """
        # Get the resource details
        resource = await self.db.fetchone(
            "SELECT * FROM resources WHERE id = ?", (resource_id,)
        )

        if not resource:
            logger.warning(f"Resource {resource_id} not found")
            return

        platform = resource["platform"]
        resource_type = resource["resource_type"]
        resource_ref = resource["resource_id"]

        logger.info(f"Cleaning up {resource_type} {resource_ref} for {user_email}")

        try:
            # Get all available PATs for fallback logic
            pats = await self.auth.get_fallback_pats(user_email, platform)

            last_error = None
            for pat in pats:
                try:
                    # Use the PAT to clean up the resource
                    if platform == "github":
                        await self._cleanup_github_resource(resource, pat)
                    elif platform == "cloudbees":
                        await self._cleanup_cloudbees_resource(resource, pat)
                    else:
                        raise ValueError(f"Unknown platform: {platform}")

                    logger.info(
                        f"Successfully cleaned up {resource_type} {resource_ref}"
                    )
                    return  # Success, exit early

                except Exception as e:
                    logger.warning(
                        f"PAT failed for {resource_type} {resource_ref}: {e}"
                    )
                    last_error = e
                    continue  # Try next PAT

            # All PATs failed
            raise NoValidPATFoundError(
                f"All PATs failed for {user_email} on {platform}: {last_error}"
            )

        except NoValidPATFoundError:
            logger.error(f"No valid PATs found for {user_email} on {platform}")
            raise
        except Exception as e:
            logger.error(f"Failed to cleanup resource {resource_id}: {e}")
            raise

    async def _cleanup_github_resource(self, resource: Any, github_pat: str) -> None:
        """Clean up a GitHub resource.

        Args:
            resource: Database resource record
            github_pat: GitHub PAT to use
        """
        resource_type = resource["resource_type"]
        resource_ref = resource[
            "resource_id"
        ]  # This should be the full_name like "owner/repo"

        if resource_type == "github_repo":
            client = GitHubClient(token=github_pat)
            await client.delete_repository(resource_ref)  # type: ignore[attr-defined]
            logger.info(f"Deleted GitHub repository {resource_ref}")
        else:
            raise ValueError(f"Unknown GitHub resource type: {resource_type}")

    async def _cleanup_cloudbees_resource(self, resource: Any, unify_pat: str) -> None:
        """Clean up a CloudBees resource.

        Args:
            resource: Database resource record
            unify_pat: CloudBees Unify PAT to use
        """
        resource_type = resource["resource_type"]
        resource_ref = resource["resource_id"]  # This should be the UUID or identifier

        # Parse metadata if available
        metadata = {}
        if resource["metadata"]:
            import json

            metadata = json.loads(resource["metadata"])

        try:
            with UnifyAPIClient(api_key=unify_pat) as client:
                if resource_type == "cloudbees_component":
                    # Need org_id from metadata to delete component
                    org_id = metadata.get("org_id")
                    if not org_id:
                        raise ValueError("Missing org_id in component metadata")
                    client.delete_component(org_id, resource_ref)  # type: ignore[attr-defined]
                    logger.info(f"Deleted CloudBees component {resource_ref}")

                elif resource_type == "cloudbees_environment":
                    # Need org_id from metadata to delete environment
                    org_id = metadata.get("org_id")
                    if not org_id:
                        raise ValueError("Missing org_id in environment metadata")
                    client.delete_environment(org_id, resource_ref)  # type: ignore[attr-defined]
                    logger.info(f"Deleted CloudBees environment {resource_ref}")

                elif resource_type == "cloudbees_application":
                    # Need org_id from metadata to delete application
                    org_id = metadata.get("org_id")
                    if not org_id:
                        raise ValueError("Missing org_id in application metadata")
                    client.delete_application(org_id, resource_ref)  # type: ignore[attr-defined]
                    logger.info(f"Deleted CloudBees application {resource_ref}")

                elif resource_type == "cloudbees_flag":
                    # Feature flags are shared resources and should NOT be cleaned up
                    logger.info(
                        f"Skipping cleanup of CloudBees flag {resource_ref} (shared resource)"
                    )
                    return

                else:
                    raise ValueError(
                        f"Unknown CloudBees resource type: {resource_type}"
                    )

        except UnifyAPIError as e:
            # Handle "Not Found" errors gracefully - resource might already be deleted
            if "not found" in str(e).lower() or "404" in str(e):
                logger.info(
                    f"CloudBees resource {resource_ref} already deleted or not found"
                )
                return
            raise

    async def cleanup_session(self, session_id: str, user_email: str) -> dict[str, Any]:
        """Clean up all resources in a session.

        Args:
            session_id: The session ID to clean up
            user_email: The email of the user requesting cleanup

        Returns:
            Cleanup summary with success/failure counts
        """
        # Verify session ownership
        session = await self.db.fetchone(
            "SELECT * FROM resource_sessions WHERE id = ? AND email = ?",
            (session_id, user_email),
        )

        if not session:
            raise ValueError(
                f"Session {session_id} not found or not owned by {user_email}"
            )

        # Get all active resources in this session
        resources = await self.db.get_session_resources(session_id)

        results = {
            "session_id": session_id,
            "total_resources": len(resources),
            "successful": 0,
            "failed": 0,
            "errors": [],
            "session_deleted": False,
        }

        for resource in resources:
            try:
                # Only mark as deleted AFTER successful cleanup
                await self.cleanup_single_resource(resource["id"], user_email)
                # If we get here, cleanup was successful
                await self.db.mark_resource_deleted(resource["id"])
                results["successful"] += 1
            except Exception as e:
                error_msg = f"Failed to cleanup {resource['resource_type']} {resource['resource_name']}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                # Only mark as failed, don't mark as deleted
                await self.db.mark_resource_failed(resource["id"])
                results["failed"] += 1

        logger.info(
            f"Session {session_id} cleanup completed: {results['successful']} successful, {results['failed']} failed"
        )

        # If all resources were successfully deleted, mark the session as deleted
        if results["successful"] > 0 and results["failed"] == 0:
            try:
                await self.db.mark_session_deleted(session_id)
                logger.info(f"Marked session {session_id} as deleted")
                results["session_deleted"] = True
            except Exception as e:
                logger.error(f"Failed to mark session {session_id} as deleted: {e}")
                results["session_deleted"] = False

        return results

    async def mark_expired_resources(self) -> int:
        """Stage 1: Mark resources in expired sessions for deletion.

        Returns:
            Number of resources marked for deletion
        """
        count = await self.db.mark_resources_for_deletion()
        if count > 0:
            logger.info(f"Marked {count} resources for deletion (expired sessions)")
        return count

    async def process_pending_deletions(self) -> dict[str, Any]:
        """Stage 2: Process resources marked for deletion.

        Returns:
            Summary of cleanup results
        """
        resources = await self.db.get_resources_pending_deletion()

        results = {
            "total_resources": len(resources),
            "successful": 0,
            "failed": 0,
            "no_valid_pat": 0,
            "errors": [],
        }

        for resource in resources:
            try:
                await self.cleanup_single_resource(resource["id"], resource["email"])
                await self.db.mark_resource_deleted(resource["id"])
                results["successful"] += 1

            except NoValidPATFoundError:
                error_msg = f"No valid PAT for {resource['email']}: {resource['resource_type']} {resource['resource_name']}"
                logger.warning(error_msg)
                results["errors"].append(error_msg)
                await self.db.mark_resource_failed(resource["id"])
                results["no_valid_pat"] += 1

            except Exception as e:
                error_msg = f"Cleanup failed for {resource['resource_type']} {resource['resource_name']}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                # Resource remains 'delete_pending' to be retried on the next run
                results["failed"] += 1

        logger.info(
            f"Processed {results['total_resources']} pending deletions: "
            f"{results['successful']} successful, {results['failed']} failed, "
            f"{results['no_valid_pat']} no valid PAT"
        )

        # Mark sessions as deleted if all their resources have been cleaned up
        await self._mark_empty_sessions_as_deleted()

        return results

    async def _mark_empty_sessions_as_deleted(self) -> None:
        """Mark sessions as deleted if all their resources have been deleted."""
        # Find sessions that have no active resources left but are still marked as active
        sessions_to_mark_deleted = await self.db.fetchall(
            """
            SELECT s.id
            FROM resource_sessions s
            LEFT JOIN resources r ON s.id = r.session_id AND r.status = 'active'
            WHERE s.status = 'active' AND r.id IS NULL
            """
        )

        for session in sessions_to_mark_deleted:
            try:
                await self.db.mark_session_deleted(session["id"])
                logger.info(f"Marked empty session {session['id']} as deleted")
            except Exception as e:
                logger.error(f"Failed to mark session {session['id']} as deleted: {e}")


# Global cleanup service instance
_cleanup_service = None


def get_cleanup_service() -> CleanupService:
    """Get the global cleanup service instance."""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = CleanupService()
    return _cleanup_service
