export type Verdict = 'ai-proven' | 'capture-proven' | 'ai-signal' | 'inconsistent' | 'no-signal';

export interface Evidence {
  id: string;
  layer: 'provenance' | 'metadata' | 'artifact';
  strength: 'weak' | 'strong' | 'proof';
  origin: 'ai' | 'capture';
  detail: string;
  /**
   * For text: `start`/`end` are UTF-8 byte offsets; use `text`, not `input.slice(start, end)`.
   * For a file in another encoding (UTF-16, Windows-1252), they are offsets in the decoded text.
   */
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
   * PEM bundle of trusted C2PA roots. It replaces the default, which is the two official C2PA
   * trust lists embedded in the library (manifest signers, time-stamp authorities). The bundle
   * is used for both, so it must also hold the roots of the time-stamps to trust. A valid
   * manifest whose signer does not chain to the roots in use gives at most `ai-signal`. A
   * bundle without a usable certificate throws.
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

/** Default `maxBytes` of `checkStream`: 256 MiB. */
export const DEFAULT_MAX_STREAM_BYTES: number;

export interface CheckStreamOptions extends CheckOptions {
  /** Largest stream to read, in bytes. Default: `DEFAULT_MAX_STREAM_BYTES`. */
  maxBytes?: number;
}

/**
 * Checks a stream that cannot seek: a Node `Readable`, a web `ReadableStream` (`fetch().body`),
 * the `Body` of an AWS SDK v3 `GetObject`, or any async iterable of byte chunks. The caller
 * opens the source: isitai makes no network request.
 *
 * The chunks are collected in memory, up to `maxBytes`, then checked like `check`. Rejects
 * with a `RangeError` when the stream holds more than `maxBytes` (a cut file is never
 * analysed), with a `TypeError` when a chunk is not bytes or `maxBytes` is not a
 * non-negative integer, with the error of the stream when it fails, and like `check`.
 *
 * Only the collection is asynchronous: the check then runs on the event loop, like `check`.
 * Options other than `maxBytes` are validated after the stream is read.
 */
export function checkStream(
  readable: AsyncIterable<Buffer | Uint8Array>,
  options?: CheckStreamOptions,
): Promise<Report>;
