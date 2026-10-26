// Registering the `dgf-mcp` server with each chosen harness (ADR 0029 §7).
//
// dgf-mcp is a remote Streamable-HTTP server with no credentials. Each harness that has a verified
// project-level MCP file gets one entry, in its own shape (FORMATS); one with none gets a printed
// manual step. Files are parsed, never replaced: a JSON file that does not parse, or is not an object,
// is reported and left byte-for-byte as it was. TOML is only appended to. An existing `dgf-mcp` entry
// that differs from ours is a conflict, never overwritten.
import { existsSync, readFileSync } from 'node:fs';

import { ensureWithinRoot, writeAtomic } from './fsops.mjs';
import { hashBytes } from './hash.mjs';
import * as log from './log.mjs';

export const SERVER = 'dgf-mcp';
export const URL = 'https://dgf-mcp.dotgov.uk/mcp';

// format → how the entry sits in its file. Each was read from the harness's own documentation on
// 2026-10-26; the sources are in ADR 0029's MCP table (Errata). `type` is required by Claude Code,
// VS Code and Roo Code, and absent from the others' documented shapes; Gemini and Qwen take
// `httpUrl`, which every Gemini CLI version reads as Streamable HTTP.
export const FORMATS = {
  'mcpServers-http': { syntax: 'json', container: ['mcpServers'], entry: () => ({ type: 'http', url: URL }) },
  'mcpServers-url': { syntax: 'json', container: ['mcpServers'], entry: () => ({ url: URL }) },
  'servers-http': { syntax: 'json', container: ['servers'], entry: () => ({ type: 'http', url: URL }) },
  'mcpServers-httpUrl': { syntax: 'json', container: ['mcpServers'], entry: () => ({ httpUrl: URL }) },
  'mcpServers-streamable': { syntax: 'json', container: ['mcpServers'], entry: () => ({ type: 'streamable-http', url: URL }) },
  'mcpServers-serverUrl': { syntax: 'json', container: ['mcpServers'], entry: () => ({ serverUrl: URL }) },
  'opencode-remote': { syntax: 'json', container: ['mcp'], entry: () => ({ type: 'remote', url: URL }) },
  'codex-toml': { syntax: 'toml', entry: () => ({ url: URL }) },
};

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

export function entryHash(entry) {
  return hashBytes(Buffer.from(canonical(entry), 'utf8'));
}

function tomlBlock(entry) {
  const body = Object.entries(entry).map(([key, value]) => `${key} = ${JSON.stringify(value)}`);
  return [`[mcp_servers.${SERVER}]`, ...body].join('\n');
}

const TOML_HEADER = new RegExp(`^\\s*\\[\\s*mcp_servers\\.(?:${SERVER}|"${SERVER}")\\s*\\]\\s*$`, 'm');

/** The `[mcp_servers.dgf-mcp]` table in a TOML text, as `key = value` lines, or null. */
export function tomlTable(text) {
  const match = TOML_HEADER.exec(text);
  if (!match) return null;
  const rest = text.slice(match.index + match[0].length).split('\n');
  const lines = [];
  for (const line of rest) {
    if (/^\s*\[/.test(line)) break;
    if (line.trim() && !line.trim().startsWith('#')) lines.push(line.trim());
  }
  return lines;
}

function readJson(abs, rel) {
  if (!existsSync(abs)) return { data: {} };
  const text = readFileSync(abs, 'utf8');
  try {
    const data = JSON.parse(text);
    if (data === null || typeof data !== 'object' || Array.isArray(data)) return { invalid: `${rel} is not a JSON object` };
    return { data, existed: true };
  } catch (err) {
    return { invalid: `${rel} does not parse as JSON (${err.message}); comments are not supported — add the entry by hand` };
  }
}

function getPath(object, keys) {
  return keys.reduce((node, key) => (node && typeof node === 'object' ? node[key] : undefined), object);
}

/** The action for one MCP file: register | unchanged | conflict | invalid. */
function planJson(projectRoot, harness, format) {
  const rel = harness.mcp.file;
  const entry = format.entry();
  const { data, invalid } = readJson(ensureWithinRoot(projectRoot, rel), rel);
  if (invalid) return { kind: 'invalid', harness: harness.id, file: rel, reason: invalid };
  const container = getPath(data, format.container);
  if (container !== undefined && (container === null || typeof container !== 'object' || Array.isArray(container))) {
    return { kind: 'invalid', harness: harness.id, file: rel, reason: `${rel} \`${format.container.join('.')}\` is not an object` };
  }
  const existing = container?.[SERVER];
  if (existing === undefined) return { kind: 'register', harness: harness.id, file: rel, entry, format };
  if (canonical(existing) === canonical(entry)) return { kind: 'unchanged', harness: harness.id, file: rel, entry };
  return { kind: 'conflict', harness: harness.id, file: rel, entry, existing: JSON.stringify(existing) };
}

function planToml(projectRoot, harness, format) {
  const rel = harness.mcp.file;
  const entry = format.entry();
  const abs = ensureWithinRoot(projectRoot, rel);
  const text = existsSync(abs) ? readFileSync(abs, 'utf8') : '';
  const table = tomlTable(text);
  if (table === null) return { kind: 'register', harness: harness.id, file: rel, entry, format };
  const want = tomlBlock(entry).split('\n').slice(1);
  if (table.join('\n') === want.join('\n')) return { kind: 'unchanged', harness: harness.id, file: rel, entry };
  return { kind: 'conflict', harness: harness.id, file: rel, entry, existing: table.join('; ') };
}

/** One action per MCP file the chosen harnesses use, plus a manual step for each that has none. */
export function planMcp(projectRoot, harnesses) {
  const actions = [];
  const seen = new Map();
  for (const harness of harnesses) {
    if (!harness.mcp) {
      actions.push({ kind: 'manual', harness: harness.id, line: `${harness.displayName}: add the \`${SERVER}\` server (${URL}, Streamable HTTP) in its MCP settings by hand` });
      continue;
    }
    const key = harness.mcp.file;
    if (seen.has(key)) {
      actions.push({ ...seen.get(key), harness: harness.id, shared: true });
      continue;
    }
    const format = FORMATS[harness.mcp.format];
    const action = format.syntax === 'toml' ? planToml(projectRoot, harness, format) : planJson(projectRoot, harness, format);
    seen.set(key, action);
    actions.push(action);
    log.info('mcp.planMcp', action.kind, { harness: harness.id, file: key });
  }
  return actions;
}

export function previewMcp(actions) {
  return actions.map((a) => {
    if (a.kind === 'manual') return `MANUAL    ${a.line}`;
    if (a.shared) return `shared    ${a.file} (${a.harness}) — same file as above`;
    if (a.kind === 'register') return `register  ${a.file} (${a.harness})`;
    if (a.kind === 'unchanged') return `unchanged ${a.file} (${a.harness})`;
    if (a.kind === 'conflict') return `CONFLICT  ${a.file} (${a.harness}) — a different \`${SERVER}\` entry is there (${a.existing}); left as is`;
    return `INVALID   ${a.file} (${a.harness}) — ${a.reason}; left as is`;
  });
}

function writeJson(projectRoot, action, journal) {
  const abs = ensureWithinRoot(projectRoot, action.file);
  const { data } = readJson(abs, action.file);
  let node = data;
  for (const key of action.format.container) {
    node[key] = node[key] ?? {};
    node = node[key];
  }
  node[SERVER] = action.entry;
  writeAtomic(projectRoot, action.file, Buffer.from(`${JSON.stringify(data, null, 2)}\n`, 'utf8'), { journal });
}

function writeToml(projectRoot, action, journal) {
  const abs = ensureWithinRoot(projectRoot, action.file);
  const text = existsSync(abs) ? readFileSync(abs, 'utf8') : '';
  const glue = text === '' ? '' : text.endsWith('\n\n') ? '' : text.endsWith('\n') ? '\n' : '\n\n';
  writeAtomic(projectRoot, action.file, Buffer.from(`${text}${glue}${tomlBlock(action.entry)}\n`, 'utf8'), { journal });
}

/** Write every `register` action; return the receipt's `mcp` entries for registered and unchanged ones. */
export function applyMcp(projectRoot, actions, journal) {
  const receipt = {};
  for (const action of actions) {
    if (action.kind === 'register' && !action.shared) {
      if (action.format.syntax === 'toml') writeToml(projectRoot, action, journal);
      else writeJson(projectRoot, action, journal);
      log.info('mcp.applyMcp', 'registered', { harness: action.harness, file: action.file });
    }
    if (action.kind === 'register' || action.kind === 'unchanged') {
      receipt[action.harness] = { file: action.file, key: SERVER, entryHash: entryHash(action.entry) };
    }
  }
  return receipt;
}
