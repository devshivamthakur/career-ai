import { useEffect } from 'react';
import { useUiStore } from '../stores/uiStore';
import { checkHealth } from '../api/client';

const POLL_INTERVAL = 30000; // 30 seconds

export function useHealthCheck() {
  const setBackendHealth = useUiStore((s) => s.setBackendHealth);

  useEffect(() => {
    let active = true;

    const poll = async () => {
      try {
        const data = await checkHealth();
        if (active) {
          setBackendHealth(data.status === 'healthy');
        }
      } catch {
        if (active) {
          setBackendHealth(false);
        }
      }
    };

    // Immediate check
    poll();

    const interval = setInterval(poll, POLL_INTERVAL);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [setBackendHealth]);
}
