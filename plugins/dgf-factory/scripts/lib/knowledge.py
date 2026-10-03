"""knowledge.py — load the machine-read tables in knowledge/.

The contract is knowledge/README.md §7: a table is read only when the line
immediately above its header row is `<!-- machine-read: <table-id> -->`; its
header cells must be exactly the ones declared here; cells are stripped of
whitespace and one pair of surrounding backticks; the first column is a unique
key; the table ends at a blank line, and any other non-row line is malformed. Any deviation is
a KnowledgeTableError, which a validator turns into exit 3 and doctor.py into the
error KNOWLEDGE_TABLE.

Stdlib only, and it imports nothing from its own package: doctor.py loads this
file by path with importlib, where a relative import cannot resolve.
"""

import os
import re
import sys
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

# table id -> (knowledge file, exact header cells, {column: allowed values})
TABLES = {
    "legacy-artifacts": (
        "composition-specs.md",
        ("Artifact", "Filename", "Folder", "Grammar"),
        {},
    ),
    "code-places": (
        "composition-specs.md",
        ("Place", "Path", "Filename", "Extension", "Loaded by", "New file loaded"),
        {"Extension": {".js", ".css"}, "New file loaded": {"yes", "no"}},
    ),
    "component-classes": (
        "json-reader.md",
        ("ComponentType", "Configuration schema", "Bound by"),
        {"Bound by": {"name", "prefix", "none"}},
    ),
    "datasource-discriminators": (
        "json-reader.md",
        ("Discriminator", "Schema"),
        {},
    ),
    "component-folders": (
        "json-reader.md",
        ("Folder", "Loader", "Selection"),
        {"Selection": {"by-type", "by-discriminator", "fragment-by-type", "none"}},
    ),
    "enum-member-names": (
        "json-reader.md",
        ("JSON name", "Enum", "Member"),
        {},
    ),
    "layout-components": (
        "json-reader.md",
        ("ComponentType", "Class"),
        {},
    ),
    "dispatchable": (
        "component-catalogue.md",
        ("ComponentType", "Service", "Component extension module"),
        {},
    ),
    "correspondence": (
        "schema-families.md",
        ("XSD", "Root", "JSON counterpart", "Relationship"),
        {},
    ),
    "parity": (
        "schema-families.md",
        ("#", "Row", "ComponentType", "Schema", "Runtime", "XML-only part"),
        {"Runtime": {"✓", "◐", "✗", "—"}},
    ),
    "process-divergence": (
        "process-model.md",
        ("Construct", "Kind", "XSD owner", "Binding"),
        {"Kind": {"attribute", "element", "enum-relaxed"}},
    ),
    "reference-edges": (
        "reference-graph.md",
        ("Edge", "From", "Element", "Attribute", "Condition", "To", "Resolves as", "When absent", "When empty",
         "Reach", "Checked by"),
        {"From": {"process", "multitask", "workflow", "form", "settings", "component"},
         "To": {"workflow", "multitask", "process", "settings", "form", "lookup-view", "lookup-dialog", "grid-form",
                "component"},
         "Condition": {"—", "control-form", "fieldset-non-empty", "extract-no-table", "mode-change-state",
                       "mode-start-info"},
         "Resolves as": set(),  # filled from RESOLVES_AS below
         "When absent": {"throws", "template", "caught", "skipped", "unknown"},
         "When empty": {"none", "throws", "unknown", "—"},
         "Reach": {"follow", "end", "none"},
         "Checked by": {"validate_process.py", "validate_model.py", "resolve_components.py", "—"}},
    ),
    "run-time-names": (
        "reference-graph.md",
        ("Name", "Step", "Replaces"),
        {},
    ),
    "role-sources": (
        "permissions.md",
        ("Source", "File", "Element", "Attribute", "Separator", "Meaning"),
        {"Separator": {",", "—"}},
    ),
    "field-types": (
        "data-model.md",
        ("Type", "In settings.xsd", "Fact"),
        {"In settings.xsd": {"yes", "no"}},
    ),
    "db-types": (
        "data-model.md",
        ("Dbtype", "Fact"),
        {},
    ),
    "field-sql-types": (
        "data-model.md",
        ("Dbtype", "Size rule", "SQL type", "Evidence"),
        {"Size rule": {"size", "none", "precision", "fixed", "max"}},
    ),
    "workspace-minimum": (
        "application-layout.md",
        ("File", "Root", "Required", "Rule", "Fact"),
        {},
    ),
    "auth-schemes": (
        "application-layout.md",
        ("Provider", "Section", "Keys", "Fact"),
        {},
    ),
    "instance-models": (
        "application-layout.md",
        ("Model", "Mounts", "Sitemap", "Applications row", "Fact"),
        {"Mounts": {"shared", "own"}, "Sitemap": {"override", "own"}, "Applications row": {"per-instance"}},
    ),
    "solution-parts": (
        "application-layout.md",
        ("Part", "Verified values", "Placeholders", "Fact"),
        {},
    ),
}

# `Resolves as` in reference-edges -> how many parts a reference passes to the rule. A row whose
# Attribute alternatives do not each have that many `+`-joined parts is malformed (README §7).
RESOLVES_AS = {
    "action": 1, "workflow-name": 1, "process-name": 1, "multitask-file": 1, "table-name": 1, "form": 2,
    "invoke-form": 2, "lookup-view": 2, "lookup-dialog": 1, "grid": 2, "owning-table": 0, "datasource": 1,
    "component-file": 1,
}
TABLES["reference-edges"][2]["Resolves as"].update(RESOLVES_AS)

NONE = "—"  # the cell value knowledge files write for "no such thing"

_MARKER = re.compile(r"<!--\s*machine-read:\s*([a-z0-9-]+)\s*-->\Z")
_SEPARATOR = re.compile(r"\|(\s*:?-+:?\s*\|)+\Z")
_CACHE = {}


class KnowledgeTableError(Exception):
    """A machine-read table is missing or does not match its declared shape."""

    def __init__(self, table_id, reason):
        super().__init__(f"knowledge table `{table_id}` malformed — {reason} — run /dgf-doctor")
        self.table_id = table_id
        self.reason = reason


def _debug(message, **kv):
    if not (os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug"):
        return
    pairs = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"DEBUG [knowledge.load] {message} {pairs}".rstrip(), file=sys.stderr)


def _cells(line):
    """The stripped cells of one table row, one pair of backticks removed."""
    inner = line.strip()[1:-1]
    cells = []
    for raw in inner.split("|"):
        cell = raw.strip()
        if len(cell) >= 2 and cell.startswith("`") and cell.endswith("`"):
            cell = cell[1:-1]
        cells.append(cell)
    return cells


def _is_row(line):
    stripped = line.strip()
    return len(stripped) >= 2 and stripped.startswith("|") and stripped.endswith("|")


def _marker_lines(lines, table_id):
    """Indexes of this table's marker lines, ignoring fenced code blocks."""
    found, in_fence = [], False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        match = _MARKER.match(line.strip())
        if not in_fence and match and match.group(1) == table_id:
            found.append(index)
    return found


def _parse(table_id, lines, headers, allowed):
    markers = _marker_lines(lines, table_id)
    if not markers:
        raise KnowledgeTableError(table_id, "marker not found")
    if len(markers) > 1:
        raise KnowledgeTableError(table_id, f"marker appears {len(markers)} times")

    start = markers[0] + 1
    if start >= len(lines) or not _is_row(lines[start]):
        raise KnowledgeTableError(table_id, "no header row directly below the marker")
    found = tuple(_cells(lines[start]))
    if found != headers:
        raise KnowledgeTableError(table_id, f"header is {list(found)}, expected {list(headers)}")
    if start + 1 >= len(lines) or not _SEPARATOR.match(lines[start + 1].strip()):
        raise KnowledgeTableError(table_id, "no separator row below the header")

    rows, keys = [], set()
    for offset, line in enumerate(lines[start + 2:], start + 3):
        if not line.strip():
            break
        if not _is_row(line):
            # Markdown still renders a row that lost its closing pipe; stopping here would
            # silently drop it and every row after it.
            raise KnowledgeTableError(table_id, f"line {offset} is not a `| … |` row — a table ends at a "
                                                f"blank line")
        cells = _cells(line)
        if len(cells) != len(headers):
            raise KnowledgeTableError(table_id, f"line {offset} has {len(cells)} cells, expected {len(headers)}")
        row = dict(zip(headers, cells))
        if row[headers[0]] in keys:
            raise KnowledgeTableError(table_id, f"duplicate key `{row[headers[0]]}` on line {offset}")
        keys.add(row[headers[0]])
        for column, values in allowed.items():
            if row[column] not in values:
                raise KnowledgeTableError(
                    table_id, f"line {offset}: {column} `{row[column]}` is not one of {sorted(values)}")
        rows.append(row)
    if not rows:
        raise KnowledgeTableError(table_id, "table has no rows")
    return rows


def load(table_id, knowledge_dir=None):
    """The rows of one machine-read table, as a list of dicts keyed by header."""
    if table_id not in TABLES:
        raise KnowledgeTableError(table_id, "unknown table id")
    base = Path(knowledge_dir) if knowledge_dir else KNOWLEDGE_DIR
    cache_key = (str(base), table_id)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    filename, headers, allowed = TABLES[table_id]
    path = base / filename
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise KnowledgeTableError(table_id, f"cannot read {filename}: {exc.strerror}") from exc
    except UnicodeDecodeError as exc:
        raise KnowledgeTableError(table_id, f"{filename} is not UTF-8: {exc}") from exc
    rows = _parse(table_id, lines, headers, allowed)
    for row in rows:
        _ROW_CHECKS.get(table_id, lambda _row: None)(row)
    _debug("loaded", table=table_id, file=filename, rows=len(rows))
    _CACHE[cache_key] = rows
    return rows


def index(table_id, knowledge_dir=None, key=None, fold=False):
    """{key column value: row}; `fold=True` lower-cases the keys."""
    rows = load(table_id, knowledge_dir)
    column = key or TABLES[table_id][1][0]
    return {(row[column].lower() if fold else row[column]): row for row in rows}


def load_all(knowledge_dir=None):
    """Load every declared table; the first malformed one raises."""
    return {table_id: load(table_id, knowledge_dir) for table_id in TABLES}


def values(cell):
    """A multi-valued cell's values: space-separated alternatives, each kept whole; `—` is none (README §7)."""
    return [] if cell.strip() == NONE else cell.split()


def parts(value):
    """The parts of one value: `a+b` is one composite reference of two parts, in order."""
    return value.split("+")


def _check_arity(row):
    """Each Attribute alternative passes as many `+`-joined parts as its `Resolves as` rule takes."""
    arity = RESOLVES_AS[row["Resolves as"]]
    counts = [len(parts(value)) for value in values(row["Attribute"])] or [0]
    if any(count != arity for count in counts):
        raise KnowledgeTableError("reference-edges", f"edge `{row['Edge']}`: Attribute `{row['Attribute']}` passes "
                                                     f"{counts} part(s), but `{row['Resolves as']}` takes {arity}")


_ROW_CHECKS = {"reference-edges": _check_arity}


def edges(knowledge_dir=None):
    """The reference-edges rows. load() has already checked each row's arity (_check_arity)."""
    return load("reference-edges", knowledge_dir)
