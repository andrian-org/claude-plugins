#!/usr/bin/env python3
"""check_drift.py — compare the provenance ledgers against a DGF checkout (ADR 0013 §4–5).

A repo-maintenance tool, not a runtime validator: maintainers run it when DGF
moves, to learn which knowledge files may no longer be true. It modifies
nothing. For every ledger under provenance/knowledge/ and every `sources` entry:

  DRIFT          the upstream file's sha256 in the checkout differs from the ledger's
  DRIFT_MISSING  the upstream file is gone from the checkout

Each names the ledger, the source path and the knowledge file it feeds. It also
reports, as INFO, the schema ledger's `dgf_commit` against the checkout's HEAD;
warns when the checkout's `<Version>` is not the stamps' `dgf_version`; and warns
when a cited file has uncommitted changes, since its digest may then reflect a
local edit.

The ledger parser is tools/check_knowledge_stamps.py's, loaded with importlib —
one implementation. Shipped-digest errors belong to that tool, so this one never
exits 1. Stdlib only.

Usage:  check_drift.py <dgf-root> [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — every cited file matches its ledger digest
  2  WARNINGS  — drift, a missing source, a version mismatch or local edits
  3  usage error — not a DGF root, or an unreadable ledger set
"""

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STAMPS = PLUGIN_ROOT / "tools" / "check_knowledge_stamps.py"
LEDGERS = PLUGIN_ROOT / "provenance"
SCHEMA_LEDGER = Path("knowledge") / "schemas" / "MANIFEST.md"
VERSION_SOURCE = Path("src") / "Directory.Build.props"
VERSION = re.compile(r"<Version>\s*([^<\s]+)\s*</Version>")

if sys.stdout.isatty():
    YELLOW, GREEN, BOLD, NC = "\033[0;33m", "\033[0;32m", "\033[1m", "\033[0m"
else:
    YELLOW = GREEN = BOLD = NC = ""

WARNINGS = 0


def fail(message):
    """The single bail-out path. Errors go to stderr, never to the report."""
    print(message, file=sys.stderr)
    raise SystemExit(3)


def warn(code, message):
    global WARNINGS
    WARNINGS += 1
    print(f"{YELLOW}WARN{NC}  {code} {message}")


def info(message):
    print(f"INFO  {message}")


def debug(message, **kv):
    if os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug":
        pairs = " ".join(f"{k}={v}" for k, v in kv.items())
        print(f"DEBUG [check_drift.{message}] {pairs}", file=sys.stderr)


def load_stamps():
    """tools/check_knowledge_stamps.py as a module: its parser, never a copy of it."""
    spec = importlib.util.spec_from_file_location("check_knowledge_stamps", STAMPS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="check_drift.py", description="Compare the ledgers against a DGF checkout.")
    parser.add_argument("dgf_root")
    parser.add_argument("--verbose", action="store_true", help="trace to stderr (same as DEBUG=1)")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        raise SystemExit(3)
    root = Path(args.dgf_root).expanduser().resolve()
    if not (root / VERSION_SOURCE).is_file():
        fail(f"Not a DGF repository root (no {VERSION_SOURCE.as_posix()}): {root}")
    if args.verbose:
        os.environ["DEBUG"] = "1"
    return root


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def ledgers(stamps):
    """[(ledger path relative to the plugin, knowledge file it feeds, parsed frontmatter)]."""
    found = []
    for path in sorted((LEDGERS / "knowledge").rglob("*.md")):
        lines = stamps.frontmatter_lines(path.read_text(encoding="utf-8"))
        if lines is None:
            fail(f"{path.relative_to(PLUGIN_ROOT)}: no closed frontmatter block — run check_knowledge_stamps.py")
        feeds = path.relative_to(LEDGERS).as_posix()
        found.append((path.relative_to(PLUGIN_ROOT).as_posix(), feeds, stamps.parse_frontmatter(lines)))
    if not found:
        fail(f"No ledgers under {LEDGERS / 'knowledge'}")
    return found


def check_sources(root, stamps, entries):
    """Warn for every cited file that drifted or is gone; return the cited paths."""
    cited = []
    for ledger, feeds, fm in entries:
        for source in fm["sources"]:
            path, expected = source.get("path"), source.get("sha256")
            if not path or not expected:
                continue
            cited.append(path)
            upstream = root / path
            actual = stamps.sha256_of(upstream) if upstream.is_file() else None
            debug("check_sources", ledger=ledger, path=path, expected=expected[:12], actual=(actual or "-")[:12])
            if actual is None:
                warn("DRIFT_MISSING", f"{ledger}: `{path}` is gone from the checkout — {feeds} cites it")
            elif actual != expected:
                warn("DRIFT", f"{ledger}: `{path}` changed (recorded {expected[:12]}, now {actual[:12]}) — "
                              f"re-read it for {feeds}")
    return cited


def check_commit(root, entries):
    recorded = next((fm["scalars"].get("dgf_commit") for ledger, feeds, fm in entries
                     if feeds == SCHEMA_LEDGER.as_posix()), None)
    head = (git(root, "rev-parse", "HEAD") or "").strip()
    if not recorded:
        info("the schema ledger records no dgf_commit")
    elif head == recorded:
        info(f"checkout HEAD is the schema ledger's dgf_commit {recorded[:12]}")
    else:
        info(f"checkout HEAD {head[:12] or 'unknown'} is not the schema ledger's dgf_commit {recorded[:12]}")


def check_version(root, stamps):
    match = VERSION.search((root / VERSION_SOURCE).read_text(encoding="utf-8"))
    checkout = match.group(1) if match else None
    stale = []
    for path in stamps.knowledge_files(PLUGIN_ROOT):
        lines = stamps.frontmatter_lines(path.read_text(encoding="utf-8"))
        version = stamps.parse_frontmatter(lines)["scalars"].get("dgf_version", "").strip('"') if lines else ""
        if version and version != checkout:
            stale.append(f"{path.relative_to(PLUGIN_ROOT).as_posix()} ({version})")
    if checkout is None:
        warn("VERSION_UNKNOWN", f"no <Version> in {VERSION_SOURCE.as_posix()}")
    elif stale:
        warn("VERSION_MISMATCH", f"the checkout is DGF {checkout}; stamped otherwise: {', '.join(stale)}")
    else:
        info(f"every stamp is dgf_version {checkout}, the checkout's")


def check_local_edits(root, cited):
    status = git(root, "status", "--porcelain", "--", *sorted(set(cited)))
    if status is None:
        info("not a git checkout — local edits cannot be ruled out")
        return
    edited = [line[3:] for line in status.splitlines() if line.strip()]
    if edited:
        warn("LOCAL_EDITS", f"{len(edited)} cited file(s) have uncommitted changes, so their digests may reflect "
                            f"local edits: {', '.join(edited[:5])}{' …' if len(edited) > 5 else ''}")


def main(argv):
    root = parse_args(argv)
    stamps = load_stamps()
    entries = ledgers(stamps)
    print(f"{BOLD}Provenance drift check{NC}")
    print(f"DGF: {root}")
    cited = check_sources(root, stamps, entries)
    check_commit(root, entries)
    check_version(root, stamps)
    check_local_edits(root, cited)
    print(f"\n{BOLD}Summary{NC}")
    print(f"Ledgers:  {len(entries)}")
    print(f"Sources:  {len(cited)}")
    print(f"Warnings: {WARNINGS}")
    print()
    if WARNINGS:
        print(f"{YELLOW}WARNINGS{NC}")
        return 2
    print(f"{GREEN}CLEAN{NC}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
