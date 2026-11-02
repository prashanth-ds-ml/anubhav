// Replay mode can only answer saved requests. This picks the closest saved prompt for what a person typed or said.
// Word overlap (Jaccard) on letters and digits in any script, so Telugu and Roman Telugu both work. No model call.

export const THRESHOLD = 0.3;

const tokens = (s: string) => new Set((s.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []).filter((t) => t.length > 2));
const norm = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim();

export interface Match { prompt: string; score: number; exact: boolean; }

export function closest(text: string, prompts: string[]): Match | null {
  const q = tokens(text);
  let best: Match | null = null;
  for (const p of prompts) {
    if (norm(p) === norm(text)) return { prompt: p, score: 1, exact: true };
    const t = tokens(p);
    const inter = [...q].filter((x) => t.has(x)).length;
    const score = inter / (q.size + t.size - inter || 1);
    if (!best || score > best.score) best = { prompt: p, score, exact: false };
  }
  return best && best.score >= THRESHOLD ? best : null;
}
