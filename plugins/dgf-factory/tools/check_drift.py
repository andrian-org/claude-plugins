#!/usr/bin/env python3
"""check_drift.py — compare one knowledge pack's provenance ledgers against a DGF checkout (ADR 0036 §6).

A repo-maintenance tool, not a runtime validator: maintainers run it when DGF
moves, to learn which knowledge files may no longer be true. It modifies
nothing. It checks one pack — the current line's by default, another with
--pack X.Y (tools/packs.py says where its ledgers live). For every ledger of
that pack and every `sources` entry:

  DRIFT          the upstream file's sha256 in the checkout differs from the ledger's
  DRIFT_MISSING  the upstream file is gone from the checkout

Each names the ledger, the source path and the knowledge file it feeds. It also
reports, as INFO, the schema ledger's `dgf_commit` against the checkout's HEAD;
compares the checkout's exact release tag with the pack's `dgf_version` (ADR 0036
§1 — a pack is read at a tag, never from Directory.Build.props, whose
`<Version>` is printed as INFO only):

  VERSION_NOT_A_TAG  HEAD is at no release tag: an unreleased tree
  VERSION_MISMATCH   HEAD's tag is not the pack's dgf_version

and warns when a cited file has uncommitted changes, since its digest may then
reflect a local edit. A legacy pack (pinned to a commit, ADR 0036 §2) is compared
with its registry commit instead.

The ledger parser is tools/check_knowledge_stamps.py's, loaded with importlib —
one implementation. Shipped-digest errors belong to that tool, so this one never
exits 1. Stdlib only.

Usage:  check_drift.py <dgf-root> [--pack <X.Y>] [--verbose]

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
VERSION_SOURCE = Path("src") / "Directory.Build.props"  # the DGF root marker; its <Version> is INFO only
VERSION = re.compile(r"<Version>\s*([^<\s]+)\s*</Version>")
RELEASE_TAG = re.compile(r"^\d+\.\d+\.\d+$")

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


def load_packs():
    """tools/packs.py as a module: where each pack and its ledgers live."""
    spec = importlib.util.spec_from_file_location("packs_for_drift", PLUGIN_ROOT / "tools" / "packs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Pack:
    """The pack under check: its line, knowledge and ledger directories, and registry entries."""

    def __init__(self, line=None):
        packs = load_packs()
        try:
            shipped, maintainer, current = packs.load_registry(PLUGIN_ROOT)
        except packs.RegistryError as exc:
            fail(f"line registry: {exc}")
        self.line = line or current
        if self.line not in shipped:
            fail(f"--pack {self.line}: no such line in packs/lines.json ({', '.join(sorted(shipped))})")
        self.entry, self.maintainer = shipped[self.line], maintainer[self.line]
        self.knowledge = packs.pack_dir(self.line, PLUGIN_ROOT)
        self.ledgers = packs.ledger_dir(self.line, PLUGIN_ROOT)
        debug("pack", line=self.line, knowledge=self.knowledge, ledgers=self.ledgers,
              dgf_version=self.entry["dgf_version"], legacy=bool(self.entry.get("legacy")))


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="check_drift.py", description="Compare the ledgers against a DGF checkout.")
    parser.add_argument("dgf_root")
    parser.add_argument("--pack", metavar="X.Y", help="the pack's line (default: the current line)")
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
    return root, args.pack


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def ledgers(stamps, pack):
    """[(ledger path relative to the plugin, knowledge file it feeds, parsed frontmatter)]."""
    found = []
    for path in sorted(pack.ledgers.rglob("*.md")):
        lines = stamps.frontmatter_lines(path.read_text(encoding="utf-8"))
        if lines is None:
            fail(f"{path.relative_to(PLUGIN_ROOT)}: no closed frontmatter block — run check_knowledge_stamps.py")
        feeds = path.relative_to(LEDGERS).as_posix()
        found.append((path.relative_to(PLUGIN_ROOT).as_posix(), feeds, stamps.parse_frontmatter(lines)))
    if not found:
        fail(f"No ledgers under {pack.ledgers.relative_to(PLUGIN_ROOT)}")
    debug("ledgers", pack=pack.line, count=len(found))
    return found


def drift_findings(root, stamps, entries):
    """(cited paths, [(code, ledger, path, feeds, expected, actual)]) — the comparison, printed by no one.

    tools/dgf_lines.py status counts these per knowledge file; check_sources prints them.
    """
    cited, found = [], []
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
                found.append(("DRIFT_MISSING", ledger, path, feeds, expected, None))
            elif actual != expected:
                found.append(("DRIFT", ledger, path, feeds, expected, actual))
    return cited, found


def check_sources(root, stamps, entries):
    """Warn for every cited file that drifted or is gone; return the cited paths."""
    cited, found = drift_findings(root, stamps, entries)
    for code, ledger, path, feeds, expected, actual in found:
        if code == "DRIFT_MISSING":
            warn(code, f"{ledger}: `{path}` is gone from the checkout — {feeds} cites it")
        else:
            warn(code, f"{ledger}: `{path}` changed (recorded {expected[:12]}, now {actual[:12]}) — "
                       f"re-read it for {feeds}")
    return cited


def check_commit(root, entries):
    recorded = next((fm["scalars"].get("dgf_commit") for ledger, feeds, fm in entries
                     if feeds.endswith("schemas/MANIFEST.md")), None)
    head = (git(root, "rev-parse", "HEAD") or "").strip()
    if not recorded:
        info("the schema ledger records no dgf_commit")
    elif head == recorded:
        info(f"checkout HEAD is the schema ledger's dgf_commit {recorded[:12]}")
    else:
        info(f"checkout HEAD {head[:12] or 'unknown'} is not the schema ledger's dgf_commit {recorded[:12]}")


def release_tag(root):
    """The release tag at the checkout's HEAD (the highest, when several point at it), or None."""
    out = git(root, "tag", "--points-at", "HEAD") or ""
    tags = [tag.strip() for tag in out.splitlines() if RELEASE_TAG.match(tag.strip())]
    tags.sort(key=lambda tag: tuple(int(part) for part in tag.split(".")))
    debug("release_tag", tags=",".join(tags) or "-")
    return tags[-1] if tags else None


def check_version(root, stamps, pack):
    """ADR 0036 §1: the pack's dgf_version is the release tag it was read at."""
    props = VERSION.search((root / VERSION_SOURCE).read_text(encoding="utf-8"))
    info(f"PROPS_VERSION {VERSION_SOURCE.as_posix()} <Version> is {props.group(1) if props else 'absent'} "
         f"— not a release version; never a stamp (ADR 0036 §1)")
    expected = pack.entry["dgf_version"]
    head = (git(root, "rev-parse", "HEAD") or "").strip()
    if pack.entry.get("legacy"):
        pinned = pack.maintainer.get("commit", "")
        if head == pinned:
            info(f"pack {pack.line} is a legacy pin; HEAD is its commit {pinned[:12]}")
        else:
            warn("VERSION_MISMATCH", f"pack {pack.line} is a legacy pin at {pinned[:12]}; HEAD is {head[:12] or 'unknown'}")
        return
    tag = release_tag(root)
    stale = []
    for path in stamps.knowledge_files(PLUGIN_ROOT, pack.knowledge.relative_to(PLUGIN_ROOT).as_posix()):
        lines = stamps.frontmatter_lines(path.read_text(encoding="utf-8"))
        version = stamps.parse_frontmatter(lines)["scalars"].get("dgf_version", "").strip('"') if lines else ""
        if version and version != expected:
            stale.append(f"{path.relative_to(PLUGIN_ROOT).as_posix()} ({version})")
    if tag is None:
        warn("VERSION_NOT_A_TAG", f"HEAD {head[:12] or 'unknown'} is at no release tag — an unreleased tree; "
                                  f"pack {pack.line} was read at {expected}")
    elif tag != expected:
        warn("VERSION_MISMATCH", f"the checkout is at tag {tag}; pack {pack.line} was read at {expected}")
    else:
        info(f"the checkout is at tag {tag}, pack {pack.line}'s dgf_version")
    if stale:
        warn("VERSION_MISMATCH", f"stamped other than the registry's {expected}: {', '.join(stale)}")


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
    root, line = parse_args(argv)
    stamps = load_stamps()
    pack = Pack(line)
    entries = ledgers(stamps, pack)
    print(f"{BOLD}Provenance drift check{NC}")
    print(f"DGF:  {root}")
    print(f"Pack: {pack.line} — {pack.knowledge.relative_to(PLUGIN_ROOT).as_posix()}/ "
          f"(dgf_version {pack.entry['dgf_version']})")
    cited = check_sources(root, stamps, entries)
    check_commit(root, entries)
    check_version(root, stamps, pack)
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
