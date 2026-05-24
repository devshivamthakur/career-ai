import { useState } from 'react';
import { API_BASE_URL } from '../api/client';

interface ResumeTailorHookResult {
  uploadedResume: string | null;
  isLoading: boolean;
  error: string | null;
  stream: ReadableStream<Uint8Array> | null;
  uploadResume: (text: string) => Promise<void>;
  tailorResume: (masterResume: string, jobDescription: string) => Promise<ReadableStream<Uint8Array>>;
}

export const useResumeTailor = (): ResumeTailorHookResult => {
  const [uploadedResume, setUploadedResume] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [stream, setStream] = useState<ReadableStream<Uint8Array> | null>(null);

  const uploadResume = async (text: string) => {
    setIsLoading(true);
    setError(null);
    try {
      // Store the resume text for later use
      setUploadedResume(text);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsLoading(false);
    }
  };

  const tailorResume = async (
    masterResume: string,
    jobDescription: string
  ): Promise<ReadableStream<Uint8Array>> => {
    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('master_resume', masterResume);
      formData.append('job_description', jobDescription);

      const response = await fetch(`${API_BASE_URL}/resume/tailor/stream`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      setStream(response.body);
      return response.body;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Tailoring failed';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  return {
    uploadedResume,
    isLoading,
    error,
    stream,
    uploadResume,
    tailorResume,
  };
};

export default useResumeTailor;
