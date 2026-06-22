import { create } from 'zustand';
import type { ResumeStage } from '../types/api';
import { stripTrailingCommentary } from '../utils/cleanup';

interface ResumeState {
  file: File | null;
  jobDescription: string;
  stage: ResumeStage;
  atsScore: number | null;
  matchedSkills: string[];
  missingSkills: string[];
  streamedResume: string;
  tailoredResume: string;
  isStreaming: boolean;
  error: string | null;

  // Actions
  setFile: (file: File | null) => void;
  setJobDescription: (jd: string) => void;
  setStage: (stage: ResumeStage) => void;
  setAtsData: (score: number, matched: string[], missing: string[]) => void;
  appendToken: (text: string) => void;
  setComplete: (resume: string) => void;
  setStreaming: (streaming: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useResumeStore = create<ResumeState>((set) => ({
  file: null,
  jobDescription: '',
  stage: 'idle',
  atsScore: null,
  matchedSkills: [],
  missingSkills: [],
  streamedResume: '',
  tailoredResume: '',
  isStreaming: false,
  error: null,

  setFile: (file) => set({ file, error: null }),

  setJobDescription: (jd) => set({ jobDescription: jd }),

  setStage: (stage) => set({ stage }),

  setAtsData: (score, matched, missing) =>
    set({ atsScore: score, matchedSkills: matched, missingSkills: missing }),

  appendToken: (text) =>
    set((state) => ({ streamedResume: state.streamedResume + text })),

  setComplete: (resume) =>
    set({
      stage: 'complete',
      tailoredResume: stripTrailingCommentary(resume),
      streamedResume: stripTrailingCommentary(resume),
      isStreaming: false,
    }),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  setError: (error) => set({ error, stage: 'error', isStreaming: false }),

  reset: () =>
    set({
      file: null,
      jobDescription: '',
      stage: 'idle',
      atsScore: null,
      matchedSkills: [],
      missingSkills: [],
      streamedResume: '',
      tailoredResume: '',
      isStreaming: false,
      error: null,
    }),
}));
