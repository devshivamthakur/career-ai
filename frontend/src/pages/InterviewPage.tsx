import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { generateInterviewPrep } from '../api/client';
import { useToastStore } from '../stores/toastStore';
import { InterviewAccordion } from '../components/career/InterviewAccordion';
import { PDFDropZone } from '../components/resume/PDFDropZone';
import type { InterviewQuestion } from '../types/api';

export function InterviewPage() {
  const [role, setRole] = useState('');
  const [company, setCompany] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [includeResume, setIncludeResume] = useState(false);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);

  const showToast = useToastStore((s) => s.showToast);

  const mutation = useMutation({
    mutationFn: async () => {
      const resumeText = resumeFile ? await resumeFile.text() : undefined;
      return generateInterviewPrep({
        job_description: jobDescription,
        role,
        company: company || undefined,
        resume_text: resumeText,
      });
    },
    onSuccess: (data) => {
      setQuestions(data.questions);
    },
    onError: (err) => {
      showToast(
        err instanceof Error ? err.message : 'Failed to generate interview prep',
        'error',
      );
    },
  });

  const canGenerate =
    role.trim().length > 0 &&
    jobDescription.trim().length >= 50 &&
    (!includeResume || resumeFile !== null) &&
    !mutation.isPending;

  const handleGenerate = () => {
    if (!canGenerate) return;
    setQuestions([]);
    mutation.mutate();
  };

  return (
    <div className="overflow-y-auto h-full">
      <div className="max-w-2xl mx-auto px-6 py-8">
        {/* Form */}
        <div className="space-y-5">
          {/* Job Title */}
          <div>
            <label className="block text-xs font-semibold text-text-secondary mb-2 font-mono">
              JOB TITLE
            </label>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g. Senior Frontend Engineer"
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder-text-secondary outline-none focus:border-accent/50 transition-colors"
            />
          </div>

          {/* Company */}
          <div>
            <label className="block text-xs font-semibold text-text-secondary mb-2 font-mono">
              COMPANY <span className="text-text-secondary font-normal">(optional)</span>
            </label>
            <input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Optional — personalizes answers"
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

          {/* Include resume toggle */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIncludeResume(!includeResume)}
              className={`relative w-10 h-5 rounded-full transition-colors ${
                includeResume ? 'bg-accent' : 'bg-border'
              }`}
            >
              <span
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                  !includeResume ? 'translate-x-[-22px]' : 'translate-x-0.5'
                }`}
              />
            </button>
            <label className="text-sm text-text-primary cursor-pointer">
              Include my resume for personalized answers
            </label>
          </div>

          {/* PDF upload */}
          {includeResume && (
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
            {mutation.isPending ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Generating...
              </>
            ) : (
              'Generate Interview Prep'
            )}
          </button>
        </div>

        {/* Result */}
        <InterviewAccordion
          questions={questions}
          isLoading={mutation.isPending}
        />
      </div>
    </div>
  );
}
