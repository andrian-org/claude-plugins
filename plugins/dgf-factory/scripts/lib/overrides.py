"""overrides.py — read a skill-context override and check it may only tighten its skill (ADR 0024 §3–§5).

An override is `<paths.skill_context>/<skill>/SKILL.md`, in a fixed template:

    # Project Rules for /<skill>

    > Written by /dgf-evolve from the estate's patches. Each rule may only tighten /<skill> (ADR 0021).
    > Updated: <YYYY-MM-DD HH:mm>

    ## Rules

    ### <name>
    - source: <patch name>, <patch name>
    - rule: <text>
      <text continued on lines indented by two or more spaces>

Anyone who commits to the estate can write one, so every skill that reads an
override has check_override.py check it first. Three checks refuse it:

  shape      the template above — the two quoted lines exactly, each optional —
             at most MAX_RULES rules of MAX_RULE_CHARS, a regular file of at
             most MAX_BYTES, UTF-8, no fence or HTML comment, and no character
             outside printable ASCII, spaces and a few typographic marks: an
             override is English, and an invisible, control or look-alike
             character could hide a construct from the patterns below
  sources    every source a patch name present in the patches directory
  forbidden  no FORBIDDEN construct in a rule's name or text: a gate block, a
             flag other than --strict or --verbose, a tool grant, an install or
             download, a git command that rewrites history or discards work, a
             path outside the workspaces root. The text is read as ASCII first
             (read_as()): a typographic dash is a hyphen, and any space a space

One check hands a rule to the reading skill's judgement: a rule naming a word
in LIMIT_WORDS — or its plural, past, -ing or -ly form — is
OVERRIDE_TOUCHES_LIMIT, one warning per rule. The check is lexical: it refuses
what a script can see, and cannot prove that a rule tightens. Stdlib only.
"""

import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from . import patches, report

TITLE = "# Project Rules for /{skill}"
RULES_HEADING = "## Rules"
MAX_RULES, MAX_RULE_CHARS, MAX_NAME_CHARS, MAX_BYTES = 40, 600, 100, 32768
ALLOWED_FLAGS = ("--strict", "--verbose")
BULLETS = ("source", "rule")
# A frozen format, not a citation (ADR 0024 §3): every committed override carries this exact line,
# "(ADR 0021)" included, so it does not follow the number of the ADR that now decides it.
WRITTEN = "> Written by /dgf-evolve from the estate's patches. Each rule may only tighten /{skill} (ADR 0021)."
_UPDATED = re.compile(r"> Updated: \d{4}-\d{2}-\d{2} \d{2}:\d{2}\Z")

# The characters an English override may hold beyond printable ASCII, each read as its ASCII form before the
# patterns run: a typographic dash is a hyphen (two for an en or em dash, which is how `--` is often retyped), and
# a tab or any Unicode space (category Zs) is a space. Everything else is refused as OVERRIDE_SHAPE.
READ_AS = {"\t": " ", "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2212": "-", "\u2013": "--", "\u2014": "--",
           "\u2015": "--", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2026": "...",
           "\u00a7": "\u00a7", "\u2192": "->"}

# Built from pieces, as doctor.py's ABSOLUTE_PATH_MARKERS are: a literal home-directory
# marker in this shipped file would make every doctor run warn ABSOLUTE_PATH.
_SEP = "/"
_SYSTEM_DIRS = ("Users", "home", "etc", "tmp", "var", "usr", "opt", "root", "private", "dev", "proc", "sys", "bin",
                "sbin", "Volumes", "mnt")
OUTSIDE_ROOT = "|".join((
    re.escape(".." + _SEP), re.escape("..\\"), re.escape("~" + _SEP),
    r"(?<![\w.~-])" + re.escape(_SEP) + "(?:" + "|".join(_SYSTEM_DIRS) + r")\b",   # an absolute system path
    r"\$\{?HOME\b", r"%(?:USERPROFILE|HOMEPATH|HOMEDRIVE|APPDATA)%",               # a home directory
    r"(?<!\w)[A-Za-z]:[\\/]", r"\bfile:" + re.escape(_SEP * 2),                     # a drive; a file URL
))
_FLAG = r"(?<![\w-])--(?!(?:" + "|".join(re.escape(f[2:]) for f in ALLOWED_FLAGS) + r")(?![\w-]))[a-z][a-z-]*"

# (id, pattern, why) — each entry is pinned by a test, so a false refusal is fixed by narrowing one pattern. They run
# on read_as() text, so `\s` covers every space an author could type.
FORBIDDEN = tuple((name, re.compile(pattern, re.IGNORECASE), why) for name, pattern, why in (
    ("gate-block", r"dgf[-_ ]?gate[-_ ]?result", "a rule never writes, edits or adds a gate block"),
    ("flag", _FLAG, "a flag other than --strict or --verbose narrows or skips a check"),
    ("tool-grant", r"allowed[-_ ]?tools|\bBash\s*\(|disable[-_ ]?model[-_ ]?invocation", "a rule never grants a tool"),
    ("install", r"\b(?:pip3?|pipx)\s+install\b|\bpython3?\s+-m\s+pip\b|\buv\s+(?:pip|add|tool)\b"
                r"|\bnpm\s+(?:install|i|ci)\b|\b(?:yarn|pnpm)\s+(?:add|install)\b|\bnpx\s|\bbrew\s+install\b"
                r"|\bapt(?:-get)?\s+install\b|\bapt-get\b|\b(?:curl|wget)\b",
     "a rule never installs or downloads anything"),
    ("git-write", r"\bgit(?:\s+-{1,2}[\w.-]+(?:[= ]\S+)?)*\s+(?:push|reset|clean|checkout|switch|rebase|rm|restore|stash)\b",
     "a rule never rewrites history or discards work"),
    ("outside-root", OUTSIDE_ROOT, "a rule never names a path outside the workspaces root"),
))

LIMIT_WORDS = ("stop", "exit", "status", "block", "blocking", "blocker", "warn", "warning", "critical rule",
               "artifact ownership", "not run", "pre_existing", "skip", "ignore", "optional", "unless", "instead",
               "allow", "permit", "relax", "bypass", "waive", "override", "overridden", "precedence", "supersede",
               "disregard", "unblock")


def _forms(word):
    """The word, and for a word ending in `e` its stem before `-ing` (waive → waiving)."""
    stem = re.escape(word)
    return [stem, re.escape(word[:-1]) + "(?=ing)"] if word.endswith("e") else [stem]


# Word-bounded and case-insensitive; a plural, past, -ing or -ly form counts too (STOPs, skipped, waiving, optionally).
_LIMIT = re.compile(r"\b(?:" + "|".join(f for w in LIMIT_WORDS for f in _forms(w))
                    + r")(?:s|es|d|ed|ing|ly|ped|ping|ted|ting)?\b", re.IGNORECASE)
_FENCE = ("```", "~~~")
_BULLET = re.compile(r"- (source|rule):(?:[ \t]+(.*?))?[ \t]*\Z")
_CONTINUATION = re.compile(r"  +\S")


@dataclass
class Rule:
    name: str
    line: int
    sources: list = field(default_factory=list)
    text: str = ""
    source_line: object = None  # int, or None when the bullet is missing
    bullets: dict = field(default_factory=dict)  # bullet -> line


@dataclass
class Override:
    rules: list


@dataclass
class _State:
    rel: str
    rep: object
    skill: str
    rules: list = field(default_factory=list)
    headings: int = 0
    last_bullet: object = None
    ok: bool = True

    def shape(self, message, line=None):
        self.rep.add("OVERRIDE_SHAPE", message, line=line, file=self.rel)
        self.ok = False


# --- shape ------------------------------------------------------------------------

def parse(path, rel, skill, rep):
    """The Override at `path`, or None when it is unreadable or off the template; findings go in `rep`."""
    lines = _read(Path(path), rel, rep)
    if lines is None:
        return None
    state = _State(rel, rep, skill)
    body = _title(lines, skill, state)
    if body is None:
        return None
    for number, line in body:
        _line(number, line, state)
    _finish(state)
    report.debug("overrides.parse", "parsed", skill=skill, rules=len(state.rules), ok=state.ok)
    return Override(state.rules) if state.ok else None


def _read(path, rel, rep):
    raw, why = patches.read_small(path, MAX_BYTES)
    if why:
        rep.add("OVERRIDE_UNREADABLE", why, file=rel)
        return None
    try:
        text = patches.decode(raw)
    except UnicodeDecodeError as exc:
        rep.add("OVERRIDE_UNREADABLE", f"not UTF-8 at byte {exc.start}", file=rel)
        return None
    return text.replace("\r\n", "\n").split("\n")  # not splitlines(): U+2028 and friends stay in their line


def _title(lines, skill, state):
    """Check the title line → the (number, text) pairs after it, or None for an empty file."""
    numbered = list(enumerate(lines, 1))
    first = next((i for i, (_, line) in enumerate(numbered) if line.strip()), None)
    title = TITLE.format(skill=skill)
    if first is None:
        state.shape(f"the file is empty; it opens with `{title}`")
        return None
    number, line = numbered[first]
    if line.rstrip() != title:
        state.shape(f"the first line is not `{title}`", number)
    return numbered[first + 1:]


def _refused_character(line):
    """The first character an English override never needs, or None."""
    for char in line:
        if not (" " <= char <= "~" or char in READ_AS or unicodedata.category(char) == "Zs"):
            return char
    return None


def read_as(text):
    """`text` as the patterns read it: each READ_AS character as its ASCII form, and any space as a space."""
    return "".join(READ_AS.get(c, " " if unicodedata.category(c) == "Zs" else c) for c in text)


def _line(number, line, state):
    char = _refused_character(line)
    if char is not None:
        state.shape(f"U+{ord(char):04X} ({unicodedata.name(char, 'unnamed')}) is not allowed: an override is English, "
                    f"and an invisible, control or look-alike character can hide a construct from this check", number)
        report.debug("overrides.parse", "refused character", line=number, codepoint=f"U+{ord(char):04X}")
        return
    stripped = line.strip()
    if "<!--" in line:
        state.shape("an HTML comment can hide text from a reviewer", number)
    if stripped.startswith(_FENCE):
        state.shape("a fence can hide text from a reviewer or carry a block", number)
        return
    if not stripped:
        return
    if line.startswith("#"):
        _heading(number, line, state)
    elif state.headings == 0 and line.startswith(">"):
        _quoted(number, line, state)
    elif not state.rules:
        state.shape("text outside a rule: before `## Rules`, only blank and `> ` lines", number)
    else:
        _rule_line(number, line, state)


def _quoted(number, line, state):
    written = WRITTEN.format(skill=state.skill)
    if line.rstrip() == written or _UPDATED.match(line.rstrip()):
        return
    state.shape(f"a quoted line other than the template's two, `{written}` and `> Updated: <YYYY-MM-DD HH:mm>`",
                number)


def _heading(number, line, state):
    if line.rstrip() == RULES_HEADING:
        state.headings += 1
        if state.headings > 1 or state.rules:
            state.shape("`## Rules` appears twice, or after a rule", number)
        return
    if line.startswith("### ") and state.headings:
        _new_rule(number, line[4:].strip(), state)
        return
    state.shape(f"`{line.split(' ', 1)[0]}` heading: only the title, one `## Rules` and `### <name>` rules "
                f"are allowed", number)


def _new_rule(number, name, state):
    if not name or len(name) > MAX_NAME_CHARS:
        state.shape(f"a rule's name is 1–{MAX_NAME_CHARS} characters; this one is {len(name)}", number)
    if any(rule.name == name for rule in state.rules):
        state.shape(f"a second rule is named `{name}`", number)
    state.rules.append(Rule(name, number))
    state.last_bullet = None


def _rule_line(number, line, state):
    rule = state.rules[-1]
    match = _BULLET.match(line)
    if match:
        bullet, value = match.group(1), (match.group(2) or "").strip()
        if bullet in rule.bullets:
            state.shape(f"rule `{rule.name}` has a second `- {bullet}:` bullet", number)
            return
        rule.bullets[bullet] = number
        if bullet == "source":
            rule.sources, rule.source_line = [s.strip() for s in value.split(",") if s.strip()], number
        else:
            rule.text = value
        state.last_bullet = bullet
    elif _CONTINUATION.match(line) and state.last_bullet == "rule":
        rule.text = f"{rule.text} {line.strip()}".strip()
    elif _CONTINUATION.match(line) and state.last_bullet == "source":
        rule.sources += [s.strip() for s in line.split(",") if s.strip()]
    else:
        state.shape(f"rule `{rule.name}` holds a line that is not its `- source:` or `- rule:` bullet, or their "
                    f"indented continuation", number)


def _finish(state):
    if state.headings == 0:
        state.shape(f"no `{RULES_HEADING}` heading")
    elif not state.rules:
        state.shape("`## Rules` holds no rule")
    if len(state.rules) > MAX_RULES:
        state.shape(f"{len(state.rules)} rules; the most is {MAX_RULES}")
    for rule in state.rules:
        for bullet in BULLETS:
            if bullet not in rule.bullets:
                state.shape(f"rule `{rule.name}` has no `- {bullet}:` bullet", rule.line)
        if not rule.text and "rule" in rule.bullets:
            state.shape(f"rule `{rule.name}` has an empty `- rule:`", rule.bullets["rule"])
        if len(rule.text) > MAX_RULE_CHARS:
            state.shape(f"rule `{rule.name}` is {len(rule.text)} characters; the most is {MAX_RULE_CHARS}",
                        rule.line)


# --- sources ----------------------------------------------------------------------

def patch_names(patches_dir):
    """The file names directly in `patches_dir`, exactly as the directory spells them."""
    try:
        with os.scandir(patches_dir) as entries:
            return {entry.name for entry in entries if entry.is_file()}
    except OSError:
        return set()


def check_sources(rules, patches_dir, rel, rep):
    """OVERRIDE_SOURCE_MISSING for each source that is not a patch in `patches_dir`."""
    present = patch_names(patches_dir)
    for rule in rules:
        if not rule.sources:
            rep.add("OVERRIDE_SOURCE_MISSING", f"rule `{rule.name}` names no patch", line=rule.source_line, file=rel)
        for source in rule.sources:
            if not patches.NAME.match(source):
                rep.add("OVERRIDE_SOURCE_MISSING", f"rule `{rule.name}`: `{source}` is not a patch name",
                        line=rule.source_line, file=rel)
            elif source not in present:
                rep.add("OVERRIDE_SOURCE_MISSING", f"rule `{rule.name}`: patch `{source}` is not in the patches "
                                                   f"directory", line=rule.source_line, file=rel)
    report.debug("overrides.check_sources", "checked", rules=len(rules), patches=len(present))


# --- forbidden constructs and the limit ------------------------------------------

def check_rules(rules, rel, rep):
    """OVERRIDE_FORBIDDEN for each construct a rule holds; OVERRIDE_TOUCHES_LIMIT once per rule naming a limit word.

    The quoted lines need no check: the shape allows only the template's two.
    """
    for rule in rules:
        what, line, text = f"rule `{rule.name}`", rule.line, read_as(f"{rule.name}\n{rule.text}")
        for construct, pattern, why in FORBIDDEN:
            match = pattern.search(text)
            if match:
                rep.add("OVERRIDE_FORBIDDEN", f"{what} holds `{match.group(0).strip()}` ({construct}): {why}",
                        line=line, file=rel)
                report.debug("overrides.check_rules", "forbidden", rule=what, construct=construct)
        words = []
        for match in _LIMIT.finditer(text):
            word = match.group(0).lower()
            if word not in words:
                words.append(word)
        if words:
            rep.add("OVERRIDE_TOUCHES_LIMIT", f"{what} names {', '.join(f'`{w}`' for w in words)} — judge it "
                                              f"against the limit: an override may only tighten", line=line, file=rel)
