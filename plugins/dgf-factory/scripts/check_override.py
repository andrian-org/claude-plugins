#!/usr/bin/env python3
"""check_override.py — may a skill read its skill-context override? (ADR 0021 §5)

Checks `<root>/<skill-context-dir>/<skill>/SKILL.md`, the override one skill
reads, before that skill reads it:

  override-shape      the fixed template — `# Project Rules for /<skill>`, `> `
                      lines, one `## Rules`, and `### <name>` rules each holding
                      one `- source:` and one `- rule:` bullet; at most 40 rules
                      of 600 characters and 32768 bytes; UTF-8; no fence and no
                      HTML comment
  override-sources    every source a patch present in the patches directory
  override-forbidden  no gate block, flag other than --strict or --verbose, tool
                      grant, install or download, history-rewriting git command,
                      or path outside the root, in a rule or a quoted line
  override-limit      a rule naming a word the limit protects (STOP, exit,
                      status, skip, unless, allow …) is handed to the reading
                      skill's judgement

The shape runs first; when it fails, the other three are NOT RUN. The check is
lexical: it refuses what a script can see, and cannot prove that a rule only
tightens. It knows no list of skills — `--skill` names the one to check — and
needs only an existing root, not a set-up one. It reads nothing but the
override and the patches directory's file names, and never writes. Stdlib only.

Usage:  check_override.py --workspaces-root R --skill S [--skill-context-dir D]
                          [--patches-dir P] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  apply it — or `OVERRIDE: none`, there is no override
  1  refused — do not read or apply it; the shipped rules alone apply
  2  apply it, and judge each rule an OVERRIDE_TOUCHES_LIMIT line names
  3  usage error: no root, or a skill name that is not a plain name
"""

import re
import sys
from pathlib import Path

from lib import cli, overrides, report

HEADER = "Override check"
DEFAULT_SKILL_CONTEXT = ".dgf-factory/skill-context/"
DEFAULT_PATCHES = ".dgf-factory/patches/"
SKILL = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
AFTER_SHAPE = ("override-sources", "override-forbidden", "override-limit")


def build_parser():
    parser = cli.parser("check_override.py", "Check a dgf-* skill's skill-context override before the skill reads it.")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds .dgf-factory/")
    parser.add_argument("--skill", required=True, help="the skill whose override to check, e.g. dgf-plan")
    parser.add_argument("--skill-context-dir", default=DEFAULT_SKILL_CONTEXT,
                        help="relative to the root (paths.skill_context)")
    parser.add_argument("--patches-dir", default=DEFAULT_PATCHES, help="relative to the root (paths.patches)")
    return parser


def rejected(message, **kv):
    report.debug("check_override.main", "rejected", **kv)
    report.fail(report.EXIT_USAGE, message)


def rule_line(index, rule):
    return f"RULE: {index} line={rule.line} sources={len(rule.sources)} name=\"{rule.name}\""


def check(root, args, rel):
    """(report, lines) for the override at `rel`, which exists."""
    rep = report.Report(rel)
    rep.ran("override-shape")
    parsed = overrides.parse(root / rel, rel, args.skill, rep)
    if parsed is None:
        for check_id in AFTER_SHAPE:
            rep.skipped(check_id, "the override did not parse")
        return rep, [f"OVERRIDE: {rel} skill={args.skill} rules=?"]
    for check_id in AFTER_SHAPE:
        rep.ran(check_id)
    overrides.check_sources(parsed.rules, root / args.patches_dir, rel, rep)
    overrides.check_rules(parsed.rules, rel, rep, quoted=parsed.quoted)
    lines = [f"OVERRIDE: {rel} skill={args.skill} rules={len(parsed.rules)}"]
    return rep, lines + [rule_line(i, rule) for i, rule in enumerate(parsed.rules, 1)]


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    root = Path(args.workspaces_root)
    if not root.is_dir():
        rejected(f"--workspaces-root is not a directory: {args.workspaces_root}", root=args.workspaces_root)
    if not SKILL.match(args.skill):
        rejected(f"--skill is not a skill name (lowercase letters, digits and single hyphens): {args.skill}",
                 skill=args.skill)
    rel = f"{Path(args.skill_context_dir).as_posix().rstrip('/')}/{args.skill}/SKILL.md"
    if not (root / rel).exists():
        report.debug("check_override.main", "checked", skill=args.skill, found=False, rules=0, exit=0)
        return report.render([], header=HEADER, lines=[f"OVERRIDE: none — no {rel}"])
    rep, lines = check(root, args, rel)
    code = report.render([rep], header=HEADER, lines=lines)
    report.debug("check_override.main", "checked", skill=args.skill, found=True, rules=len(lines) - 1, exit=code)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
