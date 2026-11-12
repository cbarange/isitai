/**
 * `ai-likely`: no proof and no signal, and the statistical score of the text is above the
 * 1 % false-positive threshold of its calibration table. An estimate, never a proof.
 */
export type Verdict =
  | 'ai-proven'
  | 'capture-proven'
  | 'ai-signal'
  | 'inconsistent'
  | 'ai-likely'
  | 'no-signal';

/**
 * Statistical score of a plain text (detector `text-light-v1`). Present with every field
 * `null` when the detector abstained: text too short, or no calibration table for its
 * language (a warning says which).
 */
export interface Coefficient {
  /**
   * Likelihood ratio: how much more often this score is seen on AI text than on human
   * text in the calibration data. Above 1 points to AI, below 1 to human.
   * It is NOT the probability that the text is AI-made.
   */
  lr: number | null;
  /** Bootstrap interval of `lr`, at the stated `coverage`. */
  lr_interval: [number, number] | null;
  coverage: number | null;
  /** Detector, language and date of the calibration table, e.g. `text-light-v1/en/2026-11-12`. */
  calibration_id: string | null;
  /** The `prevalence` option, when given. */
  prevalence_used: number | null;
  /** Probability that the text is AI-made under `prevalence_used`; `null` without it. */
  posterior: number | null;
}

export interface Evidence {
  id: string;
  layer: 'provenance' | 'metadata' | 'artifact' | 'rhetoric';
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
  /** Absent when the score is off or the input is not plain text. */
  coefficient?: Coefficient;
  /** What the coefficient was computed on: detected language, words, calibration data. */
  notes?: string[];
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
   * PEM bundle of trusted C2PA roots. It replaces the default, which is the trust lists
   * embedded in the library: the two official C2PA lists (manifest signers, time-stamp
   * authorities) and the older interim list. The bundle is used for signers and for
   * time-stamps, so it must also hold the roots of the time-stamps to trust. A valid
   * manifest whose signer does not chain to the roots in use gives at most `ai-signal`. A
   * bundle without a usable certificate throws.
   */
  trustAnchorsPem?: string;
  /** MIME type claimed by the caller, compared with the sniffed type. */
  declaredMime?: string;
  /** An unknown value throws. */
  effort?: Effort;
  /** Statistical score of plain text (`coefficient`). Default: `true`. */
  score?: boolean;
  /**
   * Share of AI text you expect among the texts you check, strictly between 0 and 1
   * (anything else throws). With it the report gives `posterior`; without it a
   * likelihood ratio only: the library cannot guess a prevalence.
   */
  prevalence?: number;
}

export type CheckTextOptions = Pick<CheckOptions, 'score' | 'prevalence'>;

/**
 * Checks a text string: AI copy-paste artifacts, and a statistical score (`coefficient`)
 * when the text is long enough and its language has a calibration table.
 * Throws when `prevalence` is not strictly between 0 and 1.
 */
export function checkText(text: string, options?: CheckTextOptions): Report;
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
