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
export async function getScenario(scenarioId: string): Promise<ScenarioDetailResponse> {
  const response = await apiClient.get<ScenarioDetailResponse>(`/api/scenarios/${scenarioId}`);
  return response.data;
}

/**
 * Validate scenario parameters without running
 */
export async function validateParameters(
  scenarioId: string,
  request: ValidateParametersRequest
): Promise<ValidateParametersResponse> {
  const response = await apiClient.get<ValidateParametersResponse>(
    `/api/scenarios/${scenarioId}/validate`,
    {
      params: { parameters: JSON.stringify(request.parameters) },
    }
  );
  return response.data;
}

/**
 * Execute a scenario with parameters
 */
export async function runScenario(
  scenarioId: string,
  request: RunScenarioRequest
): Promise<RunScenarioResponse> {
  const response = await apiClient.post<RunScenarioResponse>(
    `/api/scenarios/${scenarioId}/run`,
    request
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
  invitee_username?: string
): Promise<RunScenarioResponse> {
  return runScenario(scenarioId, {
    organization_id: organizationId,
    parameters,
    ttl_days,
    dry_run,
    invitee_username,
  });
}

/**
 * Check required properties/secrets for a scenario
 */
export async function checkProperties(
  scenarioId: string,
  request: CheckPropertiesRequest
): Promise<CheckPropertiesResponse> {
  const response = await apiClient.post<CheckPropertiesResponse>(
    `/api/scenarios/${scenarioId}/check-properties`,
    request
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
  request: ScenarioPreviewRequest
): Promise<ScenarioPreviewResponse> {
  const response = await apiClient.post<ScenarioPreviewResponse>(
    `/api/scenarios/${scenarioId}/preview`,
    request
  );
  return response.data;
}
