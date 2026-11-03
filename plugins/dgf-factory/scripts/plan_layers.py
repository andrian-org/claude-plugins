#!/usr/bin/env python3
"""plan_layers.py — which tasks may a coordinator dispatch next, and which at once? (ADR 0033 §3)

Reads one plan entrypoint — a fast `PLAN.md`, a full plan, or an ultra bundle's
`index.md` — and answers from its tasks alone:

  ready     the unchecked tasks whose every `depends` is a checked task
  parallel  the ready tasks, in task order, admitted one by one while each
            declares at least one path in `files` or `deletes`, shares none
            with a task already admitted, and has none that is a folder
            holding an admitted task's path or lies inside one, up to
            --max-parallel (default 4)
  serial    every other ready task, with why: it shares a path with an
            admitted task, one of its paths is inside an admitted task's
            path or holds one (`a/b` and `a/b/c.xml`), it declares no files,
            or the batch is full

Paths are compared NFC-normalised and without regard to case: two paths that
differ only in case, or only in how an accented letter is encoded, name one
file on APFS and NTFS, so they never run at once.

A dependency that names no task, and a set of unchecked tasks that can never
become ready (a cycle, or a task behind one), are LAYERS_CYCLE, exit 1. Whether
the plan is otherwise sound is check_plan.py's question, not this script's: it
reports only what stops it from reading the tasks — PLAN_UNREADABLE or
PLAN_FORMAT_UNSUPPORTED, exit 3, as check_plan.py does. For an ultra plan it
names the phase file that holds each ready task's `## Task N` section. A
finished plan is exit 0 with `READY: none` and `REMAINING: 0`. Stdlib only;
reads no git and no workspace.

Usage:  plan_layers.py --workspaces-root <root> --plan <entrypoint> [--max-parallel <n>] [--verbose]

Output, in place of the `FAMILY:` lines:
  PLAN: <path> progress=<done>/<total>
  READY: <n>,… | none
  PARALLEL: <n>,… | none
  SERIAL: <n> — <why>                 one per held task, also an INFO LAYERS_SERIAL finding
  REMAINING: <n>                      unchecked tasks not yet ready
  PHASE: <n> <phase file>             ultra only, one per ready task

Exit codes (contract, see .ai-factory/rules/base.md):
  0  the layer is computed (also when the plan is finished)
  1  a dependency names no task, or some tasks can never become ready
  3  the plan is unreadable or its format unsupported, or a usage error
"""

if __name__ == "__main__":
    from lib import runtime; runtime.use_project_venv()

import re
import sys
import unicodedata
from pathlib import Path

from lib import cli, plan, report

HEADER = "Plan layers"
DEFAULT_MAX_PARALLEL = 4
MAX_PARALLEL_RANGE = (1, 8)
_SECTION = re.compile(r"## Task (\d+)\b")


def build_parser():
    parser = cli.parser("plan_layers.py",
                        "The next layer of a dgf-factory plan: what is ready, and what may run at once.")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds .dgf-factory/")
    parser.add_argument("--plan", required=True, help="the plan entrypoint: PLAN.md, <stem>.md or <stem>/index.md")
    parser.add_argument("--max-parallel", default=str(DEFAULT_MAX_PARALLEL),
                        help=f"the most tasks in one parallel batch, {MAX_PARALLEL_RANGE[0]}–{MAX_PARALLEL_RANGE[1]} "
                             f"(default {DEFAULT_MAX_PARALLEL})")
    return parser


def max_parallel(raw, parser):
    low, high = MAX_PARALLEL_RANGE
    if not re.fullmatch(r"[0-9]{1,2}", raw or "") or not low <= int(raw) <= high:
        parser.error(f"--max-parallel must be a whole number from {low} to {high}, not `{raw}`")
    return int(raw)


# --- the dependency graph ---------------------------------------------------------

def unreachable(tasks):
    """The unchecked tasks that can never become ready, as a sorted list of ids.

    A task becomes ready once every dependency is checked or will be. A
    dependency that names no task counts as met here — check_graph() reports it
    on its own — so what is left is held by a cycle alone.
    """
    ids = {task.id for task in tasks}
    done = {task.id for task in tasks if task.checked}
    pending = [task for task in tasks if not task.checked]
    progressed = True
    while progressed:
        progressed = False
        for task in pending:
            if task.id in done:
                continue
            deps = [d for d in task.depends if d in ids]
            if all(d in done and d != task.id for d in deps):
                done.add(task.id)
                progressed = True
    return sorted(task.id for task in pending if task.id not in done)


def check_graph(tasks, rep):
    ids = {task.id for task in tasks}
    for task in tasks:
        if task.checked:
            continue
        for dep in task.depends:
            if dep not in ids:
                rep.add("LAYERS_CYCLE", f"Task {task.id} depends on Task {dep}, which does not exist — it can never "
                                        f"become ready", line=task.line)
    stuck = unreachable(tasks)
    if stuck:
        named = ", ".join(f"Task {n}" for n in stuck)
        rep.add("LAYERS_CYCLE", f"{named} can never become ready: their dependencies form a cycle, or wait on one")
    report.debug("plan_layers.check_graph", "graph", tasks=len(tasks), stuck=",".join(map(str, stuck)) or "none")


def ready_tasks(tasks):
    checked = {task.id for task in tasks if task.checked}
    return [task for task in tasks if not task.checked and all(d in checked and d != task.id for d in task.depends)]


# --- the batch --------------------------------------------------------------------

def path_key(rel):
    """`rel` as it is compared: NFC, casefolded, NFC again, without a trailing `/`."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", rel).casefold()).rstrip("/")


def footprint(task):
    """{comparison key: the path as declared} for the task's `files` and `deletes`."""
    paths = {}
    for rel in task.files + task.deletes:
        paths.setdefault(path_key(rel), rel)
    return paths


def overlap(paths, claimed):
    """Why `paths` may not run beside the claimed ones — one shared, or one a folder of the other — or None."""
    for key, rel in paths.items():
        if key in claimed:
            other, task_id = claimed[key]
            return f"shares {rel} with task {task_id}" if other == rel else f"shares {rel} ({other}) with task {task_id}"
    for key, rel in paths.items():
        for held_key, (other, task_id) in claimed.items():
            if held_key.startswith(key + "/"):
                return f"declares {rel}, a folder holding {other} of task {task_id}"
            if key.startswith(held_key + "/"):
                return f"declares {rel}, inside {other} of task {task_id}"
    return None


def split_batch(ready, cap):
    """([admitted Task], [(held Task, why)]) — ready tasks in task order."""
    admitted, held, claimed = [], [], {}
    for task in ready:
        paths = footprint(task)
        shared = overlap(paths, claimed) if paths else None
        if not paths:
            held.append((task, "declares no files"))
        elif shared is not None:
            held.append((task, shared))
        elif len(admitted) >= cap:
            held.append((task, f"over --max-parallel {cap}"))
        else:
            admitted.append(task)
            for key, rel in paths.items():
                claimed[key] = (rel, task.id)
        report.debug("plan_layers.split_batch", "decided", task=task.id, paths=len(paths),
                     admitted=task in admitted)
    return admitted, held


def phase_files(parsed):
    """{task id: phase file path} for an ultra bundle, from its `## Phase Index` links."""
    bundle = Path(parsed.path).parent
    found = {}
    for target, _ in parsed.phase_links:
        name = target.split("#", 1)[0]
        if not name or "/" in name or "\\" in name or not (bundle / name).is_file():
            continue
        try:
            text = (bundle / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report.debug("plan_layers.phase_files", "unreadable phase", file=name, error=exc)
            continue
        for line in text.splitlines():
            heading = _SECTION.match(line)
            if heading:
                found.setdefault(int(heading.group(1)), bundle / name)
    return found


def _ids(tasks):
    return ",".join(str(task.id) for task in tasks) or "none"


def layers(plan_path, cap=DEFAULT_MAX_PARALLEL):
    """(Report, lines) for one plan entrypoint."""
    plan_path = plan.entrypoint(plan_path)
    rep = report.Report(cli.display(plan_path))
    rep.ran("plan-parse")
    try:
        parsed = plan.parse(plan_path)
    except plan.PlanFormatError as exc:
        rep.add("PLAN_UNREADABLE", exc.message, line=exc.line)
        return rep, [f"PLAN: {rep.file} unreadable"]
    fmt = parsed.header.get("plan_format")
    if fmt not in (None, "", plan.SUPPORTED_FORMAT):
        rep.add("PLAN_FORMAT_UNSUPPORTED", f"`plan_format: {fmt}` — this plugin reads format "
                                           f"{plan.SUPPORTED_FORMAT} only", line=parsed.header_lines.get("plan_format"))
        return rep, [f"PLAN: {rep.file} unsupported"]
    rep.ran("layers")
    tasks = parsed.tasks
    done, total = parsed.progress()
    check_graph(tasks, rep)
    ready = ready_tasks(tasks)
    admitted, held = split_batch(ready, cap)
    lines = [f"PLAN: {rep.file} progress={done}/{total}", f"READY: {_ids(ready)}", f"PARALLEL: {_ids(admitted)}"]
    for task, why in held:
        lines.append(f"SERIAL: {task.id} — {why}")
        rep.add("LAYERS_SERIAL", f"Task {task.id} is held serial: it {why}", line=task.line)
    lines.append(f"REMAINING: {total - done - len(ready)}")
    if parsed.mode == "ultra":
        phases = phase_files(parsed)
        lines += [f"PHASE: {task.id} {cli.display(phases[task.id])}" for task in ready if task.id in phases]
    report.debug("plan_layers.layers", "done", ready=_ids(ready), parallel=_ids(admitted), held=len(held))
    return rep, lines


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.verbose:
        report.set_verbose()
    cap = max_parallel(args.max_parallel, parser)
    if not Path(args.workspaces_root).is_dir():
        report.fail(report.EXIT_USAGE, f"--workspaces-root is not a directory: {args.workspaces_root}")
    rep, lines = layers(args.plan, cap)
    return report.render([rep], header=HEADER, lines=lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
