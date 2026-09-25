#!/usr/bin/env python3
"""locate_plan.py — find the workspaces root and the active plan (ADR 0017 §6).

One definition of discovery for every dgf-* skill that reads a plan.

1. The root. `--workspaces-root`, else the nearest directory holding
   `.dgf-factory/config.yaml`: the working directory and its ancestors first,
   then its descendants to depth 4, skipping dot-directories and node_modules.
   Several descendants → ROOT_AMBIGUOUS; none → ROOT_NOT_SET_UP (run /dgf).
   `--root-only` stops here.
2. The plan. The branch is `--branch`, else the root's checked-out branch; its
   stem is the branch with `/` → `-`. `<plans>/<stem>/index.md` and
   `<plans>/<stem>.md` are the branch's plan; both → PLAN_AMBIGUOUS. Neither
   (or a detached HEAD, or no git) → a fallback, exit 2: the one active
   entrypoint in the plans directory, else the fast plan. A plan that parses
   and has no unchecked task is finished and never a fallback. Several →
   PLAN_AMBIGUOUS; none → PLAN_NOT_FOUND (run /dgf-plan).
3. `--list` prints every entrypoint, with its progress, and exits 0.

The skills read `.dgf-factory/config.yaml` and pass its paths here; this
script never reads the config. Stdlib only; git is optional.

Usage:  locate_plan.py [--workspaces-root R] [--plans-dir D] [--fast-plan F]
                       [--branch B] [--root-only | --list] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  found: the root, and the branch's plan (or the list)
  1  not found or ambiguous — STOP and say what to run
  2  a fallback plan was chosen — say which, and ask before using it
  3  usage error
"""

import os
import sys
from pathlib import Path

from lib import cli, git, plan, report

HEADER = "Plan discovery"
CONFIG = Path(plan.PIPELINE_DIR) / "config.yaml"
DEFAULT_PLANS = Path(plan.PIPELINE_DIR) / "plans"
DEFAULT_FAST = Path(plan.PIPELINE_DIR) / "PLAN.md"
SEARCH_DEPTH = 4
SKIPPED_DIRS = {"node_modules"}


def build_parser():
    parser = cli.parser("locate_plan.py", "Find the workspaces root and the active dgf-factory plan.")
    parser.add_argument("--workspaces-root", help="the root; default: the nearest .dgf-factory/config.yaml")
    parser.add_argument("--plans-dir", default=str(DEFAULT_PLANS), help="relative to the root (paths.plans)")
    parser.add_argument("--fast-plan", default=str(DEFAULT_FAST), help="relative to the root (paths.plan)")
    parser.add_argument("--branch", help="the branch whose plan to find; default: the root's current branch")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--root-only", action="store_true", help="find the root and stop")
    mode.add_argument("--list", action="store_true", help="list every plan with its progress")
    return parser


# --- 1. the root ------------------------------------------------------------------

def _is_root(directory):
    return (Path(directory) / CONFIG).is_file()


def _descendants(start, depth):
    """Directories below `start` to `depth` levels, dot-directories and node_modules skipped."""
    found = []
    for dirpath, dirnames, _ in os.walk(start):
        level = len(Path(dirpath).relative_to(start).parts)
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in SKIPPED_DIRS)
        if level >= depth:
            dirnames[:] = []
        if level > 0 and _is_root(dirpath):
            found.append(Path(dirpath))
    return found


def find_root(start, rep):
    """The workspaces root for `start`, or None with a finding in `rep`."""
    start = Path(start).resolve()
    for candidate in [start, *start.parents]:
        report.debug("locate_plan.find_root", "ancestor", path=candidate, root=_is_root(candidate))
        if _is_root(candidate):
            return candidate
    below = _descendants(start, SEARCH_DEPTH)
    report.debug("locate_plan.find_root", "descendants", start=start, found=len(below))
    if len(below) == 1:
        return below[0]
    if below:
        rep.add("ROOT_AMBIGUOUS", f"{len(below)} workspaces roots below {start}: "
                                  f"{', '.join(str(p) for p in below)} — pass --workspaces-root")
        return None
    rep.add("ROOT_NOT_SET_UP", f"no `{CONFIG.as_posix()}` in {start}, its parents, or {SEARCH_DEPTH} levels below "
                               f"it — run /dgf in the workspaces root")
    return None


def explicit_root(value, rep):
    root = Path(value)
    if not root.is_dir():
        report.fail(report.EXIT_USAGE, f"--workspaces-root is not a directory: {value}")
    if not _is_root(root):
        rep.add("ROOT_NOT_SET_UP", f"{root} holds no `{CONFIG.as_posix()}` — run /dgf there")
        return None
    return root.resolve()


# --- 2. the plan ------------------------------------------------------------------

def entrypoints(plans_dir):
    """Every plan entrypoint directly in `plans_dir`: `*.md` and `*/index.md`."""
    if not plans_dir.is_dir():
        return []
    return sorted(plans_dir.glob("*.md")) + sorted(p for p in plans_dir.glob("*/index.md") if p.is_file())


def describe(path):
    """(mode, done, total), or ("unreadable", None, None) when the plan does not parse."""
    try:
        parsed = plan.parse(path)
    except plan.PlanFormatError as exc:
        report.debug("locate_plan.describe", "unreadable", path=path, error=exc)
        return "unreadable", None, None
    done, total = parsed.progress()
    return parsed.mode or "unknown", done, total


def _finished(path):
    mode, done, total = describe(path)
    return mode != "unreadable" and total and done == total


def current_branch(root, given):
    if given:
        return given
    if not git.available():
        report.debug("locate_plan.current_branch", "git is not installed")
        return None
    try:
        return git.current_branch(root)
    except git.GitError as exc:
        report.debug("locate_plan.current_branch", "no branch", error=exc)
        return None


def find_plan(root, plans_dir, fast_plan, branch, rep):
    """(path, source) or None with a finding in `rep`."""
    if branch:
        stem = branch.replace("/", "-")
        found = [p for p in (plans_dir / stem / "index.md", plans_dir / f"{stem}.md") if p.is_file()]
        report.debug("locate_plan.find_plan", "branch plan", branch=branch, stem=stem, found=len(found))
        if len(found) == 2:
            rep.add("PLAN_AMBIGUOUS", f"branch `{branch}` has both {cli.display(found[0])} and "
                                      f"{cli.display(found[1])} — keep one")
            return None
        if found:
            return found[0], "branch"
    candidates = [p for p in entrypoints(plans_dir) if not _finished(p)]
    report.debug("locate_plan.find_plan", "fallback", branch=branch, active=len(candidates),
                 fast=fast_plan.is_file())
    why = f"no plan for branch `{branch}`" if branch else "no branch is checked out"
    if len(candidates) == 1:
        rep.add("PLAN_FALLBACK", f"{why}; the only active plan is {cli.display(candidates[0])}")
        return candidates[0], "lone"
    if len(candidates) > 1:
        rep.add("PLAN_AMBIGUOUS", f"{why}, and {len(candidates)} plans are active: "
                                  f"{', '.join(cli.display(p) for p in candidates)} — name one")
        return None
    if fast_plan.is_file():
        rep.add("PLAN_FALLBACK", f"{why}; using the fast plan {cli.display(fast_plan)}")
        return fast_plan, "fast"
    rep.add("PLAN_NOT_FOUND", f"{why}, and no fast plan — run /dgf-plan")
    return None


def list_lines(plans_dir, fast_plan):
    lines = []
    for path in entrypoints(plans_dir) + ([fast_plan] if fast_plan.is_file() else []):
        mode, done, total = describe(path)
        progress = "unreadable" if mode == "unreadable" else f"{done}/{total}"
        lines.append(f"PLAN: {cli.display(path)} mode={mode} progress={progress}")
    return lines or ["PLAN: (none)"]


def emit(lines, rep):
    print(f"{report.BOLD}{HEADER}{report.NC}")
    for line in lines:
        print(report.one_line(line))
    for finding in rep.findings:
        print(finding.render())
    print()
    print(report.verdict_line(rep.exit_code()))
    return rep.exit_code()


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    rep = report.Report(".")
    root = explicit_root(args.workspaces_root, rep) if args.workspaces_root else find_root(Path.cwd(), rep)
    if root is None:
        return emit([], rep)
    lines = [f"ROOT: {root}"]
    if args.root_only:
        return emit(lines, rep)
    plans_dir, fast_plan = root / args.plans_dir, root / args.fast_plan
    if args.list:
        return emit(lines + list_lines(plans_dir, fast_plan), rep)
    found = find_plan(root, plans_dir, fast_plan, current_branch(root, args.branch), rep)
    if found is not None:
        path, source = found
        lines.append(f"PLAN: {cli.display(path)} mode={describe(path)[0]} source={source}")
    return emit(lines, rep)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
