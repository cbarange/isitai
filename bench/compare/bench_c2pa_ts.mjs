// Time @trustnxt/c2pa-ts read + validate per file. It has no network access and,
// per its README, no chain-of-trust validation. Same protocol as examples/bench_files.rs.
// Usage: node bench_c2pa_ts.mjs <iterations> FILE...
import { readFile } from 'node:fs/promises';
import { basename } from 'node:path';
import { performance } from 'node:perf_hooks';

const t0 = performance.now();
// c2pa-ts depends on tsyringe, which needs this polyfill (npm i reflect-metadata).
await import('reflect-metadata');
const { createAsset } = await import('@trustnxt/c2pa-ts/asset');
const { SuperBox } = await import('@trustnxt/c2pa-ts/jumbf');
const { ManifestStore, ValidationResult } = await import('@trustnxt/c2pa-ts/manifest');
console.error(`import_ms=${(performance.now() - t0).toFixed(1)}`);

const [iterArg, ...files] = process.argv.slice(2);
const iterations = Number(iterArg);

for (const path of files) {
  const times = [];
  let state = '';
  for (let i = 0; i < iterations; i++) {
    const t = performance.now();
    try {
      const buf = await readFile(path);
      const asset = await createAsset(buf);
      const jumbf = await asset.getManifestJUMBF();
      if (!jumbf) {
        state = 'no-manifest';
      } else {
        let result;
        try {
          result = await ManifestStore.read(SuperBox.fromBuffer(jumbf)).validate(asset);
        } catch (e) {
          result = ValidationResult.fromError(e);
        }
        state = result.isValid ? 'valid' : 'invalid';
      }
    } catch (e) {
      state = `error:${e?.constructor?.name}`;
    }
    times.push(performance.now() - t);
  }
  const first = times[0];
  times.sort((a, b) => a - b);
  console.log(JSON.stringify({
    file: basename(path), first_ms: first, median_ms: times[Math.floor(times.length / 2)],
    p95_ms: times[Math.min(Math.floor(times.length * 0.95), times.length - 1)], state,
  }));
}
