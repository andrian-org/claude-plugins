#!/usr/bin/env python3
"""dgf_lines.py — which DGF release lines have moved past their knowledge packs, and the pack bookkeeping (ADR 0036 §7).

A repo-maintenance tool, not shipped. Four subcommands:

  status   <dgf-root> [--fetch] [--json <out>] [--line <X.Y>]
      For every registered line (packs/lines.json, provenance/lines.json):
        TAG_AVAILABLE       a release tag newer than the pack's exists on its line
        DRIFT               the pack's ledgers cite files that changed at that tag
                            (counted per knowledge file; check_drift.py's comparison)
        SCHEMA_SET_CHANGED  schema files were added or removed upstream at that tag
      and, as INFO, the unreleased commits on the line's support branch and its
      `.next` release-note fragments. Across the repository:
        NEW_LINE            a release line newer than every pack, or one with a
                            support branch (origin/X.Y.x), has no pack
      An untagged branch such as 2.x, and an old line with neither a pack nor a
      support branch, are INFO. Changes no knowledge file: safe to schedule.
  diff     <dgf-root> <line> --to <X.Y.Z> [--path <dgf-path>]… [--stat]
      Read-only. For each source the pack's ledgers cite that changed between the
      pack's pinned commit and <X.Y.Z> (the vendored schema set's excepted — that
      is vendor_schemas.py's), the knowledge file it feeds and its `git diff`, so
      the maintainer skill needs no git grant (ADR 0035). --path narrows it to the
      named sources; --stat prints the per-file summary only.
  checkout <dgf-root> <line> [--tag <X.Y.Z>]
      Materialises the line at its tag (default: the pack's tag, or the line's
      newest when the pack is a legacy pin) in a `git clone --shared` cache under
      $DGF_LINES_CACHE (default $XDG_CACHE_HOME/dgf-factory/lines, or
      ~/.cache/dgf-factory/lines), and prints its path. The maintainer's DGF
      working copy is never checked out or modified.
  freeze   <dgf-root> <line> --next <X.Y> --tag <X.Y.Z>
      The current line moves to packs/<line>/ (fact files, ledgers and its
      known-good exceptions copied), and <X.Y> becomes the current line in
      knowledge/, registered at <X.Y.Z>. The knowledge/ files still describe the
      old line until /dgf-sync brings them to the tag, so the stamp check fails in
      between — the honest state of a sync in progress.
  fork     <dgf-root> <new-line> --from <X.Y> --tag <X.Y.Z>
      A new older or side line: <X.Y>'s pack copied to packs/<new-line>/, and
      registered at <X.Y.Z>. Sync it next.

freeze and fork copy files and edit the two registries. They never edit a fact,
and they refuse an existing target and uncommitted changes under knowledge/,
packs/ or provenance/.

`--fetch` runs `git fetch --tags origin` in the DGF repository first: the only
write to it, and to its remote-tracking refs only.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — status: every pack is at its line's newest tag with no drift; freeze/fork/checkout: done
  1  BLOCKED   — freeze/fork/checkout refused (existing target, dirty tree, unknown tag)
  2  WARNINGS  — status: work is available
  3  usage error — not a DGF root, a bad registry, a bad argument
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TOOLS = PLUGIN_ROOT / "tools"
VERSION_SOURCE = Path("src") / "Directory.Build.props"  # the DGF root marker
RELEASE_TAG = re.compile(r"^\d+\.\d+\.\d+$")
SUPPORT_BRANCH = re.compile(r"^origin/(\d+\.\d+)\.x$")
NEXT_FRAGMENTS = "docs/wiki/Release-notes/.next"
EOL_CONFIG = (("core.autocrlf", "false"), ("core.eol", "lf"), ("core.safecrlf", "false"))
EXIT_CLEAN, EXIT_BLOCKED, EXIT_WARNINGS, EXIT_USAGE = 0, 1, 2, 3

if sys.stdout.isatty():
    RED, YELLOW, GREEN, BOLD, NC = "\033[0;31m", "\033[0;33m", "\033[0;32m", "\033[1m", "\033[0m"
else:
    RED = YELLOW = GREEN = BOLD = NC = ""

WARNINGS = 0
ERRORS = 0


def fail(code, message):
    """The single bail-out path. Errors go to stderr."""
    print(message, file=sys.stderr)
    raise SystemExit(code)


def warn(code, message):
    global WARNINGS
    WARNINGS += 1
    print(f"{YELLOW}WARN{NC}  {code} {message}")


def error(code, message):
    global ERRORS
    ERRORS += 1
    print(f"{RED}ERROR{NC} {code} {message}")


def info(message):
    print(f"INFO  {message}")


def debug(event, **kv):
    if os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug":
        pairs = " ".join(f"{k}={v}" for k, v in kv.items())
        print(f"DEBUG [dgf_lines.{event}] {pairs}", file=sys.stderr)


def load_tool(name):
    spec = importlib.util.spec_from_file_location(f"{name}_for_dgf_lines", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packs = load_tool("packs")


# --- git ---------------------------------------------------------------------

def git(root, *args, check=True):
    """stdout of `git -C root …`; None when the command fails and check is False."""
    debug("git", root=root, args=" ".join(args))
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        if check:
            fail(EXIT_BLOCKED, f"git {' '.join(args)} failed in {root}: {proc.stderr.strip()}")
        return None
    return proc.stdout


def version_key(tag):
    return tuple(int(part) for part in tag.split("."))


def release_tags(dgf):
    """{line: [tags, oldest first]} for every `X.Y.Z` tag in the DGF repository."""
    found = {}
    for tag in (git(dgf, "tag", "--list") or "").split():
        if RELEASE_TAG.match(tag):
            found.setdefault(packs.line_of(tag), []).append(tag)
    for tags in found.values():
        tags.sort(key=version_key)
    debug("release_tags", lines=",".join(f"{k}:{v[-1]}" for k, v in sorted(found.items())))
    return found


def support_branches(dgf):
    """{line: ref} for every remote-tracking `origin/X.Y.x` branch."""
    out = git(dgf, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin", check=False) or ""
    found = {}
    for ref in out.split():
        match = SUPPORT_BRANCH.match(ref)
        if match:
            found[match.group(1)] = ref
    return found


def commit_of(dgf, ref):
    out = git(dgf, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    return out.strip() if out else None


def cache_root():
    configured = os.environ.get("DGF_LINES_CACHE", "").strip()
    if configured:
        return Path(configured).expanduser()
    base = os.environ.get("XDG_CACHE_HOME", "").strip() or str(Path.home() / ".cache")
    return Path(base).expanduser() / "dgf-factory" / "lines"


def materialise(dgf, line, tag):
    """The cache checkout of `tag` for `line`: a shared clone, detached at the tag's commit. Returns its path."""
    sha = commit_of(dgf, tag)
    if sha is None:
        fail(EXIT_BLOCKED, f"no tag {tag} in {dgf}")
    cache = cache_root() / line
    if not (cache / ".git").is_dir():
        cache.parent.mkdir(parents=True, exist_ok=True)
        if cache.exists():
            shutil.rmtree(cache)
        git(cache.parent, "clone", "--shared", "--no-checkout", "--quiet", str(dgf), str(cache))
    # The ledgers digest the bytes a DGF working copy holds with core.autocrlf=input: the blob
    # content, LF. A maintainer's global core.autocrlf=true would write CRLF here and turn every
    # source into drift, so the cache pins its own end-of-line settings and rewrites every file.
    head = (git(cache, "rev-parse", "HEAD", check=False) or "").strip()
    eol_set = all((git(cache, "config", "--get", key, check=False) or "").strip() == value for key, value in EOL_CONFIG)
    if head == sha and eol_set and not (git(cache, "status", "--porcelain", check=False) or "").strip():
        # Already there and clean: reading it again needs no checkout, so readers of the same cache never collide.
        git(cache, "fetch", "--quiet", "--force", "--tags", str(dgf))
        debug("checkout", line=line, tag=tag, sha=sha[:12], cache=cache, state="already checked out")
        return cache
    for key, value in EOL_CONFIG:
        git(cache, "config", key, value)
    git(cache, "fetch", "--quiet", "--force", "--tags", str(dgf))
    git(cache, "read-tree", "--empty")
    git(cache, "checkout", "--quiet", "--force", "--detach", sha)
    git(cache, "clean", "--quiet", "-fdx")
    debug("checkout", line=line, tag=tag, sha=sha[:12], cache=cache)
    return cache


# --- status ------------------------------------------------------------------

def pack_tag(shipped_entry, maintainer_entry):
    """The tag a pack was read at, or None for a legacy pin."""
    return maintainer_entry.get("tag") if not shipped_entry.get("legacy") else None


def target_tag(line, shipped_entry, maintainer_entry, tags):
    """(the newest tag on the line, whether it is newer than the pack's)."""
    on_line = tags.get(line, [])
    if not on_line:
        return None, False
    newest = on_line[-1]
    current = pack_tag(shipped_entry, maintainer_entry)
    return newest, current is None or version_key(newest) > version_key(current)


def drift_at(cache, line):
    """{knowledge file: drifted source count}, drifted-or-missing in total, for one pack at a cache checkout."""
    drift = load_tool("check_drift")
    stamps = drift.load_stamps()
    pack = drift.Pack(line)
    _cited, found = drift.drift_findings(cache, stamps, drift.ledgers(stamps, pack))
    per_file = {}
    for _code, _ledger, _path, feeds, _expected, _actual in found:
        per_file[feeds] = per_file.get(feeds, 0) + 1
    return per_file


def schema_set_change(cache, line):
    """(added, removed) upstream schema paths at the cache checkout, against the pack's schema ledger."""
    vendor = load_tool("vendor_schemas")
    stamps = load_tool("check_knowledge_stamps")
    ledger = packs.ledger_dir(line) / "schemas" / "MANIFEST.md"
    lines = stamps.frontmatter_lines(ledger.read_text(encoding="utf-8")) or []
    recorded = {source.get("path") for source in stamps.parse_frontmatter(lines)["sources"]}
    upstream = {up for _vendored, up, _path in vendor.upstream_files(cache)}
    return sorted(upstream - recorded), sorted(recorded - upstream)


def unreleased(dgf, line, branch, newest):
    """(commits on the support branch since the newest tag, `.next` fragments there), or (None, None)."""
    if not branch or not newest:
        return None, None
    count = git(dgf, "rev-list", "--count", f"{newest}..{branch}", check=False)
    listing = git(dgf, "ls-tree", "--name-only", f"{branch}:{NEXT_FRAGMENTS}", check=False) or ""
    fragments = [name for name in listing.split() if name.endswith(".md")]
    return (int(count.strip()) if count else None), len(fragments)


def status_line(dgf, line, shipped_entry, maintainer_entry, tags, branches):
    """One line's report, as a dict for --json; prints as it goes."""
    newest, newer = target_tag(line, shipped_entry, maintainer_entry, tags)
    branch = branches.get(line) or (f"origin/{maintainer_entry['support_branch']}"
                                    if maintainer_entry.get("support_branch") else None)
    record = {"pack_version": shipped_entry["dgf_version"], "legacy": bool(shipped_entry.get("legacy")),
              "pack_tag": pack_tag(shipped_entry, maintainer_entry), "newest_tag": newest,
              "tag_available": newer, "drift": {}, "drift_total": 0, "schema_added": [], "schema_removed": [],
              "unreleased_commits": None, "next_fragments": None, "cache": None}
    print(f"\n{BOLD}Line {line}{NC} — pack {shipped_entry['dir']}/ at {shipped_entry['dgf_version']}"
          f"{' (legacy pin)' if record['legacy'] else ''}; newest release tag {newest or 'none'}")
    if newest is None:
        info(f"line {line} has no release tag in this repository — nothing to compare")
        return record
    if newer:
        warn("TAG_AVAILABLE", f"line {line}: {newest} is newer than the pack's "
                              f"{record['pack_tag'] or shipped_entry['dgf_version'] + ' (legacy pin)'} — "
                              f"/dgf-sync sync {line} --to {newest}")
    cache = materialise(dgf, line, newest)
    record["cache"] = str(cache)
    per_file = drift_at(cache, line)
    record["drift"], record["drift_total"] = per_file, sum(per_file.values())
    for feeds, count in sorted(per_file.items()):
        warn("DRIFT", f"line {line}: {feeds} cites {count} source(s) that changed at {newest}")
    added, removed = schema_set_change(cache, line)
    record["schema_added"], record["schema_removed"] = added, removed
    if added or removed:
        warn("SCHEMA_SET_CHANGED", f"line {line} at {newest}: {len(added)} schema file(s) added, "
                                   f"{len(removed)} removed — {', '.join((added + removed)[:4])}"
                                   f"{' …' if len(added) + len(removed) > 4 else ''}")
    commits, fragments = unreleased(dgf, line, branch, newest)
    record["unreleased_commits"], record["next_fragments"] = commits, fragments
    if commits:
        info(f"line {line}: {commits} unreleased commit(s) on {branch} since {newest}, "
             f"{fragments} .next fragment(s) — synced once tagged")
    if not newer and not per_file and not (added or removed):
        print(f"{GREEN}OK{NC}    line {line} is at {newest} with no drift")
    return record


def status_new_lines(tags, branches, registered):
    """Release lines with no pack: NEW_LINE when newer than every pack or maintained, INFO otherwise."""
    newest_registered = max(registered, key=packs.parse_line)
    new_lines, untracked = [], []
    for line in sorted(set(tags) | set(branches), key=packs.parse_line):
        if line in registered:
            continue
        newer = packs.parse_line(line) > packs.parse_line(newest_registered)
        if newer or line in branches:
            if line in tags:
                warn("NEW_LINE", f"release line {line} ({tags[line][-1]}) has no knowledge pack — "
                                 f"/dgf-sync {'new-line' if newer else 'add-line'} {line}")
                new_lines.append({"line": line, "newest_tag": tags[line][-1], "newer": newer})
            else:
                info(f"line {line} has a support branch ({branches[line]}) and no release tag yet")
        else:
            untracked.append(line)
    if untracked:
        info(f"older lines with no pack and no support branch, not tracked: {', '.join(untracked)}")
    return new_lines, untracked


def untagged_branches(dgf):
    """INFO for origin branches named like a major line (`2.x`) with no release tag of that major."""
    out = git(dgf, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin", check=False) or ""
    tags = set((git(dgf, "tag", "--list") or "").split())
    for ref in out.split():
        match = re.match(r"^origin/(\d+)\.x$", ref)
        if match and not any(tag.startswith(f"{match.group(1)}.") for tag in tags if RELEASE_TAG.match(tag)):
            info(f"{ref} carries no release tag — not a release line, no pack")


def cmd_status(args):
    dgf = args.dgf_root
    if args.fetch:
        print(f"Fetching tags and branches in {dgf} …")
        git(dgf, "fetch", "--quiet", "--tags", "origin")
    try:
        shipped, maintainer, current = packs.load_registry()
    except packs.RegistryError as exc:
        fail(EXIT_USAGE, f"line registry: {exc}")
    if args.line and args.line not in shipped:
        fail(EXIT_USAGE, f"--line {args.line}: not a registered line ({', '.join(sorted(shipped))})")
    print(f"{BOLD}DGF line status{NC}")
    print(f"DGF:     {dgf} (HEAD {(git(dgf, 'rev-parse', '--short', 'HEAD') or '?').strip()}, never checked out)")
    print(f"Packs:   {', '.join(sorted(shipped, key=packs.parse_line))} (current {current})")
    print(f"Cache:   {cache_root()}")
    tags, branches = release_tags(dgf), support_branches(dgf)
    report = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dgf_root": str(dgf),
              "current": current, "lines": {}, "new_lines": [], "untracked": []}
    for line in sorted(shipped, key=packs.parse_line):
        if args.line and line != args.line:
            continue
        report["lines"][line] = status_line(dgf, line, shipped[line], maintainer[line], tags, branches)
    if not args.line:
        print(f"\n{BOLD}Lines without a pack{NC}")
        report["new_lines"], report["untracked"] = status_new_lines(tags, branches, set(shipped))
        untagged_branches(dgf)
    report["verdict"] = "WARNINGS" if WARNINGS else "CLEAN"
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        info(f"report written to {args.json}")
    return summary()


# --- diff --------------------------------------------------------------------

def drifted_sources(cache, line):
    """[(knowledge file it feeds, source path)] that changed at the cache checkout, schema ledger excepted."""
    drift = load_tool("check_drift")
    stamps = drift.load_stamps()
    pack = drift.Pack(line)
    _cited, found = drift.drift_findings(cache, stamps, drift.ledgers(stamps, pack))
    return [(feeds, path) for _code, _ledger, path, feeds, _e, _a in found if not feeds.endswith("schemas/MANIFEST.md")]


def cmd_diff(args):
    try:
        shipped, maintainer, _current = packs.load_registry()
    except packs.RegistryError as exc:
        fail(EXIT_USAGE, f"line registry: {exc}")
    if args.line not in shipped:
        fail(EXIT_USAGE, f"line {args.line} has no pack")
    if not RELEASE_TAG.match(args.to) or packs.line_of(args.to) != args.line or commit_of(args.dgf_root, args.to) is None:
        fail(EXIT_USAGE, f"--to {args.to}: not a release tag on line {args.line} in {args.dgf_root}")
    pinned = maintainer[args.line]["commit"]
    cache = materialise(args.dgf_root, args.line, args.to)
    sources = drifted_sources(cache, args.line)
    if args.path:
        wanted = set(args.path)
        sources = [(feeds, path) for feeds, path in sources if path in wanted]
    print(f"{BOLD}Drifted sources of pack {args.line}{NC}: {pinned[:12]} → {args.to} ({len(sources)})")
    by_file = {}
    for feeds, path in sources:
        by_file.setdefault(feeds, []).append(path)
    for feeds in sorted(by_file):
        print(f"\n{BOLD}{feeds}{NC} — {len(by_file[feeds])} source(s)")
        for path in by_file[feeds]:
            stat = git(args.dgf_root, "diff", "--no-ext-diff", "--no-textconv", "--stat=120", pinned, args.to, "--",
                       path, check=False) or "  (no textual change — the file was renamed or its mode changed)\n"
            print(stat.rstrip())
            if not args.stat:
                print(git(args.dgf_root, "diff", "--no-ext-diff", "--no-textconv", "--no-color", pinned, args.to,
                          "--", path, check=False) or "")
    debug("diff", line=args.line, to=args.to, sources=len(sources))
    return EXIT_CLEAN


# --- checkout ----------------------------------------------------------------

def cmd_checkout(args):
    try:
        shipped, maintainer, _current = packs.load_registry()
    except packs.RegistryError as exc:
        fail(EXIT_USAGE, f"line registry: {exc}")
    tags = release_tags(args.dgf_root)
    tag = args.tag
    if tag is None:
        if args.line not in shipped:
            fail(EXIT_USAGE, f"line {args.line} has no pack; name the tag with --tag")
        tag = pack_tag(shipped[args.line], maintainer[args.line]) or (tags.get(args.line) or [None])[-1]
    if tag is None or not RELEASE_TAG.match(tag) or packs.line_of(tag) != args.line:
        fail(EXIT_USAGE, f"--tag {tag}: not a release tag on line {args.line}")
    cache = materialise(args.dgf_root, args.line, tag)
    print(cache)
    return EXIT_CLEAN


# --- freeze and fork ---------------------------------------------------------

def require_clean_tree():
    dirty = git(PLUGIN_ROOT, "status", "--porcelain", "--", "knowledge", "packs", "provenance", check=False)
    if dirty is None:
        fail(EXIT_BLOCKED, f"{PLUGIN_ROOT} is not a git work tree — refusing to move packs without one")
    if dirty.strip():
        fail(EXIT_BLOCKED, "uncommitted changes under knowledge/, packs/ or provenance/ — commit them first:\n"
                           + dirty.rstrip())


def copy_pack(source_dir, source_ledgers, source_exceptions, line):
    """Copy a pack's fact files (no README.md), its ledgers and its exceptions to packs/<line>/."""
    target, ledgers = PLUGIN_ROOT / "packs" / line, PLUGIN_ROOT / "provenance" / "packs" / line
    if target.exists() or ledgers.exists():
        fail(EXIT_BLOCKED, f"packs/{line}/ or provenance/packs/{line}/ already exists — refusing to overwrite it")
    shutil.copytree(source_dir, target, ignore=shutil.ignore_patterns("README.md", "__pycache__"),
                    copy_function=shutil.copy2)
    shutil.copytree(source_ledgers, ledgers, copy_function=shutil.copy2)
    if source_exceptions.is_file():
        shutil.copy2(source_exceptions, ledgers / packs.EXCEPTIONS_NAME)
    files = sum(1 for path in target.rglob("*") if path.is_file())
    print(f"copied {source_dir.relative_to(PLUGIN_ROOT)}/ → packs/{line}/ ({files} files), ledgers and exceptions")
    debug("copy_pack", source=source_dir, line=line, files=files)


def check_tag(dgf, line, tag):
    if not RELEASE_TAG.match(tag) or packs.line_of(tag) != line:
        fail(EXIT_USAGE, f"--tag {tag}: not a release tag on line {line}")
    sha = commit_of(dgf, tag)
    if sha is None:
        fail(EXIT_BLOCKED, f"no tag {tag} in {dgf} — run `dgf_lines.py status {dgf} --fetch` first")
    return sha


def registry_entries(dgf, line, tag, sha, read_date):
    branch = f"{line}.x" if commit_of(dgf, f"origin/{line}.x") else None
    shipped = {"line": line, "dgf_version": tag, "read_date": read_date}
    maintainer = {"tag": tag, "commit": sha, "support_branch": branch}
    return shipped, maintainer


def write_registries(shipped_data, maintainer_data):
    packs.write_json(PLUGIN_ROOT, packs.SHIPPED_REGISTRY, shipped_data)
    packs.write_json(PLUGIN_ROOT, packs.MAINTAINER_REGISTRY, maintainer_data)


def raw_registries():
    return (json.loads((PLUGIN_ROOT / packs.SHIPPED_REGISTRY).read_text(encoding="utf-8")),
            json.loads((PLUGIN_ROOT / packs.MAINTAINER_REGISTRY).read_text(encoding="utf-8")))


def cmd_freeze(args):
    try:
        shipped, _maintainer, current = packs.load_registry()
    except packs.RegistryError as exc:
        fail(EXIT_USAGE, f"line registry: {exc}")
    if args.line != current:
        fail(EXIT_USAGE, f"only the current line ({current}) can be frozen; {args.line} is already in packs/")
    if args.next in shipped:
        fail(EXIT_USAGE, f"--next {args.next} already has a pack")
    if packs.parse_line(args.next) <= packs.parse_line(args.line):
        fail(EXIT_USAGE, f"--next {args.next} must be newer than {args.line}; use fork for an older line")
    sha = check_tag(args.dgf_root, args.next, args.tag)
    require_clean_tree()
    copy_pack(PLUGIN_ROOT / "knowledge", PLUGIN_ROOT / "provenance" / "knowledge",
              packs.exceptions_file(args.line), args.line)
    ship, maint = raw_registries()
    for entry in ship["lines"]:
        if entry["line"] == args.line:
            entry["dir"] = f"packs/{args.line}"
    new_ship, new_maint = registry_entries(args.dgf_root, args.next, args.tag, sha,
                                           shipped[args.line]["read_date"])
    ship["lines"].insert(0, {"line": args.next, "dir": "knowledge", **{k: v for k, v in new_ship.items()
                                                                       if k != "line"}})
    ship["current"] = args.next
    maint["lines"] = {args.next: new_maint, **maint["lines"]}
    write_registries(ship, maint)
    print(f"line {args.line} frozen into packs/{args.line}/; line {args.next} is current in knowledge/ at "
          f"{args.tag} — next: /dgf-sync sync {args.next} --to {args.tag}")
    return EXIT_CLEAN


def cmd_fork(args):
    try:
        shipped, _maintainer, _current = packs.load_registry()
    except packs.RegistryError as exc:
        fail(EXIT_USAGE, f"line registry: {exc}")
    if args.source not in shipped:
        fail(EXIT_USAGE, f"--from {args.source}: not a registered line")
    if args.line in shipped:
        fail(EXIT_USAGE, f"line {args.line} already has a pack")
    sha = check_tag(args.dgf_root, args.line, args.tag)
    require_clean_tree()
    copy_pack(packs.pack_dir(args.source), packs.ledger_dir(args.source), packs.exceptions_file(args.source),
              args.line)
    ship, maint = raw_registries()
    new_ship, new_maint = registry_entries(args.dgf_root, args.line, args.tag, sha,
                                           shipped[args.source]["read_date"])
    ship["lines"].append({"line": args.line, "dir": f"packs/{args.line}",
                          **{k: v for k, v in new_ship.items() if k != "line"}})
    maint["lines"][args.line] = new_maint
    write_registries(ship, maint)
    print(f"line {args.line} forked from {args.source} into packs/{args.line}/ at {args.tag} — "
          f"next: /dgf-sync sync {args.line} --to {args.tag}")
    return EXIT_CLEAN


# --- main --------------------------------------------------------------------

def summary():
    print(f"\n{BOLD}Summary{NC}")
    print(f"Warnings: {WARNINGS}")
    print(f"Errors:   {ERRORS}")
    if ERRORS:
        print(f"\n{RED}BLOCKED{NC}")
        return EXIT_BLOCKED
    if WARNINGS:
        print(f"\n{YELLOW}WARNINGS{NC}")
        return EXIT_WARNINGS
    print(f"\n{GREEN}CLEAN{NC}")
    return EXIT_CLEAN


def dgf_root(value):
    root = Path(value).expanduser().resolve()
    if not (root / VERSION_SOURCE).is_file():
        fail(EXIT_USAGE, f"Not a DGF repository root (no {VERSION_SOURCE.as_posix()}): {root}")
    return root


def line_arg(value):
    try:
        packs.parse_line(value)
    except packs.VersionError as exc:
        fail(EXIT_USAGE, str(exc))
    return value


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="dgf_lines.py", description="DGF release lines against the knowledge packs.")
    parser.add_argument("--verbose", action="store_true", help="trace to stderr (same as DEBUG=1)")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("dgf_root", type=dgf_root)
    status.add_argument("--fetch", action="store_true")
    status.add_argument("--json")
    status.add_argument("--line", type=line_arg)
    diff = sub.add_parser("diff")
    diff.add_argument("dgf_root", type=dgf_root)
    diff.add_argument("line", type=line_arg)
    diff.add_argument("--to", required=True)
    diff.add_argument("--path", action="append", default=[])
    diff.add_argument("--stat", action="store_true")
    checkout = sub.add_parser("checkout")
    checkout.add_argument("dgf_root", type=dgf_root)
    checkout.add_argument("line", type=line_arg)
    checkout.add_argument("--tag")
    freeze = sub.add_parser("freeze")
    freeze.add_argument("dgf_root", type=dgf_root)
    freeze.add_argument("line", type=line_arg)
    freeze.add_argument("--next", required=True, type=line_arg)
    freeze.add_argument("--tag", required=True)
    fork = sub.add_parser("fork")
    fork.add_argument("dgf_root", type=dgf_root)
    fork.add_argument("line", type=line_arg)
    fork.add_argument("--from", dest="source", required=True, type=line_arg)
    fork.add_argument("--tag", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        raise SystemExit(EXIT_USAGE if exc.code else EXIT_CLEAN)
    if args.verbose:
        os.environ["DEBUG"] = "1"
    return args


def main(argv):
    args = parse_args(argv)
    debug("main", command=args.command)
    commands = {"status": cmd_status, "diff": cmd_diff, "checkout": cmd_checkout, "freeze": cmd_freeze, "fork": cmd_fork}
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
