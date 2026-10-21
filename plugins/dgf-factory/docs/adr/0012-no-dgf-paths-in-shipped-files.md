---
id: 0012
title: Shipped files carry no DGF repository paths
status: accepted
date: 2026-09-23
deciders: [Andrian Mamei]
supersedes: []
tags: [packaging, portability, knowledge]
---

# 0012 — Shipped files carry no DGF repository paths

**Status: accepted** (2026-09-23, Andrian Mamei).

## Context

Read from this repository on **2026-09-23**.

**The decider's rule**, stated 2026-09-23: *"NO DGF paths must be in files that will be installed
by developers."*

**Why it matters.** A developer who installs this plugin works in DGF workspaces. Nothing in the
install tells them where a DGF framework checkout is, and nothing requires one:
[ADR 0001](0001-independent-plugin-with-ai-factory-derived-architecture.md) makes the plugin
self-contained, and `.mcp.json` declares the hosted DGF docs MCP. A path such as
`src/Core/DGF.Kernel/WorkspaceSettings.cs` resolves to nothing on a developer's machine.

**"Shipped" is already defined.** `skills/dgf-doctor/scripts/doctor.py:47` lists
`SHIPPED_DIRS = ("skills", "agents", "commands", "scripts", "knowledge", ".claude-plugin")`.
`.claude/` is excluded there because the aif-* corpus is installer-managed and does not ship
(ADR 0001 §2). `doctor.py:298-312` already warns on machine-specific absolute paths in those
directories. It did not look for DGF repository paths.

**What the shipped directories held** before this ADR:

| Where | Lines with a DGF path | Why |
|---|---|---|
| `skills/`, `.claude-plugin/` | 0 | — |
| `knowledge/*.md` frontmatter `sources` | 58 | [ADR 0008](0008-version-gating-revised.md) §1 required every fact file to name its DGF sources by path |
| `knowledge/*.md` prose | 22 | Citations such as "From `src/Core/DGF.Kernel/WorkspaceSettings.cs`" |
| `knowledge/schemas/MANIFEST.md` | 174 | Upstream path and `sha256` per vendored file, and the re-vendor commands |
| Vendored schemas | 121 | DGF's own text. 60 JSON schemas name `docs/wiki/Components/Behavior/Validators.md` twice; `xsd/form.xsd:273` names `src/Core/DGF.Domain/Data/Form/ComponentEvent.cs` |
| `scripts/check-dual-schema-docs.sh` | 3 | A repo-maintenance check that sat in a shipped directory |

The accepted [ADR 0010](0010-dgf-implement-scope.md), as first written, told the shipped
`/dgf-implement` to read DGF's `format-coverage.md`. It was corrected by erratum the same day.

**The MCP resolves DGF wiki pages by name.** `get_doc_page('AI-Authoring/format-coverage.md')`
and `get_doc_page('Components/Behavior/Validators.md')` both returned their pages on
2026-09-23. So a wiki citation has a form that works on a developer's machine. A source-file
citation has none: no MCP tool serves DGF source code.

## Decision

**No file under a shipped directory contains a path into the DGF repository. Shipped content
names a DGF source by knowledge file, MCP call, or type or file name. The paths, and the
digests that go with them, live in maintainer-only files. `doctor.py` blocks on a violation.**

### 1. What is shipped

Everything under the directories in `doctor.py`'s `SHIPPED_DIRS`. Everything else is maintainer
material: `docs/` (including these ADRs and the blueprint), `.ai-factory/`, `provenance/`,
`tools/`, `AGENTS.md`. Maintainer material keeps citing DGF paths. The ADR contract's rule that
Context cites file and line depends on it.

### 2. What counts as a DGF path

A path into the DGF repository:

- under one of its top-level `src/` or `docs/` folders;
- under the MCP's `Schemas/Json/`, `Schemas/XSD/` or `Schemas/XmlReference/` folders;
- or through a checkout folder named after the repository.

The exact list is `DGF_PATH_PATTERN` in `doctor.py`.

Not a DGF path:

- **Workspace layout paths** such as `FM/_COMPONENTS/` or `<workspace>/js/`. They describe the
  developer's own workspaces.
- **This plugin's own paths**, such as `knowledge/…` or `../docs/adr/…`.
- **A bare type or file name**, such as `WorkspaceSettings` or `format-coverage.md`.
- **An MCP argument**, such as `get_doc_page('AI-Authoring/format-coverage.md')`. It resolves on
  the hosted server.

### 3. What a shipped file cites instead

In order of preference:

1. The shipped knowledge base.
2. A DGF docs MCP call with its argument.
3. A DGF type or file name.

### 4. Where the paths go

- **Knowledge provenance moves to `provenance/`.** A knowledge file's `sources` move to a
  ledger at the same relative path under `provenance/`. That changes ADR 0008 §1, so
  [ADR 0013](0013-version-gating-provenance-ledger.md) supersedes ADR 0008 in full and holds the
  contract.
- **Vendored schemas are rewritten on the way in.** `tools/vendor_schemas.py` copies DGF's schema
  set and applies two rewrites:
  - `docs/wiki/<page>` becomes `get_doc_page('<page>')`;
  - any other DGF path is cut to its file name.

  Nothing else in a schema changes. The tool refuses to write when a DGF path survives or a
  rewritten file no longer parses. The schema ledger records both the upstream and the shipped
  digest of every file.
- **Maintainer tools do not ship.** Repo-maintenance checks move from `scripts/` to `tools/`.
  `scripts/` is for the validators skills call ([ADR 0007](0007-validator-runtime.md)).

### 5. Enforcement

`doctor.py` §4 reports `DGF_PATH` as an **error** (exit `1`) for every line of a shipped file
that matches `DGF_PATH_PATTERN`. `tools/check-dual-schema-docs.sh` runs the doctor in its
section 6, so a violation also blocks the documentation check. The pattern is built in pieces,
so `doctor.py` does not match its own check.

## Alternatives considered

- **Keep provenance in shipped frontmatter, as a metadata exception.** Rejected. The decider's
  rule has no exception, and a path in frontmatter still points at nothing on a developer's
  machine.
- **Replace paths with opaque source ids, in place.** Rejected. An id needs a lookup table, which
  is the ledger under another name, and a maintainer cannot read it.
- **Leave upstream schema text untouched, as DGF's own content.** Rejected. The rule is about what
  a developer installs, not about who wrote it. The rewrite is mechanical and recorded, and the
  upstream digest is still kept for drift detection.
- **A warning instead of an error.** Rejected. A warning lets the violation ship, and the rule
  says it must not.

## Consequences

### Positive

- Every path in a shipped file resolves on a developer's machine, or is plainly a name rather
  than a location.
- The rule is checked by script, not by review.
- `scripts/` holds only what skills call, so its contents match its place in `SHIPPED_DIRS`.

### Negative

- **Vendored schemas are no longer byte-identical to upstream.** A reader who diffs one against
  DGF sees the rewrite. Drift detection uses the recorded upstream digest, not the shipped file.
- **Shipped prose is less precise for a maintainer.** "DGF's `WorkspaceSettings` class" replaces
  a path and line number. The precision moved to the ledger, one step away.
- **The pattern is a list of DGF folder names.** A new top-level DGF folder is not caught until
  it is added to the list.
- **A bare file name is allowed and is not resolvable.** `format-coverage.md` on its own tells a
  developer what to look for, not where.
- **The rule covers `SHIPPED_DIRS`, not every file an install copies.** `docs/`, `.ai-factory/`,
  `provenance/` and `tools/` sit in the same plugin folder and still cite DGF paths. Making the
  whole folder clean would mean moving the maintainer material out of `plugins/dgf-factory/`.
  That is a further decision.

### Follow-ups

- Milestone 8's drift check reads the `provenance/` ledgers and runs as a maintainer tool against
  a DGF checkout ([ADR 0013](0013-version-gating-provenance-ledger.md) §5).
- Before the marketplace release, decide whether maintainer material must leave the plugin
  folder as well.

## Errata

Corrections of fact that do not change what this ADR decides. See
[the ADR contract](README.md) §"Errata".

- **2026-09-23** — §Context counted 121 lines with a DGF path in the vendored schemas. It is
  **181**. Each of the 60 JSON schemas also names `docs/Components/Behavior/Events.md`, which
  the first count's search did not cover, because it looked only under `docs/wiki/`,
  `docs/schemas/` (the three hand-authored standalone contracts) and `docs/Research/`. `DGF_PATH_PATTERN` covers every top-level `docs/`
  folder and caught it. That link is broken upstream: the page is under `docs/wiki/`. Source:
  the dry run of `tools/vendor_schemas.py`, and
  `provenance/knowledge/schemas/MANIFEST.md` §3.
