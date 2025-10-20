/**
 * Environment API endpoints
 */

import { apiClient } from '../client';
import type {
  EnvironmentListResponse,
  AddEnvironmentRequest,
  AddPropertyRequest,
  PropertiesResponse,
  StatusResponse,
} from '../../types/api';

/**
 * List all environments with current selection
 */
export async function listEnvironments(): Promise<EnvironmentListResponse> {
  const response = await apiClient.get<EnvironmentListResponse>('/api/environments');
  return response.data;
}

/**
 * Add a custom environment
 */
export async function addEnvironment(request: AddEnvironmentRequest): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>('/api/environments', request);
  return response.data;
}

/**
 * Remove an environment
 */
export async function removeEnvironment(envName: string): Promise<StatusResponse> {
  const response = await apiClient.delete<StatusResponse>(`/api/environments/${envName}`);
  return response.data;
}

/**
 * Set an environment as current
 */
export async function selectEnvironment(envName: string): Promise<StatusResponse> {
  const response = await apiClient.patch<StatusResponse>(`/api/environments/${envName}/select`);
  return response.data;
}

/**
 * Get environment properties
 */
export async function getEnvironmentProperties(envName: string): Promise<PropertiesResponse> {
  const response = await apiClient.get<PropertiesResponse>(`/api/environments/${envName}/properties`);
  return response.data;
}

/**
 * Add/update an environment property
 */
export async function addEnvironmentProperty(
  envName: string,
  request: AddPropertyRequest
): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>(
    `/api/environments/${envName}/properties`,
    request
  );
  return response.data;
}

// ==================== Convenience Wrappers ====================

/**
 * List environments - convenience alias
 */
export const list = listEnvironments;

/**
 * Add environment - convenience wrapper
 */
export async function add(
  name: string,
  url: string,
  endpoint_id: string,
  properties: Record<string, string>
): Promise<StatusResponse> {
  return addEnvironment({ name, url, endpoint_id, properties });
}

/**
 * Remove environment - convenience alias
 */
export const remove = removeEnvironment;

/**
 * Select environment - convenience alias
 */
export const select = selectEnvironment;

/**
 * Get properties - convenience alias
 */
export const getProperties = getEnvironmentProperties;

/**
 * Add property - convenience wrapper
 */
export async function addProperty(
  envName: string,
  key: string,
  value: string
): Promise<StatusResponse> {
  return addEnvironmentProperty(envName, { key, value });
}
