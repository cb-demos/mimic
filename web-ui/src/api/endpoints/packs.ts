/**
 * Scenario Pack API endpoints
 */

import { apiClient } from '../client';
import type {
  ScenarioPackListResponse,
  AddScenarioPackRequest,
  UpdatePacksRequest,
  UpdatePacksResponse,
  EnablePackRequest,
  StatusResponse,
} from '../../types/api';

/**
 * List all scenario packs
 */
export async function listPacks(): Promise<ScenarioPackListResponse> {
  const response = await apiClient.get<ScenarioPackListResponse>('/api/packs');
  return response.data;
}

/**
 * Add a new scenario pack
 */
export async function addPack(request: AddScenarioPackRequest): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>('/api/packs/add', request);
  return response.data;
}

/**
 * Remove a scenario pack
 */
export async function removePack(packName: string): Promise<StatusResponse> {
  const response = await apiClient.delete<StatusResponse>(`/api/packs/${packName}`);
  return response.data;
}

/**
 * Enable or disable a scenario pack
 */
export async function togglePack(packName: string, request: EnablePackRequest): Promise<StatusResponse> {
  const response = await apiClient.patch<StatusResponse>(`/api/packs/${packName}/enable`, request);
  return response.data;
}

/**
 * Update scenario packs via git pull
 */
export async function updatePacks(request?: UpdatePacksRequest): Promise<UpdatePacksResponse> {
  const response = await apiClient.post<UpdatePacksResponse>('/api/packs/update', request);
  return response.data;
}

// ==================== Convenience Wrappers ====================

/**
 * List packs - convenience alias
 */
export const list = listPacks;

/**
 * Add pack - convenience wrapper
 */
export async function add(name: string, git_url: string): Promise<StatusResponse> {
  return addPack({ name, git_url });
}

/**
 * Remove pack - convenience alias
 */
export const remove = removePack;

/**
 * Set pack enabled status - convenience wrapper
 */
export async function setEnabled(packName: string, enabled: boolean): Promise<StatusResponse> {
  return togglePack(packName, { enabled });
}

/**
 * Update packs - convenience wrapper
 */
export async function update(packName?: string): Promise<UpdatePacksResponse> {
  return updatePacks(packName ? { pack_name: packName } : {});
}
