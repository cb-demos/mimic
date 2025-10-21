/**
 * Setup API endpoints
 */

import { apiClient } from '../client';
import type {
  SetupStatusResponse,
  RunSetupRequest,
  RunSetupResponse,
} from '../../types/api';

/**
 * Check if initial setup is needed
 */
export async function getSetupStatus(): Promise<SetupStatusResponse> {
  const response = await apiClient.get<SetupStatusResponse>('/api/setup/status');
  return response.data;
}

/**
 * Run initial setup wizard
 */
export async function runSetup(request: RunSetupRequest): Promise<RunSetupResponse> {
  const response = await apiClient.post<RunSetupResponse>('/api/setup/run', request);
  return response.data;
}
