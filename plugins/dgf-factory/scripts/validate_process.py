#!/usr/bin/env python3
"""validate_process.py — verify processes and the workflows that drive them (ADR 0014).

For each `process.xml`: its structure, in two passes with the runtime-divergence
allowance; then, only when the structure is usable, the dead-transition,
unreachable-state, workflow-reference (MultiTask actions included) and
validation-flow checks. For each `_workflow.xml`: change-state target
resolution. References resolve by the engine's own rules — one path per form,
exact case, no fallback (knowledge/process-model.md §2) — and one that depends on
which application runs a webasm process is a warning naming the applications.

The unreachable-state entry set is always collected from every workflow under
the workspaces root, even when one process is named.

Usage:  validate_process.py [--workspaces-root R] (--all | <process.xml|_workflow.xml>...) [--verbose]
        --all checks every process and workflow under R, which it requires.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — verified by every check listed under CHECKS RUN
  1  BLOCKED   — invalid structure, a dead transition, or a reference that resolves nowhere
  2  WARNINGS  — a runtime divergence, an unreachable state, an app-dependent or case-only reference
  3  usage error, missing dependency, unresolved family, not a process or workflow
"""

import sys
from pathlib import Path

from lib import cli, deps, report


def build_parser():
    parser = cli.parser("validate_process.py", "Verify processes and the workflows that drive them.")
    parser.add_argument("paths", nargs="*", help="process.xml or _workflow.xml files")
    parser.add_argument("--all", action="store_true", help="every process and workflow under --workspaces-root")
    parser.add_argument("--workspaces-root", help="the directory that holds the workspaces (default: the parent "
                                                  "of each file's workspace)")
    return parser


def targets(args):
    from lib import process_checks
    if args.all:
        if args.paths:
            report.fail(report.EXIT_USAGE, "give --all or files, not both")
        if not args.workspaces_root:
            report.fail(report.EXIT_USAGE, "--all needs --workspaces-root")
        root = Path(args.workspaces_root)
        if not root.is_dir():
            report.fail(report.EXIT_USAGE, f"not a directory: {root}")
        return process_checks.processes_under(root) + process_checks.workflows_under(root)
    if not args.paths:
        report.fail(report.EXIT_USAGE, "name a process.xml or _workflow.xml, or give --all")
    for raw in args.paths:
        if not Path(raw).is_file():
            report.fail(report.EXIT_USAGE, f"not a file: {raw}")
    return [Path(raw) for raw in args.paths]


def check_file(path, root_override):
    from lxml import etree
    from lib import family, process_checks, xsd
    rep = report.Report(cli.display(path))
    detection = family.detect(path.read_bytes(), set(xsd.roots()))
    rep.family = detection.family
    if detection.code:
        rep.add(detection.code, detection.message, line=detection.line)
        return rep
    root = etree.QName(detection.tree.getroot()).localname if detection.family == "xsd" else None
    report.debug("validate_process.check_file", "root", file=rep.file, root=root)
    if root == "Process":
        process_checks.check_process(path, detection.tree, rep, root_override)
    elif root == "Workflow":
        process_checks.check_workflow(path, detection.tree, rep, root_override)
    else:
        rep.add("SCHEMA_UNSELECTABLE", f"a `{root or 'JSON'}` document is neither a process nor a workflow")
    return rep


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
        report.fail(report.EXIT_USAGE, "no process.xml or _workflow.xml under the workspaces root")
    return report.render(reports, header="Process verification")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
