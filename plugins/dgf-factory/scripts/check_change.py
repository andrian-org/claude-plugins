#!/usr/bin/env python3
"""check_change.py — does a branch's change stay inside its plan, and what did it break? (ADR 0017 §6, ADR 0018)

The changed set is the working tree against the merge-base of HEAD and
`--base` (tracked changes plus untracked files), or an explicit `--changed`
list. Paths under `.dgf-factory/` are the pipeline's own and are ignored.

  change-scope    every changed file's workspace is in `affects_workspaces`
                  (ADR 0009); a file in no workspace is a warning. A workspace
                  the change deleted is still one: a deleted `<ws>/FM/…` path
                  proves `<ws>` had an `FM/`
  change-means    nothing excluded changed — C#, TypeScript, SQL, assemblies,
                  anything under `applibs*` (ADR 0010 §3); every code file that
                  changed is listed by a `kind: code` task (ADR 0005 rule 2); no
                  file was added under `js/`, `FM/js/` or `css/` (ADR 0017 §3)
  change-planned  every changed file is listed by a task; every checked task's
                  files changed and its deletes are gone
  baseline        the validators run at the working tree and at the merge-base
                  tree (materialised blob by blob, never `git archive`), on the
                  same scope. A finding at both is PRE_EXISTING (INFO), one only
                  at the base is FIXED (INFO); only new findings keep their code
                  and their exit (ADR 0018)

The validators run over the whole root, or over `--files` (root-relative).
Only a whole-root run records the check `validators` as run: a `--files` run
prints `NOT RUN: validators (narrowed to N file(s) by --files …)`, because the
gate's scope is the whole root (ADR 0026 §3, ADR 0022 §4). They need lxml and
jsonschema; `--skip-validators` runs only the three change checks and needs
neither. Without git or a merge-base the change checks are NOT RUN and every
validator finding counts as new — stricter, never looser.

Without git, a writing skill takes its own baseline (ADR 0025): with
`--changed`, `--save-baseline FILE` saves the run before its write — its
validator findings are written to FILE and not judged, so its exit is the
change checks' — and `--baseline FILE` settles the run after the write against
that one, exactly as against a merge-base tree. A saved baseline is refused
(BASELINE_UNUSABLE) when it is missing or malformed, or was saved for another
root or another `--files` scope. The verify gate never passes either flag.

run() is the same check as a function, for scripts/verify_gate.py: it returns
an Outcome holding the reports, the changed set and each validated file's
schema family.

Usage:  check_change.py --workspaces-root R --plan P (--base REF | --changed S:PATH ...)
                        [--files PATH ...] [--skip-validators] [--save-baseline FILE | --baseline FILE]
                        [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  the change is inside its plan and introduced no finding
  1  blocked: an undeclared workspace, an out-of-scope or unplanned code file,
     a new global script, or a new blocking validator finding
  2  warnings: an unplanned or untouched file, a file nothing authors, a new warning
  3  usage error — including a `--files` or `--changed` path that is not plain
     and root-relative, a `--base` that starts with `-`, or a saved baseline
     with `--base` or `--skip-validators` — an unreadable plan, a saved baseline
     that cannot be used, or the validators' dependencies missing
"""

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from lib import cli, git, knowledge, plan, report, workspace

HEADER = "Change check"
CHANGE_CHECKS = ("change-scope", "change-means", "change-planned")
NEW_FILE_STATUSES = ("A", "R")
SKIPPED = "--skip-validators"


@dataclass
class Outcome:
    """What run() found: what main() renders, and what the verify gate needs besides."""
    reports: list
    lines: list
    summary: list = field(default_factory=list)
    changes: object = None                         # [git.Change] outside .dgf-factory/, or None: no changed set
    known: set = field(default_factory=set)        # the workspaces, deleted ones included (known_workspaces)
    families: dict = field(default_factory=dict)   # {root-relative file: "json" | "xsd" | None}, the head run
    validated: int = 0                             # files the validators read
    parsed: object = None                          # the Plan, or None when it is unreadable


def build_parser():
    parser = cli.parser("check_change.py", "Check a branch's change against its plan and the merge-base.")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds .dgf-factory/")
    parser.add_argument("--plan", required=True, help="the plan entrypoint")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base", help="the base branch; the change is the working tree against the merge-base")
    source.add_argument("--changed", nargs="+", metavar="S:PATH",
                        help="an explicit changed set, root-relative: A:path, M:path or D:path")
    parser.add_argument("--files", nargs="+", metavar="PATH", help="the validator scope, root-relative")
    parser.add_argument("--skip-validators", action="store_true", help="run only the change checks")
    saved = parser.add_mutually_exclusive_group()
    saved.add_argument("--save-baseline", metavar="FILE",
                       help="with --changed: save this run's validator findings, unjudged, as the baseline of the "
                            "run after the write (ADR 0025)")
    saved.add_argument("--baseline", metavar="FILE",
                       help="with --changed: compare the validator findings with the baseline --save-baseline "
                            "saved before the write (ADR 0025)")
    return parser


def refuse_baseline(args):
    """Exit 3 on a saved baseline the call cannot use: the gate's baseline is the merge-base tree (ADR 0018)."""
    flag = "--save-baseline" if args.save_baseline else "--baseline" if args.baseline else None
    if flag is None:
        return
    if args.base is not None:
        report.fail(report.EXIT_USAGE, f"{flag} takes a --changed set: with --base the baseline is the merge-base "
                                       f"tree (ADR 0018)")
    if args.skip_validators:
        report.fail(report.EXIT_USAGE, f"{flag} needs the validators, which --skip-validators leaves out")


# --- the changed set ----------------------------------------------------------------

def parse_changed(values):
    changes = []
    for value in values:
        status, sep, rel = value.partition(":")
        if not sep or status not in ("A", "M", "D") or not rel.strip():
            report.fail(report.EXIT_USAGE, f"--changed takes A:path, M:path or D:path, not `{value}`")
        rel = rel.strip()
        changes.append(git.Change(status, rel[2:] if rel.startswith("./") else rel))
    return changes


def refuse(base, files, changed):
    """Exit 3 before any check runs on a path that leaves the root, or a `--base` git would read as an option."""
    if base is not None and base.startswith("-"):
        report.debug("check_change.inputs", "refused", arg="--base", why="starts with -")
        report.fail(report.EXIT_USAGE, f"--base takes a branch or commit, not `{base}`")
    named = [("--files", rel) for rel in files or []]
    named += [("--changed", value.partition(":")[2].strip()) for value in changed or []]
    for flag, rel in named:
        problem = plan.path_problem(rel[2:] if rel.startswith("./") else rel)
        if problem:
            report.debug("check_change.inputs", "refused", arg=flag, path=rel, why=problem)
            report.fail(report.EXIT_USAGE, f"{flag} takes paths relative to the workspaces root; `{rel}` {problem}")


def changes_from_git(root, base, rep):
    """(changes, merge-base sha), or (None, None) with the change checks NOT RUN."""
    reason = None
    if not git.available():
        reason = "git is not installed"
    else:
        try:
            sha = git.merge_base(root, base)
            return git.changed(root, sha), sha
        except git.GitError as exc:
            reason = f"no changed set against `{base}`: {exc}"
    for check_id in CHANGE_CHECKS:
        rep.skipped(check_id, reason)
    return None, None


def known_workspaces(root, changes):
    """The root's workspaces, plus each one a deleted path proves existed: `<ws>/FM/…` was there before.

    A change that deletes a workspace's last file leaves no `<ws>/FM/` behind, so
    the working tree alone would no longer call it a workspace, and the deletion
    would read as a file in no workspace.
    """
    known = set(workspace.workspace_names(root))
    for change in changes:
        gone = [change.path] if change.status == "D" else []
        gone += [change.old] if change.old else []
        for rel in gone:
            parts = plan.segments(rel)
            if len(parts) >= 3 and parts[1] == workspace.FM and not plan.is_plugin_assembly_folder(parts[0]):
                known.add(parts[0])
    report.debug("check_change.known_workspaces", "known", workspaces=",".join(sorted(known)))
    return known


def own_changes(changes):
    """The changes outside `.dgf-factory/`, which is the pipeline's own."""
    kept = [c for c in changes if not plan.is_pipeline(c.path) and not (c.old and plan.is_pipeline(c.old))]
    report.debug("check_change.own_changes", "kept", changed=len(changes), kept=len(kept))
    return kept


# --- the three change checks ------------------------------------------------------

def _listed(parsed):
    """({path: [task ids]} for any task, {path: [task ids]} for code tasks)."""
    anyone, code = {}, {}
    for task in parsed.tasks:
        for rel in task.files + task.deletes:
            anyone.setdefault(rel, []).append(task.id)
            if (task.kind or "").strip() == "code":
                code.setdefault(rel, []).append(task.id)
    return anyone, code


def change_line(change, known):
    ws = plan.workspace_of(change.path)
    line = f"CHANGE: {change.status} {change.path} class={plan.classify(change.path)} " \
           f"workspace={ws if ws in known else '-'}"
    return line + (f" from={change.old}" if change.old else "")


def check_scope(changes, declared, known, rep):
    rep.ran("change-scope")
    for change in changes:
        for rel in filter(None, (change.path, change.old)):
            ws = plan.workspace_of(rel)
            report.debug("check_change.classify", "scope", path=rel, workspace=ws, known=ws in known)
            if ws in known and ws not in declared:
                rep.add("CHANGE_UNDECLARED_WORKSPACE", f"`{rel}` changed in `{ws}`, which the plan's "
                                                       f"`affects_workspaces` does not list (ADR 0009)", file=rel)
            elif ws not in known and plan.classify(rel) != "excluded":
                rep.add("CHANGE_OUTSIDE_WORKSPACE", f"`{rel}` changed under the root but in no workspace", file=rel)


def check_means(changes, code_listed, rep):
    rep.ran("change-means")
    for change in changes:
        klass = plan.classify(change.path)
        if klass == "excluded":
            rep.add("CHANGE_OUT_OF_SCOPE", f"`{change.path}` changed — C#, TypeScript, SQL, assemblies and anything "
                                           f"under `applibs*` are out of scope (ADR 0010 §3)", file=change.path)
            continue
        if klass != "code":
            continue
        if change.path not in code_listed:
            rep.add("CHANGE_CODE_UNPLANNED", f"`{change.path}` is code, and no `kind: code` task lists it — script "
                                             f"needs a planned reason (ADR 0005 rule 2, ADR 0010 §2)",
                    file=change.path)
        place = plan.code_place(change.path)
        if change.status in NEW_FILE_STATUSES and place["New file loaded"] != "yes":
            rep.add("CHANGE_CODE_FILE_NEW", f"`{change.path}` was added under `{place['Path']}`, where nothing in the "
                                            f"workspaces root loads a new file (ADR 0017 §3)", file=change.path)


def _plain(task, paths):
    """The task's paths that are plain root-relative; check_plan.py reports the rest as PLAN_PATH_INVALID (D2)."""
    kept = []
    for rel in paths:
        if plan.path_problem(rel):
            report.debug("check_change.planned", "skipped a refused path", task=task.id, file=rel)
        else:
            kept.append(rel)
    return kept


def check_planned(changes, parsed, root, listed, rep):
    rep.ran("change-planned")
    for change in changes:
        klass = plan.classify(change.path)
        if klass == "other":
            rep.add("CHANGE_NOT_AUTHORED", f"`{change.path}` changed; it is neither configuration nor a code place",
                    file=change.path)
        if klass in ("config", "other") and change.path not in listed:
            rep.add("CHANGE_UNPLANNED_FILE", f"`{change.path}` changed, and no task lists it", file=change.path)
    changed = {c.path for c in changes} | {c.old for c in changes if c.old}
    for task in parsed.tasks:
        if not task.checked:
            continue
        for rel in _plain(task, task.files):
            if rel not in changed:
                rep.add("CHANGE_TASK_FILE_UNCHANGED", f"Task {task.id} is checked, but `{rel}` did not change",
                        line=task.line)
        for rel in _plain(task, task.deletes):
            if workspace.exact_file(root, plan.segments(rel))[0] == workspace.OK:
                rep.add("CHANGE_TASK_FILE_UNCHANGED", f"Task {task.id} is checked, but `{rel}`, which it deletes, "
                                                      f"still exists", line=task.line)


# --- the validators and the baseline (ADR 0018) --------------------------------------

def run_validators(root, files):
    """(every validator Finding, the number of files validated) for one tree.

    The run's working directory is the tree's root, so each finding's file, and
    each path a message shows through cli.display(), is root-relative — the same
    at the working tree and at the base tree.
    """
    from lib import runner
    root = Path(root).resolve()
    previous = os.getcwd()
    os.chdir(root)
    try:
        runs, _ = runner.run(root, files)
    finally:
        os.chdir(previous)
    findings, validated = [], set()
    for reports in runs.values():
        for rep in reports:
            validated.add(rep.file)
            findings.extend(rep.findings)
    report.debug("check_change.run_validators", "validated", root=root, files=len(validated), findings=len(findings))
    return runs, findings, len(validated)


def base_findings(root, base_sha, files):
    """The validators' findings at the merge-base tree, materialised blob by blob; GitError when it cannot be read."""
    import tempfile
    from lib import baseline
    with tempfile.TemporaryDirectory(prefix="dgf-base-") as tmp:
        started = time.monotonic()
        counts = git.materialise(root, base_sha, tmp)
        report.debug("check_change.base_findings", "materialised", seconds=round(time.monotonic() - started, 2),
                     **counts)
        _, findings, _ = run_validators(tmp, files)
        return findings, baseline.root_forms(tmp)


def validator_report(runs):
    merged = report.Report("(validators)")
    for reports in runs.values():
        for rep in reports:
            for check_id in rep.checks_run:
                merged.ran(check_id)
            for check_id, reason in rep.not_run:
                merged.skipped(check_id, reason)
    return merged


def settle(rep, merged, head, root, base_sha, files, reason, saved=None):
    """Fill `merged` with the new findings as themselves, and the rest as PRE_EXISTING or FIXED.

    `saved` is a baseline a run saved before the write (ADR 0025): its findings hold no root to remove.
    """
    from lib import baseline
    if saved is not None:
        rep.ran("baseline")
        return _merge(merged, *baseline.compare(head, saved, root, []))
    if base_sha is None:
        rep.skipped("baseline", f"{reason}; every finding counts as new")
        merged.findings.extend(head)
        return len(head), 0, 0
    try:
        base, base_forms = base_findings(root, base_sha, files)
    except git.GitError as exc:
        rep.skipped("baseline", f"the base tree could not be read: {exc}; every finding counts as new")
        merged.findings.extend(head)
        return len(head), 0, 0
    rep.ran("baseline")
    return _merge(merged, *baseline.compare(head, base, root, base_forms))


def _merge(merged, new, pre_existing, fixed):
    merged.findings.extend(new)
    for finding in pre_existing:
        merged.add("PRE_EXISTING", f"[{finding.code}] {finding.message}", line=finding.line, file=finding.file)
    for finding in fixed:
        merged.add("FIXED", f"[{finding.code}] {finding.message}", line=finding.line, file=finding.file)
    return len(new), len(pre_existing), len(fixed)


def families(runs):
    """{root-relative file: family} over every report of the head run; a resolved family wins."""
    found = {}
    for reports in runs.values():
        for rep in reports:
            if found.get(rep.file) is None:
                found[rep.file] = rep.family
    return found


def summary_lines(merged, validated):
    new = [f for f in merged.findings if f.code not in ("PRE_EXISTING", "FIXED")]
    errors = sum(1 for f in new if f.label == "ERROR")
    warnings = sum(1 for f in new if f.label == "WARN")
    pre = sum(1 for f in merged.findings if f.code == "PRE_EXISTING")
    fixed = sum(1 for f in merged.findings if f.code == "FIXED")
    return [f"Validated: {validated} file(s)",
            f"new: {errors} error(s), {warnings} warning(s); pre-existing: {pre}; fixed: {fixed}"]


def change_checks(parsed, root, base, changed, rep, outcome, saved=None):
    """The BASE:/CHANGE: lines and the three change checks; returns the merge-base sha, or None."""
    outcome.known = set(workspace.workspace_names(root))
    if changed:
        changes, base_sha = parse_changed(changed), None
        outcome.lines.append(f"BASE: {cli.display(Path(saved))} (saved before the write, --baseline)" if saved else
                             "BASE: none (--changed)")
    else:
        changes, base_sha = changes_from_git(root, base, rep)
        outcome.lines.append(f"BASE: {base_sha} ({base})" if base_sha else f"BASE: none ({base})")
    if changes is None:
        return base_sha
    changes = own_changes(changes)
    outcome.changes = changes
    known = outcome.known = known_workspaces(root, changes)
    outcome.lines.append(f"CHANGED: {len(changes)}")
    outcome.lines.extend(change_line(change, known) for change in changes)
    listed_ws = parsed.header.get("affects_workspaces")
    declared = set(listed_ws) if isinstance(listed_ws, list) else set()  # a bare scalar declares nothing
    listed, code_listed = _listed(parsed)
    check_scope(changes, declared, known, rep)
    check_means(changes, code_listed, rep)
    check_planned(changes, parsed, root, listed, rep)
    report.debug("check_change.check", "change checks", changed=len(changes), findings=len(rep.findings))
    return base_sha


def validate(root, files, changed, base_sha, rep, outcome, save_baseline=None, saved_baseline=None):
    """The validators at the working tree, settled against the merge-base tree (ADR 0018).

    Without git, a writing skill saves the run before its write (`save_baseline`), whose findings are not judged, and
    settles the run after it against that one (`saved_baseline`) — ADR 0025. The gate passes neither.
    """
    from lib import baseline
    root = Path(root).resolve()
    saved = None
    if saved_baseline is not None:
        try:
            saved = baseline.load(saved_baseline, root, files)
        except baseline.Unusable as exc:
            report.debug("check_change.validate", "baseline unusable", file=saved_baseline, why=str(exc))
            rep.add("BASELINE_UNUSABLE", str(exc), file=cli.display(Path(saved_baseline)))
            rep.skipped("baseline", "the saved baseline cannot be used")
            return
    runs, head, validated = run_validators(root, files)
    if files is None:
        rep.ran("validators")
    else:
        rep.skipped("validators", f"narrowed to {len(files)} file(s) by --files; the gate's scope is the whole "
                                  f"root (ADR 0026 §3)")
    merged = validator_report(runs)
    outcome.reports.append(merged)
    outcome.families = families(runs)
    outcome.validated = validated
    if save_baseline is not None:
        save(save_baseline, head, root, files, validated, rep, outcome)
        return
    reason = "--changed gives no base tree" if changed else "no merge-base"
    settle(rep, merged, head, root, base_sha, files, reason, saved=saved)
    outcome.summary.extend(summary_lines(merged, validated))


def save(path, head, root, files, validated, rep, outcome):
    """Save the run's findings as the baseline of the run after the write, and judge none of them (ADR 0025)."""
    from lib import baseline
    try:
        kept = baseline.save(path, head, root, files)
    except OSError as exc:
        rep.add("BASELINE_UNUSABLE", f"`{path}` cannot be written: {exc.strerror or exc}", file=cli.display(Path(path)))
        return
    errors = sum(1 for f in kept if f.label == "ERROR")
    warnings = sum(1 for f in kept if f.label == "WARN")
    rep.skipped("baseline", "this run saves the baseline of the run after the write; its findings are not judged")
    outcome.lines.append(f"BASELINE: saved {len(kept)} finding(s) — {errors} error(s), {warnings} warning(s) — "
                         f"to {cli.display(Path(path))}")
    outcome.summary.append(f"Validated: {validated} file(s)")
    report.debug("check_change.save", "saved", file=path, findings=len(kept), errors=errors, warnings=warnings)


def run(root, plan_path, *, base=None, changed=None, files=None, skip_validators=False, skip_reason=SKIPPED,
        save_baseline=None, saved_baseline=None):
    """The whole check for one plan → Outcome. `changed` is S:PATH values; KnowledgeTableError propagates.

    `skip_reason` is the reason recorded for `validators` and `baseline` when
    `skip_validators` is set. `save_baseline` and `saved_baseline` are a writing
    skill's, with `changed` and no git (ADR 0025); the verify gate passes neither.
    """
    plan_path = str(plan.entrypoint(plan_path))
    rep = report.Report(cli.display(plan_path))
    try:
        parsed = plan.parse(plan_path)
    except plan.PlanFormatError as exc:
        rep.add("PLAN_UNREADABLE", exc.message, line=exc.line)
        return Outcome([rep], [f"PLAN: {rep.file} unreadable"])
    outcome = Outcome([rep], [f"PLAN: {rep.file}"], parsed=parsed)
    base_sha = change_checks(parsed, root, base, changed, rep, outcome, saved=saved_baseline)
    if skip_validators:
        rep.skipped("validators", skip_reason)
        rep.skipped("baseline", skip_reason)
    else:
        validate(root, files, changed, base_sha, rep, outcome, save_baseline, saved_baseline)
    report.debug("check_change.run", "done", changed="-" if outcome.changes is None else len(outcome.changes),
                 validated=outcome.validated, families=",".join(sorted({str(f) for f in outcome.families.values()})))
    return outcome


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    refuse(args.base, args.files, args.changed)
    refuse_baseline(args)
    root = Path(args.workspaces_root)
    if not root.is_dir():
        report.fail(report.EXIT_USAGE, f"--workspaces-root is not a directory: {args.workspaces_root}")
    try:
        outcome = run(root, args.plan, base=args.base, changed=args.changed, files=args.files,
                      skip_validators=args.skip_validators, save_baseline=args.save_baseline,
                      saved_baseline=args.baseline)
    except knowledge.KnowledgeTableError as exc:
        report.fail(report.EXIT_USAGE, f"ERROR KNOWLEDGE_TABLE {exc}")
    return report.render(outcome.reports, header=HEADER, lines=outcome.lines, summary=outcome.summary)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
