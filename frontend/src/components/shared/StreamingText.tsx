import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';

interface StreamingTextProps {
  text: string;
  isStreaming: boolean;
}

const markdownComponents = {
  code({ className, children, ...props }: { className?: string; children?: React.ReactNode }) {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="bg-bg-elevated px-1.5 py-0.5 rounded text-sm font-mono text-accent" {...props}>
          {children}
        </code>
      );
    }
    return (
      <pre className="bg-bg-base rounded-md p-4 my-2 overflow-x-auto text-sm font-mono">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    );
  },
  ul({ children }: { children?: React.ReactNode }) {
    return <ul className="list-disc ml-5 my-1 text-text-primary">{children}</ul>;
  },
  ol({ children }: { children?: React.ReactNode }) {
    return <ol className="list-decimal ml-5 my-1 text-text-primary">{children}</ol>;
  },
  p({ children }: { children?: React.ReactNode }) {
    return <p className="mb-1">{children}</p>;
  },
  strong({ children }: { children?: React.ReactNode }) {
    return <strong className="font-semibold">{children}</strong>;
  },
};

export function StreamingText({ text, isStreaming }: StreamingTextProps) {
  const rendered = useMemo(
    () => (
      <ReactMarkdown components={markdownComponents}>
        {text}
      </ReactMarkdown>
    ),
    [text],
  );

  return (
    <div className="leading-relaxed break-words overflow-hidden [&_*]:break-words">
      {rendered}
      {isStreaming && (
        <span className="cursor-blink inline-block w-[2px] h-[1em] bg-accent ml-0.5 align-middle" />
      )}
    </div>
  );
}
