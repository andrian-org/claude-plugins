// Writing inside a project, and nowhere else (ADR 0029 §6).
//
// A target is a project-relative path: no `..`, not absolute, and — once symlinks are resolved — still
// under the project root, as AI Factory checks its own targets (`dist/core/installer.js:27-38,112-127`).
// Every write goes to a temporary file in the same folder, is flushed, and is renamed into place, so a
// reader sees the old file or the new one, never half of either. The temporary name carries random
// bytes and is created exclusively, never through a symlink, so a file planted in a cloned repository
// cannot redirect the write; a target that is itself a symlink is refused, never replaced. A Journal
// records what was written and what failed, for the end-of-run report.
import { randomBytes } from 'node:crypto';
import { chmodSync, closeSync, constants, existsSync, fsyncSync, lstatSync, mkdirSync, openSync, realpathSync, renameSync, rmSync, rmdirSync, statSync, writeSync } from 'node:fs';
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

// Create, write only, fail if anything — a file or a symlink — is already there, and never follow one.
// O_NOFOLLOW is absent on Windows, where O_EXCL alone refuses an existing name.
const CREATE_NEW = constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | (constants.O_NOFOLLOW ?? 0);

/** True when `abs` is a symbolic link; false when it is anything else or absent. */
export function isSymlink(abs) {
  try {
    return lstatSync(abs).isSymbolicLink();
  } catch {
    return false;
  }
}

function refuseSymlinkTarget(target, rel, journal) {
  if (!isSymlink(target)) return;
  journal?.failed.push({ rel, error: 'symlink' });
  log.error('fsops.writeAtomic', 'refused: the target is a symbolic link', { file: rel });
  throw new CliError(EXIT_BLOCKED, `refusing to write ${rel}: it is a symbolic link — remove it, then re-run`);
}

export function writeAtomic(root, rel, bytes, { mode, journal } = {}) {
  const target = ensureWithinRoot(root, rel);
  refuseSymlinkTarget(target, rel, journal);
  const temp = path.join(path.dirname(target), `.${path.basename(target)}.dgf-factory-${randomBytes(12).toString('hex')}.tmp`);
  let created = false;
  try {
    mkdirSync(path.dirname(target), { recursive: true });
    const fd = openSync(temp, CREATE_NEW, mode ?? 0o644);
    created = true;
    try {
      writeSync(fd, bytes);
      fsyncSync(fd);
    } finally {
      closeSync(fd);
    }
    if (mode !== undefined) chmodSync(temp, mode);
    renameSync(temp, target);
  } catch (err) {
    if (created) rmSync(temp, { force: true });
    journal?.failed.push({ rel, error: err.code || err.message });
    log.error('fsops.writeAtomic', 'write failed', { file: rel, error: err.code || err.message });
    throw new CliError(EXIT_BLOCKED, `could not write ${rel}: ${err.message}`);
  }
  journal?.written.push(rel);
  log.debug('fsops.writeAtomic', 'written', { file: rel, bytes: bytes.length });
  return target;
}

/**
 * Remove one recorded file. A symlinked folder on the way is refused: it would point a receipt's
 * entry — say `.claude/skills/x/Program.cs` — at a project file setup never wrote. A symlink at
 * `rel` itself is removed as a link; what it points at is never touched.
 */
export function removeFile(root, rel, { journal } = {}) {
  const target = ensureWithinRoot(root, rel);
  const parent = path.dirname(target);
  if (existsSync(parent) && realpathSync(parent) !== parent) {
    log.error('fsops.removeFile', 'refused: a symlinked folder', { file: rel, resolved: realpathSync(parent) });
    throw new CliError(EXIT_BLOCKED, `refusing to remove ${rel}: a symlinked folder takes it to ${path.relative(realpathSync(root), realpathSync(parent)) || '.'}`);
  }
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
