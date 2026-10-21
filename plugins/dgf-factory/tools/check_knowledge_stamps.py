#!/usr/bin/env python3
"""check_knowledge_stamps.py — is every knowledge file stamped, and sourced, the way README.md says?

A repo-maintenance check, not a runtime validator: contributors run it (via
tools/check-dual-schema-docs.sh section 7), skills do not. It reads and
reports; it never edits.

The contract is knowledge/README.md §1 and ADR 0013:
  - every knowledge file carries its stamp (`dgf_version`, `read_date`, and an
    `applies` range or `review_date` where its fact class needs one), and never
    a `sources` key — a shipped file carries no DGF paths (ADR 0012);
  - every knowledge file has exactly one provenance ledger at the same relative
    path under provenance/, and every ledger has its knowledge file;
  - each ledger lists its DGF sources, each with a 64-hex `sha256`;
  - the vendored schema set's ledger also names each shipped file (`vendored`)
    and its digest (`shipped_sha256`), and every shipped schema must match it —
    a mismatch is a hand edit to a vendored file.

It exists because the frontmatter is nested — `sources` is a list of maps,
`applies` is a map — and the only frontmatter parsing the shell script does is
one flat key. Asserting "every source has a digest" in awk is fragile in
exactly the way this check is meant to prevent.

Usage:  check_knowledge_stamps.py [<plugin-root>]
        DEBUG=1 check_knowledge_stamps.py          # per-file trace
        LOG_LEVEL=debug check_knowledge_stamps.py  # same trace

With no argument the plugin root is resolved from this file's location.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — every stamped file and ledger conforms
  1  BLOCKED   — a stamp or ledger field is missing or malformed, a ledger is
                 missing or orphaned, or a vendored schema was edited by hand
  2  WARNINGS  — stamps conform but disagree with each other
  3  usage error

No dgf-gate-result block is emitted: this is not a skill-facing gate, and
milestone 10 owns the plugin-wide gate contract.
"""

import hashlib
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
PROVENANCE = "provenance"  # maintainer-only ledgers, outside the shipped tree
SCHEMA_MANIFEST = "knowledge/schemas/MANIFEST.md"  # the vendored set's stamp

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
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
    result = {"scalars": {}, "sources": [], "applies": {}, "applies_declared": False,
              "sources_declared": False}
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
    if key == "sources":
        result["sources_declared"] = True  # any form — a shipped file may not carry one
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
    if fm["sources_declared"]:
        error(f"{rel}: `sources` belongs in {PROVENANCE}/{rel}, not in a shipped file (ADR 0013)")


def check_sources(rel, sources):
    for index, entry in enumerate(sources, 1):
        path, digest = entry.get("path"), entry.get("sha256")
        if not path:
            error(f"{rel}: sources[{index}] has no `path`")
        if not digest:
            error(f"{rel}: sources[{index}] ({path or '?'}) has no `sha256` sibling")
        elif not SHA256_PATTERN.match(digest):
            error(f"{rel}: sources[{index}] ({path}) `sha256` is not a 64-hex digest")
        shipped = entry.get("shipped_sha256")
        if entry.get("vendored") and not shipped:
            error(f"{rel}: sources[{index}] ({path}) names a `vendored` file but no `shipped_sha256`")
        elif shipped and not SHA256_PATTERN.match(shipped):
            error(f"{rel}: sources[{index}] ({path}) `shipped_sha256` is not a 64-hex digest")


def read_frontmatter(root, path):
    """(rel, parsed frontmatter) — or (rel, None) after reporting why it is unusable."""
    rel = path.relative_to(root).as_posix()
    lines = frontmatter_lines(path.read_text(encoding="utf-8"))
    if lines is None:
        error(f"{rel}: no closed frontmatter block")
        return rel, None
    return rel, parse_frontmatter(lines)


def check_ledger(root, knowledge_rel):
    """ADR 0013 §1: one ledger per knowledge file, same relative path under provenance/."""
    ledger = root / PROVENANCE / knowledge_rel
    if not ledger.is_file():
        error(f"{knowledge_rel}: no provenance ledger at {PROVENANCE}/{knowledge_rel}")
        return None
    rel, fm = read_frontmatter(root, ledger)
    if fm is None:
        return None
    if not fm["sources"]:
        error(f"{rel}: `sources` is missing or empty — a fact with no source is a guess")
    check_sources(rel, fm["sources"])
    commit = fm["scalars"].get("dgf_commit")
    if commit is not None and not COMMIT_PATTERN.match(commit):
        error(f"{rel}: `dgf_commit` must be a 40-hex commit SHA, got {commit}")
    trace(f"{rel}: {len(fm['sources'])} source(s)")
    return fm


def check_orphan_ledgers(root, knowledge_rels):
    """A ledger with no knowledge file records the provenance of nothing."""
    base = root / PROVENANCE
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*.md")):
        rel = path.relative_to(base).as_posix()
        if rel not in knowledge_rels:
            error(f"{PROVENANCE}/{rel}: ledger has no knowledge file at {rel}")


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_vendored(root, fm):
    """Every shipped schema is listed in the schema ledger, and matches its shipped digest."""
    rel = f"{PROVENANCE}/{SCHEMA_MANIFEST}"
    base = (root / SCHEMA_MANIFEST).parent
    if not fm["scalars"].get("dgf_commit"):
        error(f"{rel}: no `dgf_commit` — the vendored set's position in DGF is unrecorded")
    listed = set()
    for index, entry in enumerate(fm["sources"], 1):
        vendored = entry.get("vendored")
        if not vendored:
            error(f"{rel}: sources[{index}] ({entry.get('path', '?')}) has no `vendored` path")
            continue
        listed.add(vendored)
        path = base / vendored
        if not path.is_file():
            error(f"{rel}: sources[{index}] names knowledge/schemas/{vendored}, which does not exist")
        elif entry.get("shipped_sha256") and sha256_of(path) != entry["shipped_sha256"]:
            error(f"knowledge/schemas/{vendored}: does not match its recorded `shipped_sha256` — "
                  "a vendored file was edited by hand; re-vendor with tools/vendor_schemas.py")
    for path in sorted(base.rglob("*")):
        vendored = path.relative_to(base).as_posix()
        if path.is_file() and path != root / SCHEMA_MANIFEST and vendored not in listed:
            error(f"knowledge/schemas/{vendored}: vendored file has no entry in {rel}")
    trace(f"{rel}: {len(listed)} vendored file(s) checked against their shipped digests")


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
            root = Path(__file__).resolve().parents[1]  # tools/ -> plugin root
        except IndexError:
            fail(3, "Cannot resolve the plugin root from this file's location; pass it explicitly")
    if not (root / "knowledge").is_dir():
        fail(3, f"No knowledge directory under {root}")
    return root


def check_files(root):
    """Runs the per-file rules; returns ({rel: dgf_version}, {rel: ledger}, files checked)."""
    versions, ledgers, checked = {}, {}, 0
    for path in knowledge_files(root):
        rel, fm = read_frontmatter(root, path)
        checked += 1
        if fm is None:
            continue
        trace(f"{rel}: applies={'yes' if fm['applies'] else 'no'}")
        check_required(rel, fm)
        check_applies(rel, fm)
        if fm["scalars"].get("dgf_version"):
            versions[rel] = fm["scalars"]["dgf_version"]
        ledgers[rel] = None
    return versions, ledgers, checked


def main(argv):
    root = resolve_root(argv[1:])
    print(f"{BOLD}Knowledge stamp check{NC}")
    print(f"Root: {root}")

    section("1. Stamp contract per file")
    versions, ledgers, checked = check_files(root)
    if checked == 0:
        warn("no stamped files found under knowledge/ — a clean tree and a broken glob look the same")

    section("2. Provenance ledgers")
    for rel in ledgers:
        ledgers[rel] = check_ledger(root, rel)
    check_orphan_ledgers(root, set(ledgers))

    section("3. Vendored schema digests")
    if ledgers.get(SCHEMA_MANIFEST):
        check_vendored(root, ledgers[SCHEMA_MANIFEST])
    else:
        trace(f"skipped — no usable ledger for {SCHEMA_MANIFEST}")

    section("4. Version agreement")
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
