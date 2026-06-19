import { memo } from 'react';
import { Sparkles } from 'lucide-react';

interface ChatEmptyStateProps {
  onSuggestionClick: (text: string) => void;
}

const suggestions = [
  'Review my resume for a Senior Engineer role',
  'What skills should I highlight for a GenAI position?',
  'Help me prepare for a system design interview',
];

export const ChatEmptyState = memo(function ChatEmptyState({ onSuggestionClick }: ChatEmptyStateProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
      <div className="flex items-center justify-center w-16 h-16 rounded-full bg-accent/10 mb-6">
        <Sparkles size={32} className="text-accent" />
      </div>

      <h2 className="text-xl font-bold text-text-primary mb-2">Your Career Co-pilot</h2>
      <p className="text-sm text-text-secondary text-center max-w-md mb-8">
        Ask me anything — resume advice, job strategy, interview tips, or upload your resume for a detailed review.
      </p>

      <div className="flex flex-col gap-2 w-full max-w-md">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => onSuggestionClick(suggestion)}
            className="w-full text-left px-4 py-3 rounded-lg bg-bg-surface border border-border hover:border-accent/40 text-sm text-text-secondary hover:text-text-primary transition-all"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
});
