import { useState, useEffect } from 'react';
import useApiService from './useApiService';

interface InterviewPrepResponse {
  interview_prep: string;
}

export interface InterviewPrepHookResult {
  isLoading: boolean;
  error: string | null;
  interviewPrep: string;
  generateInterviewPrep: (jobDescription: string, cvFile?: File | null) => Promise<void>;
}

export const useInterviewPrep = (): InterviewPrepHookResult => {
  const [interviewPrep, setInterviewPrep] = useState<string>('');
  
  const {
    data,
    isLoading,
    error,
    execute,
  } = useApiService<InterviewPrepResponse>({ endpoint: '/career/interview-prep' });

  useEffect(() => {
    if (data) {
      setInterviewPrep(data.interview_prep || '');
    }
  }, [data]);

  const generateInterviewPrep = async (jobDescription: string, cvFile?: File | null) => {
    if (!jobDescription || jobDescription.trim().length < 50) {
      throw new Error('Job description must be at least 50 characters');
    }

    const formData = new FormData();
    formData.append('job_description', jobDescription);

    if (cvFile) {
      formData.append('cv_file', cvFile);
    }

    await execute(formData);
  };

  return {
    isLoading,
    error,
    interviewPrep,
    generateInterviewPrep,
  };
};

export default useInterviewPrep;
