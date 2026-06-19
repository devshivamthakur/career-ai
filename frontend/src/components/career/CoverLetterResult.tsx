import { memo } from 'react';
import { Copy, RotateCcw, Download } from 'lucide-react';
import { Skeleton } from '../shared/Skeleton';
import { StreamingText } from '../shared/StreamingText';
import { useToastStore } from '../../stores/toastStore';

interface CoverLetterResultProps {
  coverLetter: string | null;
  streamedText?: string;
  isLoading: boolean;
  isStreaming?: boolean;
  company: string;
  role: string;
  onRegenerate: () => void;
}

export const CoverLetterResult = memo(function CoverLetterResult({
  coverLetter,
  streamedText = '',
  isLoading,
  isStreaming = false,
  company,
  role,
  onRegenerate,
}: CoverLetterResultProps) {
  const handleCopy = async () => {
    const text = coverLetter ?? streamedText;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      useToastStore.getState().showToast('Failed to copy to clipboard', 'error');
    }
  };

  const handleExportTxt = () => {
    const text = coverLetter ?? streamedText;
    if (!text) return;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Cover_Letter_${company.replace(/\s+/g, '_')}_${role.replace(/\s+/g, '_')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="mt-8 max-w-2xl mx-auto">
        <div className="bg-bg-surface rounded-lg p-8 border border-border">
          <div className="space-y-4">
            <Skeleton count={1} height="20px" className="w-1/3" />
            <Skeleton count={3} height="60px" />
          </div>
        </div>
      </div>
    );
  }

  if (!coverLetter && !isStreaming && !streamedText) return null;

  const displayText = coverLetter ?? streamedText;

  return (
    <div className="mt-8 max-w-2xl mx-auto">
      {/* Letter card */}
      <div className="bg-bg-surface rounded-lg p-8 border border-border">
        {/* Letter metadata */}
        <div className="mb-6 pb-4 border-b border-border">
          <p className="text-sm text-text-secondary font-mono">{company}</p>
          <p className="text-xs text-text-secondary">{role}</p>
        </div>

        {/* Letter content */}
        <div className="text-sm text-text-primary leading-relaxed whitespace-pre-wrap">
          {isStreaming && !coverLetter ? (
            <StreamingText text={displayText} isStreaming={true} />
          ) : (
            displayText
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 mt-4">
        <button
          onClick={handleCopy}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-bg-surface border border-border text-sm text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
        >
          <Copy size={16} />
          Copy
        </button>
        <button
          onClick={onRegenerate}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-bg-surface border border-border text-sm text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
        >
          <RotateCcw size={16} />
          Regenerate
        </button>
        <button
          onClick={handleExportTxt}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-bg-surface border border-border text-sm text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
        >
          <Download size={16} />
          Export .txt
        </button>
      </div>
    </div>
  );
});
