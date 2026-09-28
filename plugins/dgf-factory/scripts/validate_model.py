#!/usr/bin/env python3
"""validate_model.py — check the references an entity and a form make, and an entity's own load (ADR 0023 §3).

For each `FM/_DATA/<E>/settings.xml` and `FM/_DATA/<E>/_forms/<f>/_form.xml`,
every reference-edges row whose `Checked by` is this script
(knowledge/reference-graph.md §1): an `extract`'s table, view or dialog, a
`slavegrid`'s table and grid, and a form's own entity. Each resolves by its
loader's own rule (knowledge/data-model.md §3), and blocks only where that
loader throws: a missing table or dialog is an error — so is an empty one where
the row's `When empty` is `throws` — while a missing view or grid is a
warning, because the runtime fills it and writes it into the workspace. It is
an error where the runtime cannot: a grid folder that exists while the table
has a `default` to copy, which the copy throws into; a view whose table has no
Text field besides its key; or a generated file that does not parse once names
and titles are pasted into it (knowledge/data-model.md §3.6). A workflow's form
references are not checked here: the audit reports them.
An entity's load runs Table.InitFields, which throws on a field with no name,
two fields of one name, no primary key, or a key that names no field
(data-model.md §1). That is all of its load checked here: what XmlSerializer
refuses first — a `type` no FieldTypeEnum member names, say — is not.
A form with tabs must bind every cell to a field of its entity: Form.InitFields
throws on one that does not.

Usage:  validate_model.py [--workspaces-root R] (--all | <settings.xml | _form.xml>...) [--verbose]
        --all checks every settings.xml and _form.xml under R, which it requires.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — every reference resolves, Table.InitFields accepts the
                 entity's key and fields, and every bound cell names a field,
                 as far as the checks ran: a NOT RUN line names one that did
                 not — form-cells when the form's entity settings.xml does not
                 parse, entity-load when the file holds a DTD or does not
                 parse once decoded as the runtime decodes it
  1  BLOCKED   — a reference whose loader throws resolves nowhere,
                 Table.InitFields throws on the entity, a bound cell names no
                 field, or the file does not parse
  2  WARNINGS  — a reference the runtime fills from a template, one that
                 depends on the application running a webasm file, or a
                 case-only match
  3  usage error, missing dependency, a malformed knowledge table, not a
     settings.xml or _form.xml under FM/_DATA/<entity>/
"""

import sys
from pathlib import Path

from lib import cli, deps, report

CHECKED_BY = "validate_model.py"
ARTIFACTS = ("settings", "form")
SETTINGS_NOT_RUN = (
    ("relation-table", "a relation's table is a database object outside the root"),
    ("entity-datasource", "a `DB` or `Provider` name is a database object or an assembly, not a file in the root"),
)


def build_parser():
    parser = cli.parser("validate_model.py", "Check the references an entity and a form make.")
    parser.add_argument("paths", nargs="*", help="settings.xml or _form.xml files")
    parser.add_argument("--all", action="store_true", help="every settings.xml and _form.xml under --workspaces-root")
    parser.add_argument("--workspaces-root", help="the directory that holds the workspaces (default: the parent "
                                                  "of each file's workspace)")
    return parser


def artifact_of(path, root):
    """`settings`, `form`, or None for a file that is neither, by its place under the root."""
    from lib import plan
    if root is None:
        return None
    try:
        rel = Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return None
    found = plan.artifact(rel)
    return found[0] if found and found[0] in ARTIFACTS else None


def targets(args):
    if args.all:
        if args.paths:
            report.fail(report.EXIT_USAGE, "give --all or files, not both")
        if not args.workspaces_root:
            report.fail(report.EXIT_USAGE, "--all needs --workspaces-root")
        root = Path(args.workspaces_root)
        if not root.is_dir():
            report.fail(report.EXIT_USAGE, f"not a directory: {root}")
        return [path for path in cli.collect([root], want_json=False) if artifact_of(path, root)]
    if not args.paths:
        report.fail(report.EXIT_USAGE, "name a settings.xml or _form.xml, or give --all")
    for raw in args.paths:
        if not Path(raw).is_file():
            report.fail(report.EXIT_USAGE, f"not a file: {raw}")
    return [Path(raw) for raw in args.paths]


def _parse(path, rep):
    """The file's lxml tree, or None after recording XML_MALFORMED."""
    from lxml import etree
    from lib import family
    try:
        tree = etree.parse(str(path), family.xml_parser())
    except (etree.XMLSyntaxError, OSError) as exc:
        rep.add("XML_MALFORMED", f"the file does not parse: {str(exc).splitlines()[0]}")
        return None
    rep.family = "xsd"
    return tree


def check_file(path, root_override=None):
    """The Report for one settings.xml or _form.xml."""
    from lib import edges, workspace
    path = Path(path)
    rep = report.Report(cli.display(path))
    root = workspace.workspaces_root(path, root_override)
    kind = artifact_of(path, root)
    report.debug("validate_model.check_file", "file", file=rep.file, artifact=kind or "-")
    if kind is None:
        rep.add("SCHEMA_UNSELECTABLE", "not a settings.xml or _form.xml under FM/_DATA/<entity>/ in a workspace")
        return rep
    tree = _parse(path, rep)
    if tree is None:
        return rep
    rep.ran("model-references")
    if kind == "settings":
        for check, why in SETTINGS_NOT_RUN:
            rep.skipped(check, why)
        check_entity_load(rep, path, tree)
    rows = edges.rows(CHECKED_BY)
    for row in rows:
        if row["When absent"] == "unknown" and row["From"] == kind:
            rep.skipped(f"edge-{row['Edge']}", "what the runtime does when its target is missing is not established")
    checked = [row for row in rows if row["When absent"] not in ("unknown", "skipped")]
    owner = workspace.owning_workspace(path)
    for reference in edges.xml_references(path, tree, kind, owner, root, rows_=checked):
        report_reference(rep, reference)
    if kind == "form":
        check_cells(rep, path, tree, root)
    return rep


def check_entity_load(rep, path, tree):
    """TableManager.LoadAsync calls Table.InitFields on every load, which throws on some keys and fields (§1)."""
    from lib import model
    read = model.read_entity(path)
    if read is None:
        why = ("holds a DTD" if tree.docinfo.doctype else "does not parse once decoded as the runtime decodes it "
                                                          "(UTF-8 unless a byte-order mark says otherwise)")
        rep.skipped("entity-load", f"the file {why}, which this check does not read")
        return
    rep.ran("entity-load")
    reason = model.init_fields_throws(*read)
    report.debug("validate_model.check_entity_load", "loads" if reason is None else "throws", file=rep.file)
    if reason:
        rep.add("MODEL_ENTITY_UNLOADABLE", f"{reason} — TableManager.LoadAsync throws, so the entity does not load")


def report_reference(rep, reference):
    """Add the finding, if any, for one reference; a resolved one adds nothing."""
    from lib import edges, workspace
    row, result = reference.row, reference.result
    edge, what, value = row["Edge"], edges.describe(reference), reference.value
    report.debug("validate_model.report_reference", edge, value=value, result=type(result).__name__)
    if edges.restates_its_table(reference):
        return  # its table part's own edge reports it
    if isinstance(result, workspace.CaseOnly):
        rep.add("CASE_ONLY_MATCH", f"{edge}: {what} names `{value}`, which reaches `{result.path}` only on a "
                                   f"case-insensitive filesystem — on disk it is `{result.actual}`", line=reference.line)
    elif isinstance(result, workspace.AppDependent):
        rep.add("MODEL_REFERENCE_APP_DEPENDENT",
                f"{edge}: {what} in a webasm file names `{value}`, which the running application decides — "
                f"`{result.path}` is present in {', '.join(result.resolved_in) or 'no application'}, absent from "
                f"{', '.join(result.missing_in) or 'no application'}", line=reference.line)
    elif isinstance(result, workspace.Unresolved) and (row["When absent"] == "throws" or result.throws):
        rep.add("MODEL_REFERENCE_UNRESOLVED", unresolved_text(edge, what, value, result), line=reference.line)
    elif isinstance(result, workspace.Unresolved) and row["When absent"] == "template":
        rep.add("MODEL_REFERENCE_TEMPLATED", f"{edge}: {what} names `{value}`, but `{result.path}` does not exist — "
                                             f"the runtime generates a default and writes it into the workspace",
                line=reference.line)


def unresolved_text(edge, what, value, result):
    """What a reference whose loader throws names, and why it resolves nowhere — root-relative, never absolute."""
    if not result.path:
        return f"{edge}: {what} {result.reason}"  # an empty name: the reason says what the loader does with it
    head = (f"{edge}: {what} names `{value}`, but `{result.path}` does not exist" if value else
            f"{edge}: {what} needs `{result.path}`, which does not exist")
    return head + (f" — {result.reason}" if result.reason else "") + ", and the loader throws"


def check_cells(rep, path, form_tree, root):
    """Every bound cell with a name and no content names a field of the form's entity (data-model.md §4)."""
    from lib import model, process_checks, workspace
    table = model.owning_table(path, root)
    if not isinstance(table, workspace.Resolved):
        rep.skipped("form-cells", "the form's entity does not load")
        return
    settings = process_checks.parse(Path(root) / table.path)
    if settings is None:
        rep.skipped("form-cells", "the form's entity settings.xml does not parse")
        return
    rep.ran("form-cells")
    fields = model.fields(settings)
    entity = model.form_parts(path)[1]
    for name, line, custom in model.cells(form_tree):
        if custom or name in fields:
            continue
        rep.add("MODEL_CELL_UNBOUND", f"cell `{name}` names no field of `{entity}` and carries no `content` — "
                                      f"Form.InitFields throws, so the form does not load", line=line)


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    deps.require()
    from lib import knowledge
    try:
        reports = [check_file(path, args.workspaces_root) for path in targets(args)]
    except knowledge.KnowledgeTableError as exc:
        report.fail(report.EXIT_USAGE, f"ERROR KNOWLEDGE_TABLE {exc}")
    if not reports:
        report.fail(report.EXIT_USAGE, "no settings.xml or _form.xml under the workspaces root")
    return report.render(reports, header="Model validation")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
