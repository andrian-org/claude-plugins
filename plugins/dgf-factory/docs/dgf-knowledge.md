[← Skill Authoring](skill-authoring.md) · [Back to README](../README.md) · [DGF Schemas →](dgf-schemas.md)

# DGF Knowledge Sourcing

The knowledge base is this plugin's reason to exist. The pipeline is copyable; accurate,
versioned DGF facts are not. Wrong framework facts are also the single most expensive
kind of mistake here — they get baked into prompts and propagate into generated code.

## The rule

> **Every fact in `knowledge/` cites where it came from, when it was read, and which DGF
> version it was read from. A fact that cannot be cited stays marked `[assume]` until it can.**

The exact stamp fields — `dgf_version` and `read_date` in the knowledge file, a per-source
`sha256` in its provenance ledger — and the rule for when a fact needs a *version range*
rather than just a stamp are decided in
[ADR 0013](adr/0013-version-gating-provenance-ledger.md). Short version: stamp everything,
range only facts whose runtime behaviour changed between releases. `dgf_version` is read from
`src/Directory.Build.props`, never from a git tag.

**Where a fact came from is recorded outside `knowledge/`.** `knowledge/` ships, and a shipped
file names no path into the DGF repository
([ADR 0012](adr/0012-no-dgf-paths-in-shipped-files.md)): a developer's install has no DGF
checkout to resolve one against. So each knowledge file has a ledger at the same relative path
under `provenance/` that lists its DGF source files with their digests. The knowledge file
itself names a source by DGF type, file name or MCP call.

The **operative contract** — exact field shapes, the three fact classes, what `null` means in
a `since`/`until` range, and which file is exempt — is
[`knowledge/README.md`](../knowledge/README.md). This page is the reader-facing summary;
where the two differ, that file wins, and `tools/check_knowledge_stamps.py` enforces it.

Acceptable sources, in order of preference:

1. The DotGov Framework repository — a specific file, whose path and digest go in the
   provenance ledger
2. The DGF docs MCP at `https://dgf-mcp.dotgov.uk/mcp` (declared in `.mcp.json`, no
   credentials) — name the tool and the argument, e.g.
   `get_doc_page('AI-Authoring/format-coverage.md')`
3. A DGF ADR under `DotGovFramework/docs/adr/`, recorded in the ledger like any other file

Not acceptable: inference from a name, analogy to another framework, or recall.

**For schemas specifically**, the acceptable sources are narrower, because DGF ships two
families and three disagreeing inventories:

- Modern JSON component config — `src/Tools/dgf-mcp/Schemas/Json/`, or the MCP tools
  `list_available_json_schemas` / `get_json_schema_details`
- Legacy XML grammar — `src/Tools/dgf-mcp/Schemas/XSD/` and
  `Schemas/XmlReference/form.reference.json`, or `list_available_xsd_schemas` /
  `get_xsd_schema_details`
- Runtime parity — `docs/wiki/AI-Authoring/format-coverage.md` is the only authority for
  whether the runtime actually reads a given format for a given component
- `DotGovFramework/docs/schemas/` is **not** the generated set. It holds 3 hand-authored
  standalone contracts, only one of which is synced into the MCP.

See [DGF Schemas](dgf-schemas.md) for the inventories, the precedence rule and the
correspondence map.

## Where the facts live

```text
knowledge/
├── README.md                  # this policy, in short
├── component-catalogue.md     # the component plugins and their contracts
├── composition-specs.md       # declarative composition + EventBase verbs
├── naming-conventions.md
├── schema-families.md         # JSON vs XSD: parity, correspondence, resolution
├── json-reader.md             # how the runtime reads component JSON
├── process-model.md           # process.xsd vs the runtime model; how process references resolve
├── data-model.md              # entities, fields, relations; what each model loader does with a reference
├── reference-graph.md         # every reference as an edge — the reference-edges table — and what
│                              #   a static walk of them cannot see
├── permissions.md             # where a root names roles, and that nothing in it declares one
└── schemas/                   # vendored copies, version-stamped
    ├── MANIFEST.md            #   DGF version, date, per-file dialect and membership
    ├── json/                  #   generated *.schema.json (modern component config)
    ├── xsd/                   #   the 9 *.xsd + form.reference.json (legacy XML)
    └── standalone/            #   hand-authored contracts from DGF docs/schemas/

provenance/knowledge/          # NOT SHIPPED — one ledger per file above, same relative path
└── schemas/MANIFEST.md        #   DGF commit SHA, upstream and shipped sha256 per file
```

Schemas are **vendored, not referenced across the filesystem** — a validator that reads a
path outside the plugin breaks the moment the plugin is installed somewhere else. Copy
them in, record the DGF version and the date, and re-vendor deliberately.

The complete set is vendored — both families, roughly 3.5 MB, 82 files, each recorded with
its upstream and shipped `sha256` in the schema ledger. They differ for 61 files, because
`tools/vendor_schemas.py` rewrites the DGF paths inside DGF's own schema text as it copies
the set in. Three further details make the set non-obvious, and all three are recorded with
their mitigations in [DGF Schemas](dgf-schemas.md):

- The hand-authored contracts live in `standalone/` rather than beside the generated set,
  because `dataFetcherConfiguration.schema.json` and `DataFetcherConfiguration.schema.json`
  differ only in case and silently overwrite each other on a case-insensitive filesystem.
- The set mixes JSON Schema draft-04 and draft-07, so `MANIFEST.md` records the dialect
  per file.
- The schema ledger records the DGF commit SHA, because the deployed MCP can lag the
  repository and the vendored set needs a knowable position between the two.

The three files milestone 12 added were read from the engine's loaders, not its samples or its
XSDs: what `TableManager`, `FormManager`, `LookUpViewManager`, `LookUpDialogManager` and
`EditableGridManager` do with a reference, and what each workflow step loads and when. Where the
first draft of the milestone's plan disagreed with the code — a grid's table name is cleaned before
`BASE:` is tested; a form cell that names no field throws — the ledger records the difference and
the file states the code.

Nothing in `knowledge/` may name a skill, a step number or a pipeline stage. Knowledge
states DGF facts; it does not know who reads it. A file that says "in Step 3 of
`/dgf-implement`…" has inverted the dependency and will rot when the step renumbers.

## Verified facts

Read from `DotGovFramework` on **2026-09-18**. Re-verify before relying on these.

| Fact | Source |
|------|--------|
| DGF is a **Component-Hosted Pluggable Monolith** for government e-services | `AGENTS.md` project overview |
| .NET 10 (`net10.0`), nullable references **disabled** | `src/Directory.Build.props` |
| Angular 19.2 frontend, standalone components, NGXS state | `AGENTS.md` tech stack |
| SQL Server via EF Core (`Microsoft.Data.SqlClient`) | `AGENTS.md` tech stack |
| Auth: JWT Bearer + OpenID Connect (Azure AD + DGPass) | `AGENTS.md` tech stack |
| **34** component service registrations across 31 modules, each implementing `IComponentService<TSource>` — not "~40"; DGF has five disagreeing counts and `knowledge/component-catalogue.md` explains each | the 34 `RegisterComponentService(` call sites; `src/Components/DGF.Components.Shared/Contracts/IComponentService.cs` |
| One dispatcher handles every UI request | `src/DGF.API/Controllers/ComponentsController.cs` |
| Components are **statically enumerable** — name→type registry plus a reflection scan | `ComponentServiceProvider.cs`, `RegisterComponentServices()` |
| Consumer apps compose plugins **declaratively via XML/JSON specs** and the DataFetcher EventBase verb dispatcher | `AGENTS.md` project overview |
| DGF supports **two configuration formats** — modern JSON and legacy XML — via two auto-generated reference pipelines | `Schemas/Json/README.md`, `Schemas/XmlReference/README.md` |
| Modern JSON schemas are generated from `IComponentConfiguration` classes and committed | `src/Tools/dgf-mcp/Schemas/Json/` (69 files) |
| Legacy XML has 9 XSDs plus a generated grammar reference | `src/Tools/dgf-mcp/Schemas/XSD/`, `Schemas/XmlReference/form.reference.json` |
| **Schema availability is not runtime parity** — `Workflow` and `ProcessFlow` have JSON schemas the runtime ignores in favour of XML | `docs/wiki/AI-Authoring/format-coverage.md` |
| Hand-authored standalone contracts live separately and are not the generated set | `docs/schemas/` — `componentValidator`, `dataFetcherConfiguration`, `eventBase` |
| Tests: xUnit + FluentAssertions + Moq/NSubstitute (backend), Jest + Playwright (frontend) | `AGENTS.md` tech stack |
| A hosted DGF documentation MCP exists at `https://dgf-mcp.dotgov.uk/mcp` | this plugin's `.mcp.json`; the endpoint is **unversioned** |

Because components are statically enumerable and the schemas exist, **real validators are
feasible** — component resolution and spec well-formedness do not need to be guessed.

## Corrections to the blueprint

The blueprint's Part 2 was written from a one-sentence description and marks its
assumptions `[assume]`. Two are now known to be wrong or unsupported:

- **There is no BPMN engine — but there are formal process grammars.** DGF composition is
  declarative XML/JSON plus a verb dispatcher, so "BPMN" was wrong. The inference that no
  formal process specification exists was also wrong: `process.xsd` (root `Process` →
  `OnStart`, `States`) and `workflow.xsd` (root `Workflow` → `Sequence`, `Input`) are
  machine-checkable, state-machine-shaped grammars, and `format-coverage.md` confirms both
  are the live runtime formats. `/dgf-process` was built on them (decided 2026-09-27,
  [ADR 0027](adr/0027-dgf-specific-skills-revised.md)): `validate_process.py` checks a process against
  `process.xsd` and against the runtime model ([ADR 0014](adr/0014-process-verification-runtime-resolution.md)),
  and the skill authors both artifacts in XML only.
- **"Build a system from scratch" is not the whole picture.** Consumer apps compose
  existing plugins declaratively, which means "implement a task" often means *composing
  configuration*, not writing code. That reshapes what `/dgf-implement` should do.

Answered since: headless validation exists for both families — the DGF MCP exposes
`validate_component_config` / `validate_*_json` and `validate_*_xml`, so no separate
binary is needed.

**Nothing is still open.** The four remaining questions were closed on 2026-09-21 and
recorded in [`docs/adr/`](adr/README.md): the estate is brownfield-dominant and a skill's unit
of work is the whole workspaces root ([0026](adr/0026-authoring-entry-point-revised.md)); process
verification is structural-plus-our-own-semantics, with no headless execution
([0014](adr/0014-process-verification-runtime-resolution.md), superseding 0006 and 0002); validators run on Python
with `lxml` and `jsonschema`, reading JSON the way the runtime does
([0015](adr/0015-validator-runtime-and-json-reader.md), superseding 0007); version gates are
necessary, so every fact is stamped and behavioural facts carry a range
([0013](adr/0013-version-gating-provenance-ledger.md), superseding 0008 and 0003); shipped
files carry no DGF repository paths ([0012](adr/0012-no-dgf-paths-in-shipped-files.md)); and seven conventions ship as
defaults ([0005](adr/0005-default-team-rules.md)).

## Architectural provenance

This plugin is independent: its pipeline architecture derives from AI Factory 2.18.1, and it
takes no dependency on any other DGF agent-tooling effort. Overlapping prior work exists and
its overlap was measured on 2026-09-21; it was deliberately set aside rather than overlooked,
and it is **not** a constraint, an authority or an architecture source here. See
[ADR 0001](adr/0001-independent-plugin-with-ai-factory-derived-architecture.md).

Every fact in `knowledge/` is therefore sourced from first-party DGF — the engine under
`src/Core`, the MCP server under `src/Tools/dgf-mcp`, the shipped schemas, and `docs/wiki/`.

## See Also

- [Skill Authoring](skill-authoring.md) — how a skill cites knowledge instead of inlining it
- [Architecture](architecture.md) — why `knowledge/` may never depend on a slice
- [DGF Schemas](dgf-schemas.md) — the two schema families, in full
- [Architecture Blueprint](blueprint.md) — Part 2 and its open questions in full
