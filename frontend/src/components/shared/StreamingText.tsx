import { memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface StreamingTextProps {
  text: string;
  isStreaming: boolean;
}

export const StreamingText = memo(function StreamingText({ text, isStreaming }: StreamingTextProps) {
  const rendered = useMemo(
    () => (
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {text}
      </ReactMarkdown>
    ),
    [text],
  );

  return (
    <div className="markdown-content leading-relaxed break-words overflow-hidden [&_*]:break-words">
      {rendered}
      {isStreaming && (
        <span className="cursor-blink inline-block w-[2px] h-[1em] bg-accent ml-0.5 align-middle" />
      )}
    </div>
  );
});
