#!/usr/bin/env bash
# smoke_install.sh — pack, install and set up dgf-factory end to end, as a developer would (ADR 0029).
#
# A maintainer check, not shipped. It never touches the real global prefix: the
# tarball is installed with `npm install -g --prefix` into a temporary folder.
#
#   1. npm pack
#   2. npm install -g --prefix <tmp>/npm <tarball>
#   3. dgf-factory setup --harness claude,codex,gemini --yes, in an empty project; the two implement
#      agents land in .claude/agents/ and nowhere else (ADR 0033 §5)
#   3b. a second project on the oldest packed DGF line (--dgf-line): its receipt names that line and its
#       runtime knowledge carries that line's stamp, while the first project holds the current line's
#       (ADR 0036 §3) — skipped, with a note, when the package holds one line
#   4. a second setup: exit 0, nothing written
#   5. edit one installed skill, set up again: the edit is kept, and reported
#   6. the installed doctor: exit 0, or 2 with only INSTALL_FILE_EDITED (from step 5)
#      and VALIDATOR_DEPS_MISSING (with --no-python)
#   7. no ${CLAUDE_PLUGIN_ROOT} and no {{dgf_runtime}} anywhere in the project's skills
#   8. when `claude` is on PATH: `claude -p "/dgf-doctor"` in the project ends with a pass or warn block
#
# Usage:  bash tools/smoke_install.sh [--python]     # --python also builds the project's .venv (network)
#         DEBUG=1 bash tools/smoke_install.sh         # keep the temporary folder, trace each step
#
# Exit codes (contract, see .ai-factory/rules/base.md):
#   0  CLEAN    — every step passed
#   1  BLOCKED  — a step failed; its output is above
#   3  usage error — npm or node is missing, or a bad argument
set -u

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_FLAG='--no-python'

fail() { printf 'FAIL  %s\n' "$2" >&2; exit "$1"; }
step() { printf '\n== %s\n' "$1"; }
trace() { [ -n "${DEBUG:-}" ] && printf '  · %s\n' "$1"; return 0; }

case "${1:-}" in
    '') ;;
    --python) PYTHON_FLAG='' ;;
    *) fail 3 "Usage: $(basename "$0") [--python]" ;;
esac
command -v npm >/dev/null 2>&1 || fail 3 'npm is not installed'
command -v node >/dev/null 2>&1 || fail 3 'node is not installed'

TMP="$(mktemp -d)"
if [ -z "${DEBUG:-}" ]; then
    trap 'rm -rf "${TMP}"' EXIT
else
    printf 'Keeping %s\n' "${TMP}"
fi
PROJECT="${TMP}/project"
mkdir -p "${PROJECT}"

step '1. npm pack'
tarball="$(cd "${PLUGIN_ROOT}" && npm pack --silent --pack-destination "${TMP}")" || fail 1 'npm pack failed'
trace "packed ${tarball}"

step '2. npm install -g --prefix (a temporary prefix, never the real one)'
npm install -g --silent --prefix "${TMP}/npm" "${TMP}/${tarball}" || fail 1 'npm install failed'
CLI="${TMP}/npm/bin/dgf-factory"
[ -x "${CLI}" ] || fail 1 "no dgf-factory command at ${CLI}"
printf 'dgf-factory %s\n' "$("${CLI}" --version)"

step '3. setup --harness claude,codex,gemini --yes'
code=0
"${CLI}" setup --root "${PROJECT}" --harness claude,codex,gemini --yes ${PYTHON_FLAG} || code=$?
[ "${code}" -eq 0 ] || fail 1 "setup exited ${code}"
for dir in .claude/skills .codex/skills .gemini/skills .dgf-factory/runtime/scripts; do
    [ -d "${PROJECT}/${dir}" ] || fail 1 "${dir} was not installed"
done
[ -f "${PROJECT}/.dgf-factory/install.json" ] || fail 1 'no receipt'
for agent in dgf-implement-coordinator dgf-implement-worker; do
    [ -f "${PROJECT}/.claude/agents/${agent}.md" ] || fail 1 "the ${agent} agent was not installed for claude"
    grep -qF "\".claude/agents/${agent}.md\"" "${PROJECT}/.dgf-factory/install.json" || fail 1 "the receipt does not record ${agent}"
done
for dir in .codex/agents .gemini/agents .dgf-factory/runtime/agents; do
    [ ! -e "${PROJECT}/${dir}" ] || fail 1 "${dir} was installed; agents ship for Claude Code only"
done

step '3b. two projects on two DGF lines'
REGISTRY="${TMP}/npm/lib/node_modules/@andrian-org/dgf-factory/packs/lines.json"
[ -f "${REGISTRY}" ] || fail 1 "the package holds no packs/lines.json"
lines_info="$(node -e '
const r = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8"));
const key = (l) => l.line.split(".").map(Number);
const sorted = [...r.lines].sort((a, b) => key(a)[0] - key(b)[0] || key(a)[1] - key(b)[1]);
const cur = r.lines.find((l) => l.line === r.current);
console.log([r.current, cur.dgf_version, sorted[0].line, sorted[0].dgf_version, r.lines.length].join(" "));
' "${REGISTRY}")" || fail 1 'cannot read the packed registry'
set -- ${lines_info}
current="$1"; current_version="$2"; oldest="$3"; oldest_version="$4"; line_count="$5"
trace "lines: ${line_count}; current ${current} (${current_version}); oldest ${oldest} (${oldest_version})"
stamp_of() { sed -n 's/^dgf_version: "\(.*\)"$/\1/p' "$1/.dgf-factory/runtime/knowledge/schema-families.md"; }
line_of() { node -e 'console.log(JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")).dgfLine)' "$1/.dgf-factory/install.json"; }
[ "$(line_of "${PROJECT}")" = "${current}" ] || fail 1 "the first project's receipt does not name line ${current}"
[ "$(stamp_of "${PROJECT}")" = "${current_version}" ] || fail 1 "the first project's knowledge is not stamped ${current_version}"
if [ "${line_count}" -gt 1 ]; then
    OTHER="${TMP}/other-project"
    mkdir -p "${OTHER}"
    code=0
    "${CLI}" setup --root "${OTHER}" --harness claude --dgf-line "${oldest}" --yes --no-python > "${TMP}/other.txt" || code=$?
    [ "${code}" -eq 0 ] || { cat "${TMP}/other.txt"; fail 1 "setup --dgf-line ${oldest} exited ${code}"; }
    [ "$(line_of "${OTHER}")" = "${oldest}" ] || fail 1 "the second project's receipt does not name line ${oldest}"
    [ "$(stamp_of "${OTHER}")" = "${oldest_version}" ] || fail 1 "the second project's knowledge is not stamped ${oldest_version}"
    printf 'line %s (%s) and line %s (%s) installed side by side\n' "${current}" "${current_version}" "${oldest}" "${oldest_version}"
else
    printf 'the package holds one DGF line (%s) — the side-by-side install is skipped\n' "${current}"
fi

step '4. a second setup changes nothing'
before="$(cd "${PROJECT}" && find . -type f -not -path './.dgf-factory/runtime/.venv/*' -exec shasum {} + | sort)"
code=0
"${CLI}" setup --root "${PROJECT}" --harness claude,codex,gemini --yes ${PYTHON_FLAG} > "${TMP}/second.txt" || code=$?
[ "${code}" -eq 0 ] || { cat "${TMP}/second.txt"; fail 1 "the second setup exited ${code}"; }
after="$(cd "${PROJECT}" && find . -type f -not -path './.dgf-factory/runtime/.venv/*' -exec shasum {} + | sort)"
[ "${before}" = "${after}" ] || fail 1 'the second setup changed a file'
grep -q 'Written: 0 file(s)' "${TMP}/second.txt" || fail 1 'the second setup reported writes'

step '5. an edited skill survives setup'
SKILL="${PROJECT}/.claude/skills/dgf-plan/SKILL.md"
printf '\nOur team rule.\n' >> "${SKILL}"
code=0
"${CLI}" setup --root "${PROJECT}" --harness claude,codex,gemini --yes ${PYTHON_FLAG} > "${TMP}/third.txt" || code=$?
[ "${code}" -eq 2 ] || { cat "${TMP}/third.txt"; fail 1 "setup over an edit exited ${code}, not 2"; }
grep -q 'Our team rule.' "${SKILL}" || fail 1 'the edit was overwritten'
grep -q 'kept  .claude/skills/dgf-plan/SKILL.md' "${TMP}/third.txt" || fail 1 'the edit was not reported'

step '6. the installed doctor'
code=0
(cd "${PROJECT}" && python3 .dgf-factory/runtime/skills/dgf-doctor/scripts/doctor.py) > "${TMP}/doctor.txt" 2>&1 || code=$?
unexpected="$(grep -E '^(ERROR|WARN) ' "${TMP}/doctor.txt" | grep -vE 'was edited since setup|not installed — the validators' || true)"
if [ "${code}" -eq 1 ] || [ "${code}" -eq 3 ] || [ -n "${unexpected}" ]; then
    cat "${TMP}/doctor.txt"
    fail 1 "the doctor exited ${code}"
fi
printf 'doctor exit %s\n' "${code}"

step '7. nothing left unrendered'
leftover="$(grep -rlE '\$\{CLAUDE_PLUGIN_ROOT\}|\{\{dgf_runtime\}\}' "${PROJECT}/.claude" "${PROJECT}/.codex" "${PROJECT}/.gemini" \
    "${PROJECT}/.dgf-factory/runtime/skills" --include='*.md' 2>/dev/null || true)"
[ -z "${leftover}" ] || fail 1 "unrendered tokens in: ${leftover}"

step '8. /dgf-doctor in Claude Code'
if command -v claude >/dev/null 2>&1; then
    code=0
    (cd "${PROJECT}" && claude -p '/dgf-doctor' > "${TMP}/claude.txt" 2>&1) || code=$?
    if ! grep -qE '"status": "(pass|warn)"' "${TMP}/claude.txt"; then
        cat "${TMP}/claude.txt"
        fail 1 "claude -p /dgf-doctor did not end with a pass or warn block (exit ${code})"
    fi
    printf 'claude -p /dgf-doctor: a pass or warn block\n'
else
    printf 'MANUAL: open Claude Code in a project set up by step 3, then run /dgf-doctor and /dgf\n'
fi

printf '\nCLEAN\n'
