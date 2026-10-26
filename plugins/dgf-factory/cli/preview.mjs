// The preview setup prints before it writes (ADR 0029 §6): what needs the user first, then every
// path it will create, change or remove, grouped by where it goes.
import { KINDS, countKinds } from './plan.mjs';
import { RUNTIME_DIR } from './transform.mjs';

const VERB = {
  'conflict-unmanaged': 'CONFLICT',
  conflict: 'CONFLICT',
  'keep-edited': 'EDITED',
  missing: 'MISSING',
  remove: 'REMOVE',
  create: 'create',
  update: 'update',
};

const WHY = {
  'conflict-unmanaged': 'not installed by dgf-factory, and differs from what it would write — left as is',
  conflict: 'you edited it, and the new version changes it too — yours is kept',
  'keep-edited': 'you edited it — yours is kept',
  missing: 'deleted since the last setup — recreated only if you agree',
  remove: 'no longer shipped, and unedited — removed only if you agree',
};

function sortActions(actions) {
  return [...actions].sort((a, b) => KINDS.indexOf(a.kind) - KINDS.indexOf(b.kind) || a.rel.localeCompare(b.rel));
}

function groupLabel(owner, harnessesById) {
  if (owner === 'runtime') return `Runtime (${RUNTIME_DIR}/)`;
  const harness = harnessesById.get(owner);
  return harness ? `${harness.displayName} (${harness.skillsDir}/)` : owner;
}

function summary(counts) {
  return KINDS.filter((kind) => counts[kind]).map((kind) => `${counts[kind]} ${kind}`).join(', ') || 'nothing';
}

/** The preview text. `mcp` and `python` are the MCP and Python steps' own preview lines. */
export function renderPreview({ projectRoot, harnesses, actions, mcp = [], python = [] }) {
  const harnessesById = new Map(harnesses.map((h) => [h.id, h]));
  const lines = [`dgf-factory setup — ${projectRoot}`, `Harnesses: ${harnesses.map((h) => h.id).join(', ') || '(none)'}`, ''];
  const attention = sortActions(actions.filter((a) => WHY[a.kind]));
  if (attention.length) {
    lines.push('Needs you:');
    for (const action of attention) {
      lines.push(`  ${VERB[action.kind].padEnd(8)} ${action.rel} — ${action.orphan ? 'no longer shipped, and you edited it — yours is kept' : WHY[action.kind]}`);
      if (action.diff) lines.push(...action.diff.split('\n').map((line) => `      ${line}`));
    }
    lines.push('');
  }
  const owners = [...new Set(actions.filter((a) => VERB[a.kind]).map((a) => a.owner))]
    .sort((a, b) => (a === 'runtime' ? -1 : b === 'runtime' ? 1 : a.localeCompare(b)));
  for (const owner of owners) {
    const mine = actions.filter((a) => a.owner === owner && VERB[a.kind]);
    lines.push(`${groupLabel(owner, harnessesById)}: ${summary(countKinds(mine))}`);
    for (const action of sortActions(mine)) {
      if (action.kind === 'create' || action.kind === 'update' || action.kind === 'remove' || action.kind === 'missing') {
        lines.push(`  ${VERB[action.kind].padEnd(8)} ${action.rel}`);
      }
    }
  }
  const quiet = actions.filter((a) => !VERB[a.kind]);
  if (quiet.length) lines.push(`Unchanged or carried over: ${quiet.length} file(s)`);
  if (mcp.length) lines.push('', 'MCP (dgf-mcp):', ...mcp.map((line) => `  ${line}`));
  if (python.length) lines.push('', 'Python:', ...python.map((line) => `  ${line}`));
  return `${lines.join('\n')}\n`;
}

/** True when applying would change nothing on disk. */
export function isNoop(actions, mcpActions = []) {
  return actions.every((a) => ['unchanged', 'carried', 'gone', 'keep-edited', 'conflict', 'conflict-unmanaged'].includes(a.kind))
    && mcpActions.every((a) => a.kind !== 'register');
}
