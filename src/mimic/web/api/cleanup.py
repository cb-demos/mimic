"""API endpoints for cleanup management."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from mimic.cleanup_manager import CleanupManager, is_conditional, keep_reason
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


def _to_cleanup_results(
    result: dict, session_id: str | None = None
) -> list[CleanupResult]:
    """Convert a CleanupManager.cleanup_session result into API results."""
    out: list[CleanupResult] = []
    for item in result.get("cleaned", []):
        already_gone = bool(item.get("already_gone"))
        out.append(
            CleanupResult(
                resource_type=item.get("type", "unknown"),
                resource_id=item.get("id", ""),
                resource_name=item.get("name", ""),
                status="success",
                message="Already gone (removed outside mimic)"
                if already_gone
                else item.get("message"),
                already_gone=already_gone,
                session_id=session_id,
            )
        )
    for item in result.get("errors", []):
        out.append(
            CleanupResult(
                resource_type=item.get("type", "unknown"),
                resource_id=item.get("id", ""),
                resource_name=item.get("name", ""),
                status="error",
                message=item.get("error"),
                session_id=session_id,
            )
        )
    for item in result.get("skipped", []):
        out.append(
            CleanupResult(
                resource_type=item.get("type", "unknown"),
                resource_id=item.get("id", ""),
                resource_name=item.get("name", ""),
                status="skipped",
                message=item.get("reason"),
                session_id=session_id,
            )
        )
    return out


def _to_cleanup_response(
    results: list[CleanupResult], dry_run: bool
) -> CleanupResponse:
    """Build a CleanupResponse with accurate outcome counts."""
    success = [r for r in results if r.status == "success"]
    already_gone = sum(1 for r in success if r.already_gone)
    return CleanupResponse(
        cleaned_count=len(success),
        deleted_count=len(success) - already_gone,
        already_gone_count=already_gone,
        kept_count=sum(1 for r in results if r.status == "skipped"),
        failed_count=sum(1 for r in results if r.status == "error"),
        dry_run=dry_run,
        results=results,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    config: ConfigDep,
    tenant: str | None = Query(None, description="Filter by tenant"),
    expired_only: bool = Query(False, description="Show only expired sessions"),
):
    """List sessions/instances for cleanup.

    Args:
        config: Config manager dependency
        tenant: Optional tenant filter
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

    # Filter by tenant if specified
    if tenant:
        instances = [i for i in instances if i.tenant == tenant]

    # Convert to SessionInfo
    now = datetime.now()
    sessions = []

    for instance in instances:
        is_expired = instance.expires_at is not None and instance.expires_at < now

        # Get base URL and org slug for this instance's tenant
        api_url = config.get_tenant_url(instance.tenant)
        ui_url = config.get_tenant_ui_url(instance.tenant)
        org_slug = config.get_tenant_org_slug(instance.tenant)

        # Determine the base URL to use (custom UI URL or derived from API URL)
        base_url = None
        if ui_url:
            # Use custom UI URL (e.g., https://ui.demo1.cloudbees.io)
            base_url = ui_url
        elif api_url:
            # Convert API URL to UI URL: https://api.cloudbees.io -> https://cloudbees.io
            base_url = api_url.replace("//api.", "//")

        # Build resources list
        resources = []

        # Add repositories
        for repo in instance.repositories:
            resources.append(
                Resource(
                    type="repository",
                    id=repo.id,
                    name=repo.name,
                    org_id=None,
                    url=repo.get_url(),
                    existed=repo.existed,
                    kept_reason=keep_reason("github_repo", repo),
                )
            )

        # Add components
        for comp in instance.components:
            resources.append(
                Resource(
                    type="component",
                    id=comp.id,
                    name=comp.name,
                    org_id=comp.org_id,
                    url=comp.get_url(base_url, org_slug)
                    if (base_url and org_slug)
                    else None,
                    existed=comp.existed,
                    kept_reason=keep_reason("cloudbees_component", comp),
                )
            )

        # Add environments
        for env in instance.environments:
            resources.append(
                Resource(
                    type="environment",
                    id=env.id,
                    name=env.name,
                    org_id=env.org_id,
                    url=env.get_url(base_url, org_slug)
                    if (base_url and org_slug)
                    else None,
                    existed=env.existed,
                    kept_reason=keep_reason("cloudbees_environment", env),
                )
            )

        # Add flags
        for flag in instance.flags:
            resources.append(
                Resource(
                    type="flag",
                    id=flag.id,
                    name=flag.name,
                    org_id=flag.org_id,
                    url=flag.get_url(base_url, org_slug)
                    if (base_url and org_slug)
                    else None,
                    kept_reason=keep_reason("cloudbees_flag", flag, instance),
                )
            )

        # Add applications
        for app in instance.applications:
            resources.append(
                Resource(
                    type="application",
                    id=app.id,
                    name=app.name,
                    org_id=app.org_id,
                    url=app.get_url(base_url, org_slug)
                    if (base_url and org_slug)
                    else None,
                    existed=app.existed,
                    kept_reason=keep_reason("cloudbees_application", app),
                )
            )

        for r in resources:
            r.conditional = is_conditional(r.kept_reason)

        sessions.append(
            SessionInfo(
                session_id=instance.id,
                instance_name=instance.name,
                scenario_id=instance.scenario_id,
                tenant=instance.tenant,
                created_at=instance.created_at,
                expires_at=instance.expires_at,
                is_expired=is_expired,
                status=instance.status,
                resource_count=len(resources),
                delete_count=sum(1 for r in resources if r.kept_reason is None),
                conditional_count=sum(
                    1 for r in resources if is_conditional(r.kept_reason)
                ),
                keep_count=sum(
                    1
                    for r in resources
                    if r.kept_reason is not None and not is_conditional(r.kept_reason)
                ),
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

        return _to_cleanup_response(_to_cleanup_results(result), request.dry_run)

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

    all_results: list[CleanupResult] = []

    for instance in expired_instances:
        try:
            result = await cleanup_manager.cleanup_session(
                session_id=instance.id,
                dry_run=request.dry_run,
            )
            all_results.extend(_to_cleanup_results(result, session_id=instance.id))
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
                    session_id=instance.id,
                )
            )

    return _to_cleanup_response(all_results, request.dry_run)


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
    return await cleanup_session(config, request, session_id)
