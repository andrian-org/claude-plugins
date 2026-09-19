#!/usr/bin/env bash
# check-dual-schema-docs.sh — guard the dual-schema documentation contract.
#
# DGF supports two configuration formats: modern JSON component config and legacy XML
# validated by XSD. Every document in this plugin used to assume JSON only, and all of
# them cited DotGovFramework/docs/schemas/ — which holds just three hand-authored
# contracts, not the generated set. This check stops both mistakes coming back.
#
# It is a repo-maintenance check, not a runtime validator: contributors run it, skills
# do not. It reads and reports; it never edits.
#
# Usage:  bash scripts/check-dual-schema-docs.sh
#         DEBUG=1 bash scripts/check-dual-schema-docs.sh     # per-file trace
#
# Exit codes (contract, see .ai-factory/rules/base.md):
#   0  CLEAN     — no findings
#   1  BLOCKED   — at least one error; fix before committing
#   2  WARNINGS  — no errors, but something needs a human look
#   3  usage error

set -eu

# --- colours (defined once, disabled when not a terminal) --------------------
if [ -t 1 ]; then
    RED=$'\033[0;31m'
    YELLOW=$'\033[0;33m'
    GREEN=$'\033[0;32m'
    BOLD=$'\033[1m'
    NC=$'\033[0m'
else
    RED='' YELLOW='' GREEN='' BOLD='' NC=''
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

REFERENCE_PAGE='docs/dgf-schemas.md'

# Files that must mention both families once they mention schemas at all.
REQUIRED_DOCS='
README.md
AGENTS.md
.ai-factory/ARCHITECTURE.md
.ai-factory/DESCRIPTION.md
docs/architecture.md
docs/dgf-knowledge.md
docs/getting-started.md
docs/skill-authoring.md
docs/dgf-schemas.md
'

ERRORS=0
WARNINGS=0
FILES_SCANNED=0

fail() {
    code=$1
    shift
    printf '%s\n' "$*" >&2
    exit "$code"
}

error() {
    ERRORS=$((ERRORS + 1))
    printf '%sERROR%s %s\n' "${RED}" "${NC}" "$*"
}

warn() {
    WARNINGS=$((WARNINGS + 1))
    printf '%sWARN%s  %s\n' "${YELLOW}" "${NC}" "$*"
}

trace() {
    if [ -n "${DEBUG:-}" ] || [ "${LOG_LEVEL:-}" = "debug" ]; then
        printf '  · %s\n' "$*"
    fi
}

section() {
    printf '\n%s%s%s\n' "${BOLD}" "$*" "${NC}"
}

# Markdown files this plugin owns. The aif-* corpus under .claude/ is
# installer-managed and must be neither edited nor linted. Plan artifacts are
# excluded too: they carry the user's verbatim request, which is immutable.
owned_markdown() {
    find "${PLUGIN_ROOT}" \
        -type d \( -name .claude -o -name .git -o -name node_modules -o -name plans \) -prune \
        -o -type f -name '*.md' -print
}

relpath() {
    printf '%s' "${1#"${PLUGIN_ROOT}"/}"
}

# --- 1. no stale schema-source claim -----------------------------------------
#
# docs/schemas/ may be mentioned, but only as what it actually is: three
# hand-authored standalone contracts. Presenting it as the DGF schema location
# is the regression this catches.
QUALIFIER_WINDOW=2

scan_stale_schema_source() {
    while IFS= read -r file; do
        [ -n "${file}" ] || continue
        awk -v rel="$(relpath "${file}")" -v win="${QUALIFIER_WINDOW}" '
            { lines[NR] = tolower($0) }
            END {
                for (i = 1; i <= NR; i++) {
                    if (lines[i] !~ /docs\/schemas\//) continue
                    ok = 0
                    for (j = i - win; j <= i + win; j++) {
                        if (j < 1 || j > NR) continue
                        if (lines[j] ~ /hand-authored|standalone contracts|not the generated/) {
                            ok = 1
                            break
                        }
                    }
                    if (!ok) printf "%s\t%d\n", rel, i
                }
            }
        ' "${file}"
    done <<EOF
$(owned_markdown)
EOF
}

check_stale_schema_source() {
    section '1. Stale schema-source claims'

    # Window-scoped, not file-scoped and not line-scoped.
    #   - Line-scoped produces false positives: the qualifier routinely wraps onto the
    #     next line ("… holds only three / hand-authored standalone contracts").
    #   - File-scoped is too permissive: the bare word "standalone" appears as a
    #     directory name in knowledge/schemas/{json,xsd,standalone}/, which would
    #     excuse a genuine stale claim elsewhere in the same file.
    # So: require a qualifying phrase within QUALIFIER_WINDOW lines of the mention.
    while IFS=$'\t' read -r file lineno; do
        [ -n "${file}" ] || continue
        error "${file}:${lineno} cites docs/schemas/ without noting nearby that it holds only the three hand-authored standalone contracts"
    done <<EOF
$(scan_stale_schema_source)
EOF
}

# --- 2. both families cited ---------------------------------------------------
check_both_families() {
    section '2. Both schema families cited'

    for rel in ${REQUIRED_DOCS}; do
        file="${PLUGIN_ROOT}/${rel}"
        if [ ! -f "${file}" ]; then
            error "${rel} is missing but is a required document"
            continue
        fi

        FILES_SCANNED=$((FILES_SCANNED + 1))

        if ! grep -qi 'schema' "${file}"; then
            trace "${rel}: no schema mention, nothing to check"
            continue
        fi

        has_json=0
        has_xsd=0
        grep -qi 'json' "${file}" && has_json=1 || true
        grep -qiE 'xsd|legacy xml' "${file}" && has_xsd=1 || true

        if [ "${has_json}" -eq 1 ] && [ "${has_xsd}" -eq 1 ]; then
            trace "${rel}: both families cited"
            continue
        fi
        if [ "${has_json}" -eq 1 ]; then
            warn "${rel} mentions schemas and JSON but never XSD or legacy XML"
            continue
        fi
        warn "${rel} mentions schemas but not both families (JSON: ${has_json}, XSD: ${has_xsd})"
    done
}

# --- 3. reference page exists and is linked -----------------------------------
check_reference_page() {
    section '3. Reference page present and linked'

    if [ ! -f "${PLUGIN_ROOT}/${REFERENCE_PAGE}" ]; then
        error "${REFERENCE_PAGE} is missing — it is the canonical dual-schema reference"
        return
    fi
    trace "${REFERENCE_PAGE} exists"

    for rel in README.md AGENTS.md; do
        file="${PLUGIN_ROOT}/${rel}"
        if [ ! -f "${file}" ]; then
            error "${rel} is missing but must link ${REFERENCE_PAGE}"
            continue
        fi
        if grep -q 'dgf-schemas.md' "${file}"; then
            trace "${rel} links the reference page"
            continue
        fi
        error "${rel} does not link ${REFERENCE_PAGE}"
    done
}

# --- 4. no absolute paths in link targets or fenced code ----------------------
#
# Deliberately narrow. Prose citations of where the DGF repository lives are
# legitimate and must not fail this check — including the anti-pattern rule in
# ARCHITECTURE.md that quotes /Users/... as the thing to forbid. What breaks for
# other readers is a link target or a command, so only those are scanned.
scan_absolute_paths() {
    while IFS= read -r file; do
        awk -v rel="$(relpath "${file}")" '
            /^[[:space:]]*```/ { in_fence = !in_fence; next }
            $0 ~ /\]\((\/Users\/|\/home\/|~\/)/ { printf "LINK\t%s\t%d\n", rel, NR; next }
            in_fence && $0 ~ /(\/Users\/|\/home\/)/ { printf "CODE\t%s\t%d\n", rel, NR }
        ' "${file}"
    done <<EOF
$(owned_markdown)
EOF
}

check_absolute_paths() {
    section '4. Absolute paths in link targets and code blocks'

    while IFS=$'\t' read -r kind file lineno; do
        [ -n "${kind}" ] || continue
        if [ "${kind}" = "LINK" ]; then
            error "${file}:${lineno} markdown link target uses an absolute path"
        else
            error "${file}:${lineno} code block contains an absolute path"
        fi
    done <<EOF
$(scan_absolute_paths)
EOF

    trace 'scanned link targets and fenced blocks'
}

main() {
    if [ "$#" -gt 0 ]; then
        fail 3 "Usage: $(basename "$0")   (no arguments; set DEBUG=1 for a per-file trace)"
    fi
    if [ ! -d "${PLUGIN_ROOT}/docs" ]; then
        fail 3 "Not a dgf-factory checkout: ${PLUGIN_ROOT}/docs not found"
    fi

    printf '%sDual-schema documentation check%s\n' "${BOLD}" "${NC}"
    printf 'Root: %s\n' "${PLUGIN_ROOT}"

    # Each check appends to ERRORS / WARNINGS in this shell, so none of them may
    # run in a subshell — that is why the loops above read from here-docs rather
    # than from a pipe.
    check_stale_schema_source
    check_both_families
    check_reference_page
    check_absolute_paths

    section 'Summary'
    printf 'Files checked: %d\n' "${FILES_SCANNED}"
    printf 'Errors:        %d\n' "${ERRORS}"
    printf 'Warnings:      %d\n' "${WARNINGS}"

    if [ "${ERRORS}" -gt 0 ]; then
        printf '\n%sBLOCKED%s\n' "${RED}" "${NC}"
        exit 1
    fi
    if [ "${WARNINGS}" -gt 0 ]; then
        printf '\n%sWARNINGS%s\n' "${YELLOW}" "${NC}"
        exit 2
    fi
    printf '\n%sCLEAN%s\n' "${GREEN}" "${NC}"
    exit 0
}

main "$@"
