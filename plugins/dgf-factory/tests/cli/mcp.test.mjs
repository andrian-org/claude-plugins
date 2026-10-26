// The MCP writers: every format, files the tool does not own left intact, conflicts never overwritten.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { Journal } from '../../cli/fsops.mjs';
import { HARNESSES, getHarness } from '../../cli/harnesses.mjs';
import { FORMATS, SERVER, URL, applyMcp, entryHash, planMcp, tomlTable } from '../../cli/mcp.mjs';

function project(t) {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'dgf-mcp-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function put(root, rel, text) {
  mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
  writeFileSync(path.join(root, rel), text);
}

function registerOne(root, id) {
  const actions = planMcp(root, [getHarness(id)]);
  return { actions, receipt: applyMcp(root, actions, new Journal()) };
}

test('every harness with an MCP file names a known format', () => {
  for (const harness of HARNESSES.filter((h) => h.mcp)) assert.ok(FORMATS[harness.mcp.format], harness.id);
});

test('each JSON harness gets its own shape in a new file', (t) => {
  for (const harness of HARNESSES.filter((h) => h.mcp && FORMATS[h.mcp.format].syntax === 'json')) {
    const root = project(t);
    const { receipt } = registerOne(root, harness.id);
    const format = FORMATS[harness.mcp.format];
    const data = JSON.parse(readFileSync(path.join(root, harness.mcp.file), 'utf8'));
    const entry = format.container.reduce((node, key) => node[key], data)[SERVER];
    assert.deepEqual(entry, format.entry(), harness.id);
    assert.ok(JSON.stringify(entry).includes(URL), harness.id);
    assert.deepEqual(receipt[harness.id], { file: harness.mcp.file, key: SERVER, entryHash: entryHash(format.entry()) });
  }
});

test('a JSON file that does not parse, or is not an object, is invalid and untouched', (t) => {
  for (const text of ['{ // comment\n}', '[1, 2]', 'null']) {
    const root = project(t);
    put(root, '.mcp.json', text);
    const { actions } = registerOne(root, 'claude');
    assert.equal(actions[0].kind, 'invalid', text);
    assert.equal(readFileSync(path.join(root, '.mcp.json'), 'utf8'), text);
  }
});

test('a container that is not an object is invalid, not overwritten', (t) => {
  const root = project(t);
  put(root, '.mcp.json', '{"mcpServers": []}');
  assert.equal(registerOne(root, 'claude').actions[0].kind, 'invalid');
});

test('the same entry is unchanged; a different one is a conflict, never overwritten', (t) => {
  const root = project(t);
  put(root, '.mcp.json', JSON.stringify({ mcpServers: { [SERVER]: { url: URL, type: 'http' } } }));
  assert.equal(registerOne(root, 'claude').actions[0].kind, 'unchanged');
  const other = JSON.stringify({ mcpServers: { [SERVER]: { type: 'http', url: 'https://elsewhere.example/mcp' } } });
  put(root, '.mcp.json', other);
  const { actions } = registerOne(root, 'claude');
  assert.equal(actions[0].kind, 'conflict');
  assert.equal(readFileSync(path.join(root, '.mcp.json'), 'utf8'), other);
});

test('claude and universal share .mcp.json: one write, two receipt entries', (t) => {
  const root = project(t);
  const journal = new Journal();
  const actions = planMcp(root, [getHarness('claude'), getHarness('universal')]);
  const receipt = applyMcp(root, actions, journal);
  assert.equal(journal.written.filter((rel) => rel === '.mcp.json').length, 1);
  assert.deepEqual(Object.keys(receipt).sort(), ['claude', 'universal']);
});

test('a harness with no project-level file gets a manual step, and nothing is written', (t) => {
  const root = project(t);
  const { actions, receipt } = registerOne(root, 'windsurf');
  assert.equal(actions[0].kind, 'manual');
  assert.deepEqual(receipt, {});
});

test('TOML is appended to, and an existing table that differs is a conflict', (t) => {
  const tomlHarness = HARNESSES.find((h) => h.mcp && FORMATS[h.mcp.format].syntax === 'toml');
  if (!tomlHarness) return t.skip('no harness writes TOML');
  const root = project(t);
  const rel = tomlHarness.mcp.file;
  put(root, rel, 'model = "x"\n\n[mcp_servers.other]\ncommand = "y"\n');
  registerOne(root, tomlHarness.id);
  const text = readFileSync(path.join(root, rel), 'utf8');
  assert.ok(text.startsWith('model = "x"\n\n[mcp_servers.other]\ncommand = "y"\n'), 'the existing text is kept, byte for byte');
  assert.deepEqual(tomlTable(text), [`url = "${URL}"`]);
  assert.equal(registerOne(root, tomlHarness.id).actions[0].kind, 'unchanged');
  put(root, rel, `[mcp_servers.${SERVER}]\nurl = "https://elsewhere.example/mcp"\n`);
  assert.equal(registerOne(root, tomlHarness.id).actions[0].kind, 'conflict');
});

test('no entry ever carries a secret or a header', () => {
  for (const format of Object.values(FORMATS)) {
    const entry = JSON.stringify(format.entry()).toLowerCase();
    for (const word of ['token', 'secret', 'authorization', 'header', 'env']) assert.ok(!entry.includes(word), entry);
  }
});

test('a file in a folder that does not exist yet is created with its folder', (t) => {
  const root = project(t);
  registerOne(root, 'gemini');
  assert.ok(existsSync(path.join(root, '.gemini', 'settings.json')));
});
