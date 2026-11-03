#!/usr/bin/env python3
"""check_rules.py — may a skill read the estate's rules file? And, on request, the scripted rule layout-case (ADR 0032 §4).

Checks `<root>/<paths.rules_file>`, the rules /dgf-rules writes and /dgf-plan,
/dgf-implement, /dgf-review and /dgf-rules-check read, before any of them reads
it:

  rules-format    the fixed format (skills/dgf-rules/references/RULES-FORMAT.md):
                  `# Rules`, at most the one `> Written by /dgf-rules. …` line,
                  then `## R<n> — <title>` rules, each a field list —
                  `enforcement`, `check`, `source`, `demoted` — a blank line
                  and its text; a regular UTF-8 file of at most 65536 bytes,
                  no fence, no HTML comment; ids unique, R5 and R1–R7 reserved,
                  and `check:` a row of the check table below
  rules-limit     no overrides.FORBIDDEN construct and no refused (zero-width
                  or control) character; a rule naming a word the override
                  limit protects, or a word of the gate's own vocabulary
                  (GATE_WORDS: fail, pass, error, verdict, proceed, commit, …),
                  is handed to the reading skill's judgement — over every
                  estate rule and every edited default, and over a demoted
                  default's reason, read as overrides.read_as reads an
                  override, and read again with each hyphen inside a word and
                  each line break closed up (`by-pass`, `sk⏎ip`)
  rules-defaults  each default against the shipped one, default-rules.md
                  beside RULES-FORMAT.md: edited, missing, or demoted
  layout-case     with --layout, over every workspace: a folder that matches
                  one of the framework's layout constants only when case is
                  ignored (knowledge/composition-specs.md §1) — an `FM/`
                  itself included. NOT RUN when no rule that applies cites it,
                  which is a demoted R7

Each rule prints a `RULE:` line. A script or gate rule that applies prints
`ENFORCED: R<n> by <what>` when it is a shipped default as shipped — its check
decides it. An estate rule, or an edited default, that cites a check prints
`JUDGE: R<n> — …` instead: its text is the estate's, so the reading skill
judges it against the limit; the check it cites runs regardless.

An absent file is `RULES: none`, exit 0: the shipped defaults apply. A refused
file is never read; the shipped defaults apply. The check is lexical: it
refuses what a script can see, and cannot prove that a rule only adds a
constraint. It reads the rules file, the shipped defaults and, with --layout,
directory names; it never writes. Stdlib only — /dgf-plan runs it on every
plan, with or without the validators' dependencies.

Usage:  check_rules.py --workspaces-root R --rules F [--layout] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  apply the rules — or `RULES: none`, the shipped defaults apply
  1  refused — do not read the file; the shipped defaults apply. With
     --layout, also a RULES_LAYOUT_CASE folder
  2  apply them, and judge each RULES_TOUCHES_LIMIT rule; or a default
     edited or missing
  3  usage error: no root, a rules path that leaves it, or shipped defaults
     that do not parse (the install's defect)
"""

if __name__ == "__main__":
    from lib import runtime; runtime.use_project_venv()

import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from lib import cli, overrides, patches, plan, report, workspace
import inventory_root

HEADER = "RULES CHECK"
DEFAULTS_FILE = Path(__file__).resolve().parent.parent / "skills" / "dgf-rules" / "references" / "default-rules.md"
TITLE = "# Rules"
WRITTEN = ("> Written by /dgf-rules. Each rule names how it is enforced; check_rules.py checks this file before any "
           "skill reads it.")
MAX_BYTES, MAX_RULES = 65536, 60
DEFAULT_IDS = (1, 2, 3, 4, 6, 7)
RESERVED_ID = 5          # sign-in is /dgf's question, recorded in DESCRIPTION.md (ADR 0028 rule 5)
FIRST_ESTATE_ID = 8
ENFORCEMENTS = ("script", "gate", "prompt-only")
FIELDS = ("enforcement", "check", "source", "demoted")
ESTATE = "estate"
LAYOUT_CHECK = "layout-case"

# The check table: `check:` value -> what enforces it (ADR 0032 §4).
CHECKS = {
    "means-route": "the verify gate — check_plan.py PLAN_ROUTE_MISMATCH",
    "code-planned": "the verify gate — check_change.py CHANGE_CODE_UNPLANNED and CHANGE_CODE_FILE_NEW",
    "base-reason": "the verify gate — check_plan.py PLAN_BASE_REASON_MISSING",
    LAYOUT_CHECK: "check_rules.py --layout",
}

# The layout constants, from DGF's WorkspaceSettings as knowledge/composition-specs.md §1 records them: the
# artifact folders joined under FM/, and StoragePath joined to the workspace root, not to FM/. The three
# constants nothing uses (_DataSources, _SiteMaps, _EndPoints) are left out, as ADR 0028 rule 7 leaves them.
FM_FOLDERS = ("_PROCESS", "_WORKFLOW", "_COMPONENTS", "_DATA", "_LOOKUP", "_PROFILE", "Services")
ROOT_FOLDERS = ("_STORAGE",)

_HEADING = re.compile(r"## R([1-9][0-9]*) — (\S.*?)\s*\Z")
_ANY_HEADING = re.compile(r"#{1,6}(?:\s|\Z)")
_FIELD = re.compile(r"- ([A-Za-z][A-Za-z-]*):(?:[ \t]+(.*?))?[ \t]*\Z")
_SOURCE_DEFAULT = re.compile(r"default \(ADR 0028 rule ([0-9]+)\)\Z")
_FENCE = ("```", "~~~")
REASON_SHOWN = 60  # the most of a demoted reason the INFO line quotes

# Words of the gate's own vocabulary a rule may use to recast a result; rules only — an override is held to
# overrides.LIMIT_WORDS alone. Whole words, with the plural, past, -ing and -ly forms overrides._LIMIT counts.
GATE_WORDS = ("fail", "failure", "pass", "error", "verdict", "proceed", "commit", "informational", "report",
              "advisory", "exempt", "downgrade", "succeed", "success")
_GATE_LIMIT = re.compile(r"\b(?:" + "|".join(f for w in GATE_WORDS for f in overrides._forms(w))
                         + r")(?:s|es|d|ed|ing|ly|ped|ping|ted|ting)?\b", re.IGNORECASE)
_IN_WORD_HYPHEN = re.compile(r"(?<=[A-Za-z])-[ \t]*(?:\n[ \t]*)?(?=[A-Za-z])")
_LINE_BREAK = re.compile(r"[ \t]*\n[ \t]*")
RULE_CHECKS = ("rules-format", "rules-limit", "rules-defaults")


@dataclass
class Rule:
    number: int
    title: str
    line: int
    fields: dict = field(default_factory=dict)       # name -> value
    field_lines: dict = field(default_factory=dict)  # name -> line
    text_lines: list = field(default_factory=list)
    refused: bool = False  # a line of it was refused (RULES_FORBIDDEN), so it is not in text_lines

    @property
    def text(self):
        return "\n".join(self.text_lines).strip()

    @property
    def flat(self):
        """The text with its whitespace collapsed: re-wrapping a paragraph is not an edit."""
        return " ".join(self.text.split())

    @property
    def enforcement(self):
        return self.fields.get("enforcement", "")

    @property
    def check(self):
        return self.fields.get("check")

    @property
    def is_default(self):
        return _SOURCE_DEFAULT.match(self.fields.get("source", "")) is not None

    @property
    def demoted(self):
        return "demoted" in self.fields


@dataclass
class _State:
    rel: str
    rep: object
    rules: list = field(default_factory=list)
    quoted: bool = False    # the one `>` line is seen
    phase: str = "fields"   # fields | text, for the current rule
    skipping: bool = False  # after a malformed `## ` heading, until the next one

    def invalid(self, message, line=None):
        self.rep.add("RULES_FORMAT_INVALID", message, line=line, file=self.rel)


def build_parser():
    parser = cli.parser("check_rules.py", "Check the estate's rules file before a dgf-* skill reads it.")
    parser.add_argument("--workspaces-root", required=True, help="the directory that holds .dgf-factory/")
    parser.add_argument("--rules", required=True, help="the rules file, relative to the root (paths.rules_file)")
    parser.add_argument("--layout", action="store_true",
                        help="also run the scripted rule layout-case over every workspace")
    return parser


# --- reading and the format --------------------------------------------------------

def read_lines(path, rel, rep):
    """The file's lines, or None when it is not a small regular UTF-8 file (RULES_UNREADABLE)."""
    raw, why = patches.read_small(path, MAX_BYTES)
    if why:
        rep.add("RULES_UNREADABLE", why, file=rel)
        return None
    try:
        text = patches.decode(raw)
    except UnicodeDecodeError as exc:
        rep.add("RULES_UNREADABLE", f"not UTF-8 at byte {exc.start}", file=rel)
        return None
    return text.replace("\r\n", "\n").split("\n")  # not splitlines(): U+2028 and friends stay in their line


def parse(lines, rel, rep):
    """The rules in `lines`, as far as they parse; every format defect goes in `rep`."""
    state = _State(rel, rep)
    numbered = list(enumerate(lines, 1))
    first = next((i for i, (_, line) in enumerate(numbered) if line.strip()), None)
    if first is None:
        state.invalid(f"the file is empty; it opens with `{TITLE}`")
        return []
    number, line = numbered[first]
    if line.rstrip() == TITLE:
        numbered = numbered[first + 1:]
    else:
        state.invalid(f"the first line is not `{TITLE}`", number)
        numbered = numbered[first:]
    for number, line in numbered:
        _line(number, line, state)
    if len(state.rules) > MAX_RULES:
        state.invalid(f"{len(state.rules)} rules; the most is {MAX_RULES}")
    for rule in state.rules:
        _finish(rule, state)
    report.debug("check_rules.parse", "parsed", file=rel, rules=len(state.rules))
    return state.rules


def _line(number, line, state):
    char = overrides._refused_character(line)
    if char is not None:
        state.rep.add("RULES_FORBIDDEN", f"U+{ord(char):04X} ({unicodedata.name(char, 'unnamed')}) is not allowed: "
                                         f"a zero-width, control or look-alike character can hide a construct from "
                                         f"this check", line=number, file=state.rel)
        if state.rules and not state.skipping:
            state.rules[-1].refused = True
        return
    if "<!--" in line:
        state.invalid("an HTML comment can hide text from a reviewer", number)
    if line.strip().startswith(_FENCE):
        state.invalid("a fence can hide text from a reviewer or carry a block", number)
        return
    if line.startswith("## "):
        _heading(number, line, state)
    elif _ANY_HEADING.match(line):
        state.invalid(f"`{line.split(' ', 1)[0]}` heading: only the one `{TITLE}` and `## R<n> — <title>` headings "
                      f"are allowed", number)
    elif state.skipping:
        return
    elif not state.rules:
        _preamble(number, line, state)
    else:
        _rule_line(number, line, state)


def _heading(number, line, state):
    match = _HEADING.match(line)
    if not match:
        state.invalid("a `## ` heading that is not `## R<n> — <title>` (an em dash, and no leading zero)", number)
        state.skipping = True
        return
    state.skipping, state.phase = False, "fields"
    state.rules.append(Rule(int(match.group(1)), match.group(2), number))


def _preamble(number, line, state):
    """Between the title and the first rule: blank lines and the one `>` line."""
    if not line.strip():
        return
    if line.rstrip() == WRITTEN and not state.quoted:
        state.quoted = True
        return
    if line.startswith(">"):
        state.invalid(f"a quoted line other than the one `{WRITTEN}`", number)
        return
    state.invalid(f"text before the first rule: only `{TITLE}` and the one `>` line", number)


def _rule_line(number, line, state):
    rule = state.rules[-1]
    if state.phase == "text":
        rule.text_lines.append(line)
        return
    if not line.strip():
        if rule.fields:
            state.phase = "text"
        return
    match = _FIELD.match(line)
    if not match:
        if rule.fields:
            state.invalid(f"R{rule.number}: a blank line separates the fields from the text", number)
        else:
            state.invalid(f"R{rule.number}: the heading is followed by its field list, `- enforcement: …`", number)
        state.phase = "text"
        rule.text_lines.append(line)
        return
    name, value = match.group(1), (match.group(2) or "").strip()
    if name not in FIELDS:
        state.invalid(f"R{rule.number}: `{name}` is not a field — only {', '.join(FIELDS)}", number)
    elif name in rule.fields:
        state.invalid(f"R{rule.number} has a second `- {name}:`", number)
    elif not value:
        state.invalid(f"R{rule.number}: `- {name}:` has no value", number)
    else:
        rule.fields[name], rule.field_lines[name] = value, number


def _finish(rule, state):
    """The field rules a whole rule must meet: enforcement, source, check, demoted, a text."""
    where = f"R{rule.number}"
    if "enforcement" not in rule.fields:
        state.invalid(f"{where} has no `- enforcement:`", rule.line)
    elif rule.enforcement not in ENFORCEMENTS:
        state.invalid(f"{where}: enforcement `{rule.enforcement}` is not {', '.join(ENFORCEMENTS)}",
                      rule.field_lines["enforcement"])
    _check_source(rule, state)
    _check_check(rule, state)
    if rule.demoted and not rule.is_default:
        state.invalid(f"{where}: only a default can be `demoted:`; delete an estate rule instead",
                      rule.field_lines["demoted"])
    if not rule.text and not rule.refused:  # a refused line is reported as itself, not as missing text
        state.invalid(f"{where} has no text after its fields", rule.line)


def _check_source(rule, state):
    where, source = f"R{rule.number}", rule.fields.get("source")
    if source is None:
        state.invalid(f"{where} has no `- source:`", rule.line)
        return
    match = _SOURCE_DEFAULT.match(source)
    if source != ESTATE and not match:
        state.invalid(f"{where}: source `{source}` is not `default (ADR 0028 rule <n>)` or `{ESTATE}`",
                      rule.field_lines["source"])
    elif match and int(match.group(1)) != rule.number:
        state.invalid(f"{where}: a default names its own number — `default (ADR 0028 rule {rule.number})`, "
                      f"not rule {match.group(1)}", rule.field_lines["source"])


def _check_check(rule, state):
    where, value = f"R{rule.number}", rule.check
    line = rule.field_lines.get("check", rule.line)
    if rule.enforcement == "prompt-only" and value is not None:
        state.rep.add("RULES_CHECK_UNKNOWN", f"{where} is prompt-only and names `check: {value}`: a prompt-only rule "
                                             f"has no check", line=line, file=state.rel)
    elif rule.enforcement in ("script", "gate") and value is None:
        state.rep.add("RULES_CHECK_UNKNOWN", f"{where} is enforced by {rule.enforcement} and names no `check:` — one "
                                             f"of {', '.join(CHECKS)}", line=line, file=state.rel)
    elif value is not None and value not in CHECKS:
        state.rep.add("RULES_CHECK_UNKNOWN", f"{where}: `check: {value}` is no row of the check table — "
                                             f"{', '.join(CHECKS)}; a rule cannot invent a script", line=line,
                      file=state.rel)


# --- ids, the limit, the defaults ---------------------------------------------------

def check_ids(rules, rel, rep):
    """RULES_ID_DUPLICATE and RULES_ID_RESERVED."""
    seen = {}
    for rule in rules:
        where = f"R{rule.number}"
        if rule.number in seen:
            rep.add("RULES_ID_DUPLICATE", f"{where} is used again; the first is at line {seen[rule.number]}",
                    line=rule.line, file=rel)
        seen.setdefault(rule.number, rule.line)
        if rule.number == RESERVED_ID:
            rep.add("RULES_ID_RESERVED", f"{where} is reserved: sign-in is /dgf's question, recorded in "
                                         f"DESCRIPTION.md (ADR 0028 rule 5)", line=rule.line, file=rel)
        elif rule.is_default and rule.number not in DEFAULT_IDS:
            rep.add("RULES_ID_RESERVED", f"{where} names itself a default; the defaults are "
                                         f"{', '.join(f'R{n}' for n in DEFAULT_IDS)}", line=rule.line, file=rel)
        elif rule.fields.get("source") == ESTATE and rule.number < FIRST_ESTATE_ID:
            rep.add("RULES_ID_RESERVED", f"{where} is an estate rule numbered like a default; estate rules start at "
                                         f"R{FIRST_ESTATE_ID}", line=rule.line, file=rel)


def check_forbidden(rule, text, rel, rep):
    """RULES_FORBIDDEN for each overrides.FORBIDDEN construct in `text`, read as an override is read."""
    for construct, pattern, why in overrides.FORBIDDEN:
        match = pattern.search(overrides.read_as(text))
        if match:
            rep.add("RULES_FORBIDDEN", f"R{rule.number} holds `{match.group(0).strip()}` ({construct}): {why}",
                    line=rule.line, file=rel)
            report.debug("check_rules.check_forbidden", "forbidden", rule=rule.number, construct=construct)


def limit_words(text):
    """The limit words and GATE_WORDS `text` names, first seen first, lowercased.

    Read three ways, so neither a hyphen inside a word nor a line break hides one: as written, with
    each in-word hyphen closed up (`by-pass` → `bypass`, `by-⏎pass` too), and with every line break
    closed up as well (`sk⏎ip` → `skip`).
    """
    plain = overrides.read_as(text)
    dehyphened = _IN_WORD_HYPHEN.sub("", plain)
    words = []
    for variant in (plain, dehyphened, _LINE_BREAK.sub("", dehyphened)):
        for pattern in (overrides._LIMIT, _GATE_LIMIT):
            for match in pattern.finditer(variant):
                word = match.group(0).lower()
                if word not in words:
                    words.append(word)
    return words


def touches_limit(rule, text, rel, rep, what=""):
    """One RULES_TOUCHES_LIMIT for `rule` when `text` names a limit word."""
    words = limit_words(text)
    if words:
        rep.add("RULES_TOUCHES_LIMIT", f"R{rule.number}{what} names {', '.join(f'`{w}`' for w in words)} — judge "
                                       f"it against the limit: a rule may only add a constraint", line=rule.line,
                file=rel)


def check_limit(rule, rel, rep):
    """The limit over a rule a reader applies as written: FORBIDDEN in any of it, one RULES_TOUCHES_LIMIT per rule."""
    values = " ".join(value for name, value in rule.fields.items() if name != "source")
    check_forbidden(rule, f"{rule.title}\n{values}\n{rule.text}", rel, rep)
    touches_limit(rule, f"{rule.title}\n{rule.text}\n{rule.fields.get('demoted', '')}", rel, rep)


def quoted(text, most=REASON_SHOWN):
    """`text` cut to `most` characters and quoted, its backslashes and double quotes escaped."""
    cut = text if len(text) <= most else text[:most].rstrip() + "…"
    return '"' + cut.replace("\\", "\\\\").replace('"', '\\"') + '"'


def edits(rule, shipped):
    """What of `rule` differs from its shipped default: [] when nothing does."""
    differs = [name for name in ("enforcement", "check") if rule.fields.get(name) != shipped.fields.get(name)]
    if rule.title != shipped.title:
        differs.insert(0, "title")
    if rule.flat != shipped.flat:
        differs.append("text")
    return differs


def check_defaults(rules, shipped, rel, rep):
    """RULES_DEFAULT_EDITED, _MISSING and _DEMOTED; then the limit over every estate rule and edited default."""
    present = {rule.number: rule for rule in rules if rule.is_default}
    for number, default in shipped.items():
        rule = present.get(number)
        if rule is None:
            rep.add("RULES_DEFAULT_MISSING", f"R{number} ({default.title}) is a shipped default the file leaves out "
                                             f"without `demoted: <why>`; it still applies as shipped", file=rel)
        elif rule.demoted:
            rep.add("RULES_DEFAULT_DEMOTED", f"R{number} ({default.title}) is demoted — not enforced; its reason: "
                                             f"{quoted(rule.fields['demoted'])}", line=rule.line, file=rel)
    for rule in rules:
        shipped_rule = shipped.get(rule.number) if rule.is_default else None
        differs = edits(rule, shipped_rule) if shipped_rule else []
        if differs:
            rep.add("RULES_DEFAULT_EDITED", f"R{rule.number} differs from the shipped default in its "
                                            f"{', '.join(differs)} — re-seed it with /dgf-rules, or demote it",
                    line=rule.line, file=rel)
        if shipped_rule is None or differs:
            check_limit(rule, rel, rep)
        elif rule.demoted:  # the shipped text, set aside: only the reason is the estate's
            check_forbidden(rule, rule.fields["demoted"], rel, rep)
            touches_limit(rule, rule.fields["demoted"], rel, rep, what="'s demoted reason")


def applying(rules, shipped):
    """The rules a reader applies from an accepted file: its own, and each shipped default it leaves out."""
    present = {rule.number for rule in rules if rule.is_default}
    return rules + [default for number, default in shipped.items() if number not in present]


def refused(rep):
    return any(f.severity == report.EXIT_BLOCKED for f in rep.findings)


# --- the scripted rule layout-case ---------------------------------------------------

def _case_only(directory, constants):
    """[(actual name, the constant it matches only case-insensitively)] for the folders in `directory`."""
    folded = {name.lower(): name for name in constants}
    try:
        entries = sorted(os.scandir(directory), key=lambda e: e.name)
    except OSError:
        return [], 0
    folders = [entry.name for entry in entries if entry.is_dir()]
    found = [(name, folded[name.lower()]) for name in folders
             if name.lower() in folded and name != folded[name.lower()]]
    return found, len(folders)


def check_layout(root, rep):
    """LAYOUT lines per workspace; RULES_LAYOUT_CASE per folder that matches a constant only when case is ignored."""
    names, others = inventory_root.classify_dirs(root)
    lines = []
    for name in names:
        fm = root / name / workspace.FM
        under_fm, folders = _case_only(fm, FM_FOLDERS)
        at_root, _ = _case_only(root / name, ROOT_FOLDERS)
        for actual, constant in under_fm:
            _layout_case(rep, f"{name}/{workspace.FM}/{actual}", constant, "under FM/")
        for actual, constant in at_root:
            _layout_case(rep, f"{name}/{actual}", constant, "at the workspace root")
        lines.append(f"LAYOUT: {name} folders={folders}")
    for name, _ in others:
        status, actual = workspace.exact_child(root / name, workspace.FM)
        if status == workspace.CASE_ONLY:
            _layout_case(rep, f"{name}/{actual}", workspace.FM, "at the workspace root")
    report.debug("check_rules.check_layout", "checked", workspaces=len(names))
    return lines


def _layout_case(rep, rel, constant, where):
    rep.add("RULES_LAYOUT_CASE", f"matches `{constant}` {where} only when case is ignored — the runtime reads "
                                 f"`{constant}`, case-sensitively on Linux, so this folder is never read there "
                                 f"(R7; knowledge/composition-specs.md §1)", file=rel)


# --- output ---------------------------------------------------------------------------

def rule_line(rule):
    check = rule.check or "-"
    source = "default" if rule.is_default else (ESTATE if rule.fields.get("source") == ESTATE else "?")
    title = rule.title.replace("\\", "\\\\").replace('"', '\\"')
    return (f"RULE: R{rule.number} enforcement={rule.enforcement or '?'} check={check} source={source}"
            f"{' demoted' if rule.demoted else ''} title=\"{title}\"")


def enforced_lines(rules, shipped):
    """ENFORCED for a script or gate default as shipped; JUDGE for an estate rule or an edited default citing a check.

    A check decides only the rule it was written for. An estate rule's text, or an edited default's, is the
    estate's: it could relax what the check it cites holds, so it is judged against the limit by its text.
    """
    lines = []
    for rule in rules:
        if rule.enforcement not in ("script", "gate") or rule.check not in CHECKS or rule.demoted:
            continue
        default = shipped.get(rule.number) if rule.is_default else None
        if default is not None and not edits(rule, default):
            lines.append(f"ENFORCED: R{rule.number} by {CHECKS[rule.check]}")
            continue
        whose = "an edited default" if rule.is_default else "an estate rule"
        lines.append(f"JUDGE: R{rule.number} — {whose} is judged by its text, against the limit; the check it cites "
                     f"({rule.check}) runs regardless")
    return lines


def shipped_defaults():
    """{number: Rule} from the shipped default-rules.md; exit 3 when it does not parse clean."""
    rep = report.Report(DEFAULTS_FILE.name)
    lines = read_lines(DEFAULTS_FILE, DEFAULTS_FILE.name, rep)
    rules = parse(lines, DEFAULTS_FILE.name, rep) if lines is not None else []
    if rep.findings or sorted(r.number for r in rules) != list(DEFAULT_IDS):
        report.debug("check_rules.shipped_defaults", "malformed", findings=len(rep.findings))
        report.fail(report.EXIT_USAGE, f"the shipped defaults ({DEFAULTS_FILE}) do not parse as the rules format — "
                                       f"the installed runtime's defect: run /dgf-doctor, then re-run "
                                       f"`dgf-factory setup`")
    return {rule.number: rule for rule in rules}


def check(root, rel, layout):
    """(report, lines) for the rules file at `rel`, absent or present."""
    shipped = shipped_defaults()
    rep = report.Report(rel)
    rules = None
    if not os.path.lexists(root / rel):  # a dangling link is there, and unreadable — never "none"
        for check_id in RULE_CHECKS:
            rep.skipped(check_id, f"no {rel} — the shipped defaults apply")
        lines = [f"RULES: none — no {rel}"]
    else:
        rep.ran("rules-format")
        raw = read_lines(root / rel, rel, rep)
        if raw is None:
            for check_id in RULE_CHECKS[1:]:
                rep.skipped(check_id, "the file could not be read")
        else:
            rules = parse(raw, rel, rep)
            check_ids(rules, rel, rep)
            rep.ran("rules-limit")
            rep.ran("rules-defaults")
            check_defaults(rules, shipped, rel, rep)
        parsed = rules or []
        defaults = sum(1 for r in parsed if r.is_default)
        estate = sum(1 for r in parsed if r.fields.get("source") == ESTATE)
        lines = [f"RULES: {rel} rules={len(parsed)} defaults={defaults} estate={estate}"]
    applied = list(shipped.values()) if rules is None or refused(rep) else applying(rules, shipped)
    shown = list(shipped.values()) if not os.path.lexists(root / rel) else rules or []
    lines += [rule_line(rule) for rule in shown] + enforced_lines(applied, shipped)
    if layout:
        lines += _layout(root, rep, applied)
    return rep, lines


def _layout(root, rep, applied):
    if any(r.check == LAYOUT_CHECK and not r.demoted for r in applied):
        rep.ran(LAYOUT_CHECK)
        return check_layout(root, rep)
    rep.skipped(LAYOUT_CHECK, "no rule that applies cites it — R7 is demoted")
    return []


def main(argv):
    args = build_parser().parse_args(argv)
    if args.verbose:
        report.set_verbose()
    root = Path(args.workspaces_root)
    if not root.is_dir():
        report.fail(report.EXIT_USAGE, f"--workspaces-root is not a directory: {args.workspaces_root}")
    why = plan.path_problem(args.rules)
    if why:
        report.fail(report.EXIT_USAGE, f"--rules {why}: it names a file below the root, as paths.rules_file does — "
                                       f"{args.rules}")
    rep, lines = check(root, args.rules, args.layout)
    code = report.render([rep], header=HEADER, lines=[f"ROOT: {root}", *lines])
    report.debug("check_rules.main", "checked", rules=args.rules, layout=args.layout, exit=code)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
