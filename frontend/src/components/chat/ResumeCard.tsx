import { memo } from 'react';
import type { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileText, Sparkles } from 'lucide-react';

interface ResumeCardProps {
  content: string;
  isStreaming?: boolean;
}

// ── Helpers for custom markdown rendering ─────────────────────

/** Flattens React children into plain text (for heading parsing). */
function extractPlainText(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(extractPlainText).join('');
  if (node && typeof node === 'object' && 'props' in node) {
    const props = (node as { props: { children?: ReactNode } }).props;
    return extractPlainText(props.children);
  }
  return '';
}

/** Resume name/title header (from `## Name | Title`). */
function ResumeHeader({ children }: { children?: ReactNode }) {
  const text = extractPlainText(children);
  const parts = text.split('|').map((s) => s.trim());
  const name = parts[0];
  const title = parts.slice(1).join(' | ');

  return (
    <div className="mb-4 border-b border-accent/20 pb-3 text-center">
      {name && <p className="text-lg font-bold leading-snug text-text-primary">{name}</p>}
      {title && <p className="mt-0.5 text-sm font-medium text-accent">{title}</p>}
    </div>
  );
}

/** Resume section heading (from `### Heading`). */
function SectionHeading({ children }: { children?: ReactNode }) {
  return (
    <h3 className="mb-2 mt-5 border-b border-border pb-1.5 text-xs font-bold uppercase tracking-widest text-accent">
      {children}
    </h3>
  );
}

const resumeMarkdownComponents = {
  h1: ResumeHeader,
  h2: ResumeHeader,
  h3: SectionHeading,
  p: ({ children }: { children?: ReactNode }) => (
    <p className="mb-1.5 text-[13px] leading-relaxed text-text-primary">{children}</p>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="mb-2 ml-4 list-disc space-y-1">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="mb-2 ml-4 list-decimal space-y-1">{children}</ol>
  ),
  li: ({ children }: { children?: ReactNode }) => (
    <li className="text-[13px] leading-relaxed text-text-primary">{children}</li>
  ),
  strong: ({ children }: { children?: ReactNode }) => (
    <strong className="font-semibold text-text-primary">{children}</strong>
  ),
};

/**
 * Renders the content between the resume markers as a polished,
 * document-style card (markers are hidden by the segment parser).
 */
export const ResumeCard = memo(function ResumeCard({ content, isStreaming }: ResumeCardProps) {
  return (
    <div className="my-2 overflow-hidden rounded-xl border border-accent/25 bg-bg-elevated shadow-sm">
      {/* Card header */}
      <div className="flex items-center justify-between gap-2 border-b border-accent/20 bg-accent/10 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <FileText size={15} className="shrink-0 text-accent" />
          <span className="truncate text-xs font-semibold text-text-primary">
            Tailored Resume
          </span>
        </div>
        <span className="flex shrink-0 items-center gap-1 rounded-full border border-accent/20 bg-accent/10 px-2 py-0.5 text-[10px] font-medium text-accent">
          <Sparkles size={10} />
          ATS-optimized
        </span>
      </div>

      {/* Document body */}
      <div className="bg-bg-surface px-5 py-4">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={resumeMarkdownComponents}>
          {content}
        </ReactMarkdown>
        {isStreaming && (
          <span className="cursor-blink ml-0.5 inline-block h-[1em] w-[2px] bg-accent align-middle" />
        )}
      </div>
    </div>
  );
});
