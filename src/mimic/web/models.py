"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ==================== Common Models ====================


class StatusResponse(BaseModel):
    """Generic status response."""

    status: str
    message: str | None = None


class ErrorCode(str, Enum):
    """Standardized error codes for the API."""

    # Validation errors (1xxx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    MISSING_REQUIRED_PROPERTY = "MISSING_REQUIRED_PROPERTY"

    # Credential errors (2xxx)
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    MISSING_CREDENTIALS = "MISSING_CREDENTIALS"
    KEYRING_UNAVAILABLE = "KEYRING_UNAVAILABLE"

    # API errors (3xxx)
    GITHUB_API_ERROR = "GITHUB_API_ERROR"
    CLOUDBEES_API_ERROR = "CLOUDBEES_API_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"

    # Pipeline errors (4xxx)
    PIPELINE_ERROR = "PIPELINE_ERROR"
    REPOSITORY_CREATION_FAILED = "REPOSITORY_CREATION_FAILED"
    COMPONENT_CREATION_FAILED = "COMPONENT_CREATION_FAILED"
    ENVIRONMENT_CREATION_FAILED = "ENVIRONMENT_CREATION_FAILED"

    # Resource errors (5xxx)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"

    # System errors (9xxx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class ErrorDetail(BaseModel):
    """Detailed error information for a specific field or issue."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """Enhanced error response with structured information."""

    error: str  # High-level error type
    code: ErrorCode  # Machine-readable error code
    message: str  # User-friendly message
    details: list[ErrorDetail] = Field(default_factory=list)  # Additional details
    suggestion: str | None = None  # Recovery suggestion
    request_id: str | None = None  # Correlation ID for tracing
    timestamp: str  # ISO timestamp


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

    organization_id: str
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


class CheckPropertiesRequest(BaseModel):
    """Request to check required properties/secrets for a scenario."""

    organization_id: str


class PropertyInfo(BaseModel):
    """Information about a property or secret."""

    name: str
    type: str  # "property" or "secret"
    exists: bool


class CheckPropertiesResponse(BaseModel):
    """Response for property check."""

    required_properties: list[str] = Field(default_factory=list)
    required_secrets: list[str] = Field(default_factory=list)
    missing_properties: list[str] = Field(default_factory=list)
    missing_secrets: list[str] = Field(default_factory=list)
    all_properties: list[PropertyInfo] = Field(default_factory=list)


class CreatePropertyRequest(BaseModel):
    """Request to create a property or secret in CloudBees organization."""

    organization_id: str
    name: str
    value: str
    is_secret: bool = False


class ScenarioPreviewRequest(BaseModel):
    """Request to preview a scenario without executing it."""

    organization_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ScenarioPreviewResponse(BaseModel):
    """Response with scenario preview."""

    preview: dict[str, Any]


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


class CloudBeesTenantCredentials(BaseModel):
    """CloudBees credentials for a specific tenant."""

    name: str
    has_token: bool


class CloudBeesConfigResponse(BaseModel):
    """Response for CloudBees configuration status."""

    tenants: list[CloudBeesTenantCredentials]


class SetCloudBeesTokenRequest(BaseModel):
    """Request to set CloudBees token for a tenant."""

    tenant: str
    token: str


class RecentValuesResponse(BaseModel):
    """Response with recent values for a category."""

    category: str
    values: list[str]


class AddRecentValueRequest(BaseModel):
    """Request to add a recent value."""

    value: str


class CachedOrg(BaseModel):
    """A cached organization with ID and display name."""

    org_id: str
    display_name: str


class CachedOrgsResponse(BaseModel):
    """Response with cached CloudBees organizations."""

    orgs: list[CachedOrg]


class FetchOrgNameRequest(BaseModel):
    """Request to fetch organization name by ID."""

    org_id: str


class FetchOrgNameResponse(BaseModel):
    """Response with organization name."""

    org_id: str
    display_name: str


# ==================== Tenant Models ====================


class TenantInfo(BaseModel):
    """Information about a single tenant."""

    name: str
    url: str
    endpoint_id: str
    is_current: bool
    is_preset: bool
    flag_api_type: str  # "org" or "app"
    properties: dict[str, str] = Field(default_factory=dict)


class TenantListResponse(BaseModel):
    """Response for listing tenants."""

    tenants: list[TenantInfo]
    current: str | None = None


class AddTenantRequest(BaseModel):
    """Request to add a custom tenant."""

    name: str
    url: str
    endpoint_id: str
    pat: str | None = None
    org_id: str | None = None
    use_legacy_flags: bool = False


class AddPropertyRequest(BaseModel):
    """Request to add/update a tenant property."""

    key: str
    value: str


class PropertiesResponse(BaseModel):
    """Response with tenant properties."""

    properties: dict[str, str]


class PresetTenantInfo(BaseModel):
    """Information about a preset tenant."""

    name: str
    url: str
    endpoint_id: str
    description: str
    flag_api_type: str  # "org" or "app"
    default_properties: dict[str, str] = Field(default_factory=dict)
    is_configured: bool  # Whether this preset has been added to config


class PresetTenantListResponse(BaseModel):
    """Response for listing preset tenants."""

    presets: list[PresetTenantInfo]


class AddPresetTenantRequest(BaseModel):
    """Request to add a preset tenant."""

    name: str
    pat: str
    org_id: str
    custom_properties: dict[str, str] = Field(default_factory=dict)


class ValidateCredentialsRequest(BaseModel):
    """Request to validate CloudBees credentials."""

    pat: str
    org_id: str
    environment_url: str


class ValidateCredentialsResponse(BaseModel):
    """Response for credential validation."""

    valid: bool
    error: str | None = None
    org_name: str | None = None


class ValidateAllCredentialsRequest(BaseModel):
    """Request to validate both CloudBees and GitHub credentials."""

    cloudbees_pat: str
    cloudbees_url: str
    organization_id: str
    github_pat: str


class CredentialValidationResult(BaseModel):
    """Result of a single credential validation."""

    valid: bool
    error: str | None = None


class ValidateAllCredentialsResponse(BaseModel):
    """Response for validating all credentials."""

    cloudbees_valid: bool
    github_valid: bool
    cloudbees_error: str | None = None
    github_error: str | None = None


# ==================== Cleanup Models ====================


class Resource(BaseModel):
    """A resource created during scenario execution."""

    type: str
    id: str
    name: str
    org_id: str | None = None
    url: str | None = None  # URL to view the resource in its respective UI


class SessionInfo(BaseModel):
    """Information about a session for cleanup."""

    session_id: str
    instance_name: str
    scenario_id: str
    tenant: str
    created_at: datetime
    expires_at: datetime | None
    is_expired: bool
    resource_count: int
    resources: list[Resource] = Field(default_factory=list)


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


class GitHubBranch(BaseModel):
    """Information about a git branch."""

    name: str
    sha: str
    protected: bool


class GitHubPullRequest(BaseModel):
    """Information about a pull request."""

    number: int
    title: str
    head_branch: str
    head_sha: str
    head_repo_url: str | None = (
        None  # Fork repository URL (None if PR is from same repo)
    )
    author: str
    state: str  # "open", "closed", "merged"
    created_at: str
    updated_at: str


class DiscoverRefsRequest(BaseModel):
    """Request to discover branches and PRs for a GitHub URL."""

    git_url: str


class DiscoverRefsResponse(BaseModel):
    """Response with available branches and PRs."""

    owner: str
    repo: str
    default_branch: str
    branches: list[GitHubBranch]
    pull_requests: list[GitHubPullRequest]
    error: str | None = None


class SwitchPackRefRequest(BaseModel):
    """Request to switch a pack to a different branch or PR."""

    branch: str | None = None
    pr_number: int | None = None


class PackRefInfo(BaseModel):
    """Current reference information for a pack."""

    type: str  # "branch" or "pr"
    branch: str
    pr_number: int | None = None
    pr_title: str | None = None
    pr_author: str | None = None
    pr_head_repo_url: str | None = None  # Fork repo URL for PRs from forks
    last_updated: str | None = None


class ScenarioPackInfo(BaseModel):
    """Information about a scenario pack."""

    name: str
    git_url: str
    enabled: bool
    scenario_count: int
    current_ref: PackRefInfo | None = None


class ScenarioPackListResponse(BaseModel):
    """Response for listing scenario packs."""

    packs: list[ScenarioPackInfo]


class AddScenarioPackRequest(BaseModel):
    """Request to add a new scenario pack."""

    name: str
    git_url: str
    branch: str = "main"
    pr_number: int | None = None
    pr_title: str | None = None
    pr_author: str | None = None
    pr_head_repo_url: str | None = None  # Fork repo URL for PRs from forks


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
    tenant: str
    cloudbees_token: str


class RunSetupResponse(BaseModel):
    """Response after running setup."""

    success: bool
    message: str | None = None
