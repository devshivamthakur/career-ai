import { useCallback, useRef, useState } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';

interface SseOptions {
  url: string;
  body: FormData | Record<string, unknown>;
  onEvent: (type: string, data: unknown) => void;
  onComplete: () => void;
  onError: (error: string) => void;
  /** Called once the server accepts the request (HTTP 2xx). */
  onOpen?: () => void;
}

export function useSseStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async ({ url, body, onEvent, onComplete, onError, onOpen }: SseOptions) => {
    // Abort any existing stream
    if (abortRef.current) {
      abortRef.current.abort();
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);

    let errorReported = false;

    try {
      const options: Record<string, unknown> = {
        method: 'POST',
        signal: controller.signal,
        onopen: async (response: Response) => {
          if (!response.ok) {
            let errorMsg = `HTTP ${response.status}`;
            try {
              const errBody = await response.json();
              errorMsg = errBody.detail ?? errorMsg;
            } catch {
              // ignore parse errors
            }
            throw new Error(errorMsg);
          }
          // Request accepted — notify the caller (e.g. to mark a file upload
          // as confirmed before any streaming begins).
          onOpen?.();
        },
        onmessage: (event: { event: string; data: string }) => {
          const { event: type, data } = event;
          let parsed: unknown;
          try {
            parsed = JSON.parse(data);
          } catch {
            parsed = data;
          }
          onEvent(type || 'message', parsed);
        },
        onclose: () => {
          onComplete();
        },
        onerror: (err: Error) => {
          errorReported = true;
          onError(err.message);
          // Throw to prevent automatic reconnection
          throw err;
        },
      };

      // Prevent fetchEventSource from reconnecting on tab visibility changes
      options.openWhenHidden = true;

      if (body instanceof FormData) {
        options.body = body;
      } else {
        (options as Record<string, unknown>).headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify(body);
      }

      await fetchEventSource(url, options as Parameters<typeof fetchEventSource>[1]);
    } catch (err) {
      // Ignore abort errors (user cancelled the stream)
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      // Only report if not already handled by onerror
      if (!errorReported) {
        onError(err instanceof Error ? err.message : 'Connection lost');
      }
    } finally {
      // Only update state if we're still the active controller —
      // a newer stream may have started if start() was called again
      if (abortRef.current === controller) {
        setIsStreaming(false);
        abortRef.current = null;
      }
    }
  }, []);

  const stop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  return { start, stop, isStreaming };
}
