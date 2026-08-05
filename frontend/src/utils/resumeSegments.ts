/**
 * Splits assistant message content into conversational and resume
 * segments so the UI can render the block between
 * `---BEGIN RESUME---` / `---END RESUME---` (or HTML comment markers)
 * as a styled document card instead of raw markdown with visible markers.
 *
 * Streaming-safe: if the closing marker hasn't arrived yet, everything
 * after the opening marker is treated as an in-progress resume block.
 */

export type ContentSegment =
  | { type: 'text'; content: string }
  | { type: 'resume'; content: string };

const HTML_BEGIN_RE = /^<!--\s*RESUME\s*-->$/i;
const HTML_END_RE = /^<!--\s*\/\s*RESUME\s*-->$/i;

/**
 * Collapses a marker line to a bare keyword so decorated variants are all
 * recognized: `---BEGIN RESUME---`, `**BEGIN RESUME**`, `### BEGIN RESUME ###`,
 * `BEGIN RESUME:` …
 */
function markerKeyword(line: string): string {
  return line.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
}

export function isBeginResumeMarker(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (HTML_BEGIN_RE.test(trimmed)) return true;
  return markerKeyword(trimmed) === 'BEGINRESUME';
}

export function isEndResumeMarker(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (HTML_END_RE.test(trimmed)) return true;
  return markerKeyword(trimmed) === 'ENDRESUME';
}

export function splitResumeSegments(text: string): ContentSegment[] {
  if (!text) return [];

  const lines = text.split('\n');
  const segments: ContentSegment[] = [];
  let textBuffer: string[] = [];
  let resumeBuffer: string[] | null = null;

  const flushText = () => {
    if (textBuffer.length > 0) {
      segments.push({ type: 'text', content: textBuffer.join('\n') });
      textBuffer = [];
    }
  };

  for (const line of lines) {
    if (resumeBuffer !== null) {
      // Inside a resume block — stop at the closing marker
      if (isEndResumeMarker(line)) {
        const content = resumeBuffer.join('\n').trim();
        if (content) segments.push({ type: 'resume', content });
        resumeBuffer = null;
      } else {
        resumeBuffer.push(line);
      }
      continue;
    }

    // Opening marker — everything after this belongs to the resume
    if (isBeginResumeMarker(line)) {
      flushText();
      resumeBuffer = [];
      continue;
    }

    textBuffer.push(line);
  }

  // Unclosed resume block (still streaming) — treat the rest as resume
  if (resumeBuffer !== null) {
    const content = resumeBuffer.join('\n').trim();
    if (content) segments.push({ type: 'resume', content });
  }
  flushText();

  return segments;
}
