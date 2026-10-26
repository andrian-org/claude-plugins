// The CLI's entry: --version, --help, and unknown input as a usage error (exit 3).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.resolve(fileURLToPath(new URL('../..', import.meta.url)));
const BIN = path.join(ROOT, 'bin', 'dgf-factory.mjs');
const VERSION = JSON.parse(readFileSync(path.join(ROOT, 'package.json'), 'utf8')).version;

function run(...args) {
  const env = { ...process.env };
  delete env.DEBUG;
  delete env.LOG_LEVEL;
  return spawnSync(process.execPath, [BIN, ...args], { encoding: 'utf8', env });
}

test('--version prints the package version', () => {
  const result = run('--version');
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), VERSION);
});

test('--help lists the commands and the exit codes', () => {
  const result = run('--help');
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Usage: dgf-factory <command>/);
  assert.match(result.stdout, /Exit codes: 0 clean, 1 blocked, 2 warnings, 3 usage error/);
});

test('no command prints the help and is a usage error', () => {
  const result = run();
  assert.equal(result.status, 3);
  assert.match(result.stdout, /Usage:/);
});

test('an unknown command is exit 3 and names it', () => {
  const result = run('frobnicate');
  assert.equal(result.status, 3);
  assert.match(result.stderr, /unknown command `frobnicate`/);
  assert.doesNotMatch(result.stderr, /at .*\.mjs/, 'no stack trace for a usage error');
});

test('DEBUG=1 traces to stderr, never stdout', () => {
  const result = spawnSync(process.execPath, [BIN, '--version'], { encoding: 'utf8', env: { ...process.env, DEBUG: '1' } });
  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), VERSION);
  assert.match(result.stderr, /DEBUG \[main\.main\] argv/);
});
