/**
 * Server-Sent Events (SSE) client for progress streaming
 */

import type { ProgressEvent } from '../types/api';

export type ProgressCallback = (event: ProgressEvent) => void;
export type ErrorCallback = (error: Error) => void;
export type CompleteCallback = () => void;

export interface SSEClientOptions {
  onProgress: ProgressCallback;
  onError?: ErrorCallback;
  onComplete?: CompleteCallback;
}

/**
 * Create an SSE connection to stream progress events for a scenario run
 */
export function createProgressStream(
  sessionId: string,
  options: SSEClientOptions
): () => void {
  const baseURL = import.meta.env.DEV ? 'http://localhost:8080' : '';
  const url = `${baseURL}/api/scenarios/progress/${sessionId}`;

  const eventSource = new EventSource(url);

  // Handle incoming messages
  eventSource.onmessage = (event) => {
    try {
      const progressEvent: ProgressEvent = JSON.parse(event.data);
      options.onProgress(progressEvent);

      // If scenario is complete, close the connection
      if (progressEvent.event === 'scenario_complete') {
        eventSource.close();
        options.onComplete?.();
      }
    } catch (error) {
      console.error('[SSE] Failed to parse event:', error);
      options.onError?.(
        error instanceof Error ? error : new Error('Failed to parse SSE event')
      );
    }
  };

  // Handle errors
  eventSource.onerror = (error) => {
    console.error('[SSE] Connection error:', error);
    eventSource.close();
    options.onError?.(new Error('SSE connection failed'));
  };

  // Return cleanup function
  return () => {
    eventSource.close();
  };
}
