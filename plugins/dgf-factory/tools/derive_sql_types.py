#!/usr/bin/env python3
"""derive_sql_types.py — derive each `dbtype`'s SQL column type from DGF's own settings/table pairs.

A repo-maintenance tool, not a runtime validator: a maintainer runs it against a DGF
checkout to (re)produce the `field-sql-types` table in knowledge/data-model.md §6. It
modifies nothing and needs no lxml (xml.etree only), so it runs anywhere.

No DGF code turns a `settings.xml` into a `CREATE TABLE`, so the mapping is not read from
code: it is tallied from the samples. Every `FM/_DATA/<T>/settings.xml` in DGF's `webasm`
and `dgf` sample workspaces is paired with the baseline's `dbo/Tables/<T>.sql` by exact
case. For each field of a pair that has a column, the field's `dbtype` and `size` and the
column's declared type are read, and per (`dbtype`, size rule) the tool prints the majority
SQL type, `n/N`, and every alternative it saw.

  Size rule   the column's length against the field's `size`:
    size      the column length is the field's `size`          -> TYPE(size)
              (a (MAX) column, whose field `size` is 2147483647, is this rule too)
    max       the column length is MAX, and the field has none  -> TYPE(MAX)
    fixed     the column has a length, and it is not `size`     -> TYPE(<literal>)
    none      the column has no length or precision             -> TYPE
    precision a DECIMAL/NUMERIC column's precision and scale    -> TYPE(p,s)

A computed (`AS`) column is skipped, and so is a field with no column.

Usage:  derive_sql_types.py <dgf-root> [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  the tally was printed
  3  usage error — not a DGF root, or no pair was found
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib import report  # noqa: E402 — after the path insert

WORKSPACES = ("webasm", "dgf")
SAMPLES = Path("src") / "samples"
TABLES = SAMPLES / "Database" / "dbo" / "Tables"

CREATE = re.compile(r"CREATE\s+TABLE\s+[^(]*\(", re.IGNORECASE)
COLUMN = re.compile(
    r"^\s*\[?(?P<name>[A-Za-z0-9_]+)\]?\s+\[?(?P<type>[A-Za-z0-9_]+)\]?"
    r"(?:\s*\(\s*(?P<args>[^)]*?)\s*\))?",
)
MAX_SIZE = "2147483647"  # a field `size` for a (MAX) column
NOT_A_COLUMN = {"constraint", "primary", "unique", "foreign", "index", "check", "period"}


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(report.EXIT_USAGE)


def table_columns(path):
    """{lower-case column name: (SQL type, args)} of one CREATE TABLE; computed columns skipped."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"--[^\n]*", "", text)
    opened = CREATE.search(text)
    if not opened:
        return {}
    depth, body_start, end = 1, opened.end(), None
    for i in range(body_start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    body = text[body_start:end] if end is not None else text[body_start:]
    columns, part, depth = {}, [], 0
    parts = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(part))
            part = []
        else:
            part.append(ch)
    parts.append("".join(part))
    for raw in parts:
        match = COLUMN.match(raw)
        if not match:
            continue
        name, sql_type = match["name"], match["type"]
        if name.lower() in NOT_A_COLUMN:
            continue
        if sql_type.upper() == "AS":
            report.debug("derive_sql_types.pair", "computed", column=name)
            continue
        columns[name.lower()] = (sql_type.upper(), (match["args"] or "").replace(" ", "").upper())
    return columns


def entity_fields(path):
    """[(name, dbtype, size)] of one settings.xml, read with xml.etree."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        report.debug("derive_sql_types.pair", "unreadable", path=path, error=error)
        return []
    return [
        (f.get("name", ""), f.get("dbtype", ""), (f.get("size") or "").strip())
        for f in root.iter("field")
    ]


def size_rule(sql_type, args, size):
    """(rule, SQL type text) — the text uses `size` where the column length is the field's."""
    if not args:
        return "none", sql_type
    if sql_type in ("DECIMAL", "NUMERIC"):
        return "precision", f"{sql_type}({args})"
    if args == "MAX" and size == MAX_SIZE:
        return "size", f"{sql_type}(size)"  # the settings file spells MAX as 2147483647
    if args == "MAX":
        return "max", f"{sql_type}(MAX)"
    if size and args == size:
        return "size", f"{sql_type}(size)"
    return "fixed", f"{sql_type}({args})"


def collect(root):
    """(tally, pairs) — tally[(dbtype, rule)] is a Counter of SQL type text."""
    tally = defaultdict(Counter)
    pairs = 0
    for workspace in WORKSPACES:
        data = root / SAMPLES / "workspaces" / workspace / "FM" / "_DATA"
        if not data.is_dir():
            continue
        for entry in sorted(data.iterdir()):
            script = root / TABLES / f"{entry.name}.sql"
            settings = entry / "settings.xml"
            if not (settings.is_file() and script.is_file()):
                continue
            if script.name != f"{entry.name}.sql" or not any(
                    p.name == script.name for p in script.parent.iterdir()):
                continue  # exact case only
            columns = table_columns(script)
            fields = entity_fields(settings)
            pairs += 1
            matched = 0
            for name, dbtype, size in fields:
                column = columns.get(name.lower())
                if column is None:
                    report.debug("derive_sql_types.pair", "no-column", table=entry.name, field=name)
                    continue
                matched += 1
                rule, text = size_rule(column[0], column[1], size)
                tally[(dbtype, rule)][text] += 1
            report.debug("derive_sql_types.pair", "matched", table=entry.name,
                         fields=len(fields), columns=len(columns), matched=matched)
    return tally, pairs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("dgf_root")
    parser.add_argument("--verbose", action="store_true")
    parser.error = lambda message: fail(message)  # usage errors exit 3, as every script's do
    args = parser.parse_args(argv)
    if args.verbose:
        report.set_verbose()
    root = Path(args.dgf_root)
    if not (root / SAMPLES).is_dir():
        fail(f"not a DGF root: {root}")
    tally, pairs = collect(root)
    if not pairs:
        fail(f"no settings/table pair found under {root / SAMPLES}")
    fields = sum(sum(c.values()) for c in tally.values())
    print(f"PAIRS: {pairs}")
    print(f"FIELDS: {fields}")
    for (dbtype, rule), counts in sorted(tally.items()):
        total = sum(counts.values())
        (majority, n), *rest = counts.most_common()
        alternatives = "; ".join(f"{text} {c}/{total}" for text, c in rest) or "-"
        label = dbtype if dbtype else "(empty)"
        print(f"TYPE: {label} | {rule} | {majority} | {n}/{total} | {alternatives}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
