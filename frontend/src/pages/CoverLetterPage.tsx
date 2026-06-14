import { useState, useCallback, useRef } from 'react';
import { generateCoverLetterUrl } from '../api/client';
import { useSseStream } from '../hooks/useSseStream';
import { useToastStore } from '../stores/toastStore';
import { CoverLetterResult } from '../components/career/CoverLetterResult';
import { PDFDropZone } from '../components/resume/PDFDropZone';

export function CoverLetterPage() {
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [personalize, setPersonalize] = useState(false);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [streamedText, setStreamedText] = useState('');
  const accumulatedRef = useRef('');

  const showToast = useToastStore((s) => s.showToast);
  const { start, isStreaming } = useSseStream();

  const canGenerate =
    company.trim().length > 0 &&
    role.trim().length > 0 &&
    jobDescription.trim().length >= 50 &&
    (!personalize || resumeFile !== null) &&
    !isStreaming;

  const handleGenerate = useCallback(async () => {
    if (!canGenerate) return;

    setResult(null);
    setStreamedText('');
    accumulatedRef.current = '';

    const resumeText = resumeFile ? await resumeFile.text() : undefined;

    start({
      url: generateCoverLetterUrl(),
      body: {
        job_description: jobDescription,
        company,
        role,
        resume_text: resumeText,
      },
      onEvent: (type, data) => {
        const d = data as { content?: string };
        if (type === 'token' && d.content) {
          accumulatedRef.current += d.content;
          setStreamedText(accumulatedRef.current);
        } else if (type === 'error') {
          showToast(d.content ?? 'Failed to generate cover letter', 'error');
        }
      },
      onComplete: () => {
        setResult(accumulatedRef.current);
        setStreamedText('');
      },
      onError: (error) => {
        showToast(error, 'error');
      },
    });
  }, [canGenerate, jobDescription, company, role, resumeFile, start, showToast]);

  return (
    <div className="overflow-y-auto h-full">
      <div className="max-w-2xl mx-auto px-6 py-8">
        {/* Form */}
        <div className="space-y-5">
          {/* Company Name */}
          <div>
            <label className="block text-xs font-semibold text-text-secondary mb-2 font-mono">
              COMPANY NAME
            </label>
            <input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="e.g. Acme Corp"
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder-text-secondary outline-none focus:border-accent/50 transition-colors"
            />
          </div>

          {/* Job Title */}
          <div>
            <label className="block text-xs font-semibold text-text-secondary mb-2 font-mono">
              JOB TITLE
            </label>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g. Senior Software Engineer"
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder-text-secondary outline-none focus:border-accent/50 transition-colors"
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
              rows={8}
              maxLength={5000}
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-secondary outline-none focus:border-accent/50 transition-colors resize-none"
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

          {/* Personalize toggle */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setPersonalize(!personalize)}
              className={`relative w-10 h-5 rounded-full transition-colors ${
                personalize ? 'bg-accent' : 'bg-border'
              }`}
            >
              <span
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                  !personalize ? 'translate-x-[-22px]' : 'translate-x-0.5'
                }`}
              />
            </button>
            <label className="text-sm text-text-primary cursor-pointer">
              Personalize with my resume
            </label>
          </div>

          {/* PDF upload (when personalized) */}
          {personalize && (
            <PDFDropZone
              onFileSelect={setResumeFile}
              currentFile={resumeFile}
            />
          )}

          {/* Generate button */}
          <button
            onClick={canGenerate ? handleGenerate : undefined}
            disabled={!canGenerate}
            className="w-full py-2.5 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/80 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isStreaming ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Generating...
              </>
            ) : (
              'Generate Cover Letter'
            )}
          </button>
        </div>

        {/* Result */}
        <CoverLetterResult
          coverLetter={result}
          streamedText={streamedText}
          isStreaming={isStreaming}
          isLoading={false}
          company={company}
          role={role}
          onRegenerate={handleGenerate}
        />
      </div>
    </div>
  );
}
