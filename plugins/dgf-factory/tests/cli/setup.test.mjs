// dgf-factory setup, end to end in temporary projects (ADR 0029). Every run skips Python.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

import { run } from '../../cli/commands/setup.mjs';

const REPO = path.resolve(fileURLToPath(new URL('../..', import.meta.url)));
const BIN = path.join(REPO, 'bin', 'dgf-factory.mjs');
const LEFTOVER = /\$\{CLAUDE_PLUGIN_ROOT\}|\{\{dgf_runtime\}\}/;

function tmp(t, prefix = 'dgf-setup-') {
  const dir = mkdtempSync(path.join(os.tmpdir(), prefix));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function cli(...args) {
  const env = { ...process.env };
  delete env.DEBUG;
  delete env.LOG_LEVEL;
  return spawnSync(process.execPath, [BIN, 'setup', ...args], { encoding: 'utf8', env, stdio: ['ignore', 'pipe', 'pipe'] });
}

function snapshot(root) {
  const out = {};
  const walk = (rel) => {
    for (const name of readdirSync(path.join(root, rel))) {
      const child = rel ? `${rel}/${name}` : name;
      if (statSync(path.join(root, child)).isDirectory()) walk(child);
      else out[child] = readFileSync(path.join(root, child)).toString('base64');
    }
  };
  walk('');
  return out;
}

function sink() {
  let text = '';
  return { write: (chunk) => { text += chunk; return true; }, text: () => text };
}

test('claude, codex and gemini: skills, MCP, runtime and receipt, with nothing left unrendered', (t) => {
  const project = tmp(t);
  const result = cli('--root', project, '--harness', 'claude,codex,gemini', '--yes', '--no-python');
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  for (const dir of ['.claude/skills', '.codex/skills', '.gemini/skills']) {
    assert.equal(readdirSync(path.join(project, dir)).length, 13, dir);
    assert.ok(existsSync(path.join(project, dir, 'dgf-plan', 'SKILL.md')));
  }
  assert.deepEqual(JSON.parse(readFileSync(path.join(project, '.mcp.json'), 'utf8')).mcpServers['dgf-mcp'].url, 'https://dgf-mcp.dotgov.uk/mcp');
  assert.ok(JSON.parse(readFileSync(path.join(project, '.gemini/settings.json'), 'utf8')).mcpServers['dgf-mcp']);
  assert.match(readFileSync(path.join(project, '.codex/config.toml'), 'utf8'), /^\[mcp_servers\.dgf-mcp\]\nurl = "https:\/\/dgf-mcp\.dotgov\.uk\/mcp"\n$/);
  assert.doesNotMatch(result.stdout, /MANUAL/);
  assert.ok(existsSync(path.join(project, '.dgf-factory/runtime/scripts/locate_plan.py')));
  assert.ok(existsSync(path.join(project, '.dgf-factory/runtime/knowledge/schemas/xsd')));
  assert.equal(readFileSync(path.join(project, '.dgf-factory/runtime/.gitignore'), 'utf8').includes('.venv/'), true);
  const receipt = JSON.parse(readFileSync(path.join(project, '.dgf-factory/install.json'), 'utf8'));
  assert.deepEqual(receipt.harnesses.map((h) => h.id), ['claude', 'codex', 'gemini']);
  assert.match(readFileSync(path.join(project, '.codex/skills/dgf-plan/SKILL.md'), 'utf8'), /\$dgf-implement/);
  const skills = Object.entries(snapshot(project)).filter(([rel]) => rel.endsWith('.md') && !rel.startsWith('.dgf-factory/runtime/skills/dgf-doctor/scripts'));
  for (const [rel, data] of skills) assert.doesNotMatch(Buffer.from(data, 'base64').toString(), LEFTOVER, rel);
});

test('a second run reports everything unchanged and changes no byte', (t) => {
  const project = tmp(t);
  cli('--root', project, '--harness', 'claude,gemini', '--yes', '--no-python');
  const before = snapshot(project);
  const again = cli('--root', project, '--harness', 'claude,gemini', '--yes', '--no-python');
  assert.equal(again.status, 0, again.stdout + again.stderr);
  assert.match(again.stdout, /Written: 0 file\(s\); removed: 0/);
  assert.deepEqual(snapshot(project), before);
});

test('a hand-edited skill survives an update of the package, and is reported', async (t) => {
  const project = tmp(t);
  const pkg = tmp(t, 'dgf-pkg-');
  for (const entry of ['package.json', 'skills', 'scripts', 'knowledge']) cpSync(path.join(REPO, entry), path.join(pkg, entry), { recursive: true });
  const out = sink();
  assert.equal(await run(['--root', project, '--harness', 'claude', '--yes', '--no-python'], { parseArgs }, { io: null, out, pkgRoot: pkg }), 0, out.text());
  const mine = path.join(project, '.claude/skills/dgf-plan/SKILL.md');
  writeFileSync(mine, `${readFileSync(mine, 'utf8')}\nMy team's own rule.\n`);
  // the next release changes that skill, and bumps the version
  const shipped = path.join(pkg, 'skills/dgf-plan/SKILL.md');
  writeFileSync(shipped, `${readFileSync(shipped, 'utf8')}\nA new upstream line.\n`);
  const manifest = JSON.parse(readFileSync(path.join(pkg, 'package.json'), 'utf8'));
  writeFileSync(path.join(pkg, 'package.json'), JSON.stringify({ ...manifest, version: '9.9.9' }));
  const second = sink();
  assert.equal(await run(['--root', project, '--harness', 'claude', '--yes', '--no-python'], { parseArgs }, { io: null, out: second, pkgRoot: pkg }), 2);
  assert.match(readFileSync(mine, 'utf8'), /My team's own rule\./);
  assert.doesNotMatch(readFileSync(mine, 'utf8'), /A new upstream line\./);
  assert.match(second.text(), /CONFLICT \.claude\/skills\/dgf-plan\/SKILL\.md — you edited it/);
  assert.match(second.text(), /\+A new upstream line\./, 'the conflict shows the new version\'s diff');
  assert.equal(JSON.parse(readFileSync(path.join(project, '.dgf-factory/install.json'), 'utf8')).version, '9.9.9');
});

test('without a terminal, --harness is required (exit 3)', (t) => {
  const result = cli('--root', tmp(t), '--yes');
  assert.equal(result.status, 3);
  assert.match(result.stderr, /pass --harness/);
});

test('without a terminal and without --yes, nothing is written (exit 3)', (t) => {
  const project = tmp(t);
  const result = cli('--root', project, '--harness', 'claude', '--no-python');
  assert.equal(result.status, 3);
  assert.match(result.stderr, /pass --yes/);
  assert.equal(existsSync(path.join(project, '.dgf-factory')), false);
});

test('--dry-run previews and writes nothing', (t) => {
  const project = tmp(t);
  const result = cli('--root', project, '--harness', 'claude', '--dry-run');
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /create {3}\.claude\/skills\/dgf\/SKILL\.md/);
  assert.deepEqual(readdirSync(project), []);
});

test('an MCP file that does not parse is left as it was, and blocks (exit 1)', (t) => {
  const project = tmp(t);
  writeFileSync(path.join(project, '.mcp.json'), '{ // a comment\n "mcpServers": {} }\n');
  const result = cli('--root', project, '--harness', 'claude', '--yes', '--no-python');
  assert.equal(result.status, 1, result.stdout);
  assert.match(result.stdout, /INVALID {3}\.mcp\.json/);
  assert.equal(readFileSync(path.join(project, '.mcp.json'), 'utf8'), '{ // a comment\n "mcpServers": {} }\n');
});

test('other servers in an MCP file are kept', (t) => {
  const project = tmp(t);
  writeFileSync(path.join(project, '.mcp.json'), JSON.stringify({ mcpServers: { other: { command: 'x' } }, extra: 1 }));
  assert.equal(cli('--root', project, '--harness', 'claude', '--yes', '--no-python').status, 0);
  const data = JSON.parse(readFileSync(path.join(project, '.mcp.json'), 'utf8'));
  assert.deepEqual(data.mcpServers.other, { command: 'x' });
  assert.equal(data.extra, 1);
  assert.ok(data.mcpServers['dgf-mcp']);
});

test('a folder that is not a git repository installs the same', (t) => {
  const project = tmp(t);
  mkdirSync(path.join(project, 'nested'));
  assert.equal(cli('--root', path.join(project, 'nested'), '--harness', 'claude', '--yes', '--no-python').status, 0);
  assert.ok(existsSync(path.join(project, 'nested', '.dgf-factory', 'install.json')));
});

test('the home folder and the filesystem root are refused', () => {
  assert.equal(cli('--root', os.homedir(), '--harness', 'claude', '--dry-run').status, 3);
  assert.equal(cli('--root', path.parse(REPO).root, '--harness', 'claude', '--dry-run').status, 3);
});

test('an unknown harness and an unknown flag are usage errors', (t) => {
  assert.equal(cli('--root', tmp(t), '--harness', 'emacs').status, 3);
  assert.equal(cli('--frobnicate').status, 3);
});

// readline/promises rejects question() this way when the user presses Ctrl+D (or Ctrl+C)
function abortedTerminal(answers = []) {
  const queue = [...answers];
  return {
    output: sink(),
    question: async () => {
      if (queue.length) return queue.shift();
      throw Object.assign(new Error('Aborted with Ctrl+D'), { name: 'AbortError', code: 'ABORT_ERR' });
    },
    close: () => {},
  };
}

test('Ctrl+D at the harness prompt is a usage error, and nothing is written', async (t) => {
  const project = tmp(t);
  await assert.rejects(run(['--root', project, '--no-python'], { parseArgs }, { io: abortedTerminal(), out: sink() }),
    (err) => err.code === 3 && /cancelled/.test(err.message));
  assert.deepEqual(readdirSync(project), []);
});

test('Ctrl+D at the apply prompt is a usage error, and nothing is written', async (t) => {
  const project = tmp(t);
  await assert.rejects(run(['--root', project, '--harness', 'claude', '--no-python'], { parseArgs }, { io: abortedTerminal(), out: sink() }),
    (err) => err.code === 3 && /cancelled/.test(err.message));
  assert.deepEqual(readdirSync(project), []);
});
