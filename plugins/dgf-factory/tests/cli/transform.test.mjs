// Rendering: the runtime token everywhere, invocations per harness in the body only.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { HARNESSES, getHarness } from '../../cli/harnesses.mjs';
import { RUNTIME_DIR, renderRuntimeFile, renderSkill, rewriteInvocations } from '../../cli/transform.mjs';

const ROOT = path.resolve(fileURLToPath(new URL('../..', import.meta.url)));
const SKILLS = path.join(ROOT, 'skills');
const PLUGIN_TOKEN = '${' + 'CLAUDE_PLUGIN_ROOT}';

function skillFiles() {
  return readdirSync(SKILLS).map((name) => path.join(SKILLS, name, 'SKILL.md'));
}

test('every shipped skill renders for every harness with no token left', () => {
  for (const file of skillFiles()) {
    const text = readFileSync(file, 'utf8');
    for (const harness of HARNESSES) {
      const out = renderSkill(harness, text, file);
      assert.ok(!out.includes('{{dgf_runtime}}'), `${harness.id} ${file}`);
      assert.ok(!out.includes(PLUGIN_TOKEN), `${harness.id} ${file}`);
    }
  }
});

test('the runtime token becomes the project-relative runtime folder', () => {
  const out = renderSkill(getHarness('claude'), 'run `python3 "{{dgf_runtime}}/scripts/x.py"`\n');
  assert.equal(out, `run \`python3 "${RUNTIME_DIR}/scripts/x.py"\`\n`);
});

test('codex rewrites body invocations and leaves the frontmatter alone', () => {
  const text = '---\nname: dgf-plan\nallowed-tools: Read Bash(python3 "{{dgf_runtime}}/scripts/*)\ndescription: run /dgf-plan\n---\nThen run /dgf-implement, or `/dgf`.\n';
  const out = renderSkill(getHarness('codex'), text);
  assert.match(out, /description: run \/dgf-plan\n/, 'frontmatter kept');
  assert.match(out, /Then run \$dgf-implement, or `\$dgf`\./);
  assert.match(out, /Bash\(python3 "\.dgf-factory\/runtime\/scripts\/\*\)/);
});

test('qwen invokes through /skills', () => {
  assert.equal(rewriteInvocations('next: /dgf-verify\n', 'qwen'), 'next: /skills dgf-verify\n');
});

test('paths that contain /dgf-… are not invocations', () => {
  const body = 'see ~/x/dgf-plan, a/dgf-plan, .claude/skills/dgf-plan/SKILL.md and }/dgf-x; /dgf-factoryish stays\n';
  assert.equal(rewriteInvocations(body, 'codex'), body.replace('/dgf-factoryish', '$dgf-factoryish'));
});

test('the default transform changes nothing but the token', () => {
  const text = '---\nname: x\n---\nrun /dgf-plan\n';
  assert.equal(renderSkill(getHarness('gemini'), text), text);
});

test('runtime Markdown has its token replaced; other files pass through byte for byte', () => {
  const md = renderRuntimeFile('skills/dgf/references/x.md', Buffer.from('a {{dgf_runtime}}/b\n'));
  assert.equal(md.toString(), `a ${RUNTIME_DIR}/b\n`);
  const bytes = Buffer.from([0, 1, 2, 0x7b, 0x7b]);
  assert.equal(renderRuntimeFile('knowledge/schemas/x.json', bytes), bytes);
});
