/**
 * React hook for consuming progress streams via SSE
 */

import { useEffect, useState, useCallback } from 'react';
import { createProgressStream } from '../api/sse';
import type { ProgressEvent, TaskStartData, TaskProgressData, TaskCompleteData } from '../types/api';

export interface ProgressState {
  events: ProgressEvent[];
  tasks: Map<string, TaskProgress>;
  isComplete: boolean;
  error: Error | null;
  isConnected: boolean;
}

export interface TaskProgress {
  id: string;
  description: string;
  current: number;
  total: number;
  status: 'running' | 'complete' | 'error';
  message?: string;
  error?: string;
}

/**
 * Hook to stream progress events for a scenario run
 */
export function useProgress(sessionId: string | null) {
  const [state, setState] = useState<ProgressState>({
    events: [],
    tasks: new Map(),
    isComplete: false,
    error: null,
    isConnected: false,
  });

  const reset = useCallback(() => {
    setState({
      events: [],
      tasks: new Map(),
      isComplete: false,
      error: null,
      isConnected: false,
    });
  }, []);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    // Reset state when session changes
    reset();

    // Mark as connected when stream starts
    setState((prev) => ({ ...prev, isConnected: true }));

    const cleanup = createProgressStream(sessionId, {
      onProgress: (event: ProgressEvent) => {
        setState((prev) => {
          const newState = { ...prev };
          newState.events = [...prev.events, event];

          // Update task map based on event type
          if (event.event === 'task_start') {
            const data = event.data as TaskStartData;
            newState.tasks = new Map(prev.tasks);
            newState.tasks.set(data.task_id, {
              id: data.task_id,
              description: data.description,
              current: 0,
              total: data.total,
              status: 'running',
            });
          } else if (event.event === 'task_progress') {
            const data = event.data as TaskProgressData;
            newState.tasks = new Map(prev.tasks);
            const task = newState.tasks.get(data.task_id);
            if (task) {
              newState.tasks.set(data.task_id, {
                ...task,
                current: data.current,
                total: data.total,
                message: data.message,
              });
            }
          } else if (event.event === 'task_complete') {
            const data = event.data as TaskCompleteData;
            newState.tasks = new Map(prev.tasks);
            const task = newState.tasks.get(data.task_id);
            if (task) {
              newState.tasks.set(data.task_id, {
                ...task,
                status: data.success ? 'complete' : 'error',
                message: data.message,
                current: task.total, // Set to 100%
              });
            }
          } else if (event.event === 'task_error') {
            const data = event.data as any;
            newState.tasks = new Map(prev.tasks);
            const task = newState.tasks.get(data.task_id);
            if (task) {
              newState.tasks.set(data.task_id, {
                ...task,
                status: 'error',
                error: data.error,
              });
            }
          } else if (event.event === 'scenario_complete') {
            newState.isComplete = true;
          }

          return newState;
        });
      },
      onError: (error: Error) => {
        setState((prev) => ({ ...prev, error, isConnected: false }));
      },
      onComplete: () => {
        setState((prev) => ({ ...prev, isComplete: true, isConnected: false }));
      },
    });

    return cleanup;
  }, [sessionId, reset]);

  return { ...state, reset };
}
