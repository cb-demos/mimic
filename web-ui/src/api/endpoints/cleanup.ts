/**
 * Cleanup API endpoints
 */

import { apiClient } from '../client';
import type {
  SessionListResponse,
  CleanupSessionRequest,
  CleanupResponse,
} from '../../types/api';

/**
 * List sessions for cleanup
 */
export async function listSessions(params?: {
  tenant?: string;
  expired_only?: boolean;
}): Promise<SessionListResponse> {
  const response = await apiClient.get<SessionListResponse>('/api/cleanup/sessions', {
    params,
  });
  return response.data;
}

/**
 * Clean up a specific session
 */
export async function cleanupSession(
  sessionId: string,
  request: CleanupSessionRequest
): Promise<CleanupResponse> {
  const response = await apiClient.post<CleanupResponse>('/api/cleanup/run', request, {
    params: { session_id: sessionId },
  });
  return response.data;
}

/**
 * Clean up all expired sessions
 */
export async function cleanupExpired(request: CleanupSessionRequest): Promise<CleanupResponse> {
  const response = await apiClient.post<CleanupResponse>('/api/cleanup/expired', request);
  return response.data;
}

/**
 * Delete a session (alias for cleanup)
 */
export async function deleteSession(
  sessionId: string,
  request: CleanupSessionRequest
): Promise<CleanupResponse> {
  const response = await apiClient.delete<CleanupResponse>(`/api/cleanup/sessions/${sessionId}`, {
    data: request,
  });
  return response.data;
}

// ==================== Convenience Exports ====================

/**
 * Convenience alias for listSessions
 */
export const list = listSessions;

/**
 * Convenience alias for cleanupSession
 */
export const cleanup = cleanupSession;
