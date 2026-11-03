#!/usr/bin/env bash
# build_papers.sh — render the decision-maker papers under docs/papers/ to PDF.
#
# A maintainer tool, not shipped. Each docs/papers/<name>.md becomes docs/papers/<name>.pdf:
# pandoc renders standalone HTML with docs/papers/paper.css, and a headless Chrome or Chromium
# prints it to PDF. The Markdown is the source of truth; the PDF is rebuilt from it, never edited.
#
# Usage:  bash tools/build_papers.sh [<name> …]        # default: every docs/papers/*.md
#         CHROME=/path/to/chrome bash tools/build_papers.sh
#         DEBUG=1 bash tools/build_papers.sh           # keep the intermediate HTML, trace each step
#
# Exit codes (contract, see .ai-factory/rules/base.md):
#   0  CLEAN    — every paper rendered
#   1  BLOCKED  — a render failed; its output is above
#   3  usage error — pandoc or Chrome is missing, or a named paper does not exist
set -u

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAPERS="$PLUGIN_ROOT/docs/papers"
CSS="$PAPERS/paper.css"

fail() { printf 'FAIL  %s\n' "$2" >&2; exit "$1"; }
trace() { [ -n "${DEBUG:-}" ] && printf '  · %s\n' "$1" >&2; return 0; }

command -v pandoc >/dev/null 2>&1 || fail 3 'pandoc is not installed (brew install pandoc)'
find_chrome() {
    if [ -n "${CHROME:-}" ]; then printf '%s' "$CHROME"; return; fi
    for candidate in \
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
        "/Applications/Chromium.app/Contents/MacOS/Chromium" \
        "$(command -v google-chrome 2>/dev/null)" "$(command -v chromium 2>/dev/null)" "$(command -v chromium-browser 2>/dev/null)"; do
        [ -n "$candidate" ] && [ -x "$candidate" ] && { printf '%s' "$candidate"; return; }
    done
}
CHROME_BIN="$(find_chrome)"
[ -n "$CHROME_BIN" ] || fail 3 'no Chrome or Chromium found; set CHROME=/path/to/chrome'
[ -f "$CSS" ] || fail 3 "missing stylesheet: $CSS"

if [ "$#" -gt 0 ]; then names=("$@"); else
    names=()
    for md in "$PAPERS"/*.md; do [ -e "$md" ] && names+=("$(basename "$md" .md)"); done
fi
[ "${#names[@]}" -gt 0 ] || fail 3 "no papers under $PAPERS"

WORK="$(mktemp -d)"
[ -n "${DEBUG:-}" ] || trap 'rm -rf "$WORK"' EXIT
trace "work folder $WORK"

status=0
for name in "${names[@]}"; do
    src="$PAPERS/$name.md"
    [ -f "$src" ] || fail 3 "no such paper: $src"
    html="$WORK/$name.html"
    pdf="$PAPERS/$name.pdf"
    cp "$CSS" "$WORK/paper.css"
    if ! pandoc "$src" --standalone --from gfm+yaml_metadata_block --to html5 --css paper.css \
            --toc --toc-depth=2 --output "$html"; then
        printf 'ERROR %s — pandoc failed\n' "$name"; status=1; continue
    fi
    trace "rendered $html"
    if ! "$CHROME_BIN" --headless=new --disable-gpu --no-pdf-header-footer --no-sandbox \
            --print-to-pdf="$pdf" "file://$html" >"$WORK/$name.chrome.log" 2>&1 || [ ! -s "$pdf" ]; then
        cat "$WORK/$name.chrome.log" >&2
        printf 'ERROR %s — Chrome could not print the PDF\n' "$name"; status=1; continue
    fi
    printf 'PAPER %s → %s (%s bytes)\n' "$name" "docs/papers/$name.pdf" "$(wc -c < "$pdf" | tr -d ' ')"
done

if [ "$status" -eq 0 ]; then echo CLEAN; else echo BLOCKED; fi
exit "$status"
