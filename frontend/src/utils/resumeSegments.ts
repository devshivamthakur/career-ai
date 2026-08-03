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

const BEGIN_RESUME_RE = /^---\s*BEGIN\s*RESUME\s*---\s*$/i;
const END_RESUME_RE = /^---\s*END\s*RESUME\s*---\s*$/i;
const HTML_BEGIN_RE = /^<!--\s*RESUME\s*-->$/i;
const HTML_END_RE = /^<!--\s*\/\s*RESUME\s*-->$/i;

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
    const trimmed = line.trim();

    if (resumeBuffer !== null) {
      // Inside a resume block — stop at the closing marker
      if (END_RESUME_RE.test(trimmed) || HTML_END_RE.test(trimmed)) {
        const content = resumeBuffer.join('\n').trim();
        if (content) segments.push({ type: 'resume', content });
        resumeBuffer = null;
      } else {
        resumeBuffer.push(line);
      }
      continue;
    }

    // Opening marker — everything after this belongs to the resume
    if (BEGIN_RESUME_RE.test(trimmed) || HTML_BEGIN_RE.test(trimmed)) {
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
