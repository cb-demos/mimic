"""Event broadcasting system for real-time progress updates via SSE."""

import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Broadcasts progress events to connected SSE clients.

    This broadcaster manages subscriptions by session_id and allows
    the CreationPipeline to emit events that are streamed to connected
    clients in real-time.

    Example:
        # Pipeline emits events during execution
        await broadcaster.broadcast(session_id, {
            "event": "task_progress",
            "data": {"task_id": "repositories", "current": 3, "total": 10}
        })

        # Clients subscribe to receive events
        queue = broadcaster.subscribe(session_id)
        event = await queue.get()
    """

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """Subscribe to events for a specific session.

        Args:
            session_id: The session ID to subscribe to

        Returns:
            An asyncio.Queue that will receive events for this session
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[session_id].append(queue)
        logger.debug(f"New subscription for session {session_id}")
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """Unsubscribe from session events.

        Args:
            session_id: The session ID to unsubscribe from
            queue: The queue to remove
        """
        async with self._lock:
            if session_id in self._subscribers:
                try:
                    self._subscribers[session_id].remove(queue)
                    if not self._subscribers[session_id]:
                        del self._subscribers[session_id]
                    logger.debug(f"Unsubscribed from session {session_id}")
                except ValueError:
                    pass  # Queue already removed

    async def broadcast(self, session_id: str, event: dict[str, Any]):
        """Broadcast an event to all subscribers of a session.

        Args:
            session_id: The session ID to broadcast to
            event: The event dictionary with 'event' and 'data' keys
        """
        async with self._lock:
            subscribers = self._subscribers.get(session_id, [])
            if not subscribers:
                logger.debug(f"No subscribers for session {session_id}, event dropped")
                return

            logger.debug(
                f"Broadcasting {event.get('event')} to {len(subscribers)} subscribers"
            )

            # Put event in all subscriber queues
            for queue in subscribers:
                try:
                    # Use put_nowait to avoid blocking if queue is full
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(
                        f"Queue full for session {session_id}, dropping event"
                    )

    def get_subscriber_count(self, session_id: str) -> int:
        """Get the number of active subscribers for a session.

        Args:
            session_id: The session ID to check

        Returns:
            Number of active subscribers
        """
        return len(self._subscribers.get(session_id, []))


# Global broadcaster instance
broadcaster = EventBroadcaster()
