#!/usr/bin/env python3
"""validate_config.py — validate DGF configuration in either schema family.

Resolves each file's family before parsing it — never assumes JSON — then
validates it against the family's vendored schema, and checks runtime parity
before reporting success:

- JSON: the component's class schema, read the way the runtime reads JSON
  (knowledge/json-reader.md), then the parity table (knowledge/schema-families.md
  §6). A config the runtime does not read from JSON is a warning, never a pass.
- XML: the grammar its root element names. `process.xml` is checked in two
  passes with the runtime-divergence allowance (ADR 0014); every other grammar's
  failures are advisory warnings (ADR 0016).

Usage:  validate_config.py <path>... [--component-type T] [--view-kind table|lookup|grid] [--verbose]
        A directory is walked for the legacy artifact files and *.json.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — valid, and read by the runtime in that family
  1  BLOCKED   — invalid, malformed, or an unknown component
  2  WARNINGS  — valid but not (fully) runtime-supported, unknown properties, XSD lag
  3  usage error, missing dependency, unresolved family, no selectable schema
"""

import sys

from lib import cli, deps, report


def build_parser():
    parser = cli.parser("validate_config.py", "Validate DGF configuration in either schema family.")
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("--component-type", help="validate JSON as this ComponentType (or DataSource kind)")
    parser.add_argument("--view-kind", choices=sorted(("table", "lookup", "grid")),
                        help="which view grammar a <view> root uses, when its folder does not say")
    return parser


def validate_json(detection, path, rep, override):
    from lib import json_resolve, json_validate, parity
    selection = json_resolve.select(path, detection.document, override)
    report.debug("validate_config.validate_json", "selected", file=rep.file, kind=selection.kind,
                 schema=selection.schema if isinstance(selection.schema, str) else selection.kind)
    json_validate.validate(detection.document, selection, rep)
    if rep.exit_code() in (report.EXIT_CLEAN, report.EXIT_WARNINGS):
        parity.check(selection, rep)
    else:
        rep.skipped("runtime-parity", "schema invalid")


def validate_xml(detection, path, rep, view_kind):
    from lxml import etree
    from lib import xsd
    root = etree.QName(detection.tree.getroot()).localname
    grammar, reason = xsd.grammar_for(root, path, view_kind)
    report.debug("validate_config.validate_xml", "grammar", file=rep.file, root=root, grammar=grammar)
    if grammar is None:
        rep.add("SCHEMA_UNSELECTABLE", reason)
        return
    if xsd.schema(grammar) is None:
        rep.skipped("xsd-structure", f"{grammar} does not compile")
        rep.add("XSD_NOT_COMPILABLE", f"{grammar} does not compile, so `{root}` is not validated: "
                                      f"{xsd.uncompilable_reason(grammar)}")
        return
    if grammar == xsd.PROCESS:
        xsd.validate_process_structure(detection.tree, rep)
        rep.skipped("process-semantics", "run validate_process.py")
        return
    xsd.validate(detection.tree, grammar, rep)


def validate_file(path, args):
    from lib import family, xsd
    rep = report.Report(cli.display(path))
    detection = family.detect(path.read_bytes(), set(xsd.roots()))
    rep.family = detection.family
    report.debug("validate_config.validate_file", "family", file=rep.file, family=detection.family or "unresolved")
    if detection.code:
        rep.add(detection.code, detection.message, line=detection.line)
    elif detection.family == "json":
        validate_json(detection, path, rep, args.component_type)
    else:
        validate_xml(detection, path, rep, args.view_kind)
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
        reports = [validate_file(path, args) for path in files]
    except knowledge.KnowledgeTableError as exc:
        report.fail(report.EXIT_USAGE, f"ERROR KNOWLEDGE_TABLE {exc}")
    return report.render(reports, header="Config validation")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
