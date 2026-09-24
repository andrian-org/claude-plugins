"""workspace.py — the workspaces-root model and exact-case file lookup (DD10, ADR 0014 §2).

A file's owning workspace is the directory directly above its `FM/`, and the
workspaces root is that directory's parent, unless --workspaces-root overrides
it. The base workspace is `webasm` (knowledge/composition-specs.md); every other
directory under the root that has an `FM/` is an application workspace.

Existence is exact-case. The runtime runs on Linux, where a name matches only
byte for byte, while APFS and NTFS match regardless of case — so a lookup
compares directory entries (os.scandir), never Path.exists(). A name that
matches only when case is ignored is reported as such, not as present. No I/O
beyond os.scandir and is_file. Stdlib only.
"""

import os
from pathlib import Path

from . import report

BASE_WORKSPACE = "webasm"
FM = "FM"
OK = "ok"
CASE_ONLY = "case-only"
MISSING = "missing"


def owning_workspace(path):
    """The workspace directory `path` lives in — the one directly above FM/ — or None."""
    parts = Path(os.path.abspath(path)).parts
    for index in range(len(parts) - 1, 0, -1):
        if parts[index] == FM:
            return Path(*parts[:index])
    return None


def workspaces_root(path, override=None):
    """The workspaces root: `override`, else the owning workspace's parent, else None."""
    if override:
        return Path(override)
    owner = owning_workspace(path)
    return owner.parent if owner is not None else None


def applications(root):
    """The application workspaces under `root`: every directory with an FM/, but webasm."""
    found = []
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name)
    except OSError:
        return found
    for entry in entries:
        if entry.is_dir() and entry.name != BASE_WORKSPACE and exact_child(entry.path, FM)[0] == OK:
            found.append(entry.name)
    return found


def exact_child(directory, name):
    """(OK | CASE_ONLY | MISSING, the entry's actual name or None) for `name` in `directory`."""
    try:
        names = [entry.name for entry in os.scandir(directory)]
    except OSError:
        return MISSING, None
    if name in names:
        return OK, name
    folded = name.lower()
    actual = next((n for n in sorted(names) if n.lower() == folded), None)
    return (CASE_ONLY, actual) if actual is not None else (MISSING, None)


def exact_file(base, parts):
    """(OK | CASE_ONLY | MISSING, the path as it exists) for the file base/parts[0]/….

    Walks one segment at a time. A segment that matches only case-insensitively
    makes the result CASE_ONLY, and the walk continues through the actual name so
    a missing file further down still reads MISSING.
    """
    current, status = Path(base), OK
    for index, name in enumerate(parts):
        found, actual = exact_child(current, name)
        if found == MISSING:
            report.debug("workspace.exact_file", "missing", base=base, segment=name)
            return MISSING, None
        if found == CASE_ONLY:
            status = CASE_ONLY
        current = current / actual
        if index < len(parts) - 1 and not current.is_dir():
            return MISSING, None
    if not current.is_file():
        return MISSING, None
    return status, current
