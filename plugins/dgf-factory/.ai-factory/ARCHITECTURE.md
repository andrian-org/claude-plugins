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
- **Tech stack:** Markdown (prompt-as-program), Python 3 and Node.js (`.mjs`) for
  validators, packaged as a Claude Code plugin.
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
│   ├── dgf/                            # Setup slice
│   │   └── SKILL.md
│   │
│   ├── dgf-component/                  # Slice: component scaffold / inspect / validate
│   │   ├── SKILL.md                    #   the prompt-program (steps, gates, STOP rules)
│   │   ├── references/                 #   facts only this slice cites
│   │   │   └── component-contract.md
│   │   ├── scripts/                    #   validators only this slice calls
│   │   │   └── validate_component.py
│   │   └── templates/                  #   output shapes this slice emits
│   │       └── component-report.md
│   │
│   ├── dgf-plan/                       # Slice: fast / full / ultra planning
│   │   └── SKILL.md
│   ├── dgf-implement/                  # Slice: the execution state machine
│   │   └── SKILL.md
│   └── dgf-verify/                     # Slice: emits dgf-gate-result
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
│   ├── schema-families.md              #   JSON vs XSD: parity, correspondence, resolution
│   └── schemas/                        #   vendored copies, version-stamped
│       ├── MANIFEST.md                 #     DGF version, date, per-file dialect and membership
│       ├── json/                       #     generated *.schema.json (modern component config)
│       ├── xsd/                        #     the 9 *.xsd + form.reference.json (legacy XML)
│       └── standalone/                 #     hand-authored contracts from DGF docs/schemas/
│
├── scripts/                            # ── SHARED INFRASTRUCTURE ── cross-slice validators
│   ├── validate_config.py              #   dual-dispatch: JSON Schema or XSD, by family
│   ├── resolve_components.py           #   every referenced component exists
│   └── lib/
│       ├── detect_family.py            #   JSON vs XSD resolution + runtime-parity lookup
│       └── gate_result.py              #   emits the dgf-gate-result block
│
├── .mcp.json                           # MCP servers (DGF docs MCP only)
│
│   ── NOT SHIPPED ── everything below is maintainer material
├── tools/                              # ── MAINTENANCE ── run by contributors, never by a skill
│   ├── check-dual-schema-docs.sh       #   documentation and decision-record contracts
│   ├── check_knowledge_stamps.py       #   stamps, ledgers, vendored-schema digests
│   └── vendor_schemas.py               #   re-vendors DGF's schemas, rewriting DGF paths
├── provenance/                         # ── PROVENANCE ── where each knowledge fact came from
│   └── knowledge/                      #   one ledger per knowledge file, same relative path
│       └── schemas/MANIFEST.md         #     DGF commit, upstream + shipped sha256 per file
├── docs/                               # documentation, the blueprint, ADRs (docs/adr/)
├── AGENTS.md                           # navigation index
└── .ai-factory/                        # pipeline artifacts
```

The tree is the target shape. Today only `skills/dgf-doctor/`, `knowledge/`, `tools/`,
`provenance/` and the files around them exist. The other slices, `agents/`, and the shared
validators in `scripts/` arrive with roadmap milestones 8 onward, and `scripts/` is absent
until then.

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
- ✅ A slice hands work to another slice by **invoking it as a command** (`/dgf-verify`)
  or by **writing an artifact** the other slice reads
- ❌ A slice reads another slice's `references/`, `scripts/` or `templates/` directly —
  that is reaching into internals. Promote the shared material to `knowledge/` or
  `scripts/` instead.
- ❌ Anything in `knowledge/` mentions a skill, a step number or a pipeline stage.
  Knowledge states DGF facts; it does not know who reads it.
- ❌ A shared script imports from a slice, or branches on which skill called it
- ❌ A validator or skill that handles only one schema family. DGF configurations are
  authored in modern JSON **and** legacy XML; a single-family consumer silently passes
  everything in the other family.
- ✅ A maintenance tool in `tools/` reads `knowledge/`, `provenance/` and a DGF checkout,
  and may import a shipped script to share one definition — `vendor_schemas.py` imports
  `doctor.py`'s `DGF_PATH_PATTERN`
- ❌ A shipped file reads, calls or links anything in `tools/` or `provenance/`. They are
  not part of what a developer runs, and the direction is maintainer → shipped only.
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

### A slice calling its own validator (self-containment)

```markdown
---
name: dgf-component
description: Scaffold, inspect or validate a DGF component against the catalogue. Use for "add component", "check component", "is this component valid".
argument-hint: "[scaffold | inspect | validate] <component-name>"
allowed-tools: Read Write Glob Grep Bash(python3 *) AskUserQuestion
disable-model-invocation: false
version: 1.0.0
---

# DGF Component

## Workflow

### Step 2: Validate the declaration

Run the slice's own validator. Do not assess the declaration by reading it.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-component/scripts/validate_component.py" <path>
```

Exit codes are a contract:

| code | meaning | action |
|---|---|---|
| 0 | valid | continue to Step 3 |
| 1 | invalid | **STOP.** Report each finding verbatim. Do not repair silently. |
| 2 | warnings | continue, surface every warning to the user |
| 3 | usage error | **STOP.** The call is wrong; fix the invocation. |

### Step 3: Confirm against the catalogue

Read `${CLAUDE_PLUGIN_ROOT}/knowledge/component-catalogue.md`.
If the component is absent from the catalogue, STOP and report it as unknown —
never infer a contract from a name.
```

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
    # validate against JSON schemas the runtime never reads.
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
  `_workflow.xml` and `_process.xml`. Schema availability is not runtime parity.
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
