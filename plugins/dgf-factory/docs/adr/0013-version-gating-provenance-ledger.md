---
id: 0013
title: Stamp every fact, gate only behavioural ones — provenance in a maintainer ledger
status: accepted
date: 2026-09-23
deciders: [Andrian Mamei]
supersedes: [0008]
tags: [knowledge, versioning, drift, portability]
---

# 0013 — Stamp every fact, gate only behavioural ones — provenance in a maintainer ledger

Supersedes ADR 0008, which superseded ADR 0003. It still closes [blueprint](../blueprint.md) open
question **#6**: *do DGF versions differ enough that references need version gates?*

The decision is unchanged: **yes, stamp every fact, range only behavioural ones.** One thing
changes: **where a fact's sources are recorded.**

1. ADR 0008 §1 put each fact file's `sources` in its own frontmatter: a DGF repository path and
   a `sha256` per source. §5 put the vendored schema set's digest table in
   `knowledge/schemas/MANIFEST.md`. Both are shipped files, and
   [ADR 0012](0012-no-dgf-paths-in-shipped-files.md) forbids DGF paths in shipped files. The
   sources move to a maintainer-only ledger under `provenance/`. The shipped stamp keeps the
   version, the dates and the range.
2. ADR 0008 §4 and §5 described the digest drift check as comparing against "a consumer's DGF
   checkout". A developer has no DGF checkout (ADR 0012 §Context). The digest check is a
   maintainer check against a DGF checkout. The version-range gate is the part that runs for a
   developer.

Everything else in ADR 0008 is restated below.

## Context

Read from the DotGov Framework repository at `aa1d5c4c2` on **2026-09-23**. Paths are
relative to the DGF repository root.

### Versions differ behaviourally — carried forward

`docs/wiki/Release-notes/RELEASE-1.1.15.md` §"Breaking Changes" — *"TreeTable: expandAll and
paging now do what they say"*. Both properties "were accepted in configuration and then
ignored". In 1.1.15, `"expandAll": false` genuinely collapses an eager tree, and `"paging"` on
an eager TreeTable is rejected with a configuration error. **The same JSON validates against
the same schema in 1.1.14 and 1.1.15, and is fatal in one of them.** No schema check can see
this. That is what a version gate is for.

### No first-party version stamping — carried forward

- The XSDs under `src/Tools/dgf-mcp/Schemas/XSD/` carry no version and have no per-version
  copies. The JSON schemas under `Schemas/Json/` record no DGF version. No component doc has a
  "since" marker, and no compatibility matrix exists under `docs/`.
- The hosted MCP endpoint in `.mcp.json`, `https://dgf-mcp.dotgov.uk/mcp`, has no version
  segment or parameter.
- The only version-aware surface is the release notes: one file per version under
  `docs/wiki/Release-notes/` (`1.0.30`–`1.0.33`, `1.1.0`–`1.1.15`, plus
  `RELEASE-NOTES-NEXT.md`), and the MCP's `get_release_notes("since:X.Y.Z")`.

### The version source lags, and is still the right source — carried forward

- `src/Directory.Build.props` sets `<Version>1.1.11</Version>` (L33) and
  `<AssemblyVersion>1.1.11</AssemblyVersion>` (L34) inside the `PropertyGroup` opened at L32,
  `<PropertyGroup Condition="'$(Configuration)' == 'ClientDebug'">`. It is the only version
  the repository states, and the only `Directory.Build.props`. Its comment (L29-31) says all
  configurations share the version; the condition does not implement that.
- Git tags reach **`1.1.15`**, and release notes exist through 1.1.15. So a fact stamped
  `1.1.11` may have been read from a tree that behaves like 1.1.15.
- A tag is worse. `git describe` returns a value that depends on which branch is checked out:
  on `develop` at `aa1d5c4c2` it returns `1.1.12-21-gaa1d5c4c2`, with `1.1.13` and `1.1.15`
  unreachable from that branch. The props file returns the same value regardless. The drift
  check has to be reproducible, and a version source that shifts with branch state is not.

### What the range bounds mean — carried forward

ADR 0003 §2's worked example is `applies: { since: "1.1.15", until: null }`, stamped with
`dgf_version: "1.1.11"`. It is coherent only if `until: null` means "no known end", not "still
true at `dgf_version`". ADR 0008 §3 decided that, and adopted `knowledge/README.md` §3's answer
to ADR 0003's open `since` question.

### Shipped files carry no DGF paths — new

[ADR 0012](0012-no-dgf-paths-in-shipped-files.md) (accepted 2026-09-23) forbids DGF repository
paths under `doctor.py`'s `SHIPPED_DIRS`, which include `knowledge/`. Under ADR 0008 the four
fact files carried 57 source paths in their frontmatter. `knowledge/schemas/MANIFEST.md`
carried 82 more, plus an upstream-path column and the re-vendor commands. None of that can stay
in a shipped file.

### The schema set's shipped copy differs from upstream — new

ADR 0012 §4 rewrites DGF paths inside vendored schemas as they are copied in. 61 of the 82
vendored files change (60 JSON schemas and `form.xsd`). A single upstream digest per file no
longer describes the shipped file, so the ledger records both.

## Decision

**Every fact in `knowledge/` carries a version stamp. Only facts whose *behaviour* changed
between releases carry a range. Over-gating is a failure mode, not a safety margin. The
version is read from DGF's `Directory.Build.props` because it is deterministic, and its lag is
recorded, never hidden. Where each fact came from is recorded in a maintainer-only ledger,
never in the shipped file.**

`knowledge/README.md` is the operative contract. It and this ADR agree.

### 1. Stamp fields — changed

Every knowledge file except `knowledge/README.md` carries, in frontmatter:

```yaml
dgf_version: "1.1.11"      # from DGF's Directory.Build.props, never from a git tag
read_date: 2026-09-23
```

Its sources are in a **provenance ledger** at the same relative path under `provenance/`, so
`knowledge/composition-specs.md` has `provenance/knowledge/composition-specs.md`:

```yaml
sources:
  - path: src/Tools/dgf-mcp/Schemas/XSD/process.xsd
    sha256: <digest of the file as read>
```

- **Every stamped knowledge file has exactly one ledger, and every ledger has its knowledge
  file.** A `sources` key in a shipped knowledge file is an error. `tools/check_knowledge_stamps.py`
  enforces all three.
- **`dgf_version` is read from DGF's `Directory.Build.props`, because it is deterministic.** It
  is not the most current value. Its lag behind the tags is a known, stated limitation.
  **Never "correct" a stamp to a tag value.**
- **The per-source `sha256` is what makes drift detectable.** Re-running the digest against
  upstream answers "has this changed since we read it" without diffing prose.
- **The vendored schema set's ledger, `provenance/knowledge/schemas/MANIFEST.md`, adds three
  fields.** `dgf_commit` is the DGF commit at vendor time. Between a lagging version string and
  a deployed MCP that can lag the repository, the commit is the one exact position. Each entry
  also carries `vendored` (its path under `knowledge/schemas/`) and `shipped_sha256` (the digest
  of the shipped file after ADR 0012's rewrite). `tools/vendor_schemas.py` writes that ledger's
  frontmatter. It is never hand-edited.

### 2. Stamp versus range, decided per fact class — carried forward

| fact class | example | treatment |
|---|---|---|
| **structural** | `process.xsd` declares `State/@name`; `FM/_PROCESS` is the process directory | **stamp only** — changes are rare and caught by digest drift |
| **behavioural** | `paging` on an eager TreeTable is rejected; `expandAll: false` takes effect | **stamp + range** (`since` / `until`) |
| **policy** | XML-always generation for the five legacy artifact types | **stamp + `review_date`** — changes by decision, not by release. Its ledger cites the document that states the policy, so the digest catches a rewrite |

A behavioural fact adds:

```yaml
applies:
  since: "1.1.15"   # first version where this is true, or null
  until: null       # no known end — true from `since` onward until proven otherwise
```

Both keys are mandatory whenever `applies:` is present. Each is a quoted version or `null`.

**Do not range everything.** An over-gated fact base goes stale as fast as an unstamped one,
because every fact then needs revisiting on every release and none of them get it.

### 3. What `null` means in a range — carried forward

- **`until: null` — no known end.** The range is open-ended: true from `since` onward until
  proven otherwise. It does **not** mean "true at `dgf_version`". A `since` above the stamp's
  `dgf_version` is therefore legal, which is exactly the TreeTable case.
- **`since: null` — no known lower bound.** Use it when a behavioural fact's origin is unknown
  or predates 1.1.11. **Never substitute a floor value such as `"1.1.11"`.** That asserts a
  boundary nobody verified, and would wrongly block consumers on older releases for a fact that
  was very likely true there too. The cost, stated plainly: the below-`since` error in §4 never
  fires for such a fact, so it applies to every consumer version.

### 4. Out-of-range behaviour — split by who runs it

Tied to the exit-code contract in `.ai-factory/rules/base.md`.

**The version gate** reads the shipped stamps and runs for a developer:

| situation | behaviour | exit |
|---|---|---|
| consumer version **below** a fact's `since` | **error** — the fact is not true of their DGF | `1` |
| consumer version **above** a fact's `until` | **warn** — possibly stale, not proven wrong | `2` |
| consumer DGF version **cannot be determined** | **warn**, and say so | `2` |

**The digest checks** read the ledgers and run for a maintainer, never from a skill:

| situation | behaviour | exit |
|---|---|---|
| a ledger's upstream `sha256` no longer matches a DGF checkout | **warn** — a maintenance signal | `2` |
| a vendored file no longer matches its `shipped_sha256` | **error** — the shipped copy was edited by hand | `1` |

Blocking below `since` is the default because of an asymmetry. Applying a newer *restriction*
too early is merely over-strict. Claiming a newer *capability* too early is wrong: it tells the
author to use something their runtime ignores, which is how `expandAll` sat inert in real
configurations for releases at a time. A fact that is purely a restriction may opt out with
`out_of_range: warn`, and must say why.

**Never proceed silently on an unknown version.**

### 5. Who carries the gate — changed

The hosted MCP is unversioned, so the gate lives entirely in this plugin.

- **The shipped part** is the frontmatter stamps and the vendored schema set under
  `knowledge/schemas/`. The version gate reads them.
- **The maintainer part** is the ledgers under `provenance/` and a drift check in `tools/`. The
  drift check compares ledger digests against a DGF checkout.

`get_release_notes("since:X.Y.Z")` is the version gate's natural input: given a stamped version
and a consumer's version, it returns exactly the changes in between.

## Alternatives considered

- **Keep `sources` in shipped frontmatter.** Rejected by ADR 0012: no metadata exception.
- **One ledger file for the whole knowledge base.** Rejected. It merges unrelated churn into one
  file, and "every fact file has its ledger" stops being a one-to-one check.
- **A ledger inside `knowledge/`, exempted from the doctor's check.** Rejected. `knowledge/` is
  shipped, and exempting a subfolder makes ADR 0012's rule leaky by design.
- **Keep ADR 0008 and let `knowledge/README.md` override it.** Rejected for the reason ADR 0008
  itself rejected the same move for ADR 0003: an accepted ADR would state what the operative
  contract says is wrong.
- **Carried forward from ADR 0008:** read `dgf_version` from a git tag (branch-dependent, so not
  reproducible); read it from the commit SHA alone (not comparable as "below `since`" without a
  checkout, so the SHA is recorded next to the version, not instead of it); floor unknown
  `since` values at `"1.1.11"` (false precision, rejected in §3).
- **Still rejected from ADR 0003:** stamp nothing and rely on schema validation (the 1.1.15
  evidence refutes it); range every fact (maintenance nobody does); version-address the hosted
  MCP (not available); pin to one DGF version (too blunt for a brownfield estate — see
  [ADR 0004](0004-authoring-entry-point.md)).

## Consequences

### Positive

- **Shipped knowledge carries no DGF paths**, and the ADR 0012 check passes on `knowledge/`.
- **Nothing is lost.** Every source path and digest ADR 0008 recorded is in a ledger, and the
  schema ledger adds the shipped digest.
- **Hand edits to vendored schemas are caught offline**, against `shipped_sha256`, without a DGF
  checkout. ADR 0008 could not check this.
- **Carried forward:** the TreeTable example is coherent; stamps are reproducible across branches
  and machines; the one proven breaking-change class is covered.

### Negative

- **Two files change on every re-read**, the fact file and its ledger. The check enforces that
  both exist and are well-formed. It cannot tell whether they describe the same read.
- **A developer reading an installed fact file cannot see its sources.** They see the version
  and the date, and a DGF type or page name in the prose.
- **Carried forward:** the stamp understates the DGF it describes (`1.1.11` is four releases
  behind the tags, and only `dgf_commit` tells the truth); the version source is set under
  `ClientDebug` only, contrary to its own comment; `since: null` facts are never blocked;
  `since` values are often unknowable retroactively.
- **Carried forward:** stamping is still discipline plus a structural check.
  `tools/check_knowledge_stamps.py` enforces the shape of stamps and ledgers, and the shipped
  digests. It does not check upstream digests or whether a range is true. The drift check that
  would is not written yet.

### Follow-ups

- Report upstream to the DGF team: `<Version>1.1.11</Version>` is conditioned on `ClientDebug`
  despite a comment asserting all configurations share it, and it lags the release tags.
  Carried forward from ADR 0008.
- Write the drift check in `tools/` (milestone 8). It reads the `provenance/` ledgers, compares
  them against a DGF checkout, and runs under [ADR 0007](0007-validator-runtime.md)'s runtime.
- Decide how the version gate learns a developer's DGF version. Neither ADR 0003 nor ADR 0008
  said, and it is the gate's only input that is not in this plugin.
