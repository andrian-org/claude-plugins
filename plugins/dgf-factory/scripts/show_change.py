#!/usr/bin/env python3
"""show_change.py — the unified diff of a branch's change, for the skills that read it (ADR 0032 §3).

The change is the working tree against the merge-base of HEAD and `--base` —
tracked changes plus untracked files, the set check_change.py computes — with
`.dgf-factory/` and every file `dgf-factory setup` installed left out, as
check_change.own_changes leaves them out (ADR 0029 §2). The base side of each
file is read blob by blob through lib/git.py (its old path for a rename); the
working-tree side from disk.

Each changed file prints `CHANGE: <A|M|D|R> <path>` (with ` from=<old>` for a
rename), then its unified diff. A path holding any whitespace, a `"` or a `\\`
is printed in double quotes, each `"` and `\\` in it escaped with a `\\`
(`CHANGE: A "x from=y.xml"`), so no file's name can forge the ` from=` suffix
or another path; a plain path is printed as it is. In the diff every line is
prefixed `| ` and, like every report line, has its control and line-separator
characters escaped (report.one_line), so
no line of a file's content can read as a line of this report. Tabs are
expanded before the escape. A file whose content does not end in a newline gets
a `\\ No newline at end of file` line, as git prints one.

  diff  every changed file, or only the `--files` named (root-relative); a
        file's diff longer than `--max-lines` is cut (SHOW_DIFF_TRUNCATED); a
        binary file, a file that is not UTF-8, a symlink, a submodule or a file
        that cannot be read is named and not diffed (SHOW_BINARY)

A report, never a gate: it decides nothing about the change, and its verdict is
CLEAN whenever it runs. Never writes. Stdlib only; git is required.

Usage:  show_change.py --workspaces-root R --base REF [--files PATH ...]
                       [--context N] [--max-lines N] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  the diff was shown (INFO findings only: SHOW_DIFF_TRUNCATED, SHOW_BINARY)
  3  usage error — a `--files` path that is not plain and root-relative, a
     `--base` that starts with `-`, a bad `--context` or `--max-lines`, no git,
     or no merge-base with `--base`
"""

if __name__ == "__main__":
    from lib import runtime; runtime.use_project_venv()

import difflib
import os
import stat
import sys
import unicodedata
from pathlib import Path

from lib import cli, git, report

HEADER = "CHANGE DIFF"
DIFF_PREFIX = "| "
NO_NEWLINE = "\\ No newline at end of file"
DEFAULT_CONTEXT = 3
DEFAULT_MAX_LINES = 400
BINARY_PROBE = 8000  # git's own: a NUL in the first 8000 bytes makes a file binary


def build_parser():
    parser = cli.parser("show_change.py", "Show the unified diff of a branch's change against the merge-base.")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds the workspaces")
    parser.add_argument("--base", required=True, help="the base branch; the change is the working tree against "
                                                      "the merge-base")
    parser.add_argument("--files", nargs="+", metavar="PATH", help="show only these changed files, root-relative")
    parser.add_argument("--context", type=int, default=DEFAULT_CONTEXT, metavar="N",
                        help=f"lines of context around each change (default {DEFAULT_CONTEXT})")
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES, metavar="N",
                        help=f"cut each file's diff after N lines (default {DEFAULT_MAX_LINES})")
    return parser


def check_inputs(args):
    """The resolved root; exit 3 on arguments that name nothing the diff can read."""
    import check_change
    root = Path(args.workspaces_root)
    if not root.is_dir():
        report.fail(report.EXIT_USAGE, f"--workspaces-root is not a directory: {root}")
    check_change.refuse(args.base, args.files, None)
    if args.context < 0:
        report.fail(report.EXIT_USAGE, f"--context takes a number of lines, 0 or more, not {args.context}")
    if args.max_lines < 1:
        report.fail(report.EXIT_USAGE, f"--max-lines takes a number of lines, 1 or more, not {args.max_lines}")
    return root.resolve()


def changed_set(root, base):
    """(merge-base sha, [git.Change] outside the pipeline's and the install's files), or exit 3."""
    import check_change
    if not git.available():
        report.fail(report.EXIT_USAGE, "--base needs git, which is not installed")
    try:
        sha = git.merge_base(root, base)
        changes = git.changed(root, sha)
    except git.GitError as exc:
        report.fail(report.EXIT_USAGE, f"no changed set against `{base}`: {exc}")
    return sha, sorted(check_change.own_changes(changes, root), key=lambda c: c.path)


def narrowed(changes, files):
    """The changes `--files` names, by the path or a rename's old path; every change without `--files`."""
    if not files:
        return changes
    named = {rel[2:] if rel.startswith("./") else rel for rel in files}
    kept = [c for c in changes if c.path in named or (c.old and c.old in named)]
    for rel in sorted(named - {c.path for c in kept} - {c.old for c in kept if c.old}):
        report.debug("show_change.narrowed", "named, but not changed", file=rel)
    return kept


# --- the two sides of a file --------------------------------------------------------

def base_modes(root, sha, changes):
    """{root-relative path: git mode} at the merge-base, for the changes that have a base side."""
    if not any(c.status != "A" for c in changes):
        return {}
    try:
        return {entry.path: entry.mode for entry in git.ls_tree(root, sha)}
    except git.GitError as exc:
        report.fail(report.EXIT_USAGE, f"no base tree at `{sha}`: {exc}")


def base_side(root, sha, change, modes):
    """(bytes or None, why not diffable or None) — the file at the merge-base."""
    if change.status == "A":
        return None, None
    rel = change.old or change.path
    mode = modes.get(rel)
    if mode == git.SYMLINK_MODE:
        return None, "a symlink at the base"
    if mode == git.SUBMODULE_MODE:
        return None, "a submodule"
    try:
        return git.show(root, sha, rel), None
    except git.GitError as exc:
        report.debug("show_change.base_side", "unreadable", file=rel, error=exc)
        return None, f"its base side cannot be read ({exc})"


def work_side(root, change):
    """(bytes or None, why not diffable or None) — the file in the working tree."""
    if change.status == "D":
        return None, None
    path = root.joinpath(*change.path.split("/"))
    try:
        info = os.lstat(path)
    except OSError as exc:
        return None, f"it cannot be read ({exc.strerror or exc})"
    if stat.S_ISLNK(info.st_mode):
        return None, "a symlink"
    if not stat.S_ISREG(info.st_mode):
        return None, "not a regular file"
    try:
        return path.read_bytes(), None
    except OSError as exc:
        return None, f"it cannot be read ({exc.strerror or exc})"


def as_text(content):
    """[lines] of `content`, or None when it is binary or not UTF-8."""
    if content is None:
        return []
    if b"\0" in content[:BINARY_PROBE]:
        return None
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not text:
        return []
    # Split on "\n" only: splitlines() would also split on \r, \x0b,   … and hide them from the escape.
    lines = [line.expandtabs() for line in text.split("\n")]
    if lines[-1] == "":
        lines.pop()
    else:
        lines.append(NO_NEWLINE)
    return lines


# --- one file ------------------------------------------------------------------------

def shown_path(path):
    """`path` as a `CHANGE:` line prints it: as it is, or quoted when a space, `"` or `\\` could make it read as more."""
    if not any(ch.isspace() or ch in '"\\' or unicodedata.category(ch) == "Zs" for ch in path):
        return path
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def change_line(change):
    return f"CHANGE: {change.status} {shown_path(change.path)}" + \
        (f" from={shown_path(change.old)}" if change.old else "")


def _style(lines):
    """`CRLF` when every line that ends ends in a carriage return, `LF` when none does, else None (mixed)."""
    body = [line for line in lines if line != NO_NEWLINE]
    if not body:
        return None
    crlf = sum(1 for line in body if line.endswith("\r"))
    return "CRLF" if crlf == len(body) else ("LF" if crlf == 0 else None)


def same_endings(old, new):
    """(old, new, note): when one side is wholly CRLF and the other wholly LF — a checkout under core.autocrlf, or a
    line-ending conversion — the carriage returns are dropped from both, so the diff shows content, and the note
    names the two styles. Mixed or matching endings are diffed as they are."""
    before, after = _style(old), _style(new)
    if not before or not after or before == after:
        return old, new, None
    strip = lambda lines: [line[:-1] if line.endswith("\r") else line for line in lines]
    report.debug("show_change.same_endings", "line endings differ", base=before, disk=after)
    return strip(old), strip(new), f"{before} at the base, {after} in the working tree"


def diff_lines(change, old, new, context):
    before = "/dev/null" if change.status == "A" else f"a/{change.old or change.path}"
    after = "/dev/null" if change.status == "D" else f"b/{change.path}"
    return list(difflib.unified_diff(old, new, fromfile=before, tofile=after, n=context, lineterm=""))


def show_one(root, sha, change, modes, args):
    """(Report, lines) for one changed file."""
    rep = report.Report(change.path)
    rep.ran("diff")
    lines = [change_line(change)]
    old, old_why = base_side(root, sha, change, modes)
    new, new_why = work_side(root, change)
    why = old_why or new_why
    old_lines, new_lines = (None, None) if why else (as_text(old), as_text(new))
    if why or old_lines is None or new_lines is None:
        rep.add("SHOW_BINARY", f"{why or 'binary, or not UTF-8 text'} — no diff shown")
        report.debug("show_change.show_one", "not diffed", file=change.path, why=why or "binary")
        return rep, lines
    note = []
    old_lines, new_lines, endings = same_endings(old_lines, new_lines)
    if endings:
        note = [DIFF_PREFIX + f"(line endings: {endings} — compared without them, as a checkout with core.autocrlf "
                              f"converts them)"]
    diff = diff_lines(change, old_lines, new_lines, args.context)
    if len(diff) > args.max_lines:
        rep.add("SHOW_DIFF_TRUNCATED", f"the diff has {len(diff)} lines; the first {args.max_lines} are shown — "
                                       f"pass --files {change.path} with a larger --max-lines to see it all")
        diff = diff[:args.max_lines]
    report.debug("show_change.show_one", "diffed", file=change.path, status=change.status, lines=len(diff))
    return rep, lines + note + [DIFF_PREFIX + line for line in diff]


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    root = check_inputs(args)
    sha, changes = changed_set(root, args.base)
    shown = narrowed(changes, args.files)
    modes = base_modes(root, sha, shown)
    counted = f"CHANGED: {len(shown)}" + (f" of {len(changes)} (narrowed by --files)" if args.files else "")
    lines = [f"ROOT: {root}", f"BASE: {sha} ({args.base})", counted]
    reports = []
    for change in shown:
        rep, more = show_one(root, sha, change, modes, args)
        reports.append(rep)
        lines += more
    if not reports:
        empty = report.Report(".")
        empty.ran("diff")
        reports.append(empty)
    report.debug("show_change.main", "shown", changed=len(changes), shown=len(shown))
    return report.render(reports, header=HEADER, lines=lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
