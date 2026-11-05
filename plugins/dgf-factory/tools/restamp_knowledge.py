#!/usr/bin/env python3
"""restamp_knowledge.py — re-digest a pack's ledgers after its facts were re-read at a release tag (ADR 0036 §1).

A repo-maintenance tool, not shipped. After a maintainer (or /dgf-sync) re-read the
facts of one or more knowledge files against a DGF checkout at an exact release
tag, this tool records that read:

  - every `sources` digest in each named file's ledger is recomputed from the checkout;
  - the knowledge file's stamp becomes `dgf_version: "<tag>"` and `read_date: <date>`;
  - --add-source <dgf-path> appends a source to the (single) named file's ledger;
  - --all restamps every fact file of the pack, and then records the pack itself in
    both registries: packs/lines.json (`dgf_version`, `read_date`, no `legacy`) and
    provenance/lines.json (`tag`, `commit`, no `legacy`).

It never edits a fact. The vendored schema set is vendor_schemas.py's: its manifest is
refused here, and --all requires the schema ledger to be at this tag already.

It refuses (exit 1):
  - a checkout whose HEAD is not exactly a release tag, or a tag on another line;
  - a cited source missing from the checkout, or with uncommitted changes there;
  - --all while the schema ledger's `dgf_tag` is not this tag (vendor first).

Usage:  restamp_knowledge.py <dgf-checkout> --pack <X.Y> (<knowledge-file>… | --all)
                             [--add-source <dgf-path>]… [--read-date YYYY-MM-DD] [--dry-run] [--verbose]

A knowledge file is named relative to its pack: `schema-families.md`.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — restamped; or, with --dry-run, nothing would change
  1  BLOCKED   — refused, nothing written
  2  WARNINGS  — --dry-run only: files would change
  3  usage error
"""

import argparse
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TOOLS = PLUGIN_ROOT / "tools"
RELEASE_TAG = re.compile(r"^\d+\.\d+\.\d+$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCHEMA_MANIFEST = "schemas/MANIFEST.md"
PATH_LINE = re.compile(r"^(\s*-\s+path:\s*)(\S.*?)\s*$")
SHA_LINE = re.compile(r"^(\s*sha256:\s*)([0-9a-f]+)\s*$")
EXIT_CLEAN, EXIT_BLOCKED, EXIT_WARNINGS, EXIT_USAGE = 0, 1, 2, 3

if sys.stdout.isatty():
    RED, YELLOW, GREEN, BOLD, NC = "\033[0;31m", "\033[0;33m", "\033[0;32m", "\033[1m", "\033[0m"
else:
    RED = YELLOW = GREEN = BOLD = NC = ""

ERRORS = 0


def fail(code, message):
    print(message, file=sys.stderr)
    raise SystemExit(code)


def error(message):
    global ERRORS
    ERRORS += 1
    print(f"{RED}ERROR{NC} {message}")


def debug(event, **kv):
    if os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug":
        pairs = " ".join(f"{k}={v}" for k, v in kv.items())
        print(f"DEBUG [restamp.{event}] {pairs}", file=sys.stderr)


def load_tool(name):
    spec = importlib.util.spec_from_file_location(f"{name}_for_restamp", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packs = load_tool("packs")
stamps = load_tool("check_knowledge_stamps")


def git(root, *args):
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="restamp_knowledge.py", description="Re-digest a pack's ledgers at a tag.")
    parser.add_argument("checkout")
    parser.add_argument("files", nargs="*")
    parser.add_argument("--pack", required=True)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--add-source", action="append", default=[])
    parser.add_argument("--read-date", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    try:
        args = parser.parse_intermixed_args(argv)
    except SystemExit as exc:
        raise SystemExit(EXIT_USAGE if exc.code else EXIT_CLEAN)
    if args.verbose:
        os.environ["DEBUG"] = "1"
    if bool(args.files) == args.all:
        fail(EXIT_USAGE, "name the knowledge files to restamp, or pass --all — not both, not neither")
    if args.add_source and len(args.files) != 1:
        fail(EXIT_USAGE, "--add-source needs exactly one knowledge file")
    if not ISO_DATE.match(args.read_date):
        fail(EXIT_USAGE, f"--read-date {args.read_date} is not YYYY-MM-DD")
    args.checkout = Path(args.checkout).expanduser().resolve()
    if not args.checkout.is_dir():
        fail(EXIT_USAGE, f"no checkout at {args.checkout}")
    return args


def checkout_tag(checkout, line):
    """(tag, commit) at HEAD; refuses an untagged HEAD or a tag on another line."""
    head = (git(checkout, "rev-parse", "HEAD") or "").strip()
    tags = sorted((t.strip() for t in (git(checkout, "tag", "--points-at", "HEAD") or "").splitlines()
                   if RELEASE_TAG.match(t.strip())), key=lambda t: tuple(int(p) for p in t.split(".")))
    debug("checkout", head=head[:12], tags=",".join(tags) or "-")
    if not head:
        fail(EXIT_BLOCKED, f"{checkout} is not a git checkout")
    if not tags:
        fail(EXIT_BLOCKED, f"HEAD {head[:12]} is at no release tag — a pack is read only at one (ADR 0036 §1); "
                           f"use tools/dgf_lines.py checkout")
    tag = tags[-1]
    if packs.line_of(tag) != line:
        fail(EXIT_BLOCKED, f"HEAD is at tag {tag}, which is not on line {line}")
    return tag, head


def pack_files(pack_dir, names, all_files):
    """[(knowledge rel inside the pack, path)] to restamp."""
    if all_files:
        found = [p for p in sorted(pack_dir.rglob("*.md")) if p.name != "README.md"]
        return [(p.relative_to(pack_dir).as_posix(), p) for p in found
                if p.relative_to(pack_dir).as_posix() != SCHEMA_MANIFEST]
    chosen = []
    for name in names:
        rel = Path(name).as_posix()
        if rel == SCHEMA_MANIFEST:
            fail(EXIT_USAGE, f"{rel} is vendor_schemas.py's to stamp — run it with --pack")
        if rel == "README.md" or not (pack_dir / rel).is_file():
            fail(EXIT_USAGE, f"{rel}: not a stamped knowledge file in {pack_dir.relative_to(PLUGIN_ROOT)}/")
        chosen.append((rel, pack_dir / rel))
    return chosen


def restamped_ledger(text, checkout, add_sources, ledger_rel):
    """(new ledger text, [(path, old, new)]) with every digest recomputed; errors for missing sources."""
    lines = text.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        fail(EXIT_USAGE, f"{ledger_rel}: no closed frontmatter block")
    end = lines.index("---", 1)
    changes, current = [], None
    for index in range(1, end):
        path_match, sha_match = PATH_LINE.match(lines[index]), SHA_LINE.match(lines[index])
        if path_match:
            current = path_match.group(2)
        elif sha_match and current:
            new = digest(checkout, current, ledger_rel)
            if new and new != sha_match.group(2):
                changes.append((current, sha_match.group(2), new))
                lines[index] = f"{sha_match.group(1)}{new}"
            current = None
    existing = {m.group(2) for m in (PATH_LINE.match(line) for line in lines[1:end]) if m}
    for path in add_sources:
        if path in existing:
            error(f"{ledger_rel}: `{path}` is already a source")
            continue
        new = digest(checkout, path, ledger_rel)
        if new:
            lines[end:end] = [f"  - path: {path}", f"    sha256: {new}"]
            end += 2
            changes.append((path, None, new))
    return "\n".join(lines), changes


def digest(checkout, path, ledger_rel):
    upstream = checkout / path
    if not upstream.is_file():
        error(f"{ledger_rel}: `{path}` is not in the checkout — re-read the fact and edit the ledger by hand")
        return None
    if (git(checkout, "status", "--porcelain", "--", path) or "").strip():
        error(f"{ledger_rel}: `{path}` has uncommitted changes in the checkout")
        return None
    return hashlib.sha256(upstream.read_bytes()).hexdigest()


def restamped_fact(text, tag, read_date):
    text = re.sub(r'(?m)^dgf_version: .*$', f'dgf_version: "{tag}"', text, count=1)
    return re.sub(r"(?m)^read_date: .*$", f"read_date: {read_date}", text, count=1)


def schema_ledger_tag(ledger_dir):
    path = ledger_dir / SCHEMA_MANIFEST
    lines = stamps.frontmatter_lines(path.read_text(encoding="utf-8")) if path.is_file() else None
    return stamps.parse_frontmatter(lines)["scalars"].get("dgf_tag") if lines else None


def update_registries(line, tag, commit, read_date, dry_run):
    import json
    ship = json.loads((PLUGIN_ROOT / packs.SHIPPED_REGISTRY).read_text(encoding="utf-8"))
    maint = json.loads((PLUGIN_ROOT / packs.MAINTAINER_REGISTRY).read_text(encoding="utf-8"))
    for entry in ship["lines"]:
        if entry["line"] == line:
            entry["dgf_version"], entry["read_date"] = tag, read_date
            entry.pop("legacy", None)
    entry = maint["lines"][line]
    entry["tag"], entry["commit"] = tag, commit
    entry.pop("legacy", None)
    print(f"registries: line {line} → dgf_version {tag}, commit {commit[:12]}, read_date {read_date}")
    if not dry_run:
        packs.write_json(PLUGIN_ROOT, packs.SHIPPED_REGISTRY, ship)
        packs.write_json(PLUGIN_ROOT, packs.MAINTAINER_REGISTRY, maint)


def newest_read_date(pack_dir, planned):
    dates = []
    for path in pack_dir.rglob("*.md"):
        if path.name == "README.md":
            continue
        text = planned.get(path) or path.read_text(encoding="utf-8")
        match = re.search(r"(?m)^read_date: (\d{4}-\d{2}-\d{2})$", text)
        if match:
            dates.append(match.group(1))
    return max(dates)


def main(argv):
    args = parse_args(argv)
    try:
        pack_dir, ledger_dir = packs.pack_dir(args.pack), packs.ledger_dir(args.pack)
    except packs.RegistryError as exc:
        fail(EXIT_USAGE, f"line registry: {exc}")
    tag, commit = checkout_tag(args.checkout, args.pack)
    print(f"{BOLD}Restamp knowledge{' (dry run)' if args.dry_run else ''}{NC}")
    print(f"Checkout: {args.checkout} @ {tag} ({commit[:12]})")
    print(f"Pack:     {args.pack} — {pack_dir.relative_to(PLUGIN_ROOT).as_posix()}/")
    if args.all and schema_ledger_tag(ledger_dir) != tag:
        fail(EXIT_BLOCKED, f"the schema ledger is at {schema_ledger_tag(ledger_dir) or 'no tag'}, not {tag} — "
                           f"run tools/vendor_schemas.py {args.checkout} --pack {args.pack} first")
    planned, changed = {}, 0
    for rel, path in pack_files(pack_dir, args.files, args.all):
        ledger = ledger_dir / rel
        ledger_rel = ledger.relative_to(PLUGIN_ROOT).as_posix()
        if not ledger.is_file():
            error(f"{ledger_rel}: no ledger for {rel}")
            continue
        new_ledger, changes = restamped_ledger(ledger.read_text(encoding="utf-8"), args.checkout,
                                               args.add_source, ledger_rel)
        new_fact = restamped_fact(path.read_text(encoding="utf-8"), tag, args.read_date)
        for source, old, new in changes:
            debug("source", path=source, old=(old or "-")[:12], new=new[:12])
        print(f"  {rel}: {len(changes)} digest(s) changed, stamped {tag} / {args.read_date}")
        planned[ledger], planned[path] = new_ledger, new_fact
        changed += bool(changes) or new_fact != path.read_text(encoding="utf-8")
    if ERRORS:
        print(f"\n{RED}BLOCKED{NC} — nothing was written")
        return EXIT_BLOCKED
    if not args.dry_run:
        for target, text in planned.items():
            target.write_text(text, encoding="utf-8")
    if args.all:
        update_registries(args.pack, tag, commit, newest_read_date(pack_dir, planned), args.dry_run)
    if args.dry_run:
        print(f"\n{YELLOW if changed else GREEN}{'WARNINGS — would change' if changed else 'CLEAN'}{NC}")
        return EXIT_WARNINGS if changed else EXIT_CLEAN
    print(f"\n{GREEN}CLEAN{NC} — {len(planned) // 2} file(s) restamped")
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
