#!/usr/bin/env python3
"""check_knowledge_stamps.py — is every knowledge file stamped the way README.md says?

A repo-maintenance check, not a runtime validator: contributors run it (via
scripts/check-dual-schema-docs.sh section 7), skills do not. It reads and
reports; it never edits.

It exists because the stamp frontmatter is nested — `sources` is a list of
maps, `applies` is a map — and the only frontmatter parsing the shell script
does is one flat key. Asserting "every source has a digest" in awk is fragile
in exactly the way this check is meant to prevent.

Usage:  check_knowledge_stamps.py [<plugin-root>]
        DEBUG=1 check_knowledge_stamps.py          # per-file trace
        LOG_LEVEL=debug check_knowledge_stamps.py  # same trace

With no argument the plugin root is resolved from this file's location.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — every stamped file conforms
  1  BLOCKED   — a required stamp field is missing or malformed
  2  WARNINGS  — stamps conform but disagree with each other
  3  usage error

No dgf-gate-result block is emitted: this is not a skill-facing gate, and
milestone 10 owns the plugin-wide gate contract.
"""

import os
import re
import sys
from datetime import date
from pathlib import Path

# --- colours (defined once, disabled when not a terminal) --------------------
if sys.stdout.isatty():
    RED = "\033[0;31m"
    YELLOW = "\033[0;33m"
    GREEN = "\033[0;32m"
    BOLD = "\033[1m"
    NC = "\033[0m"
else:
    RED = YELLOW = GREEN = BOLD = NC = ""

EXEMPT = {"README.md"}  # describes the convention; is not itself a DGF fact

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
VERSION_PATTERN = re.compile(r'"\d+\.\d+\.\d+"\Z')
FLAT_KEY = re.compile(r"([A-Za-z_][\w-]*):\s*(.*)\Z")

ERRORS = 0
WARNINGS = 0


def fail(code, message):
    """The single bail-out path. Errors go to stderr, never to the report."""
    print(message, file=sys.stderr)
    raise SystemExit(code)


def error(summary):
    global ERRORS
    ERRORS += 1
    print(f"{RED}ERROR{NC} {summary}")


def warn(summary):
    global WARNINGS
    WARNINGS += 1
    print(f"{YELLOW}WARN{NC}  {summary}")


def trace(message):
    if os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug":
        print(f"  · {message}")


def section(title):
    print(f"\n{BOLD}{title}{NC}")


# --- frontmatter scanner -----------------------------------------------------
#
# Scoped to the shape README.md §1 defines: flat scalars at indent 0, a
# `sources` list of {path, sha256} maps, and an optional `applies` map. Not a
# YAML parser — depending on pyyaml would put a third-party import in a check
# that must run anywhere. Comment lines (`#`) are skipped at any indent.

def frontmatter_lines(text):
    """The lines strictly between the opening and closing `---`, or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return lines[1:index]
    return None  # unterminated block


def parse_frontmatter(lines):
    """Returns {scalars: {}, sources: [{}], applies: {}}."""
    result = {"scalars": {}, "sources": [], "applies": {}, "applies_declared": False}
    block = None  # which nested structure indented lines belong to
    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()
        if indent == 0:
            block = parse_top_level(body, result)
        elif block == "sources":
            parse_source_line(body, result["sources"])
        elif block == "applies":
            match = FLAT_KEY.match(body)
            if match:
                result["applies"][match.group(1)] = match.group(2)
    return result


def parse_top_level(body, result):
    match = FLAT_KEY.match(body)
    if not match:
        return None
    key, value = match.groups()
    if key in ("sources", "applies") and value == "":
        if key == "applies":
            result["applies_declared"] = True  # declared-but-empty must not pass as "no range"
        return key
    result["scalars"][key] = value
    return None


def parse_source_line(body, sources):
    if body == "-" or body.startswith("- "):  # both `- path: x` and a bare `-` open an item
        sources.append({})
        body = body[1:].strip()
    match = FLAT_KEY.match(body)
    if match and sources:
        sources[-1][match.group(1)] = match.group(2)


# --- checks ------------------------------------------------------------------

def valid_date(value):
    """A real calendar date in ISO form — `2026-13-45` has the right shape and is still wrong."""
    try:
        return bool(date.fromisoformat(value))
    except (TypeError, ValueError):
        return False


def knowledge_files(root):
    base = root / "knowledge"
    for path in sorted(base.rglob("*.md")):
        if path.relative_to(base).as_posix() not in EXEMPT:
            yield path


def check_required(rel, fm):
    scalars = fm["scalars"]
    if not scalars.get("dgf_version"):
        error(f"{rel}: missing `dgf_version`")
    elif not VERSION_PATTERN.match(scalars["dgf_version"]):
        error(f"{rel}: `dgf_version` must be a quoted semver string, got {scalars['dgf_version']}")
    read_date = scalars.get("read_date", "")
    if not read_date:
        error(f"{rel}: missing `read_date`")
    elif not valid_date(read_date):
        error(f"{rel}: `read_date` must be a real YYYY-MM-DD date, got {read_date}")
    review_date = scalars.get("review_date")
    if review_date is not None and not valid_date(review_date):
        error(f"{rel}: `review_date` must be a real YYYY-MM-DD date, got {review_date}")
    if not fm["sources"]:
        error(f"{rel}: `sources` is missing or empty — a fact with no source is a guess")


def check_sources(rel, sources):
    for index, entry in enumerate(sources, 1):
        path, digest = entry.get("path"), entry.get("sha256")
        if not path:
            error(f"{rel}: sources[{index}] has no `path`")
        if not digest:
            error(f"{rel}: sources[{index}] ({path or '?'}) has no `sha256` sibling")
        elif not SHA256_PATTERN.match(digest):
            error(f"{rel}: sources[{index}] ({path}) `sha256` is not a 64-hex digest")


def check_applies(rel, fm):
    """README.md §2.1: when a range is declared, both bounds are mandatory."""
    if not fm["applies_declared"]:
        return  # structural fact — no range, nothing to check
    applies = fm["applies"]
    if not applies:
        error(f"{rel}: `applies` is declared but empty — a range needs both `since` and `until`")
        return
    for key in ("since", "until"):
        value = applies.get(key)
        if value is None:
            error(f"{rel}: `applies` declares a range but has no `{key}`")
        elif value != "null" and not VERSION_PATTERN.match(value):
            error(f"{rel}: `applies.{key}` must be a quoted version or null, got {value}")


def check_version_agreement(versions):
    """One `dgf_version` across the tree; divergence is a re-vendor in progress."""
    distinct = sorted(set(versions.values()))
    if len(distinct) <= 1:
        trace(f"dgf_version agrees across {len(versions)} file(s): {distinct[0] if distinct else '—'}")
        return
    warn(f"`dgf_version` diverges across the tree: {', '.join(distinct)}")
    for rel, version in sorted(versions.items()):
        print(f"      {version}  {rel}")


# --- main --------------------------------------------------------------------

def resolve_root(argv):
    if len(argv) > 1:
        fail(3, f"Usage: {Path(argv[0]).name} [<plugin-root>]   (DEBUG=1 for a per-file trace)")
    if argv:
        root = Path(argv[0]).expanduser().resolve()
    else:
        try:
            root = Path(__file__).resolve().parents[1]  # scripts/ -> plugin root
        except IndexError:
            fail(3, "Cannot resolve the plugin root from this file's location; pass it explicitly")
    if not (root / "knowledge").is_dir():
        fail(3, f"No knowledge directory under {root}")
    return root


def check_files(root):
    """Runs the per-file rules; returns ({rel: dgf_version}, files checked)."""
    versions, checked = {}, 0
    for path in knowledge_files(root):
        rel = path.relative_to(root).as_posix()
        checked += 1
        lines = frontmatter_lines(path.read_text(encoding="utf-8"))
        if lines is None:
            error(f"{rel}: no closed frontmatter block")
            continue
        fm = parse_frontmatter(lines)
        trace(f"{rel}: {len(fm['sources'])} source(s), applies={'yes' if fm['applies'] else 'no'}")
        check_required(rel, fm)
        check_sources(rel, fm["sources"])
        check_applies(rel, fm)
        if fm["scalars"].get("dgf_version"):
            versions[rel] = fm["scalars"]["dgf_version"]
    return versions, checked


def main(argv):
    root = resolve_root(argv[1:])
    print(f"{BOLD}Knowledge stamp check{NC}")
    print(f"Root: {root}")

    section("1. Stamp contract per file")
    versions, checked = check_files(root)
    if checked == 0:
        warn("no stamped files found under knowledge/ — a clean tree and a broken glob look the same")

    section("2. Version agreement")
    check_version_agreement(versions)

    section("Summary")
    print(f"Files checked: {checked}")
    print(f"Errors:        {ERRORS}")
    print(f"Warnings:      {WARNINGS}")
    if ERRORS:
        print(f"\n{RED}BLOCKED{NC}")
        return 1
    if WARNINGS:
        print(f"\n{YELLOW}WARNINGS{NC}")
        return 2
    print(f"\n{GREEN}CLEAN{NC}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
