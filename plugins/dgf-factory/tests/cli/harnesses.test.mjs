// The harness registry: AI Factory's folders, this tool's transforms, and the collision guard.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

import { HARNESSES, getHarness, harnessIds, selectHarnesses } from '../../cli/harnesses.mjs';

test('all 16 of AI Factory 2.19.0\'s harnesses are listed, ids unique', () => {
  assert.equal(HARNESSES.length, 16);
  assert.equal(new Set(harnessIds()).size, 16);
  for (const id of ['claude', 'codex', 'gemini', 'cursor', 'copilot', 'universal']) assert.ok(getHarness(id));
});

test('every harness renders with a known transform, and an MCP target or none', () => {
  for (const harness of HARNESSES) {
    assert.ok(['default', 'codex', 'qwen'].includes(harness.transform), harness.id);
    assert.ok(harness.mcp === null || (typeof harness.mcp.file === 'string' && typeof harness.mcp.format === 'string'), harness.id);
  }
});

test('an unknown harness is a usage error naming the choices', () => {
  assert.throws(() => getHarness('emacs'), (err) => err.code === 3 && /available: claude/.test(err.message));
});

test('codex-app and universal share .agents/skills with different transforms and are refused together', () => {
  assert.throws(() => selectHarnesses(['codex-app', 'universal']), (err) => err.code === 3 && /codex-app.*universal/.test(err.message));
});

test('a repeated id is selected once', () => {
  assert.deepEqual(selectHarnesses(['claude', 'claude', 'gemini']).map((h) => h.id), ['claude', 'gemini']);
});

function aiFactoryRegistry() {
  let root;
  try {
    root = execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim();
  } catch {
    return null;
  }
  const file = path.join(root, 'ai-factory', 'dist', 'core', 'agents.js');
  return existsSync(file) ? file : null;
}

test('the folders match an installed AI Factory\'s registry', async (t) => {
  const file = aiFactoryRegistry();
  if (!file) return t.skip('ai-factory is not installed globally');
  const { getBuiltinAgentConfigs } = await import(pathToFileURL(file).href);
  const theirs = new Map(getBuiltinAgentConfigs().map((agent) => [agent.id, agent]));
  for (const harness of HARNESSES) {
    const agent = theirs.get(harness.id);
    assert.ok(agent, `${harness.id} is not in AI Factory's registry`);
    for (const key of ['displayName', 'configDir', 'skillsDir', 'settingsFile']) {
      assert.equal(harness[key], agent[key] ?? null, `${harness.id}.${key}`);
    }
    assert.equal(harness.agentsDir, agent.agentsDir, `${harness.id}.agentsDir`);
  }
  assert.equal(theirs.size, HARNESSES.length, 'AI Factory lists a harness this registry does not');
});
