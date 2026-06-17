import { Loader2, CheckCircle2 } from 'lucide-react';
import type { ResumeStage } from '../../types/api';
import { ATSScoreRing } from './ATSScoreRing';
import { SkillBadges } from './SkillBadges';
import { StreamingText } from '../shared/StreamingText';
import { Skeleton } from '../shared/Skeleton';

interface StageSectionProps {
  number: number;
  title: string;
  status: 'pending' | 'active' | 'done';
  children?: React.ReactNode;
}

function StageSection({ number, title, status, children }: StageSectionProps) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-accent/10 text-xs font-mono font-bold text-accent">
          {number}
        </span>
        <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
        {status === 'active' && <Loader2 size={14} className="text-accent animate-spin" />}
        {status === 'done' && <CheckCircle2 size={14} className="text-success" />}
      </div>
      {children}
    </div>
  );
}

interface ResumeStagesProps {
  stage: ResumeStage;
  atsScore: number | null;
  matchedSkills: string[];
  missingSkills: string[];
  streamedResume: string;
  isStreaming: boolean;
  tailoredResume: string;
  onExportPdf: () => void;
  onCopyResume: () => void;
}

export function ResumeStages({
  stage,
  atsScore,
  matchedSkills,
  missingSkills,
  streamedResume,
  isStreaming,
  tailoredResume,
  onExportPdf,
  onCopyResume,
}: ResumeStagesProps) {
  // Empty state
  if (stage === 'idle') {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-sm">
          <p className="text-sm text-text-secondary">
            Upload your resume and paste a job description to get started.
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (stage === 'error') {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-sm">
          <p className="text-sm text-danger">An error occurred during processing.</p>
          <p className="text-xs text-text-secondary mt-1">Please try again.</p>
        </div>
      </div>
    );
  }

  const isAnalyzing = stage === 'analyzing';
  const isSkills = stage === 'skills' || (stage === 'rewriting' && atsScore !== null) || (stage === 'complete' && atsScore !== null);
  const isRewriting = stage === 'rewriting' || (stage === 'complete' && streamedResume);
  const isComplete = stage === 'complete';

  return (
    <div className="p-6 overflow-y-auto h-full">
      {/* Stage 1: Analyzing */}
      <StageSection
        number={1}
        title="Analyzing"
        status={isAnalyzing ? 'active' : 'done'}
      >
        {isAnalyzing && (
          <div className="space-y-2">
            <Skeleton count={3} height="12px" />
          </div>
        )}
      </StageSection>

      {/* Stage 2: Skills Match */}
      <StageSection
        number={2}
        title="Skills Match"
        status={isSkills && isComplete ? 'done' : isSkills ? 'active' : 'pending'}
      >
        {isSkills && atsScore !== null && (
          <div className="flex flex-col items-center mb-4">
            <div className="relative flex items-center justify-center mb-2" style={{ width: 120, height: 120 }}>
              <ATSScoreRing score={atsScore} size={120} animated />
            </div>

            <div className="w-full mt-4">
              <SkillBadges skills={matchedSkills} type="matched" />
              <SkillBadges skills={missingSkills} type="missing" />
            </div>
          </div>
        )}
      </StageSection>

      {/* Stage 3: Rewriting */}
      <StageSection
        number={3}
        title="Rewriting"
        status={isRewriting && isComplete ? 'done' : isRewriting ? 'active' : 'pending'}
      >
        {isRewriting && streamedResume && (
          <div className="bg-bg-base rounded-lg p-4 border border-border">
            <div className="text-sm font-mono leading-relaxed whitespace-pre-wrap">
              <StreamingText text={streamedResume} isStreaming={isStreaming && !isComplete} />
            </div>
          </div>
        )}
      </StageSection>

      {/* Stage 4: Polished Resume */}
      <StageSection
        number={4}
        title="Polished Resume"
        status={isComplete ? 'done' : 'pending'}
      >
        {isComplete && tailoredResume && (
          <div>
            <div className="bg-bg-surface rounded-lg p-6 border border-border mb-4">
              <pre className="text-sm font-mono leading-relaxed whitespace-pre-wrap text-text-primary">
                {tailoredResume}
              </pre>
            </div>

            <div className="flex gap-3">
              <button
                onClick={onExportPdf}
                className="px-4 py-2 rounded-lg border border-accent text-accent text-sm font-medium hover:bg-accent/10 transition-colors"
              >
                Export as PDF
              </button>
              <button
                onClick={onCopyResume}
                className="px-4 py-2 rounded-lg border border-border text-text-secondary text-sm font-medium hover:text-text-primary hover:bg-bg-elevated transition-colors"
              >
                Copy to clipboard
              </button>
            </div>
          </div>
        )}
      </StageSection>
    </div>
  );
}
