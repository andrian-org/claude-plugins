---
id: 0008
title: Stamp every fact, gate only behavioural ones (revised)
status: accepted
date: 2026-09-23
deciders: [Andrian Mamei]
supersedes: [0003]
tags: [knowledge, versioning, drift]
---

# 0008 — Stamp every fact, gate only behavioural ones (revised)

Supersedes ADR 0003. It still closes [blueprint](../blueprint.md) open question **#6**:
*do DGF versions differ enough that references need version gates?*

The decision is unchanged: **yes, stamp every fact, range only behavioural ones.** Two parts
of ADR 0003 did not survive the first real use of the convention when the knowledge base was
stamped on 2026-09-22, and [`knowledge/README.md`](../../knowledge/README.md) §1.1 and §3 have
overridden them since, with no decision record behind the override. This ADR is that record.

1. **Why the version comes from `Directory.Build.props`.** ADR 0003 said a git tag "lags the
   thing it stamps". The props file is the source that lags. The choice is still right, for a
   different reason: determinism.
2. **What `until: null` means.** ADR 0003 annotated it as "still true at `dgf_version`",
   which its own flagship example contradicts.

Everything else in ADR 0003 is restated below.

## Context

Read from the DotGov Framework repository at `aa1d5c4c2` on **2026-09-23**. Paths are
relative to the DGF repository root.

### Versions differ behaviourally — carried forward, re-verified

`docs/wiki/Release-notes/RELEASE-1.1.15.md` §"Breaking Changes" — *"TreeTable: expandAll and
paging now do what they say"*. Both properties "were accepted in configuration and then
ignored". In 1.1.15, `"expandAll": false` genuinely collapses an eager tree, and `"paging"` on
an eager TreeTable is rejected with a configuration error. **The same JSON validates against
the same schema in 1.1.14 and 1.1.15, and is fatal in one of them.** No schema check can see
this. That is what a version gate is for.

### No first-party version stamping — carried forward, re-verified

- The XSDs under `src/Tools/dgf-mcp/Schemas/XSD/` carry no version and have no per-version
  copies. The JSON schemas under `Schemas/Json/` record no DGF version. No component doc has a
  "since" marker, and no compatibility matrix exists under `docs/`.
- The hosted MCP endpoint in `.mcp.json`, `https://dgf-mcp.dotgov.uk/mcp`, has no version
  segment or parameter.
- The only version-aware surface is the release notes: one file per version under
  `docs/wiki/Release-notes/` (`1.0.30`–`1.0.33`, `1.1.0`–`1.1.15`, plus
  `RELEASE-NOTES-NEXT.md`), and the MCP's `get_release_notes("since:X.Y.Z")`.

### The version source lags, and is still the right source

- `src/Directory.Build.props` sets `<Version>1.1.11</Version>` (L33) and
  `<AssemblyVersion>1.1.11</AssemblyVersion>` (L34) inside the `PropertyGroup` opened at L32,
  `<PropertyGroup Condition="'$(Configuration)' == 'ClientDebug'">`. It is the only version
  the repository states, and the only `Directory.Build.props`. Its comment (L29-31) says all
  configurations share the version; the condition does not implement that.
- Git tags reach **`1.1.15`**, and release notes exist through 1.1.15. So a fact stamped
  `1.1.11` may have been read from a tree that behaves like 1.1.15. ADR 0003's stated reason —
  "a stamp that lags the thing it stamps is worse than no stamp" — argues **against** the props
  file, which is the lagging source.
- A tag is worse for a different reason. `git describe` returns a value that depends on which
  branch is checked out: on `develop` at `aa1d5c4c2` it returns `1.1.12-21-gaa1d5c4c2`
  (re-run 2026-09-23), with `1.1.13` and `1.1.15` unreachable from that branch. The props file returns the same value regardless.
  The drift check has to be reproducible, and a version source that shifts with branch state
  is not.

### `until: null` as ADR 0003 defined it contradicts ADR 0003's example

ADR 0003 §2's worked example is `applies: { since: "1.1.15", until: null }`, stamped with
`dgf_version: "1.1.11"`. Its annotation says `until: null` means "still true at
`dgf_version`". But 1.1.11 is below 1.1.15, so the fact is **not** true at `dgf_version`. The
flagship example is incoherent under its own definition. It is coherent only if `until: null`
means "no known end".

### The `since` convention ADR 0003 left open

ADR 0003's follow-up asked whether `applies.since` for facts predating 1.1.11 should be
`null` or a floor value, to be recorded in `knowledge/README.md`. It was recorded there, in §3,
on 2026-09-22. This ADR adopts that answer.

## Decision

**Every fact in `knowledge/` carries a version stamp. Only facts whose *behaviour* changed
between releases carry a range. Over-gating is a failure mode, not a safety margin. The
version is read from `src/Directory.Build.props` because it is deterministic, and its lag is
recorded, never hidden.**

`knowledge/README.md` is the operative contract. It and this ADR agree.

### 1. Stamp fields

Every knowledge file except `knowledge/README.md` carries, in frontmatter:

```yaml
dgf_version: "1.1.11"      # from src/Directory.Build.props, never from a git tag
read_date: 2026-09-23
sources:
  - path: src/Tools/dgf-mcp/Schemas/XSD/process.xsd
    sha256: <digest of the file as read>
```

- **`dgf_version` is read from `src/Directory.Build.props`, because it is deterministic.**
  It is not the most current value. Its lag behind the tags is a known, stated limitation.
  **Never "correct" a stamp to a tag value.**
- **The per-source `sha256` is what makes drift detectable.** Re-running the digest against
  upstream answers "has this changed since we read it" without diffing prose.
- The vendored schema set's `MANIFEST.md` also records the **DGF commit SHA** at vendor time.
  Between a lagging version string and a deployed MCP that can lag the repository, the commit
  is the one position that is exact.

### 2. Stamp versus range, decided per fact class — carried forward

| fact class | example | treatment |
|---|---|---|
| **structural** | `process.xsd` declares `State/@name`; `FM/_PROCESS` is the process directory | **stamp only** — changes are rare and caught by digest drift |
| **behavioural** | `paging` on an eager TreeTable is rejected; `expandAll: false` takes effect | **stamp + range** (`since` / `until`) |
| **policy** | XML-always generation for the five legacy artifact types | **stamp + `review_date`** — changes by decision, not by release |

A behavioural fact adds:

```yaml
applies:
  since: "1.1.15"   # first version where this is true, or null
  until: null       # no known end — true from `since` onward until proven otherwise
```

Both keys are mandatory whenever `applies:` is present. Each is a quoted version or `null`.

**Do not range everything.** An over-gated fact base goes stale as fast as an unstamped one,
because every fact then needs revisiting on every release and none of them get it.

### 3. What `null` means in a range

- **`until: null` — no known end.** The range is open-ended: true from `since` onward until
  proven otherwise. It does **not** mean "true at `dgf_version`". A `since` above the stamp's
  `dgf_version` is therefore legal, which is exactly the TreeTable case.
- **`since: null` — no known lower bound.** Use it when a behavioural fact's origin is unknown
  or predates 1.1.11. **Never substitute a floor value such as `"1.1.11"`.** That asserts a
  boundary nobody verified, and would wrongly block consumers on older releases for a fact that
  was very likely true there too. The cost, stated plainly: the below-`since` error in §4 never
  fires for such a fact, so it applies to every consumer version.

### 4. Out-of-range behaviour — carried forward

Tied to the exit-code contract in `.ai-factory/rules/base.md`:

| situation | behaviour | exit |
|---|---|---|
| consumer version **below** a fact's `since` | **error** — the fact is not true of their DGF | `1` |
| consumer version **above** a fact's `until` | **warn** — possibly stale, not proven wrong | `2` |
| consumer DGF version **cannot be determined** | **warn**, and say so | `2` |
| vendored `sha256` no longer matches upstream | **warn** — a maintenance signal | `2` |

Blocking below `since` is the default because of an asymmetry. Applying a newer
*restriction* too early is merely over-strict. Claiming a newer *capability* too early is
wrong: it tells the author to use something their runtime ignores, which is how `expandAll`
sat inert in real configurations for releases at a time. A fact that is purely a restriction
may opt out with `out_of_range: warn`, and must say why.

**Never proceed silently on an unknown version.**

### 5. The gate is carried by this plugin's own artifacts — carried forward

The hosted MCP is unversioned, so the gate lives entirely in this plugin: the frontmatter
stamps, the vendored schema set under `knowledge/schemas/` with its `MANIFEST.md`, and a drift
check in `scripts/` that compares stamps and digests against a consumer's DGF checkout.
`get_release_notes("since:X.Y.Z")` is the drift check's natural input: given a stamped version
and a consumer's version, it returns exactly the changes in between.

## Alternatives considered

- **Keep ADR 0003 and let `knowledge/README.md` override it.** This is what happened from
  2026-09-22. Rejected: it left an accepted ADR stating two things the operative contract says
  are wrong, which is the silent drift this repository's ADR contract exists to prevent.
- **Read `dgf_version` from a git tag.** More current. Rejected: `git describe` is
  branch-dependent, so two people stamping the same file on different branches record different
  versions, and the drift check stops being reproducible.
- **Read `dgf_version` from the commit SHA alone.** Exact, but a SHA cannot be compared as
  "below `since`" without a git checkout and a walk. The SHA is recorded in `MANIFEST.md`
  alongside the version, not instead of it.
- **Floor unknown `since` values at `"1.1.11"`.** Rejected in §3: false precision that blocks
  consumers on older releases.
- **The alternatives ADR 0003 rejected still stand rejected:** stamp nothing and rely on schema
  validation (the 1.1.15 evidence refutes it); range every fact (maintenance that nobody does);
  version-address the hosted MCP (not available); pin to one DGF version (too blunt for a
  brownfield estate — see [ADR 0004](0004-authoring-entry-point.md)).

## Consequences

### Positive

- **The decision record and the operative contract agree again.** `knowledge/README.md` no
  longer has to warn readers that an accepted ADR is wrong.
- **The TreeTable example is coherent**, and so is every future fact whose `since` is above the
  stamped version.
- **Stamps are reproducible** across branches and machines.
- **The one proven breaking-change class is covered**, and drift is detectable rather than silent.

### Negative

- **The stamp understates the DGF it describes.** `1.1.11` sits four releases behind the tags.
  A reader who takes `dgf_version` as "the version this was read from" is misled, and only the
  commit SHA in `MANIFEST.md` tells the truth.
- **The version source is defective upstream.** It is set under `ClientDebug` only, contrary to
  its own comment.
- **`since: null` facts are never blocked.** A fact that was in truth introduced late applies to
  every consumer until someone establishes its `since`.
- **`since` values are often unknowable retroactively.** Establishing one means reading back
  through release notes, and sometimes the honest answer is `null`.
- **Stamping is still discipline plus a structural check.** `scripts/check_knowledge_stamps.py`
  enforces the shape of the stamp, not whether its digests or ranges are true; the drift check
  that would is not written yet.

### Follow-ups

- Report upstream to the DGF team: `<Version>1.1.11</Version>` is conditioned on `ClientDebug`
  despite a comment asserting all configurations share it, and it lags the release tags.
- Write the drift check in `scripts/` (milestone 8), using `get_release_notes("since:X.Y.Z")` as
  its input and running under [ADR 0007](0007-validator-runtime.md)'s runtime.
- ADR 0003's `applies.since` follow-up is **discharged** by §3 above and `knowledge/README.md` §3.
