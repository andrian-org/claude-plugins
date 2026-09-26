#!/usr/bin/env python3
"""verify_gate.py — the verify gate: one computed `dgf-gate-result` block for a branch's change (ADR 0020 §9).

`/dgf-verify` relays this script's output verbatim. It never writes or edits a
block; the status is computed here, by scripts/lib/gate_result.py.

1. Discovery, in-process, by locate_plan.py's rules: the root is
   `--workspaces-root`, else the nearest `.dgf-factory/config.yaml`; the plan
   is `--plan`, else the branch's plan. No root, an ambiguous plan, or no plan
   for the branch is a `fail` with no check run. The gate never chooses a
   fallback plan: without `--plan` that is GATE_PLAN_UNCONFIRMED.
2. The call. The plan must be inside the root. With a plan, `--base` or
   `--changed` is required; a `--base` starting with `-`, or a `--changed`
   path that leaves the root, is exit 3.
3. check_plan.py's checks (`--overlap` unless `--no-overlap`). An unreadable
   plan stops here: the change checks are NOT RUN.
4. The validators' dependencies. When lxml or jsonschema is missing, that is
   DEPENDENCY_MISSING (exit 3), and the change checks still run without the
   validators, so `validators` and `baseline` are NOT RUN with the reason.
5. check_change.py's checks and the whole-root validator run, against the
   merge-base of `--base` (ADR 0018), or `--changed` with no baseline.
6. The gate's own findings: GATE_TASK_UNCHECKED for each unchecked task;
   under `--strict`, GATE_STRICT_WARNING for each WARN line check_change.py
   reported; GATE_CHECK_NOT_RUN for each required check that did not run.

Required checks: plan-header, plan-tasks, plan-files, plan-routes,
plan-commits, change-scope, change-means, change-planned, baseline and
validators — and frontend-tests when any task is `kind: code`. The gate never
runs frontend tests (ADR 0010 §2), so that one is always a warning.

The block: an ERROR line is a blocker and a WARN line a warning (a promoted
warning is a blocker, once); INFO — PRE_EXISTING, FIXED — is never an entry.
`checks_run` is every check that ran; `schema_family` counts the files the
validators read per family; `affected_components` and `affected_processes`
are the changed set's own configuration, not its blast radius (ADR 0020 §6).
The output ends with the block, and nothing follows it.

Usage:  verify_gate.py [--workspaces-root R] [--plans-dir D] [--fast-plan F] [--branch B] [--plan P]
                       [--base REF | --changed S:PATH ...] [--no-overlap] [--strict] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md) — they agree with the block's status:
  0  pass
  1  fail: a blocker — a defective plan, an unchecked task, a new finding, no
     root or no plan, or a promoted warning
  2  warn: warnings only, including a required check that did not run
  3  a finding forces it, and the block says `fail`: the gate could not run
     (the validators' dependencies missing, a knowledge table malformed, the
     plan unreadable), or a validator could not read a file (FAMILY_UNRESOLVED,
     SCHEMA_UNSELECTABLE). Or a usage error — including a plan outside the
     root — and then no block is printed
"""

import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import check_change
import check_plan
import locate_plan
from lib import cli, deps, gate_result, knowledge, plan, report, workspace

HEADER = "Verify gate"
GATE = "verify"
REQUIRED = ("plan-header", "plan-tasks", "plan-files", "plan-routes", "plan-commits", "change-scope",
            "change-means", "change-planned", "baseline", "validators")
FRONTEND_TESTS = "frontend-tests"
FRONTEND_REASON = "the project's own CI runs its frontend tests, never the gate — ADR 0010 §2"
SHOWN_MAX = 20
CUT_CODES = ("PRE_EXISTING", "FIXED")
UNREADABLE_PLAN = ("PLAN_UNREADABLE", "PLAN_FORMAT_UNSUPPORTED")
DISCOVERY = "."
PROCESS_DIR = "_PROCESS"
FORM_SCRIPT = "form-script"
# The gate could not run: the reason names the fix, and there is no command to suggest.
CANNOT_RUN = {
    "DEPENDENCY_MISSING": lambda: f"the validators cannot run — install lxml and jsonschema: {deps.install_command()}",
    "KNOWLEDGE_TABLE": lambda: "a knowledge table is malformed — run /dgf-doctor and reinstall the plugin",
    "ROOT_NOT_SET_UP": lambda: "there is no workspaces root — run /dgf in the workspaces root",
    "ROOT_AMBIGUOUS": lambda: "several workspaces roots were found — pass --workspaces-root",
    "PLAN_AMBIGUOUS": lambda: "more than one plan could be this branch's — pass --plan",
    "GATE_PLAN_UNCONFIRMED": lambda: "this branch has no plan of its own — pass --plan to verify against another",
}


@dataclass
class Run:
    """Everything one gate run found, in the order it was found."""
    discovery: object
    root: object = None
    plan_path: object = None
    plan_rel: object = None
    displays: dict = field(default_factory=dict)  # {path as a report shows it: root-relative path}
    lines: list = field(default_factory=list)
    plan_rep: object = None
    outcome: object = None
    parsed: object = None
    gate_rep: object = None
    skip_reason: object = None                    # why steps 4–6 did not run
    promoted: list = field(default_factory=list)  # (GATE_STRICT_WARNING finding, the WARN finding it promotes)
    not_run: list = field(default_factory=list)   # (GATE_CHECK_NOT_RUN finding, check, reason)
    tasks: dict = field(default_factory=dict)     # {id(GATE_TASK_UNCHECKED finding): task id}
    footprint: object = None                      # (affected_components, affected_processes), or None

    def reports(self):
        found = [self.discovery] if self.discovery.findings else []
        found += [self.plan_rep] if self.plan_rep else []
        found += self.outcome.reports if self.outcome else []
        return found + ([self.gate_rep] if self.gate_rep else [])


def build_parser():
    parser = cli.parser("verify_gate.py", "Gate a branch's DGF change and print one dgf-gate-result block.")
    parser.add_argument("--workspaces-root", help="the root; default: the nearest .dgf-factory/config.yaml")
    parser.add_argument("--plans-dir", default=str(locate_plan.DEFAULT_PLANS), help="relative to the root (paths.plans)")
    parser.add_argument("--fast-plan", default=str(locate_plan.DEFAULT_FAST), help="relative to the root (paths.plan)")
    parser.add_argument("--branch", help="the branch whose plan to find; default: the root's current branch")
    parser.add_argument("--plan", help="the plan entrypoint; default: the branch's plan")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--base", help="the base branch; the change is the working tree against the merge-base")
    source.add_argument("--changed", nargs="+", metavar="S:PATH",
                        help="an explicit changed set, root-relative: A:path, M:path or D:path (no baseline)")
    parser.add_argument("--no-overlap", action="store_true", help="skip the scan of other branches' plans")
    parser.add_argument("--strict", action="store_true", help="a new warning from the change check blocks")
    return parser


# --- 1. discovery -------------------------------------------------------------------

def _root_relative(root, path):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def _register(run, path):
    run.displays[cli.display(path)] = _root_relative(run.root, path)


def _refuse_outside(run, path):
    """Exit 3, with no block, on a plan outside the root: every file in the block is root-relative."""
    try:
        Path(path).resolve().relative_to(Path(run.root).resolve())
    except ValueError:
        report.debug("verify_gate.discover", "refused", plan=path, why="outside the root")
        report.fail(report.EXIT_USAGE, f"the plan must be inside the workspaces root {run.root}; {path} is not")


def discover(args, run):
    """The root and the plan, by locate_plan's rules; False when the gate cannot go on."""
    disc = run.discovery
    if args.workspaces_root:
        run.root = locate_plan.explicit_root(args.workspaces_root, disc)
    else:
        run.root = locate_plan.find_root(Path.cwd(), disc)
    if run.root is None:
        return False
    run.lines.append(f"ROOT: {run.root}")
    if args.plan:
        run.plan_path, source = plan.entrypoint(args.plan), "--plan"
        _refuse_outside(run, run.plan_path)
    else:
        branch = locate_plan.current_branch(run.root, args.branch)
        found = locate_plan.find_plan(run.root, run.root / args.plans_dir, run.root / args.fast_plan, branch, disc)
        if found is None:
            return False
        run.plan_path, source = found
        _refuse_outside(run, run.plan_path)
        if source != "branch":
            _register(run, run.plan_path)
            disc.add("GATE_PLAN_UNCONFIRMED", f"{cli.display(run.plan_path)} is not this branch's plan — the gate "
                                              f"never chooses a plan; pass --plan to verify against it",
                     file=cli.display(run.plan_path))
            return False
    _register(run, run.plan_path)
    run.plan_rel = _root_relative(run.root, run.plan_path)
    report.debug("verify_gate.discover", "found", root=run.root, plan=run.plan_rel, source=source)
    return True


# --- 2–5. the call, the plan and the change -------------------------------------------

def check_call(args):
    """Exit 3, with no block, on a call that cannot gate a change."""
    if args.base is None and not args.changed:
        report.fail(report.EXIT_USAGE, "verify_gate.py needs --base <branch> or --changed S:PATH …: the gate "
                                       "checks a change")
    check_change.refuse(args.base, None, args.changed)
    if args.changed:
        check_change.parse_changed(args.changed)


def check_the_plan(args, run):
    try:
        run.plan_rep, lines = check_plan.check(run.plan_path, run.root, overlap=not args.no_overlap)
    except knowledge.KnowledgeTableError as exc:
        run.gate_rep.add("KNOWLEDGE_TABLE", str(exc))
        run.skip_reason = "a knowledge table is malformed"
        return
    run.lines += lines
    if any(f.code in UNREADABLE_PLAN for f in run.plan_rep.findings):
        run.skip_reason = "the plan is unreadable"
        return
    run.parsed = plan.parse(run.plan_path)


def check_the_change(args, run):
    absent = deps.missing()
    skip = {}
    if absent:
        run.gate_rep.add("DEPENDENCY_MISSING", f"{', '.join(absent)} not installed — the validators cannot run. "
                                               f"Install with: {deps.install_command()}")
        skip = {"skip_validators": True, "skip_reason": f"{', '.join(absent)} not installed"}
    try:
        run.outcome = check_change.run(run.root, run.plan_path, base=args.base, changed=args.changed, **skip)
    except knowledge.KnowledgeTableError as exc:
        run.gate_rep.add("KNOWLEDGE_TABLE", str(exc))
        run.skip_reason = "a knowledge table is malformed"
        return
    run.lines += [line for line in run.outcome.lines if not line.startswith("PLAN: ")]


def trace_footprint(run):
    """The changed set's footprint, once; a malformed knowledge table is a finding, never a traceback."""
    if run.outcome is None or run.outcome.changes is None:
        return
    try:
        run.footprint = footprint(run.outcome.changes, run.outcome.known)
    except knowledge.KnowledgeTableError as exc:
        run.gate_rep.add("KNOWLEDGE_TABLE", str(exc))


# --- 6. the gate's own findings ----------------------------------------------------------

def audit_tasks(run):
    for task in run.parsed.tasks if run.parsed else []:
        if not task.checked:
            found = run.gate_rep.add("GATE_TASK_UNCHECKED", f"Task {task.id} is not checked: {task.title}",
                                     line=task.line)
            run.tasks[id(found)] = task.id


def promote(run):
    """Strict mode: every WARN line check_change.py reported blocks. They are new by construction."""
    for rep in run.outcome.reports if run.outcome else []:
        for found in rep.findings:
            if found.label == "WARN":
                gate = run.gate_rep.add("GATE_STRICT_WARNING", f"strict mode: [{found.code}] {found.message}",
                                        line=found.line, file=found.file)
                run.promoted.append((gate, found))


def code_tasks(run):
    return [t for t in (run.parsed.tasks if run.parsed else []) if (t.kind or "").strip() == "code"]


def required_checks(run):
    return list(REQUIRED) + ([FRONTEND_TESTS] if code_tasks(run) else [])


def account(run, required):
    """A GATE_CHECK_NOT_RUN warning, with the script's reason, for each required check that did not run."""
    reports = run.reports()
    ran = {check for rep in reports for check in rep.checks_run}
    reasons = {}
    for rep in reports:
        for check, why in rep.not_run:
            reasons.setdefault(check, why)
    for check in required:
        if check in ran:
            continue
        why = FRONTEND_REASON if check == FRONTEND_TESTS else reasons.get(check, run.skip_reason or "no script ran it")
        if check not in reasons:
            run.gate_rep.skipped(check, why)
        found = run.gate_rep.add("GATE_CHECK_NOT_RUN", f"{check} did not run: {why}")
        run.not_run.append((found, check, why))
        report.debug("verify_gate.required", "not run", check=check, why=why)


# --- the block ------------------------------------------------------------------------

def _rel(run, file):
    if file == DISCOVERY:
        return None
    return run.displays.get(file, file)


def _family(run, found, validator_ids):
    return run.outcome.families.get(found.file) if id(found) in validator_ids else None


def entries(run):
    """(blockers, warnings) from every finding, by ADR 0020's entry table."""
    promoted = {id(gate): original for gate, original in run.promoted}
    originals = {id(original) for _, original in run.promoted}
    not_run = {id(found): (check, why) for found, check, why in run.not_run}
    validator_ids = {id(f) for rep in (run.outcome.reports[1:] if run.outcome else []) for f in rep.findings}
    blockers, warnings = [], []
    for rep in run.reports():
        for found in rep.findings:
            if found.label == "INFO" or id(found) in originals:
                continue
            if id(found) in not_run:
                warnings.append(gate_result.not_run(*not_run[id(found)], file=run.plan_rel))
            elif id(found) in run.tasks:
                blockers.append(gate_result.entry(f"task-{run.tasks[id(found)]}", "error", found.message,
                                                  file=run.plan_rel, line=found.line))
            elif id(found) in promoted:
                was = promoted[id(found)]
                blockers.append(gate_result.entry(was.code, "warning", was.message, file=_rel(run, was.file),
                                                  line=was.line, schema_family=_family(run, was, validator_ids)))
            else:
                severity = "error" if found.label == "ERROR" else "warning"
                (blockers if severity == "error" else warnings).append(gate_result.entry(
                    found.code, severity, found.message, file=_rel(run, found.file), line=found.line,
                    schema_family=_family(run, found, validator_ids)))
    return blockers, warnings


def family_counts(families):
    counts = {"json": 0, "xsd": 0, "unresolved": 0}
    for family in families.values():
        counts[family if family in gate_result.FAMILIES else "unresolved"] += 1
    return counts


def _touched(changes):
    """(status, path) per changed path; a rename is its old path deleted and its new path added."""
    for change in changes:
        if change.status == "R" and change.old:
            yield "D", change.old
            yield "A", change.path
        else:
            yield change.status, change.path


def _form_file():
    return next(row["Filename"] for row in knowledge.load("legacy-artifacts") if row["Artifact"] == "form")


def _component_of(rel, inside):
    """(artifact, name) for a changed file outside every process folder, or None when it is no component."""
    klass = plan.classify(rel)
    if klass == "config":
        return plan.artifact(rel) or ("configuration", "/".join(inside[1:]))
    if klass == "code" and (plan.code_place(rel) or {}).get("Place") == FORM_SCRIPT:
        form = plan.artifact("/".join([*plan.segments(rel)[:-1], _form_file()]))
        return form if form and form[0] == "form" else None
    return None


def footprint(changes, known):
    """(affected_components, affected_processes): the configuration the change itself touched (ADR 0020 §6)."""
    components, processes = [], {}
    for status, rel in _touched(changes):
        ws = plan.workspace_of(rel)
        if ws not in known:
            continue
        inside = plan.segments(rel)[1:]
        if len(inside) >= 4 and inside[0] == plan.FM and inside[1] == PROCESS_DIR:
            name = inside[2]
            processes[(ws, name)] = {"workspace": ws, "name": name,
                                     "reference": workspace.process_reference(name, ws)}
            continue
        found = _component_of(rel, inside)
        if found:
            components.append({"workspace": ws, "artifact": found[0], "name": found[1], "file": rel,
                               "change": status})
    components.sort(key=lambda c: (c["file"], c["change"]))
    listed = [processes[key] for key in sorted(processes)]
    report.debug("verify_gate.footprint", "listed", components=len(components), processes=len(listed))
    return components, listed


def _errors(reports):
    return [f for rep in reports for f in rep.findings if f.label == "ERROR"]


def suggest(run, status, warnings):
    """(command, reason), first match wins (ADR 0020 §9)."""
    codes = {f.code for f in _errors(run.reports())}
    for code, why in CANNOT_RUN.items():
        if code in codes:
            return None, why()
    plan_errors = _errors([run.plan_rep] if run.plan_rep else [])
    if "PLAN_NOT_FOUND" in codes:
        return "/dgf-plan", "there is no plan for this branch — a change with no plan has no declared scope"
    if plan_errors:
        return "/dgf-plan", f"the plan is defective: {len(plan_errors)} error(s) — fix the plan before the change"
    change_errors = _errors(run.outcome.reports if run.outcome else [])
    parts = [f"{n} {what}" for n, what in ((len(run.tasks), "task(s) unchecked"),
                                           (len(change_errors), "new blocking finding(s)"),
                                           (len(run.promoted), "warning(s) promoted by --strict")) if n]
    if parts:
        return "/dgf-implement", "; ".join(parts)
    if status == "pass":
        return "/dgf-commit", "every required check ran and nothing blocks"
    if status == "warn":
        return "/dgf-commit", f"nothing blocks; review the {warnings} warning(s) first"
    return None, "the gate failed on a finding no command fixes — read the blockers"


def build_block(run, required, discovered):
    blockers, warnings = entries(run)
    status = "fail" if blockers else "warn" if warnings else "pass"
    command, reason = suggest(run, status, len(warnings))
    report.debug("verify_gate.status", "computed", status=status, blockers=len(blockers), warnings=len(warnings))
    report.debug("verify_gate.next", "chose", command=command, why=reason)
    kw = {"checks_run": list(dict.fromkeys(c for rep in run.reports() for c in rep.checks_run)),
          "required": required if discovered else (), "extra_files": [run.plan_rel] if run.plan_rel else []}
    outcome = run.outcome
    if outcome and "validators" in outcome.reports[0].checks_run:
        kw["schema_family"] = family_counts(outcome.families)
    if run.footprint is not None:
        kw["affected_components"], kw["affected_processes"] = run.footprint
    try:
        return gate_result.build(GATE, blockers, warnings, command, reason, **kw)
    except gate_result.GateContractError as exc:
        report.fail(report.EXIT_USAGE, f"the verify gate built a contradictory block: {exc}")


# --- output ---------------------------------------------------------------------------

def shown(rep):
    """`rep` with PRE_EXISTING and FIXED cut to their first SHOWN_MAX each."""
    kept, seen = [], dict.fromkeys(CUT_CODES, 0)
    for found in rep.findings:
        if found.code in seen:
            seen[found.code] += 1
            if seen[found.code] > SHOWN_MAX:
                continue
        kept.append(found)
    return replace(rep, findings=kept)


def summary_lines(args, run, status):
    lines = list(run.outcome.summary) if run.outcome else []
    source = f"--base {args.base}" if args.base else "--changed …"
    for code in CUT_CODES:
        total = sum(1 for rep in run.reports() for f in rep.findings if f.code == code)
        if total > SHOWN_MAX:
            lines.append(f"Shown: {SHOWN_MAX} of {total} {code} — check_change.py {source} lists every one")
    return lines + [f"STATUS: {status}"]


def emit(args, run, payload):
    lines = run.lines + [f"CODE TASK: {t.id} reason=\"{(t.reason or '').strip()}\"" for t in code_tasks(run)]
    code = report.render([shown(rep) for rep in run.reports()], header=HEADER, lines=lines,
                         summary=summary_lines(args, run, payload["status"]))
    print()
    print(gate_result.render(payload))
    return code


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    started = time.monotonic()
    run = Run(report.Report(DISCOVERY))
    if not discover(args, run):
        return emit(args, run, build_block(run, (), discovered=False))
    check_call(args)
    run.gate_rep = report.Report(cli.display(run.plan_path))
    check_the_plan(args, run)
    if run.skip_reason is None:
        check_the_change(args, run)
        trace_footprint(run)
    if run.skip_reason is None:
        audit_tasks(run)
        if args.strict:
            promote(run)
    required = required_checks(run)
    account(run, required)
    code = emit(args, run, build_block(run, required, discovered=True))
    report.debug("verify_gate.main", "done", exit=code, seconds=round(time.monotonic() - started, 2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
