// dgf-factory uninstall: only what setup wrote, only while unedited; the estate's state never.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(fileURLToPath(new URL('../..', import.meta.url)));
const BIN = path.join(REPO, 'bin', 'dgf-factory.mjs');

function cli(...args) {
  const env = { ...process.env };
  delete env.DEBUG;
  delete env.LOG_LEVEL;
  return spawnSync(process.execPath, [BIN, ...args], { encoding: 'utf8', env, stdio: ['ignore', 'pipe', 'pipe'] });
}

function installed(t, harnesses = 'claude,gemini,universal') {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'dgf-uninstall-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  // the estate's own state, which uninstall must never touch
  mkdirSync(path.join(dir, '.dgf-factory', 'plans'), { recursive: true });
  writeFileSync(path.join(dir, '.dgf-factory', 'config.yaml'), 'dgf:\n  version: unknown\n');
  writeFileSync(path.join(dir, '.dgf-factory', 'plans', 'feature-x.md'), '# plan\n');
  writeFileSync(path.join(dir, '.mcp.json'), JSON.stringify({ mcpServers: { other: { command: 'x' } } }));
  const setup = cli('setup', '--root', dir, '--harness', harnesses, '--yes', '--no-python');
  assert.equal(setup.status, 0, setup.stdout + setup.stderr);
  mkdirSync(path.join(dir, '.dgf-factory/runtime/scripts/__pycache__'), { recursive: true });
  writeFileSync(path.join(dir, '.dgf-factory/runtime/scripts/__pycache__/x.pyc'), 'x');
  return dir;
}

test('a partial uninstall removes one harness, keeps the runtime and a shared MCP file', (t) => {
  const project = installed(t);
  const result = cli('uninstall', '--root', project, '--harness', 'claude', '--yes');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(existsSync(path.join(project, '.claude')), false, 'the emptied harness folder is pruned');
  assert.ok(existsSync(path.join(project, '.gemini/skills/dgf/SKILL.md')));
  assert.ok(existsSync(path.join(project, '.dgf-factory/runtime/scripts/locate_plan.py')));
  // universal still uses .mcp.json, so dgf-mcp stays
  assert.ok(JSON.parse(readFileSync(path.join(project, '.mcp.json'), 'utf8')).mcpServers['dgf-mcp']);
  assert.match(result.stdout, /still used by gemini, universal/);
  const receipt = JSON.parse(readFileSync(path.join(project, '.dgf-factory/install.json'), 'utf8'));
  assert.deepEqual(receipt.harnesses.map((h) => h.id), ['gemini', 'universal']);
  assert.ok(Object.values(receipt.files).every((f) => f.owner !== 'claude'));
});

test('an edited file is kept and reported (exit 2)', (t) => {
  const project = installed(t);
  writeFileSync(path.join(project, '.claude/skills/dgf-plan/SKILL.md'), 'mine\n');
  const result = cli('uninstall', '--root', project, '--harness', 'claude', '--yes');
  assert.equal(result.status, 2);
  assert.equal(readFileSync(path.join(project, '.claude/skills/dgf-plan/SKILL.md'), 'utf8'), 'mine\n');
  assert.match(result.stdout, /kept {5}\.claude\/skills\/dgf-plan\/SKILL\.md \(edited/);
  assert.equal(existsSync(path.join(project, '.claude/skills/dgf/SKILL.md')), false);
});

test('a full uninstall removes the runtime, the receipt and the MCP entries, and keeps the estate', (t) => {
  const project = installed(t);
  mkdirSync(path.join(project, '.dgf-factory/runtime/.venv/bin'), { recursive: true });
  writeFileSync(path.join(project, '.dgf-factory/runtime/.venv/bin/python'), '');
  const result = cli('uninstall', '--root', project, '--yes');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(existsSync(path.join(project, '.dgf-factory/runtime')), false);
  assert.equal(existsSync(path.join(project, '.dgf-factory/install.json')), false);
  for (const dir of ['.claude', '.gemini/skills', '.agents']) assert.equal(existsSync(path.join(project, dir)), false, dir);
  // the settings file setup merged into is kept — the receipt cannot say who created it — without dgf-mcp
  assert.deepEqual(JSON.parse(readFileSync(path.join(project, '.gemini/settings.json'), 'utf8')), { mcpServers: {} });
  const mcp = JSON.parse(readFileSync(path.join(project, '.mcp.json'), 'utf8'));
  assert.deepEqual(mcp.mcpServers, { other: { command: 'x' } }, 'the sibling server is kept, dgf-mcp is gone');
  assert.equal(readFileSync(path.join(project, '.dgf-factory/config.yaml'), 'utf8'), 'dgf:\n  version: unknown\n');
  assert.ok(existsSync(path.join(project, '.dgf-factory/plans/feature-x.md')));
  assert.match(result.stdout, /Left in \.dgf-factory\/ \(the estate's, never removed\): config\.yaml, plans/);
  assert.deepEqual(readdirSync(path.join(project, '.dgf-factory')).sort(), ['config.yaml', 'plans']);
});

test('a changed dgf-mcp entry is left in place (exit 2)', (t) => {
  const project = installed(t, 'gemini');
  const file = path.join(project, '.gemini/settings.json');
  writeFileSync(file, JSON.stringify({ mcpServers: { 'dgf-mcp': { httpUrl: 'https://elsewhere.example/mcp' } } }));
  const result = cli('uninstall', '--root', project, '--yes');
  assert.equal(result.status, 2, result.stdout);
  assert.match(readFileSync(file, 'utf8'), /elsewhere/);
});

test('--dry-run removes nothing; no receipt and an unknown harness are exit 3', (t) => {
  const project = installed(t, 'claude');
  assert.equal(cli('uninstall', '--root', project, '--dry-run').status, 0);
  assert.ok(existsSync(path.join(project, '.claude/skills/dgf/SKILL.md')));
  assert.equal(cli('uninstall', '--root', project, '--harness', 'gemini', '--yes').status, 3);
  const empty = mkdtempSync(path.join(os.tmpdir(), 'dgf-uninstall-'));
  t.after(() => rmSync(empty, { recursive: true, force: true }));
  assert.equal(cli('uninstall', '--root', empty, '--yes').status, 3);
});

test('without a terminal and without --yes, nothing is removed (exit 3)', (t) => {
  const project = installed(t, 'claude');
  const result = cli('uninstall', '--root', project);
  assert.equal(result.status, 3);
  assert.ok(existsSync(path.join(project, '.claude/skills/dgf/SKILL.md')));
});

test('Ctrl+D at the confirm prompt is a usage error, and nothing is removed', async (t) => {
  const project = installed(t, 'claude');
  const { run } = await import('../../cli/commands/uninstall.mjs');
  const { parseArgs } = await import('node:util');
  const io = {
    question: async () => { throw Object.assign(new Error('Aborted with Ctrl+D'), { name: 'AbortError', code: 'ABORT_ERR' }); },
    close: () => {},
  };
  const out = { write: () => true };
  await assert.rejects(run(['--root', project], { parseArgs }, { io, out }), (err) => err.code === 3 && /cancelled/.test(err.message));
  assert.ok(existsSync(path.join(project, '.claude/skills/dgf/SKILL.md')));
});
