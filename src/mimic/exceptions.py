"""Custom exceptions for Mimic application.

This module provides a hierarchical exception structure to improve
error handling consistency across the application.
"""

from typing import Any


class MimicError(Exception):
    """Base exception for all Mimic operations."""

    pass


class PipelineError(MimicError):
    """Pipeline execution failures."""

    def __init__(self, message: str, step: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.step = step
        self.details = details or {}


class ValidationError(MimicError):
    """Parameter validation failures."""

    def __init__(self, message: str, field: str | None = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value


class ScenarioError(MimicError):
    """Scenario loading and processing errors."""

    def __init__(self, message: str, scenario_id: str | None = None):
        super().__init__(message)
        self.scenario_id = scenario_id


class GitHubError(MimicError):
    """GitHub API and operations errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class UnifyAPIError(MimicError):
    """CloudBees Unify API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class CredentialError(MimicError):
    """Credential validation errors."""

    def __init__(
        self,
        message: str,
        credential_type: str | None = None,  # 'github' or 'cloudbees'
        details: str | None = None,
    ):
        super().__init__(message)
        self.credential_type = credential_type
        self.details = details


class KeyringUnavailableError(MimicError):
    """Keyring backend is not available or not functioning.

    This error is raised when the system keyring cannot be used to store
    or retrieve credentials. Common causes include:
    - No keyring backend installed (e.g., gnome-keyring on Linux)
    - D-Bus session not configured (headless/SSH sessions)
    - Keyring daemon not running
    """

    def __init__(self, message: str, instructions: str | None = None):
        super().__init__(message)
        self.instructions = instructions
