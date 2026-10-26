// A unified line diff for a conflict's preview (ADR 0029 §5): the user's file against the new
// rendering. Longest common subsequence over lines — enough for SKILL.md-sized files; anything
// larger is summarised rather than diffed.
const MAX_LINES = 4000;
const CONTEXT = 3;

function lcsTable(a, b) {
  const table = Array.from({ length: a.length + 1 }, () => new Uint32Array(b.length + 1));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  return table;
}

function edits(a, b) {
  const table = lcsTable(a, b);
  const out = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { out.push([' ', a[i]]); i += 1; j += 1; }
    else if (table[i + 1][j] >= table[i][j + 1]) { out.push(['-', a[i]]); i += 1; }
    else { out.push(['+', b[j]]); j += 1; }
  }
  while (i < a.length) out.push(['-', a[i++]]);
  while (j < b.length) out.push(['+', b[j++]]);
  return out;
}

/** `--- yours` / `+++ new` hunks, or a one-line summary when either side is too long to diff. */
export function unifiedDiff(before, after, label) {
  const a = before.split('\n');
  const b = after.split('\n');
  if (a.length > MAX_LINES || b.length > MAX_LINES) {
    return `  (${label}: ${a.length} lines on disk, ${b.length} in the new version — too long to diff here)`;
  }
  const ops = edits(a, b);
  const changed = ops.map((op, index) => (op[0] === ' ' ? -1 : index)).filter((index) => index >= 0);
  if (!changed.length) return '';
  const lines = [`--- ${label} (yours)`, `+++ ${label} (new)`];
  let start = 0;
  while (start < changed.length) {
    let end = start;
    while (end + 1 < changed.length && changed[end + 1] - changed[end] <= CONTEXT * 2) end += 1;
    const from = Math.max(0, changed[start] - CONTEXT);
    const to = Math.min(ops.length - 1, changed[end] + CONTEXT);
    lines.push('@@');
    for (let k = from; k <= to; k += 1) lines.push(`${ops[k][0]}${ops[k][1]}`);
    start = end + 1;
  }
  return lines.join('\n');
}
