import { useState } from 'react';
import { Loader2, CheckCircle2, XCircle, ChevronDown, ChevronRight } from 'lucide-react';
import type { ToolCallInfo } from '../../types/api';

interface ToolCallCardProps {
  toolCall: ToolCallInfo;
}

export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);

  const statusIcon = () => {
    switch (toolCall.status) {
      case 'running':
        return <Loader2 size={16} className="text-accent animate-spin" />;
      case 'done':
        return <CheckCircle2 size={16} className="text-success" />;
      case 'error':
        return <XCircle size={16} className="text-danger" />;
    }
  };

  const statusText = () => {
    switch (toolCall.status) {
      case 'running':
        return 'Running...';
      case 'done':
        return `Completed${toolCall.duration ? ` in ${toolCall.duration.toFixed(1)}s` : ''}`;
      case 'error':
        return 'Failed';
    }
  };

  return (
    <div className="my-2 rounded-lg border border-border bg-bg-elevated overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2">
        {statusIcon()}
        <span className="text-xs font-mono text-text-primary font-medium">{toolCall.toolName}</span>
        <span className={`text-xs font-mono ml-auto ${
          toolCall.status === 'running' ? 'text-accent'
          : toolCall.status === 'done' ? 'text-success'
          : 'text-danger'
        }`}>
          {statusText()}
        </span>
        {toolCall.output && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-text-secondary hover:text-text-primary transition-colors"
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        )}
      </div>

      {/* Expanded output */}
      {expanded && toolCall.output && (
        <pre className="m-2 p-3 rounded-md bg-bg-base text-xs font-mono text-text-secondary overflow-auto max-h-[200px] border border-border">
          {toolCall.output}
        </pre>
      )}
    </div>
  );
}
