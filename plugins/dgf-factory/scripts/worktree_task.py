#!/usr/bin/env python3
"""worktree_task.py — a worker's worktree synced from the main tree, and merged back into it (ADR 0033 §3).

Two modes, each over a pair of trees that must be worktrees of one repository —
the same `git rev-parse --git-common-dir` — the worker's being a linked worktree,
never the main one (else WORKTREE_NOT_LINKED, exit 3).

--sync --from <main workspaces root> --worktree <a folder inside the worker's worktree>

  Moves a clean worktree's own branch to the main tree's HEAD (`reset --hard`):
  Claude Code starts a subagent's worktree from the remote default branch. A
  worktree with changes of its own at another commit is WORKTREE_HEAD_MISMATCH.
  Then copies the main tree's uncommitted state below the workspaces root into
  the worktree — modified, staged, untracked-and-not-ignored files with their
  mode bits, symlinks as links — and removes what the main tree deleted.
  `<root>/.dgf-factory/runtime/` and `.claude/worktrees/` are never copied.
  What it copied is recorded in the worktree's own git dir, `dgf-sync.json`:
  `{"head", "main", "root", "files": {<toplevel-relative path>: <sha256, or
  null for a deletion>}}` — no status sees it, no commit can take it, and
  `git worktree remove` deletes it.

--merge --from <the worker's workspaces root> --to <the main workspaces root>
        --plan <the main plan entrypoint> --task <n> [--cleanup]

  The worker's change is every path whose worktree content differs from its
  base: the sync record's digest when it has one, else HEAD — read from the
  worktree's own status, never by comparing bytes with a blob (core.autocrlf).
  Each changed path must be in Task n's `files` (added or modified) or `deletes`
  (deleted), below the workspaces root, and not a symlink, else
  WORKTREE_UNDECLARED_FILE — the plan file included. Both HEADs must still be
  the synced commit, else WORKTREE_HEAD_MISMATCH; and the main tree's copy must
  still be its base, else WORKTREE_MAIN_CHANGED: the recorded digest for a
  synced path; for an addition, nothing at the path at all (os.path.lexists —
  an ignored file, or a name that differs only in case on APFS, is something);
  for a modification or deletion, HEAD's blob (`git hash-object --path`, the
  repository's filters applied), never the main tree's status, which an ignore
  rule or an assume-unchanged or skip-worktree bit can hide a change from. Any
  finding: nothing is copied, exit 1. Otherwise each file is copied (a
  temporary file mkstemp creates beside the target, its mode kept, then
  os.replace) or deleted. With --cleanup the worktree is removed
  (`worktree remove --force`) and its branch deleted (`branch -D`); a locked
  worktree is left in place, and that never changes the exit code.

The workspaces root may sit below the git toplevel; every printed path is
root-relative. Needs git. Stdlib only.

Usage:  worktree_task.py --sync --from <root> --worktree <dir> [--verbose]
        worktree_task.py --merge --from <root> --to <root> --plan <plan> --task <n> [--cleanup] [--verbose]

Output, in place of the `FAMILY:` lines:
  MAIN: <main toplevel>     WORKTREE: <worktree toplevel>     WORKTREE ROOT: <the worker's workspaces root>
  --sync:  HEAD: <sha> [(moved from <sha>)]; SYNCED: <n> file(s), <d> deletion(s)
  --merge: MERGED: <A|M|D> <root-relative path>, one per file;
           with --cleanup, REMOVED: <path> (<branch>) or REMOVED: none — <why>

Exit codes (contract, see .ai-factory/rules/base.md):
  0  synced, or merged
  1  refused: a dirty worktree at another commit, no sync record, a moved HEAD,
     an undeclared file, or a main tree that changed — nothing was copied
  3  not a linked worktree of the same repository, an unreadable plan, or a
     usage error
"""

if __name__ == "__main__":
    from lib import runtime; runtime.use_project_venv()

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from lib import cli, git, plan, report, worktree

HEADER = "Worktree task"
RECORD = "dgf-sync.json"
RUNTIME = ".dgf-factory/runtime/"


class TaskError(Exception):
    """A file could not be copied or removed, or a path git printed is not a plain relative one."""


def build_parser():
    parser = cli.parser("worktree_task.py", "Sync a worker's worktree from the main tree, or merge it back.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sync", action="store_true", help="copy the main tree's uncommitted state into the worktree")
    mode.add_argument("--merge", action="store_true", help="copy the worker's declared files back into the main tree")
    parser.add_argument("--from", dest="source", required=True, metavar="DIR",
                        help="--sync: the main workspaces root; --merge: the worker's workspaces root")
    parser.add_argument("--worktree", metavar="DIR", help="--sync: a folder inside the worker's worktree")
    parser.add_argument("--to", metavar="DIR", help="--merge: the main workspaces root")
    parser.add_argument("--plan", help="--merge: the main plan entrypoint")
    parser.add_argument("--task", metavar="N", help="--merge: the task whose files the worker wrote")
    parser.add_argument("--cleanup", action="store_true",
                        help="--merge: then remove the worktree and delete its branch")
    return parser


def check_arguments(args, parser):
    given = {name for name in ("worktree", "to", "plan", "task") if getattr(args, name) is not None}
    if args.cleanup:
        given.add("cleanup")
    wanted = {"worktree"} if args.sync else {"to", "plan", "task"}
    allowed = wanted | (set() if args.sync else {"cleanup"})
    mode = "--sync" if args.sync else "--merge"
    if wanted - given:
        parser.error(f"{mode} needs {', '.join('--' + n for n in sorted(wanted - given))}")
    if given - allowed:
        parser.error(f"{mode} does not take {', '.join('--' + n for n in sorted(given - allowed))}")
    if args.merge and not re.fullmatch(r"[0-9]{1,9}", args.task):
        parser.error(f"--task is a task number, not `{args.task}`")
    for name in ("source", "worktree", "to"):
        value = getattr(args, name)
        if value is not None and not Path(value).is_dir():
            flag = "--from" if name == "source" else f"--{name}"
            parser.error(f"{flag} is not a directory: {value}")


# --- the two trees ----------------------------------------------------------------

@dataclass(frozen=True)
class Side:
    top: Path      # the git toplevel, resolved
    git_dir: Path
    common: Path


def side(path, rep, label):
    try:
        top = git.toplevel(path).resolve()
        git_dir, common = worktree.git_dirs(top)
    except git.GitError as exc:
        rep.add("WORKTREE_NOT_LINKED", f"the {label} `{path}` is not inside a git repository: {exc}")
        return None
    return Side(top, git_dir, common)


def linked_pair(main_dir, work_dir, rep):
    """(main Side, worktree Side), or None with WORKTREE_NOT_LINKED."""
    rep.ran("worktree-linked")
    main, work = side(main_dir, rep, "main tree"), side(work_dir, rep, "worktree")
    if main is None or work is None:
        return None
    if main.common != work.common:
        rep.add("WORKTREE_NOT_LINKED", f"{work.top} and {main.top} are not worktrees of one repository — their git "
                                       f"common dirs are {work.common} and {main.common}")
    elif work.git_dir == work.common:
        rep.add("WORKTREE_NOT_LINKED", f"{work.top} is the repository's main worktree, not a linked one — a worker "
                                       f"runs in a worktree `git worktree add` or Claude Code's isolation made")
    elif work.top == main.top:
        rep.add("WORKTREE_NOT_LINKED", f"{work.top} is the main tree itself, not a worker's worktree")
    report.debug("worktree_task.linked_pair", "sides", main=main.top, worktree=work.top, common=main.common)
    return None if rep.findings else (main, work)


def root_below(root, top):
    """The workspaces root relative to its git toplevel, as a POSIX string — "" when it is the toplevel."""
    try:
        rel = Path(root).resolve().relative_to(top)
    except ValueError:
        report.fail(report.EXIT_USAGE, f"{root} is not below its git toplevel {top}")
    return rel.as_posix() if rel.parts else ""


def runtime_prefix(root_rel):
    return f"{root_rel}/{RUNTIME}" if root_rel else RUNTIME


def excluded(rel, root_rel):
    return rel.startswith(runtime_prefix(root_rel)) or rel.startswith(worktree.CLAUDE_WORKTREES)


def inside_root(rel, root_rel):
    """`rel` (toplevel-relative) as a workspaces-root-relative path, or None when it is outside the root."""
    if not root_rel:
        return rel
    return rel[len(root_rel) + 1:] if rel.startswith(root_rel + "/") else None


def target(top, rel):
    parts = rel.split("/")
    if rel.startswith("/") or any(part in ("", ".", "..") for part in parts):
        raise TaskError(f"git printed `{rel}`, which is not a plain relative path")
    return top.joinpath(*parts)


# --- files ------------------------------------------------------------------------

def digest(path):
    """What a path holds, comparable across trees: sha256 of a file's bytes or a link's target, None when absent."""
    if not os.path.lexists(path):
        return None
    if os.path.islink(path):
        return "link:" + hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
    if path.is_dir():
        return "dir"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clear_for(dst):
    if os.path.isdir(dst) and not os.path.islink(dst):
        raise TaskError(f"{dst} is a folder; a file cannot replace it")
    dst.parent.mkdir(parents=True, exist_ok=True)


def copy_file(src, dst):
    """Copy bytes and mode bits through a temporary file beside `dst`, then os.replace.

    The temporary file is mkstemp's — created exclusively under an unpredictable name — so no link
    planted beside `dst` can redirect the write.
    """
    _clear_for(dst)
    tmp = None
    try:
        fd, name = tempfile.mkstemp(dir=dst.parent, prefix=f".{dst.name}.", suffix=".dgf.tmp")
        tmp = Path(name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(src.read_bytes())
        shutil.copymode(src, tmp)
        os.replace(tmp, dst)
    except OSError as exc:
        if tmp is not None and os.path.lexists(tmp):
            os.unlink(tmp)
        raise TaskError(f"cannot copy {src} to {dst}: {exc.strerror or exc}") from exc


def copy_link(src, dst):
    _clear_for(dst)
    try:
        if os.path.lexists(dst):
            os.unlink(dst)
        os.symlink(os.readlink(src), dst)
    except OSError as exc:
        raise TaskError(f"cannot copy the symlink {src} to {dst}: {exc.strerror or exc}") from exc


def remove_path(path):
    if not os.path.lexists(path):
        return
    if os.path.isdir(path) and not os.path.islink(path):
        raise TaskError(f"{path} is a folder; only a file is removed")
    try:
        os.unlink(path)
    except OSError as exc:
        raise TaskError(f"cannot remove {path}: {exc.strerror or exc}") from exc


def short(sha):
    return (sha or "?")[:12]


# --- --sync -----------------------------------------------------------------------

def tree_lines(main, work, root_rel):
    worker_root = work.top / root_rel if root_rel else work.top
    return [f"MAIN: {main.top}", f"WORKTREE: {work.top}", f"WORKTREE ROOT: {worker_root}"]


def move_base(main, work, rep, lines):
    """Bring the worktree to the main tree's HEAD, or refuse; returns the sha or None."""
    rep.ran("head")
    main_head, work_head = worktree.head(main.top), worktree.head(work.top)
    if work_head == main_head:
        lines.append(f"HEAD: {main_head}")
        return main_head
    own = worktree.status(work.top)
    if own:
        rep.add("WORKTREE_HEAD_MISMATCH", f"the worktree is at {short(work_head)} and the main tree at "
                                          f"{short(main_head)}, and the worktree has {len(own)} change(s) of its own "
                                          f"(first: {own[0][1]}) — moving it would lose them", file=str(work.top))
        return None
    worktree.reset_to(work.top, main_head)
    report.debug("worktree_task.move_base", "moved", worktree=work.top, frm=work_head, to=main_head)
    lines.append(f"HEAD: {main_head} (moved from {work_head})")
    return main_head


def copy_dirty(main, work, root_rel):
    """{toplevel-relative path: digest or None} for each path below the root the main tree changed."""
    files = {}
    for code, rel in worktree.status(main.top, root_rel or "."):
        if excluded(rel, root_rel):
            report.debug("worktree_task.sync", "excluded", path=rel)
            continue
        src, dst = target(main.top, rel), target(work.top, rel)
        if not os.path.lexists(src):
            remove_path(dst)
            files[rel] = None
        elif os.path.islink(src):
            copy_link(src, dst)
            files[rel] = digest(src)
        elif src.is_dir():
            report.debug("worktree_task.sync", "skipped a folder", path=rel, status=code)
            continue
        else:
            copy_file(src, dst)
            files[rel] = digest(src)
        report.debug("worktree_task.sync", "synced", path=rel, status=code, deleted=files[rel] is None)
    return files


def write_record(work, data):
    path = work.git_dir / RECORD
    tmp = path.with_name(f".{RECORD}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    report.debug("worktree_task.write_record", "written", path=path, files=len(data["files"]))


def sync(source, worktree_dir):
    rep, lines = report.Report(cli.display(worktree_dir)), []
    sides = linked_pair(source, worktree_dir, rep)
    if sides is None:
        return rep, lines
    main, work = sides
    root_rel = root_below(source, main.top)
    lines += tree_lines(main, work, root_rel)
    head = move_base(main, work, rep, lines)
    if head is None:
        return rep, lines
    rep.ran("sync")
    files = copy_dirty(main, work, root_rel)
    write_record(work, {"head": head, "main": str(main.top), "root": root_rel, "files": files})
    deleted = sum(1 for value in files.values() if value is None)
    lines.append(f"SYNCED: {len(files) - deleted} file(s), {deleted} deletion(s)")
    return rep, lines


# --- --merge ----------------------------------------------------------------------

def read_record(main, work, root_rel, rep):
    rep.ran("sync-record")
    path = work.git_dir / RECORD
    if not path.is_file():
        rep.add("WORKTREE_SYNC_MISSING", f"no sync record at {path} — the worker never ran `worktree_task.py "
                                         f"--sync`, so its base is unknown")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        rep.add("WORKTREE_SYNC_MISSING", f"the sync record {path} cannot be read: {exc}")
        return None
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict) or not isinstance(data.get("head"), str) or not isinstance(data.get("main"), str) \
            or not all(isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in files.items()):
        rep.add("WORKTREE_SYNC_MISSING", f"the sync record {path} is not one `--sync` wrote")
        return None
    if Path(data["main"]).resolve() != main.top or data.get("root", "") != root_rel:
        rep.add("WORKTREE_SYNC_MISSING", f"the sync record names {data['main']} root `{data.get('root', '')}`, not "
                                         f"{main.top} root `{root_rel}` — the worktree was synced from another tree")
        return None
    return data


def check_heads(main, work, record, rep):
    main_head, work_head = worktree.head(main.top), worktree.head(work.top)
    if main_head != record["head"]:
        rep.add("WORKTREE_HEAD_MISMATCH", f"the main tree's HEAD is {short(main_head)}, and the worktree was synced at "
                                          f"{short(record['head'])} — a commit landed since the sync",
                file=str(main.top))
    if work_head != record["head"]:
        rep.add("WORKTREE_HEAD_MISMATCH", f"the worktree's HEAD moved from {short(record['head'])} to "
                                          f"{short(work_head)} since the sync — a worker never commits",
                file=str(work.top))


def load_task(plan_path, task_id, rep):
    entry = plan.entrypoint(plan_path)
    try:
        parsed = plan.parse(entry)
    except plan.PlanFormatError as exc:
        rep.add("PLAN_UNREADABLE", exc.message, line=exc.line, file=cli.display(entry))
        return None
    fmt = parsed.header.get("plan_format")
    if fmt not in (None, "", plan.SUPPORTED_FORMAT):
        rep.add("PLAN_FORMAT_UNSUPPORTED", f"`plan_format: {fmt}` — this plugin reads format {plan.SUPPORTED_FORMAT} "
                                           f"only", line=parsed.header_lines.get("plan_format"),
                file=cli.display(entry))
        return None
    task = next((t for t in parsed.tasks if t.id == task_id), None)
    if task is None:
        report.fail(report.EXIT_USAGE, f"Task {task_id} is not a task of {entry}")
    return task


def worker_changes(work, root_rel, record):
    """[(A|M|D, toplevel-relative path)] — where the worktree differs from what --sync left."""
    files = record["files"]
    status = {rel: code for code, rel in worktree.status(work.top)}
    changes = []
    for rel in sorted(set(status) | set(files)):
        if excluded(rel, root_rel):
            continue
        path = target(work.top, rel)
        if rel in files:
            if digest(path) == files[rel]:
                continue
            base_absent = files[rel] is None
        else:
            base_absent = status[rel] == "??" or status[rel][0] == "A"
        exists = os.path.lexists(path)
        if not exists and base_absent:
            continue
        changes.append(("D" if not exists else "A" if base_absent else "M", rel))
    report.debug("worktree_task.worker_changes", "changes", count=len(changes))
    return changes


def scope_problem(kind, shown, path, task, plan_rel):
    """Why a change may not be merged, or None."""
    if shown is None:
        return "is outside the workspaces root — a worker changes only its task's files"
    if os.path.islink(path):
        return "is a symlink — a symlink is never merged"
    if shown == plan_rel:
        return "is the plan — only the coordinator ticks it"
    if kind == "D":
        if shown in task.deletes:
            return None
        if shown in task.files:
            return f"was deleted, but Task {task.id} lists it in `files`: it must be added or modified"
        return f"was deleted, and Task {task.id} does not list it in `deletes`"
    if shown in task.files:
        return None
    if shown in task.deletes:
        return (f"was {'added' if kind == 'A' else 'modified'}, but Task {task.id} lists it in `deletes`: it must be "
                f"deleted")
    return f"was {'added' if kind == 'A' else 'modified'}, and Task {task.id} does not list it in `files`"


def plan_relative(plan_path, root):
    try:
        return plan.entrypoint(plan_path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return None


def check_scope(changes, work, root_rel, task, plan_rel, rep):
    rep.ran("scope")
    for kind, rel in changes:
        shown = inside_root(rel, root_rel)
        why = scope_problem(kind, shown, target(work.top, rel), task, plan_rel)
        if why:
            rep.add("WORKTREE_UNDECLARED_FILE", f"{shown or rel} {why}", file=shown or rel)


def main_is_base(kind, rel, main, files):
    """True when the main tree's copy of `rel` is still the worker's base — never judged from git's status alone.

    A synced path: its digest is the recorded one. An addition: nothing is at the path — `lexists`, so
    a file git ignores, or one whose name differs only in case on a case-insensitive disk, counts. A
    modification or deletion: the file holds HEAD's blob (worktree.matches_head), which an
    assume-unchanged or skip-worktree bit cannot hide.
    """
    path = target(main.top, rel)
    if rel in files:
        return digest(path) == files[rel]
    if kind == "A":
        return not os.path.lexists(path)
    return worktree.matches_head(main.top, rel)


def check_main(changes, main, root_rel, record, rep):
    rep.ran("main-unchanged")
    for kind, rel in changes:
        if not main_is_base(kind, rel, main, record["files"]):
            shown = inside_root(rel, root_rel) or rel
            rep.add("WORKTREE_MAIN_CHANGED", f"{shown} changed in the main tree since the sync — merging the "
                                             f"worker's {kind} would overwrite it", file=shown)


def apply_changes(changes, main, work, root_rel, lines):
    for kind, rel in changes:
        dst = target(main.top, rel)
        if kind == "D":
            remove_path(dst)
        else:
            copy_file(target(work.top, rel), dst)
        lines.append(f"MERGED: {kind} {inside_root(rel, root_rel)}")
        report.debug("worktree_task.merge", "merged", kind=kind, path=rel)


def clean_up(main, work, lines):
    entry = next((e for e in worktree.worktrees(main.top) if e.path == work.top), None)
    if entry is not None and entry.locked:
        lines.append(f"REMOVED: none — {work.top} is locked")
        return
    try:
        worktree.remove(main.top, work.top)
    except git.GitError as exc:
        lines.append(f"REMOVED: none — {work.top}: {exc}")
        return
    if entry is None or entry.branch is None:
        lines.append(f"REMOVED: {work.top} (detached)")
        return
    try:
        worktree.delete_branch(main.top, entry.branch)
    except git.GitError as exc:
        lines.append(f"REMOVED: {work.top} (its branch {entry.branch} is kept: {exc})")
        return
    lines.append(f"REMOVED: {work.top} ({entry.branch})")


def merge(source, dest, plan_path, task_id, cleanup=False):
    rep, lines = report.Report(cli.display(source)), []
    sides = linked_pair(dest, source, rep)
    if sides is None:
        return rep, lines
    main, work = sides
    root_rel = root_below(dest, main.top)
    if root_below(source, work.top) != root_rel:
        report.fail(report.EXIT_USAGE, f"--from is `{root_below(source, work.top)}` below its worktree and --to is "
                                       f"`{root_rel}` below the main tree — they are not one workspaces root")
    lines += tree_lines(main, work, root_rel)
    task = load_task(plan_path, task_id, rep)
    record = read_record(main, work, root_rel, rep) if task is not None else None
    if record is None:
        return rep, lines
    check_heads(main, work, record, rep)
    if rep.findings:
        return rep, lines
    changes = worker_changes(work, root_rel, record)
    check_scope(changes, work, root_rel, task, plan_relative(plan_path, dest), rep)
    check_main(changes, main, root_rel, record, rep)
    if rep.findings:
        return rep, lines
    rep.ran("merge")
    try:
        apply_changes(changes, main, work, root_rel, lines)
    except TaskError as exc:
        merged = [line[len("MERGED: "):] for line in lines if line.startswith("MERGED: ")]
        raise TaskError(f"{exc} — merged before the failure: {', '.join(merged) or 'nothing'}") from exc
    if cleanup:
        clean_up(main, work, lines)
    return rep, lines


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.verbose:
        report.set_verbose()
    check_arguments(args, parser)
    if not git.available():
        report.fail(report.EXIT_USAGE, "git is not installed — a worktree needs git")
    try:
        if args.sync:
            rep, lines = sync(args.source, args.worktree)
        else:
            rep, lines = merge(args.source, args.to, args.plan, int(args.task), args.cleanup)
    except (git.GitError, TaskError) as exc:
        report.fail(report.EXIT_USAGE, f"worktree_task.py: {exc}")
    return report.render([rep], header=HEADER, lines=lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
