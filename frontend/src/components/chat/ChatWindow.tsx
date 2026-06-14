import { useEffect, useRef } from 'react';
import type { ChatMessage } from '../../types/api';
import { MessageBubble } from './MessageBubble';
import { ChatEmptyState } from './ChatEmptyState';

interface ChatWindowProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  onSuggestionClick: (text: string) => void;
}

export function ChatWindow({ messages, isStreaming, onSuggestionClick }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const userScrolledUpRef = useRef(false);

  // Track user scroll intent — if they scroll up, don't fight them
  const handleScroll = () => {
    const container = containerRef.current;
    if (!container) return;
    const distFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    userScrolledUpRef.current = distFromBottom > 80;
  };

  // Auto-scroll when new messages appear or during streaming
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Use requestAnimationFrame so the DOM has painted new content first
    const raf = requestAnimationFrame(() => {
      // Scroll if user hasn't intentionally scrolled up
      if (!userScrolledUpRef.current) {
        bottomRef.current?.scrollIntoView({
          behavior: isStreaming ? 'auto' : 'smooth',
        });
      }
    });

    return () => cancelAnimationFrame(raf);
  }, [messages, isStreaming]);

  if (messages.length === 0) {
    return <ChatEmptyState onSuggestionClick={onSuggestionClick} />;
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto px-4 py-6"
    >
      <div className="max-w-3xl mx-auto">
        {messages.map((msg, idx) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreaming={isStreaming && idx === messages.length - 1 && msg.role === 'assistant'}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
