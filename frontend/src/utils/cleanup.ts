import { isEndResumeMarker } from './resumeSegments';

/**
 * Strips trailing conversational / suggestion text that the LLM sometimes
 * appends after the resume content (e.g. "This tailored version emphasizes…",
 * "Would you like me to adjust anything…").
 *
 * Returns the text truncated at the first matching line.
 */

const TRAILING_PATTERNS = [
  /^this tailored version/i,
  /^this version emphasizes/i,
  /^this resume emphasizes/i,
  /^i'?ve tailored/i,
  /^here'?s what i emphasized/i,
  /^let me know if you/i,
  /^would you like (me to|to)/i,
  /^feel free to ask/i,
  /^do you want me to/i,
  /^you (may|might) want to/i,
  /^i recommend/i,
  /^key changes/i,
  /^what i changed/i,
  /^changes made/i,
  /^adjustments made/i,
  /^here'?s a summary/i,
  /^overview of changes/i,
  /^i focused on/i,
  /^the focus was on/i,
  /^i can (also|further|adjust)/i,
  /^i'?m happy to/i,
  /^does this (work|look)/i,
  /^is there anything/i,
  /^please let me know/i,
  /^tell me if you/i,
  /^some suggestions/i,
];

export function stripTrailingCommentary(text: string): string {
  if (!text) return text;

  const lines = text.split('\n');
  let cutoff = lines.length;

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (!trimmed) continue;

    // Check for known trailing patterns
    if (TRAILING_PATTERNS.some((p) => p.test(trimmed))) {
      cutoff = i;
      break;
    }

    // After ---END RESUME---, check if remaining content is empty or just commentary
    if (isEndResumeMarker(lines[i]) && i < lines.length - 1) {
      const remaining = lines.slice(i + 1).filter((l) => l.trim().length > 0);
      if (remaining.length > 0) {
        const allCommentary = remaining.every(
          (l) =>
            /^\s*[-*]\s*$/.test(l.trim()) ||
            TRAILING_PATTERNS.some((p) => p.test(l.trim())),
        );
        if (allCommentary) {
          cutoff = i + 1;
          break;
        }
      }
    }
  }

  return lines.slice(0, cutoff).join('\n').trim();
}
