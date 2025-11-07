/**
 * Axios client instance for API requests
 */

import axios from 'axios';

// Create axios instance with base configuration
export const apiClient = axios.create({
  baseURL: import.meta.env.DEV ? 'http://localhost:8080' : '',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout for normal requests
});

// Request interceptor for logging (development only)
if (import.meta.env.DEV) {
  apiClient.interceptors.request.use((config) => {
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  });
}

/**
 * Structured error type returned by the API
 */
export interface StructuredError {
  message: string;
  code?: string;
  suggestion?: string;
  details?: Array<{ message: string; field?: string; code?: string }>;
  requestId?: string;
  statusCode?: number;
}

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Log errors in development
    if (import.meta.env.DEV) {
      console.error('[API Error]', error.response?.data || error.message);
    }

    // Extract structured error from response
    const errorData = error.response?.data;

    if (errorData && typeof errorData === 'object') {
      // Check if this is a structured error response
      if (errorData.code || errorData.suggestion || errorData.details) {
        const structuredError: StructuredError = {
          message: errorData.message || errorData.error || 'An error occurred',
          code: errorData.code,
          suggestion: errorData.suggestion,
          details: errorData.details || [],
          requestId: errorData.request_id || errorData.requestId,
          statusCode: error.response?.status,
        };

        // Create enhanced error object with structured data attached
        const enhancedError = new Error(structuredError.message);
        (enhancedError as any).structured = structuredError;

        return Promise.reject(enhancedError);
      }
    }

    // Fallback for non-structured errors (legacy or external errors)
    const errorMessage =
      errorData?.message ||
      errorData?.error ||
      errorData?.detail ||
      error.message ||
      'An unknown error occurred';

    const fallbackError = new Error(errorMessage);
    (fallbackError as any).structured = {
      message: errorMessage,
      statusCode: error.response?.status,
    } as StructuredError;

    return Promise.reject(fallbackError);
  }
);
