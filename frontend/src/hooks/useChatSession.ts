import { useEffect, useCallback, useRef } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useToastStore } from '../stores/toastStore';
import * as api from '../api/client';

const SESSION_KEY = 'careerAI_session_id';

export function useChatSession() {
  const {
    sessionId,
    setSessionId,
    setMessages,
    clearMessages,
    messages,
  } = useChatStore();

  const showToast = useToastStore((s) => s.showToast);

  // Guard against React StrictMode double-firing in development.
  // useRef values persist across the StrictMode unmount/remount cycle,
  // so this flag ensures initSession() runs only once.
  const initStarted = useRef(false);

  const initSession = useCallback(async () => {
    try {
      // Check localStorage for existing session
      const storedId = localStorage.getItem(SESSION_KEY);

      if (storedId) {
        try {
          const data = await api.getSessionMessages(storedId);
          setSessionId(storedId);
          setMessages(data.messages ?? []);
          return;
        } catch {
          // Session expired or invalid — create new one
          localStorage.removeItem(SESSION_KEY);
        }
      }

      // Create new session
      const { session_id } = await api.createSession();
      localStorage.setItem(SESSION_KEY, session_id);
      setSessionId(session_id);
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : 'Failed to initialize session',
        'error',
      );
    }
  }, [setSessionId, setMessages, showToast]);

  const clearSession = useCallback(async () => {
    if (!sessionId) {
      clearMessages();
      return;
    }

    try {
      await api.deleteSession(sessionId);
    } catch {
      // Ignore errors on delete — proceed to create new
    }

    localStorage.removeItem(SESSION_KEY);

    try {
      const { session_id } = await api.createSession();
      localStorage.setItem(SESSION_KEY, session_id);
      setSessionId(session_id);
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : 'Failed to create new session',
        'error',
      );
    }

    clearMessages();
  }, [sessionId, setSessionId, clearMessages, showToast]);

  // Initialize on mount (runs once even with StrictMode double-mount)
  useEffect(() => {
    if (!sessionId && !initStarted.current) {
      initStarted.current = true;
      initSession();
    }
  }, [sessionId, initSession]);

  return {
    sessionId,
    messages,
    initSession,
    clearSession,
    isLoading: !sessionId,
  };
}
