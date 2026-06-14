import { useState } from 'react';
import { ChevronDown, ChevronRight, Copy } from 'lucide-react';
import type { InterviewQuestion } from '../../types/api';

interface InterviewAccordionProps {
  questions: InterviewQuestion[];
  isLoading: boolean;
}

function StarSection({ label, text, color }: { label: string; text: string; color: string }) {
  return (
    <div className="mb-3">
      <span className={`text-xs font-bold font-mono ${color}`}>{label}</span>
      <p className="text-sm text-text-primary mt-0.5">{text}</p>
    </div>
  );
}

function AccordionCard({
  question,
  index,
}: {
  question: InterviewQuestion;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [yourAnswer, setYourAnswer] = useState('');

  return (
    <div className="border border-border rounded-lg overflow-hidden bg-bg-surface">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-bg-elevated/50 transition-colors"
      >
        <span className="flex items-center justify-center w-7 h-7 rounded-full bg-accent/10 text-xs font-mono font-bold text-accent shrink-0">
          {index + 1}
        </span>
        <span className="flex-1 text-sm font-medium text-text-primary">
          {question.question}
        </span>
        {expanded ? (
          <ChevronDown size={16} className="text-text-secondary shrink-0" />
        ) : (
          <ChevronRight size={16} className="text-text-secondary shrink-0" />
        )}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-border">
          {/* STAR sections */}
          <div className="mt-3">
            <StarSection label="SITUATION" text={question.star_answer.situation} color="text-accent" />
            <StarSection label="TASK" text={question.star_answer.task} color="text-success" />
            <StarSection label="ACTION" text={question.star_answer.action} color="text-warning" />
            <StarSection label="RESULT" text={question.star_answer.result} color="text-text-primary" />
          </div>

          <div className="my-3 border-t border-border" />

          {/* Your Answer */}
          <div>
            <label className="text-xs font-semibold text-text-secondary font-mono mb-1 block">
              YOUR ANSWER
            </label>
            <textarea
              value={yourAnswer}
              onChange={(e) => setYourAnswer(e.target.value)}
              placeholder="Write your own version for practice..."
              rows={3}
              className="w-full bg-bg-base border border-border rounded-md px-3 py-2 text-sm text-text-primary placeholder-text-secondary outline-none focus:border-accent/50 transition-colors resize-none"
            />
          </div>
        </div>
      )}
    </div>
  );
}

function AccordionSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="h-14 skeleton-shimmer rounded-lg"
        />
      ))}
    </div>
  );
}

export function InterviewAccordion({ questions, isLoading }: InterviewAccordionProps) {
  const handleCopyAll = () => {
    const text = questions
      .map(
        (q, i) =>
          `Q${i + 1}: ${q.question}\n\nSituation: ${q.star_answer.situation}\nTask: ${q.star_answer.task}\nAction: ${q.star_answer.action}\nResult: ${q.star_answer.result}\n\n---\n`,
      )
      .join('\n');

    navigator.clipboard.writeText(text).catch(() => {});
  };

  if (isLoading) {
    return (
      <div className="mt-8 max-w-2xl mx-auto">
        <AccordionSkeleton />
      </div>
    );
  }

  if (questions.length === 0) return null;

  return (
    <div className="mt-8 max-w-2xl mx-auto">
      {/* Copy button */}
      <div className="flex justify-end mb-3">
        <button
          onClick={handleCopyAll}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-surface border border-border text-xs text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
        >
          <Copy size={14} />
          Copy All Q&As
        </button>
      </div>

      {/* Accordion list */}
      <div className="space-y-3">
        {questions.map((q, i) => (
          <AccordionCard key={i} question={q} index={i} />
        ))}
      </div>
    </div>
  );
}
