// ─── Message Types ───────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  toolCalls?: ToolCallInfo[];
  resumeContent?: string;
  /** Path to an uploaded file (e.g. "storage/resume_xxx.pdf") stored on the backend */
  file?: string;
}

export interface ToolCallInfo {
  id: string;
  toolName: string;
  status: 'running' | 'done' | 'error';
  output?: string;
  duration?: number;
}

// ─── API Request/Response Types ─────────────────────────────

export interface CreateSessionResponse {
  session_id: string;
}

export interface SessionMessagesResponse {
  messages: ChatMessage[];
}

export interface CoverLetterRequest {
  job_description: string;
  company: string;
  role: string;
  resume_text?: string;
}

export interface CoverLetterResponse {
  cover_letter: string;
}

export interface InterviewPrepRequest {
  job_description: string;
  role: string;
  company?: string;
  resume_text?: string;
}

export interface StarAnswer {
  situation: string;
  task: string;
  action: string;
  result: string;
}

export interface InterviewQuestion {
  question: string;
  star_answer: StarAnswer;
}

export interface InterviewPrepResponse {
  questions: InterviewQuestion[];
}

export interface HealthResponse {
  status: string;
}

// ─── Resume Types ──────────────────────────────────────────

export type ResumeStage = 'idle' | 'analyzing' | 'skills' | 'rewriting' | 'complete' | 'error';

export interface ToastMessage {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}
