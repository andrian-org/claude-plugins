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

The resolvers follow knowledge/process-model.md §2, branch for branch: a process
`action` becomes a workflow name (§2.3), a workflow name a path (§2.2), and a
process name a path (§2.5). A reference the *selected* workspace decides is
exact when the owning workspace is an application. From webasm it is decided by
whichever application runs it, so it is resolved in every application and is
app-dependent unless all of them have it (ADR 0014, D2).
"""

import os
from dataclasses import dataclass, field
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
        return Path(os.path.abspath(override))
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


def workspace_names(root):
    """Every workspace under `root` by name: the applications, plus webasm when it has an FM/."""
    names = set(applications(root))
    if exact_child(root, BASE_WORKSPACE)[0] == OK and exact_child(Path(root) / BASE_WORKSPACE, FM)[0] == OK:
        names.add(BASE_WORKSPACE)
    return names


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


# --- resolver results ---------------------------------------------------------

@dataclass(frozen=True)
class Resolved:
    path: str         # relative to the workspaces root; `<app>/…` when `apps` is set
    apps: tuple = ()  # a webasm reference found in every application: each of them


@dataclass(frozen=True)
class Unresolved:
    path: str
    reason: str = ""  # why the engine cannot load it, when the path alone does not say


@dataclass(frozen=True)
class CaseOnly:
    path: str    # the path the reference builds
    actual: str  # the path on disk, which differs only in case


@dataclass(frozen=True)
class AppDependent:
    path: str  # the path under each application, with <app> in place of its name
    resolved_in: list = field(default_factory=list)
    missing_in: list = field(default_factory=list)


BASE_PREFIX = "BASE:"
BASE_SCOPE = "base"
SELECTED_SCOPE = "selected"
ROOTED_SCOPE = "rooted"  # a remainder starting with `/`: Path.Combine discards the workspace
ROOTED_REASON = ("a name starting with `/` is rooted, so Path.Combine drops the workspace path and the engine "
                 "looks outside every workspace")


def is_base(owner):
    return owner is not None and Path(owner).name == BASE_WORKSPACE


def _segments(name):
    """A relative name's path segments: empty segments collapse, as Path.Combine joins them.

    A name that starts with `/` is not relative — the location functions route it
    to ROOTED_SCOPE before splitting.
    """
    return [segment for segment in name.split("/") if segment]


def _relative(path, root):
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _resolve(scope, parts, owner, root, module_fn, **trace):
    """Look `parts` up in webasm (BASE_SCOPE) or in the selected workspace (SELECTED_SCOPE)."""
    root = Path(os.path.abspath(root))
    if scope == ROOTED_SCOPE:
        result = Unresolved("/" + "/".join(parts), ROOTED_REASON)
        report.debug(module_fn, "rooted", result="Unresolved", **trace)
        return result
    if scope == BASE_SCOPE or not is_base(owner):
        base = root / BASE_WORKSPACE if scope == BASE_SCOPE else Path(owner)
        shown = "/".join([base.name] + parts)
        status, actual = exact_file(base, parts)
        result = (Resolved(shown) if status == OK else
                  CaseOnly(shown, _relative(actual, root)) if status == CASE_ONLY else
                  Unresolved(shown))
        report.debug(module_fn, "resolved", candidates=[shown], result=type(result).__name__, **trace)
        return result
    resolved_in, missing_in = [], []
    for app in applications(root):
        (resolved_in if exact_file(root / app, parts)[0] == OK else missing_in).append(app)
    shown = "/".join(["<app>"] + parts)
    result = (Resolved(shown, tuple(resolved_in)) if resolved_in and not missing_in else
              AppDependent(shown, resolved_in, missing_in))
    report.debug(module_fn, "per application", candidates=[shown], resolved=",".join(resolved_in),
                 missing=",".join(missing_in), result=type(result).__name__, **trace)
    return result


# --- workflow references ------------------------------------------------------

def presentation(value):
    """(kind, name) of a process `action`, as StateProcessClient.ResolveUiSettings splits it.

    The part before the first `;` is split on `:`; the first piece is the kind and
    the second the name, except that `BASE` or `/BASE` followed by a third piece is
    rejoined, slashes removed, as `BASE:<third>`. No `:` past the first character
    means no kind. The kind is compared exactly: `workflow:X` is not a workflow.
    """
    if not value:
        return "", ""
    if value.find(";") > 0:
        value = value.split(";")[0]
    if value.find(":") <= 0:
        return "", ""
    pieces = value.split(":")
    name = pieces[1]
    if (name.startswith("BASE") or name.startswith("/BASE")) and len(pieces) >= 3:
        name = name.replace("/", "") + ":" + pieces[2]
    return pieces[0], name


def process_reference(process_name, owner):
    """How a process folder is referenced: `P` in an application, `BASE:P` in webasm."""
    return BASE_PREFIX + process_name if is_base(owner) else process_name


def action_workflow_name(name, process_ref):
    """The workflow name StateProcessClient.RenderUiControlAsync loads for an action's name.

    `BASE:X` and `/X` are kept; any other name is process-local, `<process>/X`.
    """
    if name.startswith(BASE_PREFIX):
        return name
    if process_ref is not None and not name.startswith("/"):
        return f"{process_ref}/{name}"
    return name


def workflow_location(name):
    """(scope, parts under the workspace) for a workflow name, as WorkflowManager.GetWorkPath builds it."""
    slash = name.find("/")
    if slash > 0:
        if name.startswith(BASE_PREFIX):
            rest = name[len(BASE_PREFIX):]
            if rest.startswith("/"):
                return ROOTED_SCOPE, _segments(rest) + ["_workflow.xml"]
            return BASE_SCOPE, [FM, "_PROCESS"] + _segments(rest) + ["_workflow.xml"]
        return SELECTED_SCOPE, [FM, "_PROCESS"] + _segments(name) + ["_workflow.xml"]
    if slash == 0:
        name = name[1:]
        if name.startswith("/"):
            return ROOTED_SCOPE, _segments(name) + ["_workflow.xml"]
    elif name.startswith(BASE_PREFIX):
        return BASE_SCOPE, [FM, "_WORKFLOW"] + _segments(name[len(BASE_PREFIX):]) + ["_workflow.xml"]
    return SELECTED_SCOPE, [FM, "_WORKFLOW"] + _segments(name) + ["_workflow.xml"]


def resolve_workflow_name(name, owner, root, module_fn="workspace.resolve_workflow_name", **trace):
    """Resolve a workflow name exactly as WorkflowManager loads it."""
    scope, parts = workflow_location(name)
    return _resolve(scope, parts, owner, root, module_fn, value=name, form=scope, **trace)


def resolve_workflow_ref(value, process_ref, owner, root):
    """Resolve a process `action` (or a MultiTask action); None when it is not a workflow reference."""
    kind, name = presentation(value)
    if kind != "WORKFLOW":
        return None
    if not name:
        # RenderUiControlAsync reads name[0], which throws on an empty name.
        return Unresolved("", "has an empty workflow name — the engine throws on it")
    loaded = action_workflow_name(name, process_ref)
    return resolve_workflow_name(loaded, owner, root, "workspace.resolve_workflow_ref", action=value)


def resolve_validation_flow(value, owner, root):
    """Resolve `Process/@validationFlow`: a workflow name used verbatim (process-model.md §2.4)."""
    return resolve_workflow_name(value, owner, root, "workspace.resolve_validation_flow")


# --- process references -------------------------------------------------------

def process_location(name):
    """(scope, parts under the workspace) for a process name, as ProcessManager.GetWorkPath builds it."""
    if name.startswith(BASE_PREFIX):
        rest = name.replace(BASE_PREFIX, "")
        if rest.startswith("/"):
            return ROOTED_SCOPE, _segments(rest) + ["process.xml"]
        return BASE_SCOPE, [FM, "_PROCESS"] + _segments(rest) + ["process.xml"]
    if name.startswith("/"):
        return ROOTED_SCOPE, _segments(name) + ["process.xml"]
    return SELECTED_SCOPE, [FM, "_PROCESS"] + _segments(name) + ["process.xml"]


def resolve_process(name, owner, root):
    """Resolve a process name — a StateProcess step's `process` — to its process.xml."""
    scope, parts = process_location(name)
    return _resolve(scope, parts, owner, root, "workspace.resolve_process", value=name, form=scope)


# --- component file references ------------------------------------------------

def component_location(name, member):
    """(scope, parts under the workspace) for a component file, as ComponentFileLoadService builds it.

    `BASE:` is matched in any case here, unlike the workflow and process managers
    (knowledge/json-reader.md §2.1).
    """
    if name[:len(BASE_PREFIX)].lower() == BASE_PREFIX.lower():
        rest = name[len(BASE_PREFIX):]
        if rest.startswith("/"):
            return ROOTED_SCOPE, _segments(rest + ".json")
        return BASE_SCOPE, [FM, "_COMPONENTS", member] + _segments(rest + ".json")
    if name.startswith("/"):
        return ROOTED_SCOPE, _segments(name + ".json")
    return SELECTED_SCOPE, [FM, "_COMPONENTS", member] + _segments(name + ".json")


def resolve_component_file(name, member, owner, root):
    """Resolve a component file reference: a layout child's `path`, or a ReferenceComponent's target."""
    scope, parts = component_location(name, member)
    return _resolve(scope, parts, owner, root, "workspace.resolve_component_file", value=name, form=scope)
