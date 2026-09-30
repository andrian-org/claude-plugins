#!/usr/bin/env python3
"""audit_root.py — audit a workspaces root, or show a change's blast radius (ADR 0027 §5).

Two modes, both read-only, and neither emits a dgf-gate-result block: blast
radius is a report, not a gate (ADR 0022 §6 is unchanged).

  whole root  the validators' counts over the root's configuration — a JSON
              draft outside every FM/, which no loader reads, is left out and
              said so — and every validator ERROR as its own line; the
              reference graph of each application (lib/graph.py), with the
              references no validator checks that resolve nowhere; the shared
              workflows no traced reference reaches; and every role name the
              root uses (lib/roles.py) — an inventory, since nothing in the
              root declares roles (knowledge/permissions.md §1).
  reach       for each named file (--reach), or each file a branch changed
              (--base, --changed), the processes that reach it in each
              application and its direct referrers.

Every report ends with a LIMIT line: a static walk cannot see names assigned at
run time, processes chosen from the database, open handlers or entry points
outside processes (knowledge/reference-graph.md §3). A reach is never complete.
--app narrows the audit to one application, for speed only, and says so.

Usage:  audit_root.py --workspaces-root R [--reach PATH ... | --base REF | --changed S:PATH ...]
                      [--app NAME] [--skip-validators] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  clean — or findings that are INFO only
  1  a validator ERROR in the root — one the validator itself exits 3 on, such
     as FAMILY_UNRESOLVED, included: the audit's call was good
  2  a reference no validator checks resolves nowhere — its loader throws, the
     step records an error, or the runtime writes a default in its place — a
     case-only match, or the audit was narrowed by --app
  3  usage error, missing dependency, a malformed knowledge table, a vendored
     schema whose dialect the validators cannot read (SCHEMA_UNSELECTABLE), a
     check that raised (AUDIT_CHECK_FAILED, with the report so far), a --reach
     path that is not a configuration file under the root, or
     --skip-validators with a reach mode
"""

import dataclasses
import os
import sys
import traceback
from collections import Counter
from pathlib import Path

from lib import cli, deps, report, workspace

HEADER = "Audit"
LIMIT = ("LIMIT: static reach only — names assigned at run time (_WORKFLOWNAME_, _FORMNAME_, _TABLENAME_), processes "
         "chosen from the database, open handlers, and entry points outside processes (_PROFILE, sitemaps, _form.xml "
         "and view WORKFLOW: strings, JSON workflow components) are not traced (knowledge/reference-graph.md §3)")
REPORTED_ABSENT = {"throws": "the loader throws", "caught": "the step records an error and the workflow goes on",
                   "template": "the runtime generates a default and writes it into the workspace"}


def build_parser():
    parser = cli.parser("audit_root.py", "Audit a workspaces root, or show a change's blast radius.")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds the workspaces")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--reach", nargs="+", metavar="PATH", help="configuration files, root-relative")
    mode.add_argument("--base", help="the base branch: reach every file changed against the merge-base")
    mode.add_argument("--changed", nargs="+", metavar="S:PATH", help="an explicit changed set: A:, M: or D:path")
    parser.add_argument("--app", help="audit one application only — for speed; the audit says it was narrowed")
    parser.add_argument("--skip-validators", action="store_true", help="whole-root audit only: skip the validators")
    return parser


def check_inputs(args):
    """Exit 3 on arguments that name nothing the audit can read."""
    import check_change
    from lib import plan
    root = Path(args.workspaces_root)
    if not root.is_dir():
        report.fail(report.EXIT_USAGE, f"--workspaces-root is not a directory: {root}")
    reach_mode = bool(args.reach or args.base or args.changed)
    if args.skip_validators and reach_mode:
        report.fail(report.EXIT_USAGE, "--skip-validators applies to a whole-root audit only")
    check_change.refuse(args.base, None, args.changed)
    for rel in args.reach or []:
        problem = plan.path_problem(rel[2:] if rel.startswith("./") else rel)
        if problem:
            report.fail(report.EXIT_USAGE, f"--reach takes paths relative to the workspaces root; `{rel}` {problem}")
    apps = workspace.applications(root)
    if args.app and args.app not in apps:
        report.fail(report.EXIT_USAGE, f"--app `{args.app}` is not an application under the root "
                                       f"({', '.join(apps) or 'none'})")
    if not apps:
        report.fail(report.EXIT_USAGE, "ERROR ROOT_NO_WORKSPACE the root holds no application workspace to audit")
    return root, [args.app] if args.app else apps


def narrowed(rep, app):
    rep.skipped("applications", f"narrowed to {app} by --app; the other applications were not audited")
    rep.add("AUDIT_NARROWED", f"the audit covers {app} and webasm only — a narrowed audit is never the whole root's "
                              f"(ADR 0026 §3)")


# --- the whole root --------------------------------------------------------------------

def run_validators(root, apps, narrow, rep):
    """{cli: [Report]} over the root's configuration, or over the audited applications' and webasm's.

    A walk collects a JSON file outside every FM/ as a draft, for a validator's own call. No loader reads one, so for
    the root it is no configuration: it is left out, and the report says so.
    """
    from lib import runner
    processes, workflows, configs = runner.targets(root)
    files = sorted({Path(os.path.relpath(p, root)).as_posix() for p in processes + workflows + configs})
    drafts = {rel for rel in files if rel.endswith(".json") and workspace.FM not in rel.split("/")}
    if drafts:
        rep.skipped("drafts", f"{len(drafts)} JSON file{'s' if len(drafts) > 1 else ''} outside every FM/, which no "
                              f"loader reads")
    keep = set(apps) | {workspace.BASE_WORKSPACE}
    files = [rel for rel in files if rel not in drafts and (not narrow or rel.split("/")[0] in keep)]
    runs, _ = runner.run(root, files)
    report.debug("audit_root.run_validators", "ran", files=len(files), drafts=len(drafts))
    return runs


def validator_lines(runs, rep):
    lines = []
    for name, reports in runs.items():
        counts = Counter((f.label, f.code) for r in reports for f in r.findings)
        shown = " ".join(f"{label} {code}={n}" for (label, code), n in sorted(counts.items()))
        lines.append(f"VALIDATOR: {name} files={len(reports)}{' ' + shown if shown else ''}")
        for r in reports:
            rep.findings += [in_the_root(f) for f in r.findings if f.label == "ERROR"]
    return lines


def in_the_root(finding):
    """A validator ERROR as the audit reports it: exit 1, a defect in the root — unless it is about the install.

    A validator's exit-3 code is about its call. For the audit, whose call was good, one about a file — a family that
    does not resolve, a file no schema selects — is a defect in the root. A vendored schema whose dialect the
    validators cannot read (json_validate.is_unknown_dialect) is about the plugin itself, and stays exit 3; a missing
    dependency and a malformed knowledge table stop the run before any finding.
    """
    from lib import json_validate  # needs jsonschema, which deps.require() has checked by now
    if finding.severity != report.EXIT_USAGE or json_validate.is_unknown_dialect(finding):
        return finding
    report.debug("audit_root.in_the_root", "a validator's usage code about a file", code=finding.code,
                 file=finding.file)
    return dataclasses.replace(finding, severity=report.EXIT_BLOCKED)


def check_failed(rep, check, exc):
    """A check that raised: exit 3 with the report so far, never exit 1, which reads as a defect in the root."""
    reason = f"stopped on {type(exc).__name__}: {(str(exc).splitlines() or [''])[0]}"
    report.debug("audit_root.check_failed", check, error=reason)
    if report.verbose():
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
    rep.skipped(check, reason)
    rep.add("AUDIT_CHECK_FAILED", f"the {check} {reason} — the audit is incomplete; --verbose prints the traceback")


def graph_lines(graphs):
    lines = []
    for app, g in graphs.items():
        status = Counter(edge.status for edge in g.edges)
        lines.append(f"GRAPH: {app} nodes={len(g.nodes)} edges={len(g.edges)} " +
                     " ".join(f"{s}={status.get(s, 0)}" for s in ("resolved", "unresolved", "case-only", "dynamic")))
        by_kind = {}
        for edge in g.edges:
            by_kind.setdefault(edge.kind, Counter())[edge.status] += 1
        for kind in sorted(by_kind):
            counts = by_kind[kind]
            lines.append(f"EDGE: {app} {kind} " + " ".join(f"{s}={counts.get(s, 0)}" for s in
                                                          ("resolved", "unresolved", "case-only", "dynamic")))
    return lines


def unchecked_references(graphs, rep):
    """AUDIT_REFERENCE_UNRESOLVED and CASE_ONLY_MATCH for the edges no validator checks, once per reference."""
    seen = {}
    for app, g in graphs.items():
        for edge in g.edges:
            if edge.checked_by != "—" or edge.restates_table or edge.status not in ("unresolved", "case-only"):
                continue
            if edge.status == "unresolved" and edge.when_absent not in REPORTED_ABSENT:
                continue
            seen.setdefault((edge.source, str(edge.line), edge.kind, edge.value, edge.status), []).append((app, edge))
    for (source, line, kind, value, status), found in sorted(seen.items()):
        apps = ", ".join(app for app, _ in found)
        edge = found[0][1]
        at = None if edge.line is None or isinstance(edge.line, str) else edge.line
        if status == "case-only":
            rep.add("CASE_ONLY_MATCH", f"{kind}: `{value}` reaches `{edge.target}` only on a case-insensitive "
                                       f"filesystem (in {apps})", line=at, file=source)
        else:
            why = f" — {edge.reason}" if edge.reason else ""
            rep.add("AUDIT_REFERENCE_UNRESOLVED", f"{kind}: `{value}` resolves nowhere in {apps} — expected "
                                                  f"`{edge.target}`{why}, and {REPORTED_ABSENT[edge.when_absent]}; no "
                                                  f"validator checks this reference", line=at, file=source)


def unreached_workflows(graphs, rep):
    """AUDIT_WORKFLOW_UNREACHED (INFO) for each shared workflow no graph's edges reach."""
    counts = Counter(node.path for g in graphs.values() for node in g.unreached())
    for path in sorted(counts):
        in_all = counts[path] == len(graphs) if path.startswith(workspace.BASE_WORKSPACE + "/") else True
        if in_all:
            rep.add("AUDIT_WORKFLOW_UNREACHED", "no traced reference reaches this shared workflow — a candidate, not "
                                                "dead code: an entry point outside processes may start it", file=path)


def role_lines(root):
    from lib import roles
    return [f'ROLE: "{name}" ' + " ".join(f"{source}={len(places)}" for source, places in sorted(sources.items()))
            for name, sources in sorted(roles.inventory(root).items())]


def audit_root(args, root, apps, rep, lines):
    """The whole-root audit, added to `rep` and `lines` as each part runs."""
    from lib import graph, knowledge
    graphs = {app: graph.build(root, app) for app in apps}
    rep.ran("graph")
    lines += graph_lines(graphs)
    if args.skip_validators:
        rep.skipped("validators", "skipped by --skip-validators")
    else:
        try:
            lines += validator_lines(run_validators(root, apps, bool(args.app), rep), rep)
        except knowledge.KnowledgeTableError:
            raise  # the install's defect, which main() reports as every script does
        except Exception as exc:  # the validators could not check the root, which is no finding about it
            check_failed(rep, "validators", exc)
        else:
            rep.ran("validators")
    rep.skipped("role-check", "nothing in the root declares roles (knowledge/permissions.md §1)")
    lines += role_lines(root)
    rep.ran("roles")  # only once it has: a raise before here leaves it out of CHECKS RUN
    unchecked_references(graphs, rep)
    unreached_workflows(graphs, rep)
    if args.app:
        narrowed(rep, args.app)


# --- reach ------------------------------------------------------------------------------

def reach_targets(args, root):
    """[(root-relative path, change status or None)] to reach."""
    import check_change
    from lib import git, plan
    if args.reach:
        return [(rel[2:] if rel.startswith("./") else rel, None) for rel in args.reach]
    if args.changed:
        changes = check_change.parse_changed(args.changed)
    else:
        if not git.available():
            report.fail(report.EXIT_USAGE, "--base needs git, which is not installed")
        try:
            changes = git.changed(root, git.merge_base(root, args.base))
        except git.GitError as exc:
            report.fail(report.EXIT_USAGE, f"no changed set against `{args.base}`: {exc}")
    found = []
    for change in changes:
        if plan.is_pipeline(change.path):
            continue
        found.append((change.path, "D" if change.status == "D" else change.status))
        if change.old:
            found.append((change.old, "D"))
    return found


def process_reference(path):
    """How a process at `path` is referenced: `P` in an application, `BASE:P` in webasm."""
    parts = path.split("/")
    return workspace.BASE_PREFIX + parts[3] if parts[0] == workspace.BASE_WORKSPACE else parts[3]


def chain_text(chain, target):
    hops = [f"{edge.source}:{edge.line}" if isinstance(edge.line, int) else edge.source for edge in chain]
    return " > ".join(hops + [target])


def reach_one(rel, status, graphs, root, rep, lines, narrowed=False):
    from lib import graph as graph_lib
    # Exactly as on Linux, where DGF runs: APFS and NTFS would find `ax.notify` for `AX.Notify`, and the graph,
    # whose nodes carry the case on disk, would then report that nothing reaches it (RULES.md rule 2).
    exact, actual = workspace.exact_file(root, rel.split("/"))
    on_disk = exact == workspace.OK
    report.debug("audit_root.reach_one", "target", file=rel, on_disk=exact)
    kind, content = graph_lib._parse(root / rel) if on_disk else (None, None)
    found = graph_lib.artifact_of(rel, content if kind == "xml" else None)
    if found is None or (status is None and not on_disk):
        if status is None:
            case = (f" — on disk it is `{actual.relative_to(root).as_posix()}`, and a name matches only byte for byte "
                    f"on Linux, where DGF runs" if exact == workspace.CASE_ONLY else "")
            rep.add("AUDIT_REACH_NOT_ARTIFACT", f"`{rel}` is not a configuration file under the root{case}", file=rel)
        else:
            lines.append(f"SKIP: {rel} — not a configuration file")
        return
    artifact, name = found
    deleted = status == "D" or not on_disk
    lines.append(f"REACH: {rel} artifact={artifact} name={name}" + (f" change={status}" if status else "") +
                 (" deleted — reached through references that now resolve nowhere" if deleted else ""))
    ws = rel.split("/")[0]
    if ws != workspace.BASE_WORKSPACE and ws not in graphs:
        # No graph holds this file's own processes, so nothing was walked: --app left its application out, or the
        # workspace is no application under the root now — a change that deleted it, say.
        lines.append(f"NOT AUDITED: {ws} — --app narrowed the audit to {', '.join(graphs)}, so no process of {ws} "
                     f"was walked" if narrowed else
                     f"NONE: {ws} — no application `{ws}` is under the root now, so no process of it was walked")
        report.debug("audit_root.reach_one", "no graph", file=rel, workspace=ws, narrowed=narrowed,
                     apps=",".join(graphs))
        return
    for app, g in graphs.items():
        if ws not in (app, workspace.BASE_WORKSPACE):
            continue
        reached = g.reach(rel)
        lines.append(f"APP: {app} processes={len(reached)}")
        for start, chain in reached:
            lines.append(f"PROCESS: {app} {process_reference(start)} via {chain_text(chain, rel)}")
            dynamic = next((edge for edge in chain if edge.status == "dynamic"), None)
            if dynamic is not None:
                rep.add("AUDIT_REFERENCE_DYNAMIC", f"in {app}, the chain from `{start}` passes a run-time name at "
                                                   f"{dynamic.source}:{dynamic.line} ({dynamic.kind}) — the step may "
                                                   f"load another file", file=rel)
        for edge in g.referrers(rel):
            lines.append(f"REFERRER: {app} {edge.kind} {edge.source}" +
                         (f":{edge.line}" if isinstance(edge.line, int) else ""))
        if not reached:
            lines.append(f"NONE: {app} — no traced reference reaches it")
    report.debug("audit_root.reach_one", "reached", file=rel, apps=",".join(graphs))


def audit_reach(args, root, apps, rep, lines):
    """The reach of each named or changed file, added to `rep` and `lines` as each part runs."""
    from lib import graph
    targets = reach_targets(args, root)
    graphs = {app: graph.build(root, app) for app in apps}
    rep.ran("graph")
    for rel, status in targets:
        reach_one(rel, status, graphs, root, rep, lines, narrowed=bool(args.app))
    rep.ran("reach")  # only once every target is reached
    if args.app:
        narrowed(rep, args.app)


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    root, apps = check_inputs(args)
    root = root.resolve()
    deps.require()
    from lib import knowledge
    mode = "reach" if (args.reach or args.base or args.changed) else "whole-root"
    report.debug("audit_root.main", "mode", mode=mode, applications=",".join(apps))
    from lib import json_validate
    rep = report.Report("audit")
    lines = [f"ROOT: {root}", f"APPLICATIONS: {' '.join(apps)} (base {workspace.BASE_WORKSPACE})"]
    try:  # what ran before a raise stays in the report
        (audit_reach if mode == "reach" else audit_root)(args, root, apps, rep, lines)
    except knowledge.KnowledgeTableError as exc:
        report.fail(report.EXIT_USAGE, f"ERROR KNOWLEDGE_TABLE {exc}")
    except json_validate.UnknownDialect as exc:  # a reference it hides is not one that is absent: the install's defect
        json_validate.add_unknown_dialect(rep, exc)
    except Exception as exc:  # the audit could not run, which is no finding about the root
        check_failed(rep, "audit", exc)
    return report.render([rep], header=HEADER, lines=lines + [LIMIT])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
