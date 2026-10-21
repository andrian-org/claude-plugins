---
id: 0019
title: The estate's DGF version is declared at setup and recorded in the pipeline config
status: accepted
date: 2026-09-25
deciders: [Andrian Mamei]
supersedes: []
tags: [versioning, setup, knowledge]
---

# 0019 — The estate's DGF version is declared at setup and recorded in the pipeline config

**Status: accepted** (2026-09-25, Andrian Mamei). It answers
[ADR 0013](0013-version-gating-provenance-ledger.md)'s follow-up "Decide how the version gate learns a
developer's DGF version" (`docs/adr/0013-version-gating-provenance-ledger.md:259-260`). It decides
where the version comes from and where it is kept. The gate that uses it is not built here.

## Context

Read on **2026-09-25** from this repository (`develop` at `a3e02a3`) and from the DGF repository at
`aa1d5c4c2`. DGF paths are relative to the DGF repository root.

- **The gate needs one input this plugin does not have.** ADR 0013 §4
  (`docs/adr/0013-version-gating-provenance-ledger.md:167-178`) compares the consumer's DGF version
  with a behavioural fact's `applies:` range: below `since` is exit `1`, above `until` is exit `2`,
  and "consumer DGF version **cannot be determined**" is exit `2`, with a warning that says so.
- **Nothing in a workspaces root states the DGF version.** No file in DGF's samples
  (`src/samples/workspaces/`) carries a DGF version key in XML, JSON or Markdown (grep for
  `dgfversion`, `dgf_version` and `frameworkversion`, 2026-09-25). `sitemap.json`'s
  `"version": "1.0.0"` (`src/samples/workspaces/dgf/FM/_COMPONENTS/sitemap.json:4`) is the site
  map's own version. The workspace readmes do not name one.
- **The UI's version is the container's build version, not DGF's.**
  `src/DGF.UI/src/app/interfaces/app-settings.type.ts:9` declares an optional `version`. The UI
  image takes it from build arguments (`src/DGF.UI/Dockerfile:1, 30`, defaults `0.0.1` and `alpha0`)
  and stamps it into `package.json` and a generated `version.ts` (`:36-42`). It is not reachable from
  the workspaces root, and it is whatever the build passed.
- **DGF's own version is in its build props.** `src/Directory.Build.props:33` holds
  `<Version>1.1.11</Version>`, which ADR 0013 found conditioned and lagging the release tags. The
  knowledge base's stamp reads it (`knowledge/README.md:24`, `dgf_version: "1.1.11"`). A developer's
  install has no DGF checkout ([ADR 0012](0012-no-dgf-paths-in-shipped-files.md)), so the plugin
  cannot read it for them.
- **No gate can fire yet.** No knowledge file outside `knowledge/README.md` carries an `applies:`
  range (grep of `knowledge/`, 2026-09-25). ADR 0013 stamps every fact and gates only behavioural
  ones, and no behavioural fact has been written.
- **Schemas do not reveal the version.** ADR 0013's Context records a TreeTable configuration that
  validates against the same schema in DGF 1.1.14 and 1.1.15 and behaves differently in them
  (`docs/adr/0013-version-gating-provenance-ledger.md:39-43`), so which schemas a configuration
  passes cannot tell the versions apart.

## Decision

**`/dgf` asks for the DGF version the estate runs and records it once, as `dgf.version` in
`.dgf-factory/config.yaml`. `unknown` is a permitted answer and is reported as a warning. The future
version gate reads only that key.**

- `/dgf` asks during setup and shows the knowledge base's stamp beside the question, so the
  developer sees which release the shipped facts were read from.
- The value is a quoted `X.Y.Z` or the string `unknown`:

  ```yaml
  dgf:
    version: "1.1.15"          # the DGF version this estate runs, or "unknown"
  ```

- `unknown` is ADR 0013 §4's "cannot be determined" row: a warning (exit `2`) that says so. `/dgf`
  repeats it in `.dgf-factory/DESCRIPTION.md`, so every later reader sees it.
- When the declared version is newer than the knowledge stamp, `/dgf` says the facts were read at an
  older release and offers the DGF docs MCP's `get_release_notes("since:<stamp>")`.
- `/dgf` owns the key. A re-run of `/dgf` may change it; no other skill writes it.
- **The gate itself is a follow-up.** It has no input until a behavioural fact with an `applies:`
  range exists. When it lands, it reads `dgf.version` and nothing else.

## Alternatives considered

- **The UI container's build version.** Rejected: it is not reachable from the workspaces root, and
  it is the image's build argument, not DGF's version.
- **The estate repository's git tags.** Rejected: they version the estate, not the DGF it runs on.
- **Ask on every run.** Rejected: the answer does not change between runs, and asking again invites
  a different answer to the same question.
- **Infer the version from which schemas validate.** Rejected: consecutive releases validate the
  same JSON (ADR 0013 §Context), so validation cannot tell them apart.

## Consequences

### Positive

- The version gate has a defined, single input before it is written, so it needs no new decision
  when the first behavioural fact lands.
- `unknown` is honest: the gate warns instead of guessing.
- The developer sees, at setup, how far the shipped facts are from their release.

### Negative

- **A declared value can be wrong, and it goes stale** when the estate upgrades DGF and nobody
  re-runs `/dgf`. Nothing checks it against a deployment.
- One more setup question, and one more key to keep correct.
- Until the gate exists, the key is recorded and shown but decides nothing.

### Follow-ups

- Build the version gate once a behavioural fact with an `applies:` range exists (ADR 0013 §4). It
  reads `dgf.version`.
- Consider a staleness prompt — for example when the knowledge stamp moves past the declared
  version — after the first estates have been set up.
