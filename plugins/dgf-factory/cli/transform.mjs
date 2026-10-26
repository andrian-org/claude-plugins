// Rendering the payload for a project (ADR 0029 §3).
//
// `{{dgf_runtime}}` becomes `.dgf-factory/runtime` in every installed Markdown file — relative,
// because a skill runs from the project root, where the harness found it. A harness's SKILL.md
// then has its `/dgf-x` invocations rewritten for that harness, in the body only: the frontmatter
// is kept as written for every harness, as AI Factory keeps it.
import * as log from './log.mjs';

export const RUNTIME_TOKEN = '{{dgf_runtime}}';
export const RUNTIME_DIR = '.dgf-factory/runtime';

// AI Factory's boundary (`dist/core/transformer.js:42`) with `aif` replaced by `dgf`: a `/` that
// follows a letter, digit, `_ . ~ / } -` is part of a path, not an invocation.
const INVOCATION = /(^|[^A-Za-z0-9_.~/}-])\/(dgf(?:-[a-z0-9-]+)?)(?![A-Za-z0-9_-])/g;

const INVOCATION_FORMS = {
  default: null,
  codex: (name) => `$${name}`,
  qwen: (name) => `/skills ${name}`,
};

function replaceToken(text) {
  const count = text.split(RUNTIME_TOKEN).length - 1;
  return { text: count ? text.split(RUNTIME_TOKEN).join(RUNTIME_DIR) : text, count };
}

function splitFrontmatter(text) {
  const match = /^---\n[\s\S]*?\n---\n/.exec(text);
  return match ? [match[0], text.slice(match[0].length)] : ['', text];
}

export function rewriteInvocations(body, transform) {
  const form = INVOCATION_FORMS[transform];
  if (form === undefined) throw new Error(`unknown transform \`${transform}\``);
  if (form === null) return body;
  return body.replace(INVOCATION, (_match, prefix, name) => `${prefix}${form(name)}`);
}

/** A SKILL.md as one harness installs it. */
export function renderSkill(harness, text, where = '') {
  const { text: replaced, count } = replaceToken(text);
  const [front, body] = splitFrontmatter(replaced);
  const rendered = front + rewriteInvocations(body, harness.transform);
  log.debug('transform.renderSkill', 'rendered', { harness: harness.id, file: where, tokens: count });
  if (count === 0 && /python3 /.test(text)) {
    log.warn('transform.renderSkill', 'a skill that runs python3 cites no runtime path', { harness: harness.id, file: where });
  }
  return rendered;
}

/** A payload file as the runtime holds it: Markdown has its token replaced; everything else is untouched. */
export function renderRuntimeFile(rel, bytes) {
  if (!rel.endsWith('.md')) return bytes;
  const { text, count } = replaceToken(bytes.toString('utf8'));
  if (count) log.debug('transform.renderRuntimeFile', 'rendered', { file: rel, tokens: count });
  return Buffer.from(text, 'utf8');
}
