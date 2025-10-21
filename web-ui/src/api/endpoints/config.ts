/**
 * Configuration API endpoints
 */

import { apiClient } from '../client';
import type {
  AddRecentValueRequest,
  CachedOrgsResponse,
  CloudBeesConfigResponse,
  FetchOrgNameRequest,
  FetchOrgNameResponse,
  GitHubConfigResponse,
  RecentValuesResponse,
  SetCloudBeesTokenRequest,
  SetGitHubTokenRequest,
  SetGitHubUsernameRequest,
  StatusResponse,
  ValidateAllCredentialsRequest,
  ValidateAllCredentialsResponse,
} from '../../types/api';

// ==================== GitHub Configuration ====================

/**
 * Get GitHub configuration status
 */
export async function getGitHubConfig(): Promise<GitHubConfigResponse> {
  const response = await apiClient.get<GitHubConfigResponse>('/api/config/github');
  return response.data;
}

/**
 * Set GitHub personal access token
 */
export async function setGitHubToken(request: SetGitHubTokenRequest): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>('/api/config/github/token', request);
  return response.data;
}

/**
 * Set GitHub username
 */
export async function setGitHubUsername(
  request: SetGitHubUsernameRequest
): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>('/api/config/github/username', request);
  return response.data;
}

// ==================== CloudBees Configuration ====================

/**
 * Get CloudBees configuration status for all environments
 */
export async function getCloudBeesConfig(): Promise<CloudBeesConfigResponse> {
  const response = await apiClient.get<CloudBeesConfigResponse>('/api/config/cloudbees');
  return response.data;
}

/**
 * Set CloudBees PAT for a specific environment
 */
export async function setCloudBeesToken(
  request: SetCloudBeesTokenRequest
): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>('/api/config/cloudbees/token', request);
  return response.data;
}

// ==================== Convenience Wrappers ====================

/**
 * Get GitHub config - convenience alias
 */
export const getGithub = getGitHubConfig;

/**
 * Get CloudBees config - convenience alias
 */
export const getCloudbees = getCloudBeesConfig;

/**
 * Set GitHub token - convenience wrapper
 */
export async function setGithubToken(token: string): Promise<StatusResponse> {
  return setGitHubToken({ token });
}

/**
 * Set GitHub username - convenience wrapper
 */
export async function setGithubUsername(username: string): Promise<StatusResponse> {
  return setGitHubUsername({ username });
}

/**
 * Set CloudBees token - convenience wrapper
 */
export async function setCloubeesToken(environment: string, token: string): Promise<StatusResponse> {
  return setCloudBeesToken({ environment, token });
}

// ==================== Recent Values ====================

/**
 * Get recent values for a category
 */
export async function getRecentValues(category: string): Promise<RecentValuesResponse> {
  const response = await apiClient.get<RecentValuesResponse>(`/api/config/recent/${category}`);
  return response.data;
}

/**
 * Add a recent value to a category
 */
export async function addRecentValue(category: string, value: string): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>(
    `/api/config/recent/${category}`,
    { value } as AddRecentValueRequest
  );
  return response.data;
}

// ==================== CloudBees Organizations ====================

/**
 * Get cached CloudBees organizations for current environment
 */
export async function getCachedOrgs(): Promise<CachedOrgsResponse> {
  const response = await apiClient.get<CachedOrgsResponse>('/api/config/cloudbees-orgs');
  return response.data;
}

/**
 * Fetch organization name from API and cache it
 */
export async function fetchOrgName(orgId: string): Promise<FetchOrgNameResponse> {
  const response = await apiClient.post<FetchOrgNameResponse>(
    '/api/config/cloudbees-orgs/fetch',
    { org_id: orgId } as FetchOrgNameRequest
  );
  return response.data;
}

// ==================== Credential Validation ====================

/**
 * Validate both CloudBees and GitHub credentials
 */
export async function validateAllCredentials(
  request: ValidateAllCredentialsRequest
): Promise<ValidateAllCredentialsResponse> {
  const response = await apiClient.post<ValidateAllCredentialsResponse>(
    '/api/config/validate-all-credentials',
    request
  );
  return response.data;
}
