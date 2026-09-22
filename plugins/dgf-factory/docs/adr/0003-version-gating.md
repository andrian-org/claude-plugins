---
id: 0003
title: Stamp every fact, gate only behavioural ones
status: accepted
date: 2026-09-21
deciders: [Andrian Mamei]
supersedes: []
tags: [knowledge, versioning, drift]
---

# 0003 — Stamp every fact, gate only behavioural ones

Closes [blueprint](../blueprint.md) open question **#6**: *do DGF versions differ enough
that references need version gates?*

## Context

Read from the DotGov Framework repository on **2026-09-21** and re-verified the same day.

**The answer is yes, and one release note settles it.**
`docs/wiki/Release-notes/RELEASE-1.1.15.md` §"Breaking Changes" — *"TreeTable: expandAll and
paging now do what they say"*. Two properties "were accepted in configuration and then
ignored". In 1.1.15:

- `"expandAll": false` **now genuinely collapses** an eager tree where previously it did
  nothing at all. A configuration that was inert becomes load-bearing, with no error at any
  point in either version.
- `"paging"` on an eager TreeTable is **now rejected with a configuration error** instead of
  being quietly dropped — *"those pages will now fail to load until you remove it, or move
  them to `"loadMode": "lazy"`."*

This is the decisive class of change: **the same JSON validates against the same schema in
1.1.14 and 1.1.15, and is merely fatal in one of them.** No schema check can catch it,
because nothing about the schema changed. That is precisely what a version gate is for.

Three further facts shape the mechanism:

- **The version source of truth is stamped in one build configuration only.**
  `src/Directory.Build.props` L32-34 sets `<Version>1.1.11</Version>` and
  `<AssemblyVersion>1.1.11</AssemblyVersion>` inside
  `<PropertyGroup Condition="'$(Configuration)' == 'ClientDebug'">`. It is the only such
  definition in the repository; there is no second `Directory.Build.props`. The block's own
  comment (L30-31) asserts *"All configurations share the same version so the Docker
  (Release) image is compatible with plugin assemblies built via ClientDebug"* — an intent
  the condition does not implement, since no other configuration sets `Version` at all.
- **Nothing first-party version-stamps DGF knowledge.** The XSDs under
  `src/Tools/dgf-mcp/Schemas/XSD/` carry no `version` attribute and have no per-version
  copies. The generated JSON schemas under `Schemas/Json/` record no DGF version. No
  component doc carries a "since 1.1.x" marker. No compatibility matrix or
  supported-version-window document exists anywhere in `docs/`.
- **The hosted MCP endpoint is unversioned.** `.mcp.json` targets
  `https://dgf-mcp.dotgov.uk/mcp` — no version segment, no version parameter.
  Version-addressable knowledge cannot be fetched from it.

The one version-aware surface that does exist: release notes, one file per version at
`docs/wiki/Release-notes/RELEASE-<version>.md` (`1.0.30`–`1.0.33`, `1.1.0`–`1.1.15`), and
the MCP's `get_release_notes` accepts `"since:X.Y.Z"`, concatenating every strictly-newer
release's markdown.

## Decision

**Every fact in `knowledge/` carries a version stamp. Only facts whose *behaviour* changed
between releases carry a version range. Over-gating is a failure mode, not a safety
margin.**

### 1. Stamp fields

Every knowledge file carries, in frontmatter:

```yaml
dgf_version: "1.1.11"                       # from src/Directory.Build.props, not a git tag
read_date: 2026-09-21
sources:
  - path: src/Tools/dgf-mcp/Schemas/XSD/process.xsd
    sha256: <digest of the file as read>
```

`dgf_version` is read from `src/Directory.Build.props`, **never from a git tag** — a stamp
that lags the thing it stamps is worse than no stamp. The per-source `sha256` is what makes
drift detectable: re-running the digest against upstream answers "has this changed since we
read it" without diffing prose. The vendored schema set's `MANIFEST.md` additionally records
the DGF commit SHA at vendor time, because the deployed MCP can lag the repository and the
vendored set needs a knowable position between the two.

### 2. Stamp versus gate, decided per fact class

| fact class | example | treatment |
|---|---|---|
| **structural** | `process.xsd` declares `State/@name` and `Transition/@state`; `FM/_PROCESS` is the process directory | **stamp only** — changes are rare and caught by digest drift |
| **behavioural** | `paging` on an eager TreeTable is rejected; `expandAll: false` takes effect | **stamp + range** (`since` / `until`) |
| **policy** | XML-always generation for the five legacy artifact types | **stamp + review date** — changes by decision, not by release |

A behavioural fact adds:

```yaml
applies:
  since: "1.1.15"       # first version where this is true
  until: null           # still true at dgf_version
```

**Do not gate everything.** An over-gated fact base goes stale exactly as fast as an
unstamped one, because every fact then needs revisiting on every release and none of them
get it. The structural majority carries a stamp and nothing more.

### 3. Out-of-range behaviour

Tied to the exit-code contract in `.ai-factory/rules/base.md`
(`0` clean / `1` blocked / `2` warnings / `3` usage error):

| situation | behaviour | exit |
|---|---|---|
| consumer version **below** a fact's `since` | **error** — the fact is not true of their DGF | 1 |
| consumer version **above** a fact's `until` | **warn** — possibly stale, not proven wrong | 2 |
| consumer DGF version **cannot be determined** | **warn** and say so | 2 |
| vendored `sha256` no longer matches upstream | **warn** — a maintenance signal | 2 |

Blocking below `since` is the default because of an asymmetry worth naming: applying a newer
*restriction* too early is merely over-strict and safe, while claiming a newer *capability*
too early is simply wrong — it tells the author to use something their runtime ignores,
which is how `expandAll` sat inert in real configurations for releases at a time. A fact
that is purely a restriction may opt out with `out_of_range: warn`, and must say why.

**Never proceed silently on an unknown version.** An unstamped comparison that quietly
passes is the failure this whole ADR exists to prevent.

### 4. The gate is carried by this plugin's own artifacts

Because the hosted MCP is unversioned, version-addressable knowledge cannot be obtained from
it. The gate therefore lives entirely in this plugin: the frontmatter stamps above, the
vendored schema set under `knowledge/schemas/` with its `MANIFEST.md`, and a drift check in
`scripts/` that compares stamps and digests against a consumer's DGF checkout.

`get_release_notes("since:X.Y.Z")` is recorded as the natural input to that drift check —
given a stamped version and a consumer's version, it returns exactly the changes in between.
It is the only version-aware query surface DGF offers.

## Alternatives considered

- **Stamp nothing; rely on schema validation.** Rejected outright by the 1.1.15 evidence:
  identical JSON validates in both versions and is fatal in one. Schema validation cannot see
  this class of change, so "the schema passes" is not a version-safety argument.
- **Gate every fact with a range.** Maximally safe on paper. Rejected: it multiplies
  maintenance across the whole fact base so that nothing gets revisited, and it manufactures
  false precision for structural facts whose `since` nobody actually knows.
- **Version-address the hosted MCP.** Would remove the need to vendor. Not available — the
  endpoint has no version segment, and making it versioned is an upstream change this plugin
  cannot depend on.
- **Pin to a single supported DGF version and refuse everything else.** Simple and honest.
  Rejected as too blunt for a brownfield-dominant estate (see [ADR 0004](0004-authoring-entry-point.md)),
  where several systems on different versions are exactly the normal case.

## Consequences

### Positive

- **The one proven breaking-change class is covered**, and covered by the only mechanism that
  can cover it.
- **Drift is detectable rather than silent** — digests answer "did this change" without a
  prose diff.
- **Maintenance stays proportionate.** Most facts are structural and cost one stamp.

### Negative

- **Stamping is manual discipline.** Nothing enforces that a new knowledge file carries
  correct frontmatter until the drift check is written; until then it rests on review.
- **`dgf_version` is stamped against a defective source.** `1.1.11` is set only under
  `Condition="'$(Configuration)' == 'ClientDebug'"`, so the value this plugin stamps against
  is the only one the repository states, not one it states for all configurations.
- **`since` values are often unknowable retroactively.** For a behavioural fact discovered
  today, establishing when it became true may mean reading back through release notes, and
  sometimes the honest answer is "not known before 1.1.11".
- **A consumer below `since` is blocked, not warned.** That will occasionally be
  over-strict — the restriction case named above — and the `out_of_range: warn` opt-out is
  discretion that has to be exercised correctly.

### Follow-ups

- **Upstream, not ours to fix:** `<Version>1.1.11</Version>` is conditioned on
  `ClientDebug` despite a comment asserting all configurations share it. Report it to the DGF
  team. In the meantime this plugin stamps against **1.1.11**, and records that the value is
  configuration-conditioned rather than global.
- Write the drift check in `scripts/` (milestone 8), using `get_release_notes("since:X.Y.Z")`
  as its input.
- Decide, when the knowledge base lands (milestone 7), whether `applies.since` for facts
  predating 1.1.11 should be `null` or a floor value — and record the convention in
  `knowledge/README.md`.
