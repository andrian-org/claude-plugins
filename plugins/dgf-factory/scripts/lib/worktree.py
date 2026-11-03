"""worktree.py — the git calls a worker's worktree needs, with the three that change a repository (ADR 0033 §3).

lib/git.py stays read-only by contract; this module holds what parallel
execution adds to it. Read-only: each tree's git directories, its HEAD, its
status, the repository's worktree list, and whether a file on disk holds what
HEAD holds at its path (`matches_head`). Changing: moving a worktree's own
branch to a commit (`reset --hard`), removing a worktree, and deleting its
branch. Only worktree_task.py calls the changing three.

Every call goes through git._run — `git -C <dir> …` with an argument list,
never a shell, traced under --verbose — and a failure raises git.GitError.
Paths `status` returns are relative to the git toplevel, not to `<dir>`, with
`/` separators: porcelain output ignores the working directory. Stdlib only.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from . import git, report

# A Claude Code subagent's worktrees live here, below the repository's toplevel; the main tree's status
# lists each one as an untracked folder.
CLAUDE_WORKTREES = ".claude/worktrees/"


@dataclass(frozen=True)
class Entry:
    path: Path            # the worktree's folder, resolved
    head: object = None   # its HEAD sha, or None
    branch: object = None # its branch without `refs/heads/`, or None when detached
    locked: bool = False
    bare: bool = False


def _lines(raw):
    return [line for line in os.fsdecode(raw).splitlines() if line.strip()]


def git_dirs(path):
    """(git dir, common dir), both absolute and resolved. A linked worktree's two differ."""
    lines = _lines(git._run(path, ["rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir"],
                            "worktree.git_dirs"))
    if len(lines) != 2:
        raise git.GitError(f"`git rev-parse --git-dir --git-common-dir` printed {len(lines)} line(s), not 2")
    return Path(lines[0]).resolve(), Path(lines[1]).resolve()


def is_linked(path):
    """True when `path` is inside a linked worktree, not the repository's main one."""
    git_dir, common = git_dirs(path)
    return git_dir != common


def head(path):
    """The sha HEAD names."""
    sha = os.fsdecode(git._run(path, ["rev-parse", "--verify", "HEAD"], "worktree.head")).strip()
    if not sha:
        raise git.GitError("`git rev-parse --verify HEAD` printed nothing")
    return sha


def status(path, scope="."):
    """[(XY, toplevel-relative path)] for every change below `scope` — tracked, staged and untracked.

    `git --no-optional-locks status --porcelain=v1 -z --untracked-files=all --no-renames -- <scope>`.
    `scope` is read relative to `path`. Ignored files are left out, as git leaves them out. A rename
    reads as a deletion and an addition. An entry ending in `/` — a nested repository or a linked
    worktree's folder — and anything under `.claude/worktrees/` are skipped.
    """
    raw = git._run(path, ["--no-optional-locks", "status", "--porcelain=v1", "-z", "--untracked-files=all",
                          "--no-renames", "--", scope], "worktree.status")
    entries = []
    for field in git._fields(raw):
        code, rel = field[:2], field[3:]
        if not rel or rel.endswith("/") or rel.startswith(CLAUDE_WORKTREES):
            report.debug("worktree.status", "skipped", entry=field)
            continue
        entries.append((code, rel))
    report.debug("worktree.status", "status", path=path, scope=scope, entries=len(entries))
    return entries


def worktrees(path):
    """[Entry] for every worktree of the repository `path` is in, from `worktree list --porcelain -z`."""
    raw = git._run(path, ["worktree", "list", "--porcelain", "-z"], "worktree.worktrees")
    entries, current = [], None
    for field in os.fsdecode(raw).split("\0"):
        if not field:
            if current:
                entries.append(Entry(**current))
            current = None
            continue
        key, _, value = field.partition(" ")
        if key == "worktree":
            current = {"path": Path(value).resolve()}
        elif current is None:
            continue
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value[len("refs/heads/"):] if value.startswith("refs/heads/") else value
        elif key == "locked":
            current["locked"] = True
        elif key == "bare":
            current["bare"] = True
    if current:
        entries.append(Entry(**current))
    report.debug("worktree.worktrees", "listed", worktrees=len(entries))
    return entries


def head_entry(top, rel):
    """(mode, blob sha) of HEAD's entry at `rel` (toplevel-relative), or None when HEAD has no blob there."""
    raw = git._run(top, ["--literal-pathspecs", "ls-tree", "-z", "HEAD", "--", rel], "worktree.head_entry")
    for field in git._fields(raw):
        meta, _, path = field.partition("\t")
        parts = meta.split()
        if path == rel and len(parts) == 3 and parts[1] == "blob":
            return parts[0], parts[2]
    return None


def matches_head(top, rel):
    """True when the file at `<top>/<rel>` holds what HEAD holds at `rel`, as git would store it.

    Never reads git's index or status, so it cannot be fooled by a path git ignores, an
    assume-unchanged or a skip-worktree bit. A regular file is hashed with `git hash-object
    --path=<rel>`, which applies the repository's filters (core.autocrlf, .gitattributes) as a commit
    would; a symlink is compared by its target. Absent, a folder, or a kind HEAD does not hold → False.
    """
    entry = head_entry(top, rel)
    path = top.joinpath(*rel.split("/"))
    if entry is None or not os.path.lexists(path):
        return False
    mode, sha = entry
    if os.path.islink(path):
        if mode != git.SYMLINK_MODE:
            return False
        stored = git._run(top, ["hash-object", "--no-filters", "--stdin"], "worktree.matches_head",
                          stdin=os.fsencode(os.readlink(path)))
    elif path.is_file() and mode in ("100644", "100755"):
        stored = git._run(top, ["hash-object", f"--path={rel}", "--", str(path)], "worktree.matches_head")
    else:
        return False
    return os.fsdecode(stored).strip() == sha


# --- the three that change a repository -------------------------------------------

def reset_to(path, sha):
    """Move the worktree's own branch, its index and its files to `sha`: `git reset -q --hard <sha>`."""
    git._run(path, ["reset", "-q", "--hard", git._ref(sha)], "worktree.reset_to")


def remove(main, worktree_path):
    """`git worktree remove --force <worktree>`, run from the main tree. A locked worktree raises GitError."""
    git._run(main, ["worktree", "remove", "--force", str(worktree_path)], "worktree.remove")


def delete_branch(main, branch):
    """`git branch -D <branch>`."""
    git._run(main, ["branch", "-D", git._ref(branch)], "worktree.delete_branch")
