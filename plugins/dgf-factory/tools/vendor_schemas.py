#!/usr/bin/env python3
"""vendor_schemas.py — copy DGF's schema set into knowledge/schemas/, with DGF paths rewritten.

A repo-maintenance tool, not a runtime validator: maintainers run it, skills do
not. It is the re-vendor step of provenance/knowledge/schemas/MANIFEST.md §4, and
the only writer of that ledger's frontmatter.

What it does, in order:
  1. Refuses a DGF tree with uncommitted changes under the schema folders — the
     commit it records would not describe the files it copied.
  2. Reads and digests every upstream schema file in UPSTREAM_SETS.
  3. Rewrites DGF repository paths in the text (ADR 0012 §4):
       docs/wiki/<page>     -> get_doc_page('<page>')
       any other DGF path   -> its file name
     and refuses to write if a DGF path survives, or a rewritten file stops parsing.
  4. Writes the shipped copies, removes vendored files that are no longer
     upstream, regenerates the ledger's frontmatter and restamps the shipped
     manifest.

Usage:  vendor_schemas.py <dgf-root> [--dry-run] [--read-date YYYY-MM-DD]
        DEBUG=1 vendor_schemas.py <dgf-root> --dry-run   # per-file trace

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — written; or, with --dry-run, nothing would change
  1  BLOCKED   — refused: dirty DGF tree, a surviving DGF path, or a broken rewrite
  2  WARNINGS  — --dry-run only: the vendored set would change
  3  usage error
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
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

PLUGIN_ROOT = Path(__file__).resolve().parents[1]  # tools/ -> plugin root
VENDORED_ROOT = PLUGIN_ROOT / "knowledge" / "schemas"
SHIPPED_MANIFEST = VENDORED_ROOT / "MANIFEST.md"
LEDGER = PLUGIN_ROOT / "provenance" / "knowledge" / "schemas" / "MANIFEST.md"
DOCTOR = PLUGIN_ROOT / "skills" / "dgf-doctor" / "scripts" / "doctor.py"

# (vendored directory, upstream directory, glob). Non-recursive: Schemas/XSD/
# also holds fixtures and scripts that are not schemas.
UPSTREAM_SETS = (
    ("json", "src/Tools/dgf-mcp/Schemas/Json", "*.schema.json"),
    ("xsd", "src/Tools/dgf-mcp/Schemas/XSD", "*.xsd"),
    ("xsd", "src/Tools/dgf-mcp/Schemas/XmlReference", "form.reference.json"),
    ("standalone", "docs/schemas", "*.schema.json"),
)
DIR_ORDER = ("json", "xsd", "standalone")  # the ledger lists entries in this order
STANDALONE_COMMENT = "  # hand-authored standalone contract, not the generated set"
VERSION_SOURCE = "src/Directory.Build.props"

WIKI_LINK = re.compile(r"(?:(?<![\w.-])|(?<=\\[nrt]))docs/wiki/([A-Za-z0-9_./-]+?\.md)")
PATH_TAIL = r"[A-Za-z0-9_./-]*"
SHA_LINE = re.compile(r"\s*(?:-\s+)?(path|sha256):\s*(.+?)\s*\Z")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")

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


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# --- inputs ------------------------------------------------------------------

def parse_args(argv):
    usage = f"Usage: {Path(argv[0]).name} <dgf-root> [--dry-run] [--read-date YYYY-MM-DD]"
    args = argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    read_date = date.today().isoformat()
    if "--read-date" in args:
        index = args.index("--read-date")
        if index + 1 >= len(args) or not ISO_DATE.match(args[index + 1]):
            fail(3, usage)
        read_date = args[index + 1]
        del args[index:index + 2]
    if len(args) != 1:
        fail(3, usage)
    dgf_root = Path(args[0]).expanduser().resolve()
    if not (dgf_root / VERSION_SOURCE).is_file():
        fail(3, f"Not a DGF repository root (no {VERSION_SOURCE}): {dgf_root}")
    return dgf_root, dry_run, read_date


def load_dgf_path_pattern():
    """doctor.py's pattern, so the doctor and this tool agree on what a DGF path is."""
    spec = importlib.util.spec_from_file_location("doctor", DOCTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DGF_PATH_PATTERN


def git(dgf_root, *args):
    try:
        result = subprocess.run(["git", "-C", str(dgf_root), *args],
                                capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        fail(3, f"git {' '.join(args)} failed in {dgf_root}: {exc}")
    return result.stdout


def dgf_version(dgf_root):
    text = (dgf_root / VERSION_SOURCE).read_text(encoding="utf-8")
    match = re.search(r"<Version>\s*([^<\s]+)\s*</Version>", text)
    if not match:
        fail(3, f"No <Version> in {VERSION_SOURCE}")
    return match.group(1)


def upstream_files(dgf_root):
    """[(vendored rel path, upstream rel path, absolute path)] in ledger order."""
    found = []
    for vendored_dir, upstream_dir, glob in UPSTREAM_SETS:
        for path in (dgf_root / upstream_dir).glob(glob):
            if path.is_file():
                found.append((f"{vendored_dir}/{path.name}", f"{upstream_dir}/{path.name}", path))
    found.sort(key=lambda entry: (DIR_ORDER.index(entry[0].split("/")[0]), entry[0]))
    return found


def previous_digests():
    """{upstream path: sha256} from the ledger as it stands, for the drift report."""
    digests, current = {}, None
    for line in split_frontmatter(LEDGER.read_text(encoding="utf-8"))[0]:
        match = SHA_LINE.match(line)
        if not match:
            continue
        key, value = match.groups()
        if key == "path":
            current = value
        elif current is not None:
            digests[current] = value
            current = None
    return digests


def split_frontmatter(text):
    """(frontmatter lines, body) — the body is everything after the closing fence."""
    lines = text.split("\n")
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        fail(3, f"{LEDGER.relative_to(PLUGIN_ROOT)} has no closed frontmatter block")
    end = lines.index("---", 1)
    return lines[1:end], "\n".join(lines[end + 1:])


# --- the rewrite -------------------------------------------------------------

def rewrite(text, dgf_path):
    """(new text, rewrite count). Wiki links first, so they keep their page name."""
    count = 0

    def to_page(match):
        nonlocal count
        count += 1
        return f"get_doc_page('{match.group(1)}')"

    def to_file_name(match):
        nonlocal count
        count += 1
        return match.group(0).rstrip("/").rsplit("/", 1)[-1]

    text = WIKI_LINK.sub(to_page, text)
    text = re.sub(f"(?:{dgf_path.pattern}){PATH_TAIL}", to_file_name, text)
    return text, count


def parses(rel, data):
    try:
        if rel.endswith(".json"):
            json.loads(data.decode("utf-8"))
        else:
            ET.fromstring(data)
        return True
    except (ValueError, ET.ParseError):
        return False


def vendor_one(rel, data, dgf_path):
    """The shipped bytes for one upstream file, or None when the rewrite is refused."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        error(f"{rel}: upstream file is not UTF-8 — cannot rewrite it safely")
        return None
    new_text, count = rewrite(text, dgf_path)
    if count == 0:
        return data  # untouched: shipped bytes are the upstream bytes exactly
    shipped = new_text.encode("utf-8")
    for lineno, line in enumerate(new_text.splitlines(), 1):
        survivor = dgf_path.search(line)
        if survivor:
            error(f"{rel}:{lineno}: DGF path `{survivor.group(0)}…` survives the rewrite — add a rule")
            return None
    if parses(rel, data) and not parses(rel, shipped):
        error(f"{rel}: the rewrite broke it — it parsed upstream and does not parse now")
        return None
    trace(f"{rel}: {count} path(s) rewritten")
    return shipped


# --- outputs -----------------------------------------------------------------

def ledger_text(commit, entries):
    lines = ["---", f"dgf_commit: {commit}", "sources:"]
    for vendored, upstream, upstream_sha, shipped_sha in entries:
        if vendored.startswith("standalone/"):
            lines.append(STANDALONE_COMMENT)
        lines += [f"  - path: {upstream}", f"    sha256: {upstream_sha}",
                  f"    vendored: {vendored}", f"    shipped_sha256: {shipped_sha}"]
    lines.append("---")
    _, body = split_frontmatter(LEDGER.read_text(encoding="utf-8"))
    return "\n".join(lines) + "\n" + body


def restamped_manifest(version, read_date):
    text = SHIPPED_MANIFEST.read_text(encoding="utf-8")
    text = re.sub(r'(?m)^dgf_version: .*$', f'dgf_version: "{version}"', text, count=1)
    return re.sub(r"(?m)^read_date: .*$", f"read_date: {read_date}", text, count=1)


def stale_vendored(keep):
    for vendored_dir in DIR_ORDER:
        for path in sorted((VENDORED_ROOT / vendored_dir).glob("*")):
            rel = f"{vendored_dir}/{path.name}"
            if path.is_file() and rel not in keep:
                yield rel, path


# --- main --------------------------------------------------------------------

def main(argv):
    dgf_root, dry_run, read_date = parse_args(argv)
    dgf_path = load_dgf_path_pattern()
    print(f"{BOLD}Vendor DGF schemas{' (dry run)' if dry_run else ''}{NC}")
    print(f"DGF:    {dgf_root}")
    print(f"Plugin: {PLUGIN_ROOT}")

    section("1. Upstream state")
    dirty = git(dgf_root, "status", "--porcelain", "--", *[s[1] for s in UPSTREAM_SETS])
    if dirty.strip():
        error(f"uncommitted changes under the DGF schema folders — commit them first:\n{dirty.rstrip()}")
    commit = git(dgf_root, "rev-parse", "HEAD").strip()
    version = dgf_version(dgf_root)
    print(f"Commit:  {commit}")
    print(f"Version: {version}  (from {VERSION_SOURCE})")
    if ERRORS:
        return summary(dry_run, changed=False)

    section("2. Copy and rewrite")
    before = previous_digests()
    entries, outputs, rewritten = [], {}, 0
    for vendored, upstream, path in upstream_files(dgf_root):
        data = path.read_bytes()
        shipped = vendor_one(vendored, data, dgf_path)
        if shipped is None:
            continue
        rewritten += shipped is not data
        entries.append((vendored, upstream, sha256(data), sha256(shipped)))
        outputs[vendored] = shipped
    if ERRORS:
        return summary(dry_run, changed=False)

    upstream_now = {upstream: up for _, upstream, up, _ in entries}
    new = sorted(set(upstream_now) - set(before))
    gone = sorted(set(before) - set(upstream_now))
    moved = sorted(p for p in upstream_now if p in before and before[p] != upstream_now[p])
    print(f"Files:     {len(entries)}  ({rewritten} rewritten)")
    print(f"Upstream:  {len(new)} new, {len(moved)} changed, {len(gone)} gone since the last vendor")
    for label, paths in (("new", new), ("changed", moved), ("gone", gone)):
        for path in paths:
            print(f"      {label:8} {path}")

    section("3. Shipped set")
    changed_files = [rel for rel, data in outputs.items()
                     if not (VENDORED_ROOT / rel).is_file() or (VENDORED_ROOT / rel).read_bytes() != data]
    stale = list(stale_vendored(set(outputs)))
    ledger = ledger_text(commit, entries)
    ledger_changed = ledger != LEDGER.read_text(encoding="utf-8")
    manifest = restamped_manifest(version, read_date)
    for rel in changed_files:
        print(f"      write    {rel}")
    for rel, _ in stale:
        print(f"      remove   {rel}")
    print(f"Ledger:    {'regenerated' if ledger_changed else 'unchanged'}")
    changed = bool(changed_files or stale or ledger_changed)

    if not dry_run:
        for rel in changed_files:
            (VENDORED_ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            (VENDORED_ROOT / rel).write_bytes(outputs[rel])
        for _, path in stale:
            path.unlink()
        LEDGER.write_text(ledger, encoding="utf-8")
        SHIPPED_MANIFEST.write_text(manifest, encoding="utf-8")
        print(f"Manifest:  stamped dgf_version {version}, read_date {read_date}")
    return summary(dry_run, changed)


def summary(dry_run, changed):
    section("Summary")
    print(f"Errors:   {ERRORS}")
    print(f"Warnings: {WARNINGS}")
    if ERRORS:
        print(f"\n{RED}BLOCKED{NC} — nothing was written")
        return 1
    if dry_run and changed:
        print(f"\n{YELLOW}WOULD CHANGE{NC} — re-run without --dry-run to write")
        return 2
    print(f"\n{GREEN}CLEAN{NC}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
