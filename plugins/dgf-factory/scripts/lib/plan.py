"""plan.py — read a plan file and class the paths it names (ADR 0017 §1–§3).

The header is YAML frontmatter restricted to a flat subset read exactly here:
`key: scalar`, `key: "quoted scalar"` (with \\" and \\\\ escapes) and
`key: [a, "b"]`, with blank lines and `#` comments outside quotes. Anything
else raises PlanFormatError(line, message), which check_plan.py reports as
PLAN_UNREADABLE (exit 3). Values are kept as strings: `plan_format: 1` reads
as "1".

Tasks are the checkbox lines under `## Tasks`, up to the next `## ` heading,
each followed by indented field bullets (`- kind: code`). The parser records
what is there; whether it is valid is check_plan.py's job, so a task with no
`kind` parses and is reported there.

Every path is relative to the workspaces root with `/` separators, and its
first segment is a workspace name. classify() puts each path in exactly one
class — config, code, excluded or other. The code places are a DGF fact read
from the `code-places` table in knowledge/composition-specs.md §5; the
excluded extensions are this plugin's policy. Stdlib only.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import knowledge, report

HEADER_KEYS = ("plan_format", "mode", "branch", "created", "affects_workspaces", "base_workspace_reason", "archived")
MODES = ("fast", "full", "ultra")
KINDS = ("config", "code")
FIELD_NAMES = ("kind", "reason", "files", "deletes")
PIPELINE_DIR = ".dgf-factory"  # the pipeline's own artifacts; every check ignores them
FM = "FM"
CONFIG_EXTENSIONS = (".json", ".xml")
# ADR 0010 §3, restated as file types in ADR 0017 §3: C#, TypeScript and Angular, SQL,
# built assemblies and server-rendered markup are out of scope for this plugin.
EXCLUDED_EXTENSIONS = (".cs", ".csproj", ".sln", ".ts", ".tsx", ".sql", ".dll", ".exe", ".html", ".cshtml",
                       ".razor")
PLUGIN_ASSEMBLY_PREFIX = "applibs"  # ADR 0017 §4: plugin-assembly folders, never workspaces

_KEY_LINE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*):(?:[ \t]+(.*))?\Z")
_TASK_LINE = re.compile(r"- \[([ xX])\] (?:\*\*)?Task (\d+):(.*)\Z")
_FIELD_LINE = re.compile(r"[ \t]{2,}- (kind|reason|files|deletes):[ \t]*(.*)\Z")
_DEPENDS = re.compile(r"\(depends on ([0-9][0-9, and]*)\)")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
_BARE_FORBIDDEN_START = tuple("[]{}&*!|>%@`'")


class PlanFormatError(Exception):
    """The plan's header is outside the flat subset, or the file cannot be read."""

    def __init__(self, line, message):
        super().__init__(f"line {line}: {message}" if line else message)
        self.line = line
        self.message = message


@dataclass
class Task:
    id: int
    title: str
    checked: bool
    line: int
    depends: list = field(default_factory=list)
    links: list = field(default_factory=list)       # link targets in the task line
    fields: dict = field(default_factory=dict)      # name -> (raw value, line)
    duplicates: list = field(default_factory=list)  # field names given more than once

    def value(self, name):
        return self.fields[name][0] if name in self.fields else None

    @property
    def kind(self):
        return self.value("kind")

    @property
    def reason(self):
        return self.value("reason")

    @property
    def files(self):
        return split_paths(self.value("files"))

    @property
    def deletes(self):
        return split_paths(self.value("deletes"))


@dataclass
class Plan:
    path: Path
    header: dict
    header_lines: dict
    tasks: list
    phase_links: list    # (target, line) under `## Phase Index`
    tasks_section: bool  # a `## Tasks` heading exists

    @property
    def mode(self):
        return self.header.get("mode")

    def progress(self):
        return sum(1 for t in self.tasks if t.checked), len(self.tasks)


# --- the header ---------------------------------------------------------------

def _strip_comment(text):
    """`text` without a trailing ` # comment`; a `#` with no space before it stays."""
    match = re.search(r"(?:^|[ \t])#", text)
    return (text[:match.start()] if match else text).strip()


def _quoted(text, line):
    """(value, rest) for a double-quoted scalar at the start of `text`."""
    out, index = [], 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            if index + 1 >= len(text) or text[index + 1] not in '"\\':
                raise PlanFormatError(line, 'only \\" and \\\\ escapes are allowed in a quoted value')
            out.append(text[index + 1])
            index += 2
            continue
        if char == '"':
            return "".join(out), text[index + 1:]
        out.append(char)
        index += 1
    raise PlanFormatError(line, "a quoted value never closes")


def _after_value(rest, line):
    if _strip_comment(rest):
        raise PlanFormatError(line, f"unexpected text after the value: `{rest.strip()}`")


def _bare(text, line):
    value = _strip_comment(text)
    if value.startswith(_BARE_FORBIDDEN_START) or value.startswith("- "):
        raise PlanFormatError(line, f"`{value}` is outside the flat subset — quote it with double quotes")
    if ": " in value or value.endswith(":"):
        raise PlanFormatError(line, f"`{value}` contains `: ` — quote it with double quotes")
    return value


def _flow_items(text, line):
    """(raw items, the text after the closing `]`) — commas and `]` inside quotes do not count."""
    items, current, index = [], "", 1
    while index < len(text):
        char = text[index]
        if char == '"':
            value, rest = _quoted(text[index:], line)
            consumed = len(text[index:]) - len(rest)
            current += text[index:index + consumed]
            index += consumed
            continue
        if char in "[{":
            raise PlanFormatError(line, "a nested list or map is outside the flat subset")
        if char in ",]":
            items.append(current.strip())
            current = ""
            if char == "]":
                return items, text[index + 1:]
        else:
            current += char
        index += 1
    raise PlanFormatError(line, "a `[` list never closes on its line")


def _flow_list(text, line):
    raw_items, rest = _flow_items(text, line)
    _after_value(rest, line)
    if raw_items == [""]:
        return []
    items = []
    for item in raw_items:
        if item.startswith('"'):
            value, after = _quoted(item, line)
            if after.strip():
                raise PlanFormatError(line, f"unexpected text after a quoted list item: `{after.strip()}`")
            items.append(value)
        elif not item or item.startswith(_BARE_FORBIDDEN_START) or ": " in item or "#" in item:
            raise PlanFormatError(line, f"list item `{item}` is outside the flat subset")
        else:
            items.append(item)
    return items


def _value(text, line):
    if text is None or not text.strip() or text.strip().startswith("#"):
        return None
    text = text.strip()
    if text.startswith('"'):
        value, rest = _quoted(text, line)
        _after_value(rest, line)
        return value
    if text.startswith("["):
        return _flow_list(text, line)
    return _bare(text, line)


def parse_header(lines):
    """({key: value}, {key: line}, index of the first body line). Raises PlanFormatError."""
    if not lines or lines[0].rstrip() != "---":
        raise PlanFormatError(1, "no frontmatter — the first line must be `---`")
    header, where = {}, {}
    for index in range(1, len(lines)):
        number, text = index + 1, lines[index].rstrip()
        if text == "---":
            return header, where, index + 1
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        match = _KEY_LINE.match(text)
        if not match:
            raise PlanFormatError(number, f"`{text.strip()}` is not a flat `key: value` line")
        key = match.group(1)
        if key in header:
            raise PlanFormatError(number, f"`{key}` is given twice")
        header[key], where[key] = _value(match.group(2), number), number
    raise PlanFormatError(1, "the frontmatter never closes — no second `---` line")


# --- the body -----------------------------------------------------------------

def _depends(text):
    match = _DEPENDS.search(text)
    if not match:
        return [], text
    ids = [int(n) for n in re.findall(r"\d+", match.group(1))]
    return ids, (text[:match.start()] + text[match.end():])


def _title(text):
    links = [target for _, target in _LINK.findall(text)]
    plain = _LINK.sub(lambda m: m.group(1), text).replace("**", "")
    return " ".join(plain.split()), links


def _task(match, number):
    depends, rest = _depends(match.group(3))
    title, links = _title(rest)
    return Task(int(match.group(2)), title, match.group(1) != " ", number, depends, links)


def _add_field(task, match, number):
    name, value = match.group(1), match.group(2).strip()
    if name in task.fields:
        task.duplicates.append(name)
        return
    task.fields[name] = (value, number)


def _body_sections(lines, start):
    """Yield (line number, text, current `## ` heading, is-a-heading) outside fenced code blocks."""
    heading, in_fence = None, False
    for index in range(start, len(lines)):
        text = lines[index].rstrip()
        if text.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if text.startswith("## "):
            heading = text[3:].strip()
            yield index + 1, text, heading, True
            continue
        yield index + 1, text, heading, False


def parse_text(text, path="<plan>"):
    lines = text.lstrip("﻿").splitlines()
    header, where, start = parse_header(lines)
    tasks, phase_links, tasks_section, current = [], [], False, None
    for number, line, heading, is_heading in _body_sections(lines, start):
        if is_heading:
            tasks_section = tasks_section or heading == "Tasks"
            current = None
            continue
        if heading == "Phase Index":
            phase_links += [(target, number) for _, target in _LINK.findall(line)]
        if heading != "Tasks":
            continue
        task_match = _TASK_LINE.match(line)
        if task_match:
            current = _task(task_match, number)
            tasks.append(current)
            continue
        field_match = _FIELD_LINE.match(line)
        if current is not None and field_match:
            _add_field(current, field_match, number)
        elif line and not line[0].isspace():
            current = None  # an unindented line ends the task's bullets
    plan = Plan(Path(path), header, where, tasks, phase_links, tasks_section)
    report.debug("plan.parse", "parsed", path=path, keys=",".join(header), tasks=len(tasks),
                 phase_links=len(phase_links))
    return plan


def entrypoint(path):
    """`path` itself, or `<path>/index.md` when `path` is an ultra bundle's directory."""
    path = Path(path)
    return path / "index.md" if path.is_dir() else path


def parse(path):
    """The Plan at `path` — a plan file, or an ultra bundle's directory. Raises PlanFormatError."""
    path = entrypoint(path)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise PlanFormatError(None, f"cannot read {path}: {exc.strerror}") from exc
    except UnicodeDecodeError as exc:
        raise PlanFormatError(None, f"{path} is not UTF-8: {exc}") from exc
    return parse_text(text, path)


def split_paths(value):
    """A `files:`/`deletes:` value as a list of paths, backticks and `./` removed."""
    if not value:
        return []
    paths = []
    for raw in value.split(","):
        item = raw.strip().strip("`").strip()
        if item.startswith("./"):
            item = item[2:]
        if item:
            paths.append(item)
    return paths


# --- path classes (ADR 0017 §3) ---------------------------------------------------

def segments(rel_path):
    return [part for part in rel_path.replace("\\", "/").split("/") if part]


_DRIVE = re.compile(r"[A-Za-z]:")


def path_problem(rel_path):
    """Why `rel_path` is not a plain root-relative path, or None (ADR 0017 §2).

    A plan path names a file below the workspaces root, so it is never absolute,
    never names a drive, uses `/` only, and has no empty, `.` or `..` segment:
    `webasm/FM/../../x.json` would otherwise class as webasm configuration while
    naming a file outside the root.
    """
    why = None
    if rel_path.startswith(("/", "\\")):
        why = "is absolute"
    elif _DRIVE.match(rel_path):
        why = "names a drive"
    elif "\\" in rel_path:
        why = "uses `\\`"
    elif rel_path.endswith("/"):
        why = "ends with `/`"
    else:
        parts = rel_path.split("/")
        if ".." in parts:
            why = "climbs out with `..`"
        elif "." in parts:
            why = "has a `.` segment"
        elif "" in parts:
            why = "has an empty segment"
    if why:
        report.debug("plan.path_problem", "rejected", path=rel_path, why=why)
    return why


def workspace_of(rel_path):
    """The first path segment — the workspace a root-relative path names."""
    parts = segments(rel_path)
    return parts[0] if parts else ""


def is_pipeline(rel_path):
    return workspace_of(rel_path) == PIPELINE_DIR


def is_plugin_assembly_folder(name):
    return name.lower().startswith(PLUGIN_ASSEMBLY_PREFIX)


def _extension(name):
    dot = name.rfind(".")
    return name[dot:].lower() if dot > 0 else ""


def _placeholder(segment):
    return segment.startswith("<") and segment.endswith(">")


def matches_folder(pattern, parts):
    """`parts` (the folders) fill `pattern` exactly; a placeholder ending the pattern takes one or more."""
    for index, segment in enumerate(pattern):
        last = index == len(pattern) - 1
        if _placeholder(segment) and last:
            return len(parts) > index
        if index >= len(parts) or (not _placeholder(segment) and parts[index] != segment):
            return False
    return len(parts) == len(pattern)


def _matches_prefix(pattern, parts):
    """`parts` (the folders) sit at or below `pattern`, placeholders one segment each."""
    if len(parts) < len(pattern):
        return False
    return all(_placeholder(seg) or parts[i] == seg for i, seg in enumerate(pattern))


def code_place(rel_path):
    """The `code-places` row a root-relative path matches, or None."""
    inside = segments(rel_path)[1:]
    if not inside:
        return None
    folders, name = inside[:-1], inside[-1]
    for row in knowledge.load("code-places"):
        pattern = segments(row["Path"])
        if row["Filename"] != knowledge.NONE:
            if name == row["Filename"] and matches_folder(pattern, folders):
                return row
        elif _extension(name) == row["Extension"] and _matches_prefix(pattern, folders):
            return row
    return None


def classify(rel_path):
    """"config", "code", "excluded" or "other" for a root-relative path (ADR 0017 §3)."""
    parts = segments(rel_path)
    name = parts[-1] if parts else ""
    if (parts and is_plugin_assembly_folder(parts[0])) or _extension(name) in EXCLUDED_EXTENSIONS:
        result = "excluded"
    elif code_place(rel_path):
        result = "code"
    elif len(parts) >= 3 and parts[1] == FM and _extension(name) in CONFIG_EXTENSIONS:
        result = "config"
    else:
        result = "other"
    report.debug("plan.classify", "classed", path=rel_path, result=result)
    return result
