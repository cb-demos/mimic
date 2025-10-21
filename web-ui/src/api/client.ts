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

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Log errors in development
    if (import.meta.env.DEV) {
      console.error('[API Error]', error.response?.data || error.message);
    }

    // Format error message
    const errorMessage =
      error.response?.data?.error ||
      error.response?.data?.detail ||
      error.message ||
      'An unknown error occurred';

    // Reject with formatted error
    return Promise.reject(new Error(errorMessage));
  }
);
