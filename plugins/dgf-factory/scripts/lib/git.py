"""git.py — the read-only git calls the plan and change checks make (ADR 0017 §5, ADR 0018 §1).

Every call is `git -C <dir> …` with an argument list, never a shell, and a ref
argument that starts with `-` is refused before git can read it as an option. `<dir>` is
normally the workspaces root, and every path this module takes or returns is
relative to it, with `/` separators: `git diff --relative` and `ls-files` limit
themselves to that directory, `ls-tree` lists only below it, and an object path
written `<ref>:./<path>` is read relative to it. Nothing here writes to the
repository, fetches, or changes the working tree; `materialise` writes only into
the directory it is given.

A failure raises GitError(message). Callers turn it into a `NOT RUN` line or
report.fail(3, …), never a traceback. Every call is traced with its argv and exit
code under --verbose. Stdlib only.
"""

import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from . import report

SYMLINK_MODE = "120000"
SUBMODULE_MODE = "160000"


class GitError(Exception):
    """A git call failed, or its output could not be read."""


@dataclass(frozen=True)
class Change:
    status: str  # A, M, D or R; a type change reads as M
    path: str    # relative to the directory given, `/`-separated
    old: object = None  # the path before a rename, else None


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    kind: str   # blob, tree or commit
    sha: str
    path: str


def available():
    return shutil.which("git") is not None


def _run(path, args, module_fn, stdin=None):
    argv = ["git", "-C", str(path), *args]
    try:
        proc = subprocess.run(argv, input=stdin, capture_output=True, check=False)
    except OSError as exc:
        raise GitError(f"cannot run git: {exc.strerror or exc}") from exc
    report.debug(module_fn, "git", argv=" ".join(argv[3:]), exit=proc.returncode)
    if proc.returncode != 0:
        detail = os.fsdecode(proc.stderr).strip().splitlines()
        raise GitError(f"`git {' '.join(args[:2])}` failed: {detail[-1] if detail else f'exit {proc.returncode}'}")
    return proc.stdout


def _ref(ref):
    """`ref`, unless git would read it as an option: then GitError (a second guard behind the scripts)."""
    if str(ref).startswith("-"):
        report.debug("git._ref", "refused", ref=ref)
        raise GitError(f"`{ref}` is not a ref: it starts with `-`")
    return ref


def _text(raw):
    return os.fsdecode(raw).strip()


def _fields(raw):
    """NUL-separated fields, the empty trailing one dropped."""
    return [os.fsdecode(part) for part in raw.split(b"\0") if part]


def toplevel(path):
    return Path(_text(_run(path, ["rev-parse", "--show-toplevel"], "git.toplevel")))


def current_branch(path):
    """The checked-out branch, or None on a detached HEAD."""
    return _text(_run(path, ["branch", "--show-current"], "git.current_branch")) or None


def merge_base(path, ref):
    """The merge-base of HEAD and `ref`; GitError when there is none."""
    sha = _text(_run(path, ["merge-base", "HEAD", _ref(ref)], "git.merge_base"))
    if not sha:
        raise GitError(f"HEAD and `{ref}` have no merge-base")
    return sha


def changed(path, base):
    """[Change]: the working tree against `base`, plus untracked files as A, below `path`."""
    raw = _run(path, ["diff", "--name-status", "-M", "-z", "--relative", "--no-ext-diff", _ref(base), "--"],
               "git.changed")
    changes = _parse_name_status(_fields(raw))
    untracked = _run(path, ["ls-files", "--others", "--exclude-standard", "-z", "--", "."], "git.changed")
    changes += [Change("A", rel) for rel in _fields(untracked)]
    report.debug("git.changed", "changed set", base=base, files=len(changes))
    return changes


def _parse_name_status(fields):
    changes, index = [], 0
    while index < len(fields):
        status = fields[index][:1]
        if status in ("R", "C"):
            old, new = fields[index + 1], fields[index + 2]
            changes.append(Change("R", new, old) if status == "R" else Change("A", new))
            index += 3
            continue
        changes.append(Change("M" if status in ("T", "U") else status, fields[index + 1]))
        index += 2
    return changes


def refs(path):
    """[(ref name, commit sha)] for every local and remote-tracking branch; symbolic refs skipped."""
    raw = _run(path, ["for-each-ref", "--format=%(refname)%00%(objectname)%00%(symref)",
                      "refs/heads", "refs/remotes"], "git.refs")
    found = []
    for line in os.fsdecode(raw).splitlines():
        name, sha, symref = (line.split("\0") + ["", ""])[:3]
        if name and not symref:
            found.append((name, sha))
    return found


def ls_tree(path, ref, prefix="."):
    """[TreeEntry] at `ref`, recursively, below `path`/`prefix`; paths relative to `path`."""
    raw = _run(path, ["ls-tree", "-r", "-z", _ref(ref), "--", prefix], "git.ls_tree")
    entries = []
    for field in _fields(raw):
        meta, _, rel = field.partition("\t")
        mode, kind, sha = meta.split(" ")
        entries.append(TreeEntry(mode, kind, sha, rel))
    return entries


def show(path, ref, relpath=None):
    """The bytes of `ref:./relpath` (a path relative to `path`), or of the object `ref` itself."""
    spec = f"{_ref(ref)}:./{relpath}" if relpath else _ref(ref)
    return _run(path, ["cat-file", "blob", spec], "git.show")


def materialise(path, commit, dest):
    """Write the blobs below `path` at `commit` into `dest`, blob by blob (ADR 0018 §1).

    Not `git archive`: its export attributes drop and rewrite files. Symlinks and
    submodules are skipped and counted. A path that would land outside `dest`
    raises GitError. Returns {"blobs", "symlinks", "submodules"}.
    """
    dest = Path(dest).resolve()
    _ref(commit)
    counts = {"blobs": 0, "symlinks": 0, "submodules": 0}
    blobs = []
    for entry in ls_tree(path, commit):
        if entry.mode == SYMLINK_MODE:
            counts["symlinks"] += 1
        elif entry.mode == SUBMODULE_MODE or entry.kind != "blob":
            counts["submodules"] += 1
        else:
            blobs.append((entry.sha, _inside(dest, entry.path)))
    batch = _cat_batch(path, [sha for sha, _ in blobs])
    try:
        for (_, target), content in zip(blobs, batch):
            _write(target, content)
            counts["blobs"] += 1
    finally:
        batch.close()  # stops git before its pipes can fill, when a write or a read failed
    report.debug("git.materialise", "wrote the base tree", commit=commit, dest=dest, **counts)
    return counts


def _inside(dest, rel):
    parts = rel.split("/")
    if rel.startswith("/") or any(part in ("", ".", "..") for part in parts):
        raise GitError(f"refusing to write `{rel}`: it is not a plain relative path")
    target = dest.joinpath(*parts)
    if os.path.commonpath([str(dest), os.path.normpath(str(target))]) != str(dest):
        raise GitError(f"refusing to write `{rel}`: it lands outside {dest}")
    return target


def _write(target, content):
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    except OSError as exc:
        raise GitError(f"cannot write the base tree at {target}: {exc.strerror or exc}") from exc


def _cat_batch(path, shas):
    """Yield each object's bytes, in order, from one `git cat-file --batch`."""
    if not shas:
        return
    argv = ["git", "-C", str(path), "cat-file", "--batch"]
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise GitError(f"cannot run git: {exc.strerror or exc}") from exc
    feeder = threading.Thread(target=_feed, args=(proc.stdin, shas), daemon=True)
    feeder.start()
    finished = False
    try:
        for sha in shas:
            yield _read_object(proc.stdout, sha)
        finished = True
    finally:
        if not finished:
            proc.kill()  # nobody reads git's output any more: stop it, so the feeder cannot block
        proc.stdout.close()
        feeder.join()
        proc.stderr.close()
        code = proc.wait()
        report.debug("git.materialise", "git", argv="cat-file --batch", objects=len(shas), exit=code)


def _feed(stdin, shas):
    try:
        stdin.write("".join(f"{sha}\n" for sha in shas).encode("ascii"))
    except BrokenPipeError:
        pass
    finally:
        stdin.close()


def _read_object(stream, sha):
    header = stream.readline().decode("ascii", "replace").split()
    if len(header) != 3 or header[1] != "blob":
        raise GitError(f"`git cat-file --batch` returned {' '.join(header) or 'nothing'} for {sha}")
    size = int(header[2])
    content = stream.read(size)
    if len(content) != size or stream.read(1) != b"\n":
        raise GitError(f"`git cat-file --batch` ended early while reading {sha}")
    return content
