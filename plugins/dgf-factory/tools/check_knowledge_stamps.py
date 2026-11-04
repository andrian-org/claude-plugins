#!/usr/bin/env python3
"""check_knowledge_stamps.py — is every knowledge file stamped, and sourced, the way README.md says?

A repo-maintenance check, not a runtime validator: contributors run it (via
tools/check-dual-schema-docs.sh section 7), skills do not. It reads and
reports; it never edits.

The contract is knowledge/README.md §1 and §8, and ADR 0036. It holds for every
knowledge pack — the current line's in knowledge/, each older line's in
packs/<X.Y>/ (tools/packs.py says where):
  - the two line registries (packs/lines.json, provenance/lines.json) parse and
    name the same lines; each pack's stamps all carry its registry
    `dgf_version`, its registry `read_date` is the pack's newest, and its schema
    ledger's `dgf_commit` is the maintainer registry's commit;
  - every knowledge file carries its stamp (`dgf_version`, `read_date`, and an
    `applies` range or `review_date` where its fact class needs one), and never
    a `sources` key — a shipped file carries no DGF paths (ADR 0030);
  - only knowledge/ holds README.md; a pack under packs/ shares it;
  - every knowledge file has exactly one provenance ledger at the same relative
    path under provenance/ (knowledge/x.md -> provenance/knowledge/x.md,
    packs/1.2/x.md -> provenance/packs/1.2/x.md), and every ledger has its
    knowledge file;
  - each ledger lists its DGF sources, each with a 64-hex `sha256`;
  - the vendored schema set's ledger also names each shipped file (`vendored`)
    and its digest (`shipped_sha256`), and every shipped schema must match it —
    a mismatch is a hand edit to a vendored file.

It exists because the frontmatter is nested — `sources` is a list of maps,
`applies` is a map — and the only frontmatter parsing the shell script does is
one flat key. Asserting "every source has a digest" in awk is fragile in
exactly the way this check is meant to prevent.

Usage:  check_knowledge_stamps.py [<plugin-root>] [--pack <X.Y>]
        DEBUG=1 check_knowledge_stamps.py          # per-file trace
        LOG_LEVEL=debug check_knowledge_stamps.py  # same trace

With no root the plugin root is resolved from this file's location. Every pack
is checked unless --pack narrows the run to one.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — every stamped file and ledger conforms
  1  BLOCKED   — a stamp or ledger field is missing or malformed, a ledger is
                 missing or orphaned, a vendored schema was edited by hand, a
                 registry is malformed, or a stamp disagrees with its registry
  2  WARNINGS  — no stamped file was found
  3  usage error

No dgf-gate-result block is emitted: this is not a skill-facing gate, and
milestone 10 owns the plugin-wide gate contract.
"""

import hashlib
import importlib.util
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
NOT_LEDGERS = ("sync-log/",)  # maintainer notes under provenance/ that are not ledgers
SCHEMA_MANIFEST = "knowledge/schemas/MANIFEST.md"  # the current pack's vendored set's stamp

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


def load_packs():
    """tools/packs.py, beside this file, by path — the one place pack directories are decided."""
    spec = importlib.util.spec_from_file_location("packs_for_stamps", Path(__file__).resolve().parent / "packs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pack_rel(line, current):
    return "knowledge" if line == current else f"packs/{line}"


def knowledge_files(root, base_rel="knowledge"):
    """A pack's stamped files. README.md is exempt in knowledge/ and is an error in any other pack."""
    base = root / base_rel
    for path in sorted(base.rglob("*.md")):
        rel = path.relative_to(base).as_posix()
        if rel in EXEMPT and base_rel == "knowledge":
            continue
        if rel in EXEMPT:
            error(f"{base_rel}/{rel}: a pack shares knowledge/README.md and holds no copy of it")
            continue
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


def check_orphan_ledgers(root, knowledge_rels, pack_rels):
    """A ledger with no knowledge file records the provenance of nothing.

    Only the ledgers of the packs checked are scanned; with every pack checked, a
    ledger directory under provenance/packs/ for an unregistered line is an orphan too.
    """
    base = root / PROVENANCE
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*.md")):
        rel = path.relative_to(base).as_posix()
        if rel.startswith(NOT_LEDGERS):
            continue
        in_checked = any(rel.startswith(f"{pack}/") for pack in pack_rels)
        unregistered = rel.startswith("packs/") and not any(rel.startswith(f"{p}/") for p in pack_rels)
        if (in_checked or (unregistered and ALL_PACKS)) and rel not in knowledge_rels:
            error(f"{PROVENANCE}/{rel}: ledger has no knowledge file at {rel}")


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_vendored(root, fm, manifest=SCHEMA_MANIFEST):
    """Every shipped schema is listed in the schema ledger, and matches its shipped digest."""
    rel = f"{PROVENANCE}/{manifest}"
    base = (root / manifest).parent
    shown = base.relative_to(root).as_posix()
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
            error(f"{rel}: sources[{index}] names {shown}/{vendored}, which does not exist")
        elif entry.get("shipped_sha256") and sha256_of(path) != entry["shipped_sha256"]:
            error(f"{shown}/{vendored}: does not match its recorded `shipped_sha256` — "
                  "a vendored file was edited by hand; re-vendor with tools/vendor_schemas.py")
    for path in sorted(base.rglob("*")):
        vendored = path.relative_to(base).as_posix()
        if path.is_file() and path != root / manifest and vendored not in listed:
            error(f"{shown}/{vendored}: vendored file has no entry in {rel}")
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


def check_registry_agreement(pack, entry, maintainer_entry, versions, read_dates, schema_fm):
    """ADR 0036 §2: a pack's stamps are its registry's, and its schema ledger's commit is the registry's."""
    expected = f'"{entry["dgf_version"]}"'
    off = sorted(rel for rel, version in versions.items() if version != expected)
    for rel in off:
        error(f"{rel}: `dgf_version` {versions[rel]} is not the registry's {expected} for line {entry['line']}")
    if not off:
        trace(f"{pack}: every stamp is {expected}, the registry's")
    if read_dates and entry["read_date"] != max(read_dates.values()):
        error(f"packs/lines.json line {entry['line']}: `read_date` {entry['read_date']} is not the pack's newest "
              f"`read_date`, {max(read_dates.values())}")
    commit = (schema_fm or {}).get("scalars", {}).get("dgf_commit")
    if schema_fm is not None and commit != maintainer_entry.get("commit"):
        error(f"{PROVENANCE}/{pack}/schemas/MANIFEST.md: `dgf_commit` {commit} is not provenance/lines.json's "
              f"commit {maintainer_entry.get('commit')} for line {entry['line']}")
    tag = maintainer_entry.get("tag")
    ledger_tag = (schema_fm or {}).get("scalars", {}).get("dgf_tag")
    if schema_fm is not None and tag is not None and ledger_tag != tag:
        error(f"{PROVENANCE}/{pack}/schemas/MANIFEST.md: `dgf_tag` {ledger_tag} is not the registry's tag {tag}")


# --- main --------------------------------------------------------------------

ALL_PACKS = True


def resolve_root(argv):
    """(plugin root, --pack line or None)."""
    global ALL_PACKS
    usage = f"Usage: {Path(__file__).name} [<plugin-root>] [--pack <X.Y>]   (DEBUG=1 for a per-file trace)"
    args, line = list(argv), None
    if "--pack" in args:
        at = args.index("--pack")
        if at + 1 >= len(args):
            fail(3, usage)
        line = args[at + 1]
        del args[at:at + 2]
        ALL_PACKS = False
    if len(args) > 1 or any(arg.startswith("-") for arg in args):
        fail(3, usage)
    if args:
        root = Path(args[0]).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parents[1]  # tools/ -> plugin root
    if not (root / "knowledge").is_dir():
        fail(3, f"No knowledge directory under {root}")
    return root, line


def check_files(root, base_rel="knowledge"):
    """Runs the per-file rules; returns ({rel: dgf_version}, {rel: read_date}, {rel: ledger}, files checked)."""
    versions, read_dates, ledgers, checked = {}, {}, {}, 0
    for path in knowledge_files(root, base_rel):
        rel, fm = read_frontmatter(root, path)
        checked += 1
        if fm is None:
            continue
        trace(f"{rel}: applies={'yes' if fm['applies'] else 'no'}")
        check_required(rel, fm)
        check_applies(rel, fm)
        if fm["scalars"].get("dgf_version"):
            versions[rel] = fm["scalars"]["dgf_version"]
        if valid_date(fm["scalars"].get("read_date", "")):
            read_dates[rel] = fm["scalars"]["read_date"]
        ledgers[rel] = None
    return versions, read_dates, ledgers, checked


def selected_packs(root, line):
    """[(line, pack rel, shipped entry, maintainer entry)] — or [] after reporting a registry error."""
    packs = load_packs()
    try:
        shipped, maintainer, current = packs.load_registry(root)
    except packs.RegistryError as exc:
        error(f"line registry: {exc}")
        return []
    names = sorted(shipped, key=packs.parse_line)
    if line is not None and line not in shipped:
        fail(3, f"--pack {line}: no such line in packs/lines.json ({', '.join(names)})")
    chosen = [line] if line else names
    found = []
    for name in chosen:
        rel = pack_rel(name, current)
        if not (root / rel).is_dir():
            error(f"packs/lines.json names line {name} at {rel}/, which does not exist")
            continue
        found.append((name, rel, shipped[name], maintainer[name]))
    trace(f"packs: {', '.join(f'{n}={r}' for n, r, _s, _m in found)}")
    return found


def check_pack(root, name, rel, entry, maintainer_entry):
    """Every rule for one pack; returns (files checked, {knowledge rel})."""
    section(f"Pack {name} — {rel}/ (dgf_version {entry['dgf_version']}{', legacy' if entry.get('legacy') else ''})")
    versions, read_dates, ledgers, checked = check_files(root, rel)
    for knowledge_rel in ledgers:
        ledgers[knowledge_rel] = check_ledger(root, knowledge_rel)
    manifest = f"{rel}/schemas/MANIFEST.md"
    schema_fm = ledgers.get(manifest)
    if schema_fm:
        check_vendored(root, schema_fm, manifest)
    else:
        trace(f"skipped — no usable ledger for {manifest}")
    check_registry_agreement(rel, entry, maintainer_entry, versions, read_dates, schema_fm)
    return checked, set(ledgers)


def main(argv):
    root, line = resolve_root(argv[1:])
    print(f"{BOLD}Knowledge stamp check{NC}")
    print(f"Root: {root}")

    checked, knowledge_rels, pack_rels = 0, set(), []
    for name, rel, entry, maintainer_entry in selected_packs(root, line):
        count, rels = check_pack(root, name, rel, entry, maintainer_entry)
        checked += count
        knowledge_rels |= rels
        pack_rels.append(rel)
    if checked == 0 and not ERRORS:
        warn("no stamped files found — a clean tree and a broken glob look the same")

    section("Provenance ledgers without a knowledge file")
    check_orphan_ledgers(root, knowledge_rels, pack_rels)

    section("Summary")
    print(f"Packs checked: {len(pack_rels)}")
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
