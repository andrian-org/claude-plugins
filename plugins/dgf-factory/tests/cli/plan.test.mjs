// The planner: every row of ADR 0029 §5's table, an unmanaged file, a dropped harness, a stable preview.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { getHarness } from '../../cli/harnesses.mjs';
import { hashBytes } from '../../cli/hash.mjs';
import { RUNTIME_GITIGNORE, agentNames, decide, desiredFiles, payloadFiles, planInstall, skillNames } from '../../cli/plan.mjs';
import { isNoop, renderPreview } from '../../cli/preview.mjs';

const REPO = path.resolve(fileURLToPath(new URL('../..', import.meta.url)));
const SKILL = '---\nname: dgf-x\nallowed-tools: Read Bash(python3 "{{dgf_runtime}}/scripts/*)\n---\nRun `python3 "{{dgf_runtime}}/scripts/a.py"`, then /dgf-y.\n';

function tmp(t, prefix) {
  const dir = mkdtempSync(path.join(os.tmpdir(), prefix));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function write(root, rel, text) {
  mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
  writeFileSync(path.join(root, rel), text);
}

function fakePackage(t, skill = SKILL) {
  const root = tmp(t, 'dgf-pkg-');
  write(root, 'skills/dgf-x/SKILL.md', skill);
  write(root, 'skills/dgf-x/references/R.md', 'see {{dgf_runtime}}/knowledge/k.md\n');
  write(root, 'scripts/a.py', 'print(1)\n');
  write(root, 'scripts/__pycache__/a.cpython-39.pyc', 'x');
  write(root, 'knowledge/k.md', 'fact\n');
  write(root, 'skills/dgf-scaffold/templates/solution/obj/Debug/x', 'ide output');
  return root;
}

function receiptFrom(actions, harnessIds) {
  const files = {};
  for (const a of actions) {
    if (a.sourceHash) files[a.rel] = { source: a.source, owner: a.owner, sourceHash: a.sourceHash, installedHash: a.installedHash };
  }
  return { tool: 'dgf-factory', version: '0.2.0', harnesses: harnessIds.map((id) => ({ id, selected: true })), files, mcp: {} };
}

function install(projectRoot, actions) {
  for (const a of actions) if (a.content) write(projectRoot, a.rel, a.content);
}

const byRel = (actions) => new Map(actions.map((a) => [a.rel, a]));

test('the payload is skills/, scripts/ and knowledge/, without bytecode or IDE output', (t) => {
  const pkg = fakePackage(t);
  assert.deepEqual(payloadFiles(pkg), ['skills/dgf-x/SKILL.md', 'skills/dgf-x/references/R.md', 'scripts/a.py', 'knowledge/k.md']);
});

test('a first install creates the runtime, its .gitignore and one SKILL.md per harness', (t) => {
  const pkg = fakePackage(t);
  const project = tmp(t, 'dgf-proj-');
  const actions = planInstall({ projectRoot: project, harnesses: [getHarness('claude'), getHarness('codex')], receipt: null, packageRoot: pkg });
  const rels = byRel(actions);
  for (const rel of ['.dgf-factory/runtime/scripts/a.py', '.dgf-factory/runtime/skills/dgf-x/SKILL.md', RUNTIME_GITIGNORE,
    '.claude/skills/dgf-x/SKILL.md', '.codex/skills/dgf-x/SKILL.md']) {
    assert.equal(rels.get(rel)?.kind, 'create', rel);
  }
  assert.match(rels.get('.codex/skills/dgf-x/SKILL.md').content.toString(), /then \$dgf-y\./);
  assert.match(rels.get('.dgf-factory/runtime/skills/dgf-x/references/R.md').content.toString(), /\.dgf-factory\/runtime\/knowledge\/k\.md/);
  assert.ok(![...rels.keys()].some((rel) => rel.includes('__pycache__') || rel.includes('/obj/')));
});

test('a re-run with nothing changed is all unchanged, and a no-op', (t) => {
  const pkg = fakePackage(t);
  const project = tmp(t, 'dgf-proj-');
  const harnesses = [getHarness('claude')];
  const first = planInstall({ projectRoot: project, harnesses, receipt: null, packageRoot: pkg });
  install(project, first);
  const second = planInstall({ projectRoot: project, harnesses, receipt: receiptFrom(first, ['claude']), packageRoot: pkg });
  assert.ok(second.every((a) => a.kind === 'unchanged'), JSON.stringify(second.map((a) => a.kind)));
  assert.ok(isNoop(second));
});

test('a symlink at an install target is a conflict: never read, never diffed, never replaced', (t) => {
  const pkg = fakePackage(t);
  const project = tmp(t, 'dgf-proj-');
  const secret = path.join(tmp(t, 'dgf-outside-'), 'id_rsa');
  writeFileSync(secret, 'PRIVATE KEY MATERIAL\n');
  mkdirSync(path.join(project, '.claude/skills/dgf-x'), { recursive: true });
  symlinkSync(secret, path.join(project, '.claude/skills/dgf-x/SKILL.md'));
  const harnesses = [getHarness('claude')];
  const actions = planInstall({ projectRoot: project, harnesses, receipt: null, packageRoot: pkg });
  const link = byRel(actions).get('.claude/skills/dgf-x/SKILL.md');
  assert.equal(link.kind, 'conflict-unmanaged');
  assert.equal(link.reason, 'is a symbolic link');
  assert.equal(link.diff, undefined);
  const preview = renderPreview({ projectRoot: project, harnesses, actions });
  assert.doesNotMatch(preview, /PRIVATE KEY MATERIAL/);
  assert.match(preview, /\.claude\/skills\/dgf-x\/SKILL\.md — is a symbolic link/);
  // recorded by an earlier setup: still a conflict, and the receipt entry is carried over
  const previous = { source: 'skills/dgf-x/SKILL.md', owner: 'claude', sourceHash: 'a', installedHash: 'b' };
  const receipt = { tool: 'dgf-factory', version: '0.2.0', harnesses: [{ id: 'claude', selected: true }], files: { '.claude/skills/dgf-x/SKILL.md': previous }, mcp: {} };
  const again = byRel(planInstall({ projectRoot: project, harnesses, receipt, packageRoot: pkg })).get('.claude/skills/dgf-x/SKILL.md');
  assert.equal(again.kind, 'conflict');
  assert.equal(again.previous, previous);
  assert.equal(again.diff, undefined);
});

test('every row of the update table', () => {
  const want = { source: 's', owner: 'claude', sourceBytes: Buffer.from('new src'), content: Buffer.from('new out') };
  const old = { installedHash: hashBytes(Buffer.from('old out')), sourceHash: hashBytes(Buffer.from('old src')) };
  const same = { installedHash: hashBytes(Buffer.from('new out')), sourceHash: hashBytes(Buffer.from('new src')) };
  // template unchanged, file unedited
  assert.equal(decide('f', want, same, Buffer.from('new out')).kind, 'unchanged');
  // template changed, file unedited
  assert.equal(decide('f', want, old, Buffer.from('old out')).kind, 'update');
  // template unchanged, file edited
  assert.equal(decide('f', want, same, Buffer.from('mine')).kind, 'keep-edited');
  // both changed: a conflict with a diff
  const conflict = decide('f', want, old, Buffer.from('mine'));
  assert.equal(conflict.kind, 'conflict');
  assert.match(conflict.diff, /-mine\n\+new out/);
  // file missing
  assert.equal(decide('f', want, old, null).kind, 'missing');
  // never installed, not on disk
  assert.equal(decide('f', want, null, null).kind, 'create');
  // never installed, but a different file is there
  assert.equal(decide('f', want, null, Buffer.from('theirs')).kind, 'conflict-unmanaged');
  // never installed, and the same bytes are there: adopted
  assert.equal(decide('f', want, null, Buffer.from('new out\r\n')).kind, 'unchanged');
});

test('a template removed from the package: unedited is removed, edited is kept, deleted is gone', (t) => {
  const pkg = fakePackage(t);
  const project = tmp(t, 'dgf-proj-');
  const harnesses = [getHarness('claude')];
  const first = planInstall({ projectRoot: project, harnesses, receipt: null, packageRoot: pkg });
  install(project, first);
  const receipt = receiptFrom(first, ['claude']);
  rmSync(path.join(pkg, 'scripts', 'a.py'));
  rmSync(path.join(pkg, 'knowledge', 'k.md'));
  rmSync(path.join(pkg, 'skills', 'dgf-x', 'references', 'R.md'));
  write(project, '.dgf-factory/runtime/knowledge/k.md', 'my edit\n');
  rmSync(path.join(project, '.dgf-factory/runtime/skills/dgf-x/references/R.md'));
  const rels = byRel(planInstall({ projectRoot: project, harnesses, receipt, packageRoot: pkg }));
  assert.equal(rels.get('.dgf-factory/runtime/scripts/a.py').kind, 'remove');
  assert.equal(rels.get('.dgf-factory/runtime/knowledge/k.md').kind, 'keep-edited');
  assert.ok(rels.get('.dgf-factory/runtime/knowledge/k.md').orphan);
  assert.equal(rels.get('.dgf-factory/runtime/skills/dgf-x/references/R.md').kind, 'gone');
});

test('a harness dropped from the selection is carried over, never touched', (t) => {
  const pkg = fakePackage(t);
  const project = tmp(t, 'dgf-proj-');
  const first = planInstall({ projectRoot: project, harnesses: [getHarness('claude'), getHarness('gemini')], receipt: null, packageRoot: pkg });
  install(project, first);
  const rels = byRel(planInstall({ projectRoot: project, harnesses: [getHarness('claude')], receipt: receiptFrom(first, ['claude', 'gemini']), packageRoot: pkg }));
  assert.equal(rels.get('.gemini/skills/dgf-x/SKILL.md').kind, 'carried');
  assert.equal(rels.get('.claude/skills/dgf-x/SKILL.md').kind, 'unchanged');
});

test('the preview puts what needs the user first, lists every write, and is stable', (t) => {
  const pkg = fakePackage(t);
  const project = tmp(t, 'dgf-proj-');
  write(project, '.claude/skills/dgf-x/SKILL.md', 'my own skill\n');
  const harnesses = [getHarness('claude')];
  const actions = planInstall({ projectRoot: project, harnesses, receipt: null, packageRoot: pkg });
  const text = renderPreview({ projectRoot: project, harnesses, actions });
  assert.equal(text, renderPreview({ projectRoot: project, harnesses, actions: [...actions].reverse() }));
  const lines = text.split('\n');
  assert.ok(lines.indexOf('Needs you:') < lines.findIndex((l) => l.startsWith('Runtime (')));
  assert.match(text, /CONFLICT \.claude\/skills\/dgf-x\/SKILL\.md — not installed by dgf-factory/);
  assert.match(text, /create {3}\.dgf-factory\/runtime\/scripts\/a\.py/);
});

test('the real package renders: every shipped skill, for Claude Code', () => {
  const desired = desiredFiles(REPO, [getHarness('claude')]);
  const skills = [...desired.keys()].filter((rel) => rel.startsWith('.claude/skills/'));
  assert.equal(skills.length, skillNames(REPO).length);
  assert.ok(skills.length >= 13);
  for (const rel of skills) assert.ok(!desired.get(rel).content.toString().includes('{{dgf_runtime}}'), rel);
});

test('an agent installs for a harness with an agentsDir and a package folder of its own, rendered like a skill', (t) => {
  const pkg = fakePackage(t);
  write(pkg, 'agents/claude/dgf-a.md', '---\nname: dgf-a\n---\nRun `python3 "<main project>/{{dgf_runtime}}/scripts/a.py"`, then /dgf-y.\n');
  write(pkg, 'agents/claude/notes.txt', 'not an agent');
  const project = tmp(t, 'dgf-proj-');
  const harnesses = [getHarness('claude'), getHarness('codex'), getHarness('gemini')];
  const rels = byRel(planInstall({ projectRoot: project, harnesses, receipt: null, packageRoot: pkg }));
  const agent = rels.get('.claude/agents/dgf-a.md');
  assert.equal(agent?.kind, 'create');
  assert.equal(agent.owner, 'claude');
  assert.equal(agent.source, 'agents/claude/dgf-a.md');
  assert.match(agent.content.toString(), /"<main project>\/\.dgf-factory\/runtime\/scripts\/a\.py"/);
  // codex has an agentsDir but the package ships it no agents; gemini has no agentsDir
  assert.deepEqual([...rels.keys()].filter((rel) => rel.includes('/agents/')), ['.claude/agents/dgf-a.md']);
  assert.ok(![...rels.keys()].some((rel) => rel.includes('notes.txt') || rel.startsWith('.dgf-factory/runtime/agents')));
  assert.deepEqual(agentNames(pkg, 'claude'), ['dgf-a']);
  assert.deepEqual(agentNames(pkg, 'gemini'), []);
});

test('a re-run with an agent installed is unchanged, and an agent dropped from the package is removed', (t) => {
  const pkg = fakePackage(t);
  write(pkg, 'agents/claude/dgf-a.md', '---\nname: dgf-a\n---\nbody\n');
  const project = tmp(t, 'dgf-proj-');
  const harnesses = [getHarness('claude')];
  const first = planInstall({ projectRoot: project, harnesses, receipt: null, packageRoot: pkg });
  install(project, first);
  const receipt = receiptFrom(first, ['claude']);
  assert.ok(planInstall({ projectRoot: project, harnesses, receipt, packageRoot: pkg }).every((a) => a.kind === 'unchanged'));
  rmSync(path.join(pkg, 'agents'), { recursive: true });
  assert.equal(byRel(planInstall({ projectRoot: project, harnesses, receipt, packageRoot: pkg })).get('.claude/agents/dgf-a.md').kind, 'remove');
});

test('the real package ships the two implement agents for Claude Code only', () => {
  assert.deepEqual(agentNames(REPO, 'claude'), ['dgf-implement-coordinator', 'dgf-implement-worker']);
  const desired = desiredFiles(REPO, [getHarness('claude'), getHarness('codex'), getHarness('antigravity')]);
  const agents = [...desired.keys()].filter((rel) => rel.includes('/agents/'));
  assert.deepEqual(agents, ['.claude/agents/dgf-implement-coordinator.md', '.claude/agents/dgf-implement-worker.md']);
  for (const rel of agents) {
    const text = desired.get(rel).content.toString();
    assert.ok(!text.includes('{{dgf_runtime}}'), rel);
    assert.match(text, /\.dgf-factory\/runtime\/scripts\//, rel);
  }
});
