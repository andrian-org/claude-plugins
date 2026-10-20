#!/usr/bin/env python3
"""Give every schema and every schema property of an exported OpenAPI document a description.

The Schemas chapter of the specification is one table per schema, Name / Type / Description, and
the Description column comes only from the OpenAPI document. Swashbuckle fills it from `///` XML
doc comments, so it stays blank for anything compiled without them: the Core `Shared` models,
framework types such as `ProblemDetails`, and tenant DTOs nobody commented.

Describing them is a mandatory step of the document generation, run by build_package.py between
the gateway prefix and the render. The order of precedence is fixed:

1. the description the code already exports (`///`) - always wins, never overwritten;
2. the tenant's description catalogue, a reviewed and versioned JSON file in the repository:
   `src/Tenants/<T>/Swagger/schema-descriptions.json`, or
   `src/VirtualTenants/<T>/schema-descriptions.json` for a virtual tenant;
3. the same schema in another tenant's catalogue, when it has exactly the same properties - the
   entries are copied into this tenant's catalogue, so the file always holds what was used.

Anything still undescribed stops the build before a file is moved or written:
`missing-descriptions.json` lists each gap with the context needed to describe it (types, enum
members, sibling properties, the operations that return the schema, the schemas that embed it),
and whoever runs the skill writes the sentences into the catalogue and re-runs.

Catalogue format:

    {
      "PersonResponse": {
        "description": "A person registered in the National Identity Register (NIR).",
        "properties": {
          "id": "Person unique identifier.",
          "dateOfBirth": "Date of birth of the person."
        }
      }
    }

The administrator reviews the result in the rendered Word document; the catalogue is the file to
correct, never the document.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

REF = "#/components/schemas/"
STYLE = (
    "One short sentence per entry, ending with a period. Lead with the subject: "
    "'Person unique identifier.', 'Date of birth of the person.', 'Whether the permit is "
    "permanent.' Name the format or unit when the type alone does not say it (ISO 8601, "
    "ISO 3166-1 alpha-3, NRC in the form 123456/10/1). Booleans start with 'Whether'. Do not "
    "repeat the property name alone, do not list enum members (the document lists them), and "
    "never write TODO. A schema description says what one instance of the schema represents; "
    "an integer enum schema's description also maps each code to its meaning, because the "
    "export carries only the numbers (read the C# enum for the names)."
)


def catalogue_path(root: Path, tenant: str, virtual: bool) -> Path:
    if virtual:
        return root / "src" / "VirtualTenants" / tenant / "schema-descriptions.json"
    return root / "src" / "Tenants" / tenant / "Swagger" / "schema-descriptions.json"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def problem(name: str, text) -> str | None:
    """Why a description can't be used, or None when it can."""
    if not isinstance(text, str) or not text.strip():
        return "empty"
    if "TODO" in text or "__" in text:
        return "placeholder"
    if _norm(text) == _norm(name):
        return "repeats the name"
    return None


def _ref_name(node: dict) -> str | None:
    if not isinstance(node, dict):
        return None
    if isinstance(node.get("$ref"), str) and node["$ref"].startswith(REF):
        return node["$ref"][len(REF):]
    all_of = node.get("allOf")
    if isinstance(all_of, list) and len(all_of) == 1:
        return _ref_name(all_of[0])
    return None


def _reachable(node, schemas: dict, found: set[str]) -> None:
    if isinstance(node, dict):
        name = _ref_name(node) if "$ref" in node else None
        if name and name not in found:
            found.add(name)
            _reachable(schemas.get(name, {}), schemas, found)
        for k, v in node.items():
            if k != "$ref":
                _reachable(v, schemas, found)
    elif isinstance(node, list):
        for v in node:
            _reachable(v, schemas, found)


def _usage(spec: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Per schema: the operations that reach it, and the properties of other schemas that embed it."""
    schemas = spec.get("components", {}).get("schemas", {})
    used_by: dict[str, list[str]] = {}
    for path, ops in spec.get("paths", {}).items():
        for method, op in ops.items():
            if not isinstance(op, dict):
                continue
            found: set[str] = set()
            _reachable(op, schemas, found)
            label = f"{method.upper()} {path}"
            if op.get("summary"):
                label += f" - {op['summary']}"
            for name in found:
                used_by.setdefault(name, []).append(label)
    embedded_in: dict[str, list[str]] = {}
    for parent, schema in schemas.items():
        for prop, ps in (schema.get("properties") or {}).items():
            target = _ref_name(ps) or _ref_name(ps.get("items", {}) if isinstance(ps, dict) else {})
            if target:
                embedded_in.setdefault(target, []).append(f"{parent}.{prop}")
    return used_by, embedded_in


def _type_of(ps: dict) -> str:
    ref = _ref_name(ps)
    if ref:
        return ref
    if ps.get("type") == "array":
        return f"array of {_type_of(ps.get('items', {}))}"
    t = ps.get("type", "object")
    return f"{t} ({ps['format']})" if ps.get("format") else t


@dataclass
class Result:
    from_code: int = 0
    from_catalogue: int = 0
    reused: list[str] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise SystemExit(f"!! {path} must hold a JSON object keyed by schema name")
    return data


def _other_catalogues(root: Path, own: Path) -> list[tuple[str, dict]]:
    found = []
    for p in sorted([*root.glob("src/Tenants/*/Swagger/schema-descriptions.json"),
                     *root.glob("src/VirtualTenants/*/schema-descriptions.json")]):
        if p.resolve() != own.resolve():
            try:
                found.append((p.relative_to(root).as_posix(), _load(p)))
            except (ValueError, SystemExit):
                continue
    return found


def _set_description(ps: dict, text: str) -> None:
    """OpenAPI 3.0 ignores siblings of a bare $ref, so a referenced property carries its
    description the way Swashbuckle's UseAllOfToExtendReferenceSchemas does: wrapped in allOf."""
    if "$ref" in ps:
        ref = ps.pop("$ref")
        ps["allOf"] = [{"$ref": ref}]
    ps["description"] = text


def apply(spec: dict, catalogue: Path, root: Path) -> Result:
    """Fill every empty schema and property description of `spec` in place."""
    schemas = spec.get("components", {}).get("schemas", {})
    cat = _load(catalogue)
    others = _other_catalogues(root, catalogue)
    result = Result()
    used_by, embedded_in = _usage(spec)
    catalogue_changed = False

    for name, schema in schemas.items():
        props = schema.get("properties") or {}
        entry = cat.get(name) if isinstance(cat.get(name), dict) else None

        # Another tenant's description of the same model: only when the property sets match,
        # because two tenants can declare different classes under one name (ZDI and ZDA Permit).
        if entry is None:
            for source, other in others:
                candidate = other.get(name)
                if isinstance(candidate, dict) and \
                        set((candidate.get("properties") or {})) == set(props):
                    entry = json.loads(json.dumps(candidate))
                    cat[name] = entry
                    catalogue_changed = True
                    result.reused.append(f"{name} from {source}")
                    break
        entry = entry or {}
        described = entry.get("properties") or {}

        if schema.get("description"):
            result.from_code += 1
        else:
            text = entry.get("description")
            reason = problem(name, text)
            if reason is None:
                schema["description"] = text
                result.from_catalogue += 1
            else:
                result.missing.append({
                    "schema": name, "property": None,
                    "reason": "not in the catalogue" if text is None else reason,
                    "context": {
                        "properties": list(props),
                        "enum": schema.get("enum"),
                        "type": schema.get("type"),
                        "usedBy": used_by.get(name, [])[:6],
                        "embeddedIn": embedded_in.get(name, [])[:6],
                    },
                })

        for prop, ps in props.items():
            if not isinstance(ps, dict):
                continue
            if ps.get("description"):
                result.from_code += 1
                continue
            text = described.get(prop)
            reason = problem(prop, text)
            if reason is None:
                _set_description(ps, text)
                result.from_catalogue += 1
                continue
            items = ps.get("items", {}) if isinstance(ps.get("items"), dict) else {}
            result.missing.append({
                "schema": name, "property": prop,
                "reason": "not in the catalogue" if text is None else reason,
                "context": {
                    "type": _type_of(ps),
                    "nullable": bool(ps.get("nullable")),
                    "enum": ps.get("enum") or items.get("enum"),
                    "siblings": [p for p in props if p != prop],
                    "schemaDescription": schema.get("description") or entry.get("description"),
                    "usedBy": used_by.get(name, [])[:6],
                    "embeddedIn": embedded_in.get(name, [])[:6],
                },
            })

        for prop in described:
            if prop not in props:
                result.stale.append(f"{name}.{prop}")
    for name in cat:
        if name not in schemas:
            result.stale.append(name)

    if catalogue_changed:
        catalogue.parent.mkdir(parents=True, exist_ok=True)
        catalogue.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def write_missing(path: Path, result: Result, catalogue: Path, root: Path) -> None:
    try:
        shown = catalogue.relative_to(root).as_posix()
    except ValueError:
        shown = str(catalogue)
    path.write_text(json.dumps({
        "catalogue": shown,
        "style": STYLE,
        "format": {"<Schema>": {"description": "<sentence>", "properties": {"<property>": "<sentence>"}}},
        "missing": result.missing,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
