/**
 * API endpoints for version checking and upgrades
 */

import { apiClient } from '../client';

export interface VersionInfo {
  version: string;
  commit: string | null;
  commit_short: string | null;
  build_timestamp: string | null;
}

export interface UpdateCheckResponse {
  update_available: boolean;
  current_commit: string | null;
  current_commit_short: string | null;
  latest_commit: string | null;
  latest_commit_short: string | null;
  latest_commit_url: string | null;
  message: string;
}

export interface UpgradeResponse {
  status: string;
  message: string;
  output?: string;
}

/**
 * Get current version information
 */
export const getVersion = async (): Promise<VersionInfo> => {
  const response = await apiClient.get<VersionInfo>('/api/version');
  return response.data;
};

/**
 * Check if an update is available
 */
export const checkForUpdates = async (): Promise<UpdateCheckResponse> => {
  const response = await apiClient.get<UpdateCheckResponse>('/api/version/check');
  return response.data;
};

/**
 * Upgrade Mimic and scenario packs
 */
export const upgrade = async (): Promise<UpgradeResponse> => {
  const response = await apiClient.post<UpgradeResponse>('/api/version/upgrade');
  return response.data;
};

export const versionApi = {
  getVersion,
  checkForUpdates,
  upgrade,
};
