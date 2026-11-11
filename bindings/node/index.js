'use strict';
// Thin wrapper: the native addon returns JSON built by the Rust core, parsed here,
// so Node, Python and the CLI return the same reports.
const native = require('./native.js');

/** Checks a text string for AI copy-paste artifacts. */
function checkText(text) {
  return JSON.parse(native.checkTextJson(String(text)));
}

/**
 * Checks a file by path, off the event loop. The file is streamed, never loaded whole.
 * @param {string} path
 * @param {{trustAnchorsPem?: string, declaredMime?: string}} [options]
 */
async function checkFile(path, options = {}) {
  return JSON.parse(await native.checkFileJson(String(path), options.trustAnchorsPem, options.declaredMime));
}

/**
 * Checks in-memory bytes (an upload). Synchronous; prefer checkFile for files on disk.
 * @param {Buffer|Uint8Array} data
 * @param {{trustAnchorsPem?: string, declaredMime?: string}} [options]
 */
function check(data, options = {}) {
  const buf = Buffer.isBuffer(data) ? data : Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  return JSON.parse(native.checkBufferJson(buf, options.trustAnchorsPem, options.declaredMime));
}

module.exports = { check, checkText, checkFile };
