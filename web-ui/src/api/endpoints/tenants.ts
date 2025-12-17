/**
 * Tenant API endpoints
 */

import { apiClient } from '../client';
import type {
  AddPropertyRequest,
  AddPresetTenantRequest,
  AddTenantRequest,
  PresetTenantListResponse,
  PropertiesResponse,
  StatusResponse,
  TenantListResponse,
  ValidateCredentialsRequest,
  ValidateCredentialsResponse,
} from '../../types/api';

/**
 * List all environments with current selection
 */
export async function listTenants(): Promise<TenantListResponse> {
  const response = await apiClient.get<TenantListResponse>('/api/tenants');
  return response.data;
}

/**
 * Add a custom environment
 */
export async function addTenant(request: AddTenantRequest): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>('/api/tenants', request);
  return response.data;
}

/**
 * Remove an environment
 */
export async function removeTenant(tenantName: string): Promise<StatusResponse> {
  const response = await apiClient.delete<StatusResponse>(`/api/tenants/${tenantName}`);
  return response.data;
}

/**
 * Set an environment as current
 */
export async function selectTenant(tenantName: string): Promise<StatusResponse> {
  const response = await apiClient.patch<StatusResponse>(`/api/tenants/${tenantName}/select`);
  return response.data;
}

/**
 * Get environment properties
 */
export async function getTenantProperties(tenantName: string): Promise<PropertiesResponse> {
  const response = await apiClient.get<PropertiesResponse>(`/api/tenants/${tenantName}/properties`);
  return response.data;
}

/**
 * Add/update an environment property
 */
export async function addTenantProperty(
  tenantName: string,
  request: AddPropertyRequest
): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>(
    `/api/tenants/${tenantName}/properties`,
    request
  );
  return response.data;
}

/**
 * Delete an environment property
 */
export async function deleteTenantProperty(
  tenantName: string,
  propertyKey: string
): Promise<StatusResponse> {
  const response = await apiClient.delete<StatusResponse>(
    `/api/tenants/${tenantName}/properties/${propertyKey}`
  );
  return response.data;
}

/**
 * List all available preset environments
 */
export async function listPresetTenants(): Promise<PresetTenantListResponse> {
  const response = await apiClient.get<PresetTenantListResponse>('/api/tenants/presets');
  return response.data;
}

/**
 * Validate CloudBees credentials before adding environment
 */
export async function validateCredentials(
  request: ValidateCredentialsRequest
): Promise<ValidateCredentialsResponse> {
  const response = await apiClient.post<ValidateCredentialsResponse>(
    '/api/tenants/validate-credentials',
    request
  );
  return response.data;
}

/**
 * Add a preset environment with credentials
 */
export async function addPresetTenant(
  request: AddPresetTenantRequest
): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>(
    '/api/tenants/presets',
    request
  );
  return response.data;
}

// ==================== Convenience Wrappers ====================

/**
 * List environments - convenience alias
 */
export const list = listTenants;

/**
 * Add environment - convenience wrapper
 */
export async function add(
  name: string,
  url: string,
  endpoint_id: string,
  pat?: string,
  org_id?: string,
  use_legacy_flags?: boolean
): Promise<StatusResponse> {
  return addTenant({ name, url, endpoint_id, pat, org_id, use_legacy_flags });
}

/**
 * Remove environment - convenience alias
 */
export const remove = removeTenant;

/**
 * Select environment - convenience alias
 */
export const select = selectTenant;

/**
 * Get properties - convenience alias
 */
export const getProperties = getTenantProperties;

/**
 * Add property - convenience wrapper
 */
export async function addProperty(
  tenantName: string,
  key: string,
  value: string
): Promise<StatusResponse> {
  return addTenantProperty(tenantName, { key, value });
}
