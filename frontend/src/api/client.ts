/**
 * API Client Configuration
 * Axios instance with base configuration for communicating with FastAPI backend
 * and supporting concurrent-safe JWT refresh token cycles.
 */

import axios from 'axios';
import type { AxiosInstance, AxiosRequestConfig } from 'axios';

// Get API base URL from environment or use default
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Request queueing state for handling concurrent 401s during refreshing
let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

/**
 * Create and configure Axios instance
 */
const createApiClient = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 60000,
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
    async (error) => {
      const originalRequest = error.config;

      // Handle 401 errors (Unauthorized)
      if (error.response?.status === 401 && !originalRequest._retry) {
        // If login or refresh endpoint itself fails, do not try to refresh
        if (originalRequest.url?.includes('/auth/login') || originalRequest.url?.includes('/auth/refresh')) {
          return Promise.reject(error);
        }

        // If currently refreshing, queue this request
        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          })
            .then((token) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              return instance(originalRequest);
            })
            .catch((err) => {
              return Promise.reject(err);
            });
        }

        originalRequest._retry = true;
        isRefreshing = true;

        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
          localStorage.removeItem('auth_token');
          // Dispatch custom event to let AuthContext know to logout
          window.dispatchEvent(new Event('auth_logged_out'));
          return Promise.reject(error);
        }

        try {
          // Use basic axios call directly to avoid interceptor loop
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token: newRefreshToken } = response.data;
          
          localStorage.setItem('auth_token', access_token);
          localStorage.setItem('refresh_token', newRefreshToken);

          // Update header
          instance.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
          originalRequest.headers.Authorization = `Bearer ${access_token}`;

          processQueue(null, access_token);
          return instance(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError, null);
          localStorage.removeItem('auth_token');
          localStorage.removeItem('refresh_token');
          window.dispatchEvent(new Event('auth_logged_out'));
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      }

      if (error.response?.status === 403) {
        console.error('Access denied - insufficient permissions');
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
