// Which DGF release line's knowledge pack a project gets (ADR 0036 §3).
//
// The package ships one pack per DGF release line: the current line's in knowledge/, each older
// line's in packs/<X.Y>/, all named in packs/lines.json. Setup installs exactly one of them into
// .dgf-factory/runtime/knowledge/. The rules, in order:
//
//   1. --dgf-line X.Y        that line; an unregistered one is a usage error
//   2. --dgf-version X.Y.Z   the line of that version (rule 5)
//   3. the previous receipt's dgfLine, when still registered
//   4. the estate's declared dgf.version in .dgf-factory/config.yaml (ADR 0019), when a version
//   5. a version maps to its own line; between lines to the nearest older one, and newer than every
//      line to the newest — both understate, which is safe; older than every line is refused, since
//      a newer pack would describe capabilities the estate's runtime lacks
//   6. otherwise the current line
//
// scripts/lib/dgf_version.py implements the same rules for the doctor; both pass
// tests/fixtures/unit/dgf-lines/selection.json.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { CliError, EXIT_BLOCKED, usageError } from './exit.mjs';
import * as log from './log.mjs';

export const REGISTRY = 'packs/lines.json';
export const CONFIG = '.dgf-factory/config.yaml';
const VERSION = /^(\d+)\.(\d+)\.(\d+)$/;
const LINE = /^(\d+)\.(\d+)$/;

export function parseLine(line) {
  const match = LINE.exec(String(line ?? '').trim());
  if (!match) throw usageError(`\`${line}\` is not a DGF release line such as 1.3`);
  return [Number(match[1]), Number(match[2])];
}

export function isVersion(text) {
  return VERSION.test(String(text ?? '').trim());
}

export function lineOf(version) {
  const match = VERSION.exec(String(version ?? '').trim());
  if (!match) throw usageError(`\`${version}\` is not a DGF version such as 1.3.0`);
  return `${match[1]}.${match[2]}`;
}

function compareLines(a, b) {
  const [x, y] = [parseLine(a), parseLine(b)];
  return x[0] - y[0] || x[1] - y[1];
}

/** { current, lines: [{ line, dir, dgf_version, read_date }] } from the package's registry. */
export function loadLines(packageRoot) {
  const file = path.join(packageRoot, REGISTRY);
  let data;
  try {
    data = JSON.parse(readFileSync(file, 'utf8'));
  } catch (err) {
    throw usageError(`${REGISTRY} in the package cannot be read: ${err.message}`);
  }
  if (data?.format !== 1 || !Array.isArray(data.lines) || !data.lines.length) throw usageError(`${REGISTRY} is not a format-1 registry`);
  for (const entry of data.lines) {
    if (typeof entry?.line !== 'string' || typeof entry.dir !== 'string' || typeof entry.dgf_version !== 'string') {
      throw usageError(`${REGISTRY}: an entry has no line, dir or dgf_version`);
    }
    parseLine(entry.line);
  }
  if (!data.lines.some((entry) => entry.line === data.current)) throw usageError(`${REGISTRY}: current \`${data.current}\` is not listed`);
  log.debug('lines.loadLines', 'registry', { lines: data.lines.map((e) => e.line).join(','), current: data.current });
  return { current: data.current, lines: data.lines };
}

/** The `version:` under the top-level `dgf:` key of the project's config, or null. A line scan, no YAML library. */
export function readConfigVersion(projectRoot) {
  const file = path.join(projectRoot, CONFIG);
  if (!existsSync(file)) return null;
  let inDgf = false;
  for (const raw of readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.replace(/\s+#.*$/, '');
    if (!line.trim()) continue;
    if (/^\S/.test(line)) {
      inDgf = /^dgf:\s*$/.test(line);
      continue;
    }
    const match = inDgf && /^\s+version:\s*["']?([^"'\s]+)["']?\s*$/.exec(line);
    if (match) {
      log.debug('lines.readConfigVersion', 'declared', { version: match[1] });
      return match[1];
    }
  }
  return null;
}

/** The pack line for a declared version, and a note when it is not that version's own line. */
export function lineForVersion(version, lines) {
  const wanted = lineOf(version);
  const ordered = [...lines].sort(compareLines);
  if (ordered.includes(wanted)) return { line: wanted, note: '' };
  const older = ordered.filter((line) => compareLines(line, wanted) < 0);
  if (!older.length) {
    throw new CliError(EXIT_BLOCKED, `DGF ${version} is older than every knowledge pack (${ordered.join(', ')}); a newer pack would `
      + `describe capabilities its runtime lacks — pass --dgf-line ${ordered[0]} to install it anyway`);
  }
  const chosen = older[older.length - 1];
  if (chosen === ordered[ordered.length - 1]) {
    return { line: chosen, note: `DGF ${version} is newer than every knowledge pack; using ${chosen}, which may understate it` };
  }
  return { line: chosen, note: `no knowledge pack for DGF line ${wanted}; using the nearest older one, ${chosen}` };
}

/** { line, source, note } — or throws (usage: exit 3; refused: exit 1). The rules are in the header. */
export function selectLine({ lines, current, flagLine, flagVersion, receiptLine, configVersion }) {
  log.debug('lines.select', 'inputs', { lines: lines.join(','), current, flagLine, flagVersion, receiptLine, configVersion });
  let chosen;
  if (flagLine && flagVersion) throw usageError('pass --dgf-line or --dgf-version, not both');
  if (flagLine) {
    parseLine(flagLine);
    if (!lines.includes(flagLine)) {
      throw usageError(`no knowledge pack for DGF line ${flagLine}; available: ${[...lines].sort(compareLines).join(', ')}`);
    }
    chosen = { line: flagLine, source: 'flag-line', note: '' };
  } else if (flagVersion) {
    chosen = { ...lineForVersion(flagVersion, lines), source: 'flag-version' };
  } else if (receiptLine && lines.includes(receiptLine)) {
    chosen = { line: receiptLine, source: 'receipt', note: '' };
  } else if (configVersion && isVersion(configVersion)) {
    chosen = { ...lineForVersion(configVersion, lines), source: 'config' };
  } else {
    const why = !configVersion || configVersion === 'unknown' ? 'the estate declares no DGF version' : `\`dgf.version\` \`${configVersion}\` is not a version`;
    chosen = { line: current, source: 'current', note: `${why}; installing the current line, ${current}` };
  }
  log.debug('lines.select', 'chosen', chosen);
  return chosen;
}

/** The registry entry of a line. */
export function entryOf(registry, line) {
  return registry.lines.find((entry) => entry.line === line);
}
