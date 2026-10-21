"""parity.py — a schema pass is not runtime support (DD7, ADR 0011).

The gate reads the `parity` table in knowledge/schema-families.md §6, the shipped
copy of DGF's format-coverage page. It applies to a JSON document's top-level
component — the file the runtime loads — never to nested children, whose
legality is checked but whose row describes a different file. XML artifacts are
what the runtime reads, so they raise no parity finding. Stdlib only.
"""

from . import knowledge, report

NOT_RUNTIME = "✗"
PARTIAL = "◐"


def row_for(member=None, schema=None):
    """The parity row for a ComponentType member, or for a DataSource schema file."""
    for row in knowledge.load("parity"):
        if member is not None and row["ComponentType"] == member:
            return row
        if member is None and schema is not None and row["Schema"] == schema:
            return row
    return None


def check(selection, rep):
    """Add the parity finding for a selected JSON document."""
    if selection.kind == "component" or selection.kind == "interface":
        row = row_for(member=selection.member)
    elif selection.kind == "datasource":
        row = row_for(schema=selection.schema)
    else:
        return
    rep.ran("runtime-parity")
    report.debug("parity.check", "row", member=selection.member, parity_row=row["#"] if row else "none")
    if row is None:
        rep.add("NO_PARITY_ROW", f"`{selection.member}` has no row in the parity table — nothing states whether "
                                 f"the runtime reads it as JSON")
        return
    name = row["Row"]
    if row["Runtime"] == NOT_RUNTIME:
        rep.add("PARITY_NOT_RUNTIME", f"schema-valid but not runtime-supported: the runtime does not read `{name}` "
                                      f"from JSON (parity row {row['#']}): {row['XML-only part']}")
    elif row["Runtime"] == PARTIAL:
        rep.add("PARITY_PARTIAL", f"`{name}` is read from JSON only in part (parity row {row['#']}): "
                                  f"{row['XML-only part']}")
