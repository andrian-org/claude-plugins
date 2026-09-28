"""patches.py — read a patch file and the patch cursor (ADR 0024 §1, §6).

A patch is `<paths.patches>/<YYYY-MM-DD-HH.mm>-<slug>.md`, written once by
/dgf-fix and never edited:

    # <title>

    - date: YYYY-MM-DD HH:mm
    - plan: none | .dgf-factory/<path>
    - workspaces: none | <ws>, <ws>
    - files: none | <ws>/<path>, <ws>/<path>
    - findings: none | <CODE>, <CODE>
    - dgf_version: unknown | X.Y.Z
    - severity: low | medium | high | critical

    ## Problem / ## Root Cause / ## Solution / ## Prevention / ## Tags

The keys and headings are fixed English, so this module can read them; the
prose is in the estate's own language. parse() records every problem as a
finding in the caller's Report and returns what it could read, or None when
the file is not readable UTF-8. A `## ` line inside a fence is text, not a
heading.

The cursor is `<paths.evolutions>/patch-cursor.json`,
`{"processed": [<names>], "updated": "<when>"}`: a set of names, not a
high-water mark, because branches merge patches into one ledger in any order.
read_cursor() never raises.

Every file is read through read_small(): a regular file of bounded size, so a
committed symlink to a device or a huge file cannot hang or exhaust a reader.
A leading UTF-8 byte-order mark is dropped. Stdlib only.
"""

import datetime
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import plan, report

NAME = re.compile(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})\.(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md\Z")
SLUG_MAX = 50
FIELDS = ("date", "plan", "workspaces", "files", "findings", "dgf_version", "severity")
SECTIONS = ("Problem", "Root Cause", "Solution", "Prevention", "Tags")
SEVERITIES = ("low", "medium", "high", "critical")
NONE = "none"
UNKNOWN_VERSION = "unknown"
TITLE_MAX = 120
MAX_BYTES = 65536          # a patch is a page of prose
CURSOR_MAX_BYTES = 1 << 20  # about 16,000 patch names
BOM = "\ufeff"

_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})\Z")
_VERSION = re.compile(r"\d+\.\d+\.\d+\Z")
_TAG = re.compile(r"#[a-z0-9][a-z0-9-]*\Z")
_FIELD = re.compile(r"- ([A-Za-z_][A-Za-z0-9_]*):(?:[ \t]+(.*?))?[ \t]*\Z")
_FENCE = ("```", "~~~")


@dataclass
class Patch:
    name: str
    title: str = ""
    fields: dict = field(default_factory=dict)    # key -> raw value, as written
    sections: dict = field(default_factory=dict)  # section name -> its text

    def value(self, key):
        return self.fields.get(key, "")

    def codes(self):
        """The `findings` codes, or [] for `none` or a field that is missing."""
        raw = self.value("findings")
        return [] if raw in ("", NONE) else _items(raw)


def _items(raw):
    """A comma-separated value as a list, each item stripped of spaces and backticks."""
    return [item.strip().strip("`").strip() for item in raw.split(",")]


# --- reading -----------------------------------------------------------------------

def read_small(path, limit):
    """(bytes, None), or (None, why): a regular file of at most `limit` bytes, never read past `limit`."""
    path = Path(path)
    try:
        if not path.is_file():
            return None, "not a regular file"
        size = path.stat().st_size
        if size > limit:
            return None, f"it is {size} bytes; the most is {limit}"
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError as exc:
        return None, f"cannot read it: {exc.strerror}"
    if len(data) > limit:
        return None, f"it grew past {limit} bytes while being read"
    report.debug("patches.read_small", "read", path=path, size=len(data))
    return data, None


def decode(data):
    """UTF-8 text with a leading byte-order mark dropped. Raises UnicodeDecodeError."""
    text = data.decode("utf-8")
    return text[len(BOM):] if text.startswith(BOM) else text


# --- the name ---------------------------------------------------------------------

def name_problem(name):
    """Why `name` is not `<YYYY-MM-DD-HH.mm>-<slug>.md`, or None."""
    match = NAME.match(name)
    if not match:
        return "is not `<YYYY-MM-DD-HH.mm>-<slug>.md`, with a lowercase slug of letters, digits and single hyphens"
    if len(match.group(6)) > SLUG_MAX:
        return f"has a slug of {len(match.group(6))} characters; the most is {SLUG_MAX}"
    if _timestamp(match.groups()[:5]) is None:
        return "has a timestamp that is not a real date and time"
    return None


def _timestamp(parts):
    try:
        return datetime.datetime(*(int(p) for p in parts))
    except ValueError:
        return None


def name_timestamp(name):
    """The name's timestamp as a datetime, or None when the name is not a patch name."""
    match = NAME.match(name)
    return _timestamp(match.groups()[:5]) if match else None


# --- reading one patch ------------------------------------------------------------

def parse(path, rel, rep):
    """The Patch at `path`, with every problem added to `rep` at `rel`; None when unreadable."""
    path = Path(path)
    why = name_problem(path.name)
    if why:
        rep.add("PATCH_NAME_INVALID", f"`{path.name}` {why}", file=rel)
    data, why = read_small(path, MAX_BYTES)
    if why:
        rep.add("PATCH_UNREADABLE", why, file=rel)
        return None
    try:
        text = decode(data)
    except UnicodeDecodeError as exc:
        rep.add("PATCH_UNREADABLE", f"not UTF-8 at byte {exc.start}", file=rel)
        return None
    found = Patch(path.name)
    lines = text.replace("\r\n", "\n").split("\n")  # not splitlines(): U+2028 and friends stay in their line
    start = _title(lines, found, rel, rep)
    first_section = _fields(lines, start, found, rel, rep)
    _sections(lines, first_section, found, rel, rep)
    report.debug("patches.parse", "parsed", name=path.name, fields=len(found.fields), sections=len(found.sections),
                 findings=len(rep.findings))
    return found


def _title(lines, found, rel, rep):
    """Read `# <title>` from the first non-blank line → the index after it."""
    index = next((i for i, line in enumerate(lines) if line.strip()), len(lines))
    line = lines[index] if index < len(lines) else ""
    title = line[2:].strip() if line.startswith("# ") else ""
    if not title:
        rep.add("PATCH_FIELD_MISSING", "the first line is not `# <title>`", line=index + 1 if line else None,
                file=rel)
        return index
    if len(title) > TITLE_MAX:
        rep.add("PATCH_FIELD_MISSING", f"the title is {len(title)} characters; the most is {TITLE_MAX}",
                line=index + 1, file=rel)
    found.title = title
    return index + 1


def _is_heading(line):
    return line.startswith("## ")


def _fields(lines, start, found, rel, rep):
    """Read the `- <key>: <value>` bullets up to the first `## ` → the index of that heading."""
    seen = {}
    index = start
    while index < len(lines) and not _is_heading(lines[index]):
        line = lines[index]
        index += 1
        if not line.strip():
            continue
        match = _FIELD.match(line)
        if not match:
            rep.add("PATCH_FIELD_INVALID", "a line before the first section is not a `- <key>: <value>` field",
                    line=index, file=rel)
            continue
        key, value = match.group(1), (match.group(2) or "").strip()
        if key not in FIELDS:
            rep.add("PATCH_FIELD_INVALID", f"`{key}` is not a patch field; the fields are {', '.join(FIELDS)}",
                    line=index, file=rel)
        elif key in seen:
            rep.add("PATCH_FIELD_INVALID", f"`{key}` is given twice (first at line {seen[key]})", line=index, file=rel)
        else:
            seen[key] = index
            found.fields[key] = value
    for key in FIELDS:
        if key not in seen:
            rep.add("PATCH_FIELD_MISSING", f"no `- {key}:` field", file=rel)
    for key, line in seen.items():
        why = _value_problem(key, found)
        if why:
            rep.add("PATCH_FIELD_INVALID", f"`{key}` is `{found.fields[key]}`: {why}", line=line, file=rel)
    return index


def _value_problem(key, found):
    value = found.fields[key]
    if not value:
        return "it is empty"
    return _CHECKS[key](value, found)


def _check_date(value, found):
    match = _DATE.match(value)
    if not match:
        return "not `YYYY-MM-DD HH:mm`"
    when = _timestamp(match.groups())
    if when is None:
        return "not a real date and time"
    named = name_timestamp(found.name)
    if named is not None and named != when:
        return f"it disagrees with the name's timestamp, {named:%Y-%m-%d %H:%M}"
    return None


def _check_plan(value, found):
    if value == NONE:
        return None
    path = value.strip("`").strip()
    why = plan.path_problem(path)
    if why:
        return f"the path {why}"
    if not plan.is_pipeline(path) or len(plan.segments(path)) < 2:
        return f"not `{NONE}` or a path under `{plan.PIPELINE_DIR}/`"
    return None


def _workspaces(found):
    """The listed workspace names, or None when the field is `none`, missing or invalid."""
    value = found.fields.get("workspaces", "")
    if value in ("", NONE) or _check_workspaces(value, found):
        return None
    return set(_items(value))


def _check_workspaces(value, found):
    if value == NONE:
        return None
    for name in _items(value):
        if not name or plan.path_problem(name) or "/" in name:
            return f"`{name}` is not a plain workspace name"
        if name == plan.PIPELINE_DIR or plan.is_plugin_assembly_folder(name):
            return f"`{name}` is never a workspace"
    return None


def _check_files(value, found):
    if value == NONE:
        return None
    if found.fields.get("workspaces") == NONE:
        return f"`workspaces` is `{NONE}`, so `files` must be too"
    listed = _workspaces(found)
    for path in _items(value):
        why = plan.path_problem(path) if path else "is empty"
        if why:
            return f"`{path}` {why}"
        if listed is not None and plan.workspace_of(path) not in listed:
            return f"`{path}` is not in a workspace `workspaces` lists"
    return None


def _check_findings(value, found):
    if value == NONE:
        return None
    unknown = [code for code in _items(value) if code not in report.CODES]
    return f"not a finding code: {', '.join(f'`{c}`' for c in unknown)}" if unknown else None


def _check_version(value, found):
    return None if value == UNKNOWN_VERSION or _VERSION.match(value) else f"not `{UNKNOWN_VERSION}` or `X.Y.Z`"


def _check_severity(value, found):
    return None if value in SEVERITIES else f"not one of {', '.join(SEVERITIES)}"


_CHECKS = {"date": _check_date, "plan": _check_plan, "workspaces": _check_workspaces, "files": _check_files,
           "findings": _check_findings, "dgf_version": _check_version, "severity": _check_severity}


# --- the sections -----------------------------------------------------------------

def _headings(lines, start):
    """[(name, line number, [(line number, text)])] for each `## ` heading outside a fence."""
    headings, fenced = [], False
    for index in range(start, len(lines)):
        line = lines[index]
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
        if not fenced and _is_heading(line):
            headings.append((line[3:].strip(), index + 1, []))
        elif headings:
            headings[-1][2].append((index + 1, line))
    return headings


def _sections(lines, start, found, rel, rep):
    last = -1
    for name, line, body in _headings(lines, start):
        if name not in SECTIONS:
            rep.add("PATCH_SECTION_INVALID", f"`## {name}` is not a patch section; they are "
                                             f"{', '.join(SECTIONS)}", line=line, file=rel)
            continue
        if name in found.sections:
            rep.add("PATCH_SECTION_INVALID", f"`## {name}` is repeated", line=line, file=rel)
            continue
        if SECTIONS.index(name) < last:
            rep.add("PATCH_SECTION_INVALID", f"`## {name}` is out of order; the order is {', '.join(SECTIONS)}",
                    line=line, file=rel)
        last = max(last, SECTIONS.index(name))
        found.sections[name] = "\n".join(text for _, text in body).strip()
        if not found.sections[name]:
            rep.add("PATCH_SECTION_INVALID", f"`## {name}` is empty", line=line, file=rel)
        elif name == "Tags":
            _tags(body, rel, rep)
    for name in SECTIONS:
        if name not in found.sections:
            rep.add("PATCH_SECTION_INVALID", f"no `## {name}` section", file=rel)


def _tags(body, rel, rep):
    for line, text in body:
        bad = [word for word in text.split() if not _TAG.match(word)]
        if bad:
            rep.add("PATCH_SECTION_INVALID", f"`## Tags` holds {', '.join(f'`{w}`' for w in bad)}; each tag is "
                                             f"`#` and lowercase letters, digits and hyphens", line=line, file=rel)


# --- the cursor -------------------------------------------------------------------

def read_cursor(path):
    """(processed names, None), or (None, why) when the cursor cannot be used. A missing file is nothing processed."""
    path = Path(path)
    if not path.exists():
        report.debug("patches.read_cursor", "read", processed=0, missing=True)
        return set(), None
    raw, why = read_small(path, CURSOR_MAX_BYTES)
    if why:
        return _unreadable(why)
    try:
        data = json.loads(decode(raw))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:  # a deeply nested document recurses
        return _unreadable(f"not a JSON document: {exc}")
    if not isinstance(data, dict):
        return _unreadable("not a JSON object")
    processed = data.get("processed")
    if not isinstance(processed, list) or not all(isinstance(name, str) for name in processed):
        return _unreadable("`processed` is not a list of patch names")
    if not isinstance(data.get("updated"), str):
        return _unreadable("`updated` is not a string")
    report.debug("patches.read_cursor", "read", processed=len(processed))
    return set(processed), None


def _unreadable(why):
    report.debug("patches.read_cursor", "unreadable", why=why)
    return None, why
