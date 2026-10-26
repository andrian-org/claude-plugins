---
id: 0031
title: Validators run on Python with lxml and jsonschema in a project virtual environment, and read JSON the way the runtime does
status: accepted
date: 2026-10-26
deciders: [Andrian Mamei]
supersedes: [0015]
tags: [validation, runtime, dependencies, json, install]
---

# 0031 — Validators run on Python with lxml and jsonschema in a project virtual environment, and read JSON the way the runtime does

Restates [ADR 0015](0015-validator-runtime-and-json-reader.md) in full. [ADR 0014](0014-process-verification-runtime-resolution.md)
§4 says validation runs *in-process* against vendored schemas; this ADR says which process, where its
dependencies live, and how it reads a JSON configuration.

The engines and the JSON reader are unchanged: **Python 3.9+, `lxml` for the XSD family, `jsonschema`
for the JSON family, pinned with hashes, read the way the runtime reads, and a missing dependency
reported as exit `3`.** One thing changes: **where the dependencies are installed, and by whom.** ADR
0015 rested on "a plugin cannot install its own dependencies". [ADR 0029](0029-npm-cli-delivery.md)
replaces the plugin with an npm CLI whose `setup` command runs in the project, so that premise no longer
holds. `dgf-factory setup` now creates a virtual environment inside the project and installs the pinned
requirements into it, and the scripts re-run themselves under it.

ADR 0015 restated ADR 0007 and changed three things, which stand:

1. **ADR 0007 §4 was replaced.** It said the NJsonSchema pre-pass was enough, and that unknown
   properties are "then rejected". The runtime's JSON reader was read afterwards. It accepts
   property names in any case, enum names for integer enums, comments, and polymorphic children
   that the schemas describe as a closed interface object. A validator that follows the schemas
   literally passes **0** of the 230 sample files whose type it can resolve. §4 below replaces
   the pre-pass alone with the pre-pass plus the runtime's reader semantics.
2. **An unknown property is a warning, not a rejection.** The runtime skips unknown properties
   silently. This is decision D1 of the milestone 8 plan (Andrian Mamei, 2026-09-24).
3. **A false fact was corrected.** ADR 0007 §2 said `lxml` runs the "same libxml2 engine as
   `xmllint`". It does not: `lxml` 6.1.3 bundles libxml2 2.14.6, and the system `xmllint` is
   2.9.13. The results agree, by measurement, not by construction.

## Context

Read on **2026-09-24**, except where marked **2026-10-26**. DGF paths are relative to the DGF
repository root at `aa1d5c4c2`.

### Where the dependencies go — new, 2026-10-26

- **The premise below no longer holds.** ADR 0029 delivers `dgf-factory` as an npm CLI.
  `dgf-factory setup` runs in the developer's project, can run commands there, and writes everything
  except the harness files under `.dgf-factory/`. A setup step is exactly what the plugin format lacked.
- **ADR 0015 never said where dependencies go.** It said "installed by the user", and the `--user` came
  from code and docs: `scripts/lib/deps.py:24-27` and `skills/dgf-doctor/scripts/doctor.py:533-536`
  build `python3 -m pip install --user --require-hashes -r "<root>/scripts/requirements.txt"` outside a
  virtual environment, and `docs/getting-started.md:92` documents it. That puts packages in the user's
  home directory, shared by every project.
- **How the scripts start.** Every skill runs `python3 "<runtime>/scripts/<x>.py"`. Each top-level
  script imports `lib/`, and four lib modules import the engines at top level: `scripts/lib/xsd.py:25`,
  `family.py:20` and `process_checks.py:32` import `lxml`, and `json_validate.py:27` imports
  `jsonschema`. So a script started by a system `python3` without the packages fails before any of its
  own code runs, unless it switches interpreter first.
- **Tests import entry scripts as modules** (`tests/test_verify_gate.py:14`, `import verify_gate`), so a
  switch that runs at import would replace the test runner.
- **The contributor's environment** is already a `.venv` at the root of this repository, which
  `tools/check-dual-schema-docs.sh` section 8 prefers.

### Neither standard library validates either family — carried forward

- Python's standard library has **no XSD validation** and **no JSON Schema validation**.
  `xml.etree` parses XML but has no schema support.
- Node's standard library has neither either.
- The scripts this plugin already has are stdlib-only: the shipped
  `skills/dgf-doctor/scripts/doctor.py`, and the maintainer tools
  `tools/check_knowledge_stamps.py` and `tools/vendor_schemas.py`
  ([ADR 0012](0012-no-dgf-paths-in-shipped-files.md) §4 moved the tools out of `scripts/`).
- On the machine this was read on, `/usr/bin/python3` is **3.9.6** (the macOS system
  interpreter) with neither `lxml` nor `jsonschema` installed. `uv` is installed.

### A plugin cannot install its own dependencies — carried forward, no longer the premise

The Claude Code plugin format has no dependency-install step. The `plugin-structure` skill's
guidance is to *"document dependencies: list required tools and versions"*
(`.claude/skills/plugin-structure/SKILL.md`, §Portability). Under the plugin, any third-party
dependency had to be installed by the user, and the plugin had to detect when it was missing. The
detection stays; the CLI's setup step replaces the manual install.

### The pinned engines install on Python 3.9 — measured 2026-09-24

In a scratch virtual environment built on `/usr/bin/python3` 3.9.6, `uv pip install lxml
jsonschema` resolved and installed `lxml` 6.1.3 and `jsonschema` 4.25.1 (with
`jsonschema-specifications` 2025.9.1, `referencing` 0.36.2, `rpds-py` 0.27.1, `attrs` 26.1.0 and
`typing-extensions` 4.16.0), and both import.

### The XSD family: 8 of 9 vendored XSDs compile, under either libxml2 — corrected

`lxml.etree.LIBXML_VERSION` is **(2, 14, 6)**: `lxml` 6.1.3 bundles its own libxml2. The system
`xmllint --version` reports **libxml 20913**, i.e. 2.9.13. They are different engines. They agree
on every result that matters here, measured under both on 2026-09-24:

- `form`, `grid-form`, `lookup-view`, `options`, `process`, `settings`, `table-view` and
  `workflow` compile. None uses an XSD 1.1 construct.
- **`profile.xsd` does not compile.** L20-21 declare attributes named `xmlns:xsi` and `xmlns:xsd`,
  which are not valid `xs:NCName` values. That is a defect in the schema, not in libxml2. DGF's
  own `docs/wiki/AI-Authoring/format-coverage.md:113` already puts `profile.xsd` outside Wave-1
  validator scope.
- Over the samples in `src/samples/workspaces/`, **211 of 341** `_workflow.xml` files and **2 of
  23** `process.xml` files fail, the same files under both engines.

Agreement today does not guarantee agreement after the next `lxml` release. So the validator's
authority is the libxml2 that `lxml` bundles, and a result is never re-derived with `xmllint`.

### The JSON family: dialect, and NJsonSchema inheritance — carried forward

`knowledge/schemas/MANIFEST.md` §2.1: the vendored `json/` set has **68 draft-04** schemas
(generated by `SchemaExporter` via NJsonSchema) and **1 draft-07**; `standalone/` is all draft-07.
The dialect is chosen per file from its own `$schema`. `format` values include the non-standard
`int32`, `int64`, `float` and `guid`.

**NJsonSchema's inheritance does not survive a spec-compliant validator.** NJsonSchema models
inheritance as `"allOf": [ { "$ref": "#/definitions/Base" }, { properties: …,
additionalProperties: false } ]`, chained (`DatePickerConfiguration` →
`InputComponentConfigurationBase` → `ComponentConfigurationBase`). Each `allOf` branch evaluates
on its own, so the derived branch rejects every property the base declares. `additionalProperties`
considers only `properties` and `patternProperties` in the **same** schema object, in every draft,
so this is an NJsonSchema-semantics problem, not a draft problem. The pattern occurs **97 times in
64 of the 69** vendored `json/` files.

### How the runtime reads a component JSON file — new

**One options object.** `src/DGF.API/ConfigureServices.cs` L238-259, `ConfigureJsonOptions`, is
applied both as the registered `JsonSerializerOptions` (L261) and to MVC's `JsonOptions` (L265),
which `src/Core/DGF.Kernel/Utils/Serialization/JsonSerializationService.cs` L22 reads. It sets
`IncludeFields = true`, `PropertyNameCaseInsensitive = true`,
`ReadCommentHandling = JsonCommentHandling.Skip`, `JsonStringEnumConverter(CamelCase)`, and ten
more converters: `NullableDateOnly`, `NullableTimeOnly`, `DataSource`, `Dictionary`, `DateOnly`,
`Component`, `ObjectParameters`, `ComponentModel`, `AbstractStep`, `TimeOnly` and `Boolean`. It
does **not** set `AllowTrailingCommas`, `NumberHandling` or `UnmappedMemberHandling`.

So, for System.Text.Json:

- **Property names match in any case.** `"placeholder"`, `"Placeholder"` and `"PLACEHOLDER"` bind
  the same member. Two keys that differ only in case bind the same member, so one of the author's
  values silently replaces the other.
- **Unknown properties are skipped silently.** `UnmappedMemberHandling` defaults to `Skip`.
- **Comments are skipped; trailing commas are a parse error.**
- **Every enum accepts its member names, case-insensitively,** and its integer values, through the
  global `JsonStringEnumConverter`, whatever the schema's `type` says.

**The component reader dispatches on an exact `type` key.** A top-level component file is read as
`IComponentConfiguration`
(`src/Components/DGF.Components.Shared/ComponentFileLoadService.cs:55-65`), and so is every nested
child typed that way. `src/Components/DGF.Components.Services/JsonConverters/ComponentConverter.cs`
L22-42 reads it:

- `TryGetProperty("type")` is **case-sensitive**. A component with `"Type"` and no `"type"` throws
  `Component - 'Type' property should be set.`
- The value is parsed with `Enum.TryParse(ComponentType, ignoreCase: true)`. An unknown value
  returns `null`: **the component silently vanishes.**
- The class is the first type in `ComponentAssignableTypesCache` whose name equals `<Type>` or
  `<Type>Configuration`, ignoring case, and failing that the first whose name *starts with*
  `<Type>`. So `Date` → `DatePickerConfiguration`, `Textarea` → `TextAreaConfiguration`, `Pay` →
  `PayComponentConfiguration`, `ProcessMonitor` → `ProcessMonitorComponentConfiguration`. **The
  prefix match is order-dependent**: `Date` could also match `DateTimePickerConfiguration`, and
  the cache orders types by name within each assembly.
- `src/Components/Extensions/DGF.Sitemap/Models/Configuration/HeaderConfiguration.cs:11` binds
  `ComponentType.Footer`, an upstream defect. No configuration class exists for `Search`,
  `RadioButton`, `WorkflowNew`, `DropdownTree`, `Option`, `Internal` or `Template`.

**The DataSource reader dispatches the same way, and throws instead.**
`src/Core/DGF.DataSources/JsonConverters/DataSourceConverter.cs` L57-108: `GetProperty("type")` is
case-sensitive, a non-string `type` throws, and an unknown value throws `JsonException`. It has
**9 discriminators and 6 classes**: `Table`, `LookupTable` and `EditableGrid` → `TableDataSource`;
`Api` → `ApiDataSource`; `Static` → `StaticOptionsDataSource`; `Document` → `DocumentDataSource`;
`StoredProcedure` and `RawSql` → `RawSqlDataSource`; `Code` → `CodeDataSource`.
`_COMPONENTS/DataSource/<name>.json` is read straight to `IDataSource`
(`src/Core/DGF.DataSources/DataSourceLoader.cs:12-29`).

**Some folders have no component schema.** `Template/` holds fragments, each typed by its own
`type` (`ComponentFileLoadService.cs:67-71`). `Endpoints/` deserializes to `EndpointSchema`, which
has no schema. Root `sitemap*.json` → `SiteMapConfiguration`, which has its own loader and no
`type` (`ComponentFileLoadService.cs:34-53`). No loader references `Forms/` (plural).

### What the schemas say, and what the runtime accepts — new

The generated schemas declare **PascalCase** properties (`Type`, `Name`, `Placeholder`) and a
PascalCase `ComponentType` enum. Their `Type` description says values are PascalCase and
"lowercase or camelCase will fail validation". That sentence is a hand-written doc comment
(`src/Components/DGF.Components.Shared/ComponentsBase/Configuration/ComponentConfigurationBase.cs:18`)
and is false for the runtime. The committed set comes from `ExportWith_NJsonSchema`
(`src/Tools/SchemaExporter/Program.cs:129-142`). `ExportWith_SystemTextJson` (L37-114) is generated
too, into a separate folder, and is never synced into the MCP. Nested children are
`items: {$ref: "#/definitions/IComponentConfiguration"}` (a closed interface object, in 24 files)
or `$ref: "#/definitions/IDataSource"` (15 files). Across `definitions`, **166** enums are
`type: integer` with `x-enumNames`, and **95** are string enums.

### Measured against the samples — new

The samples hold **385** `FM/_COMPONENTS/**/*.json` files. All 385 parse once comments are
stripped. 32 contain `//` or `/* */` comments. Every one of the 374 that carries a discriminator
spells the key `type`, in lower case; the other 11 are sitemaps and endpoints. 98.3% of `type`
values and 99% of keys are lowercase or camelCase.

A scratch prototype (2026-09-24, not committed) measured each reading against them:

| reading | passes |
|---|---|
| DGF's MCP mode — strip `additionalProperties: false` | 230 / 230 type-resolvable files |
| strict, case-sensitive, merged inheritance — the schemas literally | **0 / 230** |
| + case-insensitive names and enums | 42 / 230 |
| + `IComponentConfiguration` / `IDataSource` dispatch by `type` | 183 / 344 |

The 161 remaining failures are dominated by integer enums written as names (133), `showHeaders`
on DataTables (42; not a `DataTableConfiguration` property), and string-valued booleans or numbers
(46). The first is the global `JsonStringEnumConverter`, the second an unknown property the runtime
skips, and the third is what the registered converters are read for.

### What DGF's MCP validator does — new

`src/Tools/dgf-mcp/Services/SchemaValidationService.cs` L23-78 and L147-217 strip `$schema` and
every `additionalProperties: false` before compiling. It never case-folds the instance, and the
caller supplies `componentType` (`Tools/ValidateComponentConfigTool.cs:30-36`). Against the live
MCP on 2026-09-24: `{}` validates as a Form; `{"Type":"form"}` fails the enum; a lowercase `type`
is invisible to it; and `validate_component_config("ApiDataSource")` returns "Schema not found",
because the MCP never indexes the DataSource schemas.

## Decision

**The validators are Python 3.9+ scripts using `lxml` for the XSD family and `jsonschema` for the
JSON family, installed from a pinned requirements file into a virtual environment inside the project,
which every script switches to before it imports an engine. A JSON
configuration is validated the way the runtime reads it: merged NJsonSchema inheritance,
case-insensitive names and enums, polymorphic children dispatched by `type`, and unknown
properties reported as warnings. The dependency is confined to the validators, and a missing
dependency is reported, never passed.**

1. **Interpreter floor: Python 3.9.** It is what macOS ships, and the validators must run on the
   interpreter a DGF developer already has.
2. **XSD family: `lxml.etree.XMLSchema`**, against the vendored XSDs. The authority is the libxml2
   that `lxml` bundles, never `xmllint`: they are different versions and agree today only by
   measurement. Documents are parsed from bytes with entity resolution, network access and DTD
   loading off.
3. **JSON family: `jsonschema`**, choosing `Draft4Validator` or `Draft7Validator` from each file's
   `$schema`. Never one dialect for the whole set.
4. **The JSON validator reads like the runtime.** It extends `jsonschema`'s validator; it does not
   replace it.
   - **Pre-pass.** Where an `allOf` combines a local `$ref` with a sibling object, the schema is
     merged: the union of `properties` (derived overrides base), the union of `required`, and
     `additionalProperties: false` over the union. The pre-pass has its own fixtures and is
     tested before any other JSON check.
   - **Parse.** Strip one UTF-8 BOM; remove `//` and `/* */` comments, never inside a string;
     otherwise strict JSON, so a trailing comma is a parse failure.
   - **Names and enums.** Property names match case-insensitively in `properties`, `required` and
     `additionalProperties`. Two instance keys that differ only in case are an error: one value is
     silently discarded, and the validator cannot know which the author meant. String enums
     compare case-insensitively. An integer enum with `x-enumNames` accepts its integers or,
     case-insensitively, its names.
   - **Converters.** Booleans, numbers, dates and dictionaries are accepted exactly as the
     registered converters accept them. What each converter reads is a stamped fact in
     `knowledge/`; anything a converter does not accept is an error.
   - **Dispatch.** A child typed `IComponentConfiguration` is validated against the class
     `ComponentConverter` selects for its `type`, and a child typed `IDataSource` against the
     class `DataSourceConverter` selects. The key must be exactly `type`. An unknown component
     `type` is an error (the runtime drops the component); a legal type with no configuration
     class is a warning, checked against the interface only; an unknown DataSource discriminator
     is an error (the runtime throws). The type-to-class tables are stamped facts in `knowledge/`.
   - **Unknown properties are a warning** (exit `2`), reported once per JSON path as ignored by
     the runtime. `required` is enforced from the merged union, as an error.
5. **`format` is annotation-only** in the first version. The non-standard formats (`int32`,
   `int64`, `float`, `guid`) are not asserted, and the report says so rather than implying they
   were checked.
6. **Pinned, and installed into the project only.** Exact versions with hashes go in
   `scripts/requirements.txt`, compiled for Python 3.9.
   - `dgf-factory setup` finds a Python 3.9+ interpreter, creates `.dgf-factory/runtime/.venv` with
     `-m venv` when it is absent, and runs
     `<venv python> -m pip install --require-hashes -r .dgf-factory/runtime/scripts/requirements.txt`.
   - It never runs `pip` outside that environment, and installs nothing outside the project.
   - `--no-python` skips the step and prints the command. A failure leaves the installed files in
     place, and setup reports the command and exits `2`.
   - The environment is gitignored by a managed `.dgf-factory/runtime/.gitignore`. A teammate who
     clones re-creates it with `dgf-factory setup` or the printed command.
   - Nothing in a skill or a validator runs `pip`.
7. **Every entry script switches to the project environment first.** `scripts/lib/runtime.py` is
   stdlib-only and imports nothing from `lib/`, so the stdlib-only scripts can load it by path. Its
   `use_project_venv()`:
   - finds `<runtime root>/.venv` — `bin/python` on POSIX, `Scripts\python.exe` on Windows — where the
     runtime root is the folder holding `scripts/`: `.dgf-factory/runtime` in a project, the repository
     root for a contributor;
   - when that interpreter exists and is not the running one, re-runs the same arguments under it:
     `os.execv` on POSIX, and on Windows, where `execv` loses the exit code, `subprocess.run` and then
     `sys.exit` with its return code;
   - is disabled by `DGF_NO_VENV=1`, and guards against a loop with `DGF_IN_VENV=1`;
   - does nothing when there is no environment, so a script falls through to rule 8.

   Each entry script calls it in its first lines, before any other `from lib import …`, and only under
   `if __name__ == "__main__":`, so importing the script in a test never switches interpreter.
8. **A missing dependency is exit `3`** (usage error, per `.ai-factory/rules/base.md`), with the
   exact install command in the message. A validator that cannot import its engine never exits
   `0`. In an installed project the command is the `pip install` into the project environment, and the
   message adds "or re-run `dgf-factory setup`". In this repository it stays the command for the
   running interpreter.
9. **The existing scripts stay stdlib-only.** `doctor.py`, the scaffold's `design.py`,
   `check_knowledge_stamps.py` and `vendor_schemas.py` take no dependency, so `/dgf-doctor` can run
   before anything is installed. The doctor's dependency probe reports whether the validators can run,
   preferring the project environment; it does not install anything.
10. **`profile.xsd` is not validated.** It is vendored for reference and drift, reported as
   uncompilable, and excluded from the XSD validator with that reason stated. This matches DGF's
   own Wave-1 scope.

## Alternatives considered

- **A .NET 10 file-based app** (`dotnet run validate.cs`) using `System.Xml` for XSD and
  System.Text.Json with DGF's own converters. It would have the closest parity with DGF, on an
  SDK every DGF developer already has. Not chosen: a NuGet restore on first run, a slow cold
  start on every gate, a second runtime next to the Python scripts, and DGF's converters are not
  a package the plugin can reference without a checkout.
- **Python stdlib plus `xmllint`**, with this plugin's own JSON validator. Rejected: it makes this
  plugin the owner and sole tester of a JSON Schema implementation, and `xmllint` is not installed
  by default on many Linux images (`libxml2-utils`).
- **Node with `ajv` and `ajv-draft-04`.** Rejected: an `npm install` step too, the same
  NJsonSchema-inheritance problem, and a Node dependency tree in a Python plugin.
- **Validate the schemas literally** — PascalCase names, closed interface objects, integer enums.
  Rejected on the measurement: **0 of 230** sample files pass, every one of which the runtime
  loads. A gate that fails everything is not a gate.
- **Do what DGF's MCP does** — strip `$schema` and every `additionalProperties: false`. Rejected.
  It gives up unknown-property reporting, and with case-sensitive names it validates almost
  nothing: `{}` passes as a Form, and a lowercase `type` is invisible.
- **Block on unknown properties**, as ADR 0007 decided. Rejected: the runtime skips them, so a
  block rejects configuration the runtime loads. 42 sample DataTables carry `showHeaders`.
- **Validate against the `ExportWith_SystemTextJson` output**, which may already encode camelCase
  names and string enums. Rejected for now: it is not committed, not vendored, and not what the
  MCP serves, so the plugin would be validating against a schema no DGF tool publishes.
- **Keep the manual install, and only report the command** (2026-10-26). Rejected: the user's request is
  that `dgf-factory setup` installs everything the project needs, and the first gate a new user runs
  would still fail with exit `3`.
- **Install into the user's site-packages (`pip install --user`)**, as the plugin's docs did.
  Rejected: it writes outside the project, and every project on the machine shares one version.
- **Have skills call the environment's interpreter directly** (`.dgf-factory/runtime/.venv/bin/python …`).
  Rejected: the path differs between POSIX and Windows, it would put two command forms in every
  skill's permission rules, and a script run without the environment would fail to import instead of
  reporting the missing dependency.

## Consequences

### Positive

- **Standard, well-tested engines for both families.** No hand-written schema validator.
- **The JSON gate agrees with the runtime in both directions.** It passes what the runtime reads
  and reports what the runtime drops or rejects — a lowercase key, an enum name, a vanished
  component — which neither the schemas literally nor DGF's MCP can do.
- **`/dgf-doctor` keeps working with nothing installed**, and can say exactly what is missing.
- **The validators work after `dgf-factory setup`**, with no manual step, and each project has its own
  pinned versions.

### Negative

- **Setup needs network access and a Python 3.9+ interpreter** to build the environment. Without
  either, the first gate a new user runs fails with exit `3` until the printed command is run.
- **Every script now starts twice** when the system `python3` is not the project's: once to switch
  interpreter, once to run.
- **A teammate who clones must build the environment**, because it is not committed.
- **The pre-pass, the reader rules and the dispatch tables are ours to maintain.** If NJsonSchema
  changes how it emits inheritance, or DGF adds a converter or a component, the validator
  silently stops matching. The fixtures, the known-good corpus and the provenance drift check are
  the only guards.
- **The reader rules are the part most likely to be wrong.** A rule that is too loose passes
  configuration the runtime rejects; one that is too strict fails configuration it loads. Either
  is a defect, and only the known-good corpus finds the second kind.
- **The converter prefix match is order-dependent.** Where it is ambiguous, the validator uses
  the class whose constructor binds the `ComponentType`, and says so. That is a reading of DGF's
  intent, not a guarantee of what the runtime picks.
- **Unknown properties warn.** A misspelt property is no longer blocked; it is reported and
  ignored, exactly as the runtime ignores it. Common warnings get ignored.
- **The validator disagrees with DGF's MCP**, in both directions. That is intended, but it has to
  be explained every time it happens.
- **`profile.xsd` stays unchecked** until DGF fixes the schema.
- **Python 3.9 is end-of-life upstream.** Pinned packages will eventually drop 3.9, and the floor
  will have to move, by a new ADR.

### Follow-ups

- Milestone 8 delivered `scripts/requirements.txt`, the pre-pass, the reader rules, the dispatch and
  the doctor's dependency probe; this ADR does not reopen them.
- The npm delivery milestone: `scripts/lib/runtime.py` and its call in every entry script, the
  `install_command()` change in `deps.py` and its duplicate in `doctor.py`, and the Python step in
  `dgf-factory setup`.
- Report upstream to the DGF team: `profile.xsd` L20-21 is invalid XSD; the `Type` description
  says lowercase fails, and the runtime accepts it; the MCP serves the NJsonSchema export and
  never indexes the DataSource schemas; `HeaderConfiguration` binds `ComponentType.Footer`; and
  `SchemaValidationService.cs` attributes to draft-04 a merge the draft-04 specification does not
  define.
- **What would reverse this:** a requirement that the gate match DGF's MCP exactly, or evidence
  that the reader rules cannot reproduce the runtime's. Either points to the .NET alternative
  above, or to vendoring the `ExportWith_SystemTextJson` output once DGF publishes it.
