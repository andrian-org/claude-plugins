"""edges.py — read one file's references, row by row of the reference-edges table (ADR 0023 §4).

knowledge/reference-graph.md §1 says which elements are references, and this
module reads them: for a row, the elements its `Element` names, the step each
belongs to, whether its `Condition` holds, the values its `Attribute`
alternatives pass, and what its `Resolves as` rule makes of them. No edge kind
is named here: a row the table adds is read with no code change, and a
`Resolves as` or `Condition` this module does not implement is a
KnowledgeTableError (exit 3), never a guess.

A webasm file's selected-scope reference resolves in every application, or in
`app` alone when the caller fixes one (workspace._resolve). XML trees come from
the caller's parser; this module parses only a MultiTask file's root, with the
same parser. The JSON rows are read by `json_references`, which needs jsonschema.
"""

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from . import knowledge, model, report, workspace

MULTITASK_ROOT = "MultiTaskSettings"
XML_FROM = ("process", "multitask", "workflow", "form", "settings")


@dataclass
class Reference:
    row: dict           # the reference-edges row
    element: object     # the element the value sits on (None for the file itself)
    step: object        # the step the row's Condition and run-time names apply to
    values: list        # the parts the Attribute alternative passed, in order
    line: object        # the element's line, or None
    result: object      # a workspace result, or None when a rule says it is no reference
    dynamic: bool = False  # the step's own Assign sets a name that replaces a part
    parts: tuple = ()   # the attribute names the values were read from
    where: str = ""     # a JSON reference's path in its document
    table: object = None  # a two-part rule's table part, resolved: its loader loads the table first

    @property
    def value(self):
        """The values as their attributes read, e.g. `table="Cases" view=""`."""
        if len(self.parts) == len(self.values) and len(self.values) > 1:
            return " ".join(f'{part}="{value}"' for part, value in zip(self.parts, self.values))
        return "+".join(self.values)


# --- where a row's references sit ----------------------------------------------

def _elements(root, element_spec):
    """(element, step) for one Element alternative: `A`, or `A/B` for a B whose parent is an A."""
    if "/" not in element_spec:
        return [(element, element) for element in root.iter(element_spec)]
    parent, child = element_spec.split("/", 1)
    found = []
    for element in root.iter(child):
        step = element.getparent() if hasattr(element, "getparent") else None
        if step is not None and step.tag == parent:
            found.append((element, step))
    return found


def _control_form(step, element):
    return (step.get("control") or "").upper() == "FORM"


def _fieldset_non_empty(step, element):
    return step.find("FieldSet/Field") is not None


def _extract_no_table(step, element):
    return not element.get("table")


CONDITIONS = {
    knowledge.NONE: lambda step, element: True,
    "control-form": _control_form,
    "fieldset-non-empty": _fieldset_non_empty,
    "extract-no-table": _extract_no_table,
    "mode-change-state": lambda step, element: step.get("mode") == "CHANGE_STATE",
    "mode-start-info": lambda step, element: step.get("mode") in ("START", "INFO"),
}


# --- what a row's rule makes of its values ----------------------------------------

def _action(values, owner, root, app, ctx):
    return workspace.resolve_workflow_ref(values[0], ctx.process_ref, owner, root, app=app)


def _multitask_file(values, owner, root, app, ctx):
    """<process folder>/<state>.xml, and only when its root is MultiTaskSettings; otherwise no reference."""
    if ctx.process_dir is None:
        return None
    found, actual = workspace.exact_child(ctx.process_dir, f"{values[0]}.xml")
    if found != workspace.OK or not (Path(ctx.process_dir) / actual).is_file():
        return None
    from . import process_checks
    tree = process_checks.parse(Path(ctx.process_dir) / actual)
    if tree is None or tree.getroot().tag != MULTITASK_ROOT:
        return None
    return workspace.Resolved(Path(ctx.process_dir, actual).resolve().relative_to(Path(root).resolve()).as_posix())


RESOLVERS = {
    "action": _action,
    "workflow-name": lambda v, owner, root, app, ctx: workspace.resolve_workflow_name(v[0], owner, root, app=app),
    "process-name": lambda v, owner, root, app, ctx: workspace.resolve_process(v[0], owner, root, app=app),
    "multitask-file": _multitask_file,
    "table-name": lambda v, owner, root, app, ctx: model.resolve_table(v[0], owner, root, app),
    "form": lambda v, owner, root, app, ctx: model.resolve_form(v[0], v[1], owner, root, app),
    "invoke-form": lambda v, owner, root, app, ctx: model.resolve_invoke_form(v[0], v[1], owner, root, app),
    "lookup-view": lambda v, owner, root, app, ctx: model.resolve_lookup_view(v[0], v[1], owner, root, app),
    "lookup-dialog": lambda v, owner, root, app, ctx: model.resolve_lookup_dialog(v[0], owner, root, app),
    "grid": lambda v, owner, root, app, ctx: model.resolve_grid(v[0], v[1], owner, root, app),
    "owning-table": lambda v, owner, root, app, ctx: model.owning_table(ctx.path, root),
    "datasource": lambda v, owner, root, app, ctx: workspace.resolve_component_file(v[0], "DataSource", owner, root,
                                                                                    app=app),
    "component-file": lambda v, owner, root, app, ctx: workspace.resolve_component_file(v[0], ctx.member, owner,
                                                                                        root, app=app),
}


def rows(checked_by=None):
    """The reference-edges rows — those `checked_by` names, when given — each one this module can read."""
    found = []
    for row in knowledge.edges():
        if row["Resolves as"] not in RESOLVERS:
            raise knowledge.KnowledgeTableError("reference-edges", f"edge `{row['Edge']}`: no rule reads "
                                                                   f"`Resolves as` `{row['Resolves as']}`")
        if row["Condition"] not in CONDITIONS:
            raise knowledge.KnowledgeTableError("reference-edges", f"edge `{row['Edge']}`: no rule reads "
                                                                   f"`Condition` `{row['Condition']}`")
        if checked_by is None or row["Checked by"] == checked_by:
            found.append(row)
    return found


def run_time_names():
    """{step tag: [(name, replaced attribute)]} from the run-time-names table (reference-graph.md §3.1)."""
    names = {}
    for row in knowledge.load("run-time-names"):
        names.setdefault(row["Step"], []).append((row["Name"], row["Replaces"]))
    return names


def _dynamic(step, parts, names):
    """True when the step's own Assign sets a run-time name that replaces one of `parts`."""
    if step is None or step.tag not in names:
        return False
    assigned = {field.get("name") for field in step.findall("Assign/Field")}
    return any(name in assigned and replaced in parts for name, replaced in names[step.tag])


# --- one file ---------------------------------------------------------------------

def context(path, artifact, root):
    """What a rule needs beyond the values: the file, its process reference and folder."""
    process_dir = process_ref = None
    path = Path(path)
    if artifact in ("process", "multitask"):
        process_dir = path.parent
        owner = workspace.owning_workspace(path)
        process_ref = workspace.process_reference(process_dir.name, owner)
    return SimpleNamespace(path=path, process_dir=process_dir, process_ref=process_ref, member=None)


def xml_references(path, tree, artifact, owner, root, app=None, rows_=None, names=None):
    """Every Reference the rows whose `From` is `artifact` find in `tree`."""
    ctx = context(path, artifact, root)
    names = run_time_names() if names is None else names
    found = []
    for row in rows_ if rows_ is not None else rows():
        if row["From"] != artifact:
            continue
        found += _row_references(row, tree, ctx, owner, root, app, names)
    report.debug("edges.xml_references", "read", file=path, artifact=artifact, app=app or "-", references=len(found))
    return found


def _row_references(row, tree, ctx, owner, root, app, names):
    alternatives = [knowledge.parts(value) for value in knowledge.values(row["Attribute"])]
    elements = knowledge.values(row["Element"])
    if not elements:
        result = RESOLVERS[row["Resolves as"]]([], owner, root, app, ctx)
        return [Reference(row, None, None, [], None, result)] if result is not None else []
    found = []
    holds = CONDITIONS[row["Condition"]]
    for spec in elements:
        for element, step in _elements(tree.getroot(), spec):
            if not holds(step, element):
                continue
            for parts in alternatives:
                reference = _one(row, element, step, parts, ctx, owner, root, app, names)
                if reference is not None:
                    found.append(reference)
    return found


def _one(row, element, step, parts, ctx, owner, root, app, names):
    values = [element.get(part) or "" for part in parts]
    dynamic = _dynamic(step, parts, names)
    line = getattr(element, "sourceline", None)
    if not values[0]:
        # An empty value is no reference unless a run-time name will fill it, or the row's loader is given the
        # empty name and throws on it (reference-graph.md §1, `When empty`).
        if dynamic:
            return Reference(row, element, step, values, line, None, dynamic=True, parts=tuple(parts))
        if row["When empty"] != "throws":
            return None
        report.debug("edges.reference", row["Edge"], value="", line=line, empty="throws")
    result = RESOLVERS[row["Resolves as"]](values, owner, root, app, ctx)
    if result is None:
        return None
    # Every two-part rule loads its table first (data-model.md §3), which throws when it is missing.
    table = model.resolve_table(values[0], owner, root, app) if len(values) == 2 else None
    report.debug("edges.reference", row["Edge"], value="+".join(values), line=line, dynamic=dynamic,
                 result=type(result).__name__, table=type(table).__name__ if table else "-")
    return Reference(row, element, step, values, line, result, dynamic=dynamic, parts=tuple(parts), table=table)


def restates_its_table(reference):
    """True when a two-part reference's finding would only repeat its table part's.

    The loader throws on a missing table before it reaches the second part — and on
    a table that matches only in case, since on Linux that table is missing too —
    and a table that only some applications have makes the second part theirs too.
    """
    table, result = reference.table, reference.result
    if table is None:
        return False
    if isinstance(table, (workspace.Unresolved, workspace.CaseOnly)):
        return True
    return (isinstance(table, workspace.AppDependent) and isinstance(result, workspace.AppDependent)
            and table.missing_in == result.missing_in)


def json_references(path, document, owner, root, app=None, rows_=None):
    """Every Reference the component rows find in a component JSON document.

    Which objects are references is resolve_components.py's walk (json-reader.md §2,
    §2.1), reused so the two never disagree; a row is matched by the key its
    Attribute names, in any case, as the runtime reads property names. An unreadable
    vendored dialect raises json_validate.UnknownDialect, which the caller reports:
    a reference it hides is not one that is absent.
    """
    import resolve_components
    from . import json_resolve
    component_rows = [row for row in (rows_ if rows_ is not None else rows()) if row["From"] == "component"]
    selection = json_resolve.select(path, document, None)
    if not component_rows or selection.kind not in ("component", "datasource"):
        return []
    occurrences = resolve_components.check_types(document, selection, report.Report(str(path)))
    found = []
    for where, member, name in resolve_components.references(path, document, selection, occurrences):
        key = where.rsplit(".", 1)[-1].lower()
        row = next((row for row in component_rows
                    if key in {value.lower() for value in knowledge.values(row["Attribute"])}), None)
        if row is None:
            continue
        ctx = SimpleNamespace(path=Path(path), process_dir=None, process_ref=None, member=member)
        result = RESOLVERS[row["Resolves as"]]([name], owner, root, app, ctx)
        found.append(Reference(row, None, None, [name], None, result, parts=(key,), where=where))
    report.debug("edges.json_references", "read", file=path, app=app or "-", references=len(found))
    return found


def describe(reference):
    """How a message names the reference: its step and, when it has one, the step's name."""
    if reference.where:
        return f"`{reference.where}`"
    if reference.step is None:
        return "the file"
    name = reference.step.get("name")
    return f"`{reference.step.tag}` `{name}`" if name else f"`{reference.step.tag}`"
