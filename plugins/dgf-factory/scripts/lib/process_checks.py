"""process_checks.py — ADR 0014 §2's semantic checks for processes and the workflows that drive them.

Every check reads files under the workspaces root only — no database, no
engine — and follows knowledge/process-model.md:

- dead-transition: every `Transition/@state` under `OnStart` and `States/State`,
  and every `OnTimeout/@state`, names a declared state or the reserved `End`
  (§3), compared ordinally. `OnStart` is a State in the model, so its own
  `OnTimeout` counts too.
- unreachable-state: every declared state is reachable, through transitions and
  timeouts, from the entry set — `OnStart`'s transitions, every `OnTimeout`
  target, and the `state` of every `CHANGE_STATE` step and every non-empty
  `state` of a `START` step that names this process anywhere under the root.
  `applyforstates` are source states, never entries. A warning.
- workflow-reference: every `WORKFLOW:` `@action` on `OnStart`, a `State` or a
  `Transition`, and every `TaskGroup` action of a MultiTask settings file beside
  the process, resolves (§2.3, §2.7).
- validation-flow: `Process/@validationFlow` resolves, verbatim (§2.4).
- change-state-target: every workflow `StateProcess` step whose `mode` is
  exactly `CHANGE_STATE` names a process that resolves (§2.5–2.6), and its
  `state` and each non-empty `;`-token of `applyforstates`, untrimmed, is a
  declared state of that process or `End`.

Element and attribute names are the ones XmlSerializer binds, so they are
matched exactly. Resolution is workspace.py's. Requires lxml.
"""

import os
from collections import Counter
from pathlib import Path

from lxml import etree

from . import cli, family, report, workspace

END = "End"
CHANGE_STATE = "CHANGE_STATE"
START = "START"
WORKFLOW_KIND = "WORKFLOW"
PROCESS_FILE = "process.xml"
WORKFLOW_FILE = "_workflow.xml"
TASK_GROUP_ACTIONS = ("action", "expiredaction", "postviewaction")
SEMANTIC_CHECKS = ("dead-transition", "unreachable-state", "workflow-reference", "validation-flow")

_ENTRY_CACHE = {}
_DECLARED_CACHE = {}


# --- files under the root -----------------------------------------------------

def parse(path):
    """The lxml tree of `path`, read from bytes, or None when it does not parse."""
    try:
        return etree.parse(str(path), family.xml_parser())
    except (etree.XMLSyntaxError, OSError) as exc:
        report.debug("process_checks.parse", "unparsable", file=path, error=str(exc).split("\n")[0])
        return None


def _entries(directory):
    try:
        return sorted(os.scandir(directory), key=lambda e: e.name)
    except OSError:
        return []


def workspaces_under(root):
    """Every workspace under `root` with an FM/, webasm included, by name."""
    return [e.name for e in _entries(root) if e.is_dir() and workspace.exact_child(e.path, workspace.FM)[0] == workspace.OK]


def processes_under(root):
    """Every `<ws>/FM/_PROCESS/<P>/process.xml` under `root`."""
    found = []
    for ws in workspaces_under(root):
        for entry in _entries(Path(root) / ws / workspace.FM / "_PROCESS"):
            candidate = Path(entry.path) / PROCESS_FILE
            if entry.is_dir() and workspace.exact_child(entry.path, PROCESS_FILE)[0] == workspace.OK:
                found.append(candidate)
    return found


def workflows_under(root):
    """Every `<ws>/FM/_WORKFLOW/<X>/_workflow.xml` and `<ws>/FM/_PROCESS/<P>/<X>/_workflow.xml`."""
    found = []
    for ws in workspaces_under(root):
        fm = Path(root) / ws / workspace.FM
        folders = [Path(e.path) for e in _entries(fm / "_WORKFLOW") if e.is_dir()]
        for process in _entries(fm / "_PROCESS"):
            if process.is_dir():
                folders += [Path(e.path) for e in _entries(process.path) if e.is_dir()]
        found += [folder / WORKFLOW_FILE for folder in folders
                  if workspace.exact_child(folder, WORKFLOW_FILE)[0] == workspace.OK]
    return found


def process_folder(path):
    """(owning workspace, process name) when `path` is `<W>/FM/_PROCESS/<P>/process.xml`, else None."""
    path = Path(os.path.abspath(path))
    if path.name != PROCESS_FILE or path.parent.parent.name != "_PROCESS" or path.parents[2].name != workspace.FM:
        return None
    return path.parents[3], path.parent.name


def root_relative(path, root):
    try:
        return Path(os.path.abspath(path)).relative_to(os.path.abspath(root)).as_posix()
    except ValueError:
        return None


# --- the process model --------------------------------------------------------

def declared(process_root):
    """The declared state names, in order: every `States/State/@name`."""
    return [state.get("name") for state in process_root.findall("States/State") if state.get("name") is not None]


def _state_nodes(process_root):
    """(label, element) for OnStart and every declared State."""
    nodes = []
    on_start = process_root.find("OnStart")
    if on_start is not None:
        nodes.append(("OnStart", on_start))
    for state in process_root.findall("States/State"):
        nodes.append((state.get("name"), state))
    return nodes


def edges(node):
    """(element, target) for a state's transitions and timeouts."""
    found = [(t, t.get("state")) for t in node.findall("Transitions/Transition")]
    found += [(t, t.get("state")) for t in node.findall("OnTimeout")]
    return [(element, target) for element, target in found if target is not None]


def declared_states_of(path):
    """The declared states of the process at `path`, cached; None when it does not parse."""
    key = os.path.abspath(path)
    if key not in _DECLARED_CACHE:
        tree = parse(path)
        _DECLARED_CACHE[key] = set(declared(tree.getroot())) if tree is not None else None
    return _DECLARED_CACHE[key]


# --- dead transition and unreachable state -----------------------------------

def dead_transitions(process_root, rep):
    rep.ran("dead-transition")
    names = set(declared(process_root))
    for label, node in _state_nodes(process_root):
        for element, target in edges(node):
            if target != END and target not in names:
                rep.add("DEAD_TRANSITION", f"`{label}` moves to `{target}`, which is neither a declared state nor "
                                           f"`End` — names are compared exactly", line=element.sourceline)


def unreachable_states(process_root, callers, rep):
    """Warn for every declared state no entry reaches; `callers` are workflow-supplied entries."""
    rep.ran("unreachable-state")
    by_name = {label: node for label, node in _state_nodes(process_root) if label not in ("OnStart", None)}
    on_start = process_root.find("OnStart")
    entry = {target for _, target in edges(on_start)} if on_start is not None else set()
    entry |= {t.get("state") for t in process_root.iter("OnTimeout") if t.get("state") is not None}
    entry |= set(callers)
    reachable, frontier = set(), [name for name in entry if name in by_name]
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        frontier += [target for _, target in edges(by_name[name]) if target in by_name]
    report.debug("process_checks.unreachable_states", "process", states=len(by_name), entry=len(entry),
                 reachable=len(reachable))
    for name, node in by_name.items():
        if name not in reachable:
            rep.add("UNREACHABLE_STATE", f"state `{name}` is reached by no entry — not from OnStart, an OnTimeout, "
                                         f"or a workflow's CHANGE_STATE or START step under the root",
                    line=node.sourceline)


def state_steps(tree):
    """Every `StateProcess` step in a workflow tree."""
    return list(tree.getroot().iter("StateProcess"))


def entry_states(root):
    """{process path relative to the root: states that workflows under the root start or move it to}."""
    key = os.path.abspath(root)
    if key in _ENTRY_CACHE:
        return _ENTRY_CACHE[key]
    found = {}
    for path in workflows_under(root):
        tree = parse(path)
        if tree is None:
            continue
        owner = workspace.owning_workspace(path)
        for step in state_steps(tree):
            mode, state, process = step.get("mode"), step.get("state"), step.get("process")
            if mode not in (CHANGE_STATE, START) or not state or not process:
                continue
            for target in _resolved_paths(workspace.resolve_process(process, owner, root)):
                found.setdefault(target, set()).add(state)
    _ENTRY_CACHE[key] = found
    report.debug("process_checks.entry_states", "collected", root=root, processes=len(found))
    return found


def _resolved_paths(result):
    if isinstance(result, workspace.Resolved):
        return [result.path]
    if isinstance(result, workspace.AppDependent):
        return [result.path.replace("<app>", app, 1) for app in result.resolved_in]
    return []


# --- references -------------------------------------------------------------------

def report_reference(rep, result, what, unresolved_code, line, file=None, in_base=None):
    """Turn a workspace resolver result into its finding, if any.

    `in_base` is the same reference resolved with a `BASE:` prefix; when an
    app-dependent reference resolves that way, the finding says so.
    """
    if isinstance(result, workspace.Unresolved):
        rep.add(unresolved_code, f"{what} names `{result.path}`, which does not exist", line=line, file=file)
    elif isinstance(result, workspace.CaseOnly):
        rep.add("CASE_ONLY_MATCH", f"{what} reaches `{result.path}` only on a case-insensitive filesystem — on disk "
                                   f"it is `{result.actual}`", line=line, file=file)
    elif isinstance(result, workspace.AppDependent):
        hint = (f" It exists at `{in_base.path}`, which only a `BASE:` name reaches."
                if isinstance(in_base, workspace.Resolved) else "")
        rep.add("WORKFLOW_APP_DEPENDENT",
                f"{what}, in webasm, is read from the application that runs it (`{result.path}`) — present in "
                f"{', '.join(result.resolved_in) or 'no application'}, absent from "
                f"{', '.join(result.missing_in) or 'no application'}.{hint}", line=line, file=file)


def _as_base(name):
    """The `BASE:` form of a workflow or process name the selected workspace decides."""
    return workspace.BASE_PREFIX + name.lstrip("/")


def _action(rep, value, process_ref, owner, root, line, skipped, file=None):
    if not value:
        return
    kind, name = workspace.presentation(value)
    result = workspace.resolve_workflow_ref(value, process_ref, owner, root)
    if result is None:
        skipped[kind or "(no kind)"] += 1
        return
    in_base = None
    if isinstance(result, workspace.AppDependent):
        in_base = workspace.resolve_workflow_name(_as_base(name), owner, root)
    report_reference(rep, result, f"action `{value}`", "WORKFLOW_UNRESOLVED", line, file, in_base)


def workflow_references(path, process_root, owner, name, root, rep):
    rep.ran("workflow-reference")
    process_ref = workspace.process_reference(name, owner)
    skipped = Counter()
    for label, node in _state_nodes(process_root):
        _action(rep, node.get("action"), process_ref, owner, root, node.sourceline, skipped)
        for transition in node.findall("Transitions/Transition"):
            _action(rep, transition.get("action"), process_ref, owner, root, transition.sourceline, skipped)
    for state in declared(process_root):
        found, actual = workspace.exact_child(Path(path).parent, f"{state}.xml")
        if found != workspace.OK:
            continue
        settings = Path(path).parent / actual
        tree = parse(settings)
        if tree is None or tree.getroot().tag != "MultiTaskSettings":
            continue
        shown = cli.display(settings)
        for group in tree.getroot().findall("TaskGroup"):
            for attribute in TASK_GROUP_ACTIONS:
                _action(rep, group.get(attribute), process_ref, owner, root, group.sourceline, skipped, file=shown)
    for kind, count in sorted(skipped.items()):
        report.debug("process_checks.workflow_references", "skipped", kind=kind, count=count)
        rep.skipped(f"{kind.lower()}-reference" if kind != "(no kind)" else "untyped-action",
                    f"`{kind}:` actions are not workflow references" if kind != "(no kind)"
                    else "an action with no `KIND:` prefix names nothing the engine loads")


def validation_flow(process_root, owner, root, rep):
    rep.ran("validation-flow")
    value = process_root.get("validationFlow")
    if not value:
        return
    result = workspace.resolve_validation_flow(value, owner, root)
    in_base = (workspace.resolve_workflow_name(_as_base(value), owner, root)
               if isinstance(result, workspace.AppDependent) else None)
    report_reference(rep, result, f"validationFlow `{value}`", "VALIDATION_FLOW_UNRESOLVED", process_root.sourceline,
                     in_base=in_base)


# --- change-state targets ---------------------------------------------------------

def _check_states(rep, step, process_path, root):
    """The step's `state` and `applyforstates` tokens against the target process's declared states."""
    names = declared_states_of(Path(root) / process_path)
    if names is None:
        return
    allowed = names | {END}
    state = step.get("state") or ""
    if state not in allowed:
        rep.add("CHANGE_STATE_STATE_UNDECLARED", f"CHANGE_STATE moves to `{state}`, which `{process_path}` does not "
                                                 f"declare — the engine throws `New state … information not found`",
                line=step.sourceline)
    for token in (step.get("applyforstates") or "").split(";"):
        if token and token not in allowed:
            rep.add("CHANGE_STATE_STATE_UNDECLARED", f"applyforstates token {token!r} is no declared state of "
                                                     f"`{process_path}` — tokens are compared untrimmed",
                    line=step.sourceline)


def change_state_targets(path, tree, owner, root, rep):
    """Check every CHANGE_STATE step; return the names of the processes that resolve nowhere."""
    rep.ran("change-state-target")
    unresolved = []
    for step in state_steps(tree):
        if step.get("mode") != CHANGE_STATE:
            continue
        process = step.get("process")
        if not process:
            rep.add("CHANGE_STATE_PROCESS_UNRESOLVED", "CHANGE_STATE names no `process` — the engine throws "
                                                       "`Table Name and Process Name is required`",
                    line=step.sourceline)
            continue
        result = workspace.resolve_process(process, owner, root)
        in_base = (workspace.resolve_process(_as_base(process), owner, root)
                   if isinstance(result, workspace.AppDependent) else None)
        report_reference(rep, result, f"CHANGE_STATE process `{process}`", "CHANGE_STATE_PROCESS_UNRESOLVED",
                         step.sourceline, in_base=in_base)
        if isinstance(result, workspace.Unresolved):
            unresolved.append(process)
        for target in _resolved_paths(result):
            _check_states(rep, step, target, root)
    return unresolved


# --- one file -------------------------------------------------------------------------

def check_process(path, tree, rep, root_override=None):
    """Structure, then — only when the structure is usable — the process's semantic checks."""
    from . import xsd
    if not xsd.validate_process_structure(tree, rep):
        for check in SEMANTIC_CHECKS:
            rep.skipped(check, "structure invalid")
        return
    process_root = tree.getroot()
    dead_transitions(process_root, rep)
    folder = process_folder(path)
    root = workspace.workspaces_root(path, root_override)
    if folder is None or root is None:
        for check in SEMANTIC_CHECKS[1:]:
            rep.skipped(check, "the file is not at <workspace>/FM/_PROCESS/<process>/process.xml")
        return
    owner, name = folder
    callers = entry_states(root).get(root_relative(path, root), set())
    unreachable_states(process_root, callers, rep)
    workflow_references(path, process_root, owner, name, root, rep)
    validation_flow(process_root, owner, root, rep)


def check_workflow(path, tree, rep, root_override=None):
    """Change-state target resolution for one workflow; returns the unresolved process names."""
    owner = workspace.owning_workspace(path)
    root = workspace.workspaces_root(path, root_override)
    if owner is None or root is None:
        rep.skipped("change-state-target", "the file is not under a workspace's FM/")
        return []
    return change_state_targets(path, tree, owner, root, rep)
