// The receipt hash, held to the digests the Python twin (scripts/lib/install_receipt.py) is held to.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { hashBytes, hashFile, isText, normalise } from '../../cli/hash.mjs';

const FIXTURES = path.resolve(fileURLToPath(new URL('../fixtures/hash', import.meta.url)));
const EXPECTED = JSON.parse(readFileSync(path.join(FIXTURES, 'expected.json'), 'utf8'));

test('every shared fixture hashes to the digest the Python twin gives', () => {
  assert.ok(Object.keys(EXPECTED).length >= 8);
  for (const [name, want] of Object.entries(EXPECTED)) {
    const bytes = readFileSync(path.join(FIXTURES, name));
    assert.equal(isText(bytes), want.text, `${name} text`);
    assert.equal(hashFile(path.join(FIXTURES, name)), want.sha256, name);
  }
});

test('CRLF, a missing final newline and trailing blank lines hash alike', () => {
  const want = hashBytes(Buffer.from('a\nb'));
  assert.equal(hashBytes(Buffer.from('a\r\nb\r\n')), want);
  assert.equal(hashBytes(Buffer.from('a\nb\n\n \t\n')), want);
});

test('leading and inner whitespace count', () => {
  assert.notEqual(hashBytes(Buffer.from(' a\nb')), hashBytes(Buffer.from('a\nb')));
  assert.notEqual(hashBytes(Buffer.from('a \nb')), hashBytes(Buffer.from('a\nb')));
});

test('a NUL byte or invalid UTF-8 is binary, hashed raw', () => {
  assert.equal(isText(Buffer.from([0x61, 0x00])), false);
  assert.equal(isText(Buffer.from([0xe9])), false);
  assert.notEqual(hashBytes(Buffer.from('a\r\n\x00')), hashBytes(Buffer.from('a\n\x00')));
});

test('normalise keeps a BOM and the text inside', () => {
  assert.equal(normalise('﻿x\r\ny  \n'), '﻿x\ny');
});
