#!/usr/bin/env bash
# dgf_lines_watch.sh — the scheduled check that DGF moved past dgf-factory's knowledge packs (ADR 0036 §7).
#
# A maintainer tool, not shipped. cron or launchd runs it (docs/dgf-lines.md). It:
#
#   1. runs `tools/dgf_lines.py status <dgf-root> --fetch --json <cache>/last-status.json`;
#   2. exit 0 → logs "nothing to do" and stops;
#   3. exit 2 → logs every WARN line, and posts a desktop notification when it can;
#      with DGF_SYNC_AUTORUN=1 and `claude` on PATH, it also:
#        - adds a git worktree of this repository beside it, on a new branch chore/dgf-sync-<date>
#          from $DGF_SYNC_BASE (default: main), and
#        - runs `claude -p "/dgf-sync sync --all"` there, with DGF_ROOT set.
#      The sync's edits stay uncommitted in that worktree for a maintainer to review. This script never
#      commits, pushes or merges, and never touches the main working tree.
#
# One run at a time: a second run while a lock is held exits 3. Everything is logged with a timestamp to
# <cache>/watch.log, where <cache> is $DGF_LINES_CACHE (default $XDG_CACHE_HOME/dgf-factory/lines, or
# ~/.cache/dgf-factory/lines).
#
# Usage:  bash tools/dgf_lines_watch.sh <dgf-root>
#         DGF_SYNC_AUTORUN=1 bash tools/dgf_lines_watch.sh <dgf-root>
#         DEBUG=1 …                      # trace each step to the log and stderr
#
# Environment: DGF_SYNC_AUTORUN, DGF_SYNC_BASE, DGF_LINES_CACHE, DGF_LINES_NO_FETCH=1 (skip the fetch),
# DGF_LINES_TOOL (the status tool to run; tests point it at a stub).
#
# Exit codes (contract, see .ai-factory/rules/base.md):
#   0  CLEAN     — every pack is at its line's newest release
#   1  BLOCKED   — status failed, or the autorun could not start (its branch exists, worktree failed)
#   2  WARNINGS  — work is available (and, with autorun, a sync ran or was attempted)
#   3  usage error — bad argument, another run holds the lock
set -u

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="${DGF_LINES_TOOL:-${PLUGIN_ROOT}/tools/dgf_lines.py}"
CACHE="${DGF_LINES_CACHE:-${XDG_CACHE_HOME:-${HOME}/.cache}/dgf-factory/lines}"
LOG="${CACHE}/watch.log"
LOCK="${CACHE}/watch.lock"
STAMP="$(date +%Y-%m-%d)"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$1" | tee -a "${LOG}"
}
trace() {
    [ -n "${DEBUG:-}" ] && log "DEBUG [dgf_lines_watch] $1"
    return 0
}
fail() {
    log "ERROR $2"
    exit "$1"
}
notify() {
    if command -v osascript >/dev/null 2>&1; then
        osascript -e "display notification \"$1\" with title \"dgf-factory\"" >/dev/null 2>&1 || true
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send 'dgf-factory' "$1" >/dev/null 2>&1 || true
    fi
    trace "notified: $1"
}

[ "$#" -eq 1 ] || { printf 'Usage: %s <dgf-root>\n' "$(basename "$0")" >&2; exit 3; }
DGF_ROOT="$(cd "$1" 2>/dev/null && pwd)" || { printf 'No such folder: %s\n' "$1" >&2; exit 3; }
mkdir -p "${CACHE}" || { printf 'Cannot create %s\n' "${CACHE}" >&2; exit 3; }

if ! mkdir "${LOCK}" 2>/dev/null; then
    log "WARN  another run holds ${LOCK} — exiting"
    exit 3
fi
trap 'rmdir "${LOCK}" 2>/dev/null' EXIT

log "INFO  status of ${DGF_ROOT} against $(basename "$(dirname "${PLUGIN_ROOT}")")/$(basename "${PLUGIN_ROOT}")"
FETCH='--fetch'
[ -n "${DGF_LINES_NO_FETCH:-}" ] && FETCH=''
code=0
python3 "${TOOL}" status "${DGF_ROOT}" ${FETCH} --json "${CACHE}/last-status.json" > "${CACHE}/last-status.txt" 2>&1 || code=$?
trace "status exited ${code}; report ${CACHE}/last-status.json"

case "${code}" in
    0)
        log "INFO  CLEAN — every pack is at its line's newest release"
        exit 0
        ;;
    2) ;;
    *)
        cat "${CACHE}/last-status.txt" >> "${LOG}"
        fail 1 "dgf_lines.py status exited ${code} — see ${CACHE}/last-status.txt"
        ;;
esac

grep -E '^WARN ' "${CACHE}/last-status.txt" | while IFS= read -r line; do log "${line}"; done
summary="$(grep -cE '^WARN ' "${CACHE}/last-status.txt" || true) item(s) of DGF knowledge work available"
log "INFO  ${summary}"
notify "${summary} — see ${CACHE}/last-status.txt"

if [ "${DGF_SYNC_AUTORUN:-}" != "1" ]; then
    log "INFO  autorun is off (DGF_SYNC_AUTORUN=1 runs /dgf-sync in a worktree) — exiting"
    exit 2
fi
command -v claude >/dev/null 2>&1 || fail 1 "autorun asked, but \`claude\` is not on PATH"

REPO="$(git -C "${PLUGIN_ROOT}" rev-parse --show-toplevel 2>/dev/null)" || fail 1 "${PLUGIN_ROOT} is not in a git repository"
PREFIX="$(git -C "${PLUGIN_ROOT}" rev-parse --show-prefix)"
BASE="${DGF_SYNC_BASE:-main}"
BRANCH="chore/dgf-sync-${STAMP}"
WORKTREE="${REPO}-dgf-sync-${STAMP}"
if git -C "${REPO}" rev-parse --verify --quiet "refs/heads/${BRANCH}" >/dev/null; then
    fail 1 "${BRANCH} already exists — review or delete it first (git worktree remove ${WORKTREE}; git branch -D ${BRANCH})"
fi
git -C "${REPO}" worktree add --quiet -b "${BRANCH}" "${WORKTREE}" "${BASE}" >> "${LOG}" 2>&1 \
    || fail 1 "git worktree add ${WORKTREE} from ${BASE} failed — see ${LOG}"
log "INFO  worktree ${WORKTREE} on ${BRANCH} (from ${BASE})"

sync_code=0
(cd "${WORKTREE}/${PREFIX}" && DGF_ROOT="${DGF_ROOT}" claude -p "/dgf-sync sync --all" > "${CACHE}/last-sync.txt" 2>&1) || sync_code=$?
log "INFO  /dgf-sync exited ${sync_code}; its output is ${CACHE}/last-sync.txt"
log "INFO  review: cd ${WORKTREE} && git status — nothing was committed"
notify "dgf-sync ran on ${BRANCH} (exit ${sync_code}) — review ${WORKTREE}"
exit 2
