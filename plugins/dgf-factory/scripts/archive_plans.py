#!/usr/bin/env python3
"""archive_plans.py — which plans are finished, and with --apply, move them into the archive (ADR 0032 §3).

Lists every plan as locate_plan.py --list does — each `*.md` and `*/index.md`
directly in the plans directory, then the fast plan — read with lib/plan.py:

  plans-progress  a plan with at least one task and every task checked is
                  complete: `ARCHIVE: <src> -> <dest> progress=<d>/<t>`; any
                  other is `KEEP: <src> progress=<d>/<t>`. A plan that does not
                  parse is kept (ARCHIVE_PLAN_SKIPPED), and so is a plan that
                  is a symlink — the plan file, the bundle's directory or its
                  index.md: it is never stamped or moved through the link
                  (ARCHIVE_PLAN_SKIPPED). The current branch's
                  plan is kept — `/dgf-commit` still follows its Commit Plan —
                  unless `--plan` names it. `--plan` restricts the run to the
                  plans it names; a named plan that is not complete is
                  ARCHIVE_PLAN_INCOMPLETE. A destination that exists, or that
                  two plans share when case is ignored, is ARCHIVE_DEST_EXISTS
  archive-move    (--apply) each `ARCHIVE:` plan is moved, a bundle's directory
                  as a whole, and arrives with `archived: <YYYY-MM-DD>` in its
                  header — its index.md for an ultra bundle — just before the
                  closing `---` (replacing an `archived:` line it already
                  has): `MOVED: <src> -> <dest>`. The stamp is written at the
                  destination, never into the source: a plan file's stamped
                  text is written beside its destination and linked into
                  place, and only then is the source removed; a bundle is
                  renamed into a directory made for it, then its index.md is
                  stamped there, and renamed back if that fails. A move never
                  replaces anything: every destination is checked again just
                  before the first move, and the move itself refuses one that
                  appeared since. Any ERROR refuses the whole run before
                  anything is written

Destinations: a full plan `<archive>/plans/<name>.md`, an ultra bundle
`<archive>/plans/<dir>/`, the fast plan `<archive>/plans/PLAN-<YYYY-MM-DD>.md`.
The date is this machine's clock, never the caller's. Every path is relative to
the root; `--archive-dir` must be under `.dgf-factory/`. Without --apply
nothing is written. The current branch is read through lib/git.py; without
git no plan is the current branch's. Stdlib only.

Usage:  archive_plans.py --workspaces-root R [--plans-dir D] [--fast-plan F]
                         [--archive-dir A] [--plan PATH ...] [--apply] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  plans listed (and with --apply, moved)
  1  refused: a named plan is not complete, or a destination exists — with
     --apply nothing was moved
  2  nothing to archive (ARCHIVE_NOTHING), or a plan that does not parse was
     left where it is (ARCHIVE_PLAN_SKIPPED)
  3  usage error — a path that is not plain and root-relative, an archive
     directory outside `.dgf-factory/`, a `--plan` that is no listed plan, or
     a write or a move that failed: that plan is where it was, byte for byte,
     and the message names the plans moved before it
"""

if __name__ == "__main__":
    from lib import runtime; runtime.use_project_venv()

import datetime
import errno
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from lib import cli, plan, report

HEADER = "Plan archive"
DEFAULT_PLANS = f"{plan.PIPELINE_DIR}/plans/"
DEFAULT_FAST = f"{plan.PIPELINE_DIR}/PLAN.md"
DEFAULT_ARCHIVE = f"{plan.PIPELINE_DIR}/archive/"
ARCHIVED_KEY = "archived"


@dataclass
class Candidate:
    src: str          # root-relative: a plan file, or an ultra bundle's directory
    entry: Path       # the file that holds the header: the plan, or the bundle's index.md
    dest: str         # root-relative
    is_dir: bool
    progress: str     # `<d>/<t>` or `unreadable`
    complete: bool
    readable: bool
    current: bool = False  # the current branch's plan
    link: bool = False     # the plan, its bundle directory or its index.md is a symlink


def build_parser():
    parser = cli.parser("archive_plans.py", "List finished dgf-factory plans, and with --apply archive them.")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds .dgf-factory/")
    parser.add_argument("--plans-dir", default=DEFAULT_PLANS, help="relative to the root (paths.plans)")
    parser.add_argument("--fast-plan", default=DEFAULT_FAST, help="relative to the root (paths.plan)")
    parser.add_argument("--archive-dir", default=DEFAULT_ARCHIVE, help="relative to the root, under .dgf-factory/ "
                                                                      "(paths.archive)")
    parser.add_argument("--plan", nargs="+", metavar="PATH", help="only these plans, root-relative: a plan file, an "
                                                                 "ultra bundle's directory or its index.md")
    parser.add_argument("--apply", action="store_true", help="move each complete plan; without it nothing is "
                                                             "written")
    return parser


def plain(flag, value):
    """`value` as a plain root-relative path — `./` and a trailing `/` dropped — or exit 3."""
    rel = value[2:] if value.startswith("./") else value
    rel = rel.rstrip("/") if rel not in ("", "/") else rel
    problem = "is empty" if not rel else plan.path_problem(rel)
    if problem:
        report.debug("archive_plans.plain", "refused", flag=flag, path=value, why=problem)
        report.fail(report.EXIT_USAGE, f"{flag} takes a path relative to the workspaces root; `{value}` {problem}")
    return rel


def check_inputs(args):
    """(root, plans dir, fast plan, archive dir) — the last three root-relative — or exit 3."""
    root = Path(args.workspaces_root)
    if not root.is_dir():
        report.fail(report.EXIT_USAGE, f"--workspaces-root is not a directory: {root}")
    plans_dir = plain("--plans-dir", args.plans_dir)
    fast = plain("--fast-plan", args.fast_plan)
    archive = plain("--archive-dir", args.archive_dir)
    if not plan.is_pipeline(archive) or archive == plan.PIPELINE_DIR:
        report.fail(report.EXIT_USAGE, f"--archive-dir must be a folder under {plan.PIPELINE_DIR}/, the pipeline's "
                                       f"own, not `{args.archive_dir}`")
    return root.resolve(), plans_dir, fast, archive


# --- the plans ---------------------------------------------------------------------------

def rel_of(root, path):
    return Path(os.path.relpath(path, root)).as_posix()


def branch_plans(root, plans_dir):
    """The root-relative sources of the current branch's plan — none without git or a branch."""
    import locate_plan
    branch = locate_plan.current_branch(root, None)
    if not branch:
        return set()
    stem = branch.replace("/", "-")
    report.debug("archive_plans.branch_plans", "current branch", branch=branch, stem=stem)
    return {f"{plans_dir}/{stem}", f"{plans_dir}/{stem}.md"}


def candidates(root, plans_dir, fast, archive, today):
    """[Candidate] for every plan, in locate_plan.py --list's order."""
    import locate_plan
    found = []
    for entry in locate_plan.entrypoints(root / plans_dir):
        is_dir = entry.name == "index.md" and entry.parent != root / plans_dir
        src_path = entry.parent if is_dir else entry
        dest = f"{archive}/plans/{src_path.name}"
        found.append(candidate(root, entry, src_path, dest, is_dir))
    if (root / fast).is_file() and fast not in {item.src for item in found}:
        found.append(candidate(root, root / fast, root / fast, f"{archive}/plans/PLAN-{today}.md", False))
    current = branch_plans(root, plans_dir)
    for item in found:
        item.current = item.src in current
    return found


def candidate(root, entry, src_path, dest, is_dir):
    import locate_plan
    link = os.path.islink(src_path) or os.path.islink(entry)  # lstat: a link is never read through
    mode, done, total = ("unreadable", None, None) if link else locate_plan.describe(entry)
    readable = mode != "unreadable"
    return Candidate(src=rel_of(root, src_path), entry=entry, dest=dest, is_dir=is_dir,
                     progress=f"{done}/{total}" if readable else "unreadable",
                     complete=readable and bool(total) and done == total, readable=readable, link=link)


def named(found, values):
    """The candidates `--plan` names, in its order, or exit 3 for a name that is no listed plan."""
    by_src = {item.src: item for item in found}
    chosen = []
    for value in values:
        rel = plain("--plan", value)
        if rel.endswith("/index.md") and rel[:-len("/index.md")] in by_src:
            rel = rel[:-len("/index.md")]
        if rel not in by_src:
            report.fail(report.EXIT_USAGE, f"--plan `{value}` is no plan in the plans directory, nor the fast plan "
                                           f"({', '.join(by_src) or 'none listed'})")
        if by_src[rel] not in chosen:
            chosen.append(by_src[rel])
    return chosen


def shown(path, is_dir):
    return path + "/" if is_dir else path


# --- the decision ----------------------------------------------------------------------

def decide(root, found, explicit, rep_of):
    """[(Candidate, line)] in order, each ARCHIVE or KEEP, findings added to each plan's report."""
    decided, dests = [], {}
    for item in found:
        rep = rep_of(item)
        src = shown(item.src, item.is_dir)
        if item.link:
            rep.add("ARCHIVE_PLAN_SKIPPED", "the plan is a symlink — left where it is; a link is never stamped or moved, "
                                            "since the write would land wherever it points")
            decided.append((item, f"KEEP: {src} progress=unreadable — a symlink"))
            continue
        if not item.readable:
            rep.add("ARCHIVE_PLAN_SKIPPED", "the plan does not parse — left where it is; check_plan.py says why")
            decided.append((item, f"KEEP: {src} progress=unreadable"))
            continue
        if not item.complete:
            if explicit:
                rep.add("ARCHIVE_PLAN_INCOMPLETE", f"named with --plan, but {item.progress} tasks are checked — only "
                                                   f"a plan with every task checked is archived")
            decided.append((item, f"KEEP: {src} progress={item.progress}"))
            continue
        if item.current and not explicit:
            decided.append((item, f"KEEP: {src} progress={item.progress} — the current branch's plan; name it with "
                                  f"--plan"))
            continue
        dest, key = shown(item.dest, item.is_dir), item.dest.casefold()  # APFS and NTFS: one name, any case
        if os.path.lexists(root / item.dest):
            rep.add("ARCHIVE_DEST_EXISTS", f"`{dest}` already exists — nothing is moved over it")
        elif key in dests:
            rep.add("ARCHIVE_DEST_EXISTS", f"`{dest}` is also the destination of {dests[key]} when case is ignored — "
                                           f"nothing is moved over it")
        dests.setdefault(key, src)
        decided.append((item, f"ARCHIVE: {src} -> {dest} progress={item.progress}"))
    return decided


# --- the move ----------------------------------------------------------------------------

def stamped(text, today):
    """`text` with `archived: <today>` in its header: replacing an `archived:` line, else before the closing `---`."""
    body = text.lstrip("﻿")
    bom = text[:len(text) - len(body)]
    raw = body.splitlines(keepends=True)  # the same split plan.parse_text makes, so the indices agree
    header, where, start = plan.parse_header(body.splitlines())
    closing = raw[start - 1]
    newline = closing[len(closing.rstrip("\r\n")):] or "\n"
    line = f"{ARCHIVED_KEY}: {today}{newline}"
    if ARCHIVED_KEY in header:
        raw[where[ARCHIVED_KEY] - 1] = line
    else:
        raw.insert(start - 1, line)
    result = bom + "".join(raw)
    if plan.parse_text(result).header.get(ARCHIVED_KEY) != today:
        raise plan.PlanFormatError(None, "the stamped header does not read back")
    return result


class _NotMoved(Exception):
    """The plan could not be archived; `where` says where it is now — where it was, unchanged, unless told otherwise."""

    def __init__(self, message, where="it is where it was, unchanged"):
        super().__init__(message)
        self.where = where


def _write_new(folder, text, like):
    """A new file in `folder` holding `text` with `like`'s mode bits — mkstemp's, so nothing planted is written through."""
    fd, name = tempfile.mkstemp(dir=folder, prefix=".archive-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(text.encode("utf-8"))
        shutil.copymode(like, name)
    except OSError:
        os.unlink(name)
        raise
    return Path(name)


def _place_file(src, target, text):
    """Write the stamped `text` at `target` — never replacing it — and only then remove `src`."""
    tmp = _write_new(target.parent, text, src)
    try:
        os.link(tmp, target)  # refuses an existing target (EEXIST); os.rename would replace it
    except FileExistsError as exc:
        raise _NotMoved(f"`{target.name}` appeared in the archive — nothing is moved over it") from exc
    except OSError as exc:
        if exc.errno not in (errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EMLINK):
            raise
        if os.path.lexists(target):  # a disk without hard links: check, then rename
            raise _NotMoved(f"`{target.name}` appeared in the archive — nothing is moved over it") from exc
        os.rename(tmp, target)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)
    try:
        os.unlink(src)
    except OSError as exc:
        os.unlink(target)
        raise _NotMoved(f"cannot remove the source: {exc.strerror or exc}") from exc


def _place_dir(src, target, index, text):
    """Rename the bundle into a new, empty directory at `target`, then stamp its index.md there; undone on failure."""
    try:
        os.mkdir(target)  # refuses an existing target; the rename below may only replace this empty one
    except FileExistsError as exc:
        raise _NotMoved(f"`{target.name}/` appeared in the archive — nothing is moved over it") from exc
    try:
        os.rename(src, target)
    except OSError:
        os.rmdir(target)
        raise
    placed, tmp = target / index.name, None
    try:
        tmp = _write_new(target, text, placed)
        os.replace(tmp, placed)
    except OSError as exc:
        if tmp is not None and os.path.lexists(tmp):
            os.unlink(tmp)
        try:
            os.rename(target, src)
        except OSError as back:
            raise _NotMoved(f"cannot stamp {index.name}: {exc.strerror or exc}",
                            f"it is at {target}, unstamped — renaming it back failed: {back.strerror or back}") from exc
        raise _NotMoved(f"cannot stamp {index.name}: {exc.strerror or exc}") from exc


def move(root, item, today, moved):
    """Move `item` and stamp it at its destination; exit 3 on a failure, which leaves that plan where it was."""
    target = root / item.dest
    try:
        text = stamped(item.entry.read_bytes().decode("utf-8"), today)  # bytes: a text read turns CRLF into LF
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.parent.is_dir() or target.parent.is_symlink():
            raise _NotMoved(f"{target.parent} is not a folder of the archive's own")
        if item.is_dir:
            _place_dir(root / item.src, target, item.entry, text)
        else:
            _place_file(root / item.src, target, text)
    except (OSError, UnicodeDecodeError, plan.PlanFormatError, _NotMoved) as exc:
        where = exc.where if isinstance(exc, _NotMoved) else "it is where it was, unchanged"
        so_far = f"moved before it: {', '.join(moved)}" if moved else "nothing was moved before it"
        report.fail(report.EXIT_USAGE, f"cannot archive {item.src}: {exc} — {where}; {so_far}")
    report.debug("archive_plans.move", "moved", src=item.src, dest=item.dest)
    moved.append(item.src)
    return f"MOVED: {shown(item.src, item.is_dir)} -> {shown(item.dest, item.is_dir)}"


def recheck(root, to_move, rep_of):
    """ARCHIVE_DEST_EXISTS for a destination that appeared since the decision — checked before the first move."""
    for item in to_move:
        if os.path.lexists(root / item.dest):
            rep_of(item).add("ARCHIVE_DEST_EXISTS", f"`{shown(item.dest, item.is_dir)}` appeared before the move — "
                                                   f"nothing is moved over it")


def apply(root, decided, reports, run, today, rep_of):
    """MOVED lines for every ARCHIVE plan — none when any report holds an ERROR."""
    to_move = [item for item, line in decided if line.startswith("ARCHIVE: ")]
    recheck(root, to_move, rep_of)
    if report.exit_code(reports) == report.EXIT_BLOCKED:
        run.skipped("archive-move", "refused: an ERROR above — nothing was moved")
        return []
    if not to_move:
        run.skipped("archive-move", "nothing to archive")
        return []
    moved = []
    lines = [move(root, item, today, moved) for item in to_move]
    run.ran("archive-move")
    return lines


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    root, plans_dir, fast, archive = check_inputs(args)
    today = datetime.date.today().isoformat()
    found = candidates(root, plans_dir, fast, archive, today)
    if args.plan:
        found = named(found, args.plan)
    run = report.Report(shown(plans_dir, True))
    run.ran("plans-progress")
    reports, by_src = [run], {}

    def rep_of(item):
        if item.src not in by_src:
            by_src[item.src] = report.Report(shown(item.src, item.is_dir))
            reports.append(by_src[item.src])
        return by_src[item.src]

    decided = decide(root, found, bool(args.plan), rep_of)
    lines = [f"ROOT: {root}"] + [line for _, line in decided]
    archived = sum(1 for _, line in decided if line.startswith("ARCHIVE: "))
    if not archived and not args.plan:  # a named plan that does not move has a finding of its own
        kept = sum(1 for item, _ in decided if item.complete)
        why = f"; {kept} complete plan(s) kept as the current branch's" if kept else ""
        run.add("ARCHIVE_NOTHING", (f"no plan is complete{why}" if found else
                                    f"no plan in {shown(plans_dir, True)}, and no fast plan {fast}"))
    if args.apply:
        lines += apply(root, decided, reports, run, today, rep_of)
    else:
        run.skipped("archive-move", "a dry run — pass --apply to move the ARCHIVE plans")
    report.debug("archive_plans.main", "decided", plans=len(found), archive=archived, apply=args.apply)
    return report.render(reports, header=HEADER, lines=lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
