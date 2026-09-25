#!/usr/bin/env python3
"""route_means.py — which family a new piece of configuration is written in (ADR 0010 §1).

The order of means, as a table lookup. For `<name>` — a ComponentType member or
a legacy artifact type, in any case — the first rule that applies decides:

  1. A legacy artifact type (the `legacy-artifacts` table in
     knowledge/composition-specs.md) → xml, at its folder and filename. Form
     included: its parity row is ◐, but the legacy types stay XML (ADR 0010 §1).
  1a. A loader folder under `_COMPONENTS/` (`DataSource`, `Template`,
     `Endpoints` — the `component-folders` table, knowledge/json-reader.md §4)
     → json: its loader reads that folder as JSON, whatever the parity table
     says about a member of the same name.
  2. The member's parity row (knowledge/schema-families.md §6) is ✗ → xml. The
     artifact is found through the row's schema, its XSD counterpart
     (`correspondence`, §5) and that XSD's legacy artifact.
  3. The row is ✓ → json, at <workspace>/FM/_COMPONENTS/<Type>/<name>.json.
  4. The row is ◐ → json, with an exit-2 warning naming the row's XML-only part.
  5. No row → exit 3. The route is never defaulted.

It never answers `code`. Means 3 — a little JavaScript or CSS — is a planner's
judgement that configuration cannot express a change (`kind: code`), not a table
lookup. Stdlib only.

Usage:  route_means.py <name> [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  a route: xml, or json read by the runtime in full
  2  json, with part of the component still read from XML (◐)
  3  usage error, or no parity row — no route
"""

import sys

from lib import cli, knowledge, report

NOT_RUNTIME = "✗"
PARTIAL = "◐"
SUPPORTED = "✓"


def build_parser():
    parser = cli.parser("route_means.py", "Route a new component or artifact to JSON or legacy XML.")
    parser.add_argument("name", help="a ComponentType member or a legacy artifact type")
    return parser


def legacy_artifact(name):
    """The `legacy-artifacts` row whose Artifact is `name` (any case), or None."""
    return knowledge.index("legacy-artifacts", fold=True).get(name.strip().lower())


def where_xml(row):
    return f"<workspace>/{row['Folder']}{row['Filename']}"


def artifact_for_schema(schema):
    """The legacy artifact whose grammar is the XSD counterpart of JSON `schema`, or None."""
    counterpart = next((row for row in knowledge.load("correspondence") if row["JSON counterpart"] == schema), None)
    if counterpart is None:
        return None
    return next((row for row in knowledge.load("legacy-artifacts") if row["Grammar"] == counterpart["XSD"]), None)


def loader_folder(name):
    """The `component-folders` row whose loader folder is `name` (any case), or None."""
    folded = name.strip().lower()
    return next((row for row in knowledge.load("component-folders")
                 if not row["Folder"].startswith("(") and row["Folder"].lower() == folded), None)


def route(name, rep):
    """(family, where, reason) for `name`, or None when there is no route; findings go to `rep`."""
    from lib import json_resolve
    legacy = legacy_artifact(name)
    folder = loader_folder(name) if legacy is None else None
    member = json_resolve.component_member(name)
    parity_row = next((row for row in knowledge.load("parity") if member and row["ComponentType"] == member), None)
    report.debug("route_means.route", "looked up", name=name, member=member,
                 row=parity_row["#"] if parity_row else None, legacy=legacy["Artifact"] if legacy else None)

    if legacy is not None:
        reason = f"`{legacy['Artifact']}` is a legacy artifact type, and new ones stay XML"
        if parity_row is not None and parity_row["Runtime"] != NOT_RUNTIME:
            reason += f" although parity row {parity_row['#']} is {parity_row['Runtime']} (ADR 0010 §1)"
        return "xml", where_xml(legacy), reason
    if folder is not None:
        return ("json", f"<workspace>/FM/_COMPONENTS/{folder['Folder']}/<name>.json",
                f"`{folder['Folder']}` is a loader folder: {folder['Loader']} reads it as JSON "
                f"(knowledge/json-reader.md §4)")
    if member is None:
        rep.add("ROUTE_NO_ROW", f"`{name}` is neither a ComponentType member nor a legacy artifact type")
        return None
    if parity_row is None:
        rep.add("ROUTE_NO_ROW", f"`{member}` has no row in the parity table — nothing states whether the runtime "
                                f"reads it as JSON, so no family is chosen")
        return None

    number, runtime, xml_part = parity_row["#"], parity_row["Runtime"], parity_row["XML-only part"]
    if runtime == NOT_RUNTIME:
        artifact = artifact_for_schema(parity_row["Schema"])
        where = where_xml(artifact) if artifact else "a legacy XML artifact"
        return "xml", where, f"parity row {number} is ✗: the runtime does not read `{member}` from JSON — {xml_part}"
    where = f"<workspace>/FM/_COMPONENTS/{member}/<name>.json"
    if runtime == PARTIAL:
        rep.add("PARITY_PARTIAL", f"`{member}` is read from JSON only in part (parity row {number}): {xml_part}")
        return "json", where, f"parity row {number} is ◐: the JSON is read; its XML-only part is a legacy artifact"
    if runtime == SUPPORTED:
        return "json", where, f"parity row {number} is ✓: the runtime reads `{member}` from JSON in full"
    rep.add("ROUTE_NO_ROW", f"parity row {number} for `{member}` states no runtime support")
    return None


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    rep = report.Report(args.name.strip())
    try:
        found = route(args.name, rep)
    except knowledge.KnowledgeTableError as exc:
        report.fail(report.EXIT_USAGE, f"ERROR KNOWLEDGE_TABLE {exc}")
    print(f"{report.BOLD}Order-of-means route{report.NC}")
    if found is not None:
        family, where, reason = found
        print(report.one_line(f"ROUTE: {family} {where} — {reason}"))
    for finding in rep.findings:
        print(finding.render())
    print()
    print(report.verdict_line(rep.exit_code()))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
