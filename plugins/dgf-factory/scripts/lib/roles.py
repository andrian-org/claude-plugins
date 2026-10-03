"""roles.py — every role name a workspaces root uses, and where (ADR 0027 §6, DD9).

Nothing in a root declares a role: roles are database rows
(knowledge/permissions.md §1). So this is an inventory, not a check. It reads
the role-sources table (permissions.md §2) and, for each row, every file its
`File` pattern matches in every workspace (`*` within one name, exact case):

  an XML file     every `Element` at any depth, its `Attribute`, split on
                  `Separator` when there is one;
  a JSON file     every list at the key path `Element`, at any depth, and each
                  item's `Attribute`;
  (folder)        the name of the folder that holds the file.

A value is split exactly as the runtime splits it — on `,`, with no trimming —
so ` B` in `roles="A, B"` is listed as ` B`, the name the runtime tests. An
empty value names no role. A file that does not parse is skipped with a trace:
the validators report malformed files. Stdlib only.
"""

import fnmatch
import json
from xml.parsers import expat
from pathlib import Path

from . import knowledge, report, workspace

FOLDER = "(folder)"


def _matches(root, ws, pattern):
    """Files under `root/ws` matching `pattern`: `*` matches within one name, and every name matches exactly."""
    current = [Path(root) / ws]
    for segment in pattern.split("/"):
        found = []
        for base in current:
            if "*" in segment:
                try:
                    found += sorted(p for p in base.iterdir()
                                    if not p.name.startswith(".") and fnmatch.fnmatchcase(p.name, segment))
                except OSError:
                    continue
            elif workspace.exact_child(base, segment)[0] == workspace.OK:
                found.append(base / segment)
        current = found
    return [path for path in current if path.is_file()]


def _split(value, separator):
    if value is None or value == "":
        return []
    return value.split(separator) if separator != knowledge.NONE else [value]


def _xml_values(path, element, attribute, separator):
    """(name, line) for every `element` at any depth — read with expat, which knows each element's line."""
    found = []
    parser = expat.ParserCreate()

    def start(tag, attributes):
        if tag == element:
            for name in _split(attributes.get(attribute), separator):
                found.append((name, parser.CurrentLineNumber))

    parser.StartElementHandler = start
    try:
        parser.Parse(Path(path).read_bytes(), True)
    except (expat.ExpatError, OSError, RecursionError) as exc:
        report.debug("roles.inventory", "unparsable", file=path, error=str(exc).splitlines()[0])
        return []
    return found


def _json_lists(value, keys):
    """Every list found at the dotted key path `keys`, at any depth of `value`."""
    found = []
    if isinstance(value, dict):
        node = value
        for key in keys:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, list):
            found.append(node)
        for child in value.values():
            found += _json_lists(child, keys)
    elif isinstance(value, list):
        for child in value:
            found += _json_lists(child, keys)
    return found


def _json_values(path, element, attribute):
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError) as exc:
        report.debug("roles.inventory", "unparsable", file=path, error=str(exc).splitlines()[0])
        return []
    found = []
    for items in _json_lists(document, element.split(".")):
        for item in items:
            name = item.get(attribute) if isinstance(item, dict) else None
            if isinstance(name, str) and name:
                found.append((name, None))
    return found


def _values(path, row):
    if row["Element"] == FOLDER:
        return [(path.parent.name, None)]
    if path.suffix == ".json":
        return _json_values(path, row["Element"], row["Attribute"])
    return _xml_values(path, row["Element"], row["Attribute"], row["Separator"])


def inventory(root):
    """{role name: {source: [(root-relative file, line)]}} over every workspace under `root`."""
    root = Path(root)
    found = {}
    for row in knowledge.load("role-sources"):
        for ws in sorted(workspace.workspace_names(root)):
            for path in _matches(root, ws, row["File"]):
                rel = path.relative_to(root).as_posix()
                for name, line in _values(path, row):
                    found.setdefault(name, {}).setdefault(row["Source"], []).append((rel, line))
                report.debug("roles.inventory", "read", source=row["Source"], file=rel)
    report.debug("roles.inventory", "done", roles=len(found))
    return found
