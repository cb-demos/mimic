"""Centralized error handling for FastAPI."""

import logging
import re
import traceback
import uuid
from datetime import UTC, datetime

from fastapi import Request, status
from fastapi.responses import JSONResponse

from mimic.exceptions import (
    CredentialError,
    GitHubError,
    KeyringUnavailableError,
    PipelineError,
    ScenarioError,
    UnifyAPIError,
    ValidationError,
)

from .models import ErrorCode, ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def sanitize_error_message(message: str) -> str:
    """Sanitize error messages to prevent information disclosure.

    Removes potential tokens, API keys, and other sensitive information
    that might be present in error messages from external APIs.

    Args:
        message: Raw error message that may contain sensitive data

    Returns:
        Sanitized error message safe for client consumption
    """
    # Patterns to detect and remove sensitive information
    patterns = [
        # Bearer tokens
        (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer [REDACTED]"),
        # API keys (various formats)
        (r'api[_-]?key["\s:=]+[A-Za-z0-9\-._~+/]{20,}', "api_key=[REDACTED]"),
        # GitHub tokens (ghp_, gho_, ghs_, etc.)
        (r"gh[pousr]_[A-Za-z0-9]{36,}", "gh*_[REDACTED]"),
        # Generic tokens
        (r'token["\s:=]+[A-Za-z0-9\-._~+/]{20,}', "token=[REDACTED]"),
        # PATs (Personal Access Tokens)
        (r'pat["\s:=]+[A-Za-z0-9\-._~+/]{20,}', "pat=[REDACTED]"),
        # Authorization headers
        (r'Authorization["\s:=]+[^,\s"]+', "Authorization=[REDACTED]"),
        # Basic auth credentials
        (r"Basic\s+[A-Za-z0-9+/=]+", "Basic [REDACTED]"),
    ]

    sanitized = message
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized


def create_error_response(
    error_code: ErrorCode,
    message: str,
    details: list[ErrorDetail] | None = None,
    suggestion: str | None = None,
    request_id: str | None = None,
) -> ErrorResponse:
    """Create a standardized error response.

    Args:
        error_code: Machine-readable error code
        message: User-friendly error message
        details: Optional list of error details
        suggestion: Optional recovery suggestion
        request_id: Optional request correlation ID

    Returns:
        Structured error response
    """
    return ErrorResponse(
        error=error_code.name,
        code=error_code,
        message=message,
        details=details or [],
        suggestion=suggestion,
        request_id=request_id,
        timestamp=datetime.now(UTC).isoformat(),
    )


def get_request_id(request: Request) -> str:
    """Get or generate request ID from request."""
    # Check if request has a state attribute with request_id
    if hasattr(request.state, "request_id"):
        return request.state.request_id
    # Otherwise generate a new one
    return str(uuid.uuid4())


async def handle_validation_error(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle validation errors from Mimic.

    Args:
        request: FastAPI request
        exc: ValidationError exception

    Returns:
        JSON response with structured error
    """
    request_id = get_request_id(request)

    details = []
    if exc.field:
        details.append(
            ErrorDetail(
                field=exc.field,
                message=str(exc),
                code="VALIDATION_FAILED",
            )
        )

    # Provide context-specific suggestions
    error_message = str(exc)
    if "GitHub App integration" in error_message:
        suggestion = (
            "Go to your CloudBees organization integrations page and add a "
            "GitHub App integration for this organization."
        )
    else:
        suggestion = "Please check your input parameters and try again."

    error_response = create_error_response(
        ErrorCode.VALIDATION_ERROR,
        f"Validation failed: {str(exc)}",
        details=details,
        suggestion=suggestion,
        request_id=request_id,
    )

    logger.warning(
        f"Validation error [{request_id}]: {exc}",
        extra={
            "request_id": request_id,
            "field": exc.field,
            "value": exc.value,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.model_dump(),
    )


def get_pipeline_error_suggestion(step: str) -> str:
    """Get recovery suggestion based on pipeline step.

    Args:
        step: Pipeline step that failed

    Returns:
        User-friendly recovery suggestion
    """
    suggestions = {
        "repository_creation": "Check your GitHub credentials and organization permissions. Ensure the GitHub App integration is configured in CloudBees.",
        "component_creation": "Verify your CloudBees organization access and endpoint configuration. Ensure the repositories were created successfully.",
        "environment_creation": "Ensure your CloudBees organization has permission to create environments. Check your PAT scopes.",
        "flag_creation": "Verify that the application was created successfully and you have permission to manage feature flags.",
        "flag_configuration": "Check that the application and environments were created successfully. Ensure flag definitions are valid.",
        "application_creation": "Verify that components and environments exist. Check your CloudBees organization permissions.",
    }
    return suggestions.get(
        step, "Please review your configuration and try again. Check logs for details."
    )


async def handle_pipeline_error(request: Request, exc: PipelineError) -> JSONResponse:
    """Handle pipeline execution errors.

    Args:
        request: FastAPI request
        exc: PipelineError exception

    Returns:
        JSON response with structured error
    """
    request_id = get_request_id(request)

    # Map pipeline step to user-friendly message
    step_messages = {
        "repository_creation": "Failed to create GitHub repositories",
        "component_creation": "Failed to create CloudBees components",
        "environment_creation": "Failed to create environments",
        "flag_creation": "Failed to define feature flags",
        "flag_configuration": "Failed to configure feature flags",
        "application_creation": "Failed to create applications",
    }

    user_message = step_messages.get(exc.step, f"Pipeline failed at step: {exc.step}")

    error_response = create_error_response(
        ErrorCode.PIPELINE_ERROR,
        user_message,
        details=[ErrorDetail(message=str(exc), code=f"STEP_{exc.step.upper()}")],
        suggestion=get_pipeline_error_suggestion(exc.step),
        request_id=request_id,
    )

    logger.error(
        f"Pipeline error [{request_id}]: {exc}",
        extra={
            "request_id": request_id,
            "step": exc.step,
            "details": exc.details,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )


async def handle_github_error(request: Request, exc: GitHubError) -> JSONResponse:
    """Handle GitHub API errors.

    Args:
        request: FastAPI request
        exc: GitHubError exception

    Returns:
        JSON response with structured error
    """
    request_id = get_request_id(request)

    # Map status codes to user-friendly messages
    status_messages: dict[int, str] = {
        401: "Your GitHub token is invalid or has expired.",
        403: "You don't have permission to perform this action on GitHub.",
        404: "The GitHub repository or organization was not found.",
        422: "The GitHub API request was invalid.",
    }

    # Map status codes to suggestions
    status_suggestions: dict[int, str] = {
        401: "Please update your GitHub token in the Config page.",
        403: "Check your GitHub token scopes and repository permissions.",
        404: "Verify the repository name and organization, then try again.",
        422: "Check your parameters and ensure they meet GitHub's requirements.",
    }

    default_message = f"GitHub API error: {str(exc)}"
    message = (
        status_messages.get(exc.status_code, default_message)
        if exc.status_code
        else default_message
    )

    default_suggestion = "Check your GitHub credentials and try again."
    suggestion = (
        status_suggestions.get(exc.status_code, default_suggestion)
        if exc.status_code
        else default_suggestion
    )

    # Sanitize the exception message to prevent information disclosure
    sanitized_exc_message = sanitize_error_message(str(exc))

    error_response = create_error_response(
        ErrorCode.GITHUB_API_ERROR,
        message,
        details=[
            ErrorDetail(
                message=sanitized_exc_message,
                code=f"GITHUB_{exc.status_code}" if exc.status_code else None,
            )
        ],
        suggestion=suggestion,
        request_id=request_id,
    )

    logger.error(
        f"GitHub API error [{request_id}]: {exc}",
        extra={
            "request_id": request_id,
            "status_code": exc.status_code,
            "response_text": exc.response_text,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=error_response.model_dump(),
    )


async def handle_unify_error(request: Request, exc: UnifyAPIError) -> JSONResponse:
    """Handle CloudBees Unify API errors.

    Args:
        request: FastAPI request
        exc: UnifyAPIError exception

    Returns:
        JSON response with structured error
    """
    request_id = get_request_id(request)

    # Map status codes to user-friendly messages
    status_messages: dict[int, str] = {
        401: "Your CloudBees PAT is invalid or has expired.",
        403: "You don't have permission in this CloudBees organization.",
        404: "The CloudBees resource was not found.",
        422: "The CloudBees API request was invalid.",
    }

    # Map status codes to suggestions
    status_suggestions: dict[int, str] = {
        401: "Please update your CloudBees PAT in the Config page.",
        403: "Contact your CloudBees organization admin for access.",
        404: "Verify the organization ID and resource identifiers.",
        422: "Check your parameters and ensure they meet CloudBees requirements.",
    }

    default_message = f"CloudBees API error: {str(exc)}"
    message = (
        status_messages.get(exc.status_code, default_message)
        if exc.status_code
        else default_message
    )

    default_suggestion = "Check your CloudBees credentials and organization access."
    suggestion = (
        status_suggestions.get(exc.status_code, default_suggestion)
        if exc.status_code
        else default_suggestion
    )

    # Sanitize the exception message to prevent information disclosure
    sanitized_exc_message = sanitize_error_message(str(exc))

    error_response = create_error_response(
        ErrorCode.CLOUDBEES_API_ERROR,
        message,
        details=[
            ErrorDetail(
                message=sanitized_exc_message,
                code=f"CLOUDBEES_{exc.status_code}" if exc.status_code else None,
            )
        ],
        suggestion=suggestion,
        request_id=request_id,
    )

    logger.error(
        f"CloudBees API error [{request_id}]: {exc}",
        extra={
            "request_id": request_id,
            "status_code": exc.status_code,
            "response_text": exc.response_text,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=error_response.model_dump(),
    )


async def handle_credential_error(
    request: Request, exc: CredentialError
) -> JSONResponse:
    """Handle credential validation errors.

    Args:
        request: FastAPI request
        exc: CredentialError exception

    Returns:
        JSON response with structured error
    """
    request_id = get_request_id(request)

    credential_type = exc.credential_type or "credentials"

    error_response = create_error_response(
        ErrorCode.INVALID_CREDENTIALS,
        f"Invalid {credential_type}: {str(exc)}",
        details=[ErrorDetail(message=exc.details or str(exc))],
        suggestion=f"Please check your {credential_type} in the Config page and ensure they are valid.",
        request_id=request_id,
    )

    logger.warning(
        f"Credential error [{request_id}]: {exc}",
        extra={
            "request_id": request_id,
            "credential_type": credential_type,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=error_response.model_dump(),
    )


async def handle_keyring_error(
    request: Request, exc: KeyringUnavailableError
) -> JSONResponse:
    """Handle keyring unavailable errors.

    Args:
        request: FastAPI request
        exc: KeyringUnavailableError exception

    Returns:
        JSON response with structured error
    """
    request_id = get_request_id(request)

    error_response = create_error_response(
        ErrorCode.KEYRING_UNAVAILABLE,
        "System keyring is not available",
        details=[ErrorDetail(message=str(exc))],
        suggestion=exc.instructions or "Please configure your system keyring.",
        request_id=request_id,
    )

    logger.error(
        f"Keyring unavailable [{request_id}]: {exc}",
        extra={
            "request_id": request_id,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=error_response.model_dump(),
    )


async def handle_scenario_error(request: Request, exc: ScenarioError) -> JSONResponse:
    """Handle scenario loading/processing errors.

    Args:
        request: FastAPI request
        exc: ScenarioError exception

    Returns:
        JSON response with structured error
    """
    request_id = get_request_id(request)

    error_response = create_error_response(
        ErrorCode.VALIDATION_ERROR,
        f"Scenario error: {str(exc)}",
        details=[ErrorDetail(message=str(exc))],
        suggestion="Check the scenario configuration and try again.",
        request_id=request_id,
    )

    logger.error(
        f"Scenario error [{request_id}]: {exc}",
        extra={
            "request_id": request_id,
            "scenario_id": exc.scenario_id,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.model_dump(),
    )


async def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: FastAPI request
        exc: Any exception

    Returns:
        JSON response with structured error
    """
    request_id = get_request_id(request)

    # Get stack trace for logging (but not for user)
    stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    error_response = create_error_response(
        ErrorCode.INTERNAL_ERROR,
        "An unexpected error occurred",
        details=[ErrorDetail(message=f"{type(exc).__name__}: {str(exc)}")],
        suggestion="Please try again. If the problem persists, contact support.",
        request_id=request_id,
    )

    logger.error(
        f"Unexpected error [{request_id}]: {exc}",
        extra={
            "request_id": request_id,
            "exception_type": type(exc).__name__,
            "stack_trace": stack_trace,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )
