#!/usr/bin/env python3
"""check_plan.py — is a plan well formed, in scope, routed and aware of its overlaps? (ADR 0017)

Reads one plan entrypoint — a fast `PLAN.md`, a full plan, or an ultra bundle's
`index.md` — and checks it against the workspaces root it plans for:

  plan-header   the flat frontmatter: required keys, allowed values, each
                workspace in `affects_workspaces` real, `base_workspace_reason`
                when `webasm` is listed, and the file stem = branch with / → -
  plan-tasks    checkbox tasks with unique ids, known dependencies, a `kind`,
                a `reason` for `kind: code`, and `files` or `deletes`; for
                ultra, every phase link a direct child of the bundle
  plan-files    each path's class (config, code, excluded, other), its
                workspace declared, its class matching the task's kind, and no
                new file where nothing loads one
  plan-routes   each NEW configuration file in the family route_means.route()
                gives it; existing files are edited in their own family
  plan-overlap  (--overlap) every other active plan in the working tree and at
                every local and remote-tracking branch tip that shares a
                workspace; `webasm` is shared with every plan. Never fetches.

A folder with no route is PLAN_ROUTE_UNKNOWN, exit 1, where route_means.py
exits 3 for the same condition: a plan is an artifact its planner can fix
(ADR 0017 §6). Needs git for --overlap only. Stdlib only.

Usage:  check_plan.py <plan> --workspaces-root <root> [--overlap] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  the plan is sound
  1  the plan is defective — /dgf-plan fixes it; nothing is implemented from it
  2  warnings: an overlap, a ◐ component, a file nothing authors
  3  the header is unreadable or the format unsupported, or a usage error
"""

import datetime
import re
import sys
from pathlib import Path

import route_means
from lib import cli, git, json_resolve, knowledge, plan, report, workspace

HEADER = "Plan check"
REQUIRED = ("plan_format", "mode", "branch", "created", "affects_workspaces")
SUPPORTED_FORMAT = "1"
BASE = workspace.BASE_WORKSPACE
COMPONENTS = "_COMPONENTS"
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


def build_parser():
    parser = cli.parser("check_plan.py", "Check a dgf-factory plan against its workspaces root.")
    parser.add_argument("plan", help="the plan entrypoint: PLAN.md, <stem>.md or <stem>/index.md")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds .dgf-factory/")
    parser.add_argument("--overlap", action="store_true", help="scan other active plans for shared workspaces")
    return parser


def exists(root, rel):
    """The file exists at exactly this case — the runtime runs on Linux (ADR 0014 §2)."""
    return workspace.exact_file(root, plan.segments(rel))[0] == workspace.OK


def affects(parsed):
    value = parsed.header.get("affects_workspaces")
    return value if isinstance(value, list) else []


# --- plan-header ------------------------------------------------------------------

def check_header(parsed, root, known, rep):
    rep.ran("plan-header")
    head, where = parsed.header, parsed.header_lines
    for key in head:
        if key not in plan.HEADER_KEYS:
            rep.add("PLAN_FIELD_INVALID", f"`{key}` is not a plan header key — the keys are "
                                          f"{', '.join(plan.HEADER_KEYS)}", line=where.get(key))
    for key in REQUIRED:
        if head.get(key) in (None, "", []):
            what = "is empty — a plan affects at least one workspace" if head.get(key) == [] else "is missing"
            rep.add("PLAN_FIELD_MISSING", f"`{key}` {what}", line=where.get(key))
    _check_values(head, where, rep)
    _check_workspaces(head, where, known, rep)
    _check_stem(parsed, rep)


def _check_values(head, where, rep):
    for key, value in head.items():
        if key in plan.HEADER_KEYS and key != "affects_workspaces" and isinstance(value, list):
            rep.add("PLAN_FIELD_INVALID", f"`{key}` takes one value, not a list", line=where.get(key))
    listed = head.get("affects_workspaces")
    if listed is not None and not isinstance(listed, list):
        rep.add("PLAN_FIELD_INVALID", "`affects_workspaces` must be a `[ … ]` list", line=where.get("affects_workspaces"))
    mode = head.get("mode")
    if isinstance(mode, str) and mode not in plan.MODES:
        rep.add("PLAN_FIELD_INVALID", f"`mode: {mode}` — it is fast, full or ultra", line=where.get("mode"))
    created = head.get("created")
    if isinstance(created, str) and not _is_date(created):
        rep.add("PLAN_FIELD_INVALID", f"`created: {created}` is not a YYYY-MM-DD date", line=where.get("created"))
    if head.get("branch") == "none" and mode in ("full", "ultra"):
        rep.add("PLAN_FIELD_INVALID", f"`branch: none` is allowed only on a fast plan; a {mode} plan lives on its "
                                      f"branch", line=where.get("branch"))


def _is_date(text):
    if not _DATE.match(text):
        return False
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _unknown_workspace_message(name, known):
    if plan.is_plugin_assembly_folder(name):
        return (f"`{name}` is a plugin-assembly folder (`.dll` files, no `FM/`), not a workspace — nothing under it "
                f"is authored (ADR 0017 §4)")
    if name == BASE:
        return ("`webasm` is listed, but this root has no `webasm/FM/` — the base workspace lives outside it "
                "(the inventory reports BASE_WORKSPACE_ABSENT), so its files cannot be planned or checked here")
    return (f"`{name}` is not a workspace under the root — no `{name}/` with an exact-case `FM/`; the workspaces "
            f"are {', '.join(sorted(known)) or '(none)'}")


def _check_workspaces(head, where, known, rep):
    listed = head.get("affects_workspaces")
    if not isinstance(listed, list):
        return
    line = where.get("affects_workspaces")
    for index, name in enumerate(listed):
        if name in listed[:index]:
            rep.add("PLAN_FIELD_INVALID", f"`{name}` is listed twice in `affects_workspaces`", line=line)
        elif name not in known:
            rep.add("PLAN_UNKNOWN_WORKSPACE", _unknown_workspace_message(name, known), line=line)
    reason = head.get("base_workspace_reason")
    if BASE in listed and not (isinstance(reason, str) and reason.strip()):
        rep.add("PLAN_BASE_REASON_MISSING", "`webasm` is listed, so `base_workspace_reason` must say why the base "
                                            "workspace changes — every application sees it (ADR 0005 rule 3)",
                line=where.get("base_workspace_reason", line))


def plan_stem(parsed):
    path = Path(parsed.path)
    return path.parent.name if parsed.mode == "ultra" else path.stem


def _check_stem(parsed, rep):
    branch = parsed.header.get("branch")
    if parsed.mode not in ("full", "ultra") or not isinstance(branch, str) or branch in ("", "none"):
        return
    expected = branch.replace("/", "-")
    if plan_stem(parsed) != expected:
        rep.add("PLAN_BRANCH_MISMATCH", f"the plan is named `{plan_stem(parsed)}`, but branch `{branch}` names it "
                                        f"`{expected}` — the stem is the branch with `/` → `-` (ADR 0017 §7)",
                line=parsed.header_lines.get("branch"))


# --- plan-tasks -------------------------------------------------------------------

def check_tasks(parsed, rep):
    rep.ran("plan-tasks")
    if not parsed.tasks:
        where = "`## Tasks` holds no `- [ ] Task N:` line" if parsed.tasks_section else "there is no `## Tasks` section"
        rep.add("PLAN_NO_TASKS", where)
        return
    ids = [task.id for task in parsed.tasks]
    for index, task in enumerate(parsed.tasks):
        if task.id in ids[:index]:
            rep.add("PLAN_TASK_INVALID", f"Task {task.id} is numbered twice", line=task.line)
        _check_task(task, set(ids), rep)
    _check_cycles(parsed.tasks, rep)
    if parsed.mode == "ultra":
        _check_bundle(parsed, rep)


def _check_task(task, ids, rep):
    for dep in task.depends:
        if dep == task.id or dep not in ids:
            what = "itself" if dep == task.id else f"Task {dep}, which does not exist"
            rep.add("PLAN_TASK_INVALID", f"Task {task.id} depends on {what}", line=task.line)
    for name in task.duplicates:
        rep.add("PLAN_TASK_INVALID", f"Task {task.id} gives `{name}:` twice", line=task.line)
    kind = (task.kind or "").strip()
    if not kind:
        rep.add("PLAN_TASK_INVALID", f"Task {task.id} has no `kind:` — every task is config or code", line=task.line)
    elif kind not in plan.KINDS:
        rep.add("PLAN_TASK_INVALID", f"Task {task.id} has `kind: {kind}` — it is config or code", line=task.line)
    if not task.files and not task.deletes:
        rep.add("PLAN_TASK_INVALID", f"Task {task.id} lists no `files:` or `deletes:`", line=task.line)
    if kind == "code" and not (task.reason or "").strip():
        rep.add("PLAN_CODE_REASON_MISSING", f"Task {task.id} is `kind: code` with no `reason:` — name the "
                                            f"configuration route tried and why it cannot express the change "
                                            f"(ADR 0010 §2)", line=task.line)


def _check_cycles(tasks, rep):
    graph = {task.id: [d for d in task.depends if d != task.id] for task in tasks}
    state = {}

    def visit(node, trail):
        state[node] = "open"
        for dep in graph.get(node, []):
            if state.get(dep) == "open":
                return trail + [node, dep]
            if dep in graph and dep not in state:
                found = visit(dep, trail + [node])
                if found:
                    return found
        state[node] = "done"
        return None

    for task in tasks:
        if task.id not in state:
            cycle = visit(task.id, [])
            if cycle:
                start = cycle.index(cycle[-1])
                loop = " → ".join(f"Task {n}" for n in cycle[start:])
                rep.add("PLAN_TASK_INVALID", f"the dependencies form a cycle: {loop}", line=task.line)
                return


def _check_bundle(parsed, rep):
    bundle = Path(parsed.path).parent
    if Path(parsed.path).name != "index.md":
        rep.add("PLAN_ULTRA_BROKEN", "an ultra plan's entrypoint is the bundle's `index.md`")
    if not parsed.phase_links:
        rep.add("PLAN_ULTRA_BROKEN", "`## Phase Index` links no phase file")
    targets = list(parsed.phase_links) + [(link, task.line) for task in parsed.tasks for link in task.links]
    for target, line in targets:
        name = target.split("#", 1)[0]
        if not name or _SCHEME.match(name):
            continue
        if "/" in name or "\\" in name or name in (".", ".."):
            rep.add("PLAN_ULTRA_BROKEN", f"`{target}` is not a file directly inside the bundle", line=line)
        elif workspace.exact_child(bundle, name)[0] != workspace.OK or not (bundle / name).is_file():
            rep.add("PLAN_ULTRA_BROKEN", f"`{target}` names `{name}`, which the bundle does not hold", line=line)


# --- plan-files -------------------------------------------------------------------

def _paths(task):
    lines = {name: task.fields[name][1] for name in ("files", "deletes") if name in task.fields}
    return [(rel, False, lines.get("files")) for rel in task.files] + \
           [(rel, True, lines.get("deletes")) for rel in task.deletes]


def _out_of_scope_message(rel):
    if plan.is_plugin_assembly_folder(plan.workspace_of(rel)):
        return f"`{rel}` is inside a plugin-assembly folder — assemblies are out of scope (ADR 0010 §3, ADR 0017 §4)"
    return (f"`{rel}` is C#, TypeScript, SQL, an assembly or server markup — out of scope for this plugin "
            f"(ADR 0010 §3); name the need under `## Scope` for a general coding flow")


def check_files(parsed, root, known, rep):
    rep.ran("plan-files")
    declared = set(affects(parsed))
    for task in parsed.tasks:
        kind = (task.kind or "").strip()
        for rel, deleting, line in _paths(task):
            _check_file(task, kind, rel, deleting, line, root, declared, known, rep)


def _check_file(task, kind, rel, deleting, line, root, declared, known, rep):
    klass = plan.classify(rel)
    ws = plan.workspace_of(rel)
    if klass == "excluded":
        rep.add("PLAN_OUT_OF_SCOPE", f"Task {task.id}: {_out_of_scope_message(rel)}", line=line)
        return
    if ws not in declared or ws not in known:
        why = "is not in `affects_workspaces`" if ws in known else "is not a workspace under the root"
        rep.add("PLAN_FILE_UNDECLARED_WORKSPACE", f"Task {task.id}: `{rel}` — `{ws}` {why}", line=line)
        return
    if klass == "other":
        rep.add("PLAN_NOT_AUTHORED", f"Task {task.id}: `{rel}` is neither configuration nor a code place — this "
                                     f"plugin does not author it", line=line)
        return
    if kind in plan.KINDS and klass != kind:
        what = "configuration" if klass == "config" else f"a code file ({plan.code_place(rel)['Place']})"
        rep.add("PLAN_KIND_MISMATCH", f"Task {task.id} is `kind: {kind}`, but `{rel}` is {what}", line=line)
        return
    if klass == "code" and not deleting and not exists(root, rel):
        place = plan.code_place(rel)
        if place["New file loaded"] != "yes":
            rep.add("PLAN_CODE_FILE_NEW", f"Task {task.id}: `{rel}` does not exist, and nothing in the workspaces "
                                          f"root loads a new `{place['Path']}` file — only a deployment bind-mount "
                                          f"does (knowledge/composition-specs.md §5). Edit an existing file, or use "
                                          f"the form's `_form.js` (ADR 0017 §3)", line=line)


# --- plan-routes ------------------------------------------------------------------

def loader_folders():
    return [row["Folder"] for row in knowledge.load("component-folders") if not row["Folder"].startswith("(")]


def check_routes(parsed, root, rep):
    rep.ran("plan-routes")
    folders = loader_folders()
    for task in parsed.tasks:
        line = task.fields["files"][1] if "files" in task.fields else task.line
        for rel in task.files:
            if plan.classify(rel) != "config" or exists(root, rel):
                continue
            report.debug("check_plan.routes", "routing a new file", task=task.id, file=rel)
            _route_new_file(task, rel, line, folders, rep)


def _route_new_file(task, rel, line, folders, rep):
    inside = plan.segments(rel)[1:]
    mismatch = lambda why: rep.add("PLAN_ROUTE_MISMATCH", f"Task {task.id}: new `{rel}` — {why}", line=line)
    if len(inside) >= 3 and inside[1] == COMPONENTS:
        _route_component(task, rel, inside[2:], line, folders, rep, mismatch)
        return
    for row in knowledge.load("legacy-artifacts"):
        as_json = row["Filename"][:-len(".xml")] + ".json"
        if inside[-1] == as_json and plan.matches_folder(plan.segments(row["Folder"]), inside[:-1]):
            mismatch(f"a new {row['Artifact']} is `{row['Filename']}`, never JSON — the five legacy types stay XML "
                     f"(ADR 0005 rule 1, knowledge/composition-specs.md §2)")
            return


def _route_component(task, rel, below, line, folders, rep, mismatch):
    if below[-1].lower().endswith(".xml"):
        mismatch("an `.xml` file under `_COMPONENTS/` is read by no loader; component configuration there is JSON")
        return
    if len(below) == 1:
        return  # directly under _COMPONENTS/: the site map (knowledge/json-reader.md §4, `(root)`)
    folder = below[0]
    if folder in folders:
        return
    member = next((f for f in folders if f.lower() == folder.lower()), None) or json_resolve.component_member(folder)
    if member is None:
        rep.add("PLAN_ROUTE_UNKNOWN", f"Task {task.id}: new `{rel}` — `_COMPONENTS/{folder}/` is neither a loader "
                                      f"folder nor a ComponentType, so nothing reads it and no route exists",
                line=line)
        return
    if member != folder:
        mismatch(f"folder case: the loader builds `_COMPONENTS/{member}/` from the member's own spelling, and Linux "
                 f"matches it exactly (knowledge/json-reader.md §4)")
        return
    probe = report.Report(rep.file)
    found = route_means.route(member, probe)
    if found is None:
        detail = probe.findings[0].message if probe.findings else f"`{member}` has no route"
        rep.add("PLAN_ROUTE_UNKNOWN", f"Task {task.id}: new `{rel}` — {detail}", line=line)
        return
    family, where, reason = found
    if family == "xml":
        mismatch(f"{reason}; write it at {where}")
    for finding in probe.findings:
        if finding.code == "PARITY_PARTIAL":
            rep.add("PARITY_PARTIAL", f"Task {task.id}: new `{rel}` — {finding.message}", line=line)


# --- plan-overlap (ADR 0017 §5) ---------------------------------------------------

def _is_plan_path(rel):
    parts = rel.split("/")
    if parts[:1] != [plan.PIPELINE_DIR]:
        return False
    if parts[1:] == ["PLAN.md"]:
        return True
    if parts[1:2] != ["plans"]:
        return False
    return (len(parts) == 3 and parts[2].endswith(".md")) or (len(parts) == 4 and parts[3] == "index.md")


def working_tree_plans(root):
    base = Path(root) / plan.PIPELINE_DIR
    found = [base / "PLAN.md"] + sorted((base / "plans").glob("*.md")) + sorted((base / "plans").glob("*/index.md"))
    return [p.relative_to(root).as_posix() for p in found if p.is_file()]


def _short(ref):
    for prefix in ("refs/heads/", "refs/remotes/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def _is_self(rel, ref, this):
    """The copy of the plan under check at `ref` — skipped, never an overlap with itself."""
    if rel != this["rel"]:
        return False
    if this["mode"] in ("full", "ultra"):
        return True  # its stem is its branch, so this path is this plan wherever it is
    for branch in (this["branch"], this["current"]):
        if branch and branch != "none" and (ref == f"refs/heads/{branch}" or ref.endswith(f"/{branch}")):
            return True
    return False


def _identity(rel, content):
    """Plans under plans/ are named by branch, so one path is one plan; PLAN.md is shared, so content counts."""
    return rel if rel.split("/")[1] == "plans" else (rel, content)


def collect_candidates(root, this):
    """({identity: {"rel", "versions": {content: [labels]}}}, refs scanned)."""
    groups = {}

    def add(rel, label, content):
        group = groups.setdefault(_identity(rel, content), {"rel": rel, "versions": {}})
        group["versions"].setdefault(content, []).append(label)

    for rel in working_tree_plans(root):
        if rel != this["rel"]:
            add(rel, "the working tree", (Path(root) / rel).read_bytes())
    refs, blobs = git.refs(root), {}
    for ref, _ in refs:
        for entry in git.ls_tree(root, ref, plan.PIPELINE_DIR):
            if entry.kind != "blob" or not _is_plan_path(entry.path) or _is_self(entry.path, ref, this):
                continue
            if entry.sha not in blobs:
                blobs[entry.sha] = git.show(root, entry.sha)
            add(entry.path, _short(ref), blobs[entry.sha])
            report.debug("check_plan.overlap", "candidate", ref=ref, path=entry.path, blob=entry.sha[:12])
    return groups, len(refs)


def _labels(labels):
    unique = list(dict.fromkeys(labels))
    shown = ", ".join(unique[:3])
    return shown + (f" and {len(unique) - 3} more" if len(unique) > 3 else "")


def _active_workspaces(group, rep):
    """The union of `affects_workspaces` over the active versions; unreadable versions are INFO."""
    union, active = set(), False
    for content, labels in group["versions"].items():
        try:
            other = plan.parse_text(content.decode("utf-8"), group["rel"])
        except (plan.PlanFormatError, UnicodeDecodeError) as exc:
            rep.add("PLAN_OVERLAP_UNREADABLE", f"`{group['rel']}` at {_labels(labels)} does not parse ({exc}); "
                                               f"skipped")
            continue
        listed = affects(other)
        done, total = other.progress()
        if not listed:
            rep.add("PLAN_OVERLAP_UNREADABLE", f"`{group['rel']}` at {_labels(labels)} has no `affects_workspaces`; "
                                               f"skipped")
        elif done < total:
            active = True
            union |= set(listed)
    return active, union


def check_overlap(parsed, root, rep, lines):
    this_set = set(affects(parsed))
    if not this_set:
        rep.skipped("plan-overlap", "the plan has no readable `affects_workspaces`")
        return
    if not git.available():
        rep.skipped("plan-overlap", "git is not installed")
        return
    try:
        git.toplevel(root)
        rel = Path(parsed.path).resolve().relative_to(Path(root).resolve()).as_posix()
    except git.GitError:
        rep.skipped("plan-overlap", "the workspaces root is not in a git work tree")
        return
    except ValueError:
        rel = None
    try:
        this = {"rel": rel, "mode": parsed.mode, "branch": parsed.header.get("branch"),
                "current": git.current_branch(root)}
        groups, scanned = collect_candidates(root, this)
    except git.GitError as exc:
        rep.skipped("plan-overlap", f"git failed: {exc}")
        return
    rep.ran("plan-overlap")
    lines.append(f"OVERLAP SOURCES: {scanned} refs scanned, plus the working tree; remote refs as of the last fetch")
    for group in groups.values():
        active, union = _active_workspaces(group, rep)
        shared = sorted(union & this_set)
        report.debug("check_plan.overlap", "decided", path=group["rel"], active=active, shared=",".join(shared))
        if not active or not (shared or BASE in union or BASE in this_set):
            continue
        labels = _labels([label for labels in group["versions"].values() for label in labels])
        named = ", ".join(f"`{ws}`" for ws in shared if ws != BASE)
        base = "`webasm`, which is shared with every plan" if BASE in union | this_set else ""
        rep.add("PLAN_OVERLAP", f"`{group['rel']}` at {labels} is active and shares "
                                f"{' and '.join(part for part in (named, base) if part)}")


# --- report -----------------------------------------------------------------------

def task_line(task):
    parts = [f"TASK: {task.id} [{'x' if task.checked else ' '}] kind={(task.kind or '?').strip()}"]
    if task.depends:
        parts.append("depends=" + ",".join(map(str, task.depends)))
    if task.files:
        parts.append("files=" + ",".join(task.files))
    if task.deletes:
        parts.append("deletes=" + ",".join(task.deletes))
    return " ".join(parts)


def check(plan_path, root, overlap=False):
    """(Report, the PLAN:/TASK: lines) for one plan entrypoint."""
    rep = report.Report(cli.display(plan_path))
    try:
        parsed = plan.parse(plan_path)
    except plan.PlanFormatError as exc:
        rep.add("PLAN_UNREADABLE", exc.message, line=exc.line)
        return rep, [f"PLAN: {rep.file} unreadable"]
    head = parsed.header
    lines = [f"PLAN: {rep.file} mode={head.get('mode')} format={head.get('plan_format')} branch={head.get('branch')}"]
    if head.get("plan_format") != SUPPORTED_FORMAT:
        rep.add("PLAN_FORMAT_UNSUPPORTED", f"`plan_format: {head.get('plan_format')}` — this plugin reads format "
                                           f"{SUPPORTED_FORMAT} only", line=parsed.header_lines.get("plan_format"))
        return rep, lines
    known = workspace.workspace_names(root)
    lines.append(f"AFFECTS: {', '.join(affects(parsed)) or '(none)'}")
    lines += [task_line(task) for task in parsed.tasks]
    done, total = parsed.progress()
    lines.append(f"PROGRESS: {done}/{total}")
    check_header(parsed, root, known, rep)
    check_tasks(parsed, rep)
    check_files(parsed, root, known, rep)
    check_routes(parsed, root, rep)
    if overlap:
        check_overlap(parsed, root, rep, lines)
    else:
        rep.skipped("plan-overlap", "--overlap not given")
    report.debug("check_plan.check", "done", checks=",".join(rep.checks_run), findings=len(rep.findings),
                 tasks=total)
    return rep, lines


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    root = Path(args.workspaces_root)
    if not root.is_dir():
        report.fail(report.EXIT_USAGE, f"--workspaces-root is not a directory: {args.workspaces_root}")
    try:
        rep, lines = check(args.plan, root, args.overlap)
    except knowledge.KnowledgeTableError as exc:
        report.fail(report.EXIT_USAGE, f"ERROR KNOWLEDGE_TABLE {exc}")
    return report.render([rep], header=HEADER, lines=lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
