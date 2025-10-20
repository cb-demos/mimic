/**
 * Configuration API endpoints
 */

import { apiClient } from '../client';
import type {
  GitHubConfigResponse,
  SetGitHubTokenRequest,
  SetGitHubUsernameRequest,
  CloudBeesConfigResponse,
  SetCloudBeesTokenRequest,
  StatusResponse,
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
