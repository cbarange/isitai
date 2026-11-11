export type Verdict = 'ai-proven' | 'capture-proven' | 'ai-signal' | 'inconsistent' | 'no-signal';

export interface Evidence {
  id: string;
  layer: 'provenance' | 'metadata' | 'artifact';
  strength: 'weak' | 'strong' | 'proof';
  origin: 'ai' | 'capture';
  detail: string;
  /** For text: `start`/`end` are UTF-8 byte offsets; use `text`, not `input.slice(start, end)`. */
  location?: { start: number; end: number; text: string } | { field: string };
}

export interface Report {
  verdict: Verdict;
  media: string;
  generator?: string;
  evidence: Evidence[];
  warnings?: string[];
  version: { lib: string; rules: string };
}

export interface CheckOptions {
  /** PEM bundle of trusted C2PA roots. Without it, a valid manifest gives at most `ai-signal`. */
  trustAnchorsPem?: string;
  /** MIME type claimed by the caller, compared with the sniffed type. */
  declaredMime?: string;
}

export function checkText(text: string): Report;
export function checkFile(path: string, options?: CheckOptions): Promise<Report>;
export function check(data: Buffer | Uint8Array, options?: CheckOptions): Report;
