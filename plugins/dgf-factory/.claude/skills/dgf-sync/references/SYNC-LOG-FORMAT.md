# The sync log

One file per pack per sync: `provenance/sync-log/<YYYY-MM-DD>-<X.Y>-<X.Y.Z>.md`.

- **The date** is the day of the sync.
- **`X.Y`** is the line.
- **`X.Y.Z`** is the tag the pack was brought to.

It is maintainer material: never shipped, never read by a skill a developer runs. It records the judgement
`/dgf-sync` made, so the next maintainer can audit or redo it.

## Template

```markdown
# Sync <X.Y> → <X.Y.Z> (<YYYY-MM-DD>)

- Pack: `<knowledge/ or packs/X.Y/>`
- From: `<previous tag, or commit for a legacy pin>`
- To: `<X.Y.Z>` (`<commit>`)
- Mode: `sync` | `new-line` | `add-line --from <A.B>`
- By: `<maintainer, or "unattended — dgf_lines_watch.sh">`

## Summary

<two to five sentences: what changed in DGF for this pack, and what changed in the pack>

## Triage

| Knowledge file | Source | Class | What moved | Section edited |
|---|---|---|---|---|
| `schema-families.md` | `docs/wiki/AI-Authoring/format-coverage.md` | FACT-CHANGE | parity 67 → 69 rows: AutoComplete ✓, Chart ✓ (JSON forms only) | §6 |
| `reference-graph.md` | `…/InstanceHandler.cs` | COSMETIC | count API added; `@table` resolution unchanged | — |

## Schemas

<vendor_schemas.py's counts: files added, changed and removed, and the knowledge facts updated for them>

## Behaviour inside the line

<each `applies:` range added or closed, with the release note that proves it — or "none">

## Validators

<each validator change and its test — or "none">

## Known-good

<exceptions added and removed, each with its runtime citation — or "unchanged">

## Open

<anything not settled; an unattended run stops here — or "none">
```

## Rules

- **Every drifted source has one row.** That includes every `DRIFT_MISSING` source and the source that replaced
  it. The schema ledger's sources are summarised under `## Schemas`, not row by row.
- **DGF paths are allowed here.** This file is maintainer material (ADR 0030): cite the evidence exactly.
- **"What moved" is concrete.** Write old → new, a row name or a member name. A row that says "updated" is not
  a triage.
- **A sync that stopped** keeps its `## Open` section non-empty. It is not complete until a later sync, or the
  same one resumed, empties it.
