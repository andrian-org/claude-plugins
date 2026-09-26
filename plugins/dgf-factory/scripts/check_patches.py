#!/usr/bin/env python3
"""check_patches.py — are the estate's patches well formed, and which are new? (ADR 0021 §1)

Checks one patch, several, or every `*.md` directly in the patches directory,
sorted by name:

  patch-name      `<YYYY-MM-DD-HH.mm>-<slug>.md`, a real timestamp, a slug of
                  at most 50 characters
  patch-fields    `# <title>`, then each field bullet once — date (equal to the
                  name's timestamp), plan, workspaces, files, findings,
                  dgf_version, severity — each value in its allowed form
  patch-sections  Problem, Root Cause, Solution, Prevention and Tags, in that
                  order, each with text; every tag `#[a-z0-9][a-z0-9-]*`
  patch-cursor    (--cursor) each well-formed patch `new` or `processed`; a
                  malformed patch is never new. An unreadable cursor warns, and
                  every well-formed patch then counts as new

The format is skills/dgf-fix/references/PATCH-FORMAT.md. A PATCH argument is an
ordinary path — absolute, or relative to the working directory — and must name
a file directly in the patches directory. `--patches-dir` and `--cursor` are
relative to the root. The root needs no `.dgf-factory/config.yaml`. Never
writes: not a patch, not the cursor. Stdlib only.

Usage:  check_patches.py --workspaces-root R [--patches-dir D] [--cursor C]
                         [PATCH ...] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  every patch is well formed (or there are none)
  1  a patch is malformed — it is never read as a lesson, nor marked processed
  2  the cursor is unreadable (PATCH_CURSOR_UNREADABLE); every patch counts as new
  3  usage error: no root, or a PATCH outside the patches directory
"""

import sys
from pathlib import Path

from lib import cli, patches, report

HEADER = "Patch check"
DEFAULT_PATCHES = ".dgf-factory/patches/"
CHECKS = ("patch-name", "patch-fields", "patch-sections")


def build_parser():
    parser = cli.parser("check_patches.py", "Check dgf-factory patches, and say which the cursor has not seen.")
    parser.add_argument("patches", nargs="*", metavar="PATCH", help="a patch file; default: every *.md in the "
                                                                    "patches directory")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds .dgf-factory/")
    parser.add_argument("--patches-dir", default=DEFAULT_PATCHES, help="relative to the root (paths.patches)")
    parser.add_argument("--cursor", help="relative to the root: <paths.evolutions>patch-cursor.json")
    return parser


def rejected(message, **kv):
    report.debug("check_patches.targets", "rejected", **kv)
    report.fail(report.EXIT_USAGE, message)


def targets(named, patches_dir):
    """The patch files to check: each PATCH, or every *.md directly in `patches_dir`."""
    if not named:
        if not patches_dir.exists():
            report.debug("check_patches.targets", "no patches directory", dir=patches_dir)
            return []
        if not patches_dir.is_dir():
            rejected(f"--patches-dir is not a directory: {patches_dir}", dir=patches_dir)
        # Every entry, regular or not: a directory or a device named like a patch is reported, never skipped.
        return sorted(patches_dir.glob("*.md"))
    home, found = patches_dir.resolve(), []
    for raw in named:
        path = Path(raw).resolve()
        if not path.is_file():
            rejected(f"not a file: {raw}", patch=raw)
        if path.parent != home:
            rejected(f"{raw} is not directly in the patches directory {patches_dir}", patch=raw, home=home)
        if path not in found:
            found.append(path)
    return found


def state(patch, rep, processed):
    if patch is None or rep.exit_code() == report.EXIT_BLOCKED:
        return "malformed"
    return "processed" if processed is not None and patch.name in processed else "new"


def patch_line(path, patch, status, with_state):
    shown = f"PATCH: {path.name}"
    if with_state:
        shown += f" state={status}"
    severity = patch.value("severity") if patch else ""
    findings = patch.value("findings") if patch else ""
    title = patch.title if patch else ""
    return f"{shown} severity={severity or '?'} findings={findings or '?'} title=\"{title}\""


def check_cursor(root, cursor, run):
    """(cursor report, processed names or None)."""
    rel = Path(cursor).as_posix()
    rep = report.Report(rel)
    rep.ran("patch-cursor")
    processed, why = patches.read_cursor(root / cursor)
    if why:
        rep.add("PATCH_CURSOR_UNREADABLE", f"{why} — every well-formed patch counts as new")
    for name in sorted((processed or set()) - run):
        report.debug("check_patches.check_cursor", "processed, and no longer in the directory", name=name)
    return rep, processed


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    root = Path(args.workspaces_root)
    if not root.is_dir():
        rejected(f"--workspaces-root is not a directory: {args.workspaces_root}", root=args.workspaces_root)
    shown_dir = Path(args.patches_dir).as_posix().rstrip("/") + "/"
    patches_dir = root / args.patches_dir
    reports, parsed = [], []
    for path in targets(args.patches, patches_dir):
        rep = report.Report(shown_dir + path.name)
        for check in CHECKS:
            rep.ran(check)
        parsed.append((path, patches.parse(path, rep.file, rep), rep))
        reports.append(rep)
    processed = None
    if args.cursor:
        in_dir = {p.name for p in patches_dir.glob("*.md")} if patches_dir.is_dir() else set()
        cursor_rep, processed = check_cursor(root, args.cursor, in_dir)
        reports.append(cursor_rep)
    states = [(path, patch, state(patch, rep, processed)) for path, patch, rep in parsed]
    count = {s: sum(1 for *_, found in states if found == s) for s in ("new", "processed", "malformed")}
    head = f"PATCHES: {shown_dir} total={len(states)}"
    if args.cursor:
        head += f" new={count['new']} processed={count['processed']}"
    lines = [head + f" malformed={count['malformed']}"]
    lines += [patch_line(path, patch, status, bool(args.cursor)) for path, patch, status in states]
    report.debug("check_patches.main", "checked", total=len(states), new=count["new"], malformed=count["malformed"])
    return report.render(reports, header=HEADER, lines=lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
