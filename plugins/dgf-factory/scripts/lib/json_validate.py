"""json_validate.py — validate a component JSON document the way the runtime reads it.

jsonschema's validator, extended with the reader semantics in
knowledge/json-reader.md (ADR 0015 §4):

- property names match case-insensitively in `properties`, `required` and
  `additionalProperties`; an unknown property is a warning, because the runtime
  skips it;
- an enum reads a member name in any case with surrounding whitespace ignored,
  or a listed integer (also written as a string); a member with a custom JSON
  name (the `enum-member-names` table) reads only that name, case-sensitively;
- a boolean accepts what `BooleanConverter` accepts: a `true`/`false` string or
  any number; nothing else is widened, because `NumberHandling` is unset;
- NJsonSchema's `oneOf` (`[{}, null]`, `[null, $ref]`, `[$ref]`) is read as the
  alternatives it means;
- an object typed `Dictionary<string, object>` (`additionalProperties: {}`) reads
  `dataSources` as DataSources and `dataSourceReferences` as strings;
- a `$ref` to IComponentConfiguration or IDataSource dispatches on the child's
  exact `type` key to the class the runtime's converter selects.

`format` is annotation-only: no format checker is passed. Requires jsonschema —
deps.require() must have run before this module is imported.
"""

import re

import jsonschema
from jsonschema import ValidationError
from jsonschema.validators import extend

from . import json_reader, json_resolve, report

DIALECTS = {
    "http://json-schema.org/draft-04/schema#": jsonschema.Draft4Validator,
    "http://json-schema.org/draft-07/schema#": jsonschema.Draft7Validator,
}
_NULL = {"type": "null"}


class DgfError(ValidationError):
    """A ValidationError that carries its finding code."""

    def __init__(self, message, code="SCHEMA_INVALID", **kwargs):
        super().__init__(message, **kwargs)
        self.dgf_code = code


class UnknownProperty(DgfError):
    def __init__(self, message, **kwargs):
        super().__init__(message, code="UNKNOWN_PROPERTY", **kwargs)


def _is_warning(error):
    return getattr(error, "dgf_code", None) in report.CODES and \
        report.CODES[error.dgf_code] in (report.EXIT_WARNINGS, report.EXIT_CLEAN)


def _match(instance, name):
    """The instance key the runtime binds to property `name`, or None."""
    if name in instance:
        return name
    folded = name.lower()
    return next((key for key in instance if key.lower() == folded), None)


# --- keyword overrides --------------------------------------------------------

_BOUND = None  # ids of objects a class schema binds, while validate() runs


def _properties(validator, properties, instance, schema):
    if not validator.is_type(instance, "object"):
        return
    if _BOUND is not None and getattr(instance, "case_duplicates", None):
        _BOUND.add(id(instance))
    for name, subschema in properties.items():
        key = _match(instance, name)
        if key is not None:
            yield from validator.descend(instance[key], subschema, path=key, schema_path=name)


def _required(validator, required, instance, schema):
    if not validator.is_type(instance, "object"):
        return
    for name in required:
        if _match(instance, name) is None:
            yield DgfError(f"required property `{name}` is missing")


def _additional_properties(validator, additional, instance, schema):
    if not validator.is_type(instance, "object"):
        return
    if additional == {}:
        yield from _dictionary(validator, instance)
        return
    known = {name.lower() for name in schema.get("properties") or {}}
    extras = [key for key in instance if key.lower() not in known]
    if additional is False:
        for key in extras:
            yield UnknownProperty(f"`{key}` is not a property here — the runtime ignores it", path=[key])
    elif isinstance(additional, dict):
        for key in extras:
            yield from validator.descend(instance[key], additional, path=key)


def _dictionary(validator, instance):
    """`Dictionary<string, object>` as DictionaryJsonConverter reads it."""
    for key, value in instance.items():
        if not key.strip():
            yield DgfError("a dictionary key is blank — the runtime throws on it", path=[key])
        elif key.lower() == "datasources":
            if not isinstance(value, dict):
                yield DgfError(f"`{key}` must be an object of DataSources", path=[key])
                continue
            for name, source in value.items():
                yield from _prefixed(_dispatch_datasource(validator, source), [key, name])
        elif key.lower() == "datasourcereferences":
            if not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
                yield DgfError(f"`{key}` must be an array of strings", path=[key])


def _prefixed(errors, segments):
    for error in errors:
        for segment in reversed(segments):
            error.path.appendleft(segment)
        yield error


_ASCII_INT = re.compile(r"-?[0-9]+")


def _as_int(value):
    """An integer, or an integer written as a string, as the enum reader takes it.

    ASCII digits with at most one leading minus only: `str.isdigit` also accepts
    superscripts such as `²`, which `int()` then rejects.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and _ASCII_INT.fullmatch(value.strip()):
        return int(value.strip())
    return None


def enum_accepts(instance, schema):
    """True when the runtime's enum reader accepts `instance` for this enum node.

    Names are read in any case with surrounding whitespace ignored; a member with
    a custom JSON name only by that name, case-sensitively (json-reader.md §1).
    An integer — or integer string — must be a listed value of an integer enum;
    a string enum lists no values, and the reader takes any integer for it.
    """
    enums = schema.get("enum") or []
    names = schema.get("x-enumNames") or []
    custom = schema.get(json_resolve.JSON_NAMES_KEY) or {}
    number = _as_int(instance)
    if number is not None and not isinstance(instance, bool):
        if "integer" in _types(schema):
            return number in enums
        if names:
            return True
    if not isinstance(instance, str):
        return any(e is instance if isinstance(instance, bool) else e == instance for e in enums)
    if custom:
        return instance in custom.values()
    folded = instance.strip().lower() if names else instance.lower()
    return any(isinstance(n, str) and n.lower() == folded for n in list(enums) + list(names))


def _enum(validator, enums, instance, schema):
    if enum_accepts(instance, schema):
        if isinstance(instance, str) and instance not in enums:
            report.debug("json_validate.enum", "read by name", value=instance)
        return
    shown = list((schema.get(json_resolve.JSON_NAMES_KEY) or {}).values()) or schema.get("x-enumNames") or enums
    yield DgfError(f"{instance!r} is not one of {shown} — the runtime cannot read it")


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _types(schema):
    declared = schema.get("type", [])
    return declared if isinstance(declared, list) else [declared]


def _bool_widened(instance):
    """What BooleanConverter reads besides true/false."""
    if isinstance(instance, str):
        return instance.strip().lower() in ("true", "false")
    return isinstance(instance, (int, float)) and not isinstance(instance, bool)


def _type(validator, types, instance, schema):
    types = types if isinstance(types, list) else [types]
    if any(validator.is_type(instance, t) for t in types):
        return
    if "enum" in schema and (schema.get("x-enumNames") or schema.get(json_resolve.JSON_NAMES_KEY)):
        return  # the enum reader decides, once, in _enum
    if "boolean" in types and _bool_widened(instance):
        report.debug("json_validate.type", "boolean widened", value=instance)
        return
    yield DgfError(f"{instance!r} is not of type {', '.join(map(str, types))}")


def _one_of(validator, branches, instance, schema):
    """NJsonSchema's oneOf means "any of these", and its null branch means nullable."""
    if any(b == {} for b in branches):
        return
    if instance is None and _NULL in branches:
        return
    live = [b for b in branches if b != _NULL]
    if len(live) == 1:
        yield from validator.descend(instance, live[0], schema_path=branches.index(live[0]))
        return
    yield from _any_of(validator, branches, instance, schema)


def _any_of(validator, branches, instance, schema):
    collected = []
    for index, branch in enumerate(branches):
        errors = list(validator.descend(instance, branch, schema_path=index))
        if all(_is_warning(e) for e in errors):
            yield from errors
            return
        collected.extend(errors)
    yield DgfError(f"{instance!r} matches none of the allowed alternatives", context=collected)


def _ref(validator, ref, instance, schema):
    if ref == json_resolve.INTERFACE:
        yield from _dispatch_component(validator, instance)
    elif ref == json_resolve.DATASOURCE_INTERFACE:
        yield from _dispatch_datasource(validator, instance)
    else:
        yield from validator._validate_reference(ref=ref, instance=instance)


def _selection_errors(selection):
    for code, message in selection.findings:
        yield DgfError(message, code=code)


_REACHED = None  # (instance, selection) per dispatched child, while components() runs


def _dispatch_component(validator, instance):
    if instance is None:
        return
    selection = json_resolve.Selection(kind="none")
    selection = json_resolve._component(instance, selection)
    if _REACHED is not None:
        _REACHED.append((instance, selection))
    yield from _selection_errors(selection)
    report.debug("json_validate.dispatch", "component", type=selection.member, kind=selection.kind,
                 schema=selection.schema if isinstance(selection.schema, str) else selection.kind)
    yield from _validate_selected(selection, instance)


def _dispatch_datasource(validator, instance):
    if instance is None:
        return
    selection = json_resolve._datasource(instance, json_resolve.Selection(kind="none"))
    yield from _selection_errors(selection)
    report.debug("json_validate.dispatch", "datasource", type=selection.member, schema=selection.schema)
    yield from _validate_selected(selection, instance)


OVERRIDES = {
    "properties": _properties,
    "required": _required,
    "additionalProperties": _additional_properties,
    "enum": _enum,
    "type": _type,
    "oneOf": _one_of,
    "anyOf": _any_of,
    "$ref": _ref,
}

_CLASSES = {}
_VALIDATORS = {}


def validator_class(schema):
    """The extended validator for the dialect `schema` declares; None if unknown."""
    dialect = schema.get("$schema") if isinstance(schema, dict) else None
    base = DIALECTS.get(dialect)
    if base is None:
        return None
    if dialect not in _CLASSES:
        _CLASSES[dialect] = extend(base, OVERRIDES)
    return _CLASSES[dialect]


def validator_for(key, schema):
    """A cached validator per selected schema — the merge and dispatch run once per class."""
    if key not in _VALIDATORS:
        cls = validator_class(schema)
        if cls is None:
            raise UnknownDialect(schema.get("$schema") if isinstance(schema, dict) else None)
        _VALIDATORS[key] = cls(schema)
    return _VALIDATORS[key]


class UnknownDialect(Exception):
    pass


def _validate_selected(selection, instance):
    if selection.kind in ("component", "datasource"):
        yield from validator_for(selection.schema, json_resolve.merged_schema(selection.schema)).iter_errors(instance)
    elif selection.kind == "interface":
        yield from validator_for("(interface)", selection.schema).iter_errors(instance)


def components(document, selection):
    """[(child, selection)] for every child the runtime reads as IComponentConfiguration.

    The walk is the validator's own, so a child is reached exactly where the
    merged schema types a member as the interface, and a child whose own `type`
    is unknown is not descended — the runtime drops it with its children. A child
    reached through two alternatives is returned once. Raises UnknownDialect.
    """
    global _REACHED
    _REACHED = []
    try:
        for _ in _validate_selected(selection, document):
            pass
        reached = _REACHED
    finally:
        _REACHED = None
    unique = {}
    for instance, child in reached:
        unique.setdefault(id(instance), (instance, child))
    return list(unique.values())


# --- findings -----------------------------------------------------------------

def json_path(path):
    out = "$"
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


def _flatten(error):
    """An any-of failure is reported through its most specific branch errors."""
    if getattr(error, "dgf_code", None) == "SCHEMA_INVALID" and error.context:
        blocking = [e for e in error.context if not _is_warning(e)]
        if blocking:
            best = max(blocking, key=lambda e: len(e.absolute_path))
            return [best] if len(best.absolute_path) > len(error.absolute_path) else [error]
    return [error]


def case_duplicates(value, path=()):
    """(json path, keys, object) for every object whose keys collide once case is ignored."""
    if isinstance(value, json_reader.JsonObject):
        if value.case_duplicates:
            yield json_path(path), value.case_duplicates, value
        for key, child in value.items():
            yield from case_duplicates(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from case_duplicates(child, path + (index,))


def _duplicate_message(path, keys):
    if len(keys) == 1:
        return f"{path}: key `{keys[0]}` appears more than once — the runtime keeps the last value"
    return (f"{path}: keys differ only in case ({', '.join(keys)}) — the runtime binds one member, so one value "
            f"silently replaces the other")


def validate(document, selection, rep):
    """Add the findings for `document`, already selected, to Report `rep`.

    Duplicate keys are reported only in objects a class schema binds. A
    dictionary (`metaData`, `events`, `propertyConverters`, …) keeps keys that
    differ in case as separate entries, so they are not a defect there.
    """
    global _BOUND
    for code, message in selection.findings:
        rep.add(code, message)
    if selection.kind not in ("component", "datasource", "interface"):
        return
    rep.ran("json-schema")
    rep.skipped("json-format", "annotation-only, ADR 0015")
    seen = set()
    _BOUND = set()
    try:
        errors = list(_validate_selected(selection, document))
        bound = _BOUND
    except UnknownDialect as exc:
        rep.add("SCHEMA_UNSELECTABLE", f"schema dialect `{exc}` is not draft-04 or draft-07")
        return
    finally:
        _BOUND = None
    for path, keys, obj in case_duplicates(document):
        if id(obj) in bound:
            rep.add("SCHEMA_INVALID", _duplicate_message(path, keys))
    for raw in errors:
        for error in _flatten(raw):
            code = getattr(error, "dgf_code", "SCHEMA_INVALID")
            where = json_path(error.absolute_path)
            if (code, where, error.message) in seen:
                continue
            seen.add((code, where, error.message))
            rep.add(code, f"{where}: {error.message}")
