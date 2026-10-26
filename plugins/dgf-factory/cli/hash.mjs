// The receipt's hash (ADR 0029 §4). scripts/lib/install_receipt.py `hash_bytes` is its Python twin;
// tests/fixtures/hash/expected.json holds both to the same digests.
//
// A file is text when it decodes as UTF-8 and holds no NUL byte. Text is normalised — CRLF becomes
// LF, and the trailing run of spaces, tabs, CRs and LFs at the end of the file is dropped — then
// hashed as UTF-8. Anything else is hashed raw. SHA-256, lower-case hex.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

import * as log from './log.mjs';

const DECODER = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });

export function isText(bytes) {
  if (bytes.includes(0)) return false;
  try {
    DECODER.decode(bytes);
    return true;
  } catch {
    return false;
  }
}

export function normalise(text) {
  return text.replace(/\r\n/g, '\n').replace(/[ \t\r\n]+$/, '');
}

export function hashBytes(bytes, where = '') {
  const text = isText(bytes);
  const input = text ? Buffer.from(normalise(DECODER.decode(bytes)), 'utf8') : bytes;
  const digest = createHash('sha256').update(input).digest('hex');
  log.debug('hash.hashBytes', 'hashed', { file: where, kind: text ? 'text' : 'binary', digest: digest.slice(0, 12) });
  return digest;
}

export function hashFile(file) {
  return hashBytes(readFileSync(file), file);
}
