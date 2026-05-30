import { useState, useEffect } from 'react';
import useApiService from './useApiService';

interface CoverLetterResponse {
  cover_letter: string;
}

export interface CoverLetterHookResult {
  isLoading: boolean;
  error: string | null;
  coverLetter: string;
  generateCoverLetter: (cvFile: File, jobDescription: string) => Promise<void>;
}

export const useCoverLetter = (): CoverLetterHookResult => {
  const [coverLetter, setCoverLetter] = useState<string>('');
  
  const {
    data,
    isLoading,
    error,
    execute,
  } = useApiService<CoverLetterResponse>({ endpoint: '/career/cover-letter' });

  useEffect(() => {
    if (data) {
      setCoverLetter(data.cover_letter || '');
    }
  }, [data]);

  const generateCoverLetter = async (cvFile: File, jobDescription: string) => {
    if (!cvFile || cvFile.type !== 'application/pdf') {
      throw new Error('A valid PDF resume is required');
    }
    if (!jobDescription || jobDescription.trim().length < 50) {
      throw new Error('Job description must be at least 50 characters');
    }

    const formData = new FormData();
    formData.append('cv_file', cvFile);
    formData.append('job_description', jobDescription);

    await execute(formData);
  };

  return {
    isLoading,
    error,
    coverLetter,
    generateCoverLetter,
  };
};

export default useCoverLetter;
