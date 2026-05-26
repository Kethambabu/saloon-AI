/**
 * useApi Hook - Custom hook for API calls with loading and error states
 */

import { useState, useCallback } from 'react';
import { AxiosError, AxiosRequestConfig } from 'axios';
import { apiClient } from '../api/client';
import { useAppStore } from '../store/appStore';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: AxiosError | null;
}

/**
 * Custom hook for making API calls
 * Integrates with global app store for loading/error states
 */
export const useApi = <T = any>() => {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const { setLoading: setAppLoading, setError: setAppError } = useAppStore();

  const request = useCallback(
    async (
      endpoint: string,
      config?: AxiosRequestConfig,
      updateAppState = true
    ): Promise<T> => {
      setState({ data: null, loading: true, error: null });

      if (updateAppState) {
        setAppLoading(true);
      }

      try {
        const response = await apiClient.request<T>({
          url: endpoint,
          ...config,
        });

        setState({
          data: response.data,
          loading: false,
          error: null,
        });

        if (updateAppState) {
          setAppLoading(false);
        }

        return response.data;
      } catch (error) {
        const axiosError = error as AxiosError;

        setState({
          data: null,
          loading: false,
          error: axiosError,
        });

        if (updateAppState) {
          setAppLoading(false);
          setAppError(axiosError.message);
        }

        throw axiosError;
      }
    },
    [setAppLoading, setAppError]
  );

  const get = useCallback(
    async (endpoint: string, config?: AxiosRequestConfig): Promise<T> => {
      return request(endpoint, { ...config, method: 'GET' });
    },
    [request]
  );

  const post = useCallback(
    async (
      endpoint: string,
      data?: any,
      config?: AxiosRequestConfig
    ): Promise<T> => {
      return request(endpoint, { ...config, method: 'POST', data });
    },
    [request]
  );

  const put = useCallback(
    async (
      endpoint: string,
      data?: any,
      config?: AxiosRequestConfig
    ): Promise<T> => {
      return request(endpoint, { ...config, method: 'PUT', data });
    },
    [request]
  );

  const del = useCallback(
    async (endpoint: string, config?: AxiosRequestConfig): Promise<T> => {
      return request(endpoint, { ...config, method: 'DELETE' });
    },
    [request]
  );

  return {
    ...state,
    request,
    get,
    post,
    put,
    delete: del,
  };
};

export default useApi;
