/**
 * API Client Configuration
 * Axios instance with base configuration for communicating with FastAPI backend
 */

import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

// Get API base URL from environment or use default
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/**
 * Create and configure Axios instance
 */
const createApiClient = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
    withCredentials: true, // Include credentials for CORS requests
  });

  // Request interceptor
  instance.interceptors.request.use(
    (config) => {
      // Add auth token if available
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor
  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      // Handle specific error codes
      if (error.response?.status === 401) {
        // Unauthorized - clear token and redirect to login
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
      } else if (error.response?.status === 403) {
        // Forbidden
        console.error('Access denied');
      } else if (error.response?.status === 500) {
        // Server error
        console.error('Server error');
      }
      return Promise.reject(error);
    }
  );

  return instance;
};

// Export configured instance
export const apiClient = createApiClient();

// Export types and utilities
export type { AxiosRequestConfig };
export { API_BASE_URL };
