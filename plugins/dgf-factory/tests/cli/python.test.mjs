// The Python step, with every external command faked.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { REQUIREMENTS, VENV, manualCommand, setupPython, venvPython } from '../../cli/python.mjs';

function project(t) {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'dgf-py-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

/** A fake spawnSync: answers by the joined command line, and records every call. */
function fakeSpawn(answers, projectRoot) {
  const calls = [];
  const spawn = (command, args) => {
    const line = [command, ...args].join(' ');
    calls.push(line);
    for (const [pattern, answer] of answers) {
      if (pattern.test(line)) {
        if (answer.makeVenv) {
          mkdirSync(path.dirname(venvPython(projectRoot, false)), { recursive: true });
          writeFileSync(venvPython(projectRoot, false), '');
        }
        return { status: answer.status ?? 0, stdout: answer.stdout ?? '', stderr: answer.stderr ?? '' };
      }
    }
    return { status: 127, stdout: '', stderr: 'not found', error: new Error('ENOENT') };
  };
  return { spawn, calls };
}

test('--no-python skips and prints the command', (t) => {
  const result = setupPython(project(t), { skip: true, windows: false });
  assert.equal(result.status, 'skipped');
  assert.match(result.lines[0], new RegExp(`-m venv ${VENV}`));
});

test('a fresh project: find Python, create the venv, install the pinned requirements into it', (t) => {
  const root = project(t);
  const { spawn, calls } = fakeSpawn([
    [/^python3 -c/, { stdout: '3.11.4\n' }],
    [/^python3 -m venv/, { makeVenv: true }],
    [/bin\/python -c import lxml/, { status: 1 }],
    [/bin\/python -m pip install --require-hashes -r/, {}],
  ], root);
  const result = setupPython(root, { spawn, windows: false });
  assert.equal(result.status, 'ready', result.lines.join('\n'));
  assert.ok(calls.some((c) => c.endsWith(`-m pip install --require-hashes -r ${REQUIREMENTS}`)));
  assert.ok(calls.every((c) => !/^python3? -m pip/.test(c)), 'pip never runs outside the venv');
});

test('a venv that already has both packages needs no pip and no network', (t) => {
  const root = project(t);
  mkdirSync(path.dirname(venvPython(root, false)), { recursive: true });
  writeFileSync(venvPython(root, false), '');
  const { spawn, calls } = fakeSpawn([[/bin\/python -c import lxml/, {}]], root);
  assert.equal(setupPython(root, { spawn, windows: false }).status, 'ready');
  assert.ok(!calls.some((c) => c.includes('pip')));
});

test('no Python is a failure that names the manual command', (t) => {
  const { spawn } = fakeSpawn([], project(t));
  const result = setupPython(project(t), { spawn, windows: false });
  assert.equal(result.status, 'failed');
  assert.match(result.lines.join('\n'), /no Python interpreter found/);
  assert.match(result.lines.join('\n'), /Re-run setup, or run:/);
});

test('Python older than 3.9 is refused', (t) => {
  const { spawn, calls } = fakeSpawn([[/^python3 -c/, { stdout: '3.8.10\n' }]], project(t));
  const result = setupPython(project(t), { spawn, windows: false });
  assert.equal(result.status, 'failed');
  assert.match(result.lines[0], /3\.8\.10.*3\.9\+/);
  assert.ok(!calls.some((c) => c.includes('venv')));
});

test('a pip failure reports its last lines and leaves the step failed', (t) => {
  const root = project(t);
  const { spawn } = fakeSpawn([
    [/^python3 -c/, { stdout: '3.9.6\n' }],
    [/^python3 -m venv/, { makeVenv: true }],
    [/-c import lxml/, { status: 1 }],
    [/-m pip install/, { status: 1, stderr: 'ERROR: hash mismatch\n' }],
  ], root);
  const result = setupPython(root, { spawn, windows: false });
  assert.equal(result.status, 'failed');
  assert.match(result.lines[0], /hash mismatch/);
});

test('the Windows command uses Scripts\\python.exe', () => {
  assert.match(manualCommand(true), /Scripts\\python\.exe -m pip install/);
});
