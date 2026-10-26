// The validators' Python environment, inside the project (ADR 0031 §6).
//
// Find a Python 3.9+, create .dgf-factory/runtime/.venv when it is absent, and install the hash-pinned
// requirements into it — skipped when both packages already import, so a re-run needs no network. pip
// never runs outside the environment. A failure leaves the installed files alone; setup reports the
// command and exits 2.
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';

import * as log from './log.mjs';
import { RUNTIME_DIR } from './transform.mjs';

export const VENV = `${RUNTIME_DIR}/.venv`;
export const REQUIREMENTS = `${RUNTIME_DIR}/scripts/requirements.txt`;
const MINIMUM = [3, 9];
const PROBE = "import sys; print('%d.%d.%d' % sys.version_info[:3])";

export function venvPython(projectRoot, windows = process.platform === 'win32') {
  return path.join(projectRoot, VENV, windows ? path.join('Scripts', 'python.exe') : path.join('bin', 'python'));
}

/** The command a user runs by hand: what --no-python prints, and what a failure reports. */
export function manualCommand(windows = process.platform === 'win32') {
  const python = windows ? 'python' : 'python3';
  const venvPy = windows ? `${VENV}\\Scripts\\python.exe` : `${VENV}/bin/python`;
  return `${python} -m venv ${VENV} && ${venvPy} -m pip install --require-hashes -r ${REQUIREMENTS}`;
}

function run(spawn, command, args, cwd) {
  log.debug('python.run', 'spawn', { command: [command, ...args].join(' ') });
  const result = spawn(command, args, { cwd, encoding: 'utf8' });
  return { ok: !result.error && result.status === 0, stdout: result.stdout ?? '', stderr: result.stderr ?? '', error: result.error };
}

function atLeast(version) {
  const [major, minor] = version.split('.').map(Number);
  return major > MINIMUM[0] || (major === MINIMUM[0] && minor >= MINIMUM[1]);
}

/** The first interpreter that answers, with its version: { command, version } or null. */
export function findPython(spawn = spawnSync, windows = process.platform === 'win32') {
  const candidates = windows ? ['python', 'python3', 'py'] : ['python3', 'python'];
  for (const command of candidates) {
    const result = run(spawn, command, ['-c', PROBE]);
    if (result.ok && /^\d+\.\d+\.\d+/.test(result.stdout.trim())) {
      log.debug('python.findPython', 'found', { command, version: result.stdout.trim() });
      return { command, version: result.stdout.trim() };
    }
  }
  return null;
}

/** What the step would do, for the preview. */
export function previewPython(projectRoot, { skip }) {
  if (skip) return [`skipped (--no-python) — run by hand: ${manualCommand()}`];
  if (existsSync(venvPython(projectRoot))) return [`${VENV} exists — install lxml and jsonschema into it if either is missing`];
  return [`create ${VENV}, then install lxml and jsonschema into it from ${REQUIREMENTS} (needs network)`];
}

/** Run the step. Returns { status, lines }: status is ready | skipped | failed. */
export function setupPython(projectRoot, { skip = false, spawn = spawnSync, windows = process.platform === 'win32' } = {}) {
  if (skip) {
    log.info('python.setupPython', 'skipped by --no-python');
    return { status: 'skipped', lines: [`Python step skipped. Run: ${manualCommand(windows)}`] };
  }
  const venvPy = venvPython(projectRoot, windows);
  if (!existsSync(venvPy)) {
    const python = findPython(spawn, windows);
    if (!python) return failed(`no Python interpreter found (tried python3 and python); install Python ${MINIMUM.join('.')}+`, windows);
    if (!atLeast(python.version)) return failed(`${python.command} is ${python.version}; the validators need ${MINIMUM.join('.')}+`, windows);
    const made = run(spawn, python.command, ['-m', 'venv', VENV], projectRoot);
    if (!made.ok) return failed(`could not create ${VENV}: ${tail(made)}`, windows);
    log.info('python.setupPython', 'created the environment', { venv: VENV, python: python.version });
  }
  if (run(spawn, venvPy, ['-c', 'import lxml.etree, jsonschema'], projectRoot).ok) {
    log.info('python.setupPython', 'dependencies already installed');
    return { status: 'ready', lines: [`${VENV}: lxml and jsonschema are installed`] };
  }
  const pip = run(spawn, venvPy, ['-m', 'pip', 'install', '--require-hashes', '-r', REQUIREMENTS], projectRoot);
  if (!pip.ok) return failed(`pip could not install the requirements: ${tail(pip)}`, windows);
  log.info('python.setupPython', 'installed the requirements', { venv: VENV });
  return { status: 'ready', lines: [`${VENV}: installed lxml and jsonschema from ${REQUIREMENTS}`] };
}

function tail(result) {
  const text = (result.stderr || result.stdout || String(result.error ?? '')).trim().split('\n');
  return text.slice(-3).join(' | ');
}

function failed(reason, windows) {
  log.error('python.setupPython', 'failed', { reason });
  return { status: 'failed', lines: [`Python step failed: ${reason}`, `The files are installed. Re-run setup, or run: ${manualCommand(windows)}`] };
}
