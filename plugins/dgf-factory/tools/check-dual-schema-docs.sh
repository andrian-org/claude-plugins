#!/usr/bin/env bash
# check-dual-schema-docs.sh — guard this plugin's documentation contracts.
#
# NAME/SCOPE MISMATCH, DELIBERATE: this script now guards five contracts — the
# dual-schema one it was named for, the decision-record one added 2026-09-21, the
# plugin-manifest one added 2026-09-22, the knowledge-stamp one added the same
# day, and ADR supersession integrity added 2026-09-23. The filename stays as it
# is because AGENTS.md, the docs and the plans reference it by name; renaming
# churns them for no gain. It moved from scripts/ to tools/ on 2026-09-23: it is
# a maintainer check, and scripts/ ships (ADR 0012).
#
# DGF supports two configuration formats: modern JSON component config and legacy XML
# validated by XSD. Every document in this plugin used to assume JSON only, and all of
# them cited DotGovFramework/docs/schemas/ — which holds just three hand-authored
# contracts, not the generated set. This check stops both mistakes coming back.
#
# It is a repo-maintenance check, not a runtime validator: contributors run it, skills
# do not. It reads and reports; it never edits. It is not shipped: tools/ is outside
# doctor.py's SHIPPED_DIRS, so it may name DGF repository paths.
#
# Usage:  bash tools/check-dual-schema-docs.sh
#         DEBUG=1 bash tools/check-dual-schema-docs.sh       # per-file trace
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
# ARCHITECTURE.md that quotes a machine-specific home path as the thing to
# forbid. What breaks for other readers is a link target or a command, so only
# those are scanned.
#
# This comment names no such path literally: doctor.py's portability check
# sweeps every shipped file, so a spelled-out example here would be reported as
# the very fault it describes.
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


# --- 5. decision records ------------------------------------------------------
#
# ADRs are discovered, not enumerated: REQUIRED_DOCS stays as it is, and
# owned_markdown() already sweeps docs/adr/*.md into checks 1 and 4 unchanged.
ADR_DIR='docs/adr'

adr_files() {
    find "${PLUGIN_ROOT}/${ADR_DIR}" -maxdepth 1 -type f -name '[0-9][0-9][0-9][0-9]-*.md' 2>/dev/null | sort
}

# One flat key from an ADR's YAML frontmatter only — never from the body — with
# a trailing `# comment` stripped. The ADR README's frontmatter template carries
# such comments, so an ADR copied from it must parse, not fail.
fm_value() {
    awk -v key="$1" '
        NR == 1 && $0 != "---" { exit }
        NR == 1 { next }
        /^---[[:space:]]*$/ { exit }
        index($0, key ":") == 1 {
            v = substr($0, length(key) + 2)
            sub(/[[:space:]]+#.*$/, "", v)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
            print v
            exit
        }
    ' "$2"
}

adr_status() {
    fm_value status "$1"
}

# Every ADR link written anywhere in this plugin's own markdown, as source<TAB>target.
scan_adr_links() {
    while IFS= read -r file; do
        [ -n "${file}" ] || continue
        grep -oE 'adr/[0-9]{4}-[A-Za-z0-9._-]+\.md' "${file}" 2>/dev/null \
            | sed "s|^adr/|$(relpath "${file}")\t|" || true
    done <<EOF
$(owned_markdown)
EOF
}

# The independence decision in ADR 0001, as far as it is mechanically checkable.
# Only the concrete path is scanned; "presents another effort as a constraint" is a
# judgement a script cannot make, and is left to review.
scan_superseded_tooling() {
    while IFS= read -r file; do
        [ -n "${file}" ] || continue
        grep -n 'dgf-harness' "${file}" 2>/dev/null \
            | cut -d: -f1 \
            | sed "s|^|$(relpath "${file}")\t|" || true
    done <<EOF
$(owned_markdown)
EOF
}

check_decision_records() {
    section '5. Decision records'

    index="${PLUGIN_ROOT}/${ADR_DIR}/README.md"
    if [ ! -f "${index}" ]; then
        error "${ADR_DIR}/README.md is missing — it is the ADR index"
        return
    fi
    trace "${ADR_DIR}/README.md exists"

    adr_count=0

    while IFS= read -r file; do
        [ -n "${file}" ] || continue
        adr_count=$((adr_count + 1))
        base="$(basename "${file}")"
        rel="${ADR_DIR}/${base}"
        prefix="${base%%-*}"

        if ! grep -q "(${base})" "${index}"; then
            error "${rel} has no row in ${ADR_DIR}/README.md"
        fi

        fm="$(awk 'NR==1 && $0 != "---" { exit } NR==1 { next } /^---[[:space:]]*$/ { exit } { print }' "${file}")"
        if [ -z "${fm}" ]; then
            error "${rel} has no YAML frontmatter"
            continue
        fi

        for key in id title status date; do
            if ! printf '%s\n' "${fm}" | grep -q "^${key}:"; then
                error "${rel} frontmatter is missing required key '${key}'"
            fi
        done

        id_val="$(fm_value id "${file}" | tr -d '"')"
        if [ -n "${id_val}" ] && [ "${id_val}" != "${prefix}" ]; then
            error "${rel} frontmatter id '${id_val}' does not match filename prefix '${prefix}'"
        fi

        status_val="$(adr_status "${file}")"
        case "${status_val}" in
            proposed|accepted|rejected) : ;;
            superseded-by-[0-9][0-9][0-9][0-9]) : ;;
            *) error "${rel} status '${status_val}' is outside the allowed vocabulary (proposed|accepted|rejected|superseded-by-NNNN)" ;;
        esac

        dec="$(awk '/^## Decision/ { grab=1; next } grab && /^## / { exit } grab { print }' "${file}" | tr -d '\n')"
        dec_len=${#dec}
        if [ "${dec_len}" -eq 0 ]; then
            warn "${rel} has no '## Decision' section"
        elif [ "${dec_len}" -lt 200 ]; then
            warn "${rel} '## Decision' is only ${dec_len} characters — too short to be a decision"
        fi

        trace "${rel}: id=${id_val} status=${status_val} decision=${dec_len}c"
    done <<EOF
$(adr_files)
EOF

    # Index rows must point at files that exist.
    while IFS= read -r target; do
        [ -n "${target}" ] || continue
        if [ ! -f "${PLUGIN_ROOT}/${ADR_DIR}/${target}" ]; then
            error "${ADR_DIR}/README.md links ${target}, which does not exist"
        fi
    done <<EOF
$(grep -oE '\([0-9]{4}-[A-Za-z0-9._-]+\.md\)' "${index}" 2>/dev/null | tr -d '()' | sort -u || true)
EOF

    # Every ADR reference anywhere in owned markdown must resolve.
    #
    # Deliberately broader than "every ANSWERED blueprint question links an ADR":
    # questions #1, #2 and #4 were answered from the repository before this plugin
    # had ADRs at all, and citing evidence rather than a decision is correct for
    # them. The regression worth catching is a dangling ADR link, which this covers
    # everywhere, not just in the blueprint.
    while IFS="$(printf '\t')" read -r src target; do
        [ -n "${src}" ] || continue
        if [ ! -f "${PLUGIN_ROOT}/${ADR_DIR}/${target}" ]; then
            error "${src} links ADR ${target}, which does not exist"
        fi
    done <<EOF
$(scan_adr_links)
EOF

    # An ADR cited by an ANSWERED blueprint question must not still be 'proposed'.
    while IFS= read -r target; do
        [ -n "${target}" ] || continue
        f="${PLUGIN_ROOT}/${ADR_DIR}/${target}"
        [ -f "${f}" ] || continue
        if [ "$(adr_status "${f}")" = "proposed" ]; then
            error "blueprint.md marks a question ANSWERED citing ${target}, but that ADR is still 'proposed'"
        fi
    done <<EOF
$(grep 'ANSWERED' "${PLUGIN_ROOT}/docs/blueprint.md" 2>/dev/null | grep -oE 'adr/[0-9]{4}-[A-Za-z0-9._-]+\.md' | sed 's|^adr/||' | sort -u || true)
EOF

    # ADR 0001 settled the independence decision; a reintroduction is a regression.
    while IFS="$(printf '\t')" read -r src lineno; do
        [ -n "${src}" ] || continue
        error "${src}:${lineno} cites a superseded DGF agent-tooling path — ADR 0001 settled that this plugin is independent"
    done <<EOF
$(scan_superseded_tooling)
EOF

    trace "scanned ${adr_count} decision record(s)"
}

# --- 5b. supersession integrity -----------------------------------------------
#
# docs/adr/README.md §"Supersession is always full" and §"Errata". A superseded
# ADR must point at a successor that points back, a blueprint answer must not
# rest on a superseded ADR, and the index must not disagree with the files.
BLUEPRINT='docs/blueprint.md'

adr_file_for_id() {
    find "${PLUGIN_ROOT}/${ADR_DIR}" -maxdepth 1 -type f -name "$1-*.md" 2>/dev/null | sort | head -1
}

# The ids in an ADR's `supersedes:` list, one per line. Only the inline form the
# existing ADRs use is accepted — [] / [0002] / [0002, 0003]. Anything else prints
# MALFORMED so the caller can report it rather than skip it silently.
adr_supersedes() {
    line="$(fm_value supersedes "$1")"
    [ -n "${line}" ] || return 0
    if ! printf '%s\n' "${line}" | grep -qE '^\[([0-9]{4}([[:space:]]*,[[:space:]]*[0-9]{4})*)?\][[:space:]]*$'; then
        printf 'MALFORMED\n'
        return 0
    fi
    printf '%s\n' "${line}" | grep -oE '[0-9]{4}' || true
}

# Index rows as target<TAB>status, from the third |-delimited column.
index_rows() {
    awk -F'|' '
        $2 ~ /\[[0-9][0-9][0-9][0-9]\]\([0-9][0-9][0-9][0-9]-[^)]*\.md\)/ {
            target = $2
            sub(/^.*\(/, "", target); sub(/\).*$/, "", target)
            status = $4
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", status)
            printf "%s\t%s\n", target, status
        }
    ' "$1"
}

# Errata entries that do not open with a date, as lineno<TAB>text.
undated_errata() {
    awk '
        /^## Errata[[:space:]]*$/ { grab = 1; next }
        grab && /^## / { exit }
        grab && /^- / && $0 !~ /^- (\*\*)?[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/ { printf "%d\t%s\n", NR, $0 }
    ' "$1"
}

check_successor_links() {
    file="$1"
    rel="$2"
    id="$3"
    status="$4"

    case "${status}" in
        superseded-by-[0-9][0-9][0-9][0-9]) : ;;
        *) return 0 ;;
    esac

    succ_id="${status#superseded-by-}"
    succ="$(adr_file_for_id "${succ_id}")"
    if [ -z "${succ}" ]; then
        error "${rel} is superseded-by-${succ_id}, but no ${ADR_DIR}/${succ_id}-*.md exists"
        return 0
    fi
    if ! adr_supersedes "${succ}" | grep -qx "${id}"; then
        error "${rel} is superseded-by-${succ_id}, but $(relpath "${succ}") does not list ${id} in 'supersedes'"
        return 0
    fi
    # A proposed ADR decides nothing, so it cannot replace a decision: the old one
    # would be retired with no live decision in its place.
    succ_status="$(adr_status "${succ}")"
    if [ "${succ_status}" = "proposed" ]; then
        error "${rel} is superseded-by-${succ_id}, but $(relpath "${succ}") is still 'proposed' — accept it first"
        return 0
    fi
    trace "${rel}: successor $(relpath "${succ}") lists ${id}"
}

check_predecessor_links() {
    file="$1"
    rel="$2"
    id="$3"

    ids="$(adr_supersedes "${file}")"
    if [ "${ids}" = "MALFORMED" ]; then
        error "${rel} has a 'supersedes' value that is not an inline list of 4-digit ids, e.g. [] or [0002]"
        return 0
    fi
    trace "${rel}: supersedes=[$(printf '%s' "${ids}" | tr '\n' ' ')]"

    while IFS= read -r old; do
        [ -n "${old}" ] || continue
        old_file="$(adr_file_for_id "${old}")"
        if [ -z "${old_file}" ]; then
            error "${rel} supersedes ${old}, but no ${ADR_DIR}/${old}-*.md exists"
            continue
        fi
        old_status="$(adr_status "${old_file}")"
        if [ "${old_status}" != "superseded-by-${id}" ]; then
            error "${rel} supersedes ${old}, but $(relpath "${old_file}") has status '${old_status}', not 'superseded-by-${id}'"
        fi
    done <<EOF
${ids}
EOF
}

check_adr_supersession() {
    section '5b. Supersession integrity'

    while IFS= read -r file; do
        [ -n "${file}" ] || continue
        rel="${ADR_DIR}/$(basename "${file}")"
        id="$(basename "${file}")"
        id="${id%%-*}"
        status="$(adr_status "${file}")"

        check_successor_links "${file}" "${rel}" "${id}" "${status}"
        check_predecessor_links "${file}" "${rel}" "${id}"

        while IFS="$(printf '\t')" read -r lineno text; do
            [ -n "${lineno}" ] || continue
            warn "${rel}:${lineno} Errata entry does not start with a YYYY-MM-DD date: ${text}"
        done <<EOF
$(undated_errata "${file}")
EOF
    done <<EOF
$(adr_files)
EOF

    # The index's Status column must match each ADR's frontmatter.
    index="${PLUGIN_ROOT}/${ADR_DIR}/README.md"
    while IFS="$(printf '\t')" read -r target cell; do
        [ -n "${target}" ] || continue
        f="${PLUGIN_ROOT}/${ADR_DIR}/${target}"
        [ -f "${f}" ] || continue
        actual="$(adr_status "${f}")"
        if [ "${cell}" != "${actual}" ]; then
            error "${ADR_DIR}/README.md lists ${target} as '${cell}', but its frontmatter status is '${actual}'"
        else
            trace "index row ${target}: status '${cell}' matches"
        fi
    done <<EOF
$(index_rows "${index}")
EOF

    # A blueprint answer must rest on a live decision, not a superseded one.
    while IFS=: read -r lineno text; do
        [ -n "${lineno}" ] || continue
        for target in $(printf '%s\n' "${text}" | grep -oE 'adr/[0-9]{4}-[A-Za-z0-9._-]+\.md' | sed 's|^adr/||' || true); do
            f="${PLUGIN_ROOT}/${ADR_DIR}/${target}"
            [ -f "${f}" ] || continue
            case "$(adr_status "${f}")" in
                superseded-by-*)
                    error "${BLUEPRINT}:${lineno} marks a question ANSWERED linking ${target}, which is $(adr_status "${f}") — link the successor" ;;
                *) trace "${BLUEPRINT}:${lineno} links live ADR ${target}" ;;
            esac
        done
    done <<EOF
$(grep -n 'ANSWERED' "${PLUGIN_ROOT}/${BLUEPRINT}" 2>/dev/null || true)
EOF
}


# --- 6. plugin manifest -------------------------------------------------------
#
# The structural checks are NOT reimplemented here. doctor.py owns them and the
# /dgf-doctor skill already calls it; duplicating them would give two
# implementations that drift apart. This section runs the doctor and adds only
# what is genuinely a documentation contract: that the reader-facing docs have
# stopped claiming the manifest does not exist.
DOCTOR='skills/dgf-doctor/scripts/doctor.py'

# Documents that described the pre-manifest state and had to be corrected.
MANIFEST_DOCS='
README.md
AGENTS.md
.ai-factory/DESCRIPTION.md
docs/getting-started.md
'

MANIFEST_WINDOW=2

# A stale claim is one of these phrases within MANIFEST_WINDOW lines of a
# plugin.json mention. Window-scoped for the same reason as check 1: the phrase
# and the filename routinely land on different lines, while file-scoped matching
# would flag any document that mentions both anywhere.
scan_stale_manifest_claims() {
    for rel in ${MANIFEST_DOCS}; do
        file="${PLUGIN_ROOT}/${rel}"
        [ -f "${file}" ] || continue
        awk -v rel="${rel}" -v win="${MANIFEST_WINDOW}" '
            { lines[NR] = tolower($0) }
            END {
                for (i = 1; i <= NR; i++) {
                    if (lines[i] !~ /not yet created|is not here yet|cannot be installed/) continue
                    for (j = i - win; j <= i + win; j++) {
                        if (j < 1 || j > NR) continue
                        if (lines[j] ~ /plugin\.json/) {
                            printf "%s\t%d\n", rel, i
                            break
                        }
                    }
                }
            }
        ' "${file}"
    done
}

check_plugin_manifest() {
    section '6. Plugin manifest'

    doctor_code=0
    # Capture the status directly, never through a pipe: `cmd | tail` would
    # report tail's exit code and turn every failure into a pass.
    doctor_output="$(python3 "${PLUGIN_ROOT}/${DOCTOR}" 2>&1)" || doctor_code=$?
    trace "ran ${DOCTOR} (exit ${doctor_code})"

    if [ "${doctor_code}" -ne 0 ]; then
        printf '%s\n' "${doctor_output}"
    fi

    case "${doctor_code}" in
        0) ;;
        2) warn "${DOCTOR} reported warnings (exit 2) — see its output above" ;;
        1) error "${DOCTOR} reported blocking findings (exit 1) — see its output above" ;;
        3) error "${DOCTOR} was invoked incorrectly (exit 3) — see its output above" ;;
        *) error "${DOCTOR} returned an unexpected exit code ${doctor_code}" ;;
    esac

    while IFS="$(printf '\t')" read -r rel lineno; do
        [ -n "${rel}" ] || continue
        error "${rel}:${lineno} still claims the plugin manifest does not exist"
    done <<EOF
$(scan_stale_manifest_claims)
EOF

    for rel in ${MANIFEST_DOCS}; do
        trace "scanned ${rel} for stale manifest claims"
    done
}


# --- 7. knowledge stamps ------------------------------------------------------
#
# Every knowledge/**/*.md except knowledge/README.md carries the stamp contract
# that README.md §1 defines: dgf_version, read_date and — when a range is
# declared — both since and until. Its sources, each with a sha256, are in a
# provenance ledger at the same path under provenance/ (ADR 0013), and the
# vendored schemas must match their recorded shipped digests. That frontmatter is
# nested (sources is a list of maps, applies is a map), and the only frontmatter
# parsing this script does is fm_value(), one flat key at a time. So the check
# lives in a Python helper and this section only invokes it, exactly as section 6
# does with doctor.py. One implementation; milestone 8's drift check is its
# second caller.
STAMPS='tools/check_knowledge_stamps.py'

check_knowledge_stamps() {
    section '7. Knowledge stamps'

    stamps_code=0
    # Capture the status directly, never through a pipe: `cmd | tail` would
    # report tail's exit code and turn every failure into a pass.
    stamps_output="$(python3 "${PLUGIN_ROOT}/${STAMPS}" 2>&1)" || stamps_code=$?
    trace "ran ${STAMPS} (exit ${stamps_code})"

    if [ "${stamps_code}" -ne 0 ]; then
        printf '%s\n' "${stamps_output}"
    fi

    case "${stamps_code}" in
        0) ;;
        2) warn "${STAMPS} reported warnings (exit 2) — see its output above" ;;
        1) error "${STAMPS} reported blocking findings (exit 1) — see its output above" ;;
        3) error "${STAMPS} was invoked incorrectly (exit 3) — see its output above" ;;
        *) error "${STAMPS} returned an unexpected exit code ${stamps_code}" ;;
    esac
}

main() {
    if [ "$#" -gt 0 ]; then
        fail 3 "Usage: $(basename "$0")   (no arguments; set DEBUG=1 for a per-file trace)"
    fi
    if [ ! -d "${PLUGIN_ROOT}/docs" ]; then
        fail 3 "Not a dgf-factory checkout: ${PLUGIN_ROOT}/docs not found"
    fi

    printf '%sDocumentation contract check%s\n' "${BOLD}" "${NC}"
    printf 'Root: %s\n' "${PLUGIN_ROOT}"

    # Each check appends to ERRORS / WARNINGS in this shell, so none of them may
    # run in a subshell — that is why the loops above read from here-docs rather
    # than from a pipe.
    check_stale_schema_source
    check_both_families
    check_reference_page
    check_absolute_paths
    check_decision_records
    check_adr_supersession
    check_plugin_manifest
    check_knowledge_stamps

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
