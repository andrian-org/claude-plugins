[← DGF Schemas](../dgf-schemas.md) · [Back to README](../../README.md) · [Blueprint →](../blueprint.md)

# Architecture Decision Records

Decisions that shape this plugin, with the evidence they were made from. An ADR is
written when a choice would otherwise have to be re-derived — or re-argued — by the next
person to read the code.

## Index

| # | Title | Status | Date | Decides |
|---|-------|--------|------|---------|
| [0001](0001-independent-plugin-with-ai-factory-derived-architecture.md) | Independent plugin with AI Factory-derived architecture | accepted | 2026-09-21 | delivery model and architectural provenance |
| [0002](0002-process-verification.md) | Process verification is structural today, semantic by our own validators | accepted | 2026-09-21 | blueprint open question #5 |
| [0003](0003-version-gating.md) | Stamp every fact, gate only behavioural ones | accepted | 2026-09-21 | blueprint open question #6 |
| [0004](0004-authoring-entry-point.md) | Brownfield-first, scoped to the whole workspaces root | accepted | 2026-09-21 | blueprint open question #3 |
| [0005](0005-default-team-rules.md) | Seven shipped defaults for dotGov DGF systems | accepted | 2026-09-21 | blueprint open question #7 |

## Numbering

This plugin's ADRs are numbered from `0001` in this directory and are **independent of any
other repository's ADR series**. A bare `0001`–`0005` in this plugin always means a
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

`scripts/check-dual-schema-docs.sh` enforces the link in both directions: every ADR has an
index row here, and no blueprint question is marked answered without pointing at an ADR
file that exists.

## See Also

- [Architecture Blueprint](../blueprint.md) — the open questions these ADRs close
- [DGF Knowledge Sourcing](../dgf-knowledge.md) — the citation rule these ADRs inherit
- [DGF Schemas](../dgf-schemas.md) — the two schema families ADRs 0002 and 0003 depend on
