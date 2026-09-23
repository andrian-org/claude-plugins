"""
Generic OpenAPI (swagger.json) -> DOCX renderer.

Walks a parsed OpenAPI 3.x document — info.description, paths, components.schemas — into the
skill's reusable Word template (templates/api-specification-template.docx). No tenant-specific
content is hardcoded here; everything the document says comes from the OpenAPI file itself
(which in turn is fed by XML doc comments, .WithSummary()/.WithDescription(), and
OpenApiInfo.Description in the tenant's own Program.cs — see references/openapi-annotations.md).

Usage:
    python openapi_to_docx.py <swagger.json> <output.docx>
        --tenant APIS --role Provider --version 1.0
        [--author "Name"] [--date "August 3, 2026"] [--route apis]

Requires Microsoft Word (via COM automation) on the machine running this, to repaginate the
Table of Contents with real page numbers. Falls back to an estimated TOC if Word is unavailable.
"""
import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import date

import docx
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from docx.table import Table
from docx.text.paragraph import Paragraph

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(SCRIPT_DIR, "..", "templates", "api-specification-template.docx")
# The signing block, lifted verbatim from the published WCF (t) specification. WordprocessingML
# body elements only, with no relationships, so it splices into any render of the template.
SIGNATURE_BLOCK = os.path.join(SCRIPT_DIR, "..", "templates", "contacts-and-signature.xml")

# Shared with apply_gateway_route.py, which writes the same URLs into the document's `servers`.
from environments import ENVIRONMENTS


# =============================================================================== low-level helpers
# Proven machinery (table borders/shading/padding, numbered-heading bookmarks, internal/external
# hyperlinks, TOC rebuild, Word-COM repagination) — unchanged from this skill's origin, the
# hand-built APIS spec generator. Only the input side (below, "OPENAPI WALKERS") is new.

def el(tag, **attrs):
    from docx.oxml import OxmlElement
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(k), v)
    return e


def set_para_text(p, text):
    runs = p.runs
    if not runs:
        p.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        r._element.getparent().remove(r._element)


TOKEN = re.compile(r"(\[\[[^\]]+\]\]|<https?://[^>]+>|\*\*.+?\*\*|`.+?`|\*.+?\*)")


def _link_run(text, bold=False):
    r = el("w:r")
    rPr = el("w:rPr")
    rPr.append(el("w:rStyle", **{"w:val": "Hyperlink"}))
    if bold:
        rPr.append(el("w:b"))
    r.append(rPr)
    t = el("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    return r


def add_internal_link(paragraph, name):
    hl = el("w:hyperlink", **{"w:anchor": f"_{name}"})
    hl.append(_link_run(name, bold=True))
    paragraph._p.append(hl)


def add_external_link(paragraph, url):
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hl = el("w:hyperlink", **{"r:id": r_id})
    hl.append(_link_run(url))
    paragraph._p.append(hl)


def add_rich(paragraph, text):
    """Inline markup: **bold**, *italic*, `code`, [[SchemaRef]], <https://external>."""
    for part in TOKEN.split(text):
        if not part:
            continue
        if part.startswith("[[") and part.endswith("]]"):
            add_internal_link(paragraph, part[2:-2])
        elif part.startswith("<http") and part.endswith(">"):
            add_external_link(paragraph, part[1:-1])
        elif part.startswith("**") and part.endswith("**"):
            paragraph.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = paragraph.add_run(part[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9)
        elif len(part) >= 3 and part.startswith("*") and part.endswith("*"):
            paragraph.add_run(part[1:-1]).italic = True
        else:
            paragraph.add_run(part)


# =============================================================================== doc_ops
# A flat list of (kind, ...) tuples the BUILD section below turns into real Word content. Both
# the markdown parser and the OpenAPI walkers only ever produce these five kinds.

doc_ops = []


def heading(level, text):
    doc_ops.append(("heading", level, text))


def para(text=""):
    if text:
        doc_ops.append(("para", text))


def bullets(items):
    if items:
        doc_ops.append(("bullets", items))


def table(rows, widths=None):
    doc_ops.append(("table", rows, widths))


def code(text):
    doc_ops.append(("code", text))


def note(text):
    doc_ops.append(("note", text))


def raw(xml):
    doc_ops.append(("raw", xml))


# =============================================================================== markdown parser
# Renders OpenAPI info.description / operation.description — arbitrary markdown written once in
# the tenant's C# code (OpenApiInfo.Description, .WithDescription()) — into doc_ops. This is what
# lets narrative content (submission rules, a protocol primer, worked examples) live in the code
# as ordinary markdown rather than needing a bespoke Python content block per tenant.

def normalize_description(text):
    """Collapses the CRLF + comment-indentation whitespace XML doc comments leave behind, while
    preserving intentional blank-line paragraph breaks AND the line-by-line structure of markdown
    block constructs (tables, code fences, headings, bullet lists) that parse_markdown depends on
    one line at a time. Joining every line in a block into one space-separated string (the naive
    approach) silently destroys any table or code fence not separated from surrounding prose by a
    blank line: a table's row-per-line structure collapses into a single line with every pipe
    still in it, which parse_markdown then reads back as one row with as many columns as there
    were cells in the whole table - and a code fence's closing ``` ends up buried mid-line instead
    of on its own line, so the fence scanner never finds it and swallows everything up to the next
    accidental ``` it can find. Only genuine soft-wrapped prose lines get joined; everything else
    passes through one line at a time. Code fence content additionally keeps its original
    (non-stripped) indentation, since pretty-printed JSON examples rely on it for readability.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    out_lines = []
    prose_buf = []
    in_code_fence = False

    def flush_prose():
        if prose_buf:
            out_lines.append(" ".join(prose_buf))
            prose_buf.clear()

    for raw_line in text.split("\n"):
        stripped = raw_line.strip()

        if in_code_fence:
            out_lines.append(raw_line.rstrip())
            if stripped.startswith("```"):
                in_code_fence = False
            continue

        if not stripped:
            flush_prose()
            out_lines.append("")
            continue

        if stripped.startswith("```"):
            flush_prose()
            out_lines.append(stripped)
            in_code_fence = True
            continue

        if stripped.startswith("|") or re.match(r"^#{2,3}\s", stripped) \
                or stripped.startswith("- ") or stripped.startswith("* "):
            flush_prose()
            out_lines.append(stripped)
            continue

        prose_buf.append(stripped)

    flush_prose()

    # Collapse runs of consecutive blank lines to one, matching the old blank-line-run-as-single-
    # paragraph-gap behavior that parse_markdown's own blank-line handling expects.
    collapsed = []
    prev_blank = False
    for line in out_lines:
        if line == "":
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        collapsed.append(line)

    return "\n".join(collapsed).strip("\n")


def parse_markdown(text):
    """Parses a CommonMark subset (##/### headings, tables, bullet lists, code fences, paragraphs) into doc_ops tuples."""
    ops = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i, n = 0, len(lines)
    para_buf = []

    def flush_para():
        if para_buf:
            ops.append(("para", " ".join(l.strip() for l in para_buf if l.strip())))
            para_buf.clear()

    while i < n:
        stripped = lines[i].strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        m = re.match(r"^(#{2,3})\s+(.*)", stripped)
        if m:
            flush_para()
            ops.append(("heading", len(m.group(1)), m.group(2).strip()))
            i += 1
            continue

        if stripped.startswith("```"):
            flush_para()
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            ops.append(("code", "\n".join(code_lines)))
            continue

        if stripped.startswith("|"):
            flush_para()
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            rows = []
            for tl in table_lines:
                if re.fullmatch(r"\|[\s\-:|]+\|", tl):
                    continue
                rows.append([c.strip() for c in tl.strip("|").split("|")])
            if rows:
                ops.append(("table", rows, None))
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_para()
            items = []
            while i < n and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                items.append(lines[i].strip()[2:].strip())
                i += 1
            ops.append(("bullets", items))
            continue

        para_buf.append(lines[i])
        i += 1

    flush_para()

    # A description commonly opens with un-headed prose (the "what is this API" paragraph)
    # before its first real heading; give that leading prose an Executive Summary heading so
    # it does not render headless directly under the Document History table.
    if ops and ops[0][0] != "heading":
        ops.insert(0, ("heading", 2, "Executive Summary"))

    return ops


def executive_summary_only(ops):
    """Keeps the first section of info.description and drops every later Heading 2.

    A tenant's Description often continues past the summary into submission models, message
    primers and error catalogues. Those render as further numbered top-level sections, which
    puts reference material ahead of the Endpoints section and duplicates what the endpoint and
    schema tables already state. The specification carries the Executive Summary only, under
    that heading whatever the Description titled its opening section. Level-3 headings inside
    it become bold lead-ins, so the summary adds no TOC entries.
    """
    kept = [("heading", 2, "Executive Summary")]
    for i, op in enumerate(ops):
        if op[0] == "heading":
            if i == 0:
                continue
            if op[1] == 2:
                break
            kept.append(("para", f"**{op[2]}**"))
            continue
        kept.append(op)
    return kept if len(kept) > 1 else []


# =============================================================================== OpenAPI walkers

def render_type(schema, components):
    if not schema:
        return "-"
    if "$ref" in schema:
        return f"[[{schema['$ref'].rsplit('/', 1)[-1]}]]"
    # Swashbuckle's UseAllOfToExtendReferenceSchemas wraps a referenced property in a
    # single-element `allOf` so it can carry a sibling description, which OpenAPI 3.0 forbids
    # next to a bare `$ref`. Unwrap it, or the property's type renders as a bare "object" and
    # loses its cross-reference link.
    all_of = schema.get("allOf")
    if all_of and len(all_of) == 1:
        return render_type(all_of[0], components)
    t = schema.get("type")
    if t == "array":
        return f"array of {render_type(schema.get('items', {}), components)}"
    fmt = schema.get("format")
    if t == "string" and fmt in ("date-time", "date"):
        return fmt
    return t or "object"


NAME_HDR = ["**Name**", "**Type**", "**Description**"]
# Short header labels on purpose: the table is fixed-layout (tblLayout type="fixed", needed for
# consistent rendering elsewhere in the doc), so a column never grows to fit a wrapping header -
# "Parameter Type"/"Status Code" wrapped to two lines in their columns. "In" matches the OpenAPI
# spec's own term for a parameter's location (query/path/header/body) and is short enough to
# never wrap regardless of column width.
PARAM_HDR = ["**In**", "**Name**", "**Type**", "**Description**"]
RESP_HDR = ["**Status**", "**Content-Type**", "**Type**", "**Description**"]


def scrub_package(path, doc_title):
    """Strip everything the template carried in that must not reach a third party.

    `docProps/core.xml` travels with the file and is visible to whoever receives it; the
    template inherits a previous author in `dc:creator` and a different person in
    `cp:lastModifiedBy`, and Word's own Save() during repagination re-stamps the latter.
    `word/webSettings.xml` carries ~1.1 MB of leftover `divsChild` data from an HTML paste into
    the template's ancestor - larger than the rest of the document combined.
    """
    with zipfile.ZipFile(path) as zf:
        parts = {n: zf.read(n) for n in zf.namelist()}

    core = parts["docProps/core.xml"].decode("utf-8")
    for tag, value in (("dc:title", doc_title),
                       ("dc:subject", "API Specification"),
                       ("dc:creator", "dotGov Solutions LLC"),
                       ("cp:lastModifiedBy", "")):
        # An empty value is written self-closing: "<cp:lastModifiedBy></cp:lastModifiedBy>" reads
        # as populated to anything scanning for a non-whitespace character after the open tag.
        replacement = f"<{tag}>{value}</{tag}>" if value else f"<{tag}/>"
        core = re.sub(rf"<{tag}>.*?</{tag}>|<{tag}/>", replacement, core, flags=re.S)
    parts["docProps/core.xml"] = core.encode("utf-8")

    web = parts["word/webSettings.xml"].decode("utf-8")
    parts["word/webSettings.xml"] = re.sub(r"<w:divs>.*?</w:divs>", "", web, flags=re.S).encode("utf-8")

    # The template's own Document History table carries direct formatting but names no style,
    # so it reads as unstyled next to the generated ones. Styles are inherited, not applied, so
    # naming it changes nothing on the page.
    doc = parts["word/document.xml"].decode("utf-8")
    doc = re.sub(r"<w:tblPr>(?!<w:tblStyle)",
                 '<w:tblPr><w:tblStyle w:val="TableGrid"/>', doc)
    parts["word/document.xml"] = doc.encode("utf-8")

    parts = {n: d for n, d in parts.items() if not n.startswith("[trash]")}

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)


# The document's chapters, in order. Nothing else is rendered at Heading 2.
CHAPTERS = ("Executive Summary", "Glossary", "Endpoints", "Schemas", "API Environments",
            "Contacts and Signature")

# Definitions for the acronyms that recur across ZamConnect tenants. A term is listed in a
# document's Glossary only when it actually appears in that document's text; an acronym not in
# this table is left out rather than given an invented expansion.
GLOSSARY = {
    "BRN": "Business Registration Number",
    "DEV": "Development environment",
    "DOC": "Department of Cooperatives",
    "JSON": "JavaScript Object Notation",
    "NAIR": "National Academic Information Register",
    "NAPSA": "National Pension Scheme Authority",
    "NBR": "National Business Register",
    "NIR": "National Identity Register",
    "NLR": "National Land Register",
    "NRC": "National Registration Card",
    "PACRA": "Patents and Companies Registration Agency",
    "PRD": "Production environment",
    "REST": "Representational State Transfer",
    "SRS": "Societies Registration System",
    "STG": "Staging environment",
    "TPIN": "Taxpayer Identification Number",
    "URL": "Uniform Resource Locator",
    "ZDA": "Zambia Development Agency",
    "ZDI": "Zambia Department of Immigration",
    "ZRA": "Zambia Revenue Authority",
}


def build_glossary(tenant, title, openapi):
    text = " ".join([json.dumps(openapi), str(doc_ops), str(ENVIRONMENTS)])
    rows = [["**Term**", "**Definition**"],
            ["API", "Application Programming Interface"],
            ["ZamConnect", "The Government Service Bus of Zambia: the secured gateway through "
                           "which this API is published"],
            [tenant, title]]
    rows += [[term, meaning] for term, meaning in sorted(GLOSSARY.items())
             if term != tenant and re.search(rf"\b{term}\b", text)]
    heading(2, "Glossary")
    table(rows, widths=[1.5, 5.0])


def build_endpoints(openapi, route_prefix, sections=None, only=None):
    """Render the endpoint reference under the single Endpoints chapter.

    `sections` maps an OpenAPI path to "Consume" or "Provide" - the OpenAPI document itself
    carries no such marker, because the split is read from the client each module injects and
    nothing in the HTTP surface reflects it. `only` keeps that section's endpoints, which is what
    makes the (c) and (p) documents projections of the (t) one rather than separate renders. The
    split decides which endpoints a document carries, never its chapter structure.
    """
    paths = openapi.get("paths", {})
    if paths and all(p.startswith("/t/") for p in paths):
        address_note = ("Each endpoint address below is the full gateway path, including the "
                        "tenant's route. The complete Endpoint URL is the environment Base URL "
                        "given in the API Environments section followed by this address.")
    else:
        address_note = (f"All endpoint addresses below are relative to the environment Base URL "
                        f"given in the API Environments section. Paths are shown relative to the "
                        f"gateway route `/t/{route_prefix}`.")

    path_list = list(paths)
    if sections:
        # Consume before Provide, so the (t) document reads in the same order as (c) then (p).
        path_list.sort(key=lambda p: sections.get(p) != "Consume")
        if only:
            path_list = [p for p in path_list if sections.get(p) == only]
            if not path_list:
                sys.exit(f"!! --only-section {only} leaves no endpoints; skip this role instead "
                         f"of shipping a document with an empty section")

    heading(2, "Endpoints")
    para(address_note)
    _build_operations(openapi, path_list, openapi.get("components", {}))


def _build_operations(openapi, path_list, components):
    paths = openapi.get("paths", {})
    for path in path_list:
        methods = paths[path]
        for method, op in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue

            heading(3, f"{method.upper()} {path}")

            summary = op.get("summary")
            if summary:
                para(summary)
            description = normalize_description(op.get("description", ""))
            if description:
                for sub_op in parse_markdown(description):
                    if sub_op[0] == "heading":
                        # A heading inside an operation's description would open a chapter or
                        # an entry of its own in the TOC; it stays prose under this endpoint.
                        if sub_op[2] != "Executive Summary":
                            para(f"**{sub_op[2]}**")
                        continue
                    doc_ops.append(sub_op)

            param_rows = [PARAM_HDR]
            for p in op.get("parameters", []):
                param_rows.append([
                    p.get("in", "-").capitalize(), p.get("name", "-"),
                    render_type(p.get("schema", {}), components),
                    normalize_description(p.get("description", "")),
                ])
            request_body = op.get("requestBody")
            if request_body:
                content = request_body.get("content", {})
                content_types = " / ".join(f"`{ct}`" for ct in content)
                first_schema = next(iter(content.values()), {}).get("schema", {})
                param_rows.append(["Body", "-", render_type(first_schema, components),
                                  f"Content-Type: {content_types}" if content_types else ""])
            if len(param_rows) > 1:
                para("**Input parameters:**")
                table(param_rows, widths=[0.7, 1.2, 1.2, 3.4])

            responses = op.get("responses", {})
            if responses:
                para("**Response:**")
                resp_rows = [RESP_HDR]
                for status_code in sorted(responses, key=lambda c: (len(c), c)):
                    r = responses[status_code]
                    content = r.get("content", {})
                    # Problem responses (.ProducesProblem) use "application/problem+json", not
                    # "application/json" - pick whichever content type is actually present rather
                    # than assuming JSON, so the real content type and schema both show up instead
                    # of silently falling back to "-".
                    content_type, media = next(iter(content.items()), (None, {}))
                    schema = media.get("schema")
                    resp_rows.append([
                        status_code,
                        content_type or "-",
                        render_type(schema, components) if schema else "-",
                        normalize_description(r.get("description", "")),
                    ])
                table(resp_rows, widths=[0.9, 1.6, 1.5, 2.5])


def reachable_schemas(openapi, path_list):
    """Schema names reachable from the given operations, transitively.

    Used to scope the Schemas section to the endpoints a document actually contains, so a
    Provider document does not define the response types only its Consumer counterpart returns.
    """
    schemas = openapi.get("components", {}).get("schemas", {})
    paths = openapi.get("paths", {})
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[-1]
                if name not in found:
                    found.add(name)
                    walk(schemas.get(name, {}))
            for k, v in node.items():
                if k != "$ref":
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for p in path_list:
        walk(paths.get(p, {}))
    return found


def build_schemas(openapi, keep=None):
    schemas = openapi.get("components", {}).get("schemas", {})
    if keep is not None:
        schemas = {n: s for n, s in schemas.items() if n in keep}
    if not schemas:
        return
    # The error envelope leads, since every endpoint's failure responses point at it; the
    # remaining schemas follow alphabetically.
    schemas = dict(sorted(schemas.items(), key=lambda kv: (kv[0] != "ProblemDetails", kv[0].lower())))
    components = openapi.get("components", {})

    heading(2, "Schemas")
    para("Each schema defines the data model for the resources and includes details about the "
         "attributes, data types, and relationships between entities. The sections below "
         "describe the key schemas.")
    para("All JSON property names use camelCase. Properties with no value are omitted from "
         "responses rather than serialised as null.")

    for name, schema in schemas.items():
        heading(3, name)
        description = normalize_description(schema.get("description", ""))
        if description:
            para(description)

        properties = schema.get("properties", {})
        if not properties:
            continue
        rows = [NAME_HDR]
        for prop_name, prop_schema in properties.items():
            rows.append([
                prop_name,
                render_type(prop_schema, components),
                normalize_description(prop_schema.get("description", "")),
            ])
        table(rows, widths=[2.0, 1.6, 2.9])

        # A tenant that returns problem details has to say which ones it can actually emit -
        # the envelope alone tells a consumer nothing about the errors to branch on. The list
        # comes from the tenant's own Error definitions via an x-problem-definitions extension
        # on the schema, so an error code can never be invented here.
        definitions = schema.get("x-problem-definitions")
        if definitions:
            heading(3, f"{name}Definitions")
            para("Every problem this API can return, and the title each is reported under. "
                 "Branch on the title, not on the detail, which names the rejected value and "
                 "therefore differs per occurrence.")
            rows = [["**Title**", "**Status**", "**Detail**", "**Source**"]]
            for d in definitions:
                rows.append([d.get("title", ""), str(d.get("status", "")),
                             d.get("detail", ""), d.get("source", "")])
            table(rows, widths=[1.7, 0.7, 3.2, 0.9])


def build_environments():
    heading(2, "API Environments")
    for name, _, description, url in ENVIRONMENTS:
        heading(3, name)
        for line in description.split("\n\n"):
            para(line)
        para(f"**Base URL:** <{url}>")


def build_contacts():
    """The signing block, left deliberately empty.

    It is filled in at signing. Rendering named individuals and their contact details here
    would put them into a document going to a third party, on every re-render.
    """
    heading(2, "Contacts and Signature")
    with open(SIGNATURE_BLOCK, encoding="utf-8") as fh:
        raw(fh.read())


def patch_numpages_field(docx_path, page_count):
    """Overwrite the footer's cached NUMPAGES result text with a known-good value.

    Word's own live recalculation of NUMPAGES was observed to be unreliable under headless COM
    automation (the same unchanged document reported 32, then 3, across successive Update/Save
    cycles) - almost certainly print-metrics-dependent pagination jitter with no visible window.
    ComputeStatistics(2), read once right after TOC repagination stabilizes, was consistent, so
    that value is written in directly rather than trusting a further field recalculation pass.
    """
    with zipfile.ZipFile(docx_path) as zf:
        parts = {n: zf.read(n) for n in zf.namelist()}

    pattern = re.compile(
        r'(<w:instrText[^>]*>\s*NUMPAGES\b.*?</w:instrText>.*?'
        r'<w:fldChar w:fldCharType="separate"\s*/>.*?<w:t[^>]*>)([^<]*)(</w:t>)', re.S)

    changed = False
    for name, data in parts.items():
        if not name.startswith(("word/footer", "word/header")):
            continue
        text = data.decode("utf-8")
        new_text, subs = pattern.subn(lambda m: m.group(1) + str(page_count) + m.group(3), text)
        if subs:
            parts[name] = new_text.encode("utf-8")
            changed = True

    if not changed:
        return

    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)


# =============================================================================== BUILD

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("openapi_json")
    parser.add_argument("output_docx")
    parser.add_argument("--tenant", required=True, help="Short tenant code, e.g. APIS")
    # "Both" is spelled "Tenant" everywhere the deliverable is filed - the `(t)` marker in the
    # filename, the Tenant folder, the cover and the running header - so it is the role word
    # written into the document; "Both" stays accepted as the older spelling of the same thing.
    parser.add_argument("--role", required=True, choices=["Provider", "Consumer", "Both", "Tenant"])
    parser.add_argument("--version", required=True)
    parser.add_argument("--author", default="")
    parser.add_argument("--date", default=date.today().strftime("%B %-d, %Y") if os.name != "nt"
                        else date.today().strftime("%B %d, %Y").replace(" 0", " "))
    parser.add_argument("--route", default=None, help="Gateway route prefix, default: tenant lowercased")
    parser.add_argument("--sections", default=None,
                        help="JSON file mapping each OpenAPI path to 'Consume' or 'Provide'. The "
                             "OpenAPI document carries no such marker - the split is read from "
                             "the client each module injects - so it is supplied here")
    parser.add_argument("--only-section", default=None, choices=["Consume", "Provide"],
                        help="Render only this section, making the (c)/(p) document a projection "
                             "of the (t) one. Requires --sections")
    parser.add_argument("--history-description", default="Originally drafted")
    args = parser.parse_args()

    route_prefix = args.route or args.tenant.lower()

    import json
    with open(args.openapi_json, encoding="utf-8") as f:
        openapi = json.load(f)

    info = openapi.get("info", {})
    # Prescribed convention (see SKILL.md prerequisites): info.title = "{full descriptive name}
    # ({TENANT})", e.g. "Advance Passenger Information System (APIS)" - the cover page shows the
    # tenant code and role separately as "({{TENANT}})"/"({{ROLE}})", so only the full name is
    # needed here. Tenants that haven't adopted that convention yet fall back gracefully: the
    # older "{TENANT} - {name}" dash format, or (like ZIMS's current "ZIMS (Consumer)") a bare
    # tenant-code prefix - rather than duplicating "(role)" on the cover page, which unprefixed
    # raw titles did before this fallback chain existed.
    if args.role == "Both":
        args.role = "Tenant"

    raw_title = info.get("title", args.tenant)
    tenant_suffix = re.search(rf"\(\s*{re.escape(args.tenant)}\s*\)\s*$", raw_title, re.IGNORECASE)
    if tenant_suffix:
        title = raw_title[:tenant_suffix.start()].strip()
    elif " - " in raw_title:
        title = raw_title.split(" - ", 1)[1]
    else:
        tenant_prefix = re.match(rf"^\s*{re.escape(args.tenant)}\s*", raw_title, re.IGNORECASE)
        if tenant_prefix:
            # Understood the front of the string (it does start with the tenant code) - safe to
            # also drop a trailing "(role)" if present. If nothing survives, the title was JUST
            # the tenant code and role - both already shown separately below, so "API" replaces
            # it rather than falling back to the original (which would just restore the
            # duplicate this whole branch exists to avoid).
            stripped = raw_title[tenant_prefix.end():]
            stripped = re.sub(rf"\(\s*{re.escape(args.role)}\s*\)\s*$", "", stripped, flags=re.IGNORECASE).strip()
            title = stripped or "API"
        else:
            # Doesn't match any known convention - safest to leave it untouched.
            title = raw_title

    description = normalize_description(info.get("description", ""))
    if description:
        doc_ops.extend(executive_summary_only(parse_markdown(description)))

    sections = None
    if args.sections:
        with open(args.sections, encoding="utf-8") as fh:
            sections = json.load(fh)
        unknown = [p for p in openapi.get("paths", {}) if p not in sections]
        if unknown:
            sys.exit(f"!! --sections does not classify: {unknown}. Every endpoint belongs to "
                     f"exactly one of Consume and Provide; an unclassified one would be dropped "
                     f"from the Tenant document silently")
    elif args.only_section:
        sys.exit("!! --only-section requires --sections")

    build_glossary(args.tenant, title, openapi)
    build_endpoints(openapi, route_prefix, sections, args.only_section)

    rendered_paths = [p for p in openapi.get("paths", {})
                      if not args.only_section or (sections or {}).get(p) == args.only_section]
    build_schemas(openapi, reachable_schemas(openapi, rendered_paths) if args.only_section else None)
    build_environments()
    build_contacts()

    chapters = [op[2] for op in doc_ops if op[0] == "heading" and op[1] == 2]
    if [c for c in chapters if c not in CHAPTERS] or chapters != [c for c in CHAPTERS if c in chapters]:
        sys.exit(f"!! chapters {chapters} are not a subset of {list(CHAPTERS)} in that order")

    # --- load template, apply token substitution --------------------------------------------
    shutil.copyfile(TEMPLATE, args.output_docx)
    d = docx.Document(args.output_docx)
    body = d.element.body

    tokens = {
        "{{TITLE}}": title,
        "{{TENANT}}": args.tenant,
        "{{ROLE}}": args.role,
        "{{VERSION}}": args.version,
        "{{VERSION_MAJOR}}": args.version.split(".", 1)[0],
        "{{VERSION_MINOR}}": args.version.split(".", 1)[1] if "." in args.version else "0",
        "{{DATE}}": args.date,
        "{{YEAR}}": str(date.today().year),
        "{{HISTORY_DESCRIPTION}}": args.history_description,
        "{{HISTORY_AUTHOR}}": args.author,
        "{{HISTORY_VERSION}}": args.version,
        "{{HISTORY_DATE}}": args.date,
    }

    def substitute_tokens(container_paragraphs):
        for p in container_paragraphs:
            for r in p.runs:
                for token, value in tokens.items():
                    if token in r.text:
                        r.text = r.text.replace(token, value)

    substitute_tokens(d.paragraphs)
    for t in d.tables:
        for row in t.rows:
            for cell in row.cells:
                substitute_tokens(cell.paragraphs)
    for section in d.sections:
        for container in (section.header, section.footer,
                          section.first_page_header, section.first_page_footer,
                          section.even_page_header, section.even_page_footer):
            if container is not None:
                substitute_tokens(container.paragraphs)

    # --- render doc_ops into the body ---------------------------------------------------------
    sectPr = body.find(qn("w:sectPr"))

    def append(element):
        if sectPr is not None:
            sectPr.addprevious(element)
        else:
            body.append(element)

    def make_para(style=None):
        p = d.add_paragraph(style=style)
        el_ = p._element
        el_.getparent().remove(el_)
        append(el_)
        return p

    def add_cell_content(cell, text):
        """Renders text into a table cell, turning normalize_description's preserved "- item"
        lines (e.g. a property's enumerated valid values) into real bulleted paragraphs instead
        of a single run-on line - a table cell can hold multiple paragraphs same as the body."""
        def render_line(p, line):
            if line.startswith("- ") or line.startswith("* "):
                pPr = p._element.get_or_add_pPr()
                pPr.append(el("w:ind", **{"w:left": "180", "w:hanging": "180"}))
                p.add_run("• ")
                add_rich(p, line[2:])
            else:
                add_rich(p, line)

        lines = str(text).split("\n")
        p = cell.paragraphs[0]
        p.style = d.styles["No Spacing"]
        render_line(p, lines[0])
        for line in lines[1:]:
            p = cell.add_paragraph(style="No Spacing")
            render_line(p, line)

    def make_table(rows, widths):
        t = d.add_table(rows=len(rows), cols=len(rows[0]))
        el_ = t._tbl
        el_.getparent().remove(el_)
        append(el_)

        tblPr = t._tbl.tblPr
        for tag in ("w:tblStyle", "w:tblBorders", "w:tblW", "w:tblLayout", "w:tblCellMar"):
            found = tblPr.find(qn(tag))
            if found is not None:
                tblPr.remove(found)
        # The explicit borders/layout/margins below are what the table actually looks like, but
        # a table still has to name a style: a styleless table is what a reviewer sees as
        # "unstyled" in the package, and mixed styled/unstyled tables is one of the defects in
        # the published set. Direct formatting wins over the style, so naming it changes nothing
        # on the page.
        tbl_style = el("w:tblStyle", **{"w:val": "TableGrid"})
        tblPr.insert(0, tbl_style)
        tblW = el("w:tblW", **{"w:w": "9360", "w:type": "dxa"})
        tbl_style.addnext(tblW)
        borders = el("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            borders.append(el(f"w:{edge}", **{"w:val": "single", "w:sz": "6",
                                              "w:space": "0", "w:color": "auto"}))
        tblW.addnext(borders)
        layout = el("w:tblLayout", **{"w:type": "fixed"})
        borders.addnext(layout)
        cell_mar = el("w:tblCellMar")
        for edge, width in (("top", "58"), ("left", "115"), ("bottom", "58"), ("right", "115")):
            cell_mar.append(el(f"w:{edge}", **{"w:w": width, "w:type": "dxa"}))
        layout.addnext(cell_mar)

        t.autofit = False
        for r_i, row in enumerate(rows):
            for c_i, value in enumerate(row):
                if c_i >= len(widths):
                    continue
                cell = t.cell(r_i, c_i)
                cell.width = Inches(widths[c_i])
                add_cell_content(cell, value)
                if r_i == 0:
                    shd = el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": "D9D9D9"})
                    cell._tc.get_or_add_tcPr().append(shd)
        for c_i, w in enumerate(widths):
            for r_i in range(len(rows)):
                if c_i < len(rows[r_i]):
                    t.cell(r_i, c_i).width = Inches(w)
        return t

    def apply_numbering(p, ilvl, num_id):
        pPr = p._element.get_or_add_pPr()
        numPr = el("w:numPr")
        numPr.append(el("w:ilvl", **{"w:val": str(ilvl)}))
        numPr.append(el("w:numId", **{"w:val": str(num_id)}))
        pStyle = pPr.find(qn("w:pStyle"))
        if pStyle is not None:
            pStyle.addnext(numPr)
        else:
            pPr.insert(0, numPr)

    headings_seen = []
    bookmark_id = [9000]
    seen_bookmark_names = set()

    for op in doc_ops:
        kind = op[0]
        if kind == "heading":
            _, level, text = op
            p = make_para(style=f"Heading {level}")
            apply_numbering(p, ilvl=level - 2, num_id=1)
            bookmark_id[0] += 1
            mark = f"_Toc{bookmark_id[0]}"
            marks = [mark]
            # A heading whose text is a bare identifier is a schema; give it a stable,
            # predictable bookmark so [[Name]] cross-references can target it. Guard against
            # duplicate heading text (e.g. two operations with the same summary) colliding.
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", text) and text not in seen_bookmark_names:
                marks.append(f"_{text}")
                seen_bookmark_names.add(text)
            for offset, name in enumerate(marks):
                bid = str(bookmark_id[0] * 10 + offset)
                p._element.append(el("w:bookmarkStart", **{"w:id": bid, "w:name": name}))
            p.add_run(text)
            for offset in range(len(marks)):
                p._element.append(el("w:bookmarkEnd", **{"w:id": str(bookmark_id[0] * 10 + offset)}))
            headings_seen.append((level, text, mark))
        elif kind == "para":
            p = make_para(style="Normal")
            add_rich(p, op[1])
        elif kind == "bullets":
            for item in op[1]:
                p = make_para(style="List Paragraph")
                apply_numbering(p, ilvl=0, num_id=6)
                add_rich(p, item)
        elif kind == "table":
            _, rows, widths = op
            if widths is None:
                widths = [6.5 / len(rows[0])] * len(rows[0])
            make_table(rows, widths)
            make_para(style="Normal")
        elif kind == "code":
            for line in op[1].split("\n"):
                p = make_para(style="No Spacing")
                r = p.add_run(line)
                r.font.name = "Consolas"
                r.font.size = Pt(8)
            make_para(style="Normal")
        elif kind == "note":
            p = make_para(style="Normal")
            r = p.add_run("Note: ")
            r.bold = True
            add_rich(p, op[1])
        elif kind == "raw":
            from lxml import etree
            wrapper = etree.fromstring(
                f'<w:body xmlns:w="{qn("w:p").split("}")[0][1:]}">{op[1]}</w:body>')
            for child in list(wrapper):
                append(child)

    # --- rebuild the Table of Contents ---------------------------------------------------------
    sdt = d.element.body.find(".//" + qn("w:sdt"))
    sdt_content = sdt.find(qn("w:sdtContent"))
    toc_paras = sdt_content.findall(qn("w:p"))
    first_p, last_p = toc_paras[0], toc_paras[-1]
    for run in list(first_p.findall(qn("w:r")))[3:]:
        first_p.remove(run)
    for hyperlink in first_p.findall(qn("w:hyperlink")):
        first_p.remove(hyperlink)
    for p in toc_paras[1:-1]:
        sdt_content.remove(p)

    def estimate_pages():
        LINES_PER_PAGE = 44
        page, line = 5, 0
        result = {}
        counters = [0, 0]
        for op in doc_ops:
            kind = op[0]
            if kind == "heading":
                level, text = op[1], op[2]
                if level == 2:
                    page, line = page + 1, 0
                    counters[0] += 1
                    counters[1] = 0
                else:
                    counters[1] += 1
                    line += 4
                key = (level, text, len(result))
                result[key] = page
            elif kind == "para":
                line += -(-len(op[1]) // 95) + 1
            elif kind == "bullets":
                line += sum(-(-len(i) // 90) for i in op[1])
            elif kind == "table":
                for row in op[1]:
                    line += max(-(-len(str(c)) // 34) for c in row)
                line += 1
            elif kind == "code":
                line += op[1].count("\n") + 2
            elif kind == "note":
                line += -(-len(op[1]) // 95) + 1
            while line >= LINES_PER_PAGE:
                line -= LINES_PER_PAGE
                page += 1
        return result

    pages = estimate_pages()

    def make_toc_entry(level, text, mark, number, page_no):
        p = el("w:p")
        pPr = el("w:pPr")
        pPr.append(el("w:pStyle", **{"w:val": f"TOC{level - 1}"}))
        tabs = el("w:tabs")
        tabs.append(el("w:tab", **{"w:val": "left", "w:pos": "720"}))
        tabs.append(el("w:tab", **{"w:val": "right", "w:leader": "dot", "w:pos": "9710"}))
        pPr.append(tabs)
        rPr = el("w:rPr")
        rPr.append(el("w:noProof"))
        pPr.append(rPr)
        p.append(pPr)

        link = el("w:hyperlink", **{"w:anchor": mark, "w:history": "1"})

        def styled_run(value, tab=False):
            r = el("w:r")
            rp = el("w:rPr")
            rp.append(el("w:rStyle", **{"w:val": "Hyperlink"}))
            rp.append(el("w:noProof"))
            r.append(rp)
            if tab:
                r.append(el("w:tab"))
            else:
                t = el("w:t")
                t.text = value
                t.set(qn("xml:space"), "preserve")
                r.append(t)
            return r

        link.append(styled_run(f"{number}\t{text}"))
        link.append(styled_run(None, tab=True))
        link.append(styled_run(str(page_no)))
        p.append(link)
        return p

    counters = [0, 0]
    for idx, (level, text, mark) in enumerate(headings_seen):
        if level == 2:
            counters[0] += 1
            counters[1] = 0
            number = f"{counters[0]}."
        else:
            counters[1] += 1
            number = f"{counters[0]}.{counters[1]}"
        page_no = pages.get((level, text, idx), pages.get((level, text, 0), 1))
        last_p.addprevious(make_toc_entry(level, text, mark, number, page_no))

    d.save(args.output_docx)

    # --- settings: no updateFields (avoids the "fields may refer to other files" prompt) -----
    with zipfile.ZipFile(args.output_docx) as zf:
        parts = {n: zf.read(n) for n in zf.namelist()}
    settings = parts["word/settings.xml"].decode("utf-8")
    settings = re.sub(r"<w:updateFields[^/]*/>", "", settings)
    parts["word/settings.xml"] = settings.encode("utf-8")
    with zipfile.ZipFile(args.output_docx, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)

    # --- repaginate the TOC for real, via Word COM automation ---------------------------------
    ps_script = r"""
$ErrorActionPreference = 'Stop'
$word = $null; $doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open('%PATH%', $false, $false)
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() | Out-Null }
    $doc.Repaginate()
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() | Out-Null }
    $doc.Repaginate()
    Write-Output ('PAGES:' + $doc.ComputeStatistics(2))
    $doc.Save()
    $doc.Close(0)
    $doc = $null
    Write-Output 'TOC_UPDATED'
} finally {
    if ($doc -ne $null) { $doc.Close(0) }
    if ($word -ne $null) { $word.Quit() }
}
""".replace("%PATH%", os.path.abspath(args.output_docx).replace("'", "''"))

    # NUMPAGES/PAGE fields are deliberately NOT refreshed via Document.Fields.Update()/StoryRanges:
    # in this environment that call made the live-computed page count oscillate between runs
    # (32, then 3, on an unchanged document) - almost certainly print-metrics-dependent pagination
    # jitter in headless Word COM automation, not something safe to trust for a shipped document.
    # ComputeStatistics(2), taken once right after TOC repagination stabilizes, was consistently
    # correct across repeated checks, so that number is written directly into the footer's cached
    # NUMPAGES text below instead of relying on Word to persist its own recalculation.
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script],
                                capture_output=True, text=True, timeout=300)
        page_match = re.search(r"PAGES:(\d+)", result.stdout)
        if "TOC_UPDATED" in result.stdout and page_match:
            print("TOC repaginated by Word; page numbers are exact.")
            patch_numpages_field(args.output_docx, int(page_match.group(1)))
        else:
            print("!! Word could not repaginate the TOC (estimated page numbers were kept):")
            print("  ", (result.stderr or result.stdout).strip()[:400])
    except Exception as ex:
        print(f"!! Word COM automation unavailable ({ex}); estimated page numbers were kept.")

    # Last, because Word's own Save() above stamps cp:lastModifiedBy with whoever is logged in.
    scrub_package(args.output_docx, f"{title} ({args.tenant}) API Specification")

    check = docx.Document(args.output_docx)
    print(f"Wrote: {args.output_docx}")
    print(f"  paragraphs: {len(check.paragraphs)}  tables: {len(check.tables)}")
    h2 = [p.text for p in check.paragraphs if p.style.name == "Heading 2"]
    print(f"  Heading 2 ({len(h2)}): {h2}")


if __name__ == "__main__":
    main()
