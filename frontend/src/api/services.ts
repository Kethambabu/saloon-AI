/**
 * API Service Layer
 * Higher-level API functions for common operations
 */

import { apiClient } from './client';

/**
 * Health check - verify backend connectivity
 */
export const healthCheck = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

/**
 * Get API information
 */
export const getApiInfo = async () => {
  const response = await apiClient.get('/');
  return response.data;
};

export default {
  healthCheck,
  getApiInfo,
};
