/**
 * TypeScript types matching backend Pydantic models
 * Generated from src/mimic/web/models.py
 */

// ==================== Common Models ====================

export interface StatusResponse {
  status: string;
  message?: string;
}

export interface ErrorResponse {
  error: string;
  detail?: string;
}

// ==================== Scenario Models ====================

export interface ScenarioListResponse {
  scenarios: Array<Record<string, any>>;
  wip_enabled: boolean;
}

export interface ScenarioDetailResponse {
  scenario: Record<string, any>;
}

export interface RunScenarioRequest {
  parameters?: Record<string, any>;
  ttl_days?: number | null;
  dry_run?: boolean;
  invitee_username?: string | null;
}

export interface RunScenarioResponse {
  session_id: string;
  status: 'running' | 'completed' | 'failed';
  message?: string;
}

export interface ValidateParametersRequest {
  parameters: Record<string, any>;
}

export interface ValidateParametersResponse {
  valid: boolean;
  errors: string[];
}

// ==================== Configuration Models ====================

export interface GitHubConfigResponse {
  username?: string;
  has_token: boolean;
}

export interface SetGitHubTokenRequest {
  token: string;
}

export interface SetGitHubUsernameRequest {
  username: string;
}

export interface CloudBeesEnvCredentials {
  name: string;
  has_token: boolean;
}

export interface CloudBeesConfigResponse {
  environments: CloudBeesEnvCredentials[];
}

export interface SetCloudBeesTokenRequest {
  environment: string;
  token: string;
}

// ==================== Environment Models ====================

export interface EnvironmentInfo {
  name: string;
  url: string;
  endpoint_id: string;
  is_current: boolean;
  is_preset: boolean;
  properties: Record<string, string>;
}

export interface EnvironmentListResponse {
  environments: EnvironmentInfo[];
  current?: string;
}

export interface AddEnvironmentRequest {
  name: string;
  url: string;
  endpoint_id: string;
  properties?: Record<string, string>;
}

export interface AddPropertyRequest {
  key: string;
  value: string;
}

export interface PropertiesResponse {
  properties: Record<string, string>;
}

// ==================== Cleanup Models ====================

export interface Resource {
  type: string;
  id: string;
  name: string;
  org_id?: string;
}

export interface SessionInfo {
  session_id: string;
  instance_name: string;
  scenario_id: string;
  environment: string;
  created_at: string; // ISO datetime string
  expires_at?: string; // ISO datetime string
  is_expired: boolean;
  resource_count: number;
  resources?: Resource[]; // Optional - may be populated in detailed views
}

export interface SessionListResponse {
  sessions: SessionInfo[];
}

export interface CleanupSessionRequest {
  dry_run?: boolean;
}

export interface CleanupResult {
  resource_type: string;
  resource_id: string;
  resource_name: string;
  status: 'success' | 'error' | 'skipped';
  message?: string;
}

export interface CleanupResponse {
  cleaned_count: number;
  results: CleanupResult[];
}

// ==================== Scenario Pack Models ====================

export interface ScenarioPackInfo {
  name: string;
  git_url: string;
  enabled: boolean;
  scenario_count: number;
}

export interface ScenarioPackListResponse {
  packs: ScenarioPackInfo[];
}

export interface AddScenarioPackRequest {
  name: string;
  git_url: string;
}

export interface UpdatePacksRequest {
  pack_name?: string; // undefined = update all
}

export interface UpdatePacksResponse {
  updated: string[];
  errors: Record<string, string>;
}

export interface EnablePackRequest {
  enabled: boolean;
}

// ==================== Setup Models ====================

export interface SetupStatusResponse {
  needs_setup: boolean;
  missing_config: string[];
}

export interface RunSetupRequest {
  github_token: string;
  github_username: string;
  environment: string;
  cloudbees_token: string;
}

export interface RunSetupResponse {
  success: boolean;
  message?: string;
}

// ==================== Progress Event Models ====================

export interface ProgressEvent {
  event: 'task_start' | 'task_progress' | 'task_complete' | 'task_error' | 'scenario_complete';
  data: ProgressEventData;
}

export type ProgressEventData =
  | TaskStartData
  | TaskProgressData
  | TaskCompleteData
  | TaskErrorData
  | ScenarioCompleteData;

export interface TaskStartData {
  task_id: string;
  description: string;
  total: number;
}

export interface TaskProgressData {
  task_id: string;
  current: number;
  total: number;
  message: string;
}

export interface TaskCompleteData {
  task_id: string;
  success: boolean;
  message: string;
}

export interface TaskErrorData {
  task_id: string;
  error: string;
}

export interface ScenarioCompleteData {
  session_id: string;
  run_name: string;
  resources: Array<Record<string, any>>;
}

// ==================== Type Aliases for Page Imports ====================

/**
 * Alias for SessionInfo - used by cleanup and dashboard pages
 */
export type Session = SessionInfo;

/**
 * Alias for EnvironmentInfo - used by environment pages
 */
export type Environment = EnvironmentInfo;

/**
 * Alias for ScenarioPackInfo - used by packs page
 */
export type ScenarioPack = ScenarioPackInfo;

/**
 * Scenario object from API responses
 */
export type Scenario = Record<string, any>;

/**
 * Environment property key-value pair
 */
export interface EnvironmentProperty {
  key: string;
  value: string;
}
