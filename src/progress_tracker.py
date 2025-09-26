"""Real-time progress tracking for scenario execution."""

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProgressEventType(str, Enum):
    """Types of progress events."""
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    LOG_MESSAGE = "log_message"
    SCENARIO_COMPLETED = "scenario_completed"
    SCENARIO_FAILED = "scenario_failed"


class ProgressStep(str, Enum):
    """Scenario execution steps."""
    INITIALIZATION = "initialization"
    REPOSITORY_CREATION = "repository_creation"
    COMPONENT_CREATION = "component_creation"
    FLAG_CREATION = "flag_creation"
    ENVIRONMENT_CREATION = "environment_creation"
    APPLICATION_CREATION = "application_creation"
    FLAG_CONFIGURATION = "flag_configuration"
    ENVIRONMENT_FM_TOKEN_UPDATE = "environment_fm_token_update"


class ProgressEvent(BaseModel):
    """A progress event in the scenario execution."""
    event_type: ProgressEventType
    step: Optional[ProgressStep] = None
    message: str
    timestamp: str
    percentage: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class ProgressTracker:
    """Manages real-time progress tracking for scenario execution."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events_queue: asyncio.Queue = asyncio.Queue()
        self.current_step = ProgressStep.INITIALIZATION
        self.step_percentages = {
            ProgressStep.INITIALIZATION: 5,
            ProgressStep.REPOSITORY_CREATION: 20,
            ProgressStep.COMPONENT_CREATION: 35,
            ProgressStep.FLAG_CREATION: 45,
            ProgressStep.ENVIRONMENT_CREATION: 60,
            ProgressStep.APPLICATION_CREATION: 80,
            ProgressStep.ENVIRONMENT_FM_TOKEN_UPDATE: 90,
            ProgressStep.FLAG_CONFIGURATION: 100,
        }
        self.completed_steps = set()

    def _calculate_percentage(self, step: ProgressStep) -> int:
        """Calculate overall completion percentage for a step."""
        return self.step_percentages.get(step, 0)

    def _create_event(
        self,
        event_type: ProgressEventType,
        message: str,
        step: Optional[ProgressStep] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ProgressEvent:
        """Create a progress event."""
        percentage = None
        if step and event_type in [ProgressEventType.STEP_STARTED, ProgressEventType.STEP_COMPLETED]:
            percentage = self._calculate_percentage(step)

        return ProgressEvent(
            event_type=event_type,
            step=step,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            percentage=percentage,
            details=details,
        )

    async def _emit_event(self, event: ProgressEvent) -> None:
        """Emit a progress event to the queue."""
        try:
            await self.events_queue.put(event)
            logger.debug(f"Progress event emitted for {self.session_id}: {event.event_type} - {event.message}")
        except Exception as e:
            logger.error(f"Failed to emit progress event: {e}")

    async def start_step(self, step: ProgressStep, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Mark a step as started."""
        self.current_step = step
        event = self._create_event(ProgressEventType.STEP_STARTED, message, step, details)
        await self._emit_event(event)

    async def complete_step(self, step: ProgressStep, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Mark a step as completed."""
        self.completed_steps.add(step)
        event = self._create_event(ProgressEventType.STEP_COMPLETED, message, step, details)
        await self._emit_event(event)

    async def fail_step(self, step: ProgressStep, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Mark a step as failed."""
        event = self._create_event(ProgressEventType.STEP_FAILED, message, step, details)
        await self._emit_event(event)

    async def log_message(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Emit a log message."""
        event = self._create_event(ProgressEventType.LOG_MESSAGE, message, self.current_step, details)
        await self._emit_event(event)

    async def complete_scenario(self, message: str, summary: Optional[Dict[str, Any]] = None) -> None:
        """Mark the entire scenario as completed."""
        event = self._create_event(ProgressEventType.SCENARIO_COMPLETED, message, details=summary)
        await self._emit_event(event)

    async def fail_scenario(self, message: str, error_details: Optional[Dict[str, Any]] = None) -> None:
        """Mark the entire scenario as failed."""
        event = self._create_event(ProgressEventType.SCENARIO_FAILED, message, details=error_details)
        await self._emit_event(event)

    async def get_events_stream(self):
        """Generator that yields progress events as they occur."""
        logger.info(f"Starting events stream for session {self.session_id}")

        # Send initial connection event
        initial_event = self._create_event(
            ProgressEventType.LOG_MESSAGE,
            "Progress tracking connected"
        )
        yield f"data: {initial_event.model_dump_json()}\n\n"

        while True:
            try:
                # Wait for next event with timeout
                event = await asyncio.wait_for(self.events_queue.get(), timeout=30.0)

                logger.info(f"Streaming event for {self.session_id}: {event.event_type} - {event.message}")

                # Format as Server-Sent Events
                event_data = event.model_dump_json()
                yield f"data: {event_data}\n\n"

                # Break if scenario is complete or failed
                if event.event_type in [ProgressEventType.SCENARIO_COMPLETED, ProgressEventType.SCENARIO_FAILED]:
                    logger.info(f"Scenario finished for {self.session_id}, ending stream")
                    break

            except asyncio.TimeoutError:
                # Send keep-alive event
                logger.debug(f"Sending keep-alive for {self.session_id}")
                yield "data: {\"event_type\": \"keep_alive\", \"message\": \"Connection active\"}\n\n"
            except Exception as e:
                logger.error(f"Error in events stream for {self.session_id}: {e}")
                error_event = self._create_event(
                    ProgressEventType.SCENARIO_FAILED,
                    f"Progress tracking error: {str(e)}"
                )
                yield f"data: {error_event.model_dump_json()}\n\n"
                break

        logger.info(f"Events stream ended for session {self.session_id}")


# Global registry of progress trackers by session ID
_progress_trackers: Dict[str, ProgressTracker] = {}


def create_progress_tracker(session_id: str) -> ProgressTracker:
    """Create and register a new progress tracker for a session."""
    tracker = ProgressTracker(session_id)
    _progress_trackers[session_id] = tracker
    logger.info(f"Created progress tracker for session {session_id}. Total trackers: {len(_progress_trackers)}")
    return tracker


def get_progress_tracker(session_id: str) -> Optional[ProgressTracker]:
    """Get an existing progress tracker for a session."""
    tracker = _progress_trackers.get(session_id)
    if tracker:
        logger.info(f"Found progress tracker for session {session_id}")
    else:
        logger.warning(f"No progress tracker found for session {session_id}. Available: {list(_progress_trackers.keys())}")
    return tracker


def cleanup_progress_tracker(session_id: str) -> None:
    """Clean up a progress tracker after scenario completion."""
    if session_id in _progress_trackers:
        del _progress_trackers[session_id]
        logger.info(f"Cleaned up progress tracker for session {session_id}")