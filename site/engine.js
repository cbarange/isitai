/*
 * isitai demo — engine adapter.
 *
 * This is the ONLY file the page talks to for analysis. Contract:
 *
 *   window.isitaiEngine = {
 *     isStub: boolean,                      // true: sample reports, input is NOT analysed
 *     async check(input): Promise<Report>   // input: string (text) | File | Blob | Uint8Array
 *   }
 *
 * `Report` is the schema emitted by the Rust core (crates/isitai-core/src/lib.rs):
 *   { verdict, media, generator?, evidence[], warnings?, history?, history_summary?,
 *     version: { lib, rules } }
 * Optional keys are omitted when empty, exactly as the core does today.
 *
 * It is a classic script that sets one global, not an ES module: browsers refuse
 * `<script type="module">` on file:// pages, and the page must work when opened
 * from disk.
 *
 * TO SWAP IN THE WASM BUILD: replace this file. Load the module, set `isStub: false`,
 * and make `check` call the core (text -> check_text, anything else -> bytes ->
 * check_bytes) and return the parsed JSON. Drop `sample` and `samples`; the page
 * hides the sample picker and the stub notices when `isStub` is false.
 * Note: fetching a .wasm file does not work on file:// either; that build will
 * need http(s) or an inlined binary.
 *
 * STUB ONLY: `sample` names the report returned by `check`, whatever the input is.
 * The `no-signal` sample (no `warnings`, no `generator` key) has the shape the real
 * Node addon returns (0.1.0-alpha.0). The other samples are
 * hand-written from the formats in provenance.rs, xmp.rs and png.rs: ids, details
 * and field paths follow the code, manifest labels and generator names are made up.
 */
(function () {
  'use strict';

  var VERSION = { lib: '0.1.0-alpha.0', rules: '0725267e10fe592b' };

  var samples = {
    'ai-proven': {
      verdict: 'ai-proven',
      media: 'image/png',
      generator: 'Example Image Generator',
      evidence: [
        {
          id: 'c2pa.dst.trainedAlgorithmicMedia',
          layer: 'provenance',
          strength: 'proof',
          origin: 'ai',
          detail: 'C2PA c2pa.created action declares digitalSourceType trainedAlgorithmicMedia (manifest trusted)',
          location: { field: 'urn:c2pa:6f1c2b5e-3a0d-4c8e-9b57-1d2e8a4f7c10/c2pa.actions.v2' }
        },
        {
          id: 'xmp.dst.trainedAlgorithmicMedia',
          layer: 'metadata',
          strength: 'strong',
          origin: 'ai',
          detail: 'unsigned XMP DigitalSourceType = trainedAlgorithmicMedia',
          location: { field: 'Iptc4xmpExt:DigitalSourceType' }
        }
      ],
      // In-progress fields, copied from the core's working tree on 2026-11-12; may change.
      history: [
        { action: 'c2pa.created', digital_source_type: 'trainedAlgorithmicMedia', software: 'Example Image Generator' },
        { action: 'c2pa.edited', software: 'Example Photo Editor' }
      ],
      history_summary: 'ai-then-edited',
      version: VERSION
    },

    'capture-proven': {
      verdict: 'capture-proven',
      media: 'image/jpeg',
      generator: 'Example Camera Firmware',
      evidence: [
        {
          id: 'c2pa.dst.digitalCapture',
          layer: 'provenance',
          strength: 'proof',
          origin: 'capture',
          detail: 'C2PA c2pa.created action declares digitalSourceType digitalCapture (manifest trusted)',
          location: { field: 'urn:c2pa:0b9d7a34-52c1-4e6f-8a2b-c3d4e5f60718/c2pa.actions.v2' }
        }
      ],
      version: VERSION
    },

    'ai-signal': {
      verdict: 'ai-signal',
      media: 'image/png',
      generator: 'Example Signing Tool',
      evidence: [
        {
          id: 'c2pa.dst.trainedAlgorithmicMedia',
          layer: 'provenance',
          strength: 'strong',
          origin: 'ai',
          detail: 'C2PA c2pa.created action declares digitalSourceType trainedAlgorithmicMedia (manifest valid)',
          location: { field: 'urn:c2pa:a41e9c07-7d3b-4f52-b6e8-90c1d2a3b4c5/c2pa.actions.v2' }
        },
        {
          id: 'png.prompt',
          layer: 'metadata',
          strength: 'strong',
          origin: 'ai',
          detail: 'PNG text chunk `prompt` written by ComfyUI',
          location: { field: 'tEXt:prompt' }
        },
        {
          id: 'png.workflow',
          layer: 'metadata',
          strength: 'strong',
          origin: 'ai',
          detail: 'PNG text chunk `workflow` written by ComfyUI',
          location: { field: 'tEXt:workflow' }
        }
      ],
      warnings: ['C2PA manifest is valid but its signer is not in the trust list'],
      version: VERSION
    },

    'inconsistent': {
      verdict: 'inconsistent',
      media: 'image/jpeg',
      generator: 'Example Camera Firmware',
      evidence: [
        {
          id: 'c2pa.dst.digitalCapture',
          layer: 'provenance',
          strength: 'proof',
          origin: 'capture',
          detail: 'C2PA c2pa.created action declares digitalSourceType digitalCapture (manifest trusted)',
          location: { field: 'urn:c2pa:5c2f8e19-04ab-4d77-93f0-6e7a8b9c0d1e/c2pa.actions.v2' }
        },
        {
          id: 'xmp.dst.trainedAlgorithmicMedia',
          layer: 'metadata',
          strength: 'strong',
          origin: 'ai',
          detail: 'unsigned XMP DigitalSourceType = trainedAlgorithmicMedia',
          location: { field: 'Iptc4xmpExt:DigitalSourceType' }
        }
      ],
      version: VERSION
    },

    'no-signal': {
      verdict: 'no-signal',
      media: 'image/jpeg',
      evidence: [],
      version: VERSION
    }
  };

  window.isitaiEngine = {
    isStub: true,
    sample: 'ai-signal',
    samples: samples,
    check: async function (input) {
      // Stub: `input` is deliberately ignored and never read.
      return JSON.parse(JSON.stringify(samples[this.sample]));
    }
  };
})();
