import { useQuery } from '@tanstack/react-query';
import { useUiStore } from '../stores/uiStore';
import { checkHealth } from '../api/client';

const POLL_INTERVAL = 60_000; // 60 seconds

export function useHealthCheck() {
  const setBackendHealth = useUiStore((s) => s.setBackendHealth);

  // React Query deduplicates concurrent calls with the same queryKey,
  // so StrictMode double-invocation only produces one HTTP request.
  // React Query deduplicates concurrent calls with the same queryKey,
  // so StrictMode double-invocation only produces one HTTP request.
  useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      try {
        const data = await checkHealth();
        setBackendHealth(data.status === 'healthy');
        return data;
      } catch {
        setBackendHealth(false);
        // Return a minimal response so React Query doesn't retry on error
        return { status: 'unhealthy' } as const;
      }
    },
    refetchInterval: POLL_INTERVAL,
    staleTime: POLL_INTERVAL / 2,
    retry: false,
  });
}
