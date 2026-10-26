// dgf-factory setup — install, or update, the pipeline in a project (ADR 0029).
//
// Resolve the project, choose the harnesses, plan every file against the receipt, preview it, ask,
// then write: the runtime, each harness's skills, the MCP entries, the Python environment, and the
// receipt last. Re-running it is the update. It never runs the /dgf interview, never edits the
// project's .gitignore, and never writes outside the project.
import { existsSync, readFileSync, statSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createInterface } from 'node:readline/promises';

import { CliError, EXIT_BLOCKED, EXIT_CLEAN, EXIT_USAGE, EXIT_WARNINGS, usageError } from '../exit.mjs';
import { Journal, ensureWithinRoot, pruneEmptyDirs, removeFile, writeAtomic } from '../fsops.mjs';
import { HARNESSES, harnessIds, selectHarnesses } from '../harnesses.mjs';
import * as log from '../log.mjs';
import { applyMcp, planMcp, previewMcp } from '../mcp.mjs';
import { packageRoot, packageVersion } from '../paths.mjs';
import { countKinds, planInstall } from '../plan.mjs';
import { isNoop, renderPreview } from '../preview.mjs';
import { previewPython, setupPython } from '../python.mjs';
import { RECEIPT, emptyReceipt, readReceipt, serialise, validate } from '../receipt.mjs';

export const SUMMARY = 'install or update dgf-factory in this project, for the harnesses you choose';

const OPTIONS = {
  harness: { type: 'string' },
  root: { type: 'string' },
  yes: { type: 'boolean', default: false },
  'dry-run': { type: 'boolean', default: false },
  'no-python': { type: 'boolean', default: false },
  help: { type: 'boolean', default: false },
};

export const USAGE = `Usage: dgf-factory setup [--harness <id,id,…>] [--root <dir>] [--yes] [--dry-run] [--no-python]

  --harness    the harnesses to install for: ${harnessIds().join(', ')}
               (asked for when omitted, on a terminal; required otherwise)
  --root       the project folder (default: the current folder)
  --yes        apply without asking: creates, updates, recreating missing files and removing
               unedited files no longer shipped. Never a conflict: an edited file is always kept.
  --dry-run    print the preview and stop
  --no-python  skip the validators' Python environment, and print the command instead`;

// --- 1. the project ---------------------------------------------------------------------------

export function resolveProject(rootOption, cwd = process.cwd()) {
  const root = path.resolve(cwd, rootOption ?? '.');
  if (!existsSync(root) || !statSync(root).isDirectory()) throw usageError(`not a folder: ${root}`);
  if (root === path.parse(root).root || root === os.homedir()) {
    throw usageError(`refusing to install into ${root}: run setup in a project folder`);
  }
  log.debug('setup.resolveProject', 'project', { root });
  return root;
}

// --- 2. the harnesses -------------------------------------------------------------------------

function previouslySelected(receipt) {
  return (receipt?.harnesses ?? []).filter((h) => h.selected).map((h) => h.id);
}

async function askHarnesses(receipt, io) {
  const preselected = new Set(previouslySelected(receipt));
  const lines = HARNESSES.map((h, i) => `  ${String(i + 1).padStart(2)}. [${preselected.has(h.id) ? 'x' : ' '}] ${h.displayName} (${h.skillsDir}/)`);
  io.output.write(`Install for which harnesses?\n${lines.join('\n')}\n`);
  const hint = preselected.size ? ` [Enter keeps ${[...preselected].join(', ')}]` : '';
  const answer = (await io.question(`Numbers or ids, comma-separated${hint}: `)).trim();
  if (!answer && preselected.size) return [...preselected];
  const ids = answer.split(/[\s,]+/).filter(Boolean).map((token) => (/^\d+$/.test(token) ? HARNESSES[Number(token) - 1]?.id ?? token : token));
  if (!ids.length) throw usageError('no harness chosen');
  return ids;
}

async function chooseHarnesses(options, receipt, io) {
  if (options.harness !== undefined) {
    const ids = options.harness.split(',').map((s) => s.trim()).filter(Boolean);
    if (!ids.length) throw usageError('--harness names no harness');
    return selectHarnesses(ids);
  }
  if (!io) throw usageError(`no terminal to ask on — pass --harness (one or more of: ${harnessIds().join(', ')})`);
  return selectHarnesses(await askHarnesses(receipt, io));
}

// --- 3. applying ------------------------------------------------------------------------------

async function confirm(io, question) {
  const answer = (await io.question(`${question} [y/N] `)).trim().toLowerCase();
  return answer === 'y' || answer === 'yes';
}

function entryOf(action) {
  return { source: action.source, owner: action.owner, sourceHash: action.sourceHash, installedHash: action.installedHash };
}

/** Write the accepted actions; return the receipt's `files`. Throws (exit 1) on the first failed write. */
function applyFiles(projectRoot, actions, accepted, journal) {
  const files = {};
  for (const action of actions) {
    switch (action.kind) {
      case 'create':
      case 'update':
        writeAtomic(projectRoot, action.rel, action.content, { journal });
        files[action.rel] = entryOf(action);
        break;
      case 'missing':
        if (accepted.missing) {
          writeAtomic(projectRoot, action.rel, action.content, { journal });
          files[action.rel] = entryOf(action);
        } else {
          files[action.rel] = action.previous ?? entryOf(action);
        }
        break;
      case 'unchanged':
        files[action.rel] = entryOf(action);
        break;
      case 'remove':
        if (accepted.remove) {
          removeFile(projectRoot, action.rel, { journal });
          pruneEmptyDirs(projectRoot, action.rel);
        } else {
          files[action.rel] = action.previous;
        }
        break;
      case 'keep-edited':
      case 'conflict':
      case 'carried':
        files[action.rel] = action.previous;
        break;
      default: // gone, conflict-unmanaged: nothing to record
        break;
    }
  }
  return files;
}

function buildReceipt(previous, version, harnesses, files, mcp) {
  const receipt = emptyReceipt(version);
  const chosen = new Set(harnesses.map((h) => h.id));
  const ids = new Set([...chosen, ...(previous?.harnesses ?? []).map((h) => h.id)]);
  receipt.harnesses = [...ids].map((id) => ({ id, selected: chosen.has(id) }));
  receipt.files = files;
  for (const [id, entry] of Object.entries(previous?.mcp ?? {})) {
    if (!chosen.has(id)) receipt.mcp[id] = entry;
  }
  Object.assign(receipt.mcp, mcp);
  return validate(receipt);
}

function writeReceiptIfChanged(projectRoot, receipt, journal) {
  const bytes = Buffer.from(serialise(receipt), 'utf8');
  const abs = ensureWithinRoot(projectRoot, RECEIPT);
  if (existsSync(abs) && readFileSync(abs).equals(bytes)) {
    log.debug('setup.writeReceipt', 'unchanged');
    return false;
  }
  writeAtomic(projectRoot, RECEIPT, bytes, { journal });
  log.info('setup.writeReceipt', 'written', { files: Object.keys(receipt.files).length });
  return true;
}

function nextSteps(harnesses) {
  const lines = ['', 'Next:'];
  if (harnesses.some((h) => h.id === 'claude')) lines.push('  - in Claude Code: /dgf to set up the estate, then /dgf-doctor');
  if (harnesses.some((h) => h.transform === 'codex')) lines.push('  - in Codex: trust this project (it reads .codex/config.toml only then), then $dgf and $dgf-doctor');
  if (harnesses.some((h) => h.id !== 'claude' && h.transform !== 'codex')) lines.push('  - in the other harnesses: run the dgf skill, then dgf-doctor');
  lines.push(`  - commit .dgf-factory/ and the harness folders (${harnesses.map((h) => `${h.skillsDir}/`).join(', ')}); .dgf-factory/runtime/.venv stays ignored`);
  return lines;
}

function report(out, { actions, mcpActions, python, journal, receiptWritten }) {
  const counts = countKinds(actions);
  const written = journal.written.filter((rel) => rel !== RECEIPT).length;
  out.write(`\nWritten: ${written} file(s); removed: ${journal.removed.length}; unchanged: ${counts.unchanged ?? 0}`
    + `${receiptWritten ? '; receipt updated' : ''}\n`);
  for (const action of actions.filter((a) => ['keep-edited', 'conflict', 'conflict-unmanaged'].includes(a.kind))) {
    out.write(`  kept  ${action.rel} (${action.kind})\n`);
  }
  for (const line of previewMcp(mcpActions.filter((a) => a.kind !== 'register' && a.kind !== 'unchanged'))) out.write(`  ${line}\n`);
  for (const line of python.lines) out.write(`${line}\n`);
}

function exitCodeOf(actions, mcpActions, python) {
  if (mcpActions.some((a) => a.kind === 'invalid')) return EXIT_BLOCKED;
  const attention = actions.some((a) => ['keep-edited', 'conflict', 'conflict-unmanaged'].includes(a.kind))
    || mcpActions.some((a) => a.kind === 'conflict' || a.kind === 'manual')
    || python.status === 'failed';
  return attention ? EXIT_WARNINGS : EXIT_CLEAN;
}

// --- the command ------------------------------------------------------------------------------

function terminal() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) return null;
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  return { question: (q) => rl.question(q), output: process.stdout, close: () => rl.close() };
}

export async function run(argv, { parseArgs }, { io = terminal(), out = process.stdout, pkgRoot = packageRoot(), spawn } = {}) {
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
  try {
    return await setup(options, { io, out, pkgRoot, spawn });
  } finally {
    io?.close?.();
  }
}

async function setup(options, { io, out, pkgRoot, spawn }) {
  const projectRoot = resolveProject(options.root);
  const receipt = readReceipt(projectRoot);
  const harnesses = await chooseHarnesses(options, receipt, io);
  log.info('setup.plan', 'planning', { project: projectRoot, harnesses: harnesses.map((h) => h.id).join(',') });

  const actions = planInstall({ projectRoot, harnesses, receipt, packageRoot: pkgRoot });
  const mcpActions = planMcp(projectRoot, harnesses);
  out.write(renderPreview({ projectRoot, harnesses, actions, mcp: previewMcp(mcpActions), python: previewPython(projectRoot, { skip: options['no-python'] }) }));
  log.info('setup.preview', 'shown', countKinds(actions));
  if (options['dry-run']) return EXIT_CLEAN;

  const accepted = { missing: options.yes, remove: options.yes };
  if (!isNoop(actions, mcpActions) && !options.yes) {
    if (!io) throw new CliError(EXIT_USAGE, 'no terminal to confirm on — pass --yes to apply, or --dry-run to preview only');
    if (!(await confirm(io, 'Apply?'))) {
      out.write('Nothing written.\n');
      return EXIT_CLEAN;
    }
    if (actions.some((a) => a.kind === 'missing')) accepted.missing = await confirm(io, 'Recreate the missing files?');
    if (actions.some((a) => a.kind === 'remove')) accepted.remove = await confirm(io, 'Remove the files no longer shipped?');
  }

  const journal = new Journal();
  let files;
  let mcp;
  try {
    log.info('setup.apply', 'writing');
    files = applyFiles(projectRoot, actions, accepted, journal);
    mcp = applyMcp(projectRoot, mcpActions, journal);
  } catch (err) {
    if (!(err instanceof CliError)) throw err;
    out.write(`\nStopped: ${err.message}\nWritten before the failure (${journal.written.length}): ${journal.written.join(', ') || 'none'}\n`
      + 'The receipt was not updated. Fix the cause and re-run setup: it resumes from what is on disk.\n');
    return EXIT_BLOCKED;
  }
  log.info('setup.python', 'environment');
  const python = setupPython(projectRoot, { skip: options['no-python'], ...(spawn ? { spawn } : {}) });
  const receiptWritten = writeReceiptIfChanged(projectRoot, buildReceipt(receipt, packageVersion(pkgRoot), harnesses, files, mcp), journal);
  report(out, { actions, mcpActions, python, journal, receiptWritten });
  out.write(`${nextSteps(harnesses).join('\n')}\n`);
  return exitCodeOf(actions, mcpActions, python);
}
