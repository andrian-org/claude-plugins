// Writing and removing inside a project: a symlink planted in a cloned repository never redirects either.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { Journal, removeFile, writeAtomic } from '../../cli/fsops.mjs';

function folder(t, prefix) {
  const dir = mkdtempSync(path.join(os.tmpdir(), prefix));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function victim(t) {
  const file = path.join(folder(t, 'dgf-outside-'), 'victim.txt');
  writeFileSync(file, 'untouched\n');
  return file;
}

test('a symlink planted at the old predictable temporary name is never written through', (t) => {
  const root = folder(t, 'dgf-fsops-');
  const target = victim(t);
  mkdirSync(path.join(root, '.claude/skills/dgf'), { recursive: true });
  // the name writeAtomic used to derive from the pid alone
  symlinkSync(target, path.join(root, `.claude/skills/dgf/.SKILL.md.dgf-factory-${process.pid}.tmp`));
  writeAtomic(root, '.claude/skills/dgf/SKILL.md', Buffer.from('payload\n'));
  assert.equal(readFileSync(target, 'utf8'), 'untouched\n');
  assert.equal(readFileSync(path.join(root, '.claude/skills/dgf/SKILL.md'), 'utf8'), 'payload\n');
  assert.equal(lstatSync(path.join(root, '.claude/skills/dgf/SKILL.md')).isSymbolicLink(), false);
});

test('the temporary name is random: two writes never share it, and none is left behind', (t) => {
  const root = folder(t, 'dgf-fsops-');
  writeAtomic(root, 'a.json', Buffer.from('1'));
  writeAtomic(root, 'a.json', Buffer.from('2'));
  assert.equal(readFileSync(path.join(root, 'a.json'), 'utf8'), '2');
  assert.deepEqual(readdirSync(root), ['a.json']);
});

test('a target that is itself a symlink is refused, and neither it nor what it points at changes', (t) => {
  const root = folder(t, 'dgf-fsops-');
  const target = victim(t);
  symlinkSync(target, path.join(root, '.mcp.json'));
  const journal = new Journal();
  assert.throws(() => writeAtomic(root, '.mcp.json', Buffer.from('{"hooks":{}}\n'), { journal }),
    (err) => err.code === 1 && /symbolic link/.test(err.message));
  assert.equal(lstatSync(path.join(root, '.mcp.json')).isSymbolicLink(), true);
  assert.equal(readFileSync(target, 'utf8'), 'untouched\n');
  assert.deepEqual(journal.failed.map((f) => f.rel), ['.mcp.json']);
  assert.deepEqual(journal.written, []);
});

test('a symlink inside the project at a target is refused too', (t) => {
  const root = folder(t, 'dgf-fsops-');
  writeFileSync(path.join(root, 'Program.cs'), 'class P {}\n');
  mkdirSync(path.join(root, '.claude/skills/dgf'), { recursive: true });
  symlinkSync(path.join(root, 'Program.cs'), path.join(root, '.claude/skills/dgf/SKILL.md'));
  assert.throws(() => writeAtomic(root, '.claude/skills/dgf/SKILL.md', Buffer.from('x')), (err) => err.code === 1);
  assert.equal(readFileSync(path.join(root, 'Program.cs'), 'utf8'), 'class P {}\n');
});

test('a recorded file behind a symlinked folder inside the project is never removed', (t) => {
  const root = folder(t, 'dgf-fsops-');
  mkdirSync(path.join(root, 'src'));
  writeFileSync(path.join(root, 'src/Program.cs'), 'class P {}\n');
  mkdirSync(path.join(root, '.claude/skills'), { recursive: true });
  symlinkSync(path.join(root, 'src'), path.join(root, '.claude/skills/evil'));
  assert.throws(() => removeFile(root, '.claude/skills/evil/Program.cs'), (err) => err.code === 1 && /symlinked folder/.test(err.message));
  assert.equal(readFileSync(path.join(root, 'src/Program.cs'), 'utf8'), 'class P {}\n');
});

test('a recorded file that is a symlink is removed as a link; what it points at stays', (t) => {
  const root = folder(t, 'dgf-fsops-');
  const target = victim(t);
  mkdirSync(path.join(root, '.claude/skills/dgf'), { recursive: true });
  symlinkSync(target, path.join(root, '.claude/skills/dgf/SKILL.md'));
  removeFile(root, '.claude/skills/dgf/SKILL.md');
  assert.deepEqual(readdirSync(path.join(root, '.claude/skills/dgf')), []);
  assert.equal(readFileSync(target, 'utf8'), 'untouched\n');
});
