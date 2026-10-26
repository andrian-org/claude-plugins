// What setup would do, file by file, before it does anything (ADR 0029 §5-6).
//
// Two kinds of file are installed:
//   runtime   every payload file under skills/, scripts/ and knowledge/, at .dgf-factory/runtime/<same
//             path>, plus a managed .gitignore for the runtime's .venv/ and __pycache__/
//   harness   each skill's SKILL.md at <skillsDir>/<skill>/SKILL.md, rendered for that harness
//
// Each is decided against the receipt and the file on disk, by the ADR's table. Nothing here writes.
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';

import { unifiedDiff } from './diff.mjs';
import { ensureWithinRoot } from './fsops.mjs';
import { hashBytes, isText } from './hash.mjs';
import * as log from './log.mjs';
import { RUNTIME_DIR, renderRuntimeFile, renderSkill } from './transform.mjs';

export const PAYLOAD_DIRS = ['skills', 'scripts', 'knowledge'];
// The same exclusions as package.json `files`, so a source checkout installs what the tarball holds.
const EXCLUDED_NAMES = new Set(['__pycache__', '.DS_Store']);
const EXCLUDED_PATHS = ['skills/dgf-scaffold/templates/solution/obj', 'skills/dgf-scaffold/templates/solution/bin'];
export const RUNTIME_GITIGNORE = `${RUNTIME_DIR}/.gitignore`;
const GITIGNORE_TEXT = '# Managed by dgf-factory setup: the validators\' environment and bytecode are never committed.\n.venv/\n__pycache__/\n';

// The order a preview lists them in: what needs the user first.
export const KINDS = ['conflict-unmanaged', 'conflict', 'keep-edited', 'missing', 'remove', 'create', 'update', 'unchanged'];

function excluded(rel, name) {
  return EXCLUDED_NAMES.has(name) || name.endsWith('.pyc') || EXCLUDED_PATHS.some((p) => rel === p || rel.startsWith(`${p}/`));
}

/** Every payload file in the package, as package-relative POSIX paths, sorted. */
export function payloadFiles(packageRoot) {
  const found = [];
  const walk = (rel) => {
    for (const name of readdirSync(path.join(packageRoot, rel)).sort()) {
      const child = rel ? `${rel}/${name}` : name;
      if (excluded(child, name)) continue;
      if (statSync(path.join(packageRoot, child)).isDirectory()) walk(child);
      else found.push(child);
    }
  };
  for (const dir of PAYLOAD_DIRS) walk(dir);
  log.debug('plan.payloadFiles', 'listed', { files: found.length });
  return found;
}

export function skillNames(packageRoot) {
  return readdirSync(path.join(packageRoot, 'skills')).filter((name) => existsSync(path.join(packageRoot, 'skills', name, 'SKILL.md'))).sort();
}

/** What the install should hold: target → { source, owner, sourceBytes, content }. */
export function desiredFiles(packageRoot, harnesses) {
  const desired = new Map();
  for (const rel of payloadFiles(packageRoot)) {
    const sourceBytes = readFileSync(path.join(packageRoot, rel));
    desired.set(`${RUNTIME_DIR}/${rel}`, { source: rel, owner: 'runtime', sourceBytes, content: renderRuntimeFile(rel, sourceBytes) });
  }
  const gitignore = Buffer.from(GITIGNORE_TEXT, 'utf8');
  desired.set(RUNTIME_GITIGNORE, { source: '(generated)', owner: 'runtime', sourceBytes: gitignore, content: gitignore });
  for (const harness of harnesses) {
    for (const skill of skillNames(packageRoot)) {
      const source = `skills/${skill}/SKILL.md`;
      const sourceBytes = readFileSync(path.join(packageRoot, source));
      const target = `${harness.skillsDir}/${skill}/SKILL.md`;
      if (desired.has(target)) continue;
      desired.set(target, { source, owner: harness.id, sourceBytes, content: Buffer.from(renderSkill(harness, sourceBytes.toString('utf8'), source), 'utf8') });
    }
  }
  return desired;
}

function diffFor(rel, disk, content) {
  if (!isText(disk) || !isText(content)) return `  (${rel}: binary — not diffed)`;
  return unifiedDiff(disk.toString('utf8'), content.toString('utf8'), rel);
}

/** One desired file against its receipt entry and the disk. */
export function decide(rel, want, previous, disk) {
  const sourceHash = hashBytes(want.sourceBytes, want.source);
  const installedHash = hashBytes(want.content, rel);
  const base = { rel, owner: want.owner, source: want.source, sourceHash, installedHash, content: want.content };
  if (disk === null) {
    return { ...base, kind: previous ? 'missing' : 'create' };
  }
  const diskHash = hashBytes(disk, rel);
  if (diskHash === installedHash) return { ...base, kind: 'unchanged' };
  if (!previous) return { ...base, kind: 'conflict-unmanaged', diff: diffFor(rel, disk, want.content) };
  const edited = diskHash !== previous.installedHash;
  const changed = installedHash !== previous.installedHash;
  if (!edited) return { ...base, kind: 'update' };
  if (!changed) return { ...base, kind: 'keep-edited', previous };
  return { ...base, kind: 'conflict', previous, diff: diffFor(rel, disk, want.content) };
}

function readDisk(projectRoot, rel) {
  const abs = ensureWithinRoot(projectRoot, rel);
  return existsSync(abs) && statSync(abs).isFile() ? readFileSync(abs) : null;
}

/**
 * Every action setup would take. A harness dropped from the selection is left alone — `uninstall`
 * removes it — and its receipt entries are carried over untouched.
 */
export function planInstall({ projectRoot, harnesses, receipt, packageRoot }) {
  const desired = desiredFiles(packageRoot, harnesses);
  const previousFiles = receipt?.files ?? {};
  const selected = new Set(harnesses.map((h) => h.id));
  const actions = [];
  for (const [rel, want] of desired) {
    actions.push(decide(rel, want, previousFiles[rel] ?? null, readDisk(projectRoot, rel)));
  }
  for (const [rel, previous] of Object.entries(previousFiles)) {
    if (desired.has(rel)) continue;
    if (previous.owner !== 'runtime' && !selected.has(previous.owner)) {
      actions.push({ rel, kind: 'carried', owner: previous.owner, previous });
      continue;
    }
    const disk = readDisk(projectRoot, rel);
    if (disk === null) {
      actions.push({ rel, kind: 'gone', owner: previous.owner, previous });
    } else if (hashBytes(disk, rel) === previous.installedHash) {
      actions.push({ rel, kind: 'remove', owner: previous.owner, previous });
    } else {
      actions.push({ rel, kind: 'keep-edited', owner: previous.owner, previous, orphan: true });
    }
  }
  const counts = countKinds(actions);
  log.info('plan.planInstall', 'planned', counts);
  for (const action of actions) log.debug('plan.planInstall', action.kind, { file: action.rel, owner: action.owner });
  return actions;
}

export function countKinds(actions) {
  const counts = {};
  for (const action of actions) counts[action.kind] = (counts[action.kind] ?? 0) + 1;
  return counts;
}

export function needsUser(action) {
  return action.kind === 'conflict' || action.kind === 'conflict-unmanaged' || action.kind === 'keep-edited';
}

