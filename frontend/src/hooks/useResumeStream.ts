import { useCallback } from 'react';
import { useResumeStore } from '../stores/resumeStore';
import { useToastStore } from '../stores/toastStore';
import { useSseStream } from './useSseStream';

const API_ORIGIN = import.meta.env.VITE_API_URL ?? '';
const STREAM_URL = API_ORIGIN
  ? `${API_ORIGIN}/api/resume/tailor/stream`
  : '/api/resume/tailor/stream';

export function useResumeStream() {
  const { start, stop, isStreaming } = useSseStream();
  const showToast = useToastStore((s) => s.showToast);

  const {
    file,
    jobDescription,
    setStage,
    setAtsData,
    appendToken,
    setComplete,
    setStreaming,
    setError,
  } = useResumeStore();

  const startStream = useCallback(() => {
    if (!file) return;

    // Reset state
    useResumeStore.getState().reset();
    useResumeStore.getState().setFile(file);
    useResumeStore.getState().setJobDescription(jobDescription);
    setStreaming(true);

    const formData = new FormData();
    formData.append('resume_pdf', file);
    formData.append('job_description', jobDescription);

    start({
      url: STREAM_URL,
      body: formData,
      onEvent: (type, data) => {
        const d = data as Record<string, unknown>;
        console.log('Stream event:', type, d);
        switch (type) {
          case 'step_start': {
            const nodeName = (d as { node?: string }).node ?? '';
            if (nodeName.includes('analyze')) setStage('analyzing');
            else if (nodeName.includes('compare_skills') || nodeName.includes('ats')) setStage('skills');
            else if (nodeName.includes('rewrite')) setStage('rewriting');
            break;
          }
          
          case "step_end":  {
            const nodeName = (d as { node?: string }).node ?? '';
            if(nodeName === "compare_skills"){

               const atsData = d as {
              ats_score?: number;
              matched_skills?: string[];
              missing_skills?: string[];
            };
            setAtsData(
              atsData.ats_score ?? 0,
              atsData.matched_skills ?? [],
              atsData.missing_skills ?? [],
            );
            setStage('skills');
            }
            break;
          }
          case 'token': {
            const tokenData = d as { content?: string };
            if (tokenData.content) {
              appendToken(tokenData.content);
            }
            break;
          }

          case 'ats_score': {
            const atsData = d as {
              score?: number;
              matched_skills?: string[];
              missing_skills?: string[];
            };
            setAtsData(
              atsData.score ?? 0,
              atsData.matched_skills ?? [],
              atsData.missing_skills ?? [],
            );
            setStage('skills');
            break;
          }

          case 'node_complete': {
            const nodeData = d as { node_name?: string };
            if (nodeData.node_name?.includes('rewrite')) {
              setStage('rewriting');
            }
            break;
          }

          case 'completed': {
            setComplete(useResumeStore.getState().streamedResume);
            break;
          }

          case 'error': {
            const errData = d as { message?: string };
            setError(errData.message ?? 'An error occurred');
            showToast(errData.message ?? 'An error occurred', 'error');
            break;
          }
        }
      },
      onComplete: () => {
        setComplete(useResumeStore.getState().streamedResume);
      },
      onError: (error) => {
        setError(error);
        showToast(error, 'error');
      },
    });
  }, [file, jobDescription, start, setStage, setAtsData, appendToken, setComplete, setStreaming, setError, showToast]);

  return { startStream, stopStream: stop, isStreaming };
}
