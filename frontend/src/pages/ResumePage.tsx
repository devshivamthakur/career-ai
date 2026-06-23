import { useCallback, useEffect } from 'react';
import { useResumeStore } from '../stores/resumeStore';
import { useResumeStream } from '../hooks/useResumeStream';
import { useToastStore } from '../stores/toastStore';
import { PDFDropZone } from '../components/resume/PDFDropZone';
import { ResumeStages } from '../components/resume/ResumeStages';
import { exportPdf } from '../api/client';

export default function ResumePage() {
  const {
    file,
    jobDescription,
    stage,
    atsScore,
    matchedSkills,
    missingSkills,
    streamedResume,
    isStreaming,
    tailoredResume,
    setFile,
    setJobDescription,
  } = useResumeStore();

  const { startStream, stopStream } = useResumeStream();
  const showToast = useToastStore((s) => s.showToast);

  // Abort any in-flight stream when navigating away
  useEffect(() => {
    return () => stopStream();
  }, [stopStream]);

  const canTailor = file !== null && jobDescription.trim().length >= 50 && !isStreaming;

  const handleTailor = useCallback(() => {
    if (!canTailor) return;
    startStream();
  }, [canTailor, startStream]);

  const handleExportPdf = useCallback(async () => {
    try {
      const blob = await exportPdf(tailoredResume);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'tailored_resume.pdf';
      a.click();
      URL.revokeObjectURL(url);
      showToast('PDF exported successfully', 'success');
    } catch {
      showToast('Failed to export PDF', 'error');
    }
  }, [tailoredResume, showToast]);

  const handleCopyResume = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(tailoredResume);
      showToast('Copied to clipboard', 'success');
    } catch {
      showToast('Failed to copy', 'error');
    }
  }, [tailoredResume, showToast]);

  return (
    <div className="flex flex-col lg:flex-row h-full">
      {/* Left panel — Input */}
      <div className="lg:w-[420px] shrink-0 p-6 border-r border-border overflow-y-auto">
        <div className="space-y-5">
          {/* PDF Drop Zone */}
          <div>
            <label className="block text-xs font-semibold text-text-secondary mb-2 font-mono">
              RESUME PDF
            </label>
            <PDFDropZone
              onFileSelect={setFile}
              currentFile={file}
              disabled={isStreaming}
            />
          </div>

          {/* Job Description */}
          <div>
            <label className="block text-xs font-semibold text-text-secondary mb-2 font-mono">
              JOB DESCRIPTION
            </label>
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the full job description here..."
              rows={10}
              disabled={isStreaming}
              maxLength={5000}
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-secondary outline-none focus:border-accent/50 transition-colors resize-none disabled:opacity-50"
            />
            <div className="flex justify-end mt-1">
              <span
                className={`text-xs font-mono ${
                  jobDescription.length >= 4500
                    ? 'text-warning'
                    : 'text-text-secondary'
                }`}
              >
                {jobDescription.length} / 5000
              </span>
            </div>
          </div>

          {/* Tailor button */}
          <button
            onClick={canTailor ? handleTailor : undefined}
            disabled={!canTailor}
            className="w-full py-2.5 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/80 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isStreaming ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Analyzing...
              </>
            ) : (
              'Tailor My Resume'
            )}
          </button>
        </div>
      </div>

      {/* Right panel — Streaming Result */}
      <div className="flex-1 min-w-0 overflow-hidden">
        <ResumeStages
          stage={stage}
          atsScore={atsScore}
          matchedSkills={matchedSkills}
          missingSkills={missingSkills}
          streamedResume={streamedResume}
          isStreaming={isStreaming}
          tailoredResume={tailoredResume}
          onExportPdf={handleExportPdf}
          onCopyResume={handleCopyResume}
        />
      </div>
    </div>
  );
}
