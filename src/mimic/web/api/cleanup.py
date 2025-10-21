"""API endpoints for cleanup management."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from mimic.cleanup_manager import CleanupManager
from mimic.instance_repository import InstanceRepository

from ..dependencies import ConfigDep
from ..models import (
    CleanupResponse,
    CleanupResult,
    CleanupSessionRequest,
    Resource,
    SessionInfo,
    SessionListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cleanup", tags=["cleanup"])


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    config: ConfigDep,
    environment: str | None = Query(None, description="Filter by environment"),
    expired_only: bool = Query(False, description="Show only expired sessions"),
):
    """List sessions/instances for cleanup.

    Args:
        config: Config manager dependency
        environment: Optional environment filter
        expired_only: If True, only show expired sessions

    Returns:
        List of sessions with their metadata
    """
    repo = InstanceRepository()

    # Get instances based on filters
    if expired_only:
        instances = repo.find_expired()
    else:
        instances = repo.find_all(include_expired=True)

    # Filter by environment if specified
    if environment:
        instances = [i for i in instances if i.environment == environment]

    # Convert to SessionInfo
    now = datetime.now()
    sessions = []
    for instance in instances:
        is_expired = instance.expires_at is not None and instance.expires_at < now

        # Build resources list
        resources = []

        # Add repositories
        for repo in instance.repositories:
            resources.append(
                Resource(type="repository", id=repo.id, name=repo.name, org_id=None)
            )

        # Add components
        for comp in instance.components:
            resources.append(
                Resource(type="component", id=comp.id, name=comp.name, org_id=comp.org_id)
            )

        # Add environments
        for env in instance.environments:
            resources.append(
                Resource(type="environment", id=env.id, name=env.name, org_id=env.org_id)
            )

        # Add flags
        for flag in instance.flags:
            resources.append(
                Resource(type="flag", id=flag.id, name=flag.name, org_id=flag.org_id)
            )

        # Add applications
        for app in instance.applications:
            resources.append(
                Resource(type="application", id=app.id, name=app.name, org_id=app.org_id)
            )

        sessions.append(
            SessionInfo(
                session_id=instance.id,
                instance_name=instance.name,
                scenario_id=instance.scenario_id,
                environment=instance.environment,
                created_at=instance.created_at,
                expires_at=instance.expires_at,
                is_expired=is_expired,
                resource_count=len(resources),
                resources=resources,
            )
        )

    # Sort by creation date (newest first)
    sessions.sort(key=lambda s: s.created_at, reverse=True)

    return SessionListResponse(sessions=sessions)


@router.post("/run", response_model=CleanupResponse)
async def cleanup_session(
    config: ConfigDep,
    request: CleanupSessionRequest,
    session_id: str = Query(..., description="Session ID to clean up"),
):
    """Clean up all resources for a specific session.

    Args:
        session_id: Session ID to clean up
        request: Cleanup options (dry_run)
        config: Config manager dependency

    Returns:
        Cleanup results
    """
    cleanup_manager = CleanupManager(config_manager=config)

    try:
        result = await cleanup_manager.cleanup_session(
            session_id=session_id,
            dry_run=request.dry_run,
        )

        # Convert to API response format
        cleanup_results = []

        for item in result.get("cleaned", []):
            cleanup_results.append(
                CleanupResult(
                    resource_type=item.get("type", "unknown"),
                    resource_id=item.get("id", ""),
                    resource_name=item.get("name", ""),
                    status="success",
                    message=item.get("message"),
                )
            )

        for item in result.get("errors", []):
            cleanup_results.append(
                CleanupResult(
                    resource_type=item.get("type", "unknown"),
                    resource_id=item.get("id", ""),
                    resource_name=item.get("name", ""),
                    status="error",
                    message=item.get("error"),
                )
            )

        for item in result.get("skipped", []):
            cleanup_results.append(
                CleanupResult(
                    resource_type=item.get("type", "unknown"),
                    resource_id=item.get("id", ""),
                    resource_name=item.get("name", ""),
                    status="skipped",
                    message=item.get("reason"),
                )
            )

        cleaned_count = len(result.get("cleaned", []))

        return CleanupResponse(cleaned_count=cleaned_count, results=cleanup_results)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error cleaning up session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {str(e)}",
        ) from e


@router.post("/expired", response_model=CleanupResponse)
async def cleanup_expired(request: CleanupSessionRequest, config: ConfigDep):
    """Clean up all expired sessions.

    Args:
        request: Cleanup options (dry_run)
        config: Config manager dependency

    Returns:
        Cleanup results for all expired sessions
    """
    cleanup_manager = CleanupManager(config_manager=config)
    repo = InstanceRepository()

    expired_instances = repo.find_expired()

    all_results = []
    total_cleaned = 0

    for instance in expired_instances:
        try:
            result = await cleanup_manager.cleanup_session(
                session_id=instance.id,
                dry_run=request.dry_run,
            )

            # Convert to API response format
            for item in result.get("cleaned", []):
                all_results.append(
                    CleanupResult(
                        resource_type=item.get("type", "unknown"),
                        resource_id=item.get("id", ""),
                        resource_name=item.get("name", ""),
                        status="success",
                        message=f"[{instance.id}] {item.get('message')}",
                    )
                )
                total_cleaned += 1

            for item in result.get("errors", []):
                all_results.append(
                    CleanupResult(
                        resource_type=item.get("type", "unknown"),
                        resource_id=item.get("id", ""),
                        resource_name=item.get("name", ""),
                        status="error",
                        message=f"[{instance.id}] {item.get('error')}",
                    )
                )

        except Exception as e:
            logger.error(
                f"Error cleaning up expired session {instance.id}: {e}", exc_info=True
            )
            all_results.append(
                CleanupResult(
                    resource_type="session",
                    resource_id=instance.id,
                    resource_name=instance.name,
                    status="error",
                    message=str(e),
                )
            )

    return CleanupResponse(cleaned_count=total_cleaned, results=all_results)


@router.delete("/sessions/{session_id}", response_model=CleanupResponse)
async def delete_session(
    session_id: str, request: CleanupSessionRequest, config: ConfigDep
):
    """Delete a specific session (alias for POST /cleanup/run).

    Args:
        session_id: Session ID to delete
        request: Cleanup options (dry_run)
        config: Config manager dependency

    Returns:
        Cleanup results
    """
    # This is just an alias for cleanup_session
    return await cleanup_session(session_id, request, config)
