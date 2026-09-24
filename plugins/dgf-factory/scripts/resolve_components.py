#!/usr/bin/env python3
"""resolve_components.py — are the component types a configuration names legal, and do the
component files it references exist?

Resolves each file's family first, like validate_config.py, then:

- JSON: every component the runtime reads — the file's own and every child a
  member typed IComponentConfiguration holds, found by the same walk the schema
  check makes (knowledge/json-reader.md §2) — must name a ComponentType member,
  in any case. The members are the vendored schemas' ComponentType enum. A
  value that is no member is blocked; a member with no configuration class is
  a warning, because the runtime drops it; a member outside the 34 dispatchable
  services (knowledge/component-catalogue.md §3) is INFO. An integer written as
  a string is reported unknown: the vendored enum carries names only.
- JSON component file references (json-reader.md §2.1): a `path` on a direct
  child of a layout file served by type and name, and every ReferenceComponent's
  `componentType`/`componentName`, must name an existing
  `_COMPONENTS/<Type>/<name>.json`, matched by exact name. `BASE:` reads
  webasm's; any other name reads the owning workspace's — for a file in webasm,
  every application's, and one that some applications lack is app-dependent.
- XML: every `component/@type` in a form. A value form.xsd's component types
  list passes. A ComponentType member it does not list is a warning, because
  the grammar lags the runtime (ADR 0016). A value that is neither is blocked,
  even though other form XSD failures only warn: no component is built for it.

Usage:  resolve_components.py <path>... [--component-type T] [--view-kind table|lookup|grid] [--verbose]
        A directory is walked for the legacy artifact files and *.json.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — every type legal and every referenced file present (INFO allowed)
  1  BLOCKED   — an unknown component type, or a referenced file that does not exist
  2  WARNINGS  — no configuration class, a case-only or app-dependent reference, XSD lag
  3  usage error, missing dependency, unresolved family, no selectable schema
"""

import sys
from collections import Counter

from lib import cli, deps, report

FORM_GRAMMAR = "form.xsd"
FORM_TYPES = "componentTypeValue"
REFERENCE = "ReferenceComponent"


def build_parser():
    parser = cli.parser("resolve_components.py", "Check component types and component file references.")
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("--component-type", help="read JSON as this ComponentType (or DataSource kind)")
    parser.add_argument("--view-kind", choices=sorted(("table", "lookup", "grid")),
                        help="which view grammar a <view> root uses, when its folder does not say")
    return parser


# --- JSON: component types ---------------------------------------------------

def _paths(document):
    """{id(object): its JSON path} for every object in `document`."""
    from lib import json_validate
    found = {}

    def walk(value, path):
        if isinstance(value, dict):
            found[id(value)] = json_validate.json_path(path)
            for key, child in value.items():
                walk(child, path + (key,))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path + (index,))

    walk(document, ())
    return found


def _folded(obj, name):
    """(key, value) under `name`, matched in any case as the runtime binds it."""
    if hasattr(obj, "get_folded"):
        return obj.get_folded(name)
    return None, None


def check_types(document, selection, rep):
    """Add the type findings for `document` and its children; return [(json path, object, member)]."""
    from lib import json_resolve, json_validate, knowledge
    dispatchable = set(knowledge.index("dispatchable"))
    occurrences = []
    if selection.kind in ("component", "interface"):
        occurrences.append(("$", document, selection.member, selection.kind))
    paths = _paths(document)
    for child, child_selection in json_validate.components(document, selection):
        where = paths.get(id(child), "$")
        for code, message in child_selection.findings:
            rep.add(code, f"{where}: {message}")
        report.debug("resolve_components.check_types", "type", path=where, value=child.get("type"),
                     member=child_selection.member)
        if child_selection.member:
            occurrences.append((where, child, child_selection.member, child_selection.kind))

    no_service = Counter(member for _, _, member, kind in occurrences
                         if member not in dispatchable and json_resolve.class_for(member)[1] != "none")
    for member, count in sorted(no_service.items()):
        times = "once" if count == 1 else f"{count} times"
        rep.add("NO_SERVICE", f"`{member}` ({times}) is a legal ComponentType with no component service — the "
                              f"runtime dispatches no request for it")
    return [(where, obj, member) for where, obj, member, _ in occurrences]


# --- JSON: component file references -----------------------------------------

def references(path, document, selection, occurrences):
    """[(json path, ComponentType member, name)] for every component file the document names."""
    from lib import json_resolve, knowledge
    found = []
    if (selection.kind == "component" and selection.member in knowledge.index("layout-components")
            and json_resolve.served_by_type(path)):
        key, content = _folded(document, "content")
        for index, child in enumerate(content if isinstance(content, list) else []):
            path_key, name = _folded(child, "path")
            member = json_resolve.component_member(child.get("type")) if isinstance(child, dict) else None
            if isinstance(name, str) and name.strip() and member:
                found.append((f"$.{key}[{index}].{path_key}", member, name))
    for where, obj, member in occurrences:
        if member != REFERENCE:
            continue
        _, target_type = _folded(obj, "componentType")
        name_key, name = _folded(obj, "componentName")
        target = json_resolve.component_member(target_type)
        if target and isinstance(name, str) and name.strip():
            found.append((f"{where}.{name_key}", target, name))
    return found


def _target(base, member, name):
    from lib import workspace
    parts = [workspace.FM, "_COMPONENTS", member] + f"{name}.json".split("/")
    return workspace.exact_file(base, parts), "/".join([base.name] + parts)


def resolve_reference(where, member, name, owner, root, rep):
    """Add the finding, if any, for one component file reference."""
    from lib import workspace
    if name[:5].lower() == "base:":
        base, rest = root / workspace.BASE_WORKSPACE, name[5:]
    elif owner.name == workspace.BASE_WORKSPACE:
        return _app_dependent(where, member, name, root, rep)
    else:
        base, rest = owner, name
    (status, actual), shown = _target(base, member, rest)
    report.debug("resolve_components.resolve_reference", "resolved", path=where, name=name, target=shown,
                 result=status)
    if status == workspace.CASE_ONLY:
        rep.add("CASE_ONLY_MATCH", f"{where}: `{name}` reaches `{shown}` only on a case-insensitive filesystem — "
                                   f"on disk it is `{actual.relative_to(root).as_posix()}`")
    elif status == workspace.MISSING:
        rep.add("COMPONENT_FILE_UNRESOLVED", f"{where}: `{name}` names `{shown}`, which does not exist — the "
                                             f"component it supplies vanishes")


def _app_dependent(where, member, name, root, rep):
    """A name without `BASE:` in a webasm file: each application reads its own copy (D2)."""
    from lib import workspace
    resolved, lacking = [], []
    for app in workspace.applications(root):
        (status, _), _ = _target(root / app, member, name)
        (resolved if status == workspace.OK else lacking).append(app)
    report.debug("resolve_components.resolve_reference", "per application", path=where, name=name,
                 resolved=",".join(resolved), lacking=",".join(lacking))
    if resolved and not lacking:
        return
    (in_base, _), _ = _target(root / workspace.BASE_WORKSPACE, member, name)
    hint = " It exists in webasm, which only a `BASE:` name reaches." if in_base == workspace.OK else ""
    rep.add("COMPONENT_FILE_APP_DEPENDENT",
            f"{where}: `{name}` in a webasm file reads the selected application's _COMPONENTS/{member}/ — "
            f"present in {', '.join(resolved) or 'no application'}, absent from "
            f"{', '.join(lacking) or 'no application'}.{hint}")


def check_references(path, document, selection, occurrences, rep):
    from lib import workspace
    found = references(path, document, selection, occurrences)
    owner = workspace.owning_workspace(path)
    if owner is None:
        if found:
            rep.skipped("component-file-references", "the file is not under a workspace's FM/")
        return
    rep.ran("component-file-references")
    root = workspace.workspaces_root(path)
    for where, member, name in found:
        resolve_reference(where, member, name, owner, root, rep)


def check_json(detection, path, rep, override):
    from lib import json_resolve, json_validate
    selection = json_resolve.select(path, detection.document, override)
    for code, message in selection.findings:
        rep.add(code, message)
    if selection.kind == "unselectable":
        return
    if selection.kind == "none" and selection.reason:
        rep.skipped("component-types", "no schema selects the file")
        return
    rep.ran("component-types")
    try:
        occurrences = check_types(detection.document, selection, rep)
    except json_validate.UnknownDialect as exc:
        rep.add("SCHEMA_UNSELECTABLE", f"schema dialect `{exc}` is not draft-04 or draft-07")
        return
    check_references(path, detection.document, selection, occurrences, rep)


# --- XML: form component types -----------------------------------------------

def check_xml(detection, rep):
    from lxml import etree
    from lib import json_resolve, xsd
    root = etree.QName(detection.tree.getroot()).localname
    if xsd.roots().get(root) != [FORM_GRAMMAR]:
        rep.skipped("component-types", f"a `{root}` document names no component types")
        return
    rep.ran("component-types")
    listed = xsd.enumeration(FORM_GRAMMAR, FORM_TYPES)
    for element in detection.tree.getroot().iter("component"):
        value = element.get("type")
        member = json_resolve.component_member(value)
        report.debug("resolve_components.check_xml", "type", line=element.sourceline, value=value, member=member)
        if value is None or value in listed:
            continue
        if member is not None:
            rep.add("XSD_LAGS_RUNTIME", f"component type `{value}` is the ComponentType `{member}`, which "
                                        f"form.xsd's component types do not list — the grammar lags the runtime",
                    line=element.sourceline)
        else:
            rep.add("UNKNOWN_COMPONENT", f"component type `{value}` is neither one of form.xsd's component types "
                                         f"nor a ComponentType member — no component is built for it, unless the "
                                         f"cell's field type replaces it", line=element.sourceline)


def check_file(path, args):
    from lib import family, xsd
    rep = report.Report(cli.display(path))
    detection = family.detect(path.read_bytes(), set(xsd.roots()))
    rep.family = detection.family
    report.debug("resolve_components.check_file", "family", file=rep.file, family=detection.family or "unresolved")
    if detection.code:
        rep.add(detection.code, detection.message, line=detection.line)
    elif detection.family == "json":
        check_json(detection, path, rep, args.component_type)
    else:
        check_xml(detection, rep)
    return rep


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    deps.require()
    from lib import knowledge
    try:
        files = cli.collect(args.paths)
        if not files:
            report.fail(report.EXIT_USAGE, "no configuration files found under the given paths")
        reports = [check_file(path, args) for path in files]
    except knowledge.KnowledgeTableError as exc:
        report.fail(report.EXIT_USAGE, f"ERROR KNOWLEDGE_TABLE {exc}")
    report.debug("resolve_components.main", "summary",
                 **Counter(f.code for rep in reports for f in rep.findings))
    return report.render(reports, header="Component resolution")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
