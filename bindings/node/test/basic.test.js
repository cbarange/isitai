'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Readable } = require('node:stream');
const { check, checkText, checkFile, checkStream, DEFAULT_MAX_STREAM_BYTES } = require('..');

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

const HTML = Buffer.from('<!DOCTYPE html>\n<p>Paris :contentReference[oaicite:0]{index=0}</p>');

test('checkStream reads a Readable, a web stream and an async generator', async () => {
  const expected = check(HTML);
  assert.strictEqual(expected.verdict, 'ai-signal');
  assert.strictEqual(DEFAULT_MAX_STREAM_BYTES, 256 * 1024 * 1024);
  // A Readable that gives the data in three chunks.
  const parts = [HTML.subarray(0, 5), HTML.subarray(5, 20), HTML.subarray(20)];
  assert.deepStrictEqual(await checkStream(Readable.from(parts)), expected);
  assert.deepStrictEqual(await checkStream(Readable.toWeb(Readable.from(parts))), expected);
  async function* generate() {
    for (const part of parts) yield new Uint8Array(part);
  }
  assert.deepStrictEqual(await checkStream(generate()), expected);
  // The limit is the size of the data: accepted.
  assert.deepStrictEqual(await checkStream(generate(), { maxBytes: HTML.length }), expected);
  assert.deepStrictEqual(await checkStream(Readable.from([])), check(Buffer.alloc(0)));
  // Options go to the check.
  await assert.rejects(checkStream(generate(), { effort: 'turbo' }), /unknown effort `turbo`/);
});

test('checkStream rejects a stream over maxBytes and stops reading it', async () => {
  let yielded = 0;
  let closed = false;
  async function* endless() {
    try {
      for (;;) {
        yielded += 1;
        yield Buffer.alloc(1024, 120);
      }
    } finally {
      closed = true;
    }
  }
  await assert.rejects(checkStream(endless(), { maxBytes: 4096 }), {
    name: 'RangeError',
    message: 'stream is larger than the limit of 4096 bytes',
  });
  assert.strictEqual(yielded, 5);
  assert.strictEqual(closed, true);
  // One byte over the limit.
  await assert.rejects(checkStream(Readable.from([HTML]), { maxBytes: HTML.length - 1 }), RangeError);
  const readable = Readable.from([HTML, HTML]);
  await assert.rejects(checkStream(readable, { maxBytes: HTML.length }), RangeError);
  assert.strictEqual(readable.destroyed, true);
});

test('checkStream rejects what is not a stream of bytes', async () => {
  await assert.rejects(checkStream(Readable.from(['text', 'chunks'])), TypeError);
  await assert.rejects(checkStream(Readable.from([HTML]), { maxBytes: -1 }), TypeError);
  await assert.rejects(checkStream(Readable.from([HTML]), { maxBytes: '10' }), TypeError);
  await assert.rejects(checkStream(HTML.toString()), TypeError);
  // An error of the source is passed on.
  async function* broken() {
    yield HTML;
    throw new Error('connection reset');
  }
  await assert.rejects(checkStream(broken()), /connection reset/);
});

test('text in Windows-1252 and UTF-16 is decoded', () => {
  const latin1 = check(Buffer.from('Très bien :contentReference[oaicite:0]{index=0}', 'latin1'));
  assert.strictEqual(latin1.verdict, 'ai-signal');
  assert.deepStrictEqual(latin1.warnings, ['text decoded as Windows-1252']);
  const utf16 = check(Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from('Très bien cite turn0search1', 'utf16le')]));
  assert.strictEqual(utf16.verdict, 'ai-signal');
  assert.deepStrictEqual(utf16.warnings, ['text decoded as UTF-16LE']);
});

test('checkFile rejects a missing file', async () => {
  await assert.rejects(checkFile('/definitely/missing.jpg'));
});
