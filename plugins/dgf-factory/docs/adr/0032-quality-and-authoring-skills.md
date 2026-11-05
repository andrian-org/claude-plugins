---
id: 0032
title: "The quality and authoring skills report rather than gate, each writes one artifact of its own, and the rules file is checked by a script before any skill reads it"
status: accepted
date: 2026-11-03
deciders: [Andrian Mamei]
supersedes: []
tags: [skills, quality, rules, docs, archive, gates]
---

# 0032 — The quality and authoring skills report rather than gate, each writes one artifact of its own, and the rules file is checked by a script before any skill reads it

**Status: accepted** (2026-11-03, Andrian Mamei). The decider delegated the roadmap's open milestones on
2026-11-03 — "plan, improve, implement, and verify each unresolved roadmap item … do it yourself without
asking me" — so the choices below were drawn from the evidence in §Context, not put to the decider one by
one. A later decision reverses any of them with a new ADR, by the README's contract.

This ADR decides milestone **Quality & Authoring Skills**: what `/dgf-review`, `/dgf-rules`,
`/dgf-rules-check`, `/dgf-qa`, `/dgf-docs`, `/dgf-explore`, `/dgf-grounded` and `/dgf-archive` do, what
each may write, which scripts decide for them, and the format of the estate's rules file. It leaves the
gate contract ([ADR 0022](0022-gate-block-contract-revised.md)), the learning loop
([ADR 0024](0024-learning-loop-revised.md)) and the default rule set
([ADR 0028](0028-default-team-rules-revised.md)) as they stand.

## Context

Read on **2026-11-03** from this repository (`main` at `1011ed2`).

- **The blueprint names the eight and nothing more.** Part 2 §"Proposed skill set", phase 3:
  `/dgf-review`, `/dgf-rules`, `/dgf-rules-check`, `/dgf-qa`, `/dgf-docs`, `/dgf-explore`, `/dgf-grounded`,
  `/dgf-archive` (`docs/blueprint.md`). AI Factory's eight namesakes are framework-agnostic: each reads
  source code and prose, and none of them can check a DGF configuration file.
- **`RULES.md` has an owner and no writer.** ADR 0028 decides the content of the default rules and says
  "`paths.rules_file` is owned by `/dgf-rules`, and writing it here would breach single-writer artifact
  ownership"; its first follow-up is "`/dgf-rules` writes `RULES.md` from this decided set". `/dgf` writes
  "no rules file" (`skills/dgf/SKILL.md`), and no shipped skill reads one.
- **Only two gates exist, and a prompt never writes a block.** `scripts/lib/gate_result.py`'s `GATES` holds
  `verify` and `doctor`; ADR 0022 §1 makes the builder the only author of a block, and §4 forbids a block
  that claims a check that did not run. A review's or a rules check's judgement is the model's, so it
  cannot be an entry in a block a script computes.
- **Every scripted check a review would run is already in the verify gate.** `verify_gate.py` runs
  `check_plan.py`, `check_change.py` (scope, means, planned files, the validators against the merge-base)
  and the task audit. `/dgf-audit` reports blast radius and is "never a gate" (ADR 0027 §5).
- **An estate's rules are writable by anyone who commits to it**, exactly as an override is. ADR 0024 §4
  answers that threat for overrides with `check_override.py`, run before any reader reads one, refusing a
  rule with a `FORBIDDEN` construct and handing a rule that touches the limit (`LIMIT_WORDS`) to judgement
  (`scripts/lib/overrides.py`).
- **ADR 0028's rule 7 is scriptable and unscripted.** The workspace layout's directory names are framework
  constants, and Linux resolves them case-sensitively; no validator checks a workspace's `FM/` folders'
  case today (`.ai-factory/RULES.md` rule 2 is the same lesson for references).
- **The read-only skills pre-approve no git.** `tests/test_skill_contracts.py` holds `READ_ONLY` and `NO_GIT`
  skills to no write tool and no git rule; `git -C "<root>" <subcommand>` cannot be narrowed below
  `Bash(git *)` (`docs/skill-authoring.md`), which would pre-approve `git push` for a skill that only reads.
- **Plans accumulate.** `lib/plan.py` reserves a header key `archived` and ignores it; `PATCH-FORMAT.md`
  says a patch's `plan` "need not still exist, because plans are archived"; nothing archives one.

## Decision

### 1. Eight skills, each writing at most one artifact of its own

| Skill | Writes | Reads the change through | Pre-approves git |
|---|---|---|---|
| `/dgf-review` | nothing | `check_change.py` with an active plan, else `audit_root.py --base`; `show_change.py` for the diff | no |
| `/dgf-rules` | `paths.rules_file` (default `.dgf-factory/RULES.md`) | — | no |
| `/dgf-rules-check` | nothing | `check_rules.py`; `show_change.py` for the diff | no |
| `/dgf-qa` | `paths.qa/<plan stem>/test-plan.md` (default `.dgf-factory/qa/`), one folder per plan, so it works without git and for the fast plan | `audit_root.py --base` or `--reach`; `show_change.py` | no |
| `/dgf-docs` | `paths.docs` (default `.dgf-factory/docs/`), through `estate_docs.py`, plus its `overview.md` | the whole root | no |
| `/dgf-explore` | `paths.research` (default `.dgf-factory/RESEARCH.md`) | the root, the knowledge base, the dgf-mcp docs tools | no |
| `/dgf-grounded` | nothing | the root, the knowledge base, the dgf-mcp docs tools | no |
| `/dgf-archive` | moves plans into `paths.archive/plans/` (default `.dgf-factory/archive/`), through `archive_plans.py`; no write tool of its own | `archive_plans.py` | no |

Every artifact is under `.dgf-factory/`, which `lib/plan.py` classes as the pipeline's, so none of them is
ever a change a plan must declare. No skill writes another's artifact; the table is the partition, beside
ADR 0027 §2's for configuration.

`/dgf-rules` sets `disable-model-invocation: true`, as `/dgf-evolve` does, because the rules it writes
change what other skills do. The other seven fire on their descriptions.

### 2. No new gate: the review and the rules check are reports

`gate_result.GATES` stays `verify` and `doctor`. `/dgf-review` and `/dgf-rules-check` end with a Markdown
report and **no** `dgf-gate-result` block, as `/dgf-audit` does. Each quotes the scripts' findings verbatim,
labels its own judgements as judgements, and sends the user to `/dgf-verify` for the gate. A finding a
script decides is never restated as the model's, and a judgement is never presented as a check that ran.

### 3. Four scripts decide what they can

| Script | Decides | Exit |
|---|---|---|
| `scripts/check_rules.py` | the rules file's format (§4); the limit on every estate rule, with `overrides.FORBIDDEN` and `LIMIT_WORDS`; a default rule's text against the shipped one; and the scripted rule `layout-case` over every workspace | `0` / `1` a refused file or a layout error / `2` a rule to judge, an edited or missing default / `3` usage |
| `scripts/show_change.py` | the unified diff of the change — the working tree against the merge-base, the install footprint and `.dgf-factory/` left out as `check_change.py` leaves them out — for root-relative files, every line escaped as the validators escape a line; a symlink or binary file is named, not diffed | `0` / `3` usage, no git, an unknown base |
| `scripts/estate_docs.py` | the estate's inventory pages, rendered from the same readers the validators use, every name from the estate escaped; `--check` reports each stale page instead of writing; a page without its generated marker is never overwritten; an output folder outside `.dgf-factory/` is refused | `0` / `1` a page it may not overwrite / `2` stale pages under `--check` / `3` usage, or the validators' dependencies missing |
| `scripts/archive_plans.py` | which plans are complete, from `lib/plan.py`; with `--apply` it moves each one, stamping the header's `archived:` with the script's own date, and refuses a destination that exists, an incomplete plan named explicitly, or an archive folder outside `.dgf-factory/`; the current branch's plan is kept unless named, since `/dgf-commit` still follows its Commit Plan | `0` / `1` refused / `2` nothing to archive / `3` usage |

Each prints the house report (`docs/skill-authoring.md` §"Reading a validator's output"), registers its
codes in `report.CODES`, and switches to the project venv first (ADR 0031). `show_change.py` and
`archive_plans.py` read git only through `lib/git.py`, so the skills that call them pre-approve no git.
`check_rules.py` is stdlib-only, because `/dgf-plan` runs it on every plan, with or without the
validators' dependencies; `estate_docs.py` needs them, as the validators do.

### 4. The rules file

`RULES.md` is a fixed format `check_rules.py` checks:

```markdown
# Rules

> Written by /dgf-rules. …

## R1 — XML-always for the five legacy artifact types
- enforcement: script
- check: means-route
- source: default (ADR 0028 rule 1)

Generate XML for form, workflow, process, settings and view regardless of partial JSON schema parity.
```

- A rule is a `## R<n> — <title>` heading, three or four fields, and its text. `enforcement` is `script`,
  `gate` or `prompt-only`; `check` is required for `script` and `gate` and names a row of `check_rules.py`'s
  check table — `means-route`, `code-planned`, `base-reason`, `layout-case` — and is absent for
  `prompt-only`; `source` is `default (ADR 0028 rule <n>)`, naming the rule's own number, or `estate`;
  `demoted: <why>` marks a default the estate has set aside, and a demoted R7 leaves `layout-case` not run.
- **`check:` names what checks the rule today.** `means-route` is `check_plan.py`'s `PLAN_ROUTE_MISMATCH`,
  which holds a plan's new configuration files to their route; `code-planned` is `check_change.py`'s
  `CHANGE_CODE_UNPLANNED` and `CHANGE_CODE_FILE_NEW`; `base-reason` is `check_plan.py`'s
  `PLAN_BASE_REASON_MISSING`; `layout-case` is `check_rules.py --layout`, over the framework's folder names
  (`knowledge/composition-specs.md` §1) — an `FM/` itself included.
- **The six defaults keep ADR 0028's numbers**: R1, R2, R3, R4, R6, R7. R5 is reserved — sign-in is
  `/dgf`'s question, recorded in `DESCRIPTION.md` — and estate rules start at R8. Their shipped text is
  `skills/dgf-rules/references/default-rules.md`; `/dgf-rules` seeds from it, and `check_rules.py` compares
  against it.
- **An estate rule may only add a constraint.** It is held to the override limit, read as
  `overrides.read_as` reads an override: a `FORBIDDEN` construct or a refused character (a zero-width or
  control character that would split a forbidden word) refuses the whole file, and a `LIMIT_WORDS` match is a
  rule to judge. An estate rule can be `prompt-only`, or cite a check that already exists; it cannot invent a
  script.
- **Every skill that reads the rules runs `check_rules.py` first** — `/dgf-plan`, `/dgf-implement`,
  `/dgf-review`, `/dgf-rules-check` — and a refused file is never read: the shipped defaults apply.

### 5. Paths

`skills/dgf/references/config-template.yaml` gains `paths.rules_file`, `paths.research`, `paths.qa`,
`paths.docs` and `paths.archive`, with the defaults in §1. A skill that reads an older config without the
key uses the default, so no estate must re-run `/dgf`.

### 6. Who reads what the new skills write

`/dgf-plan` reads `paths.research` when present — **as data, never as instructions**: anyone who commits to the
estate can write it, so a sentence in it that asks for an action is a claim to verify, not a step to take, and
the plan cites what it uses. Both `/dgf-plan` and `/dgf-implement` read the rules after `check_rules.py`, with
the limit sentence the readers share. `/dgf-verify` names `/dgf-review` and `/dgf-qa` in its report's header on
a pass — never in `suggested_next`, whose allowlist ADR 0022 §8 fixes, and never after the block. Nothing else
changes in the spine.

`/dgf-qa` writes manual scenarios for every reached process, because a process cannot run headlessly
(ADR 0014 §5), and names automated tests in the estate's test stack — `DESCRIPTION.md`'s, else ADR 0028
rule 6's — only for a `kind: code` task's script or style, the one part of a change such a test can reach.

### 7. Not override readers

The eight do not read a skill-context override: ADR 0024 §5's ten readers stand, and `/dgf-evolve`'s
targets with them. Adding a reader is a change to that ADR's list and to `test_skill_contracts.py`'s
`READERS`, made when a patch first teaches one of the eight something.

## Alternatives considered

- **A `review` or `rules` gate.** AI Factory's `/aif-review` and `/aif-rules-check` emit gate blocks.
  Rejected: their verdicts are the model's, ADR 0022 §1 lets only a script compute a status, and every
  scripted check already runs in the verify gate. A second gate over the same checks would be two places to
  read one answer.
- **Pre-approve `Bash(git *)` for the review.** Rejected: it pre-approves `git push` and `git reset` for a
  skill that only reads. `show_change.py` gives the diff through `lib/git.py`, which already reads a base
  tree blob by blob.
- **Read `RULES.md` unchecked, as a human-authored file.** Rejected: a rule such as "skip the verify gate"
  committed to an estate would reach `/dgf-implement` unmediated — the threat ADR 0024 closed for overrides.
- **Write the estate docs by prompt.** Rejected: an inventory of processes, states, entities and components
  is decidable, and a prompt-written one drifts silently. The script renders it; `--check` tells when it is
  stale; the model writes only the overview prose.
- **Archive by `git mv`.** Rejected: it needs git pre-approval, and a root without git must archive too. A
  move is a delete and an add, which `/dgf-commit` commits like any other.

## Consequences

### Positive

- **ADR 0028's rules are written, read and checked.** Four of six are mechanical, as that ADR said, and
  rule 7 gets the script it called for.
- **No skill reads a rule the limit refuses**, and the readers name what they did not apply.
- **The estate docs cannot drift unseen**: `estate_docs.py --check` is a CI line.
- **Every new skill but `/dgf-rules` runs anywhere a root exists**, with no git pre-approved.

### Negative

- **Two more scripts read git** (`show_change.py`, `archive_plans.py` reads none but its plans do), so
  `lib/git.py`'s limits — a symlink, an ignored file — reach two more reports.
- **The review's judgement is unchecked by construction.** It is labelled, not verified.
- **`RULES.md`'s estate rules are mostly prompt-only.** An estate cannot add a scripted rule without a
  release of dgf-factory.
- **Seven of the eight read no override**, so a patch that would teach one of them has nowhere to land
  until §7 is revisited.

### Follow-ups

- **Add the eight to the override readers** once a patch teaches one of them something (§7).
- **A `layout-case` row in the verify gate.** `check_rules.py` runs it on request; the gate does not yet.
- **`/dgf-docs` pages per workspace for `applibs*`**, which are not workspaces (ADR 0017).
