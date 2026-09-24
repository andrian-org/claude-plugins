"""json_resolve.py — which vendored JSON schema a component JSON file is read against.

Selection follows DGF's loaders and converters, read from the machine-read
tables in knowledge/json-reader.md: `component-folders` says which loader reads a
folder under FM/_COMPONENTS/, `component-classes` which class ComponentConverter
binds a `type` to, and `datasource-discriminators` which class DataSourceConverter
binds a DataSource `type` to. Outside _COMPONENTS the document's own `type`
decides; `--component-type` overrides both. Stdlib only.

Schema paths are always handled as Path objects, never spliced into a shell
command: one vendored filename contains a backtick.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import knowledge, prepass, report

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "schemas" / "json"
INDEX_SUFFIX = "Configuration.schema.json"
# DGF's SchemaIndexService allow-list: indexed although it has no Configuration infix.
INDEX_ALLOW_LIST = ("componentValidator.schema.json",)
INTERFACE = "#/definitions/IComponentConfiguration"
DATASOURCE_INTERFACE = "#/definitions/IDataSource"

_RAW = {}
_MERGED = {}


def index():
    """{lower-cased index key: filename}, exactly as SchemaIndexService builds it."""
    found = {}
    for path in sorted(SCHEMA_DIR.glob("*" + INDEX_SUFFIX)):
        found[path.name[: -len(INDEX_SUFFIX)].lower()] = path.name
    for name in INDEX_ALLOW_LIST:
        if (SCHEMA_DIR / name).is_file():
            found[name[: -len(".schema.json")].lower()] = name
    return found


def raw_schema(filename):
    if filename not in _RAW:
        _RAW[filename] = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    return _RAW[filename]


# NJsonSchema writes a generic type parameter as this placeholder.
_GENERIC_PLACEHOLDER = {"type": "object", "additionalProperties": False}
JSON_NAMES_KEY = "x-dgf-json-names"


def merged_schema(filename):
    """The vendored schema as the runtime reads it; cached per file.

    NJsonSchema inheritance is merged (prepass). A generic type parameter `T` is
    a JSON number, because the runtime closes a generic class over double. An enum
    whose members carry custom JSON names is annotated with them, from the
    `enum-member-names` table.
    """
    if filename not in _MERGED:
        merged = prepass.merge(raw_schema(filename))
        definitions = merged.get("definitions") or {}
        if definitions.get("T") == _GENERIC_PLACEHOLDER:
            definitions["T"] = {"type": "number"}
        for enum_name, names in custom_enum_names().items():
            if isinstance(definitions.get(enum_name), dict):
                definitions[enum_name][JSON_NAMES_KEY] = names
        _MERGED[filename] = merged
        report.debug("json_resolve.merged_schema", "merged", schema=filename)
    return _MERGED[filename]


def custom_enum_names():
    """{enum: {member: JSON name}} for members read by a custom name."""
    found = {}
    for row in knowledge.load("enum-member-names"):
        found.setdefault(row["Enum"], {})[row["Member"]] = row["JSON name"]
    return found


def interface_schema():
    """A root that validates against the IComponentConfiguration interface only."""
    for path in sorted(SCHEMA_DIR.glob("*" + INDEX_SUFFIX)):
        definitions = merged_schema(path.name).get("definitions") or {}
        if "IComponentConfiguration" in definitions:
            # Inlined, not a $ref: a $ref to the interface is what dispatches.
            root = dict(definitions["IComponentConfiguration"])
            root.update({"$schema": merged_schema(path.name).get("$schema"), "definitions": definitions})
            return root
    raise LookupError("no vendored schema defines IComponentConfiguration")


def component_member(value):
    """The ComponentType member `value` parses as — any case, surrounding space ignored."""
    if not isinstance(value, str):
        return None
    row = knowledge.index("component-classes", fold=True).get(value.strip().lower())
    return row["ComponentType"] if row else None


def class_for(member):
    """(schema filename or None, bound by) for a ComponentType member."""
    row = knowledge.index("component-classes")[member]
    schema = row["Configuration schema"]
    return (None if schema == knowledge.NONE else schema), row["Bound by"]


def datasource_for(value):
    """(discriminator, schema filename) for a DataSource `type`, or None when unknown."""
    if not isinstance(value, str):
        return None
    row = knowledge.index("datasource-discriminators", fold=True).get(value.strip().lower())
    return (row["Discriminator"], row["Schema"]) if row else None


@dataclass
class Selection:
    kind: str                 # "component", "datasource", "interface" or "none"
    schema: object = None     # filename, or a schema dict for "interface"
    member: object = None     # ComponentType member or DataSource discriminator
    reason: str = ""
    findings: list = field(default_factory=list)  # (code, message)

    def note(self, code, message):
        self.findings.append((code, message))


def components_path(path):
    """The parts of `path` below <workspace>/FM/_COMPONENTS, or None outside it."""
    parts = Path(path).parts
    for index_ in range(len(parts) - 1, 0, -1):
        if parts[index_] == "_COMPONENTS" and parts[index_ - 1] == "FM":
            return parts[index_ + 1:]
    return None


def _type_value(document, selection, what):
    """The discriminator value, read with the runtime's exact, case-sensitive key."""
    if not isinstance(document, dict):
        selection.note("SCHEMA_INVALID", f"a {what} must be a JSON object")
        return None
    if "type" in document:
        value = document["type"]
        if not isinstance(value, str) or not value.strip():
            selection.note("SCHEMA_INVALID", f"`type` must be a non-empty string — the runtime throws on it")
            return None
        return value
    folded = next((key for key in document if key.lower() == "type"), None)
    if folded is not None:
        selection.note("SCHEMA_INVALID", f"the discriminator is spelled `{folded}`; the runtime looks up exactly "
                                         f"`type` and throws without it")
        value = document[folded]
        return value if isinstance(value, str) else None
    return None


def _component(document, selection, folder_member=None):
    value = _type_value(document, selection, "component")
    if value is None:
        if not any(code == "SCHEMA_INVALID" for code, _ in selection.findings):
            selection.note("SCHEMA_INVALID", "the component has no `type` — the runtime throws on it")
        if folder_member is None:
            selection.kind = "none"
            return selection
        value = folder_member
    member = component_member(value)
    if member is None:
        selection.kind = "none"
        selection.note("UNKNOWN_COMPONENT", f"`type` `{value}` is not a ComponentType member — the runtime "
                                            f"drops the component without an error")
        return selection
    if folder_member is not None and member != folder_member:
        selection.note("TYPE_FOLDER_MISMATCH", f"`type` `{value}` is `{member}`, but the file sits in "
                                               f"`{folder_member}/` — it is served as a `{member}`")
    return _bind(selection, member)


def _bind(selection, member):
    schema, bound_by = class_for(member)
    selection.member = member
    if bound_by == "none":
        selection.kind, selection.schema = "interface", interface_schema()
        selection.note("NO_CONFIG_CLASS", f"`{member}` is a legal ComponentType with no configuration class — the "
                                          f"runtime drops it; checked against the component interface only")
    elif schema is None:
        selection.kind, selection.schema = "interface", interface_schema()
        selection.note("NO_SCHEMA", f"`{member}` has a configuration class but no generated schema; checked "
                                    f"against the component interface only")
    else:
        selection.kind, selection.schema = "component", schema
    report.debug("json_resolve.select", "bound", member=member, bound_by=bound_by, schema=selection.schema
                 if isinstance(selection.schema, str) else "interface")
    return selection


def _datasource(document, selection):
    value = _type_value(document, selection, "DataSource")
    if value is None:
        if not selection.findings:
            selection.note("SCHEMA_INVALID", "the DataSource has no `type` — the runtime throws on it")
        selection.kind = "none"
        return selection
    found = datasource_for(value)
    if found is None:
        selection.kind = "none"
        selection.note("UNKNOWN_DISCRIMINATOR", f"DataSource `type` `{value}` is not a DataSource kind — the runtime "
                                                f"throws `Invalid or unknown DataSourceType`")
        return selection
    selection.kind, selection.member, selection.schema = "datasource", found[0], found[1]
    return selection


def _no_schema(selection, reason):
    selection.kind, selection.reason = "none", reason
    selection.note("NO_SCHEMA", reason)
    return selection


def select(path, document, override=None):
    """Decide how `document`, read from `path`, is validated (DD6)."""
    selection = Selection(kind="none")
    if override:
        member = component_member(override)
        if member is not None:
            _type_value(document, selection, "component")
            return _bind(selection, member)
        if datasource_for(override):
            return _datasource(document, selection)
        selection.kind = "unselectable"
        selection.note("SCHEMA_UNSELECTABLE", f"--component-type `{override}` is neither a ComponentType member nor "
                                              f"a DataSource kind")
        return selection

    below = components_path(path)
    if below is None:
        return _outside_components(document, selection)
    folders = knowledge.index("component-folders")
    if len(below) == 1:
        return _no_schema(selection, "a file directly under _COMPONENTS/ is a site map: it has its own loader, "
                                     "which resolves reference components before deserializing, and no `type`")
    folder = below[0]
    rule = folders.get(folder)
    if rule is None and component_member(folder) == folder:
        rule = folders["(any other ComponentType name)"]
    if rule is None:
        return _unreferenced(selection, folder)
    report.debug("json_resolve.select", "folder", folder=folder, selection=rule["Selection"])
    if rule["Selection"] == "by-discriminator":
        return _datasource(document, selection)
    if rule["Selection"] == "fragment-by-type":
        return _component(document, selection)
    if rule["Selection"] == "by-type":
        return _component(document, selection, folder_member=folder)
    return _no_schema(selection, f"_COMPONENTS/{folder}/ is read by {rule['Loader']}, whose type has no "
                                 f"generated schema")


def _unreferenced(selection, folder):
    member = component_member(folder)
    if member is not None:
        reason = (f"_COMPONENTS/{folder}/ differs in case from the ComponentType `{member}`; on Linux no loader "
                  f"reads it")
    else:
        reason = f"_COMPONENTS/{folder}/ is read by no loader"
    return _no_schema(selection, reason)


def _outside_components(document, selection):
    value = _type_value(document, selection, "component")
    if value is None:
        selection.kind = "unselectable"
        selection.note("SCHEMA_UNSELECTABLE", "no `type`, not under FM/_COMPONENTS/, and no --component-type — "
                                              "nothing says which schema applies")
        return selection
    if component_member(value) is not None:
        return _component(document, selection)
    if datasource_for(value) is not None:
        return _datasource(document, Selection(kind="none"))
    selection.kind = "none"
    selection.note("UNKNOWN_COMPONENT", f"`type` `{value}` is neither a ComponentType member nor a DataSource "
                                        f"kind — the runtime drops or rejects it")
    return selection
