"""xsd.py — the legacy XML family: grammar selection and XSD validation (DD9).

- Each vendored XSD is compiled once with lxml. `profile.xsd` does not compile
  (it declares attributes named `xmlns:xsi`), so a `Tree` document is reported
  and not validated (ADR 0015 §9).
- A root element selects its grammar. The three view grammars share the root
  `view` and are told apart by the folder the file sits in — `_views`,
  `_lookupviews` or `_gridforms`, from the `legacy-artifacts` table — or by
  `--view-kind`.
- `process.xml` is checked in two passes (ADR 0014 §1). Pass 1 is the vendored
  process.xsd. If it fails, pass 2 is an extended process.xsd built in memory
  from the `process-divergence` table. A pass-2 error blocks; a pass-1 error
  pass 2 does not repeat is a construct the runtime binds and the XSD lacks.
- Every other grammar lags the runtime, so its failures are warnings until it
  has a divergence list of its own (ADR 0016).

The vendored XSDs are never modified. Requires lxml.
"""

import copy
import re
from pathlib import Path

from lxml import etree

from . import knowledge, report

XSD_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "schemas" / "xsd"
XS = "http://www.w3.org/2001/XMLSchema"
PROCESS = "process.xsd"
VIEW_KINDS = {"table": "table-view.xsd", "lookup": "lookup-view.xsd", "grid": "grid-form.xsd"}

_COMPILED = {}
_UNCOMPILABLE = {}
_ROOTS = None
_EXTENDED = None


def _q(tag):
    return f"{{{XS}}}{tag}"


def root_of(xsd_file):
    """The first top-level xs:element's name — the grammar's root."""
    tree = etree.parse(str(XSD_DIR / xsd_file))
    element = tree.getroot().find(_q("element"))
    return element.get("name") if element is not None else None


def roots():
    """{root element name: [xsd filenames]} for every vendored XSD."""
    global _ROOTS
    if _ROOTS is None:
        _ROOTS = {}
        for path in sorted(XSD_DIR.glob("*.xsd")):
            _ROOTS.setdefault(root_of(path.name), []).append(path.name)
        report.debug("xsd.roots", "read", roots=",".join(sorted(_ROOTS)))
    return _ROOTS


def schema(xsd_file):
    """The compiled XMLSchema, or None when it does not compile (reason kept)."""
    if xsd_file in _COMPILED:
        return _COMPILED[xsd_file]
    try:
        compiled = etree.XMLSchema(etree.parse(str(XSD_DIR / xsd_file)))
    except etree.XMLSchemaParseError as exc:
        _UNCOMPILABLE[xsd_file] = str(exc).split("\n")[0]
        compiled = None
    _COMPILED[xsd_file] = compiled
    report.debug("xsd.schema", "compiled" if compiled else "not compilable", grammar=xsd_file)
    return compiled


def uncompilable_reason(xsd_file):
    schema(xsd_file)
    return _UNCOMPILABLE.get(xsd_file, "")


def enumeration(xsd_file, simple_type):
    """The xs:enumeration values of a named top-level xs:simpleType, in order."""
    tree = etree.parse(str(XSD_DIR / xsd_file))
    for declared in tree.getroot().iterfind(_q("simpleType")):
        if declared.get("name") == simple_type:
            return [e.get("value") for e in declared.iter(_q("enumeration"))]
    raise LookupError(f"{xsd_file} declares no simpleType `{simple_type}`")


def _view_folders():
    """{folder marker such as `_views`: grammar}, from the legacy-artifacts table."""
    found = {}
    for row in knowledge.load("legacy-artifacts"):
        if roots().get("view") and row["Grammar"] in roots()["view"]:
            segments = [s for s in row["Folder"].split("/") if s]
            found[segments[-2]] = row["Grammar"]
    return found


def grammar_for(root_tag, path, view_kind=None):
    """(grammar filename or None, reason when None)."""
    candidates = roots().get(root_tag)
    if not candidates:
        return None, f"root `{root_tag}` is no vendored XSD's root"
    if len(candidates) == 1:
        return candidates[0], ""
    if view_kind:
        return VIEW_KINDS[view_kind], ""
    # The kind folder is the grandparent — `_views/<view>/_view.xml` — or, for a view
    # with an empty name, the parent (knowledge/naming-conventions.md §2).
    parts = Path(path).parts
    for marker in (parts[-3] if len(parts) >= 3 else "", parts[-2] if len(parts) >= 2 else ""):
        grammar = _view_folders().get(marker)
        if grammar:
            return grammar, ""
    return None, (f"root `{root_tag}` belongs to {', '.join(candidates)}, and the file is not under "
                  f"_views/, _lookupviews/ or _gridforms/; pass --view-kind table|lookup|grid")


def _errors(compiled, tree):
    compiled.validate(tree)
    return [(e.line, e.path, e.message) for e in compiled.error_log]


def validate(tree, grammar, rep):
    """A non-process grammar: every error is XSD_LAGS_RUNTIME (ADR 0016)."""
    compiled = schema(grammar)
    rep.ran("xsd-structure")
    errors = _errors(compiled, tree)
    report.debug("xsd.validate", "validated", grammar=grammar, errors=len(errors))
    for line, _, message in errors:
        rep.add("XSD_LAGS_RUNTIME", f"{message} ({grammar} lags the runtime; advisory, ADR 0016)", line=line)
    return errors


# --- process: two passes ------------------------------------------------------

def extended_process_schema():
    """process.xsd with every process-divergence row applied, on a parsed copy."""
    global _EXTENDED
    if _EXTENDED is not None:
        return _EXTENDED
    tree = copy.deepcopy(etree.parse(str(XSD_DIR / PROCESS)))
    types = {ct.get("name"): ct for ct in tree.getroot().iter(_q("complexType")) if ct.get("name")}
    for row in knowledge.load("process-divergence"):
        owner = types.get(row["XSD owner"])
        if owner is None:
            raise knowledge.KnowledgeTableError("process-divergence", f"no complexType `{row['XSD owner']}`")
        _apply(owner, row["Construct"].split("/")[-1].lstrip("@"), row["Kind"])
    _EXTENDED = etree.XMLSchema(tree)
    report.debug("xsd.extended_process_schema", "built", rows=len(knowledge.load("process-divergence")))
    return _EXTENDED


def _apply(owner, name, kind):
    if kind == "attribute":
        attribute = etree.SubElement(owner, _q("attribute"))
        attribute.set("name", name)
        attribute.set("type", "xs:string")
        attribute.set("use", "optional")
        return
    if kind == "enum-relaxed":
        for attribute in owner.findall(_q("attribute")):
            if attribute.get("name") == name:
                attribute.set("type", "xs:string")
        return
    sequence = owner.find(_q("sequence"))
    if sequence is None:
        sequence = etree.Element(_q("sequence"))
        owner.insert(0, sequence)
    element = etree.SubElement(sequence, _q("element"))
    element.set("name", name)
    element.set("type", "xs:anyType")
    element.set("minOccurs", "0")
    element.set("maxOccurs", "unbounded")


_ATTRIBUTE = re.compile(r"attribute '([^']+)'")


def _local(segment):
    return re.sub(r"\[\d+\]$", "", segment).split(":")[-1]


def construct_of(path, message):
    """The divergence-table key an lxml error names, e.g. `State/@ftitle`."""
    segments = [s for s in (path or "").split("/") if s]
    element = _local(segments[-1]) if segments else ""
    attribute = _ATTRIBUTE.search(message)
    if attribute:
        return f"{element}/@{attribute.group(1)}"
    parent = _local(segments[-2]) if len(segments) >= 2 else ""
    return f"{parent}/{element}"


def validate_process_structure(tree, rep):
    """Two passes; returns True when the structure is usable for semantic checks."""
    rep.ran("xsd-structure")
    first = _errors(schema(PROCESS), tree)
    report.debug("xsd.validate_process_structure", "pass 1", pass1_errors=len(first))
    if not first:
        return True
    second = _errors(extended_process_schema(), tree)
    report.debug("xsd.validate_process_structure", "pass 2", pass2_errors=len(second))
    repeated = {(line, path) for line, path, _ in second}
    rows = knowledge.index("process-divergence")
    for line, path, message in first:
        if (line, path) in repeated:
            continue
        construct = construct_of(path, message)
        row = rows.get(construct)
        binding = f" (bound by `{row['Binding']}`)" if row else ""
        rep.add("XSD_RUNTIME_DIVERGENCE",
                f"`{construct}` is read by the runtime{binding} but process.xsd lacks it: {message}", line=line)
    for line, _, message in second:
        rep.add("XSD_INVALID", message, line=line)
    return not second
