---
id: 0030
title: Shipped files are the npm package payload, and carry no DGF repository paths
status: accepted
date: 2026-10-26
deciders: [Andrian Mamei]
supersedes: [0012]
tags: [packaging, portability, knowledge]
---

# 0030 — Shipped files are the npm package payload, and carry no DGF repository paths

Restates [ADR 0012](0012-no-dgf-paths-in-shipped-files.md) in full, with its erratum folded in. Two
things change. **"Shipped" is now the npm package payload** rather than a plugin's directories, because
[ADR 0029](0029-npm-cli-delivery.md) delivers `dgf-factory` as an npm CLI. And **a shipped file's
relative links must stay inside the shipped set**, because an installed project holds the payload
without this repository's `docs/`. The rule against DGF paths, what counts as one, what a shipped file
cites instead, where the paths go and how the rule is enforced are unchanged.

## Context

Read from this repository on **2026-09-23**, and again on **2026-10-26** where marked.

**The decider's rule**, stated 2026-09-23: *"NO DGF paths must be in files that will be installed
by developers."*

**Why it matters.** A developer who installs this tool works in DGF workspaces. Nothing in the install
tells them where a DGF framework checkout is, and nothing requires one: the tool is self-contained
([ADR 0029](0029-npm-cli-delivery.md) §9), and setup registers the hosted DGF docs MCP. A path such as
`src/Core/DGF.Kernel/WorkspaceSettings.cs` resolves to nothing on a developer's machine.

**"Shipped" was a directory list.** ADR 0012 cited it at `skills/dgf-doctor/scripts/doctor.py:47`; it
has since moved to `doctor.py:79` (read 2026-10-26):
`SHIPPED_DIRS = ("skills", "agents", "commands", "scripts", "knowledge", ".claude-plugin")`.
`.claude/` is excluded because the aif-* corpus is installer-managed and does not ship. The doctor
already warned on machine-specific absolute paths in those directories. It did not look for DGF
repository paths until ADR 0012.

**What the shipped directories held** before ADR 0012:

| Where | Lines with a DGF path | Why |
|---|---|---|
| `skills/`, `.claude-plugin/` | 0 | — |
| `knowledge/*.md` frontmatter `sources` | 58 | [ADR 0008](0008-version-gating-revised.md) §1 required every fact file to name its DGF sources by path |
| `knowledge/*.md` prose | 22 | Citations such as "From `src/Core/DGF.Kernel/WorkspaceSettings.cs`" |
| `knowledge/schemas/MANIFEST.md` | 174 | Upstream path and `sha256` per vendored file, and the re-vendor commands |
| Vendored schemas | 181 | DGF's own text. Each of the 60 JSON schemas names `docs/wiki/Components/Behavior/Validators.md` twice and `docs/Components/Behavior/Events.md` once; `xsd/form.xsd:273` names `src/Core/DGF.Domain/Data/Form/ComponentEvent.cs` |
| `scripts/check-dual-schema-docs.sh` | 3 | A repo-maintenance check that sat in a shipped directory |

ADR 0012 first counted 121 lines in the vendored schemas. The count missed `docs/Components/Behavior/Events.md`,
because its search covered only `docs/wiki/`, `docs/schemas/` (the three hand-authored standalone
contracts) and `docs/Research/`. That link is broken
upstream: the page is under `docs/wiki/`. Source: the dry run of `tools/vendor_schemas.py`, and
`provenance/knowledge/schemas/MANIFEST.md` §3.

The accepted [ADR 0010](0010-dgf-implement-scope.md), as first written, told the shipped
`/dgf-implement` to read DGF's `format-coverage.md`. It was corrected by erratum the same day.

**The MCP resolves DGF wiki pages by name.** `get_doc_page('AI-Authoring/format-coverage.md')`
and `get_doc_page('Components/Behavior/Validators.md')` both returned their pages on
2026-09-23. So a wiki citation has a form that works on a developer's machine. A source-file
citation has none: no MCP tool serves DGF source code.

**What changed on 2026-10-26.**
- ADR 0029 delivers the tool as an npm package. Its payload is what `npm pack` puts in the tarball:
  `bin/`, `cli/`, `skills/`, `scripts/` and `knowledge/`. Setup copies `skills/`, `scripts/` and
  `knowledge/` into a project's `.dgf-factory/runtime/`, and a rendered `SKILL.md` into each chosen
  harness's skills folder. `.claude-plugin/` is removed, and `agents/` and `commands/` do not exist.
- **Relative links leave the shipped set.** `knowledge/README.md` links `../docs/adr/…` and
  `../docs/dgf-*.md` nine times, and `skills/dgf-doctor/SKILL.md:143-144` links
  `../../docs/skill-authoring.md` and `../../docs/architecture.md`. In an installed project these point
  at nothing. ADR 0012 §2 had listed `../docs/adr/…` as "this plugin's own path", which held only while
  the plugin folder was what a developer received.
- ADR 0012's last open question — whether maintainer material must leave the plugin folder — is answered
  by the package's `files` allowlist: `docs/`, `.ai-factory/`, `provenance/`, `tools/` and `tests/` stay
  in the repository and never reach a developer.

## Decision

**No shipped file contains a path into the DGF repository, or a relative link that leaves the shipped
set. "Shipped" is the npm package payload. Shipped content names a DGF source by knowledge file, MCP
call, or type or file name. The paths, and the digests that go with them, live in maintainer-only files.
`doctor.py` blocks on a violation, and `tools/check_package.py` holds the tarball to the payload.**

### 1. What is shipped

The npm package payload: `bin/`, `cli/`, `skills/`, `scripts/` and `knowledge/`, as listed in
`package.json` `files`. `doctor.py`'s `SHIPPED_DIRS` is
`("bin", "cli", "skills", "scripts", "knowledge")`. In an installed project, the shipped set is
`.dgf-factory/runtime/` plus the rendered `SKILL.md` files in each harness's skills folder.

Everything else is maintainer material: `docs/` (including these ADRs and the blueprint),
`.ai-factory/`, `provenance/`, `tools/`, `tests/`, `.claude/`, `AGENTS.md`. Maintainer material keeps
citing DGF paths. The ADR contract's rule that Context cites file and line depends on it.

`tools/check_package.py` runs `npm pack --dry-run --json` and fails when the tarball holds anything
outside the payload, or any maintainer material.

### 2. What counts as a DGF path

A path into the DGF repository:

- under one of its top-level `src/` or `docs/` folders;
- under the MCP's `Schemas/Json/`, `Schemas/XSD/` or `Schemas/XmlReference/` folders;
- or through a checkout folder named after the repository.

The exact list is `DGF_PATH_PATTERN` in `doctor.py`.

Not a DGF path:

- **Workspace layout paths** such as `FM/_COMPONENTS/` or `<workspace>/js/`. They describe the
  developer's own workspaces.
- **This tool's own paths inside the payload**, such as `knowledge/…` or `{{dgf_runtime}}/scripts/…`.
- **A bare type or file name**, such as `WorkspaceSettings` or `format-coverage.md`.
- **An MCP argument**, such as `get_doc_page('AI-Authoring/format-coverage.md')`. It resolves on
  the hosted server.

### 3. Links stay inside the shipped set

A relative Markdown link in a shipped file must resolve to a file in the shipped set. A link to
maintainer material, such as `../docs/adr/…`, is replaced by the knowledge file or DGF docs MCP page
that carries the same fact, or by plain text that names the maintainer document. `doctor.py` reports a
violation as `LINK_LEAVES_SHIPPED`, an error.

### 4. What a shipped file cites instead

In order of preference:

1. The shipped knowledge base.
2. A DGF docs MCP call with its argument.
3. A DGF type or file name.

### 5. Where the paths go

- **Knowledge provenance lives in `provenance/`.** A knowledge file's `sources` are in a ledger at the
  same relative path under `provenance/`. [ADR 0013](0013-version-gating-provenance-ledger.md) holds the
  contract.
- **Vendored schemas are rewritten on the way in.** `tools/vendor_schemas.py` copies DGF's schema
  set and applies two rewrites:
  - `docs/wiki/<page>` becomes `get_doc_page('<page>')`;
  - any other DGF path is cut to its file name.

  Nothing else in a schema changes. The tool refuses to write when a DGF path survives or a
  rewritten file no longer parses. The schema ledger records both the upstream and the shipped
  digest of every file.
- **Maintainer tools do not ship.** Repo-maintenance checks live in `tools/`. `scripts/` is for the
  validators skills call ([ADR 0031](0031-validator-runtime-project-venv.md)).

### 6. Enforcement

`doctor.py` §4 reports `DGF_PATH` as an **error** (exit `1`) for every line of a shipped file that
matches `DGF_PATH_PATTERN`, and `LINK_LEAVES_SHIPPED` for every relative link that leaves the shipped
set. `tools/check-dual-schema-docs.sh` runs the doctor and `tools/check_package.py` in its section 6,
so a violation also blocks the documentation check. The pattern is built in pieces, so `doctor.py` does
not match its own check.

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
- **Ship `docs/` in the package, so the links resolve.** Rejected. The ADRs and the blueprint cite DGF
  paths by design, so shipping them would break §2, and they are not what a developer needs at run time.
- **Keep the directory list as the only definition of "shipped".** Rejected. The tarball is decided by
  `package.json` `files`; a list in the doctor that is not checked against it can drift.

## Consequences

### Positive

- Every path in a shipped file resolves on a developer's machine, or is plainly a name rather
  than a location.
- Every relative link in an installed project resolves.
- The rule is checked by script, not by review, both in the doctor and against the real tarball.
- Maintainer material never reaches a developer, without leaving the repository.

### Negative

- **Vendored schemas are no longer byte-identical to upstream.** A reader who diffs one against
  DGF sees the rewrite. Drift detection uses the recorded upstream digest, not the shipped file.
- **Shipped prose is less precise for a maintainer.** "DGF's `WorkspaceSettings` class" replaces
  a path and line number. The precision moved to the ledger, one step away.
- **The pattern is a list of DGF folder names.** A new top-level DGF folder is not caught until
  it is added to the list.
- **A bare file name is allowed and is not resolvable.** `format-coverage.md` on its own tells a
  developer what to look for, not where.
- **"Shipped" is defined twice**, as `package.json` `files` and as `SHIPPED_DIRS`; only
  `tools/check_package.py` keeps them in step.
- **Shipped prose loses its links to the ADRs.** `knowledge/README.md` can name a decision but not link
  it.

### Follow-ups

- The drift check reads the `provenance/` ledgers and runs as a maintainer tool against a DGF checkout
  ([ADR 0013](0013-version-gating-provenance-ledger.md) §5).
