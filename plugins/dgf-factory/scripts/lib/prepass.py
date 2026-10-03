"""prepass.py — merge NJsonSchema inheritance into single objects (ADR 0015 §4).

NJsonSchema models inheritance as
    "allOf": [{"$ref": "#/definitions/Base"}, {"properties": …, "additionalProperties": false}]
chained through several levels. A spec-compliant validator evaluates each branch
on its own, so the derived branch rejects every property the base declares. The
pre-pass rewrites each such `allOf` into one object: the union of `properties`
(derived overrides base), the union of `required`, and `additionalProperties:
false` when any branch set it. Any other keyword of an inline branch is kept.

An `allOf` with no local `$ref` is not inheritance and is left as it is. `$ref`
chains resolve transitively; a cycle is left unmerged and traced. The input is
never mutated. Stdlib only.
"""

import copy

from . import report

_MERGED_KEYS = ("properties", "required", "additionalProperties", "allOf", "$ref")


def _pointer(ref):
    """The path segments of a local JSON pointer, or None for anything else."""
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    return [part.replace("~1", "/").replace("~0", "~") for part in ref[2:].split("/")]


def _resolve(root, ref):
    node = root
    for part in _pointer(ref) or []:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def is_inheritance(all_of, root):
    """True when `all_of` is NJsonSchema inheritance: a local `$ref` to an object schema."""
    if not isinstance(all_of, list):
        return False
    refs = [b for b in all_of if isinstance(b, dict) and _pointer(b.get("$ref")) is not None]
    return bool(refs) and all(isinstance(_resolve(root, b["$ref"]), dict) for b in refs)


def count_inheritance(node, root=None):
    """How many inheritance `allOf`s remain anywhere under `node`."""
    root = node if root is None else root
    if isinstance(node, list):
        return sum(count_inheritance(item, root) for item in node)
    if not isinstance(node, dict):
        return 0
    own = 1 if is_inheritance(node.get("allOf"), root) else 0
    return own + sum(count_inheritance(value, root) for value in node.values())


class _Merger:
    def __init__(self, original):
        self.original = original
        self.memo = {}      # ref -> merged target
        self.merged = 0
        self.cycles = 0

    def target(self, ref, stack):
        if ref in self.memo:
            return self.memo[ref]
        if ref in stack:
            self.cycles += 1
            report.debug("prepass.merge", "cycle skipped", ref=ref)
            return None
        node = _resolve(self.original, ref)
        if not isinstance(node, dict):
            return None
        result = self.walk(node, stack | {ref})
        self.memo[ref] = result
        return result

    def walk(self, node, stack=frozenset()):
        if isinstance(node, list):
            return [self.walk(item, stack) for item in node]
        if not isinstance(node, dict):
            return copy.deepcopy(node)
        walked = {key: self.walk(value, stack) for key, value in node.items()}
        if not is_inheritance(node.get("allOf"), self.original):
            return walked
        folded = self.fold(walked, node["allOf"], stack)
        return walked if folded is None else folded

    def fold(self, walked, branches, stack):
        """One object from an inheritance allOf, or None when a base cannot be resolved."""
        result = {key: value for key, value in walked.items() if key != "allOf"}
        properties, required, closed = {}, [], False
        for index, branch in enumerate(branches):
            if isinstance(branch, dict) and _pointer(branch.get("$ref")) is not None:
                source = self.target(branch["$ref"], stack)
                if source is None:
                    return None
            else:
                source = walked["allOf"][index]
                for key, value in source.items():
                    if key not in _MERGED_KEYS:
                        result[key] = value
            properties.update(copy.deepcopy(source.get("properties") or {}))
            for name in source.get("required") or []:
                if name not in required:
                    required.append(name)
            closed = closed or source.get("additionalProperties") is False
        result["properties"] = properties
        if required:
            result["required"] = required
        if closed:
            result["additionalProperties"] = False
        self.merged += 1
        return result


def merge(schema):
    """A deep copy of `schema` with every NJsonSchema inheritance allOf merged."""
    merger = _Merger(schema)
    result = merger.walk(schema)
    report.debug("prepass.merge", "merged", schema=schema.get("title", "?") if isinstance(schema, dict) else "?",
                 merged_allof=merger.merged, props=len(result.get("properties") or {}) if isinstance(result, dict) else 0,
                 cycles=merger.cycles)
    return result
