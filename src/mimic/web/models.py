"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ==================== Common Models ====================

class StatusResponse(BaseModel):
    """Generic status response."""

    status: str
    message: str | None = None


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str | None = None


# ==================== Scenario Models ====================

class ScenarioListResponse(BaseModel):
    """Response for listing scenarios."""

    scenarios: list[dict[str, Any]]
    wip_enabled: bool


class ScenarioDetailResponse(BaseModel):
    """Response for scenario details."""

    scenario: dict[str, Any]


class RunScenarioRequest(BaseModel):
    """Request to run a scenario."""

    parameters: dict[str, Any] = Field(default_factory=dict)
    ttl_days: int | None = 7
    dry_run: bool = False
    invitee_username: str | None = None


class RunScenarioResponse(BaseModel):
    """Response after starting a scenario run."""

    session_id: str
    status: str  # "running", "completed", "failed"
    message: str | None = None


class ValidateParametersRequest(BaseModel):
    """Request to validate scenario parameters."""

    parameters: dict[str, Any]


class ValidateParametersResponse(BaseModel):
    """Response for parameter validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)


# ==================== Configuration Models ====================

class GitHubConfigResponse(BaseModel):
    """Response for GitHub configuration status."""

    username: str | None = None
    has_token: bool


class SetGitHubTokenRequest(BaseModel):
    """Request to set GitHub token."""

    token: str


class SetGitHubUsernameRequest(BaseModel):
    """Request to set GitHub username."""

    username: str


class CloudBeesEnvCredentials(BaseModel):
    """CloudBees credentials for a specific environment."""

    name: str
    has_token: bool


class CloudBeesConfigResponse(BaseModel):
    """Response for CloudBees configuration status."""

    environments: list[CloudBeesEnvCredentials]


class SetCloudBeesTokenRequest(BaseModel):
    """Request to set CloudBees token for an environment."""

    environment: str
    token: str


# ==================== Environment Models ====================

class EnvironmentInfo(BaseModel):
    """Information about a single environment."""

    name: str
    url: str
    endpoint_id: str
    is_current: bool
    is_preset: bool
    properties: dict[str, str] = Field(default_factory=dict)


class EnvironmentListResponse(BaseModel):
    """Response for listing environments."""

    environments: list[EnvironmentInfo]
    current: str | None = None


class AddEnvironmentRequest(BaseModel):
    """Request to add a custom environment."""

    name: str
    url: str
    endpoint_id: str


class AddPropertyRequest(BaseModel):
    """Request to add/update an environment property."""

    key: str
    value: str


class PropertiesResponse(BaseModel):
    """Response with environment properties."""

    properties: dict[str, str]


# ==================== Cleanup Models ====================

class SessionInfo(BaseModel):
    """Information about a session for cleanup."""

    session_id: str
    instance_name: str
    scenario_id: str
    environment: str
    created_at: datetime
    expires_at: datetime | None
    is_expired: bool
    resource_count: int


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    sessions: list[SessionInfo]


class CleanupSessionRequest(BaseModel):
    """Request to cleanup a session."""

    dry_run: bool = False


class CleanupResult(BaseModel):
    """Result of a cleanup operation."""

    resource_type: str
    resource_id: str
    resource_name: str
    status: str  # "success", "error", "skipped"
    message: str | None = None


class CleanupResponse(BaseModel):
    """Response for cleanup operations."""

    cleaned_count: int
    results: list[CleanupResult]


# ==================== Scenario Pack Models ====================

class ScenarioPackInfo(BaseModel):
    """Information about a scenario pack."""

    name: str
    git_url: str
    enabled: bool
    scenario_count: int


class ScenarioPackListResponse(BaseModel):
    """Response for listing scenario packs."""

    packs: list[ScenarioPackInfo]


class AddScenarioPackRequest(BaseModel):
    """Request to add a new scenario pack."""

    name: str
    git_url: str


class UpdatePacksRequest(BaseModel):
    """Request to update scenario packs."""

    pack_name: str | None = None  # None = update all


class UpdatePacksResponse(BaseModel):
    """Response for pack update operation."""

    updated: list[str]
    errors: dict[str, str] = Field(default_factory=dict)


class EnablePackRequest(BaseModel):
    """Request to enable/disable a pack."""

    enabled: bool


# ==================== Setup Models ====================

class SetupStatusResponse(BaseModel):
    """Response for setup status check."""

    needs_setup: bool
    missing_config: list[str] = Field(default_factory=list)


class RunSetupRequest(BaseModel):
    """Request to run initial setup."""

    github_token: str
    github_username: str
    environment: str
    cloudbees_token: str


class RunSetupResponse(BaseModel):
    """Response after running setup."""

    success: bool
    message: str | None = None
