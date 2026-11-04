// Which DGF line setup installs (ADR 0036 §3): the shared selection vectors, the config scan, the registry, and
// setup end to end against a package with two packs.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

import { run } from '../../cli/commands/setup.mjs';
import { CliError, EXIT_BLOCKED, EXIT_USAGE } from '../../cli/exit.mjs';
import { loadLines, readConfigVersion, selectLine } from '../../cli/lines.mjs';

const REPO = path.resolve(fileURLToPath(new URL('../..', import.meta.url)));
const VECTORS = JSON.parse(readFileSync(path.join(REPO, 'tests/fixtures/unit/dgf-lines/selection.json'), 'utf8'));
const OLD = '0.9';

function tmp(t, prefix = 'dgf-lines-') {
  const dir = mkdtempSync(path.join(os.tmpdir(), prefix));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function sink() {
  let text = '';
  return { write: (chunk) => { text += chunk; return true; }, text: () => text };
}

function camel(input) {
  return { flagLine: input.flag_line, flagVersion: input.flag_version, receiptLine: input.receipt_line, configVersion: input.config_version };
}

function check(lines, current, testCase) {
  const call = () => selectLine({ lines, current, ...camel(testCase.input) });
  if (testCase.expect.error) {
    assert.throws(call, (err) => err instanceof CliError && err.code === (testCase.expect.error === 'usage' ? EXIT_USAGE : EXIT_BLOCKED), testCase.name);
    return;
  }
  const chosen = call();
  assert.equal(chosen.line, testCase.expect.line, testCase.name);
  assert.equal(chosen.source, testCase.expect.source, testCase.name);
  assert.equal(Boolean(chosen.note), Boolean(testCase.expect.note), `${testCase.name}: ${chosen.note}`);
}

test('every shared selection vector, as scripts/lib/dgf_version.py passes them', () => {
  for (const testCase of VECTORS.cases) check(VECTORS.lines, VECTORS.current, testCase);
  check(VECTORS.gap.lines, VECTORS.gap.current, VECTORS.gap);
});

test('the declared dgf.version is read from the project config without a YAML library', (t) => {
  const root = tmp(t);
  assert.equal(readConfigVersion(root), null, 'no config');
  mkdirSync(path.join(root, '.dgf-factory'));
  const config = path.join(root, '.dgf-factory/config.yaml');
  writeFileSync(config, 'language:\n  ui: en\ndgf:\n  version: "1.2.0"   # declared at setup\npaths:\n  version: "9.9.9"\n');
  assert.equal(readConfigVersion(root), '1.2.0');
  writeFileSync(config, "dgf:\n  version: unknown\n");
  assert.equal(readConfigVersion(root), 'unknown');
  writeFileSync(config, 'other:\n  version: "1.3.0"\n');
  assert.equal(readConfigVersion(root), null, 'a version under another key is not the estate\'s');
});

test('the package registry loads and names its current line', () => {
  const registry = loadLines(REPO);
  assert.ok(registry.lines.some((entry) => entry.line === registry.current && entry.dir === 'knowledge'));
});

// A package with the real current line in knowledge/ and an older line in packs/0.9/ that differs from it.
function twoPackPackage(t) {
  const pkg = tmp(t, 'dgf-pkg-');
  for (const entry of ['package.json', 'skills', 'scripts', 'knowledge']) cpSync(path.join(REPO, entry), path.join(pkg, entry), { recursive: true });
  const real = loadLines(REPO);
  cpSync(path.join(REPO, 'knowledge'), path.join(pkg, 'packs', OLD), { recursive: true });
  rmSync(path.join(pkg, 'packs', OLD, 'README.md'));
  writeFileSync(path.join(pkg, 'packs', OLD, 'only-in-old.md'), '---\ndgf_version: "0.9.1"\nread_date: 2026-11-04\n---\n');
  const facts = path.join(pkg, 'packs', OLD, 'permissions.md');
  writeFileSync(facts, `${readFileSync(facts, 'utf8')}\nRead at 0.9.\n`);
  const current = real.lines.find((entry) => entry.line === real.current);
  writeFileSync(path.join(pkg, 'packs/lines.json'), JSON.stringify({ format: 1, current: real.current, lines: [
    { ...current }, { line: OLD, dir: `packs/${OLD}`, dgf_version: '0.9.1', read_date: '2026-11-04' }] }));
  return { pkg, current: real.current };
}

async function setup(pkg, project, ...args) {
  const out = sink();
  const code = await run(['--root', project, '--harness', 'claude', '--yes', '--no-python', ...args], { parseArgs }, { io: null, out, pkgRoot: pkg });
  return { code, text: out.text(), receipt: JSON.parse(readFileSync(path.join(project, '.dgf-factory/install.json'), 'utf8')) };
}

const RUNTIME = '.dgf-factory/runtime/knowledge';

test('an older line installs its pack at the same runtime path, with the shared README', async (t) => {
  const { pkg } = twoPackPackage(t);
  const project = tmp(t);
  const result = await setup(pkg, project, '--dgf-line', OLD);
  assert.equal(result.code, 0, result.text);
  assert.equal(result.receipt.dgfLine, OLD);
  assert.match(result.text, new RegExp(`DGF line: ${OLD.replace('.', '\\.')} \\(knowledge read at DGF 0\\.9\\.1; from --dgf-line\\)`));
  assert.ok(existsSync(path.join(project, RUNTIME, 'only-in-old.md')));
  assert.match(readFileSync(path.join(project, RUNTIME, 'permissions.md'), 'utf8'), /Read at 0\.9\./);
  assert.equal(readFileSync(path.join(project, RUNTIME, 'README.md'), 'utf8'), readFileSync(path.join(pkg, 'knowledge/README.md'), 'utf8'));
  assert.equal(result.receipt.files[`${RUNTIME}/permissions.md`].source, `packs/${OLD}/permissions.md`);
  assert.equal(result.receipt.files[`${RUNTIME}/README.md`].source, 'knowledge/README.md');
  assert.ok(!Object.keys(result.receipt.files).some((rel) => rel.includes('/packs/')), 'no pack is installed under its own path');
});

test('switching line updates and removes only what differs, and keeps an edited knowledge file', async (t) => {
  const { pkg, current } = twoPackPackage(t);
  const project = tmp(t);
  assert.equal((await setup(pkg, project, '--dgf-line', OLD)).code, 0);
  const edited = path.join(project, RUNTIME, 'naming-conventions.md');
  writeFileSync(edited, `${readFileSync(edited, 'utf8')}\nOur note.\n`);
  const result = await setup(pkg, project, '--dgf-line', current);
  assert.equal(result.receipt.dgfLine, current);
  assert.equal(existsSync(path.join(project, RUNTIME, 'only-in-old.md')), false, 'a file only the old pack had is removed');
  assert.doesNotMatch(readFileSync(path.join(project, RUNTIME, 'permissions.md'), 'utf8'), /Read at 0\.9\./, 'a differing file is updated');
  assert.match(readFileSync(edited, 'utf8'), /Our note\./, 'an edited file is kept');
  assert.equal(result.code, 2, 'the kept file needs the user');
});

test('without flags the previous line is kept, and the estate\'s dgf.version chooses on a first install', async (t) => {
  const { pkg } = twoPackPackage(t);
  const project = tmp(t);
  mkdirSync(path.join(project, '.dgf-factory'));
  writeFileSync(path.join(project, '.dgf-factory/config.yaml'), 'dgf:\n  version: "0.9.4"\n');
  const first = await setup(pkg, project);
  assert.equal(first.receipt.dgfLine, OLD);
  assert.match(first.text, /from the estate's dgf\.version/);
  writeFileSync(path.join(project, '.dgf-factory/config.yaml'), 'dgf:\n  version: "unknown"\n');
  assert.equal((await setup(pkg, project)).receipt.dgfLine, OLD, 'the receipt wins over the config');
});

test('a version below every pack is refused without --dgf-line (exit 1), and an unknown line is exit 3', async (t) => {
  const { pkg } = twoPackPackage(t);
  const project = tmp(t);
  await assert.rejects(setup(pkg, project, '--dgf-version', '0.1.0'), (err) => err.code === EXIT_BLOCKED && /--dgf-line/.test(err.message));
  await assert.rejects(setup(pkg, project, '--dgf-line', '7.7'), (err) => err.code === EXIT_USAGE);
  await assert.rejects(setup(pkg, project, '--dgf-line', OLD, '--dgf-version', '0.9.1'), (err) => err.code === EXIT_USAGE);
  assert.deepEqual(readdirSync(project), [], 'nothing written');
});
