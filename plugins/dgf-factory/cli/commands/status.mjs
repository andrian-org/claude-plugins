// dgf-factory status — what is installed here, and what changed since (read-only).
//
// Reads the receipt and compares every file and MCP entry it records with the disk, per harness,
// and the receipt's version with this CLI's. It writes nothing.
import { existsSync } from 'node:fs';
import path from 'node:path';

import { EXIT_CLEAN, EXIT_USAGE, EXIT_WARNINGS, CliError, usageError } from '../exit.mjs';
import { HARNESSES } from '../harnesses.mjs';
import { hashFile } from '../hash.mjs';
import * as log from '../log.mjs';
import { currentEntryHash } from '../mcp.mjs';
import { packageRoot, packageVersion } from '../paths.mjs';
import { RECEIPT, readReceipt } from '../receipt.mjs';
import { resolveProject } from './setup.mjs';

export const SUMMARY = 'show what dgf-factory installed here, and what changed since';

const OPTIONS = {
  root: { type: 'string' },
  json: { type: 'boolean', default: false },
  help: { type: 'boolean', default: false },
};

export const USAGE = `Usage: dgf-factory status [--root <dir>] [--json]

  --root  the project folder (default: the current folder)
  --json  print the result as JSON`;

const BY_ID = new Map(HARNESSES.map((h) => [h.id, h]));

/** { version, cli, drift, groups: { <owner>: { unchanged, edited, missing } }, mcp: { <harness>: state } } */
export function inspect(projectRoot, receipt, cliVersion) {
  const groups = {};
  for (const [rel, entry] of Object.entries(receipt.files)) {
    const group = (groups[entry.owner] ??= { unchanged: 0, edited: [], missing: [] });
    const abs = path.join(projectRoot, rel);
    if (!existsSync(abs)) group.missing.push(rel);
    else if (hashFile(abs) !== entry.installedHash) group.edited.push(rel);
    else group.unchanged += 1;
    log.debug('status.inspect', 'checked', { file: rel });
  }
  const mcp = {};
  for (const [id, record] of Object.entries(receipt.mcp)) {
    const current = currentEntryHash(projectRoot, BY_ID.get(id), record.file);
    mcp[id] = { file: record.file, state: current === null ? 'missing' : current === record.entryHash ? 'unchanged' : 'edited' };
  }
  return { version: receipt.version, cli: cliVersion, drift: receipt.version !== cliVersion, harnesses: receipt.harnesses, groups, mcp };
}

function clean(result) {
  return !result.drift
    && Object.values(result.groups).every((g) => !g.edited.length && !g.missing.length)
    && Object.values(result.mcp).every((m) => m.state === 'unchanged');
}

function render(result, projectRoot) {
  const lines = [`dgf-factory status — ${projectRoot}`, `Installed by ${result.version}; this CLI is ${result.cli}${result.drift ? ' — run `dgf-factory setup` to update' : ''}`, ''];
  const owners = Object.keys(result.groups).sort((a, b) => (a === 'runtime' ? -1 : b === 'runtime' ? 1 : a.localeCompare(b)));
  for (const owner of owners) {
    const g = result.groups[owner];
    const selected = result.harnesses.find((h) => h.id === owner)?.selected;
    const label = owner === 'runtime' ? 'runtime (.dgf-factory/runtime/)' : `${owner}${selected === false ? ' (dropped from the selection; uninstall removes it)' : ''}`;
    lines.push(`${label}: ${g.unchanged} unchanged, ${g.edited.length} edited, ${g.missing.length} missing`);
    for (const rel of g.edited) lines.push(`  edited   ${rel}`);
    for (const rel of g.missing) lines.push(`  missing  ${rel}`);
  }
  const mcp = Object.entries(result.mcp);
  if (mcp.length) {
    lines.push('', 'MCP (dgf-mcp):');
    for (const [id, m] of mcp) lines.push(`  ${m.state.padEnd(9)} ${m.file} (${id})`);
  }
  return `${lines.join('\n')}\n`;
}

export async function run(argv, { parseArgs }, { out = process.stdout, pkgRoot = packageRoot() } = {}) {
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
  if (!receipt) throw new CliError(EXIT_USAGE, `no ${RECEIPT} in ${projectRoot} — dgf-factory is not installed here; run \`dgf-factory setup\``);
  const result = inspect(projectRoot, receipt, packageVersion(pkgRoot));
  out.write(options.json ? `${JSON.stringify(result, null, 2)}\n` : render(result, projectRoot));
  log.info('status.run', 'inspected', { drift: result.drift });
  return clean(result) ? EXIT_CLEAN : EXIT_WARNINGS;
}
