import { memo, useState, useCallback, useMemo } from 'react';
import { Download, FileText, Check, Paperclip } from 'lucide-react';
import type { ChatMessage } from '../../types/api';
import { StreamingText } from '../shared/StreamingText';
import { ToolCallCard } from './ToolCallCard';
import { ResumeCard } from './ResumeCard';
import { splitResumeSegments } from '../../utils/resumeSegments';
import { exportPdf } from '../../api/client';
import { useToastStore } from '../../stores/toastStore';

const API_ORIGIN = import.meta.env.VITE_API_URL ?? '';

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

function formatTime(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    return '';
  }
}

export const MessageBubble = memo(function MessageBubble({ message, isStreaming }: MessageBubbleProps) {
  const [showTime, setShowTime] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const showToast = useToastStore((s) => s.showToast);
  const isUser = message.role === 'user';

  // Split content into conversational + resume segments so the resume
  // block (between ---BEGIN RESUME--- / ---END RESUME---) renders as a
  // styled document card with the markers hidden.
  const segments = useMemo(() => splitResumeSegments(message.content), [message.content]);

  const handleDownloadResume = useCallback(async () => {
    if (!message.resumeContent) return;
    setIsDownloading(true);
    try {
      const blob = await exportPdf(message.resumeContent);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const timestamp = new Date().toISOString().slice(0, 10);
      a.download = `CareerAI_Resume_${timestamp}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('Resume PDF downloaded successfully!', 'success');
    } catch {
      showToast('Failed to download resume PDF. Please try again.', 'error');
    } finally {
      setIsDownloading(false);
    }
  }, [message.resumeContent, showToast]);

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
      onMouseEnter={() => setShowTime(true)}
      onMouseLeave={() => setShowTime(false)}
    >
      <div className={`max-w-[80%] min-w-0 ${isUser ? 'order-1' : 'order-1'}`}>
        {/* Bubble */}
        <div
          className={`rounded-lg px-4 py-3 overflow-hidden ${
            isUser
              ? 'bg-accent-soft text-text-primary rounded-br-md'
              : 'bg-bg-surface border-l-2 border-accent text-text-primary rounded-bl-md'
          }`}
        >
          {isUser ? (
            <>
              <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>

              {/* Uploaded file card */}
              {message.file && (
                <a
                  href={`${API_ORIGIN}/${message.file}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-center gap-2 mt-2 px-3 py-2 rounded-md bg-accent/10 hover:bg-accent/15 transition-colors"
                >
                  <Paperclip size={14} className="text-accent shrink-0" />
                  <span className="text-xs font-medium text-accent truncate">
                    {message.file.split('/').pop()}
                  </span>
                  <Download size={12} className="text-accent/60 shrink-0 ml-auto group-hover:translate-y-0.5 transition-transform" />
                </a>
              )}
            </>
          ) : (
            <div className="text-sm overflow-hidden [&_pre]:overflow-x-auto [&_pre]:whitespace-pre-wrap [&_pre]:break-words [&_code]:break-words [&_p]:break-words [&_h1]:break-words [&_h2]:break-words [&_h3]:break-words [&_li]:break-words">
              {segments.map((seg, idx) => {
                const isLastSegment = idx === segments.length - 1;
                const streaming = (isStreaming ?? false) && isLastSegment;
                if (seg.type === 'resume') {
                  return (
                    <ResumeCard
                      key={idx}
                      content={seg.content}
                      isStreaming={streaming}
                    />
                  );
                }
                return (
                  <StreamingText
                    key={idx}
                    text={seg.content}
                    isStreaming={streaming}
                  />
                );
              })}
            </div>
          )}
        </div>

        {/* Resume download button */}
        {message.resumeContent && !isStreaming && (
          <div className="mt-2 px-1">
            <button
              onClick={handleDownloadResume}
              disabled={isDownloading}
              className="group flex items-center gap-2 w-full px-4 py-2.5 rounded-lg border border-accent/30 bg-accent/5 hover:bg-accent/10 active:bg-accent/15 transition-all disabled:opacity-60"
            >
              <div className="flex items-center justify-center w-8 h-8 rounded-md bg-accent/10 group-hover:bg-accent/15 transition-colors">
                {isDownloading ? (
                  <Check size={16} className="text-accent" />
                ) : (
                  <FileText size={16} className="text-accent" />
                )}
              </div>
              <div className="flex-1 text-left">
                <p className="text-xs font-semibold text-text-primary">
                  {isDownloading ? 'Downloading...' : 'Download ATS Resume'}
                </p>
                <p className="text-[10px] text-text-secondary">
                  PDF format · ATS-optimized
                </p>
              </div>
              <Download size={14} className="text-accent shrink-0 group-hover:translate-y-0.5 transition-transform" />
            </button>
          </div>
        )}

        {/* Tool calls (hidden for compare_skills) */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-1 space-y-1">
            {message.toolCalls
              .filter((tc) => tc.toolName !== "compare_skills")
              .map((tc) => (
                <ToolCallCard key={tc.id} toolCall={tc} />
              ))}
          </div>
        )}

        {/* Timestamp */}
        {showTime && message.timestamp && (
          <p className="text-xs font-mono text-text-secondary mt-1 px-1">
            {formatTime(message.timestamp)}
          </p>
        )}
      </div>
    </div>
  );
});
