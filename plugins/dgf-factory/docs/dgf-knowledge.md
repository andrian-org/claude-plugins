[← Skill Authoring](skill-authoring.md) · [Back to README](../README.md) · [DGF Schemas →](dgf-schemas.md)

# DGF Knowledge Sourcing

The knowledge base is this plugin's reason to exist. The pipeline is copyable; accurate,
versioned DGF facts are not. Wrong framework facts are also the single most expensive
kind of mistake here — they get baked into prompts and propagate into generated code.

## The rule

> **Every fact in `knowledge/` cites where it came from, when it was read, and which DGF
> version it was read from. A fact that cannot be cited stays marked `[assume]` until it can.**

The exact stamp fields — `dgf_version`, `read_date`, and a per-source `sha256` — and the rule
for when a fact needs a *version range* rather than just a stamp are decided in
[ADR 0003](adr/0003-version-gating.md). Short version: stamp everything, range only facts whose
runtime behaviour changed between releases. `dgf_version` is read from
`src/Directory.Build.props`, never from a git tag.

Acceptable sources, in order of preference:

1. The DotGov Framework repository — a specific file path
2. The DGF docs MCP at `https://dgf-mcp.dotgov.uk/mcp` (declared in `.mcp.json`, no credentials)
3. A DGF ADR under `DotGovFramework/docs/adr/`

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
└── schemas/                   # vendored copies, version-stamped
    ├── MANIFEST.md            #   DGF commit SHA, version, date, per-file dialect
    ├── json/                  #   generated *.schema.json (modern component config)
    ├── xsd/                   #   the 9 *.xsd + form.reference.json (legacy XML)
    └── standalone/            #   hand-authored contracts from DGF docs/schemas/
```

Schemas are **vendored, not referenced across the filesystem** — a validator that reads a
path outside the plugin breaks the moment the plugin is installed somewhere else. Copy
them in, record the DGF version and the date, and re-vendor deliberately.

The decision is to vendor the complete set — both families, roughly 3.5 MB. Three details
make that non-obvious, and all three are recorded with their mitigations in
[DGF Schemas](dgf-schemas.md):

- The hand-authored contracts live in `standalone/` rather than beside the generated set,
  because `dataFetcherConfiguration.schema.json` and `DataFetcherConfiguration.schema.json`
  differ only in case and silently overwrite each other on a case-insensitive filesystem.
- The set mixes JSON Schema draft-04 and draft-07, so `MANIFEST.md` records the dialect
  per file.
- `MANIFEST.md` records the DGF commit SHA, because the deployed MCP can lag the
  repository and the vendored set needs a knowable position between the two.

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
| ~40 self-contained component plugins, each implementing `IComponentService<TSource>` | `src/Components/DGF.Components.Shared/Contracts/IComponentService.cs` |
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
  are the live runtime formats. The proposed `/dgf-process` skill should be re-derived
  from those two XSDs alongside `eventBase.schema.json` and
  `dataFetcherConfiguration.schema.json`.
- **"Build a system from scratch" is not the whole picture.** Consumer apps compose
  existing plugins declaratively, which means "implement a task" often means *composing
  configuration*, not writing code. That reshapes what `/dgf-implement` should do.

Answered since: headless validation exists for both families — the DGF MCP exposes
`validate_component_config` / `validate_*_json` and `validate_*_xml`, so no separate
binary is needed.

**Nothing is still open.** The four remaining questions were closed on 2026-09-21 and
recorded in [`docs/adr/`](adr/README.md): the estate is brownfield-dominant and a skill's unit
of work is the whole workspaces root ([0004](adr/0004-authoring-entry-point.md)); process
verification is structural-plus-our-own-semantics, with no headless execution
([0002](adr/0002-process-verification.md)); version gates are necessary, so every fact is
stamped and behavioural facts carry a range ([0003](adr/0003-version-gating.md)); and seven
conventions ship as defaults ([0005](adr/0005-default-team-rules.md)).

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
