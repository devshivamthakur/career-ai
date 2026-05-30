import { useState, useCallback } from 'react';
import { API_BASE_URL } from '../api/client';

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';

interface UseApiConfig {
  endpoint: string;
  method?: HttpMethod;
  headers?: Record<string, string>;
}

export interface ApiHookResult<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  execute: (body?: any, params?: Record<string, string>) => Promise<void>;
}

export const useApiService = <T>({
  endpoint,
  method = 'POST',
  headers = {},
}: UseApiConfig): ApiHookResult<T> => {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(
    async (body?: any, params?: Record<string, string>) => {
      setIsLoading(true);
      setError(null);
      setData(null);

      try {
        let url = `${API_BASE_URL}${endpoint}`;
        if (params) {
          const query = new URLSearchParams(params).toString();
          url = `${url}?${query}`;
        }

        const isFormData = body instanceof FormData;

        const response = await fetch(url, {
          method,
          headers: {
            ...(!isFormData && { 'Content-Type': 'application/json' }),
            ...headers,
          },
          body: isFormData ? body : JSON.stringify(body),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => null);
          throw new Error(errorData?.detail || `Server error: ${response.status}`);
        }

        const result = await response.json();
        setData(result);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'An unknown error occurred';
        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [endpoint, method, headers]
  );

  return { data, isLoading, error, execute };
};

export default useApiService;
