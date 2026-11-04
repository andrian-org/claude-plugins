---
id: 0036
title: "Knowledge packs per DGF release line, each pinned to a release tag; one pack installed per project"
status: accepted
date: 2026-11-04
deciders: [Andrian Mamei]
supersedes: [0013]
tags: [knowledge, versioning, drift, delivery, maintenance]
---

# 0036 — Knowledge packs per DGF release line, each pinned to a release tag; one pack installed per project

Supersedes [ADR 0013](0013-version-gating-provenance-ledger.md), which superseded ADR 0008 and ADR 0003. It still
closes [blueprint](../blueprint.md) open question **#6**: *do DGF versions differ enough that references need
version gates?*

The answer is unchanged: **yes, stamp every fact, range only behavioural ones.** Four things change:

1. **The version source.** ADR 0013 §1 read `dgf_version` from DGF's `Directory.Build.props` "because it is
   deterministic". DGF stopped moving that value with its releases, so a deterministic value is now also a wrong
   one. A fact base is versioned by the **release tag** it was read at.
2. **One knowledge base becomes one pack per release line.** DGF now maintains several release lines at once,
   and a developer works on estates that run different ones.
3. **The version gate is built.** It runs in `/dgf-doctor`'s project mode.
4. **Keeping packs current is a maintainer flow.** A detector that can run on a schedule, and a maintainer skill
   that does the edits.

Everything else in ADR 0013 is restated below.

## Context

Read on **2026-11-04** from the DotGov Framework repository (branch `1.3.x` at `9a376eb37`, remote
`dev.azure.com/dotgov/DotGovFramework`) and from this repository (branch `feature/dgf-version-packs`). DGF paths are
relative to the DGF repository root.

### Versions differ behaviourally — carried forward, and extended

`docs/wiki/Release-notes/RELEASE-1.1.15.md` §"Breaking Changes" — *"TreeTable: expandAll and paging now do what they
say"*. **The same JSON validates against the same schema in 1.1.14 and 1.1.15, and is fatal in one of them.** Since
then, `RELEASE-1.3.0.md` (which collates 1.2.0 and 1.3.0; no `RELEASE-1.2.0.md` exists on any ref) records more of
the same kind:

- `roles`/`deny` lists now match with a space after the comma (1.3.0);
- components inside tabs resolve only as `${form.component}` (1.3.0);
- `<triggers onbeforesave="false">` no longer suppresses `<onsavescript>` (1.3.0);
- a legacy cell with an unknown `<component type>` keeps the field instead of dropping it (1.2.0).

### The props version no longer follows the releases — new

`src/Directory.Build.props` holds `<Version>` inside
`<PropertyGroup Condition="'$(Configuration)' == 'ClientDebug'">` (L32-35). Its value at each release tag, read with
`git show <tag>:src/Directory.Build.props`:

| Tag | `<Version>` |
|---|---|
| 1.1.11 | 1.1.8 |
| 1.1.12 – 1.1.15 | 1.1.11 |
| 1.1.16 | 1.1.15 |
| 1.2.0, 1.3.0, and the tips of `1.2.x`, `1.3.x`, `2.x`, `develop` | 1.1.15 |

ADR 0013 accepted a lag of four releases. The value now repeats across three release lines, so it cannot tell
1.1.16 from 1.3.0. The knowledge base this repository shipped, stamped `1.1.11`, was read at `aa1d5c4c2` (develop,
2026-09-11). That commit already holds `RELEASE-1.1.12.md` through `RELEASE-1.1.15.md`, so its facts are ≈1.1.15.

### DGF versions its builds from tags — new

`GitVersion.yml` L1-7 makes `X.Y.x` branches GitFlow **support branches**: "their version is the next patch of the
line's last tag … and tag 1.3.1 gives 1.3.1" (commit `43fb6e931`, 2026-11-03, PR 7788). The release a build carries
is its tag.

### Release lines — new

Read with `git merge-base --is-ancestor` and `git log -1` on each ref:

| Line | Released | Where | State |
|---|---|---|---|
| 1.1 | tags 1.1.15 (09-10), 1.1.16 (10-02) | `master`; neither tag is an ancestor of 1.2.0 or 1.3.x | final release of the line |
| 1.2 | tag 1.2.0 (10-27) | `origin/1.2.x` (tip `a5c22295f`, 11-03) | maintained |
| 1.3 | tag 1.3.0 (11-03) | `origin/1.3.x` (tip `9a376eb37`, 11-04; 30 unreleased fragments in `docs/wiki/Release-notes/.next/`) | latest |
| 2.x | no `2.*` tag | `origin/2.x` (tip `c4ab3daa7`, 10-22); its `RELEASE-NOTES-NEXT.md` heads "v1.1.17 … Branch: develop" | not a release line |

### The shipped facts drifted — new

`tools/check_drift.py` against the checkout above (exit 2) reported **151** of the ledgers' 565 sources changed and
none missing, across all 11 ledgers. The changes include:

- two dispatchable components, AutoComplete and Chart (`RegisterComponentService` calls 34 → 36);
- every JSON schema regenerated with camelCase property names and camelCase string enums (commit `b1fcf0f61`,
  shipped in 1.1.16);
- a tenth XSD, `src/Tools/dgf-mcp/Schemas/XSD/application-sitemap.xsd`;
- `OnInit` accepting `StoredProcedureActivity` in `process.xsd`.

### Several projects, several lines — new

The runtime is per project: `dgf-factory setup` writes `.dgf-factory/runtime/` inside the project and records it in
`.dgf-factory/install.json` (ADR 0029 §2, §4). Nothing stops two projects on one machine from holding different
runtimes. Skills read knowledge only as `{{dgf_runtime}}/knowledge/…` — 85 references across the skills and agents
(grep, 2026-11-04) — so *which* files sit at that path can change without changing a skill.

### No first-party version surface besides tags and release notes — carried forward

The XSDs and JSON schemas carry no version and have no per-version copies. The hosted MCP endpoint
`https://dgf-mcp.dotgov.uk/mcp` has no version segment, though since 1.1.16 the MCP reports its own version
(`RELEASE-1.1.16.md`). `get_release_notes("since:X.Y.Z")` remains the version-aware surface.

### Shipped files carry no DGF paths — carried forward

[ADR 0030](0030-shipped-package-payload.md) forbids DGF repository paths in the npm package payload, `knowledge/`
included. Each fact file's sources therefore live in a maintainer-only ledger under `provenance/`. The vendored schema
set's shipped copy differs from upstream, because DGF paths are rewritten as it is copied in, so its ledger records
both digests.

## Decision

**Every fact is stamped with the DGF release tag it was read at, and only behavioural facts carry a range. The
knowledge base is one pack per DGF release line. `dgf-factory setup` installs exactly one pack into a project,
chosen from the estate's DGF version, so projects on different lines coexist. Where each fact came from stays in a
maintainer-only ledger. Detecting that DGF moved is a script; deciding what a change means is a maintainer skill
whose every judgement is logged.**

`knowledge/README.md` is the operative contract. It and this ADR agree.

### 1. Stamp fields — changed

Every knowledge file except `knowledge/README.md` carries, in frontmatter:

```yaml
dgf_version: "1.3.0"      # the release tag the pack was read at
read_date: 2026-11-04
```

- **`dgf_version` is the release tag the facts were read at.** A pack is read only from a checkout whose HEAD is
  exactly a release tag — `git describe --exact-match --tags HEAD` returning `X.Y.Z` — and nothing else.
  - **This is deterministic.** A tag names one commit, whichever branch is checked out. ADR 0013 rejected
    `git describe` because, without `--exact-match`, it answers relative to the branch; an exact tag does not.
  - **An unreleased branch tip is never stamped.** Its release does not exist yet.
- **Sources live in a provenance ledger** at the same relative path under the pack's provenance directory:
  - `knowledge/composition-specs.md` → `provenance/knowledge/composition-specs.md`;
  - `packs/1.2/composition-specs.md` → `provenance/packs/1.2/composition-specs.md`.

  ```yaml
  sources:
    - path: src/Tools/dgf-mcp/Schemas/XSD/process.xsd
      sha256: <digest of the file as read>
  ```
- **Every stamped knowledge file has exactly one ledger, and every ledger has its knowledge file.** A `sources` key
  in a shipped knowledge file is an error. `tools/check_knowledge_stamps.py` enforces all three, for every pack.
- **The per-source `sha256` is what makes drift detectable.** Re-running the digest against upstream answers "has
  this changed since we read it" without diffing prose.
- **The vendored schema set's ledger** (`<pack provenance>/schemas/MANIFEST.md`) adds four fields:
  - `dgf_commit` — the commit the tag names;
  - `dgf_tag` — the tag;
  - per entry, `vendored` — its path in the pack;
  - per entry, `shipped_sha256` — the digest of the shipped file after the path rewrite.

  `tools/vendor_schemas.py` writes that frontmatter. It is never hand-edited.
- **Ledger digests change only through a tool.** `tools/restamp_knowledge.py` re-digests a fact file's ledger after
  a re-read; `tools/vendor_schemas.py` writes the schema ledger. Both refuse a checkout that is not at an exact
  release tag of the pack's line.

### 2. Packs — new

- **A pack is a complete knowledge tree for one release line `X.Y`:** the fact files, `schemas/`, and their
  stamps. All of a pack's stamps carry the same `dgf_version`.
- **The current line** — the newest release line this repository tracks — is `knowledge/`. Every existing path,
  skill reference and test reads it.
- **Each older line** is `packs/<X.Y>/`, with the same file names as `knowledge/` and no `README.md`: the stamping
  convention is shared, not per line.
- **Two registries name the packs:**
  - `packs/lines.json` — **shipped**: line, `dir`, `dgf_version`, `read_date`, and which line is `current`;
  - `provenance/lines.json` — **maintainer**: line → `tag`, `commit`, `support_branch`.

  They agree on the set of lines, and each pack's stamps equal its registry `dgf_version`.
  `tools/check_knowledge_stamps.py` enforces both.
- **Packs are full copies, not overlays.** An inherited file would carry a ledger read at another line's tag, so
  "every fact names the release it was read at" would stop being true file by file.
- **A line whose final release is out** (1.1) keeps its pack as long as estates run it. Dropping a line is a
  decision recorded in `docs/dgf-lines.md`, not a silent deletion.
- **A branch with no release tag** (`2.x` today) gets no pack.

### 3. One pack per project — new

- **`dgf-factory setup` installs exactly one pack into `.dgf-factory/runtime/knowledge/`:** the shared `README.md`
  plus that line's files.
- **The receipt records the line as `dgfLine`.**
- **Skills and scripts are unchanged in a project.** They read the same path; the installer decides what is there.
- **The validators, skills and installer are one codebase.** They must work against every pack.
- **Setup chooses the line** from `--dgf-line X.Y`, or `--dgf-version X.Y.Z`, or — when neither is given — the
  previous receipt's `dgfLine`, then the project's declared `dgf.version`
  ([ADR 0019](0019-declared-dgf-version.md)), then the current line. Interactive setup asks, with that default.
- **The asymmetry of §5 decides the fallbacks:**

  | Declared version | Pack installed |
  |---|---|
  | its line has a pack | that pack |
  | newer than every line | the newest pack, with a warning — it understates capability, which is safe |
  | older than every line | refused, unless `--dgf-line` is given explicitly — it would overstate capability |

### 4. Stamp versus range, decided per fact class — carried forward

| fact class | example | treatment |
|---|---|---|
| **structural** | `process.xsd` declares `State/@name`; `FM/_PROCESS` is the process directory | **stamp only** — changes are rare and caught by digest drift |
| **behavioural** | `paging` on an eager TreeTable is rejected; `expandAll: false` takes effect | **stamp + range** (`since` / `until`) |
| **policy** | XML-always generation for the five legacy artifact types | **stamp + `review_date`** — changes by decision, not by release. Its ledger cites the document that states the policy |

A behavioural fact adds:

```yaml
applies:
  since: "1.1.15"   # first version where this is true, or null
  until: null       # no known end — true from `since` onward until proven otherwise
```

Both keys are mandatory whenever `applies:` is present. Each is a quoted version or `null`.

- **Packs move the coarse boundary to the line.** A difference between 1.2 and 1.3 is two packs, not a range. A range
  is needed only for a boundary **inside** a line, such as a fact that changed in 1.3.1.
- **Ranges are file-level.** A row of a machine-read table cannot carry one yet; that is a stated limitation.
- **Do not range everything.** An over-gated fact base goes stale as fast as an unstamped one.

### 5. What `null` means in a range — carried forward

- **`until: null` — no known end.** The range is open-ended: true from `since` onward until proven otherwise. It does
  **not** mean "true at `dgf_version`", so a `since` above the stamp is legal.
- **`since: null` — no known lower bound.** Never substitute a floor value: that asserts a boundary nobody verified.
  The cost: the below-`since` error never fires for such a fact.

### 6. The version gate and the maintainer checks — changed: the gate is built

Tied to the exit-code contract in `.ai-factory/rules/base.md`.

**The version gate** runs in `/dgf-doctor`'s project mode. It reads only the project's `dgf.version`
([ADR 0019](0019-declared-dgf-version.md)) and compares it with the installed pack:

| situation | behaviour | exit |
|---|---|---|
| declared version **below** an installed fact's `since` | **error** — the fact is not true of their DGF | `1` |
| declared version **above** an installed fact's `until` | **warn** — possibly stale, not proven wrong | `2` |
| declared version **cannot be determined** (`unknown`) | **warn**, and say so | `2` |
| the declared version's line is not the installed pack's line | **warn**, with the exact `dgf-factory setup --dgf-version <v>` | `2` |
| same line, but the declared version is older than the pack's tag | **warn** — the pack may describe a patch the estate lacks; offer `get_release_notes` | `2` |
| the receipt records no line (installed before this ADR) | **warn** — re-run setup | `2` |

- **Blocking below `since` is the default because of an asymmetry.** Applying a newer *restriction* too early is
  merely over-strict. Claiming a newer *capability* too early tells the author to use something their runtime
  ignores, which is how `expandAll` sat inert for releases at a time.
- **A purely restrictive fact may opt out** with `out_of_range: warn`, and must say why.
- **Never proceed silently on an unknown version.**

**The digest checks** read the ledgers and run for a maintainer, never from a skill:

| situation | behaviour | exit |
|---|---|---|
| a ledger's upstream `sha256` no longer matches its line's release tag | **warn** — a maintenance signal | `2` |
| a vendored file no longer matches its `shipped_sha256` | **error** — the shipped copy was edited by hand | `1` |
| a newer release tag exists on a pack's line, or a release line has no pack | **warn** — a maintenance signal | `2` |

### 7. Keeping packs current — new

- **Detection is a script.** `tools/dgf_lines.py status <dgf-root> [--fetch]`:
  - **Inputs:** each registered line's pinned tag, its newest release tag, and the unreleased commits on its
    support branch.
  - **Drift:** each pack's ledgers checked at that tag.
  - **Schema set:** files added or removed upstream.
  - **Lines:** release lines with no pack.
  - **Contract:** it changes no knowledge file, so it is safe to schedule. `tools/dgf_lines_watch.sh` is the
    cron/launchd entry.
- **A line is read from its own checkout,** never by switching the maintainer's DGF working copy. A
  `git clone --shared` cache is detached at the tag's commit. `--fetch` (remote-tracking refs and tags) is the only
  write to the DGF repository.
- **Meaning is judgement, logged.** The maintainer skill `.claude/skills/dgf-sync/` (project-local, not shipped):
  1. reads each drifted source's diff between tags;
  2. classifies it COSMETIC / FACT-CHANGE / NEW-FACT;
  3. edits only the facts that moved;
  4. re-digests and re-vendors through the tools;
  5. runs the stamp check, the known-good corpus and the tests;
  6. writes a sync log per line and tag under `provenance/sync-log/`.
- **Unattended runs never merge.** An unattended run works on its own branch in its own worktree. It never commits to
  the base branch, never pushes and never merges; a maintainer reviews it.
- **A newer line** freezes the current `knowledge/` into `packs/<old>/`, then syncs `knowledge/` to the new line's tag.
  **An older or side line** is forked from the nearest pack, then synced.

### 8. Who carries the gate — changed

- **The shipped part:** the packs and their registry. `/dgf-doctor` reads the installed pack and the receipt.
- **The maintainer part:** the ledgers, the maintainer registry, the sync logs, the drift tools and the sync skill,
  under `provenance/`, `tools/` and `.claude/skills/`.

## Alternatives considered

- **Keep reading `Directory.Build.props`.** Rejected. It is deterministic and wrong: one value across three release
  lines.
- **`git describe` without `--exact-match`.** Rejected for ADR 0013's reason: it answers relative to the checked-out
  branch.
- **One knowledge base with row-level ranges for every line difference.** Rejected for now. The vendored schemas
  differ file by file between lines (camelCase regeneration, added properties), and a JSON schema cannot be ranged
  property by property without a rewriting validator. Ranges stay for within-line boundaries.
- **One npm package version per DGF line** (`@dgf-1.1`, `@dgf-1.3` dist-tags). Rejected. Every fix to a validator or a
  skill would be backported across branches of this repository. Packs keep one toolchain and vary only the facts.
- **Overlay packs that inherit unchanged files.** Rejected in §2: an inherited file's ledger describes another tag.
- **Infer the line from the estate.** Rejected for ADR 0019's reasons: nothing in a workspaces root states the DGF
  version, and consecutive releases validate the same configuration.
- **A CI job that syncs on a schedule.** Deferred. DGF is on Azure DevOps, which this repository's GitHub CI cannot
  read without a personal access token, and a decision on that secret. The detector runs locally meanwhile.
- **Sync unreleased branch tips.** Rejected in §1: the stamp would name a release that does not exist.

## Consequences

### Positive

- **Two projects on different DGF lines each get facts read at their own release.** A 1.1 estate no longer reads
  1.3's schemas, and the reverse.
- **The stamp tells the truth again.** It names a release that exists, and the doctor can compare it with the estate.
- **The version gate finally runs.** ADR 0019's key gains its consumer.
- **Drift becomes a scheduled signal instead of a memory.** The judgement it needs is written down per source.
- **Carried forward:** shipped knowledge carries no DGF paths; hand edits to vendored schemas are caught offline.

### Negative

- **The package grows by one pack per line,** about 3.6 MB unpacked each. A project installs one.
- **A maintainer keeps several packs current.** A structural correction may be needed in more than one pack.
- **Switching a project's line is a re-run of setup.** A receipt written by this version is refused by an older CLI,
  whose receipt reader rejects unknown keys.
- **A pack read at `X.Y.0` overstates nothing and understates the patches after it** until the next sync. The doctor
  says so only when the estate declares a later patch.
- **Ranges are file-level,** so a within-line difference in one table row ranges the whole file or waits for the next
  pack.
- **Carried forward:** two files change on every re-read (the fact file and its ledger); a developer reading an
  installed fact file cannot see its sources; stamping is discipline plus a structural check.

### Follow-ups

- A scheduled CI job against Azure DevOps, once a token and its scope are decided.
- Row-level `applies:` ranges in machine-read tables, if a within-line table difference appears.
- Report upstream to the DGF team: `<Version>` in `src/Directory.Build.props` is ClientDebug-only and repeats one
  value across three release lines. Carried forward from ADR 0013, sharpened.
- Report upstream: the 1.3.1 fragments disagree on `RenderType Internal`
  (`breaking-leandocpdf-replaces-syncfusion.md:10`, `bugfix-word-report-errors.md:12`,
  `breaking-remove-obsolete-document-engines.md:11`).
