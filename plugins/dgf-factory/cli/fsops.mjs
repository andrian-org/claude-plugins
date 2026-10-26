// Writing inside a project, and nowhere else (ADR 0029 §6).
//
// A target is a project-relative path: no `..`, not absolute, and — once symlinks are resolved — still
// under the project root, as AI Factory checks its own targets (`dist/core/installer.js:27-38,112-127`).
// Every write goes to a temporary file in the same folder, is flushed, and is renamed into place, so a
// reader sees the old file or the new one, never half of either. A Journal records what was written and
// what failed, for the end-of-run report.
import { chmodSync, closeSync, existsSync, fsyncSync, mkdirSync, openSync, realpathSync, renameSync, rmSync, rmdirSync, statSync, writeSync } from 'node:fs';
import path from 'node:path';

import { CliError, EXIT_BLOCKED, usageError } from './exit.mjs';
import * as log from './log.mjs';

export class Journal {
  constructor() {
    this.written = [];
    this.removed = [];
    this.failed = [];
  }
}

function nearestExisting(dir) {
  let current = dir;
  while (!existsSync(current)) {
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return current;
}

/** The absolute path of `rel` under `root`, refusing anything that would land outside it. */
export function ensureWithinRoot(root, rel) {
  if (typeof rel !== 'string' || rel === '' || path.isAbsolute(rel) || /^[A-Za-z]:/.test(rel)
      || rel.split(/[\\/]/).includes('..')) {
    throw usageError(`refusing to write \`${rel}\`: not a path inside the project`);
  }
  const realRoot = realpathSync(root);
  const target = path.join(realRoot, rel);
  const anchor = realpathSync(nearestExisting(path.dirname(target)));
  if (anchor !== realRoot && !anchor.startsWith(realRoot + path.sep)) {
    throw usageError(`refusing to write \`${rel}\`: a symlink takes it outside the project (${anchor})`);
  }
  return target;
}

export function writeAtomic(root, rel, bytes, { mode, journal } = {}) {
  const target = ensureWithinRoot(root, rel);
  const temp = path.join(path.dirname(target), `.${path.basename(target)}.dgf-factory-${process.pid}.tmp`);
  try {
    mkdirSync(path.dirname(target), { recursive: true });
    const fd = openSync(temp, 'w', mode ?? 0o644);
    try {
      writeSync(fd, bytes);
      fsyncSync(fd);
    } finally {
      closeSync(fd);
    }
    if (mode !== undefined) chmodSync(temp, mode);
    renameSync(temp, target);
  } catch (err) {
    rmSync(temp, { force: true });
    journal?.failed.push({ rel, error: err.code || err.message });
    log.error('fsops.writeAtomic', 'write failed', { file: rel, error: err.code || err.message });
    throw new CliError(EXIT_BLOCKED, `could not write ${rel}: ${err.message}`);
  }
  journal?.written.push(rel);
  log.debug('fsops.writeAtomic', 'written', { file: rel, bytes: bytes.length });
  return target;
}

export function removeFile(root, rel, { journal } = {}) {
  const target = ensureWithinRoot(root, rel);
  rmSync(target, { force: true });
  journal?.removed.push(rel);
  log.debug('fsops.removeFile', 'removed', { file: rel });
}

/** Remove empty folders from `rel`'s parent up to, never including, `stopAt` (project-relative). */
export function pruneEmptyDirs(root, rel, stopAt = '') {
  let dir = path.posix.dirname(rel);
  while (dir && dir !== '.' && dir !== stopAt) {
    const abs = ensureWithinRoot(root, dir);
    try {
      if (!statSync(abs).isDirectory()) break;
      rmdirSync(abs);
    } catch {
      break;
    }
    log.debug('fsops.pruneEmptyDirs', 'removed empty folder', { dir });
    dir = path.posix.dirname(dir);
  }
}

export function readIfExists(root, rel) {
  const target = ensureWithinRoot(root, rel);
  return existsSync(target) ? target : null;
}
