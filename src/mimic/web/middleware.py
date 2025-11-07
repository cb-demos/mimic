"""Middleware for request tracking and context management."""

import logging
import re
import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Context variable for request ID (accessible throughout request lifecycle)
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def validate_request_id(request_id: str | None) -> str:
    """Validate and sanitize client-provided request ID.

    Protects against log injection and ensures request IDs are safe to use.
    Only accepts alphanumeric characters, hyphens, and underscores, with a
    maximum length of 64 characters.

    Args:
        request_id: Request ID from client header (may be None)

    Returns:
        Valid request ID (either sanitized client value or generated UUID)
    """
    if not request_id:
        return str(uuid.uuid4())

    # Check length (prevent excessive memory usage)
    if len(request_id) > 64:
        logger.warning(
            f"Request ID too long ({len(request_id)} chars), generating new one"
        )
        return str(uuid.uuid4())

    # Validate format: alphanumeric, hyphens, underscores only
    # This prevents log injection and other special character attacks
    if not re.match(r"^[a-zA-Z0-9\-_]+$", request_id):
        logger.warning(
            f"Request ID contains invalid characters, generating new one: {request_id[:50]}"
        )
        return str(uuid.uuid4())

    return request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID and log request/response."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """Process request and add tracking.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response with added headers
        """
        # Validate and sanitize request ID from header (or generate new one)
        client_request_id = request.headers.get("X-Request-ID")
        request_id = validate_request_id(client_request_id)

        # Store in context var for access in handlers
        request_id_var.set(request_id)

        # Also store in request state for direct access
        request.state.request_id = request_id

        # Log request start
        start_time = time.time()
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )

        try:
            # Process request
            response = await call_next(request)

            # Log successful response
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Request completed: {response.status_code}",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Add timing header
            response.headers["X-Response-Time"] = f"{duration_ms}ms"

            return response

        except Exception as e:
            # Log failed request
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"Request failed: {e}",
                extra={
                    "request_id": request_id,
                    "duration_ms": duration_ms,
                    "exception_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise
