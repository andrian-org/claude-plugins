"""overrides.py — read a skill-context override and check it may only tighten its skill (ADR 0021 §3–§5).

An override is `<paths.skill_context>/<skill>/SKILL.md`, in a fixed template:

    # Project Rules for /<skill>

    > <optional quoted lines>

    ## Rules

    ### <name>
    - source: <patch name>, <patch name>
    - rule: <text>
      <text continued on lines indented by two or more spaces>

Anyone who commits to the estate can write one, so every skill that reads an
override has check_override.py check it first. Three checks refuse it:

  shape      the template above, at most MAX_RULES rules of MAX_RULE_CHARS,
             at most MAX_BYTES, UTF-8, and no fence or HTML comment anywhere —
             either could hide text from a reviewer, or carry a block
  sources    every source a patch name present in the patches directory
  forbidden  no FORBIDDEN construct in a rule's name or text, or in a quoted
             line: a gate block, a flag other than --strict or --verbose, a
             tool grant, an install or download, a git command that rewrites
             history or discards work, a path outside the workspaces root

One check hands a rule to the reading skill's judgement: a rule naming a word
in LIMIT_WORDS — or its plural or past form — is OVERRIDE_TOUCHES_LIMIT, one
warning per rule. The check is lexical: it refuses what a script can see, and
cannot prove that a rule tightens. Stdlib only.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import patches, report

TITLE = "# Project Rules for /{skill}"
RULES_HEADING = "## Rules"
MAX_RULES, MAX_RULE_CHARS, MAX_NAME_CHARS, MAX_BYTES = 40, 600, 100, 32768
ALLOWED_FLAGS = ("--strict", "--verbose")
BULLETS = ("source", "rule")
PREAMBLE = "the quoted lines"

# Built from pieces, as doctor.py's ABSOLUTE_PATH_MARKERS are: a literal home-directory
# marker in this shipped file would make every doctor run warn ABSOLUTE_PATH.
_SEP = "/"
OUTSIDE_ROOT = "|".join(re.escape(m) for m in (".." + _SEP, "..\\", "~" + _SEP, _SEP + "Users" + _SEP,
                                               _SEP + "home" + _SEP))

# (id, pattern, why) — each entry is pinned by a test, so a false refusal is fixed by narrowing one pattern.
FORBIDDEN = tuple((name, re.compile(pattern, re.IGNORECASE), why) for name, pattern, why in (
    ("gate-block", r"dgf-gate-result", "a rule never writes, edits or adds a gate block"),
    ("flag", r"(?<![\w-])--(?!(?:strict|verbose)(?![\w-]))[a-z][a-z-]*",
     "a flag other than --strict or --verbose narrows or skips a check"),
    ("tool-grant", r"allowed-tools|Bash\(|disable-model-invocation", "a rule never grants a tool"),
    ("install", r"\b(?:pip3? install|python3? -m pip|uv (?:pip|add)|npm (?:install|i)\b|brew install|apt-get|curl |wget )",
     "a rule never installs or downloads anything"),
    ("git-write", r"\bgit (?:push|reset|clean|checkout|switch|rebase|rm|restore|stash)\b",
     "a rule never rewrites history or discards work"),
    ("outside-root", OUTSIDE_ROOT, "a rule never names a path outside the workspaces root"),
))

LIMIT_WORDS = ("stop", "exit", "status", "block", "blocking", "blocker", "warn", "warning", "critical rule",
               "artifact ownership", "not run", "pre_existing", "skip", "ignore", "optional", "unless", "instead",
               "allow", "permit", "relax", "bypass", "waive")
# Word-bounded and case-insensitive; a plural or past form counts too (STOPs, skipped, allowed, waived).
_LIMIT = re.compile(r"\b(" + "|".join(re.escape(w) for w in LIMIT_WORDS) + r")(?:s|es|d|ed|ing|ped|ping|ted|ting)?\b",
                    re.IGNORECASE)
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
    quoted: list  # (line, text) of each `> ` line — read by the skill, so checked like a rule


@dataclass
class _State:
    rel: str
    rep: object
    rules: list = field(default_factory=list)
    preamble: list = field(default_factory=list)  # (line, text) of each `> ` line
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
    state = _State(rel, rep)
    body = _title(lines, skill, state)
    if body is None:
        return None
    for number, line in body:
        _line(number, line, state)
    _finish(state)
    report.debug("overrides.parse", "parsed", skill=skill, rules=len(state.rules), ok=state.ok)
    return Override(state.rules, state.preamble) if state.ok else None


def _read(path, rel, rep):
    try:
        raw = path.read_bytes()
    except OSError as exc:
        rep.add("OVERRIDE_UNREADABLE", f"cannot read it: {exc.strerror}", file=rel)
        return None
    if len(raw) > MAX_BYTES:
        rep.add("OVERRIDE_UNREADABLE", f"it is {len(raw)} bytes; the most is {MAX_BYTES}", file=rel)
        return None
    try:
        text = raw.decode("utf-8")
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


def _line(number, line, state):
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
    elif state.headings == 0 and (line == ">" or line.startswith("> ")):
        state.preamble.append((number, line[2:]))
    elif not state.rules:
        state.shape("text outside a rule: before `## Rules`, only blank and `> ` lines", number)
    else:
        _rule_line(number, line, state)


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

def _texts(rules, quoted):
    """(what, line, text) for everything a reading skill reads as instruction."""
    found = [(f"rule `{rule.name}`", rule.line, f"{rule.name}\n{rule.text}") for rule in rules]
    return found + [(PREAMBLE, line, text) for line, text in quoted]


def check_rules(rules, rel, rep, quoted=()):
    """OVERRIDE_FORBIDDEN for each construct a text holds; OVERRIDE_TOUCHES_LIMIT once per text naming a limit word."""
    for what, line, text in _texts(rules, quoted):
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
