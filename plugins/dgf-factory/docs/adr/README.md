[← DGF Schemas](../dgf-schemas.md) · [Back to README](../../README.md) · [Blueprint →](../blueprint.md)

# Architecture Decision Records

Decisions that shape this plugin, with the evidence they were made from. An ADR is
written when a choice would otherwise have to be re-derived — or re-argued — by the next
person to read the code.

## Index

| # | Title | Status | Date | Decides |
|---|-------|--------|------|---------|
| [0001](0001-independent-plugin-with-ai-factory-derived-architecture.md) | Independent plugin with AI Factory-derived architecture | accepted | 2026-09-21 | delivery model and architectural provenance |
| [0002](0002-process-verification.md) | Process verification is structural today, semantic by our own validators | superseded-by-0006 | 2026-09-23 | blueprint open question #5 — replaced by 0006 |
| [0003](0003-version-gating.md) | Stamp every fact, gate only behavioural ones | superseded-by-0008 | 2026-09-23 | blueprint open question #6 — replaced by 0008 |
| [0004](0004-authoring-entry-point.md) | Brownfield-first, scoped to the whole workspaces root | accepted | 2026-09-21 | blueprint open question #3 |
| [0005](0005-default-team-rules.md) | Seven shipped defaults for dotGov DGF systems | accepted | 2026-09-21 | blueprint open question #7 |
| [0006](0006-process-verification-revised.md) | Process verification — structure with a runtime-divergence allowance, semantics by our own validators | accepted | 2026-09-23 | blueprint open question #5; the semantic checks of milestone 8 |
| [0007](0007-validator-runtime.md) | Validators run on Python with lxml and jsonschema | accepted | 2026-09-23 | validator runtime and dependencies |
| [0008](0008-version-gating-revised.md) | Stamp every fact, gate only behavioural ones (revised) | accepted | 2026-09-23 | blueprint open question #6; version source and range semantics |
| [0009](0009-plan-ledger-scope.md) | One plan ledger at workspaces-root scope, partitioned by affected workspaces | accepted | 2026-09-23 | plan-ledger contention (ADR 0004 follow-up): `affects_workspaces` per plan, multi-workspace plans allowed |
| [0010](0010-dgf-implement-scope.md) | /dgf-implement composes configuration, modern JSON first, and writes JS or CSS only where configuration cannot | accepted | 2026-09-23 | blueprint open question #4: JSON under `FM/_COMPONENTS/` first, XML only without a JSON alternative, a little JS/CSS only where configuration cannot |
| [0011](0011-schema-parity-authority.md) | Resolve the schema family first; format-coverage.md is the only runtime-parity authority | proposed | 2026-09-23 | dual-schema and parity rule; due before milestone 8's parity check |

## Numbering

This plugin's ADRs are numbered from `0001` in this directory and are **independent of any
other repository's ADR series**. A bare four-digit number in this plugin always means a
dgf-factory ADR. When citing an ADR from another repository, always qualify it with that
repository's name — never with a bare number.

## Frontmatter contract

Every ADR opens with YAML frontmatter:

```yaml
---
id: 0001                      # matches the filename prefix
title: <the decision, as a noun phrase>
status: accepted              # see vocabulary below
date: 2026-09-21              # when the status last changed
deciders: [<who>]             # a person or role, not "the team"
supersedes: []                # ADR ids this replaces, e.g. [0002]
tags: [delivery, knowledge]   # free-form, for grouping
---
```

Status vocabulary: `proposed` | `accepted` | `rejected` | `superseded-by-NNNN`.

An ADR is never edited to reverse its decision. Write a new one, set the old one's status
to `superseded-by-NNNN`, and list the old id in the new one's `supersedes`.

### Supersession is always full

A successor **restates every section of the old ADR that is still valid**, and then
changes what needs changing. A reader never has to combine two ADRs to learn what is
decided: the newest one in a chain is complete on its own. The superseded ADR changes only
its `status` and `date` — its body stays exactly as written, as the record of what was
believed and why.

The vocabulary has no "partially superseded" status on purpose. An ADR that is half right
is replaced whole.

### Errata — the only permitted in-place edit

An ADR may be edited in place **only** to correct a fact that does not change what it
decides: a wrong line number, a miscounted list, a misnamed owner. Every such correction is
recorded in a dated `## Errata` section at the end of the ADR:

```markdown
## Errata

- **2026-09-23** — §Consequences said "three of seven" rules were enforceable; it is four
  (rules 1, 2, 3 and 7). Source: this ADR's own enforcement tables.
```

Each entry starts with a `YYYY-MM-DD` date and names what was wrong, what is right, and
where that was read from. If a correction would change the decision, it is not an erratum —
write a superseding ADR.

A superseded ADR takes no errata. Corrections to it belong in its successor's Context.

A `proposed` ADR is a draft. It decides nothing yet, so it may be edited freely, without
errata, until it is accepted, rejected or superseded.

## Section contract

```markdown
## Context          — measured evidence, dated, with file paths. What was true when we decided.
## Decision         — imperative. A bolded one-line statement first, then the detail.
## Alternatives considered  — what else was on the table and why it lost.
## Consequences     — positive / negative / follow-ups. Negative is not optional.
```

Two rules that matter more than the shape:

- **Context cites, it does not recall.** Every claim carries the file path and line it was
  read from, and the date it was read. A claim that cannot be cited does not belong in an
  ADR — it belongs in the follow-ups as something to verify.
- **Consequences must include what this costs.** An ADR with only positive consequences has
  not finished thinking. If a decision has no downside, it was not a decision.

## Relationship to the blueprint

[`docs/blueprint.md`](../blueprint.md) §"Open questions to resolve before writing skills"
is the question list; this directory holds the answers. The blueprint's question text is
**never edited** — it is the historical record of what was unknown. An answered question
gains an `ANSWERED` block linking the ADR that decided it.

When the ADR that answered a question is superseded, the `ANSWERED` block gains a
`Revised (<date>)` sentence and its link moves to the successor. The superseded ADR may
still be named in plain text ("originally ADR 0002"), but never linked from that block.

A `proposed` ADR does not answer anything. It is never linked from a blueprint line that
contains the word `ANSWERED` — including "SUBSTANTIALLY ANSWERED". A pending decision is
linked from a separate line:

```markdown
   > **DECISION PENDING** — [ADR NNNN](adr/NNNN-<slug>.md) (proposed).
```

`scripts/check-dual-schema-docs.sh` enforces the link in both directions: every ADR has an
index row here, and no blueprint question is marked answered without pointing at an ADR
file that exists. It also enforces supersession integrity: a `superseded-by-NNNN` status
names a successor that exists and lists the old id in its `supersedes`; every id in a
`supersedes` list is marked superseded by that ADR; no `ANSWERED` line links a superseded
ADR; and each index row's Status cell matches its ADR's frontmatter.

## See Also

- [Architecture Blueprint](../blueprint.md) — the open questions these ADRs close
- [DGF Knowledge Sourcing](../dgf-knowledge.md) — the citation rule these ADRs inherit
- [DGF Schemas](../dgf-schemas.md) — the two schema families ADRs 0006, 0007 and 0008 depend on
