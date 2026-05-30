import { type FC, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface TextOutputProps {
  title: string;
  content: string;
  isLoading: boolean;
  error: string | null;
  actionLabel?: string;
  onCopy?: () => void;
}

const TextOutput: FC<TextOutputProps> = ({
  title,
  content,
  isLoading,
  error,
  actionLabel = 'Copy to clipboard',
  onCopy,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [content]);

  const handleCopy = () => {
    if (!content) return;
    navigator.clipboard.writeText(content);
    if (onCopy) onCopy();
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-start justify-between mb-4 gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
          <p className="text-sm text-gray-500 mt-1">
            {isLoading
              ? 'Generating AI-assisted output...'
              : 'Review the results and copy them into your application.'}
          </p>
        </div>
        <button
          type="button"
          disabled={!content || isLoading}
          onClick={handleCopy}
          className="inline-flex items-center justify-center rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-semibold hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {actionLabel}
        </button>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 min-h-[18rem] overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        {error ? (
          <div className="rounded-2xl border border-red-100 bg-red-50 p-5 text-red-800">
            <h3 className="font-semibold">Error</h3>
            <p className="mt-2 text-sm">{error}</p>
          </div>
        ) : content ? (
          <div ref={contentRef} className="prose prose-slate max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-slate-500">
            {isLoading ? 'Waiting for the AI assistant...' : 'The result will appear here once you generate content.'}
          </div>
        )}
      </div>
    </div>
  );
};

export default TextOutput;
