---
dgf_version: "1.1.11"
read_date: 2026-09-22
review_date: 2026-09-22
---

# Schema families — how a validator resolves, selects and trusts a DGF schema

DGF configuration comes in **two families**: modern JSON component config, validated by
generated JSON Schemas, and legacy XML, validated by XSDs. A validator that handles one
silently passes everything in the other. This file holds the facts a validator needs to
resolve the family, find the right schema, pick its dialect, and — the part most often
skipped — know whether the runtime actually reads that format for that component.

§1–§5 are **structural** facts: stamp only. §6 is a **policy** fact carrying `review_date`,
because its source is hand-maintained prose that no code regenerates.

## 1. The two families

| Family | Schema form | Where the schemas live | Vendored at |
|---|---|---|---|
| Modern JSON component config | JSON Schema, one per `IComponentConfiguration` class | DGF's generated JSON schema set, served by the MCP (`list_available_json_schemas`, `get_json_schema_details`) — 69 files, 58 of them indexed (§3) | `schemas/json/` |
| Legacy XML | XSD 1.0, one per artifact grammar | DGF's XSD set, served by the MCP (`list_available_xsd_schemas`, `get_xsd_schema_details`) — 9 files, plus the XML grammar reference `form.reference.json` | `schemas/xsd/` |

Neither family is an encoding of the other. Some concepts exist in only one (§5).

## 2. Family detection — resolve before parsing

| Signal in the input | Family |
|---|---|
| XML declaration, or a root element from the table in §5 | XSD |
| Parses as a JSON object | JSON |
| Neither, or both plausible | **Unresolved** — exit `3` |

**Never fall back to JSON.** Defaulting to JSON makes every legacy XML configuration look
like malformed JSON instead of a different format, which is the failure this rule prevents.

## 3. Resolving a JSON schema the way DGF does

The MCP's `SchemaIndexService` does **not** glob `*.schema.json`. A resolver reproduces its selection exactly:

1. **Glob `*Configuration.schema.json`** — matches 57 of the 69 files. The index key is the
   filename with `Configuration.schema.json` removed, lowercased.
2. **Add the allow-list by exact name** — `StandaloneJsonSchemas = ["componentValidator.schema.json"]`.
   That is the entire list. It is the one hand-authored, cross-cutting contract that is not
   a per-component config.
3. **Everything else is unindexed** — 11 files, present in the set but never surfaced as a
   component type:

   | Kind | Files | Why unindexed |
   |---|---|---|
   | `$ref`-only fragments | `RowConfig`, `SectionConfig`, `IDataSource`, `InputGroupConfig` | Not component types; surfacing them would invent bogus components |
   | DataSource kinds | `ApiDataSource`, `CodeDataSource`, `DocumentDataSource`, `RawSqlDataSource`, `StaticOptionsDataSource`, `TableDataSource` | Reached through a discriminator on the authored config, not by schema name |
   | Stale export | ``NumberConfiguration`1`` | Generic-arity marker leaked from the exporter; unserved. Its filename contains a backtick — quote it |

   All 11 are vendored regardless: a validator resolving `$ref` needs the fragments.

The XSD side needs no rules: `Directory.GetFiles(XSD, "*.xsd")`, non-recursive, registers
all 9.

## 4. Dialect — per file, from its own `$schema`

| Where | Dialect |
|---|---|
| The 68 generated schemas in `schemas/json/` | `http://json-schema.org/draft-04/schema#` |
| `componentValidator.schema.json` | `draft-07` — hand-authored, synced into the generated set |
| The 3 contracts in `schemas/standalone/` | `draft-07` |

Select the validator dialect from each file's `$schema`. Never assume one for the set.
`schemas/MANIFEST.md` records the dialect per file.

## 5. Correspondence map — XSD to JSON

Verified root elements, read from the first top-level `xs:element` in each XSD:

| XSD | Root | JSON counterpart | Relationship |
|---|---|---|---|
| `form.xsd` | `form` | `FormConfiguration.schema.json` | True pair; both have dedicated validators |
| `workflow.xsd` | `Workflow` | `WorkflowConfiguration.schema.json` | Pair — but see §6: runtime reads XML only |
| `process.xsd` | `Process` | `ProcessFlowConfiguration.schema.json` | Pair — but see §6: runtime reads XML only |
| `table-view.xsd`, `lookup-view.xsd`, `grid-form.xsd` | `view` | — | Three subtypes sharing one root; no single JSON counterpart |
| `settings.xsd` | `entity` | — | None. Entity field declarations |
| `options.xsd` | `options` | — | None. Legacy option lists |
| `profile.xsd` | `Tree` | — | None. Profile tree definitions |

**Do not infer a counterpart from a filename.** `options.xsd` is not
`StaticOptionsDataSource.schema.json` — it is the legacy `<options>` list grammar, an
unrelated concept. When this table says none, there is none.

## 6. Runtime parity — a schema existing is not the runtime reading it

*Policy fact. Source: DGF's format-coverage page,
`get_doc_page('AI-Authoring/format-coverage.md')`, a hand-maintained living document stamped
`last_updated: 2026-09-09`. Nothing regenerates it. Re-read it on every
re-vendor and update `review_date`.*

Legend, verbatim from the source: **`✓ supported · ◐ partial · ✗ not supported today`**.

| Parity | Components | What it means for a validator |
|---|---|---|
| `✗` — schema exists, runtime does **not** parse JSON | **`Workflow`**, **`ProcessFlow`** | A JSON config that validates against `WorkflowConfiguration.schema.json` is still not read by the runtime, which parses `_workflow.xml` / `_process.xml` exclusively. Schema-valid is **not** success — exit `2`, `schema-valid but not runtime-supported` |
| `◐` — runtime parses JSON, but a sub-behaviour still falls back to XML | `Booking`, `CorporateAccount`, `EligibilityCriteria`, `Form`, `PayComponent`, `Query`, `Uploader` | Valid and read, but not fully migrated. Exit `2` at minimum, naming the component |
| `✓` — full parity | every other component with a schema | Exit `0` on a valid config |

Five legacy artifact types have **no JSON path at all**, separate from the `✗` rows above:
`_form.xml`, `_workflow.xml`, `_process.xml`, `settings.xml`, `view.xml` (three subtypes).
Their current generation policy is recorded in `composition-specs.md`.

**Never state that a component is JSON-capable without this table behind it.** The parity
column in `format-coverage.md` is the only authority; a schema in `schemas/json/` is not.

## Not in this file

DataSource discriminator resolution (`table`, `rawsql`, `static`, …) is resolver behaviour
that mirrors DGF's `DataSourceConverter`. It belongs to the config validators and is not
stamped here until that source has been read and digested.

## See Also

- [`README.md`](README.md) — the stamping convention this file follows
- [`schemas/MANIFEST.md`](schemas/MANIFEST.md) — per-file dialect and membership for the vendored set
- [`composition-specs.md`](composition-specs.md) — the five legacy artifacts and the XML-always policy
