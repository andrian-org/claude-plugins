// The receipt, `.dgf-factory/install.json`: what setup wrote, with two hashes per file (ADR 0029 §4).
//
//   { tool, version,
//     harnesses: [{ id, selected }],
//     files: { <rel>: { source, owner, sourceHash, installedHash } },   owner: "runtime" or a harness id
//     mcp:   { <harness id>: { file, key, entryHash } } }
//
// scripts/lib/install_receipt.py reads the same file for the estate checks. Keys are project-relative
// POSIX paths; an absolute path or a `..` segment is refused, as is any key this schema does not name.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { usageError } from './exit.mjs';
import { writeAtomic } from './fsops.mjs';
import * as log from './log.mjs';

export const RECEIPT = '.dgf-factory/install.json';
export const TOOL = 'dgf-factory';

const TOP = ['tool', 'version', 'harnesses', 'files', 'mcp'];
const FILE_KEYS = ['source', 'owner', 'sourceHash', 'installedHash'];
const MCP_KEYS = ['file', 'key', 'entryHash'];

export function emptyReceipt(version) {
  return { tool: TOOL, version, harnesses: [], files: {}, mcp: {} };
}

export function checkRelative(rel, where) {
  const bad = typeof rel !== 'string' || rel === '' || rel.includes('\\') || path.posix.isAbsolute(rel)
    || /^[A-Za-z]:/.test(rel) || rel.split('/').some((part) => part === '..' || part === '' || part === '.');
  if (bad) throw usageError(`${RECEIPT} ${where}: \`${rel}\` is not a project-relative POSIX path`);
  return rel;
}

function fail(message) {
  throw usageError(`${RECEIPT} ${message}`);
}

function keysOnly(object, allowed, where) {
  if (object === null || typeof object !== 'object' || Array.isArray(object)) fail(`${where} is not an object`);
  const unknown = Object.keys(object).filter((key) => !allowed.includes(key));
  if (unknown.length) fail(`${where} has unknown key(s): ${unknown.join(', ')}`);
}

function strings(object, keys, where) {
  for (const key of keys) {
    if (typeof object[key] !== 'string' || object[key] === '') fail(`${where}.${key} must be a non-empty string`);
  }
}

export function validate(data) {
  keysOnly(data, TOP, 'the receipt');
  if (data.tool !== TOOL) fail(`tool is \`${data.tool}\`, not \`${TOOL}\``);
  strings(data, ['version'], 'the receipt');
  if (!Array.isArray(data.harnesses)) fail('harnesses must be an array');
  data.harnesses.forEach((entry, index) => {
    keysOnly(entry, ['id', 'selected'], `harnesses[${index}]`);
    strings(entry, ['id'], `harnesses[${index}]`);
    if (typeof entry.selected !== 'boolean') fail(`harnesses[${index}].selected must be true or false`);
  });
  keysOnly(data.files, Object.keys(data.files ?? {}), 'files');
  for (const [rel, entry] of Object.entries(data.files)) {
    checkRelative(rel, 'files');
    keysOnly(entry, FILE_KEYS, `files.${rel}`);
    strings(entry, FILE_KEYS, `files.${rel}`);
  }
  keysOnly(data.mcp, Object.keys(data.mcp ?? {}), 'mcp');
  for (const [id, entry] of Object.entries(data.mcp)) {
    keysOnly(entry, MCP_KEYS, `mcp.${id}`);
    strings(entry, MCP_KEYS, `mcp.${id}`);
    checkRelative(entry.file, `mcp.${id}.file`);
  }
  return data;
}

/** The project's receipt, validated, or null when it has none. A malformed one is exit 3. */
export function readReceipt(projectRoot) {
  const file = path.join(projectRoot, RECEIPT);
  if (!existsSync(file)) {
    log.debug('receipt.readReceipt', 'no receipt', { file });
    return null;
  }
  let data;
  try {
    data = JSON.parse(readFileSync(file, 'utf8'));
  } catch (err) {
    fail(`cannot be read: ${err.message} — fix or delete it, then re-run setup`);
  }
  validate(data);
  log.debug('receipt.readReceipt', 'read', { files: Object.keys(data.files).length, mcp: Object.keys(data.mcp).length });
  return data;
}

/** Sorted keys, 2-space indent, trailing newline — so a re-run that changes nothing writes nothing new. */
export function serialise(data) {
  const sortObject = (object) => Object.fromEntries(Object.keys(object).sort().map((key) => [key, object[key]]));
  const ordered = {
    tool: data.tool,
    version: data.version,
    harnesses: [...data.harnesses].sort((a, b) => a.id.localeCompare(b.id)),
    files: sortObject(data.files),
    mcp: sortObject(data.mcp),
  };
  return `${JSON.stringify(ordered, null, 2)}\n`;
}

export function writeReceipt(projectRoot, data, journal) {
  validate(data);
  writeAtomic(projectRoot, RECEIPT, Buffer.from(serialise(data), 'utf8'), { journal });
  log.info('receipt.writeReceipt', 'written', { files: Object.keys(data.files).length });
}
