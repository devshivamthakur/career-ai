import { create } from 'zustand';
import type { ChatMessage, ToolCallInfo } from '../types/api';

interface ChatState {
  sessionId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  attachedFile: File | null;

  // Actions
  setSessionId: (id: string) => void;
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (msg: ChatMessage) => void;
  appendToken: (text: string) => void;
  addToolCall: (card: ToolCallInfo) => void;
  updateToolCall: (id: string, status: ToolCallInfo['status'], output?: string, duration?: number) => void;
  setResumeContent: (content: string) => void;
  setStreaming: (streaming: boolean) => void;
  setAttachedFile: (file: File | null) => void;
  clearMessages: () => void;
  reset: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessionId: null,
  messages: [],
  isStreaming: false,
  attachedFile: null,

  setSessionId: (id) => set({ sessionId: id }),

  setMessages: (messages) => set({ messages }),

  addMessage: (msg) =>
    set((state) => ({ messages: [...state.messages, msg] })),

  appendToken: (text) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, content: last.content + text };
      }
      return { messages: msgs };
    }),

  addToolCall: (card) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        const toolCalls = [...(last.toolCalls ?? []), card];
        msgs[msgs.length - 1] = { ...last, toolCalls };
      }
      return { messages: msgs };
    }),

  updateToolCall: (id, status, output, duration) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant' && last.toolCalls) {
        const toolCalls = last.toolCalls.map((tc) =>
          tc.id === id ? { ...tc, status, output: output ?? tc.output, duration: duration ?? tc.duration } : tc,
        );
        msgs[msgs.length - 1] = { ...last, toolCalls };
      }
      return { messages: msgs };
    }),

  setResumeContent: (content) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, resumeContent: content };
      }
      return { messages: msgs };
    }),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  setAttachedFile: (file) => set({ attachedFile: file }),

  clearMessages: () => set({ messages: [] }),

  reset: () =>
    set({
      sessionId: null,
      messages: [],
      isStreaming: false,
      attachedFile: null,
    }),
}));
