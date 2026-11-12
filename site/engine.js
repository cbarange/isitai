/*
 * isitai demo — engine adapter.
 *
 * This is the ONLY file the page talks to for analysis. Contract:
 *
 *   window.isitaiEngine = {
 *     isStub: false,                        // the input is really analysed
 *     ready: Promise<void>,                 // rejects when the engine cannot be loaded
 *     async check(input): Promise<Report>   // input: string (text) | File | Blob | Uint8Array
 *   }
 *
 * `Report` is the schema emitted by the Rust core (crates/isitai-core/src/lib.rs):
 *   { verdict, media, generator?, evidence[], warnings?, history?, history_summary?,
 *     version: { lib, rules } }
 * Optional keys are omitted when empty, exactly as the core does today.
 *
 * The engine is the Rust core compiled to WebAssembly (bindings/wasm), built into
 * ./pkg/ by site/build.sh. The input is read and checked inside the page: the only
 * requests are for the page's own files (./pkg/isitai_wasm.js and its .wasm).
 *
 * This file stays a classic script that sets one global, so the page still renders
 * when the engine cannot load. That is the case on file:// pages: browsers refuse to
 * load an ES module or a .wasm file from disk. The page needs http(s).
 */
(function () {
  'use strict';

  // The file is copied whole into WebAssembly memory (32-bit: 4 GB at most).
  var MAX_BYTES = 256 * 1024 * 1024;

  // Relative to this script, so the page works at a domain root and under a sub-path.
  var loading = import('./pkg/isitai_wasm.js').then(function (wasm) {
    return wasm.default().then(function () { return wasm; });
  });

  async function bytesOf(input) {
    if (input instanceof Uint8Array) return input;
    if (input.size > MAX_BYTES) {
      throw new Error('file too large for the in-browser engine (limit ' + MAX_BYTES / 1048576 + ' MB)');
    }
    return new Uint8Array(await input.arrayBuffer());
  }

  window.isitaiEngine = {
    isStub: false,
    ready: loading.then(function () {}),
    check: async function (input) {
      var wasm = await loading;
      if (typeof input === 'string') return JSON.parse(wasm.check_text_json(input));
      return JSON.parse(wasm.check_bytes_json(await bytesOf(input)));
    }
  };
})();
