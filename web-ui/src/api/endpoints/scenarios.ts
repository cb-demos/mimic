/**
 * Scenario API endpoints
 */

import { apiClient } from '../client';
import type {
  ScenarioListResponse,
  ScenarioDetailResponse,
  RunScenarioRequest,
  RunScenarioResponse,
  ValidateParametersRequest,
  ValidateParametersResponse,
  CheckPropertiesRequest,
  CheckPropertiesResponse,
  CreatePropertyRequest,
  ScenarioPreviewRequest,
  ScenarioPreviewResponse,
  StatusResponse,
} from '../../types/api';

/**
 * List all available scenarios
 */
export async function listScenarios(): Promise<ScenarioListResponse> {
  const response = await apiClient.get<ScenarioListResponse>('/api/scenarios');
  return response.data;
}

/**
 * Get scenario details with parameter schema
 */
export async function getScenario(
  scenarioId: string,
  packSource?: string
): Promise<ScenarioDetailResponse> {
  const response = await apiClient.get<ScenarioDetailResponse>(`/api/scenarios/${scenarioId}`, {
    params: packSource ? { pack_source: packSource } : undefined,
  });
  return response.data;
}

/**
 * Validate scenario parameters without running
 */
export async function validateParameters(
  scenarioId: string,
  request: ValidateParametersRequest,
  packSource?: string
): Promise<ValidateParametersResponse> {
  const response = await apiClient.get<ValidateParametersResponse>(
    `/api/scenarios/${scenarioId}/validate`,
    {
      params: {
        parameters: JSON.stringify(request.parameters),
        ...(packSource && { pack_source: packSource }),
      },
    }
  );
  return response.data;
}

/**
 * Execute a scenario with parameters
 */
export async function runScenario(
  scenarioId: string,
  request: RunScenarioRequest,
  packSource?: string
): Promise<RunScenarioResponse> {
  const response = await apiClient.post<RunScenarioResponse>(
    `/api/scenarios/${scenarioId}/run`,
    request,
    {
      params: packSource ? { pack_source: packSource } : undefined,
    }
  );
  return response.data;
}

// ==================== Convenience Exports ====================

/**
 * Convenience alias for listScenarios
 */
export const list = listScenarios;

/**
 * Convenience alias for getScenario
 */
export const get = getScenario;

/**
 * Convenience wrapper for runScenario
 */
export async function run(
  scenarioId: string,
  organizationId: string,
  parameters: Record<string, any>,
  ttl_days?: number,
  dry_run?: boolean,
  invitee_username?: string,
  packSource?: string
): Promise<RunScenarioResponse> {
  return runScenario(
    scenarioId,
    {
      organization_id: organizationId,
      parameters,
      ttl_days,
      dry_run,
      invitee_username,
    },
    packSource
  );
}

/**
 * Check required properties/secrets for a scenario
 */
export async function checkProperties(
  scenarioId: string,
  request: CheckPropertiesRequest,
  packSource?: string
): Promise<CheckPropertiesResponse> {
  const response = await apiClient.post<CheckPropertiesResponse>(
    `/api/scenarios/${scenarioId}/check-properties`,
    request,
    {
      params: packSource ? { pack_source: packSource } : undefined,
    }
  );
  return response.data;
}

/**
 * Create a property or secret in a CloudBees organization
 */
export async function createProperty(
  request: CreatePropertyRequest
): Promise<StatusResponse> {
  const response = await apiClient.post<StatusResponse>(
    '/api/scenarios/properties/create',
    request
  );
  return response.data;
}

/**
 * Generate a preview of what will be created for a scenario
 */
export async function previewScenario(
  scenarioId: string,
  request: ScenarioPreviewRequest,
  packSource?: string
): Promise<ScenarioPreviewResponse> {
  const response = await apiClient.post<ScenarioPreviewResponse>(
    `/api/scenarios/${scenarioId}/preview`,
    request,
    {
      params: packSource ? { pack_source: packSource } : undefined,
    }
  );
  return response.data;
}
