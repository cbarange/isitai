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
  /**
   * Actions of the active C2PA manifest, in the order the manifest lists them, at most 64.
   * Not evidence: the verdict ignores it.
   */
  history?: HistoryEntry[];
  /** What `history` establishes about edits after creation; absent when it establishes nothing. */
  history_summary?: HistorySummary;
  version: { lib: string; rules: string };
}

export interface HistoryEntry {
  /** C2PA action name, e.g. `c2pa.created`, `c2pa.opened`, `c2pa.edited`. */
  action: string;
  /**
   * Declared by the action or, failing that, by the manifest of the ingredient it refers to.
   * An inherited value is the type of the ingredient's first action only.
   */
  digital_source_type?: string;
  software?: string;
}

/**
 * `ai-then-edited`: declared AI-made when created or opened, then modified by a later action.
 * `capture-then-ai-edited`: declared a camera capture, then a later edit declares an AI source.
 */
export type HistorySummary = 'ai-then-edited' | 'capture-then-ai-edited';

/**
 * `standard` (default): every layer.
 * `fast` skips the XMP scan of the whole file; C2PA validation may still read a signed file whole;
 * `fast` can miss unsigned metadata, including a contradiction that `standard` would report.
 */
export type Effort = 'fast' | 'standard';

export interface CheckOptions {
  /**
   * PEM bundle of trusted C2PA roots. Without it, a valid manifest gives at most `ai-signal`.
   * A bundle without a usable certificate throws.
   */
  trustAnchorsPem?: string;
  /** MIME type claimed by the caller, compared with the sniffed type. */
  declaredMime?: string;
  /** An unknown value throws. */
  effort?: Effort;
}

/** Checks a text string for AI copy-paste artifacts. */
export function checkText(text: string): Report;
/**
 * Checks a file by path, off the event loop. Rejects when the file cannot be read, on an
 * unknown `effort` and on unusable `trustAnchorsPem`.
 */
export function checkFile(path: string, options?: CheckOptions): Promise<Report>;
/** Checks in-memory bytes. Throws on an unknown `effort` and on unusable `trustAnchorsPem`. */
export function check(data: Buffer | Uint8Array, options?: CheckOptions): Report;
