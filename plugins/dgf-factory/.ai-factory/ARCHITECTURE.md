# Architecture: Structured Modules (Vertical Slices)

## Overview

`dgf-factory` is organised as a set of **self-contained vertical slices**, where one
slice is one skill. A skill directory owns everything it needs to run — its
prompt-program (`SKILL.md`), the DGF facts it cites (`references/`), the deterministic
validators it calls (`scripts/`), and its output shapes (`templates/`). Skills are
discovered independently, invoked independently, and can be added or removed without
touching each other.

What the slices share sits in exactly two places: a plugin-level `knowledge/` tree
holding the versioned DGF facts that more than one skill needs, and a plugin-level
`scripts/` tree holding validators that more than one skill calls. Everything else is
local to a slice. Maintainer material — the checks contributors run, and the record of
where each DGF fact came from — sits beside the slices in `tools/` and `provenance/`, and
is never shipped. This is the Structured Modules trade-off — soft boundaries and fast
authoring rather than enforced ports and adapters — which is the right level of
formalism for a corpus that has no runtime and no dependency injection to invert.

The folder names below are Claude Code plugin names, not the reference pattern's
`src/[ModuleName]/Slices/` names. Auto-discovery only loads components from
`.claude-plugin/plugin.json`, `skills/<name>/SKILL.md`, `agents/*.md`, `commands/*.md`,
`hooks/hooks.json` and `.mcp.json`; a tree that ignores those paths is a tree Claude
Code never loads. The pattern's boundary and dependency rules are kept in full — only
the folder vocabulary is translated.

## Decision Rationale

- **Project type:** Claude Code plugin — a corpus of Markdown prompt-programs plus
  deterministic validator scripts. No compile step, no runtime, no database.
- **Tech stack:** Markdown (prompt-as-program), Python 3.9+ (`lxml`, `jsonschema`) and
  Node.js (`.mjs`) for validators, packaged as a Claude Code plugin.
- **Key factor:** **feature independence is very high.** Every skill is auto-discovered
  and fires on its own description; nothing calls a skill as a function. Slices that own
  their material end-to-end match that reality, while a technical-layer split would
  scatter one skill's prompt, facts and validator across three trees for no benefit.
- **Secondary factor:** domain complexity is high and concentrated in the DGF knowledge,
  so knowledge gets a first-class home with its own rules rather than being inlined into
  prompts.
- **Why not Explicit Architecture:** its value is enforcing domain purity across a
  dependency-inverted runtime. There is no runtime here to invert, so the ceremony buys
  nothing a review of `knowledge/` would not catch.

## Folder Structure

```text
plugins/dgf-factory/
├── .claude-plugin/
│   └── plugin.json                     # ── MANIFEST ── required, must live here
│
├── skills/                             # ── SLICES ── one directory per skill
│   ├── dgf-doctor/                     # Slice: plugin install check (exists today)
│   │   ├── SKILL.md
│   │   └── scripts/doctor.py           #   owns SHIPPED_DIRS and the DGF_PATH check
│   │
│   ├── dgf/                            # Setup slice (exists)
│   │   ├── SKILL.md
│   │   └── references/                 #   config-template.yaml, description-template.md
│   │
│   ├── dgf-plan/                       # Slice: fast / full / ultra planning (exists)
│   │   ├── SKILL.md
│   │   └── references/                 #   PLAN-FORMAT.md, ULTRA-FORMAT.md
│   ├── dgf-implement/                  # Slice: the execution state machine (exists)
│   │   ├── SKILL.md
│   │   └── references/                 #   IMPLEMENTATION-GUIDE.md
│   ├── dgf-verify/                     # Slice: relays verify_gate.py's dgf-gate-result (exists)
│   │   ├── SKILL.md
│   │   └── references/                 #   GATE-RESULT-CONTRACT.md
│   ├── dgf-commit/                     # Slice: conventional commits scoped by workspace (exists)
│   │   └── SKILL.md
│   ├── dgf-fix/                        # Slice: fix inside the plan's scope, write a patch (exists)
│   │   ├── SKILL.md
│   │   └── references/                 #   PATCH-FORMAT.md
│   ├── dgf-evolve/                     # Slice: distil patches into skill-context overrides (exists)
│   │   ├── SKILL.md
│   │   └── references/                 #   OVERRIDE-FORMAT.md
│   ├── dgf-component/                  # Slice: inspect / validate / scaffold a component (exists)
│   │   └── SKILL.md                    #   the prompt-program (steps, gates, STOP rules)
│   ├── dgf-process/                    # Slice: inspect / validate / author / modify a process (exists)
│   │   ├── SKILL.md
│   │   └── templates/                  #   output shapes this slice emits: process.xml, _workflow.xml
│   ├── dgf-model/                      # Slice: inspect / validate / add / modify an entity (exists)
│   │   ├── SKILL.md
│   │   └── templates/                  #   settings.xml
│   └── dgf-audit/                      # Slice: read-only — the root's health, and blast radius (exists)
│       └── SKILL.md
│
├── agents/                             # ── SUBAGENTS ── coordinator, workers, sidecars
│   ├── dgf-implement-coordinator.md
│   └── dgf-implement-worker.md
│
├── knowledge/                          # ── SHARED DOMAIN ── the DGF knowledge base
│   ├── README.md                       #   how to cite, date and version-stamp a fact
│   ├── component-catalogue.md          #   the 34 IComponentService<TSource> registrations, and why 4 other counts differ
│   ├── composition-specs.md            #   declarative XML/JSON composition + EventBase verbs
│   ├── naming-conventions.md
│   ├── schema-families.md              #   JSON vs XSD: parity (67 rows), correspondence, resolution
│   ├── json-reader.md                  #   how the runtime reads component JSON; dispatch, folders, file refs
│   ├── process-model.md                #   process.xsd vs the runtime model; reference resolution
│   ├── data-model.md                   #   entities, fields, relations; what each model loader does
│   ├── reference-graph.md              #   the reference-edges table: every reference, its rule, Reach
│   ├── permissions.md                  #   where the root names roles; nothing in it declares one
│   └── schemas/                        #   vendored copies, version-stamped
│       ├── MANIFEST.md                 #     DGF version, date, per-file dialect and membership
│       ├── json/                       #     generated *.schema.json (modern component config)
│       ├── xsd/                        #     the 9 *.xsd + form.reference.json (legacy XML)
│       └── standalone/                 #     hand-authored contracts from DGF docs/schemas/
│
├── scripts/                            # ── SHARED INFRASTRUCTURE ── cross-slice validators
│   ├── validate_config.py              #   family first, schema read the runtime's way, parity gate
│   ├── resolve_components.py           #   component types legal; referenced component files exist
│   ├── validate_process.py             #   process structure + semantics; CHANGE_STATE targets
│   ├── validate_model.py               #   the model's references, each loader's way; a form's cells
│   ├── route_means.py                  #   ADR 0010's order of means: JSON or legacy XML
│   ├── locate_plan.py                  #   the workspaces root and the active plan (ADR 0017)
│   ├── inventory_root.py               #   each workspace, counted; what is not a workspace
│   ├── check_plan.py                   #   a plan's header, tasks, Commit Plan, file classes, routes, overlaps
│   ├── check_change.py                 #   a change against its plan and the merge-base (ADR 0018)
│   ├── verify_gate.py                  #   the verify gate: every check, the status computed, one block
│   ├── check_patches.py                #   the patch format; which patches the cursor has not seen
│   ├── check_override.py               #   may a skill read its override — shape, sources, forbidden, limit
│   ├── audit_root.py                   #   the whole-root audit, and blast radius per application
│   ├── requirements.txt                #   lxml + jsonschema, exact pins with hashes
│   └── lib/                            #   one module per concern
│       ├── report.py                   #     findings, codes → exit codes, verdict, DEBUG trace
│       ├── deps.py                     #     missing lxml/jsonschema → exit 3 with the install command
│       ├── knowledge.py                #     machine-read table loader — stdlib, no package imports
│       ├── cli.py                      #     argument parsing (usage = exit 3), the directory walk
│       ├── family.py                   #     JSON vs XSD resolution, from bytes
│       ├── json_reader.py, prepass.py  #     the runtime's JSON reader; NJsonSchema allOf merge
│       ├── json_resolve.py             #     which schema a JSON file is read against
│       ├── json_validate.py            #     jsonschema extended with the reader semantics + dispatch
│       ├── xsd.py                      #     grammar selection, two-pass process.xml, XSD lag
│       ├── parity.py                   #     the runtime-parity gate
│       ├── workspace.py                #     workspaces-root model, exact-case reference resolution
│       ├── process_checks.py           #     dead transitions, reachability, workflow/change-state refs
│       ├── plan.py                     #     the plan file's header, tasks, Commit Plan; each path's class and artifact
│       ├── git.py                      #     read-only git calls; a commit's tree written blob by blob
│       ├── runner.py                   #     every validator over a root or some of its files
│       ├── baseline.py                 #     which findings a branch introduced (merge-base comparison)
│       ├── model.py                    #     each model loader's resolution rule; a form's bound cells
│       ├── edges.py                    #     one file's references, row by row of reference-edges
│       ├── graph.py                    #     the reference graph of one application; reach, referrers
│       ├── roles.py                    #     the role names a root uses, split as the runtime splits them
│       ├── gate_result.py              #     builds every dgf-gate-result block — stdlib, no package imports
│       ├── patches.py                  #     the patch file and the patch cursor
│       └── overrides.py                #     the override template, FORBIDDEN constructs, LIMIT_WORDS
│
├── .mcp.json                           # MCP servers (DGF docs MCP only)
│
│   ── NOT SHIPPED ── everything below is maintainer material
├── tests/                              # ── TESTS ── unittest suite; fixtures/unit/, fixtures/known-bad/
├── tools/                              # ── MAINTENANCE ── run by contributors, never by a skill
│   ├── check-dual-schema-docs.sh       #   doc, decision-record, manifest, stamp contracts; runs tests/
│   ├── check_knowledge_stamps.py       #   stamps, ledgers, vendored-schema digests
│   ├── vendor_schemas.py               #   re-vendors DGF's schemas, rewriting DGF paths
│   ├── run_known_good.py               #   every validator over DGF's samples, held to the exceptions file
│   ├── known-good-exceptions.txt       #   evidenced excuses + the warning baseline
│   ├── check_drift.py                  #   provenance ledgers' digests against a DGF checkout
│   └── requirements.in                 #   the validator dependencies, compiled with uv
├── provenance/                         # ── PROVENANCE ── where each knowledge fact came from
│   └── knowledge/                      #   one ledger per knowledge file, same relative path
│       └── schemas/MANIFEST.md         #     DGF commit, upstream + shipped sha256 per file
├── docs/                               # documentation, the blueprint, ADRs (docs/adr/)
├── AGENTS.md                           # navigation index
└── .ai-factory/                        # pipeline artifacts
```

The tree is the target shape. Today `skills/dgf-doctor/`, the five spine slices (`dgf`,
`dgf-plan`, `dgf-implement`, `dgf-verify`, `dgf-commit`), the learning loop's two (`dgf-fix`,
`dgf-evolve`), the four DGF-specific slices (`dgf-component`, `dgf-process`, `dgf-model`,
`dgf-audit`), `knowledge/`, `scripts/`, `tests/`, `tools/`, `provenance/` and the files around
them exist. `dgf-scaffold`, blocked until the estate's bootstrap template is identified
([ADR 0023](../docs/adr/0023-dgf-specific-skills.md) §7), and `agents/` arrive later. Every gate block is
built by `lib/gate_result.py` and printed by a script — `verify_gate.py` for `/dgf-verify`,
`doctor.py` for `/dgf-doctor` — and the skill relays it
([ADR 0022](../docs/adr/0022-gate-block-contract-revised.md)).

Root `knowledge/` and `scripts/` are not auto-discovered — they are plain files, reached
from a slice by `${CLAUDE_PLUGIN_ROOT}/knowledge/...` and
`${CLAUDE_PLUGIN_ROOT}/scripts/...`. That is deliberate: only things Claude Code must
load automatically live in a discovered directory.

**Shipped and maintainer material are kept apart, by directory.** What ships is exactly
the directories `doctor.py` lists in `SHIPPED_DIRS`: `skills/`, `agents/`, `commands/`,
`scripts/`, `knowledge/` and `.claude-plugin/`. A developer's install has no DGF
checkout, so no shipped file names a path into the DGF repository
([ADR 0012](../docs/adr/0012-no-dgf-paths-in-shipped-files.md)). That is why
repo-maintenance checks live in `tools/`, not `scripts/`: they run against a DGF checkout
and may name its paths. It is also why a knowledge fact's DGF source paths and digests live
in its `provenance/` ledger, not in the fact file
([ADR 0013](../docs/adr/0013-version-gating-provenance-ledger.md)). Both kinds of script
follow the same exit-code contract; they differ in who runs them and whether they ship.

## Dependency Rules

The flow is strictly one-directional: **`SKILL.md` → its own `references/` and `scripts/`
→ shared `knowledge/` and `scripts/` → nothing.** Inner material never reaches back out.

- ✅ A `SKILL.md` reads its own `references/`, `templates/`, and calls its own `scripts/`
- ✅ A `SKILL.md` reads `${CLAUDE_PLUGIN_ROOT}/knowledge/` and calls
  `${CLAUDE_PLUGIN_ROOT}/scripts/`
- ✅ A shared script reads `knowledge/schemas/json/`, `knowledge/schemas/xsd/` and
  `knowledge/schemas/standalone/`
- ✅ A shared script reads a knowledge fact only through a **machine-read table**, found by
  its `<!-- machine-read: <id> -->` marker and loaded by `scripts/lib/knowledge.py`
  (`knowledge/README.md` §7). The marker is the only coupling. The knowledge file still names
  no script, and a malformed table is exit `3`, never a fallback. The one exception is
  `reference-edges`' `Checked by` column, which names the validator that reports an unresolved edge
  so that the audit does not report it twice ([ADR 0023](../docs/adr/0023-dgf-specific-skills.md)
  §4–§5) — a validator's file name, never a skill or a pipeline stage
- ✅ A slice's own script may load a shared library module by path: `doctor.py` loads
  `scripts/lib/knowledge.py` to check every table, and `scripts/lib/gate_result.py` — from its
  own plugin, never the root it checks — to build its gate block. That is why both are
  stdlib-only and import nothing from their own package
- ✅ A slice hands work to another slice by **invoking it as a command** (`/dgf-verify`)
  or by **writing an artifact** the other slice reads
- ❌ A slice reads another slice's `references/`, `scripts/` or `templates/` directly —
  that is reaching into internals. Promote the shared material to `knowledge/` or
  `scripts/` instead.
- ❌ Anything in `knowledge/` mentions a skill, a step number or a pipeline stage.
  Knowledge states DGF facts; it does not know who reads it.
- ❌ A shared script imports from a slice, branches on which skill called it, or lists its callers.
  `check_override.py` takes `--skill` and knows no list of readers; the contract test holds which
  skills read an override ([ADR 0024](../docs/adr/0024-learning-loop-revised.md) §5)
- ✅ `/dgf-evolve` reads each target's shipped `SKILL.md`, read-only, to drop rules the skill
  already covers — the one file of another slice it reads, never its `references/` or `scripts/`.
  It writes only overrides under `.dgf-factory/`, never a shipped skill
- ❌ A validator or skill that handles only one schema family. DGF configurations are
  authored in modern JSON **and** legacy XML; a single-family consumer silently passes
  everything in the other family.
- ✅ A maintenance tool in `tools/` reads `knowledge/`, `provenance/` and a DGF checkout,
  and may import a shipped script to share one definition. `vendor_schemas.py` imports
  `doctor.py`'s `DGF_PATH_PATTERN`; `run_known_good.py` imports `scripts/lib/` and the
  validator modules to run them over DGF's samples; `check_drift.py` loads
  `check_knowledge_stamps.py`'s ledger parser instead of re-implementing it. `run_known_good.py`
  runs the validators through `scripts/lib/runner.py`, the runner `check_change.py` uses, so the
  known-good corpus and the change gate cannot drift apart
- ❌ A shipped file reads, calls, imports or links anything in `tools/`, `tests/` or
  `provenance/`. They are not part of what a developer runs, and the direction is maintainer →
  shipped only.
- ❌ A shipped file names a DGF repository path — `src/…`, `docs/wiki/…`, a checkout
  folder. Cite the knowledge base, a DGF docs MCP call (`get_doc_page('<page>')`) or a DGF
  type name. `doctor.py` blocks on it as `DGF_PATH`.
- ❌ Circular invocation — slice A invokes B, B invokes A. Route through an artifact.
- ❌ Absolute paths, `~/` or working-directory-relative paths anywhere. Always
  `${CLAUDE_PLUGIN_ROOT}`.

## Layer/Module Communication

Slices do not call each other as functions. They communicate through three mechanisms
only:

- **Artifacts.** Each `.dgf-factory/` artifact has exactly one owning slice; every other
  slice treats it as read-only input. `/dgf-plan` writes the plan, `/dgf-implement` reads
  it and updates only the checkbox ledger, `/dgf-verify` reads both.
- **Gate blocks.** A quality slice ends its human-readable report with one fenced
  `dgf-gate-result` JSON block. Callers parse the **last** such block and nothing else —
  never the prose above it.
- **Command invocation.** A slice may invoke another as a command when the user's flow
  calls for it, but never reaches into its files.

Shared `knowledge/` is read-only to every slice. It changes through a deliberate edit,
with its `provenance/` ledger updated in the same change, never as a side effect of
running the pipeline. The vendored schemas change only through `tools/vendor_schemas.py`.

## Key Principles

1. **One skill, one slice, one job.** If a skill needs facts or a validator, they live in
   its directory until a second skill needs them — then they move up to `knowledge/` or
   `scripts/`. Promote on the second use, not in anticipation of it.
2. **Knowledge is the asset; the pipeline is copyable.** The DGF facts in `knowledge/`
   are what makes this plugin worth having. Every fact carries the date and the DGF
   version it was read from. Its DGF source files and their digests are in its
   `provenance/` ledger; the shipped fact names its source by DGF type, file name or MCP
   call.
3. **Determinism before prompting.** If a JSON Schema, an XSD, or a script can decide a
   question, write the script. A statically checkable rule encoded as a prompt instruction
   is a defect, not a shortcut.
4. **Two families, one contract — asymmetric today.** DGF supports modern JSON component
   configuration and legacy XML, so every component-schema consumer resolves the family
   first and handles both. And because schema availability is not runtime parity, a
   passing validation in a family the runtime does not read is not a success: `Workflow`
   and `ProcessFlow` validate against their JSON schemas while the runtime reads only XML.
   See [`docs/dgf-schemas.md`](../docs/dgf-schemas.md).
5. **Single-writer artifacts.** Exactly one slice owns each artifact. Two slices writing
   the same file silently destroy each other's work across sessions.
6. **Soft boundaries, honest ones.** Structured Modules does not enforce isolation
   mechanically — nothing stops one slice reading another's files. The boundary holds
   because review holds it. Promoting shared material is cheap; a tangle of cross-slice
   reads is not.
7. **The executor never re-decides.** When a plan bundle conflicts with the current code,
   the executing slice stops and reports the drift. Re-deciding architecture at execution
   time defeats the reason the bundle was written by a stronger model.
8. **What ships stands alone.** A developer's install holds the shipped directories and
   the hosted DGF docs MCP, nothing more. Every path in a shipped file resolves inside the
   plugin or on the MCP; everything that needs a DGF checkout is maintainer material.

## Code Organization Note

- **New Features:** All new code should follow the architecture defined in this document
  where practical.
- **Existing Code:** Document the current structure as-is. When modifying existing code,
  prefer following the architectural conventions in this document, but do not force a
  rewrite of unrelated code.
- **Interoperability:** When new code must call existing code, prefer clean interfaces but
  do not refactor purely for structural alignment.

Specifically: the `aif-*` corpus in `.claude/` is a managed AI Factory install tracked in
`.ai-factory.json`. It is reference material and the pipeline that builds this plugin —
it is not part of the plugin's own architecture and must not be hand-edited or forked.

## Code Examples

### A slice calling the shared validators (as built: `/dgf-process`)

A slice owns its prompt and its templates, and calls the shared `scripts/` for every decision a
script can make. It pre-approves only those scripts — never `Bash(python3 *)`, which would also
pre-approve `python3 -c …` — and each call has an exit table. From `skills/dgf-process/SKILL.md`:

```markdown
---
name: dgf-process
description: Inspect, validate, author or modify a DGF process or workflow — … Use for "add a process", "new workflow", "change this workflow", "check this process", "what calls this workflow", "blast radius of this workflow".
argument-hint: "[inspect | validate | author | modify] <process, workflow or file>"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__get_xml_property_reference …
disable-model-invocation: false
version: 0.1.0
---

### Step 5: Scope — decided by the script, before the write

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed A:<file> --skip-validators

| Exit | Action |
|---|---|
| `0` | Continue to Step 6. |
| `1` | A `CHANGE_*` error. **STOP** before writing anything: `/dgf-plan` widens the plan. |
| `2` | `CHANGE_UNPLANNED_FILE` → the gate will warn on this file. … |
| `3` | **STOP** and relay it. |

### Step 6: Write

Start from `${CLAUDE_PLUGIN_ROOT}/skills/dgf-process/templates/process.xml`, and replace every
`Example`. Take every fact from `knowledge/process-model.md` and `knowledge/reference-graph.md`.
```

The template is the slice's own; the scope check, the validators and the knowledge are shared.
`tests/test_skill_templates.py` proves each template passes its validator, and
`tests/test_skill_contracts.py` holds every script call to the skill's own `Bash(…)` rule.

### A shared validator (dependency rule + dual dispatch)

The validator reads the shared schemas and knows nothing about its caller — no skill name,
no step number, no branch on who invoked it. It resolves the schema **family** before
parsing, never assumes JSON, and treats a format the runtime does not read as a warning
rather than a success.

```python
#!/usr/bin/env python3
"""Validate a DGF component configuration against its family's schema.

DGF configurations come in two families: modern JSON component config and legacy
XML validated by XSD. The family is resolved from the document itself, never assumed.

Exit codes: 0 valid | 1 invalid | 2 warnings | 3 usage error
"""

import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = PLUGIN_ROOT / 'knowledge' / 'schemas'


def fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(code)


def detect_family(raw: str) -> str:
    """Return 'xsd', 'json', or 'unknown'. Never guess."""
    stripped = raw.lstrip()
    if stripped.startswith('<'):
        return 'xsd'
    try:
        json.loads(raw)
    except ValueError:
        return 'unknown'
    return 'json'


def main() -> None:
    if len(sys.argv) != 2:
        fail(3, 'Usage: validate_config.py <config-path>')

    config_path = Path(sys.argv[1])
    if not config_path.is_file():
        fail(3, f'Config not found: {config_path}')

    raw = config_path.read_text(encoding='utf-8')
    family = detect_family(raw)
    if family == 'unknown':
        fail(3, f'Cannot resolve schema family for {config_path}; refusing to assume JSON.')

    if family == 'json':
        # Dialect comes from the schema's own $schema — the set mixes draft-04 and draft-07.
        errors, warnings = validate_json(raw, SCHEMAS / 'json')
    else:
        errors, warnings = validate_xsd(raw, SCHEMAS / 'xsd')

    # Schema-valid is not the same as runtime-supported: Workflow and ProcessFlow
    # validate against JSON schemas the runtime never reads. The gate reads the shipped
    # parity table, knowledge/schema-families.md §6 — all 67 format-coverage.md rows
    # (ADR 0011) — for the top-level component only: a ✗ row is PARITY_NOT_RUNTIME and a
    # ◐ row PARITY_PARTIAL, both exit 2. XML artifacts are what the runtime reads.
    warnings += runtime_parity_warnings(raw, family)

    for error in errors:
        print(f'ERROR {error}')
    for warning in warnings:
        print(f'WARN  {warning}')

    if errors:
        sys.exit(1)
    if warnings:
        sys.exit(2)

    print('VALID')


if __name__ == '__main__':
    main()
```

Note the direction: `scripts/` reads `knowledge/`, never the reverse, and never a slice.

The sketch shows the shape only. The real `scripts/validate_config.py` is a composition of
`scripts/lib/` modules. It reads bytes rather than text, strips JSON comments, and resolves
the family by declaration or by vendored root element (`docs/dgf-schemas.md` §7). It also
reads JSON the way the runtime does (ADR 0015).

## Anti-Patterns

- ❌ **DGF facts inlined in a `SKILL.md`.** The moment a component name, a verb or a
  binding rule is written into a prompt, it stops being versioned and starts drifting.
  Facts live in `knowledge/`; prompts cite them.
- ❌ **Reaching into another slice.** `skills/dgf-plan/` reading
  `skills/dgf-component/references/` couples two slices invisibly. Promote to
  `knowledge/` instead.
- ❌ **A prompt doing a script's job.** "Check that every referenced component exists" as
  an instruction, when `resolve_components.py` can decide it and cannot forget to.
- ❌ **Assuming a configuration is JSON.** A consumer that only parses JSON silently passes
  every legacy XML configuration. Failing loudly on an unresolved family is correct;
  defaulting to JSON is not.
- ❌ **Treating a passing JSON validation as runtime support.** `Workflow` and
  `ProcessFlow` validate against their JSON schemas while the runtime reads only
  `_workflow.xml` and `process.xml`. Schema availability is not runtime parity.
- ❌ **Validating JSON with a strict, case-sensitive validator.** The runtime matches property
  and enum names in any case and ignores unknown properties, so a strict check fails configs
  the runtime serves. Read it the runtime's way ([ADR 0015](../docs/adr/0015-validator-runtime-and-json-reader.md)).
- ❌ **Excusing a validator gap in `tools/known-good-exceptions.txt`.** An exception records a
  sample defect with its runtime code path; a validator that disagrees with the runtime is
  fixed instead.
- ❌ **Inferring the JSON counterpart of an XSD from its filename.** The correspondence is
  partial and evidence-based — `options.xsd` is *not* `StaticOptionsDataSource`. Use the
  map in [`docs/dgf-schemas.md`](../docs/dgf-schemas.md).
- ❌ **Assuming one JSON Schema dialect.** The vendored set mixes draft-04 (generated) and
  draft-07 (hand-authored). Select the validator from each file's own `$schema`.
- ❌ **Knowledge that knows the pipeline.** A file in `knowledge/` that says "in Step 3 of
  `/dgf-implement`…" has inverted the dependency and will rot when the step renumbers.
- ❌ **Multiple writers on one artifact.** Two slices updating the same checkbox ledger
  lose work silently across sessions.
- ❌ **Parsing prose instead of the gate block.** Scraping a report's wording rather than
  reading the last fenced `dgf-gate-result` block breaks on the first rewording.
- ❌ **Hardcoded paths.** `/Users/...`, `~/plugins/...` or `./scripts/...` all break once
  the plugin is installed somewhere else. Use `${CLAUDE_PLUGIN_ROOT}`.
- ❌ **DGF repository paths in a shipped file.** "From `src/Core/…/WorkspaceSettings.cs`" in a
  knowledge file points at nothing on a developer's machine. Name the type, and put the path
  in the file's `provenance/` ledger.
- ❌ **A maintenance tool in `scripts/`.** `scripts/` ships. A check that runs against a DGF
  checkout belongs in `tools/`.
- ❌ **Hand-editing a vendored schema.** The shipped digest no longer matches the ledger, and
  `tools/check_knowledge_stamps.py` fails. Re-vendor with `tools/vendor_schemas.py`.
- ❌ **Forking an `aif-*` skill.** They are installer-managed; edits are detected and
  overwritten on update.
