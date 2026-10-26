// dgf-factory uninstall — remove what setup installed, and only that (ADR 0029 §5-6).
//
// A file is removed only while it is exactly what setup wrote; an edited one is kept and reported.
// A `dgf-mcp` entry is removed only while it is unchanged, and never while another installed harness
// still uses the same file. The runtime — and its .venv — goes only when no harness is left. The
// pipeline's state — config.yaml, DESCRIPTION.md, plans/, patches/, skill-context/, evolutions/ — is
// never touched: it is the estate's, not the install's.
import { existsSync, readdirSync, rmSync, rmdirSync } from 'node:fs';
import path from 'node:path';

import { CliError, EXIT_CLEAN, EXIT_USAGE, EXIT_WARNINGS, usageError } from '../exit.mjs';
import { Journal, ensureWithinRoot, pruneEmptyDirs, removeFile, writeAtomic } from '../fsops.mjs';
import { HARNESSES } from '../harnesses.mjs';
import { hashFile } from '../hash.mjs';
import * as log from '../log.mjs';
import { removeMcpEntry } from '../mcp.mjs';
import { RECEIPT, readReceipt, serialise, validate } from '../receipt.mjs';
import { RUNTIME_DIR } from '../transform.mjs';
import { resolveProject } from './setup.mjs';

export const SUMMARY = 'remove what setup installed — only files you have not edited';

const OPTIONS = {
  harness: { type: 'string' },
  root: { type: 'string' },
  yes: { type: 'boolean', default: false },
  'dry-run': { type: 'boolean', default: false },
  help: { type: 'boolean', default: false },
};

export const USAGE = `Usage: dgf-factory uninstall [--harness <id,id,…>] [--root <dir>] [--yes] [--dry-run]

  --harness  remove only these harnesses (default: all, and then the runtime too)
  --root     the project folder (default: the current folder)
  --yes      remove without asking
  --dry-run  print what would be removed and stop

An edited file is never removed. config.yaml, DESCRIPTION.md, plans/, patches/, skill-context/
and evolutions/ under .dgf-factory/ are never touched.`;

const BY_ID = new Map(HARNESSES.map((h) => [h.id, h]));
const VENV = `${RUNTIME_DIR}/.venv`;

function chooseTargets(options, receipt) {
  const installed = receipt.harnesses.map((h) => h.id);
  if (options.harness === undefined) return installed;
  const ids = [...new Set(options.harness.split(',').map((s) => s.trim()).filter(Boolean))];
  const unknown = ids.filter((id) => !installed.includes(id));
  if (!ids.length || unknown.length) {
    throw usageError(`${unknown.length ? `not installed here: ${unknown.join(', ')}` : '--harness names no harness'} — installed: ${installed.join(', ') || 'none'}`);
  }
  return ids;
}

/** Each recorded file the uninstall concerns: remove | keep (edited) | gone (already missing). */
export function planUninstall(projectRoot, receipt, targets) {
  const remaining = receipt.harnesses.filter((h) => !targets.includes(h.id));
  const everything = remaining.length === 0;
  const files = [];
  for (const [rel, entry] of Object.entries(receipt.files)) {
    if (!(targets.includes(entry.owner) || (everything && entry.owner === 'runtime'))) continue;
    const abs = ensureWithinRoot(projectRoot, rel);
    const kind = !existsSync(abs) ? 'gone' : hashFile(abs) === entry.installedHash ? 'remove' : 'keep';
    files.push({ rel, owner: entry.owner, kind });
  }
  const sharedFiles = new Set(Object.entries(receipt.mcp).filter(([id]) => !targets.includes(id)).map(([, m]) => m.file));
  const mcp = Object.entries(receipt.mcp).filter(([id]) => targets.includes(id))
    .map(([id, record]) => ({ id, record, shared: sharedFiles.has(record.file) }));
  log.info('uninstall.plan', 'planned', { files: files.length, everything });
  return { files, mcp, everything, remaining };
}

function preview(projectRoot, plan, targets) {
  const lines = [`dgf-factory uninstall — ${projectRoot}`, `Removing: ${targets.join(', ')}${plan.everything ? ', and the runtime' : ''}`, ''];
  for (const f of plan.files.filter((x) => x.kind === 'keep')) lines.push(`  KEEP     ${f.rel} — you edited it`);
  for (const f of plan.files.filter((x) => x.kind === 'remove')) lines.push(`  remove   ${f.rel}`);
  for (const m of plan.mcp) lines.push(`  ${m.shared ? 'KEEP    ' : 'mcp     '} ${m.record.file} (${m.id})${m.shared ? ' — another installed harness uses it' : ' — the dgf-mcp entry, if unchanged'}`);
  if (plan.everything && existsSync(path.join(projectRoot, VENV))) lines.push(`  remove   ${VENV}/ (the validators' environment)`);
  return `${lines.join('\n')}\n`;
}

async function confirm(io) {
  const answer = (await io.question('Remove? [y/N] ')).trim().toLowerCase();
  return answer === 'y' || answer === 'yes';
}

function terminal() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) return null;
  return import('node:readline/promises').then(({ createInterface }) => {
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    return { question: (q) => rl.question(q), close: () => rl.close() };
  });
}

/** What setup's environment and the scripts' runs leave in the runtime: .venv/ and __pycache__/. */
function removeRuntimeLeftovers(projectRoot) {
  const runtime = ensureWithinRoot(projectRoot, RUNTIME_DIR);
  if (!existsSync(runtime)) return;
  rmSync(ensureWithinRoot(projectRoot, VENV), { recursive: true, force: true });
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const child = path.join(dir, entry.name);
      if (entry.name === '__pycache__') rmSync(child, { recursive: true, force: true });
      else walk(child);
    }
  };
  walk(runtime);
  const prune = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) if (entry.isDirectory()) prune(path.join(dir, entry.name));
    if (!readdirSync(dir).length) rmdirSync(dir);
  };
  prune(runtime);
  log.info('uninstall.removeRuntimeLeftovers', 'removed the environment and bytecode', { runtime: RUNTIME_DIR });
}

function leftBehind(projectRoot) {
  const pipeline = path.join(projectRoot, '.dgf-factory');
  const left = existsSync(pipeline) ? readdirSync(pipeline).filter((name) => name !== 'install.json' && name !== 'runtime') : [];
  return left.length ? `Left in .dgf-factory/ (the estate's, never removed): ${left.join(', ')}` : '';
}

export async function run(argv, { parseArgs }, { io, out = process.stdout } = {}) {
  let options;
  try {
    ({ values: options } = parseArgs({ args: argv, options: OPTIONS, strict: true, allowPositionals: false }));
  } catch (err) {
    throw usageError(`${err.message}\n\n${USAGE}`);
  }
  if (options.help) {
    out.write(`${USAGE}\n`);
    return EXIT_CLEAN;
  }
  const projectRoot = resolveProject(options.root);
  const receipt = readReceipt(projectRoot);
  if (!receipt) throw new CliError(EXIT_USAGE, `no ${RECEIPT} in ${projectRoot} — nothing to uninstall`);
  const targets = chooseTargets(options, receipt);
  const plan = planUninstall(projectRoot, receipt, targets);
  out.write(preview(projectRoot, plan, targets));
  if (options['dry-run']) return EXIT_CLEAN;
  if (!options.yes) {
    const tty = io ?? (await terminal());
    if (!tty) throw new CliError(EXIT_USAGE, 'no terminal to confirm on — pass --yes to remove, or --dry-run to preview only');
    try {
      if (!(await confirm(tty))) {
        out.write('Nothing removed.\n');
        return EXIT_CLEAN;
      }
    } finally {
      tty.close?.();
    }
  }

  const journal = new Journal();
  for (const f of plan.files.filter((x) => x.kind === 'remove')) {
    removeFile(projectRoot, f.rel, { journal });
    pruneEmptyDirs(projectRoot, f.rel);
    log.info('uninstall.run', 'removed', { file: f.rel });
  }
  const mcpOutcome = plan.mcp.map((m) => ({ ...m, outcome: m.shared ? 'shared' : removeMcpEntry(projectRoot, BY_ID.get(m.id), m.record, journal) }));
  if (plan.everything) removeRuntimeLeftovers(projectRoot);

  const kept = plan.files.filter((f) => f.kind === 'keep');
  const receiptAbs = ensureWithinRoot(projectRoot, RECEIPT);
  if (plan.everything) {
    rmSync(receiptAbs, { force: true });
    pruneEmptyDirs(projectRoot, RECEIPT);
  } else {
    const next = { ...receipt, harnesses: receipt.harnesses.filter((h) => !targets.includes(h.id)), files: {}, mcp: {} };
    for (const [rel, entry] of Object.entries(receipt.files)) if (!targets.includes(entry.owner)) next.files[rel] = entry;
    for (const [id, record] of Object.entries(receipt.mcp)) if (!targets.includes(id)) next.mcp[id] = record;
    writeAtomic(projectRoot, RECEIPT, Buffer.from(serialise(validate(next)), 'utf8'), { journal });
  }

  out.write(`\nRemoved: ${journal.removed.length} file(s)\n`);
  for (const f of kept) out.write(`  kept     ${f.rel} (edited — remove it by hand if you no longer want it)\n`);
  for (const m of mcpOutcome) {
    if (m.outcome === 'removed') out.write(`  mcp      ${m.record.file}: dgf-mcp removed\n`);
    if (m.outcome === 'edited') out.write(`  kept     ${m.record.file}: the dgf-mcp entry was changed — remove it by hand\n`);
    if (m.outcome === 'shared') out.write(`  kept     ${m.record.file}: still used by ${plan.remaining.map((h) => h.id).join(', ')}\n`);
  }
  const left = leftBehind(projectRoot);
  if (left) out.write(`${left}\n`);
  const attention = kept.length || mcpOutcome.some((m) => m.outcome === 'edited');
  return attention ? EXIT_WARNINGS : EXIT_CLEAN;
}
