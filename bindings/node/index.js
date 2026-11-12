'use strict';
// Thin wrapper: the native addon returns JSON built by the Rust core, parsed here,
// so Node, Python and the CLI return the same reports.
const native = require('./native.js');

/**
 * Checks a text string: AI copy-paste artifacts, and a statistical score (`coefficient`)
 * for plain text long enough in a language with a calibration table.
 * Throws when `prevalence` is not strictly between 0 and 1.
 * @param {string} text
 * @param {{score?: boolean, prevalence?: number}} [options]
 */
function checkText(text, options = {}) {
  return JSON.parse(native.checkTextJson(String(text), options.score, options.prevalence));
}

/**
 * Checks a file by path, off the event loop. The file is streamed, never loaded whole.
 * Rejects on an unknown `effort` and on `trustAnchorsPem` without a usable certificate.
 * @param {string} path
 * @param {{trustAnchorsPem?: string, declaredMime?: string, effort?: 'fast'|'standard', score?: boolean, prevalence?: number}} [options]
 */
async function checkFile(path, options = {}) {
  return JSON.parse(
    await native.checkFileJson(
      String(path), options.trustAnchorsPem, options.declaredMime, options.effort, options.score, options.prevalence,
    ),
  );
}

/**
 * Checks in-memory bytes (an upload). Synchronous; prefer checkFile for files on disk.
 * Throws on an unknown `effort` and on `trustAnchorsPem` without a usable certificate.
 * @param {Buffer|Uint8Array} data
 * @param {{trustAnchorsPem?: string, declaredMime?: string, effort?: 'fast'|'standard', score?: boolean, prevalence?: number}} [options]
 */
function check(data, options = {}) {
  const buf = Buffer.isBuffer(data) ? data : Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  return JSON.parse(
    native.checkBufferJson(
      buf, options.trustAnchorsPem, options.declaredMime, options.effort, options.score, options.prevalence,
    ),
  );
}

/** Default `maxBytes` of `checkStream`: 256 MiB. */
const DEFAULT_MAX_STREAM_BYTES = native.DEFAULT_MAX_STREAM_BYTES;

/**
 * Checks a stream that cannot seek: an HTTP response body, an object store stream, an
 * upload being received. The caller opens the source: isitai makes no network request.
 * The chunks are collected in memory, then checked like `check`.
 * Rejects when the stream holds more than `maxBytes` (a cut file is never analysed), when
 * the stream fails, when a chunk is not bytes, and on the errors of `check`.
 * @param {AsyncIterable<Buffer|Uint8Array>} readable a Node Readable, a web ReadableStream, an async generator
 * @param {{maxBytes?: number, trustAnchorsPem?: string, declaredMime?: string, effort?: 'fast'|'standard'}} [options]
 */
async function checkStream(readable, options = {}) {
  if (readable == null || typeof readable[Symbol.asyncIterator] !== 'function' && typeof readable[Symbol.iterator] !== 'function' || readable instanceof Uint8Array || typeof readable === 'string') {
    throw new TypeError('checkStream needs a stream (Readable, web ReadableStream or async iterable); use check for bytes and checkText for text');
  }
  const maxBytes = options.maxBytes ?? DEFAULT_MAX_STREAM_BYTES;
  if (!Number.isInteger(maxBytes) || maxBytes < 0) {
    throw new TypeError(`maxBytes must be a non-negative integer, got ${maxBytes}`);
  }
  // One growing buffer: memory follows the bytes received, not the number of chunks
  // (an upload can arrive as millions of 1-byte chunks).
  let buf = Buffer.allocUnsafe(Math.min(64 * 1024, maxBytes));
  let size = 0;
  // Leaving the loop with an error closes the source.
  for await (const chunk of readable) {
    if (!(chunk instanceof Uint8Array)) {
      throw new TypeError('checkStream needs chunks of bytes (Buffer or Uint8Array), not strings or objects');
    }
    if (size + chunk.byteLength > maxBytes) {
      throw new RangeError(`stream is larger than the limit of ${maxBytes} bytes`);
    }
    if (size + chunk.byteLength > buf.length) {
      const grown = Buffer.allocUnsafe(Math.min(maxBytes, Math.max(buf.length * 2, size + chunk.byteLength)));
      buf.copy(grown, 0, 0, size);
      buf = grown;
    }
    buf.set(chunk, size);
    size += chunk.byteLength;
  }
  return check(buf.subarray(0, size), options);
}

module.exports = { check, checkText, checkFile, checkStream, DEFAULT_MAX_STREAM_BYTES };
