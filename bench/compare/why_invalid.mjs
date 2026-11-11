await import('reflect-metadata');
import { readFile } from 'node:fs/promises';
const { createAsset } = await import('@trustnxt/c2pa-ts/asset');
const { SuperBox } = await import('@trustnxt/c2pa-ts/jumbf');
const { ManifestStore } = await import('@trustnxt/c2pa-ts/manifest');
for (const p of process.argv.slice(2)) {
  const asset = await createAsset(await readFile(p));
  const r = await ManifestStore.read(SuperBox.fromBuffer(await asset.getManifestJUMBF())).validate(asset);
  const entries = (r.statusEntries ?? []).filter(e => !e.success).map(e => `${e.code}${e.explanation ? ' (' + e.explanation + ')' : ''}`);
  console.log(p.split('/').pop(), r.isValid, JSON.stringify(entries));
}
