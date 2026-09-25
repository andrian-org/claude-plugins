#!/usr/bin/env python3
"""inventory_root.py — what a workspaces root holds, counted (ADR 0017 §4, ADR 0019).

For each directory under the root: a workspace (an exact-case `FM/`) with its
role — `webasm` is the base, every other one an application — and its counts
of processes, workflows, component JSON, forms, settings, views, and the
script and style files in the code places; or why it is not a workspace. An
`applibs*` folder holds plugin assemblies and is never a workspace.

The artifact counts come from the `legacy-artifacts` table
(knowledge/composition-specs.md §2.1), the code places from `code-places`
(§5). It also reports the root's git position, the DGF version the shipped
knowledge was read from, and whether the validators' dependencies are
installed — probed with importlib.util.find_spec, so neither is imported.
Stdlib only.

Usage:  inventory_root.py --workspaces-root <root> [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  a workspaces root with a base workspace and the validators ready
  2  warnings: no `webasm/FM/` here, or the validators' dependencies missing
  3  not a workspaces root — no directory under it has an `FM/` — or a usage error
"""

import importlib.util
import os
import re
import sys
from pathlib import Path

from lib import cli, deps, git, knowledge, plan, report, workspace

HEADER = "Workspaces root inventory"
BASE = workspace.BASE_WORKSPACE
COUNTS = ("processes", "workflows", "components", "forms", "settings", "views", "options", "form_scripts",
          "global_scripts", "global_styles")
ARTIFACT_COUNT = {"process": "processes", "workflow": "workflows", "form": "forms", "settings": "settings",
                  "table-view": "views", "lookup-view": "views", "grid-form": "views", "options": "options"}
PLACE_COUNT = {"form-script": "form_scripts", "global-script": "global_scripts",
               "global-script-base": "global_scripts", "global-style": "global_styles"}
PROCESS_LOCAL_WORKFLOW = ("FM", "_PROCESS", "<process>", "<workflow>")
_STAMP = re.compile(r'^dgf_version:\s*"([^"]+)"', re.MULTILINE)


def build_parser():
    parser = cli.parser("inventory_root.py", "Inventory a DGF workspaces root.")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds the workspaces")
    return parser


def _artifact(inside):
    """The count key for a workspace-relative path's legacy artifact, or None."""
    folders, name = inside[:-1], inside[-1]
    for row in knowledge.load("legacy-artifacts"):
        if name == row["Filename"] and plan.matches_folder(plan.segments(row["Folder"]), folders):
            return ARTIFACT_COUNT.get(row["Artifact"])
    if name == "_workflow.xml" and plan.matches_folder(list(PROCESS_LOCAL_WORKFLOW), folders):
        return "workflows"
    return None


def count_workspace(root, name):
    """{count key: n} for one workspace."""
    counts = dict.fromkeys(COUNTS, 0)
    base = Path(root) / name
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        rel_dir = Path(dirpath).relative_to(base).parts
        for filename in filenames:
            inside = [*rel_dir, filename]
            key = _classify_count(name, inside)
            if key:
                counts[key] += 1
    report.debug("inventory_root.count_workspace", "counted", workspace=name,
                 **{k: v for k, v in counts.items() if v})
    return counts


def _classify_count(name, inside):
    if len(inside) >= 3 and inside[0] == workspace.FM and inside[1] == "_COMPONENTS" and inside[-1].endswith(".json"):
        return "components"
    place = plan.code_place("/".join([name, *inside]))
    if place:
        return PLACE_COUNT.get(place["Place"])
    return _artifact(inside)


def classify_dirs(root):
    """([workspace names], [(name, why it is not one)]) for every directory under `root`."""
    workspaces, others = [], []
    for entry in sorted(os.scandir(root), key=lambda e: e.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        status, actual = workspace.exact_child(entry.path, workspace.FM)
        report.debug("inventory_root.classify_dirs", "directory", name=entry.name, fm=status)
        if plan.is_plugin_assembly_folder(entry.name):
            dlls = sum(1 for p in Path(entry.path).rglob("*.dll"))
            others.append((entry.name, f"plugin assemblies — {dlls} .dll file(s), no FM/"))
        elif status == workspace.OK:
            workspaces.append(entry.name)
        elif status == workspace.CASE_ONLY:
            others.append((entry.name, f"`{actual}/` matches FM/ only when case is ignored"))
        else:
            others.append((entry.name, "no FM/"))
    return workspaces, others


def workspace_line(root, name):
    role = "base" if name == BASE else "application"
    counts = count_workspace(root, name)
    return f"WORKSPACE: {name} role={role} " + " ".join(f"{key}={counts[key]}" for key in COUNTS)


def git_line(root):
    if not git.available():
        return "GIT: none (git is not installed)"
    try:
        top = git.toplevel(root)
        branch = git.current_branch(root) or "(detached)"
    except git.GitError as exc:
        report.debug("inventory_root.git_line", "no repository", error=exc)
        return "GIT: none"
    try:
        rel = Path(root).resolve().relative_to(top.resolve()).as_posix()
    except ValueError:  # git spells the top level differently (case, a symlink): name the root in full
        rel = str(Path(root).resolve())
    return f"GIT: toplevel={top} branch={branch} root={rel}"


def knowledge_line():
    """The `dgf_version` the shipped knowledge was read from (every stamped file, deduplicated)."""
    versions = set()
    for path in sorted(knowledge.KNOWLEDGE_DIR.rglob("*.md")):
        match = _STAMP.search(path.read_text(encoding="utf-8"))
        if match and path.name != "README.md":
            versions.add(match.group(1))
    return f"KNOWLEDGE: dgf_version={','.join(sorted(versions)) or 'unknown'}"


def missing_dependencies():
    """Distributions whose top-level package cannot be found. Nothing is imported."""
    absent = []
    for module, dist in deps.REQUIRED:
        try:
            spec = importlib.util.find_spec(module.split(".")[0])
        except (ImportError, ValueError):
            spec = None
        if spec is None:
            absent.append(dist)
    report.debug("inventory_root.missing_dependencies", "probed", missing=",".join(absent) or "none")
    return absent


def inventory(root):
    """(lines, Report) for the root."""
    rep = report.Report(str(root))
    names, others = classify_dirs(root)
    lines = [f"ROOT: {root}"]
    lines += [workspace_line(root, name) for name in names]
    lines += [f"NOT A WORKSPACE: {name} ({why})" for name, why in others]
    lines += [git_line(root), knowledge_line()]
    absent = missing_dependencies()
    lines.append(f"VALIDATORS: missing: {', '.join(absent)}" if absent else "VALIDATORS: dependencies present")
    if not names:
        rep.add("ROOT_NO_WORKSPACE", "no directory under the root has an exact-case FM/ — this is not a DGF "
                                     "workspaces root")
    elif BASE not in names:
        rep.add("BASE_WORKSPACE_ABSENT", "no `webasm/FM/` under the root — `BASE:` references cannot be resolved "
                                         "here; the base workspace is mounted from elsewhere "
                                         "(knowledge/composition-specs.md §1.2)")
    if absent:
        rep.add("VALIDATOR_DEPS_MISSING", f"{', '.join(absent)} not installed — the validators exit 3 until they "
                                          f"are. Install with: {deps.install_command()}")
    return lines, rep


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    root = Path(args.workspaces_root)
    if not root.is_dir():
        report.fail(report.EXIT_USAGE, f"--workspaces-root is not a directory: {args.workspaces_root}")
    try:
        lines, rep = inventory(root.resolve())
    except knowledge.KnowledgeTableError as exc:
        report.fail(report.EXIT_USAGE, f"ERROR KNOWLEDGE_TABLE {exc}")
    print(f"{report.BOLD}{HEADER}{report.NC}")
    for line in lines:
        print(report.one_line(line))
    for finding in rep.findings:
        print(finding.render())
    print()
    print(report.verdict_line(rep.exit_code()))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
