import { useCallback, useRef, useEffect } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useToastStore } from '../stores/toastStore';
import { useChatSession } from '../hooks/useChatSession';
import { useSseStream } from '../hooks/useSseStream';
import { ChatWindow } from '../components/chat/ChatWindow';
import { InputBar } from '../components/chat/InputBar';
import { stripTrailingCommentary } from '../utils/cleanup';


const API_ORIGIN = import.meta.env.VITE_API_URL ?? '';
const STREAM_URL = API_ORIGIN
  ? `${API_ORIGIN}/api/chat/stream`
  : '/api/chat/stream';

// ── Client-side resume extraction fallback ───────────────────
// If the backend misses detecting resume markers, the frontend
// tries to extract them directly from the message content.

const VISIBLE_RESUME_RE = /---\s*BEGIN\s*RESUME\s*---\s*([\s\S]*?)\s*---\s*END\s*RESUME\s*---/i;
const HTML_RESUME_RE = /<!--RESUME-->([\s\S]*?)<!--\/RESUME-->/;

function extractResumeFromText(text: string): string | null {
  // Try visible markers first
  const visibleMatch = VISIBLE_RESUME_RE.exec(text);
  if (visibleMatch) {
    const extracted = visibleMatch[1].trim();
    if (extracted.length >= 200) return extracted;
  }
  // Try HTML markers
  const htmlMatch = HTML_RESUME_RE.exec(text);
  if (htmlMatch) {
    const extracted = htmlMatch[1].trim();
    if (extracted.length >= 200) return extracted;
  }
  return null;
}

// ── stripTrailingCommentary is imported from ../utils/cleanup ───

let messageCounter = 0;

function generateId(): string {
  return `msg_${Date.now()}_${++messageCounter}`;
}

export default function ChatPage() {
  const { sessionId, messages, isLoading } = useChatSession();
  const { start, stop, isStreaming } = useSseStream();
  const showToast = useToastStore((s) => s.showToast);

  const {
    addMessage,
    appendToken,
    addToolCall,
    updateToolCall,
    setResumeContent,
    setStreaming,
    setResumeUploaded,
    attachedFile,
    setAttachedFile,
    resumeUploaded,
  } = useChatStore();

  // Guard against concurrent sends (e.g., Enter + click in same tick)
  const sendingRef = useRef(false);

  // Track tool call IDs for the current stream
  const toolCallIdRef = useRef<string | null>(null);
  const toolCallNameRef = useRef<string | null>(null);
  const toolStartTimeRef = useRef<number>(0);

  // Abort any in-flight stream when navigating away
  useEffect(() => {
    return () => stop();
  }, [stop]);

  const handleSend = useCallback(
    (message: string) => {
      if (!sessionId || sendingRef.current) return;
      sendingRef.current = true;

      // Add user message
      const userMsg: import('../types/api').ChatMessage = {
        id: generateId(),
        role: 'user' as const,
        content: message,
        timestamp: new Date().toISOString(),
        file: attachedFile?.name,
      };
      addMessage(userMsg);

      // Add placeholder assistant message
      const assistantId = generateId();
      const assistantMsg = {
        id: assistantId,
        role: 'assistant' as const,
        content: '',
        timestamp: new Date().toISOString(),
      };
      addMessage(assistantMsg);
      setStreaming(true);

      toolCallIdRef.current = null;
      toolCallNameRef.current = null;

      // Build form data
      const formData = new FormData();
      formData.append('message', message);
      formData.append('session_id', sessionId);

      if (attachedFile) {
        formData.append('file', attachedFile);
        setAttachedFile(null);
        // Optimistically mark as uploaded; backend will reject duplicates
        // with a clear error if this somehow isn't the first upload.
        setResumeUploaded(true);
      }

      start({
        url: STREAM_URL,
        body: formData,
        onEvent: (type, data) => {
          const d = data as Record<string, unknown>;
          switch (type) {
            case 'token': {
              const tokenData = d as { content?: string };
              if (tokenData.content) {
                appendToken(tokenData.content);
              }
              break;
            }

            case 'tool_start': {
              const toolData = d as { tool?: string; input?: string };
              const tId = `tool_${Date.now()}`;
              const tName = toolData.tool ?? 'Unknown';
              toolCallIdRef.current = tId;
              toolCallNameRef.current = tName;
              toolStartTimeRef.current = performance.now();
              addToolCall({
                id: tId,
                toolName: tName,
                status: 'running',
              });
              break;
            }

            case 'tool_end': {
              const endData = d as {
                tool?: string;
                output?: string;
              };
              const tId = toolCallIdRef.current;
              if (tId) {
                const elapsed = (performance.now() - toolStartTimeRef.current) / 1000;
                updateToolCall(tId, 'done', endData.output ?? '', elapsed);
              }
              toolCallIdRef.current = null;
              toolCallNameRef.current = null;
              break;
            }

            case 'tool_call': {
              const tcData = d as { tool?: string; args?: string };
              addToolCall({
                id: `tool_${Date.now()}`,
                toolName: tcData.tool ?? 'Unknown',
                status: 'running',
              });
              break;
            }

            case 'resume_ready': {
              const resumeData = d as { content?: string };
              if (resumeData.content) {
                setResumeContent(resumeData.content);
                setResumeUploaded(true);
              }
              break;
            }

            case 'done': {
              // Streaming complete
              break;
            }

            case 'error': {
              const errData = d as { content?: string };
              showToast(errData.content ?? 'An error occurred', 'error');
              break;
            }
          }
        },
        onComplete: () => {
          // Client-side fallback: check if the last message has resume markers
          // (in case the backend `resume_ready` event wasn't emitted)
          const { messages: currentMsgs, resumeUploaded: alreadyUploaded } = useChatStore.getState();
          const lastMsg = currentMsgs[currentMsgs.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            // Strip trailing conversational text from the message
            const cleaned = stripTrailingCommentary(lastMsg.content);
            if (cleaned !== lastMsg.content) {
              // Update the message content in the store
              useChatStore.setState((state) => {
                const msgs = [...state.messages];
                const idx = msgs.length - 1;
                if (idx >= 0 && msgs[idx].id === lastMsg.id) {
                  msgs[idx] = { ...msgs[idx], content: cleaned };
                }
                return { messages: msgs };
              });
            }
            if (!lastMsg.resumeContent) {
              const extracted = extractResumeFromText(cleaned);
              if (extracted) {
                setResumeContent(extracted);
                if (!alreadyUploaded) {
                  setResumeUploaded(true);
                }
              }
            }
          }
          sendingRef.current = false;
          setStreaming(false);
        },
        onError: (error) => {
          sendingRef.current = false;
          // If the error is about duplicate file upload, ensure flag is set
          // (the backend rejected it because a resume was already uploaded).
          if (error.toLowerCase().includes('already uploaded')) {
            setResumeUploaded(true);
          }
          showToast(error, 'error');
          setStreaming(false);
        },
      });
    },
    [
      sessionId,
      attachedFile,
      setAttachedFile,
      addMessage,
      appendToken,
      addToolCall,
      updateToolCall,
      setResumeContent,
      setStreaming,
      start,
      showToast,
    ],
  );

  const handleStop = useCallback(() => {
    sendingRef.current = false;
    stop();
    setStreaming(false);
  }, [stop, setStreaming]);

  const handleSuggestionClick = useCallback(
    (text: string) => {
      handleSend(text);
    },
    [handleSend],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3">
          <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-text-secondary">Loading session...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <ChatWindow
        messages={messages}
        isStreaming={isStreaming}
        onSuggestionClick={handleSuggestionClick}
      />
      <InputBar
        onSend={handleSend}
        onStop={handleStop}
        onAttachFile={setAttachedFile}
        isStreaming={isStreaming}
        attachedFile={attachedFile}
        resumeUploaded={resumeUploaded}
      />
    </div>
  );
}
