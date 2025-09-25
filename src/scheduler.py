"""Background job scheduler for automated resource cleanup."""

import logging
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .cleanup import CleanupService
from .config import settings

logger = logging.getLogger(__name__)


class CleanupScheduler:
    """Manages background cleanup jobs using APScheduler."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.cleanup_service = CleanupService()
        self._job_running = False
        self._last_run: datetime | None = None
        self._last_run_result: dict[str, Any] | None = None

    async def start(self) -> None:
        """Start the background scheduler."""
        # Get cleanup interval from settings (default 1 hour)
        interval_seconds = getattr(settings, "CLEANUP_JOB_INTERVAL", 3600)

        # Add the cleanup job
        self.scheduler.add_job(
            self._run_cleanup_job,
            IntervalTrigger(seconds=interval_seconds),
            id="resource_cleanup",
            name="Resource Cleanup Job",
            max_instances=1,  # Prevent overlapping executions
            coalesce=True,  # Combine multiple missed executions
            misfire_grace_time=300,  # 5 minutes grace period
        )

        logger.info(f"Starting cleanup scheduler with {interval_seconds}s interval")
        self.scheduler.start()

    async def stop(self) -> None:
        """Stop the background scheduler."""
        logger.info("Stopping cleanup scheduler")
        self.scheduler.shutdown(wait=True)

    async def _run_cleanup_job(self) -> None:
        """Execute the two-stage cleanup process."""
        if self._job_running:
            logger.warning("Cleanup job already running, skipping this execution")
            return

        self._job_running = True
        start_time = datetime.utcnow()

        try:
            logger.info("Starting automated cleanup job")

            # Stage 1: Mark expired resources for deletion
            marked_count = await self.cleanup_service.mark_expired_resources()

            # Stage 2: Process resources marked for deletion
            cleanup_result = await self.cleanup_service.process_pending_deletions()

            # Store results for monitoring
            self._last_run = start_time
            self._last_run_result = {
                "start_time": start_time.isoformat(),
                "duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "marked_for_deletion": marked_count,
                **cleanup_result,
            }

            logger.info(
                f"Cleanup job completed: marked {marked_count} resources, "
                f"processed {cleanup_result['total_resources']} pending deletions"
            )

        except Exception as e:
            logger.error(f"Cleanup job failed: {e}")
            self._last_run_result = {
                "start_time": start_time.isoformat(),
                "duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "error": str(e),
                "status": "failed",
            }
            # Don't raise - we don't want to crash the scheduler

        finally:
            self._job_running = False

    async def trigger_cleanup_now(self) -> dict[str, Any]:
        """Manually trigger a cleanup job (for admin endpoints)."""
        if self._job_running:
            return {
                "status": "error",
                "message": "Cleanup job is already running",
            }

        # Run the cleanup job directly
        await self._run_cleanup_job()

        return {
            "status": "success",
            "message": "Cleanup job triggered manually",
            "result": self._last_run_result,
        }

    def get_job_status(self) -> dict[str, Any]:
        """Get current job status for monitoring."""
        job = self.scheduler.get_job("resource_cleanup")

        return {
            "scheduler_running": self.scheduler.running,
            "job_running": self._job_running,
            "job_configured": job is not None,
            "next_run_time": job.next_run_time.isoformat()
            if job and job.next_run_time
            else None,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_run_result": self._last_run_result,
            "interval_seconds": getattr(settings, "CLEANUP_JOB_INTERVAL", 3600),
        }


# Global scheduler instance
_scheduler: CleanupScheduler | None = None


def get_scheduler() -> CleanupScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = CleanupScheduler()
    return _scheduler


async def start_scheduler() -> None:
    """Start the global scheduler (called on app startup)."""
    scheduler = get_scheduler()
    await scheduler.start()


async def stop_scheduler() -> None:
    """Stop the global scheduler (called on app shutdown)."""
    scheduler = get_scheduler()
    await scheduler.stop()
