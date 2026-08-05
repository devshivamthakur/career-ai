import { useState, useRef, useCallback, type KeyboardEvent, type ChangeEvent } from 'react';
import { Send, Square, Paperclip, X } from 'lucide-react';
import { useToastStore } from '../../stores/toastStore';
import { LIMITS, MAX_FILE_SIZE_BYTES } from '../../utils/limits';

interface InputBarProps {
  onSend: (message: string) => void;
  onStop: () => void;
  onAttachFile: (file: File | null) => void;
  isStreaming: boolean;
  attachedFile: File | null;
  resumeUploaded: boolean;
  disabled?: boolean;
}

export function InputBar({
  onSend,
  onStop,
  onAttachFile,
  isStreaming,
  attachedFile,
  resumeUploaded,
  disabled,
}: InputBarProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const showToast = useToastStore((s) => s.showToast);

  const adjustHeight = useCallback(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 5 * 24) + 'px';
    }
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSend(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input, isStreaming, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleInputChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    // Enforce the backend message limit client-side
    setInput(e.target.value.slice(0, LIMITS.MAX_CHAT_MESSAGE_LENGTH));
    adjustHeight();
  }, [adjustHeight]);

  const handleFileSelect = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0] ?? null;
      if (file) {
        if (file.type !== 'application/pdf') {
          showToast('Only PDF files are accepted', 'error');
        } else if (file.size > MAX_FILE_SIZE_BYTES) {
          showToast(`File exceeds ${LIMITS.MAX_FILE_SIZE_MB}MB limit`, 'error');
        } else {
          onAttachFile(file);
        }
      }
      // Reset input so same file can be re-selected
      e.target.value = '';
    },
    [onAttachFile, showToast],
  );

  const charsRemaining = LIMITS.MAX_CHAT_MESSAGE_LENGTH - input.length;

  return (
    <div className="border-t border-border bg-bg-surface px-4 py-3">
      {/* Attached file pill */}
      {attachedFile && (
        <div className="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-md bg-accent/10 text-xs text-accent max-w-fit">
          <span className="font-medium truncate max-w-[200px]">{attachedFile.name}</span>
          <button
            onClick={() => onAttachFile(null)}
            className="hover:text-danger transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div className="flex items-stretch gap-2">
        {/* Attach file button — disabled once a resume is uploaded */}
        <div className="flex items-center">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming || resumeUploaded}
            className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors disabled:opacity-40"
            title={resumeUploaded ? 'Resume already uploaded (one per chat)' : 'Attach resume PDF'}
          >
            <Paperclip size={18} />
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* Textarea */}
        <div className="flex-1 min-w-0 flex items-center">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Type your message..."
            rows={1}
            maxLength={LIMITS.MAX_CHAT_MESSAGE_LENGTH}
            disabled={disabled}
            className="w-full resize-none bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent/50 transition-colors disabled:opacity-50"
            style={{ maxHeight: '120px' }}
          />
        </div>

        {/* Send / Stop button */}
        <div className="flex items-center">
          {isStreaming ? (
            <button
              onClick={onStop}
              className="p-2 rounded-lg bg-danger/20 text-danger hover:bg-danger/30 transition-colors"
              title="Stop streaming"
            >
              <Square size={18} />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming || disabled}
            className="p-2 rounded-lg bg-accent text-white hover:bg-accent/80 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Send message"
          >
            <Send size={18} />
          </button>
        )}
        </div>
      </div>
      {/* Character counter — subtle, only when near the limit */}
      {input.length > 0 && (
        <div className="flex justify-end mt-1 pr-1">
          <span
            className={`text-[10px] font-mono ${
              charsRemaining < 100 ? 'text-warning' : 'text-text-secondary'
            }`}
          >
            {input.length} / {LIMITS.MAX_CHAT_MESSAGE_LENGTH}
          </span>
        </div>
      )}
    </div>
  );
}
