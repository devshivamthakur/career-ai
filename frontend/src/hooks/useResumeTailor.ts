import { useState } from 'react';
import { API_BASE_URL } from '../api/client';
import { fetchEventSource } from '@microsoft/fetch-event-source';

export interface TailorStep {
  id: string;
  label: string;
  status: 'pending' | 'in-progress' | 'completed' | 'error';
}

export interface ResumeTailorHookResult {
  isLoading: boolean;
  error: string | null;
  content: string;
  matchedSkills: string[];
  missingSkills: string[];
  atsScore: number | null;
  steps: TailorStep[];
  tailorResume: (cvFile: File, jobDescription: string) => Promise<void>;
}

const INITIAL_STEPS: TailorStep[] = [
  { id: 'compare_skills', label: 'Comparing Skills', status: 'pending' },
  { id: 'polish_resume', label: 'Generating Tailored Resume', status: 'pending' },
];

export const useResumeTailor = (): ResumeTailorHookResult => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [content, setContent] = useState<string>('');
  const [matchedSkills, setMatchedSkills] = useState<string[]>([]);
  const [missingSkills, setMissingSkills] = useState<string[]>([]);
  const [atsScore, setAtsScore] = useState<number | null>(null);
  const [steps, setSteps] = useState<TailorStep[]>(INITIAL_STEPS);

  const tailorResume = async (
    cvFile: File,
    jobDescription: string
  ): Promise<void> => {
    setIsLoading(true);
    setError(null);
    setContent('');
    setMatchedSkills([]);
    setMissingSkills([]);
    setAtsScore(null);
    setSteps(INITIAL_STEPS.map(step => ({ ...step, status: 'pending' })));

    try {
      if (!cvFile || cvFile.type !== 'application/pdf') {
        throw new Error("A valid PDF CV file is required");
      }
      if (!jobDescription || jobDescription.trim().length < 50) {
        throw new Error("Job description must be at least 50 characters");
      }

      const formData = new FormData();
      formData.append('cv_file', cvFile);
      formData.append('job_description', jobDescription);

      await fetchEventSource(`${API_BASE_URL}/resume/tailor/stream`, {
        method: 'POST',
        body: formData,
        openWhenHidden: true, // Keep connection alive when tab is in background
        onopen: async (response) => {
          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP Error: ${response.status}` }));
            let errorMessage;
            if (response.status === 422) {
              errorMessage = `Invalid Job Description: ${errorData.detail}`;
            } else {
              errorMessage = errorData.detail || `HTTP Error: ${response.status}`;
            }
            throw new Error(errorMessage);
          }
        },
        
        onmessage: (event) => {
          // Handle backend keep-alive empty messages to prevent disconnects
          if (event.data === '') return;

          try {
            const data = JSON.parse(event.data);
            
            // Events are now directly in the data object (not nested in data.content)
            const eventType = data.type;

            switch (eventType) {
              case 'step_start':
                setSteps((prevSteps) =>
                  prevSteps.map((step) =>
                    step.id === data.node
                      ? { ...step, status: 'in-progress' }
                      : step
                  )
                );
                break;
              case 'step_end':
                setSteps((prevSteps) =>
                  prevSteps.map((step) =>
                    step.id === data.node
                      ? { ...step, status: 'completed' }
                      : step
                  )
                );
                if (data.matched_skills) {
                  setMatchedSkills(data.matched_skills);
                }
                if (data.missing_skills) {
                  setMissingSkills(data.missing_skills);
                }
                if (data.ats_score !== undefined) {
                  setAtsScore(data.ats_score);
                }
                if (data.final_result) {
                  setContent(data.final_result);
                }
                break;
              case 'complete':
                setIsLoading(false);
                break;
              case 'error':
                setSteps((prevSteps) =>
                  prevSteps.map((step) =>
                    step.status === 'in-progress'
                      ? { ...step, status: 'error' }
                      : step
                  )
                );
                throw new Error(data.data || "Unknown error from server");
            }
          } catch (e) {
            console.error('Failed to parse stream data:', e);
            throw e; 
          }
        },
        
        onclose: () => {
          setIsLoading(false);
        },
        
        onerror: (err) => {
          const errorMsg = err.message || 'Streaming failed';
          console.error('Streaming error:', err);
          setError(errorMsg);
          setIsLoading(false);
          throw err;
        },
      });

    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'An unknown error occurred';
      setError(errorMsg);
      setIsLoading(false);
    }
  };

  return {
    isLoading,
    error,
    content,
    matchedSkills,
    missingSkills,
    atsScore,
    steps,
    tailorResume,
  };
};

export default useResumeTailor;
