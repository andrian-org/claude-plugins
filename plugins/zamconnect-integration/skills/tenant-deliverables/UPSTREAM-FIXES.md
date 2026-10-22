# Defects found in `api-spec-sync`, not yet fixed in ZamConnect

The ZamConnect repo's `.claude/skills/api-spec-sync/` was left exactly as merged in PR 49310.
The renderers were copied into this plugin and fixed here instead, so the fixes below are **not**
in the repo — anyone running `/api-spec-sync` still ships them.

Three of these put real people's names, or a megabyte of unrelated data, into a file handed to a
third party. They are worth raising with the team independently of any tenant's PR.

All line references are to `.claude/skills/api-spec-sync/scripts/openapi_to_docx.py` as merged.

## 1. A colleague's name ships inside every generated document

`docProps/core.xml` is inherited from the template and never overwritten. Every document
rendered by the skill carries:

- `dc:creator` — a previous author's personal name
- `cp:lastModifiedBy` — a different person's name, re-stamped by Word's own `Save()` during the
  repagination pass
- `dc:title` and `dc:subject` — empty

This travels with the file and is visible to whoever receives it. One already-published spec
ships a personal **email address** as `dc:creator`.

**Fix:** rewrite those four fields after the Word COM pass (not before — Word's save re-stamps
`lastModifiedBy`). An empty value must be written self-closing, `<cp:lastModifiedBy/>`; the
`<tag></tag>` form still reads as populated to anything scanning for content after the open tag.

## 2. Every document is ~1.1 MB of which ~1.0 MB is junk

`word/webSettings.xml` carries leftover `divsChild` data from an HTML paste into the template's
ancestor — larger than the rest of the document combined, and describing HTML div mappings the
document has no use for.

**Fix:** strip `<w:divs>…</w:divs>`. On the ZDD package this took each document from ~1.1 MB to
75 KB with no visible change.

## 3. Tables name no style

`make_table` explicitly removes `w:tblStyle` and applies direct formatting instead, and the
template's own Document History table never had one. A reviewer opening the package sees every
table as unstyled, which is one of the defects already present in the published set (57
styleless tables in one document; a 20/15 mix in another).

**Fix:** name `TableGrid` in `tblPr` and keep the direct formatting. Styles are inherited, not
applied, so this changes nothing on the page — it only makes the document say what it is.

## 4. No Contacts and Signature section

The renderer emits five sections and stops at API Environments. The deliverable format has a
sixth: two empty representative tables plus signature rules, filled in at signing.

**Fix:** a `build_contacts()` emitting the two empty tables. Leave them empty — filling them
would put named individuals' contact details into a third-party document on every re-render.

## 5. A `$ref` property silently loses its XML doc comment

Swashbuckle emits a property whose type is another schema as a bare `$ref`, and OpenAPI 3.0
forbids siblings of `$ref`, so the description is dropped. The DOCX then shows a blank
Description cell for exactly those properties — with no warning that anything was lost.

**Fix:** two halves. `options.UseAllOfToExtendReferenceSchemas()` in the tenant's `AddSwaggerGen`
so the description survives in an `allOf` wrapper, **and** `render_type` unwrapping a
single-element `allOf` — without the second half the property's type renders as a bare `object`
and loses its `[[SchemaName]]` cross-reference.

## 6. Consume and Provide cannot be expressed

The renderer emits one `Endpoints` heading. The deliverable format needs two Heading 2 sections,
and the `(c)`/`(p)` documents need to be projections carrying one each. The split is read from
the client each module injects and nothing in the HTTP surface reflects it, so the OpenAPI
document cannot carry it.

**Fix:** a `--sections` JSON map of path → `Consume`/`Provide`, plus `--only-section`. Scoping
the Schemas section to what the rendered endpoints actually reach falls out of the same change,
which is what stops a Provider document defining response types only its Consumer counterpart
returns — a defect visible in a published package today.

## 7. `--role Both` writes "Both" into the header

The Tenant document's running header reads `<CODE> (Both) API Specification`, where the
filename, the folder and the deliverable format all say `Tenant`.

**Fix:** accept `Tenant` as the role, mapping `Both` to it for compatibility.

---

Also worth a separate look, found while auditing and **not** a renderer issue:
`src/Tenants/WCF/appsettings*.json` commits real values for `Endpoints:Wcf:Password`,
`Endpoints:ZamConnect:Username` and `Endpoints:ZamConnect:Password` rather than `__Token__`
placeholders. `scripts/inspect_tenant.py` flags these by key without printing the value.
