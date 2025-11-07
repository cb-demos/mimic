/**
 * Error handling utilities for converting API errors to structured ErrorInfo
 */

import type { ErrorInfo } from '../components/ErrorAlert';

/**
 * Convert any error to structured ErrorInfo format
 *
 * This function handles errors from the axios interceptor which attaches
 * structured error data as `error.structured` when available from the API.
 *
 * @param error - Any error object (typically from API calls)
 * @returns Structured ErrorInfo with message, code, suggestion, etc.
 */
export function toErrorInfo(error: any): ErrorInfo {
  // Check if error has structured error data attached by axios interceptor
  if (error?.structured && typeof error.structured === 'object') {
    const structured = error.structured;

    return {
      message: structured.message || 'An error occurred',
      code: structured.code,
      suggestion: structured.suggestion,
      details: Array.isArray(structured.details) ? structured.details : [],
      requestId: structured.requestId || structured.request_id,
      technical_details: structured.technical_details,
    };
  }

  // Fallback to simple error message
  return {
    message: error?.message || error?.toString() || 'An unexpected error occurred',
  };
}
