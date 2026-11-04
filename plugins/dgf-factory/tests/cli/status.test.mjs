// dgf-factory status: read-only, per harness, with drift.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, unlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(fileURLToPath(new URL('../..', import.meta.url)));
const BIN = path.join(REPO, 'bin', 'dgf-factory.mjs');
const SKILLS = readdirSync(path.join(REPO, 'skills')).filter((name) => existsSync(path.join(REPO, 'skills', name, 'SKILL.md'))).length;
const AGENTS = readdirSync(path.join(REPO, 'agents', 'claude')).filter((name) => name.endsWith('.md')).length;

function cli(...args) {
  const env = { ...process.env };
  delete env.DEBUG;
  delete env.LOG_LEVEL;
  return spawnSync(process.execPath, [BIN, ...args], { encoding: 'utf8', env, stdio: ['ignore', 'pipe', 'pipe'] });
}

function installed(t) {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'dgf-status-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  assert.equal(cli('setup', '--root', dir, '--harness', 'claude,gemini', '--yes', '--no-python').status, 0);
  return dir;
}

test('a fresh install is clean, and status writes nothing', (t) => {
  const project = installed(t);
  const receipt = readFileSync(path.join(project, '.dgf-factory/install.json'), 'utf8');
  const result = cli('status', '--root', project);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, new RegExp(`claude: ${SKILLS + AGENTS} unchanged, 0 edited, 0 missing`));
  assert.match(result.stdout, new RegExp(`gemini: ${SKILLS} unchanged, 0 edited, 0 missing`));
  assert.match(result.stdout, /unchanged .mcp.json \(claude\)/);
  assert.equal(readFileSync(path.join(project, '.dgf-factory/install.json'), 'utf8'), receipt);
});

test('edits, missing files and a changed MCP entry are reported (exit 2)', (t) => {
  const project = installed(t);
  writeFileSync(path.join(project, '.claude/skills/dgf/SKILL.md'), 'mine\n');
  unlinkSync(path.join(project, '.gemini/skills/dgf-plan/SKILL.md'));
  writeFileSync(path.join(project, '.mcp.json'), JSON.stringify({ mcpServers: { 'dgf-mcp': { type: 'http', url: 'https://x.example' } } }));
  const result = cli('status', '--root', project, '--json');
  assert.equal(result.status, 2);
  const data = JSON.parse(result.stdout);
  assert.deepEqual(data.groups.claude.edited, ['.claude/skills/dgf/SKILL.md']);
  assert.deepEqual(data.groups.gemini.missing, ['.gemini/skills/dgf-plan/SKILL.md']);
  assert.equal(data.mcp.claude.state, 'edited');
  assert.equal(data.mcp.gemini.state, 'unchanged');
});

test('an edited and a missing agent are reported like a skill (exit 2)', (t) => {
  const project = installed(t);
  writeFileSync(path.join(project, '.claude/agents/dgf-implement-coordinator.md'), 'mine\n');
  unlinkSync(path.join(project, '.claude/agents/dgf-implement-worker.md'));
  const result = cli('status', '--root', project);
  assert.equal(result.status, 2);
  assert.match(result.stdout, /edited {3}\.claude\/agents\/dgf-implement-coordinator\.md/);
  assert.match(result.stdout, /missing {2}\.claude\/agents\/dgf-implement-worker\.md/);
});

test('a receipt from another version is drift (exit 2)', (t) => {
  const project = installed(t);
  const file = path.join(project, '.dgf-factory/install.json');
  writeFileSync(file, readFileSync(file, 'utf8').replace(/"version": "[^"]+"/, '"version": "0.0.1"'));
  const result = cli('status', '--root', project);
  assert.equal(result.status, 2);
  assert.match(result.stdout, /Installed by 0\.0\.1; this CLI is .* run `dgf-factory setup` to update/);
});

test('no receipt is exit 3', (t) => {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'dgf-status-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const result = cli('status', '--root', dir);
  assert.equal(result.status, 3);
  assert.match(result.stderr, /not installed here/);
});

test('status names the installed DGF line, or says an older receipt recorded none', (t) => {
  const project = installed(t);
  const file = path.join(project, '.dgf-factory/install.json');
  const receipt = JSON.parse(readFileSync(file, 'utf8'));
  assert.match(cli('status', '--root', project).stdout, new RegExp(`DGF line: ${receipt.dgfLine.replace('.', '\\.')}\\n`));
  const { dgfLine, ...older } = receipt;
  assert.ok(dgfLine);
  writeFileSync(file, `${JSON.stringify(older, null, 2)}\n`);
  const result = cli('status', '--root', project, '--json');
  assert.equal(JSON.parse(result.stdout).dgfLine, null);
  assert.match(cli('status', '--root', project).stdout, /DGF line: unrecorded — installed before DGF lines/);
});
