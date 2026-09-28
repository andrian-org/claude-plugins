"""graph.py — the reference graph of one application, resolved the engine's way (ADR 0023 §4, DD8).

A node is a configuration file, named by its path relative to the workspaces
root. An edge is one reference, read by edges.py from a reference-edges row
(knowledge/reference-graph.md §1) and resolved by that row's rule. A graph is
built for one application: that application's files and webasm's, with a
webasm file's selected-scope reference resolved in that application — which is
how the engine reads it when that application runs.

reach() walks forward from every process over the rows whose `Reach` is
`follow`, and reaches — without walking on — a target of an `end` row. A row
whose `Reach` is `none` is never walked; its source is still a referrer. An
edge whose own step's Assign sets a run-time name is `dynamic`: the walk
follows its static target and says so (reference-graph.md §3.1). Nothing is
cached between builds: each one parses the files afresh.
"""

import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from . import edges, knowledge, plan, report, workspace

RESOLVED, UNRESOLVED, CASE_ONLY, DYNAMIC = "resolved", "unresolved", "case-only", "dynamic"
SHARED_WORKFLOW = ("FM", "_WORKFLOW")


@dataclass(frozen=True)
class Node:
    path: str        # relative to the workspaces root
    artifact: str    # a reference-edges `From`/`To` value
    name: str
    workspace: str


@dataclass(frozen=True)
class Edge:
    kind: str        # the reference-edges row's Edge
    source: str      # the referring file
    line: object
    value: str
    target: object   # the file it reaches — or, unresolved, the file it would; None for a dynamic empty value
    status: str      # resolved, unresolved, case-only or dynamic
    apps: tuple      # the application the graph was built for
    reach: str       # follow, end or none
    checked_by: str
    when_absent: str  # the row's — or `throws`, where the loader throws on this reference whatever the row says
    restates_table: bool = False  # a two-part reference whose table part is the problem
    reason: str = ""  # why an unresolved reference resolves nowhere, when its target alone does not say


@dataclass
class Graph:
    app: str
    nodes: dict = field(default_factory=dict)   # path -> Node
    edges: list = field(default_factory=list)
    _out: dict = field(default_factory=dict)    # source -> [Edge]

    def add_node(self, node):
        self.nodes.setdefault(node.path, node)

    def add_edge(self, edge):
        self.edges.append(edge)
        self._out.setdefault(edge.source, []).append(edge)

    def outgoing(self, path):
        return self._out.get(path, [])

    def processes(self):
        return sorted(path for path, node in self.nodes.items() if node.artifact == "process")

    def reach(self, target_path):
        """[(process path, chain of edges)] — one shortest chain per process that reaches the target."""
        found = []
        for start in self.processes():
            chain = self._shortest(start, target_path)
            if chain is not None:
                found.append((start, chain))
        report.debug("graph.reach", "reached", app=self.app, target=target_path, processes=len(found))
        return found

    def _shortest(self, start, target_path):
        if start == target_path:
            return []
        seen, queue = {start}, deque([(start, [])])
        while queue:
            here, chain = queue.popleft()
            for edge in self.outgoing(here):
                if edge.reach == "none" or edge.target is None:
                    continue
                if edge.target == target_path:
                    return chain + [edge]
                if edge.reach == "follow" and edge.target not in seen and edge.target in self.nodes:
                    seen.add(edge.target)
                    queue.append((edge.target, chain + [edge]))
        return None

    def referrers(self, target_path):
        """Every edge of any kind into the target, one level deep."""
        return sorted((edge for edge in self.edges if edge.target == target_path),
                      key=lambda edge: (edge.source, edge.line or 0, edge.kind))

    def unreached(self):
        """Shared workflows (`FM/_WORKFLOW/`) that no edge reaches."""
        targets = {edge.target for edge in self.edges}
        return sorted((node for node in self.nodes.values()
                       if node.artifact == "workflow" and Path(node.path).parts[1:3] == SHARED_WORKFLOW
                       and node.path not in targets), key=lambda node: node.path)


# --- building one application's graph ----------------------------------------------

def _relative(path, root):
    return Path(os.path.abspath(path)).relative_to(os.path.abspath(root)).as_posix()


def artifact_of(rel, tree=None):
    """(reference-edges artifact, name) for a root-relative file, or None.

    plan.artifact names most files. The two it has no row for are named here, with their reference-edges values
    (DD8): a `<workspace>/FM/_LOOKUP/<dialog…>/_dialog.xml` is a `lookup-dialog`, matched name by name exactly, as
    model.resolve_lookup_dialog builds it; a process folder's `<State>.xml` whose root is MultiTaskSettings is a
    `multitask`.
    """
    found = plan.artifact(rel)
    if found is None:
        parts = rel.split("/")
        if len(parts) >= 5 and parts[1:3] == [workspace.FM, "_LOOKUP"] and parts[-1] == "_dialog.xml":
            return "lookup-dialog", "/".join(parts[3:-1])
        if tree is not None and tree.getroot().tag == edges.MULTITASK_ROOT:
            return "multitask", "/".join(parts[3:])[:-len(".xml")]
        return None
    artifact, name = found
    return ("workflow" if artifact == "process-workflow" else artifact), name


def _files(root, app):
    """Every configuration file of `app` and webasm, as the runner collects them."""
    from . import runner
    keep = {app, workspace.BASE_WORKSPACE}
    processes, workflows, configs = runner.targets(root)
    return [path for path in processes + workflows + configs if _relative(path, root).split("/")[0] in keep]


def _parse(path):
    """('xml', tree) or ('json', document), or (None, None) for a file that does not parse.

    JSON is read by family.detect, the validators' reader, so comments and a BOM read as the runtime reads them.
    """
    from . import family, process_checks, xsd
    if str(path).endswith(".json"):
        try:
            detection = family.detect(Path(path).read_bytes(), set(xsd.roots()))
        except (OSError, RecursionError):
            return None, None
        return ("json", detection.document) if detection.family == "json" and not detection.code else (None, None)
    tree = process_checks.parse(path)
    return ("xml", tree) if tree is not None else (None, None)


def _target(result):
    """(target path, status) for a workspace result."""
    if isinstance(result, workspace.Resolved):
        return result.path, RESOLVED
    if isinstance(result, workspace.CaseOnly):
        return result.actual, CASE_ONLY
    return result.path, UNRESOLVED


def _edge(reference, source, app):
    """(the Edge, its static status): a dynamic edge keeps its static target, and whether that resolved."""
    row, result = reference.row, reference.result
    if result is None:
        target, static = None, None
    else:
        target, static = _target(result)
    unresolved = isinstance(result, workspace.Unresolved)
    edge = Edge(row["Edge"], source, reference.line or reference.where or None, reference.value, target,
                DYNAMIC if reference.dynamic or result is None else static, (app,), row["Reach"], row["Checked by"],
                "throws" if unresolved and result.throws else row["When absent"], edges.restates_its_table(reference),
                result.reason if unresolved else "")
    return edge, static


def build(root, app):
    """The graph of `app`: its files and webasm's, every webasm reference resolved in `app`."""
    root = Path(os.path.abspath(root))
    rows = edges.rows()
    names = edges.run_time_names()
    to_artifact = {row["Edge"]: row["To"] for row in rows}
    graph = Graph(app)
    pending = deque(_files(root, app))
    parsed = set()
    while pending:
        path = Path(pending.popleft())
        rel = _relative(path, root)
        if rel in parsed:
            continue
        parsed.add(rel)
        kind, content = _parse(path)
        found = artifact_of(rel, content if kind == "xml" else None)
        if found is None:
            continue
        artifact, name = found
        graph.add_node(Node(rel, artifact, name, rel.split("/")[0]))
        if kind is None:
            report.debug("graph.build", "unparsable", app=app, file=rel)
            continue
        owner = workspace.owning_workspace(path)
        references = (edges.json_references(path, content, owner, root, app, rows) if kind == "json" else
                      edges.xml_references(path, content, artifact, owner, root, app, rows, names))
        for reference in references:
            edge, static = _edge(reference, rel, app)
            graph.add_edge(edge)
            if static == UNRESOLVED:
                report.debug("graph.build", "unresolved", app=app, kind=edge.kind, source=rel, target=edge.target,
                             status=edge.status)
            if edge.target and static != UNRESOLVED:  # a dynamic edge's missing static target is no file
                target_found = plan.artifact(edge.target)
                graph.add_node(Node(edge.target, to_artifact[edge.kind],
                                    target_found[1] if target_found else Path(edge.target).parent.name,
                                    edge.target.split("/")[0]))
                if to_artifact[edge.kind] == "multitask" and edge.target not in parsed:
                    pending.append(root / edge.target)
    counts = {status: sum(1 for edge in graph.edges if edge.status == status)
              for status in (RESOLVED, UNRESOLVED, CASE_ONLY, DYNAMIC)}
    report.debug("graph.build", "built", app=app, nodes=len(graph.nodes), edges=len(graph.edges), **counts)
    return graph


def build_all(root):
    """{application: its graph}, one per application under the root."""
    return {app: build(root, app) for app in workspace.applications(root)}


def check_table():
    """Raise KnowledgeTableError when a reference-edges row names a rule or condition no reader has."""
    edges.rows()
    knowledge.load("run-time-names")
