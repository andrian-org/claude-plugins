// The receipt: its schema, a round trip, refused paths, and atomic writes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { Journal, ensureWithinRoot, pruneEmptyDirs, writeAtomic } from '../../cli/fsops.mjs';
import { RECEIPT, emptyReceipt, readReceipt, serialise, validate, writeReceipt } from '../../cli/receipt.mjs';

function project(t) {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'dgf-receipt-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function sample() {
  const data = emptyReceipt('0.2.0');
  data.harnesses = [{ id: 'gemini', selected: true }, { id: 'claude', selected: true }];
  data.files['.claude/skills/dgf/SKILL.md'] = { source: 'skills/dgf/SKILL.md', owner: 'claude', sourceHash: 'a', installedHash: 'b' };
  data.files['.dgf-factory/runtime/scripts/x.py'] = { source: 'scripts/x.py', owner: 'runtime', sourceHash: 'c', installedHash: 'c' };
  data.mcp.claude = { file: '.mcp.json', key: 'dgf-mcp', entryHash: 'd' };
  return data;
}

test('a receipt round-trips, sorted, with a trailing newline', (t) => {
  const root = project(t);
  writeReceipt(root, sample());
  const text = readFileSync(path.join(root, RECEIPT), 'utf8');
  assert.ok(text.endsWith('}\n'));
  assert.deepEqual(readReceipt(root), JSON.parse(text));
  assert.equal(JSON.parse(text).harnesses[0].id, 'claude', 'harnesses sorted by id');
  assert.equal(serialise(readReceipt(root)), text, 'serialising what was read writes the same bytes');
});

test('no receipt reads as null', (t) => {
  assert.equal(readReceipt(project(t)), null);
});

test('an unknown key, a wrong type or a bad path is a usage error', () => {
  const cases = [
    { ...sample(), extra: 1 },
    { ...sample(), tool: 'ai-factory' },
    { ...sample(), harnesses: [{ id: 'claude', selected: 'yes' }] },
    { ...sample(), files: { '../x': { source: 's', owner: 'runtime', sourceHash: 'a', installedHash: 'b' } } },
    { ...sample(), files: { '/abs': { source: 's', owner: 'runtime', sourceHash: 'a', installedHash: 'b' } } },
    { ...sample(), files: { 'a\\b': { source: 's', owner: 'runtime', sourceHash: 'a', installedHash: 'b' } } },
    { ...sample(), files: { x: { source: 's', owner: 'runtime', sourceHash: 'a' } } },
    { ...sample(), mcp: { claude: { file: '../.mcp.json', key: 'dgf-mcp', entryHash: 'x' } } },
    { ...sample(), files: [] },
  ];
  for (const data of cases) assert.throws(() => validate(data), (err) => err.code === 3, JSON.stringify(data).slice(0, 80));
});

test('an unparseable receipt is exit 3, never replaced', (t) => {
  const root = project(t);
  mkdirSync(path.join(root, '.dgf-factory'));
  writeFileSync(path.join(root, RECEIPT), '{oops');
  assert.throws(() => readReceipt(root), (err) => err.code === 3 && /cannot be read/.test(err.message));
  assert.equal(readFileSync(path.join(root, RECEIPT), 'utf8'), '{oops');
});

test('a path out of the project is refused, including through a symlink', (t) => {
  const root = project(t);
  const outside = project(t);
  assert.throws(() => ensureWithinRoot(root, '../x'), (err) => err.code === 3);
  assert.throws(() => ensureWithinRoot(root, '/etc/passwd'), (err) => err.code === 3);
  symlinkSync(outside, path.join(root, 'link'));
  assert.throws(() => ensureWithinRoot(root, 'link/x.md'), (err) => err.code === 3 && /symlink/.test(err.message));
  assert.ok(ensureWithinRoot(root, 'a/b/c.md').endsWith(path.join('a', 'b', 'c.md')));
});

test('an atomic write leaves no temporary file, and a failed one leaves the old file', (t) => {
  const root = project(t);
  const journal = new Journal();
  writeAtomic(root, 'dir/file.txt', Buffer.from('old'), { journal });
  assert.deepEqual(journal.written, ['dir/file.txt']);
  // a folder where the file should go makes the rename fail
  mkdirSync(path.join(root, 'dir', 'blocked'));
  assert.throws(() => writeAtomic(root, 'dir/blocked', Buffer.from('new'), { journal }), (err) => err.code === 1);
  assert.deepEqual(journal.failed.map((f) => f.rel), ['dir/blocked']);
  assert.equal(readFileSync(path.join(root, 'dir', 'file.txt'), 'utf8'), 'old');
  assert.deepEqual(readdirSync(path.join(root, 'dir')).filter((name) => name.endsWith('.tmp')), []);
});

test('a receipt that fails mid-run is not written', (t) => {
  const root = project(t);
  const bad = sample();
  delete bad.files['.claude/skills/dgf/SKILL.md'].owner;
  assert.throws(() => writeReceipt(root, bad), (err) => err.code === 3);
  assert.equal(existsSync(path.join(root, RECEIPT)), false);
});

test('pruning stops at the first non-empty folder', (t) => {
  const root = project(t);
  writeAtomic(root, 'a/b/c/file.txt', Buffer.from('x'));
  writeAtomic(root, 'a/keep.txt', Buffer.from('x'));
  rmSync(path.join(root, 'a/b/c/file.txt'));
  pruneEmptyDirs(root, 'a/b/c/file.txt');
  assert.equal(existsSync(path.join(root, 'a/b')), false);
  assert.equal(existsSync(path.join(root, 'a/keep.txt')), true);
});
