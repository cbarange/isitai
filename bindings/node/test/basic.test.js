'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { check, checkText, checkFile } = require('..');

test('checkText finds a ChatGPT citation artifact', () => {
  const r = checkText('Élève doué :contentReference[oaicite:0]{index=0}');
  assert.strictEqual(r.verdict, 'ai-signal');
  assert.strictEqual(r.evidence[0].location.text, ':contentReference[oaicite:0]{index=0}');
});

test('French typography alone is no signal', () => {
  assert.strictEqual(checkText('Il a dit : « oui »').verdict, 'no-signal');
});

test('checkFile streams a PNG written by Stable Diffusion WebUI', async () => {
  const chunk = (kind, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    return Buffer.concat([len, Buffer.from(kind), data, Buffer.alloc(4)]);
  };
  const png = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', Buffer.alloc(13)),
    chunk('tEXt', Buffer.from('parameters\0a cat, Steps: 20')),
    chunk('IEND', Buffer.alloc(0)),
  ]);
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'isitai-')), 'sd.png');
  fs.writeFileSync(file, png);
  const fromFile = await checkFile(file);
  assert.strictEqual(fromFile.verdict, 'ai-signal');
  assert.strictEqual(fromFile.generator, 'Stable Diffusion WebUI (A1111/Forge)');
  assert.deepStrictEqual(check(png), fromFile);
});

test('effort: fast skips the XMP scan, an unknown value is an error', async () => {
  const xmp =
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:Description Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/></x:xmpmeta>';
  const jpeg = Buffer.concat([Buffer.from([0xff, 0xd8, 0xff, 0xe0]), Buffer.from(xmp)]);
  assert.strictEqual(check(jpeg).verdict, 'ai-signal');
  assert.strictEqual(check(jpeg, { effort: 'standard' }).verdict, 'ai-signal');
  assert.strictEqual(check(jpeg, { effort: 'fast' }).verdict, 'no-signal');
  assert.throws(() => check(jpeg, { effort: 'thorough' }), /unknown effort `thorough`/);
  assert.throws(() => check(jpeg, { effort: 'turbo' }), /unknown effort `turbo`/);
  await assert.rejects(checkFile(__filename, { effort: 'turbo' }), /unknown effort `turbo`/);
});

test('unusable trust anchors are an error, not a silent loss of C2PA reading', async () => {
  const jpeg = Buffer.from([0xff, 0xd8, 0xff, 0xe0]);
  for (const pem of ['', 'not a pem file']) {
    assert.throws(() => check(jpeg, { trustAnchorsPem: pem }), /trust anchors: no PEM certificate block/);
    await assert.rejects(checkFile(__filename, { trustAnchorsPem: pem }), /trust anchors: no PEM certificate block/);
  }
  const junk = '-----BEGIN CERTIFICATE-----\nnot base64\n-----END CERTIFICATE-----\n';
  assert.throws(() => check(jpeg, { trustAnchorsPem: junk }), /trust anchors: .*no certificate that can be loaded/);
  // No anchors at all stays valid.
  assert.strictEqual(check(jpeg, { trustAnchorsPem: undefined }).verdict, 'no-signal');
});

test('text rules run inside an HTML file', () => {
  const html = Buffer.from('<!DOCTYPE html>\n<p>Paris :contentReference[oaicite:0]{index=0}</p>');
  const r = check(html);
  assert.strictEqual(r.media, 'text/html');
  assert.strictEqual(r.verdict, 'ai-signal');
});

test('checkFile rejects a missing file', async () => {
  await assert.rejects(checkFile('/definitely/missing.jpg'));
});
