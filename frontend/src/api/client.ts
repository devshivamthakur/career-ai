import type {
  CreateSessionResponse,
  SessionMessagesResponse,
  InterviewPrepRequest,
  InterviewPrepResponse,
  HealthResponse,
} from '../types/api';

const BASE_URL = '/api';
const HEALTH_URL = '/health';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    let detail = response.statusText;
    try {
      const parsed = JSON.parse(errorBody);
      detail = parsed.detail ?? detail;
    } catch {
      // ignore parse errors
    }

    if (response.status === 422) {
      throw new ApiValidationError(detail, response.status);
    }
    if (response.status === 429) {
      throw new ApiError('Too many requests — please wait a moment', response.status);
    }
    if (response.status === 503) {
      throw new ApiError('Service temporarily unavailable, try again shortly', response.status);
    }
    throw new ApiError(detail, response.status);
  }

  return response.json();
}

class ApiError extends Error {
  status: number;

  constructor(
    message: string,
    status: number,
  ) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

class ApiValidationError extends ApiError {
  constructor(
    message: string,
    status: number,
  ) {
    super(message, status);
    this.name = 'ApiValidationError';
  }
}

// ─── Chat API ───────────────────────────────────────────────

export async function createSession(): Promise<CreateSessionResponse> {
  return fetchJson<CreateSessionResponse>(`${BASE_URL}/chat/session`, {
    method: 'POST',
  });
}

export async function getSessionMessages(
  sessionId: string,
): Promise<SessionMessagesResponse> {
  return fetchJson<SessionMessagesResponse>(
    `${BASE_URL}/chat/session/${sessionId}`,
  );
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE_URL}/chat/session/${sessionId}`, {
    method: 'DELETE',
  });
}

// ─── Career API ─────────────────────────────────────────────

export function generateCoverLetterUrl() {
  return `${BASE_URL}/career/cover-letter`;
}

export async function generateInterviewPrep(
  data: InterviewPrepRequest,
): Promise<InterviewPrepResponse> {
  return fetchJson<InterviewPrepResponse>(`${BASE_URL}/career/interview-prep`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ─── Resume API (non-streaming) ─────────────────────────────

export async function exportPdf(tailoredResume: string): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/resume/export-pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_text: tailoredResume }),
  });

  if (!response.ok) throw new ApiError('Failed to export PDF', response.status);
  return response.blob();
}

// ─── Health ─────────────────────────────────────────────────

export async function checkHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>(HEALTH_URL);
}
