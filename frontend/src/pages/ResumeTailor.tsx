import { type FC, useState, useMemo, useCallback } from 'react';
import ResumeUpload from '../components/ResumeUpload';
import JobDescriptionForm from '../components/JobDescriptionForm';
import StreamingOutput from '../components/StreamingOutput';
import TextOutput from '../components/TextOutput';
import useResumeTailor from '../hooks/useResumeTailor';
import useCoverLetter from '../hooks/useCoverLetter';
import useInterviewPrep from '../hooks/useInterviewPrep';

const TABS = [
  { id: 'resume', label: 'Resume Tailor', description: 'Upload your resume and a job description to generate a tailored resume.' },
  { id: 'cover', label: 'Cover Letter', description: 'Create a targeted cover letter using your resume and the job posting.' },
  { id: 'interview', label: 'Interview Prep', description: 'Generate likely questions and STAR-style answers from the job description.' },
];

export const ResumeTailorPage: FC = () => {
  const [activeTab, setActiveTab] = useState<'resume' | 'cover' | 'interview'>('resume');
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [copyStatus, setCopyStatus] = useState<string>('');

  const { isLoading: isResumeLoading, error: resumeError, content, matchedSkills, missingSkills, atsScore, steps, tailorResume } = useResumeTailor();
  const { isLoading: isCoverLoading, error: coverError, coverLetter, generateCoverLetter } = useCoverLetter();
  const { isLoading: isInterviewLoading, error: interviewError, interviewPrep, generateInterviewPrep } = useInterviewPrep();

  const isLoading = useMemo(() => isResumeLoading || isCoverLoading || isInterviewLoading, [isResumeLoading, isCoverLoading, isInterviewLoading]);
  const error = useMemo(() => resumeError || coverError || interviewError, [resumeError, coverError, interviewError]);

  const activeTabData = useMemo(
    () => TABS.find((tab) => tab.id === activeTab),
    [activeTab]
  );

  const handleFileSelect = useCallback((file: File) => {
    setCvFile(file);
    setCopyStatus('');
  }, []);

  const handleGeneration = useCallback(async (jobDescription: string) => {
    if ((activeTab === 'resume' || activeTab === 'cover') && !cvFile) {
      alert('Please upload a resume first');
      return;
    }

    try {
      switch (activeTab) {
        case 'resume':
          await tailorResume(cvFile!, jobDescription);
          break;
        case 'cover':
          await generateCoverLetter(cvFile!, jobDescription);
          break;
        case 'interview':
          await generateInterviewPrep(jobDescription, cvFile);
          break;
      }
    } catch (err) {
      // Errors are handled by individual hooks, but a catch block is good practice
      console.error('Generation failed:', err);
    }
  }, [activeTab, cvFile, tailorResume, generateCoverLetter, generateInterviewPrep]);

  const onCopy = useCallback(() => {
    setCopyStatus('Copied to clipboard!');
    window.setTimeout(() => setCopyStatus(''), 2400);
  }, []);

  const submitLabel = useMemo(() => {
    switch (activeTab) {
      case 'resume': return 'Generate Tailored Resume';
      case 'cover': return 'Generate Cover Letter';
      case 'interview': return 'Generate Interview Prep';
      default: return 'Generate';
    }
  }, [activeTab]);

  const helperText = useMemo(() => {
    switch (activeTab) {
      case 'interview': return 'Paste the job description and optionally upload your resume for more personalized STAR answers.';
      case 'cover': return 'Upload your resume and paste the job description to create a tailored cover letter.';
      default: return 'Upload your resume and paste a job description to tailor your resume.';
    }
  }, [activeTab]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-sky-50 to-indigo-100">
      <div className="max-w-7xl mx-auto px-4 py-10">
        <div className="rounded-[2rem] bg-white/90 p-8 shadow-2xl backdrop-blur-xl border border-slate-200">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <p className="text-sm uppercase tracking-[0.3em] text-sky-600">CareerAI Suite</p>
              <h1 className="text-5xl font-semibold tracking-tight text-slate-950">Resume, Cover Letter & Interview Prep</h1>
              <p className="max-w-2xl text-base text-slate-600">
                One intelligent workspace to generate optimized resumes, persuasive cover letters, and interview-ready answers from a single job description.
              </p>
            </div>
            <div className="rounded-3xl bg-slate-950 px-5 py-4 text-white shadow-xl">
              <p className="text-xs uppercase tracking-[0.3em] text-cyan-300">Quick access</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${activeTab === tab.id ? 'bg-cyan-400 text-slate-950' : 'bg-slate-800/90 text-white hover:bg-slate-700'}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-900">{activeTabData?.label}</p>
              <h2 className="mt-3 text-3xl font-semibold text-slate-950">{activeTabData?.description}</h2>
            </div>
            <div className="rounded-3xl bg-sky-50 px-4 py-3 text-xs font-medium uppercase tracking-[0.2em] text-sky-700">
              {activeTab === 'interview' ? 'Job description only required' : 'Resume upload required'}
            </div>
          </div>
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-3">
          <div className="rounded-3xl bg-white shadow-xl border border-slate-200 p-8 space-y-8">
            <ResumeUpload onFileSelect={handleFileSelect} isLoading={isLoading} />
            {cvFile ? (
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-slate-700">
                <p className="text-sm font-medium">Resume loaded:</p>
                <p className="mt-1 text-sm text-slate-600 break-words">{cvFile.name}</p>
              </div>
            ) : (
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-slate-600">
                <p className="text-sm">Upload a PDF resume to power the Resume Tailor and Cover Letter flows. Interview Prep works with job description alone.</p>
              </div>
            )}
          </div>

          <div className="rounded-3xl bg-white shadow-xl border border-slate-200 p-8">
            <JobDescriptionForm
              onSubmit={handleGeneration}
              isLoading={isLoading}
              disabled={activeTab === 'cover' && !cvFile}
              submitLabel={submitLabel}
              helperText={helperText}
            />
          </div>
        </div>

        <div className="space-y-6 mt-10">
          {activeTab === 'resume' && (
            <div className="rounded-3xl bg-white shadow-xl border border-slate-200 p-8 space-y-6">
              {(matchedSkills.length > 0 || missingSkills.length > 0 || atsScore !== null) && (
                <div className="space-y-4">
                  {atsScore !== null && (
                    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="text-sm uppercase tracking-[0.2em] text-slate-500">ATS Match</p>
                          <p className="mt-2 text-3xl font-semibold text-slate-900">{atsScore}%</p>
                        </div>
                        <div className="h-24 w-24 rounded-full border-4 border-slate-200 grid place-items-center text-lg font-semibold text-slate-900">
                          {atsScore}%
                        </div>
                      </div>
                      <p className="mt-3 text-sm text-slate-600">AI analysis of how well your current resume aligns with the job description.</p>
                    </div>
                  )}
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="rounded-3xl bg-emerald-50 p-5 border border-emerald-100">
                      <h3 className="text-sm font-semibold text-emerald-900">Matched skills</h3>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {matchedSkills.length ? matchedSkills.map((skill, idx) => (
                          <span key={idx} className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-900">{skill}</span>
                        )) : <span className="text-sm text-emerald-800">No strong matches found yet</span>}
                      </div>
                    </div>
                    <div className="rounded-3xl bg-rose-50 p-5 border border-rose-100">
                      <h3 className="text-sm font-semibold text-rose-900">Skills gap</h3>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {missingSkills.length ? missingSkills.map((skill, idx) => (
                          <span key={idx} className="rounded-full bg-rose-100 px-3 py-1 text-xs font-medium text-rose-900">{skill}</span>
                        )) : <span className="text-sm text-rose-800">No missing requirements detected</span>}
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <StreamingOutput content={content} steps={steps} isStreaming={isResumeLoading} error={resumeError} />
            </div>
          )}

          {activeTab === 'cover' && (
            <div className="rounded-3xl bg-white shadow-xl border border-slate-200 p-8">
              <TextOutput
                title="Generated Cover Letter"
                content={coverLetter}
                isLoading={isCoverLoading}
                error={coverError}
                actionLabel="Copy cover letter"
                onCopy={onCopy}
              />
              {copyStatus && <p className="mt-4 text-sm text-slate-500">{copyStatus}</p>}
            </div>
          )}

          {activeTab === 'interview' && (
            <div className="rounded-3xl bg-white shadow-xl border border-slate-200 p-8">
              <TextOutput
                title="Interview Prep"
                content={interviewPrep}
                isLoading={isInterviewLoading}
                error={interviewError}
                actionLabel="Copy interview prep"
                onCopy={onCopy}
              />
              {copyStatus && <p className="mt-4 text-sm text-slate-500">{copyStatus}</p>}
            </div>
          )}
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-3">
          <div className="rounded-3xl bg-white border border-slate-200 p-8 shadow-lg">
            <h3 className="text-xl font-semibold text-slate-900">AI-Driven Workflow</h3>
            <p className="mt-3 text-sm text-slate-600">Upload a resume and paste the job description. Our AI pipeline parses both documents and creates context-aware outputs for your job search.</p>
          </div>
          <div className="rounded-3xl bg-white border border-slate-200 p-8 shadow-lg">
            <h3 className="text-xl font-semibold text-slate-900">Cover Letter First Draft</h3>
            <p className="mt-3 text-sm text-slate-600">Generate a polished cover letter tailored to the role and your resume. Use it to personalize applications in seconds.</p>
          </div>
          <div className="rounded-3xl bg-white border border-slate-200 p-8 shadow-lg">
            <h3 className="text-xl font-semibold text-slate-900">STAR Interview Answers</h3>
            <p className="mt-3 text-sm text-slate-600">Create a list of likely questions and structured STAR answers to prepare for interviews with confidence.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResumeTailorPage;

