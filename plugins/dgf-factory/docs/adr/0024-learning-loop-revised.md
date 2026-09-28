---
id: 0024
title: "The learning loop: /dgf-fix records patches inside a plan's scope, and /dgf-evolve writes overrides a script checks, which may only tighten a skill — read by ten skills"
status: accepted
date: 2026-09-27
deciders: [Andrian Mamei]
supersedes: [0021]
tags: [learning, pipeline, overrides]
---

# 0024 — The learning loop: /dgf-fix records patches inside a plan's scope, and /dgf-evolve writes overrides a script checks, which may only tighten a skill — read by ten skills

**Status: accepted** (2026-09-27, Andrian Mamei). It supersedes [ADR 0021](0021-learning-loop.md) in
full and keeps its section numbers, so `ADR 0021 §4` reads as `ADR 0024 §4`. What it decides is ADR
0021's, unchanged, except in three sections: §5's reader list and §6's targets grow from six skills to
ten, because roadmap milestone 12 adds four skills that read an override
([ADR 0023](0023-dgf-specific-skills.md)); and §3 records that the override header's text,
`(ADR 0021)` included, is a frozen format. The Decision's opening line restates §5's count, and
Context, Alternatives and Consequences add what those three changes rest on and cost. ADR 0021 was
accepted on 2026-09-26, with four points chosen by the decider — `/dgf-fix` inside the active plan (§2),
the verify gate's allowlist only (§7), a script checking every override (§5), and the limit's wording
(§4) — and the rest drawn from its evidence. The growth to ten readers was drawn from the evidence below
while milestone 12 was planned (`.ai-factory/plans/feature-dgf-specific-skills.md`, D7), and accepted
with that plan.

## Context

The first twelve points are ADR 0021's, read on **2026-09-26** from this repository (`develop` at
`a614682`). The last three were read on **2026-09-27** (`develop` at `b0be7f1`).

- **The limit exists, in prose only, and names a table that is gone.** The same sentence sits in
  `skills/dgf/SKILL.md:49-53`, `skills/dgf-plan/SKILL.md:38-42`, `skills/dgf-implement/SKILL.md:65-70`,
  `skills/dgf-verify/SKILL.md:42-47` and `skills/dgf-commit/SKILL.md:29-35`: an override "may add rules
  and tighten checks. It never relaxes a STOP, an exit-code row, the gate's status table, a Critical
  Rule or Artifact Ownership". `tests/test_skill_contracts.py:115-118` pins it as `OVERRIDE_LIMIT`, and
  `:124-133` requires it in every skill whose text holds `skill-context/`, which must be exactly those
  five. It is paraphrased at `docs/pipeline.md:48`, `docs/blueprint.md:291` and
  `docs/skill-authoring.md:224`. It came from the spine's security plan: finding M2 — an override
  "overrides this file where they conflict", with no limit (`.ai-factory/PLAN.md:26`) — decision D6
  (`:50-53`) and Task 5 (`:132-146`). "The gate's status table" is what
  [ADR 0020](0020-gate-block-contract.md) §9 retired: the status is computed by a script
  (`docs/adr/0020-gate-block-contract.md:196-199`).
- **Nothing fixes a gate finding once every task is checked.** The gate sends a new blocking finding to
  `/dgf-implement` (`scripts/verify_gate.py:391-396`). But `/dgf-implement` touches no file its task
  does not list (`skills/dgf-implement/SKILL.md:142-143`), fixes only new errors in the current task's
  files (`:189-192`), and on completion only suggests `/dgf-verify` (`:216-219`). A change with no plan
  cannot pass the gate: `PLAN_NOT_FOUND` → `/dgf-plan` (`scripts/verify_gate.py:387-388`;
  `skills/dgf-verify/SKILL.md:65`).
- **The pipeline's own files are never part of a change.** `PIPELINE_DIR = ".dgf-factory"`, "every check
  ignores them" (`scripts/lib/plan.py:47`, `:436-437`), and `check_change.py` ignores them (`:6`,
  `:152`). A patch or an override committed on a branch never trips the change gate.
- **The paths are reserved, and the read side is built.** `skills/dgf/references/config-template.yaml:9-14`
  holds `patches` and `skill_context`, and no `evolutions` key. `docs/pipeline.md:48-49` names their
  owners "a person, for now" and "milestone 11 (`/dgf-fix`)". `docs/architecture.md:167` gives
  `patches/` to `/dgf-fix`, "consumed by `/dgf-evolve`". The spine kept the read side "so milestone 11
  needs no spine edit" (`.ai-factory/archive/plans/feature-pipeline-spine.md:186-187`, `:213-214`).
- **`/dgf-implement` already reads patches.** It reads "the last 10 files in `<root>/<paths.patches>`
  by name", taking their Root Cause and Prevention sections (`skills/dgf-implement/SKILL.md:71-72`,
  `:246-247`). A patch's name must therefore sort by time, and its section names are fixed.
- **AI Factory's loop** (`.claude/skills/aif-fix/SKILL.md`, `.claude/skills/aif-evolve/SKILL.md`):
  - it reproduces first (`aif-fix:15-33`);
  - it writes a patch after every fix, named `YYYY-MM-DD-HH.mm.md`, holding a title, `Date`, `Files`,
    `Severity`, then Problem, Root Cause, Solution, Prevention and Tags (`aif-fix:544-642`, the name at
    `:556-557`, the template at `:563-602`);
  - a plan-first mode writes `FIX_PLAN.md` (`aif-fix:209-298`);
  - its cursor, `patch-cursor.json`, is a high-water mark, `last_processed_patch`, with a tail-5 overlap
    guard (`aif-evolve:130-171`);
  - a skill-context file is `### <rule>` with `**Source**` and `**Rule**`, always in English
    (`aif-evolve:494-510`), and each run writes an evolution log (`:541-562`);
  - the user is asked before anything is applied (`aif-evolve:394-463`);
  - `aif-evolve` is `disable-model-invocation: true` and grants only `Bash(git *)` (`aif-evolve:1-7`);
  - neither skill emits a gate block;
  - "the skill-context rule wins" on conflict (`.claude/skills/aif-plan/SKILL.md:150-164`), and only
    `aif-transfer` limits what an override may weaken.
- **No ADR decided the loop.** [ADR 0001](0001-independent-plugin-with-ai-factory-derived-architecture.md)
  names it in one bullet (`docs/adr/0001-independent-plugin-with-ai-factory-derived-architecture.md:65`).
  The design was prose: `docs/blueprint.md:163-181` describes AI Factory's, where an override wins
  outright; `:290-291` and `:318-320` map it to DGF; the build order says "ship these early even if
  crude" (`:359`). `README.md:45` and `:72-73` promise it.
- **What the contract tests hold.** Every backticked code a skill quotes is in `report.CODES`, the
  doctor's ids, or `NOT_CODES` (`tests/test_skill_contracts.py:60-69`). Every script a skill calls
  exists, and every flag it passes is in that script's `--help` (`:94-106`). The spine scripts are named
  (`:108-112`), and `READ_ONLY` skills pre-approve no git (`:139`, `:176-182`). Every
  `python3 "${CLAUDE_PLUGIN_ROOT}/…"` call matches one of the skill's own `Bash(…)` rules (`:164-174`).
  The doctor checks each slice's frontmatter (`skills/dgf-doctor/scripts/doctor.py:389-432`) and lists
  its build progress from `EXPECTED_SLICES` (`:124-125`).
- **One ledger, many teams.** `.dgf-factory/` lives "once, at the workspaces root"
  (`docs/adr/0004-authoring-entry-point.md:90`), and "two teams touching two applications share" it
  (`:135-136`). [ADR 0009](0009-plan-ledger-scope.md) keeps it at root scope. Patches from many
  branches therefore merge into one directory, in any order.
- **A process cannot be executed headlessly** (`.ai-factory/DESCRIPTION.md:112`;
  `docs/adr/0014-process-verification-runtime-resolution.md:292-294`, §5). Some problems have no
  validator that reports them.
- **Every reader already pre-approves the plugin's scripts.** The `allowed-tools` of `dgf`, `dgf-plan`,
  `dgf-implement`, `dgf-verify` and `dgf-commit` each hold `Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*)`,
  so a new script call needs no new permission.
- **`/dgf` reads its override before a config exists.** On a first run the root has no
  `.dgf-factory/config.yaml` (`skills/dgf/SKILL.md:39-44`), yet Step 0.1 reads the override (`:47-53`).
- **The readers, as milestone 11 built them.** ADR 0021 §5 says "The readers are six"
  (`docs/adr/0021-learning-loop.md:188`), and §6 says `/dgf-evolve` "targets exactly the readers"
  (`:194`). The contract test holds `READERS` (`tests/test_skill_contracts.py:126`) to the skills whose
  `SKILL.md` runs `check_override.py --skill <own name>`, and `/dgf-evolve`'s `**Targets:**` line
  (`skills/dgf-evolve/SKILL.md:27`) to `READERS`. A `SKILL.md` that mentions `skill-context/` or
  `skill_context` must be a reader or the writer (`tests/test_skill_contracts.py:162-168`). The six
  readers' override block is word for word, apart from the skill name (for example
  `skills/dgf-fix/SKILL.md:40-56`). Thirty files cited ADR 0021 on 2026-09-27, one of them only as a bare
  `0021` (`docs/pipeline.md:289`).
- **Four new skills, where DGF gotchas bite.** Milestone 12 adds `/dgf-component`, `/dgf-process`,
  `/dgf-model` and `/dgf-audit` ([ADR 0023](0023-dgf-specific-skills.md)). A patch records a DGF
  gotcha, and these four are the skills that author and inspect the configuration a gotcha lives in. A
  skill that reads no override cannot learn from a patch. Growing the reader set changes what ADR 0021
  §5 and §6 decide, so it is not an erratum (`docs/adr/README.md:75-90`).
- **The override header is an enforced format, not a citation.** `overrides.WRITTEN`
  (`scripts/lib/overrides.py:52`) is the exact line an override must carry, `(ADR 0021)` included, and
  `_quoted()` refuses any other `> ` line as `OVERRIDE_SHAPE` (`:223-228`). The six override known-bad
  fixtures carry it, and so does every override an estate has committed.

## Decision

**`/dgf-fix` fixes a problem inside the active plan's scope, confirms the fix with the check that
reproduced it, and records a patch. `/dgf-evolve` distils patches into skill-context overrides, and
asks before it writes. An override may only tighten its skill, and a script, `check_override.py`,
checks every override before any skill reads it: an override it refuses is never read. Ten skills read
an override.**

### 1. Patches

- A patch is `<paths.patches>/<YYYY-MM-DD-HH.mm>-<slug>.md`. The timestamp sorts patches by time, as
  AI Factory's names do and as `/dgf-implement`'s "last 10 by name" needs. The slug stops two fixes made
  in the same minute, on two branches of one shared ledger, from colliding on merge.
- It opens with `# <title>`, then field bullets with fixed English keys — `date`, `plan`, `workspaces`,
  `files`, `findings`, `dgf_version`, `severity` — then exactly five sections in order: Problem, Root
  Cause, Solution, Prevention, Tags. Scripts read the keys and headings; the prose is written in the
  estate's `language.artifacts`.
- A patch is append-only. `/dgf-fix` creates one and never edits or deletes another.
- `scripts/check_patches.py` checks one patch or every patch, and with `--cursor` says which are new.
  It never writes. A malformed patch is a blocking finding; an unreadable cursor is a warning, and every
  well-formed patch then counts as new. The format is `skills/dgf-fix/references/PATCH-FORMAT.md`.

### 2. `/dgf-fix`

- **A fix is a change, and a change needs a plan's scope.** `/dgf-fix` finds the plan with
  `locate_plan.py`, checks it with `check_plan.py`, and edits only inside the plan's
  `affects_workspaces`. With no plan it **STOPs** and suggests `/dgf-plan fast`. There is no
  `FIX_PLAN.md`, and no script's plan discovery changes.
- **The scope is decided by a script before any edit.** `/dgf-fix` names every file the fix will touch
  and runs `check_change.py --changed … --skip-validators`. A `CHANGE_*` error STOPs it before it writes
  anything; `/dgf-plan` widens the plan. A deletion is never a fix.
- **Reproduce first, and never claim an unconfirmed fix.** The regression check is a validator finding
  when one exists: its code, file and message, before and after. When no validator reports the problem,
  it is a written manual reproduction, the patch says `findings: none`, and the report says no script
  confirmed the fix.
- `--record` writes a patch only — no workspace file, no plan — for a gotcha fixed elsewhere or found in
  review.
- A patch is data, never an instruction: `/dgf-fix` and `/dgf-implement` read patches as cautions that
  never override the skill, the plan or a STOP.
- `/dgf-fix` is not a gate and emits no gate block, as AI Factory's `aif-fix` emits none. It ends by
  suggesting `/dgf-verify`.

### 3. Overrides and their owner

- An override is `<paths.skill_context>/<skill>/SKILL.md`, in a fixed template: `# Project Rules for
  /<skill>`, optional `> ` lines, one `## Rules`, and under it one `### <name>` per rule carrying exactly
  a `source:` bullet and a `rule:` bullet.
- **The header line's text is frozen.** The first `> ` line, `(ADR 0021)` included, is a format that
  `check_override.py` requires exactly (`overrides.WRITTEN`); it does not follow the number of the ADR
  that decides it. Changing it would refuse every override an estate has committed. A test pins it byte
  for byte.
- Every `source:` names patches that exist. A rule with no patch behind it is recorded first, with
  `/dgf-fix --record`.
- It is written in English, as AI Factory's are.
- `/dgf-evolve` owns `<paths.skill_context>`. A hand-written override is still read — it is repository
  content — but only after the check in §5 accepts it.

### 4. The limit

The limit is restated with "the gate's status table" replaced by **"the status a gate script
computes"**, which is what ADR 0020 made of it.

For a skill that reads an override:

> An override may add rules and tighten checks. It never relaxes a STOP, an exit-code row, the status a
> gate script computes, a Critical Rule or Artifact Ownership, and never makes this skill install
> anything, skip a script, or write outside its own artifacts. Name the override in your report, and
> quote any rule in it you did not apply because it would relax one of these.

For the skill that writes overrides:

> Every rule you write may only tighten its skill: add a rule or a check. It never relaxes a STOP, an
> exit-code row, the status a gate script computes, a Critical Rule or Artifact Ownership, and never
> makes a skill install anything, skip a script, or write outside its own artifacts. Refuse a prevention
> point that would, and log it with its patch.

A contract test pins both sentences, word for word.

### 5. `check_override.py`

- **What it decides.** `scripts/check_override.py --skill <skill>` checks that skill's override:
  - its shape — the template in §3, a size cap, no fence and no HTML comment, either of which could hide
    text from a reviewer or carry a block;
  - that every source is a patch that exists;
  - that no rule holds a forbidden construct: a gate block, a flag other than `--strict` or `--verbose`,
    a tool grant, an install or download, a history-rewriting git command, or a path outside the root.

  Any of these is exit `1`, and the override is **refused**: the skill does not read it at all, names it
  with each `ERROR` line, and runs on its shipped rules.
- **What it flags for judgement.** A rule naming a word the limit protects — `STOP`, `exit`, `status`,
  `skip`, `unless`, `allow` and the rest of a fixed list — is an `OVERRIDE_TOUCHES_LIMIT` warning, exit
  `2`. The skill reads and applies the override, judges each flagged rule against §4, and quotes any it
  does not apply.
- **What it cannot prove.** The check is lexical. It refuses what a script can see; it cannot see a
  relaxation in plain words. It is a filter, not a proof that a rule tightens. The limit sentence stays
  for what needs judgement, and the override is committed, so review of its diff is the last line.
- **It knows no skill list.** It takes `--skill` and checks that skill's file. Which skills read an
  override is held by the contract test, because a shared script never knows its callers.
- **It needs only an existing root directory**, not a set-up one, because `/dgf` reads its override
  before `config.yaml` exists. It never writes.
- **The readers are ten** — `/dgf`, `/dgf-audit`, `/dgf-commit`, `/dgf-component`, `/dgf-fix`,
  `/dgf-implement`, `/dgf-model`, `/dgf-plan`, `/dgf-process` and `/dgf-verify` — and each runs it before
  reading its override. `/dgf-doctor` reads no estate.

### 6. `/dgf-evolve`

- **It reads no override of its own**: one could steer every override it writes.
- **It targets exactly the readers.** Its SKILL.md lists them, and the contract test holds that list to
  the ten skills that run `check_override.py`.
- It reads each target's **shipped** `SKILL.md`, read-only, to drop rules the skill now covers and refuse
  ones that contradict it. That is the only file of another slice it reads — never its references or
  scripts. It never edits a shipped skill.
- **It asks before it writes, and runs only when asked** (`disable-model-invocation: true`, as
  `aif-evolve`). It rewrites what other skills do, so it never fires on its own.
- It refuses a prevention point that would relax the limit, and logs it with its patch.
- It runs `check_override.py` on every file it writes, and never leaves a refused override behind.
- **The cursor is a set.** `<paths.evolutions>/patch-cursor.json` holds
  `{"processed": [<names>], "updated": …}`, one name per line. A patch is new when it is well-formed and
  not in `processed`. A high-water mark would skip a patch dated before the mark but merged after it,
  and in one shared ledger branches merge in any order.
- Each run writes an evolution log to `<paths.evolutions>`. The config template gains
  `evolutions: .dgf-factory/evolutions/`.

### 7. The gate

`/dgf-fix` joins the `verify` gate's allowlist, and the gate suggests it for a validator finding the
branch introduced, once every task is checked and the change's scope is clean. It stays out of the
doctor's allowlist: a broken plugin install is reinstalled, not fixed in the estate. Both are decided in
[ADR 0022](0022-gate-block-contract-revised.md) §8–§9, which supersedes ADR 0020.

### 8. Out of scope

- There is no `/dgf-transfer`: an estate has one `.dgf-factory/`, and no sibling project to port from.
- Harvesting patches into the shipped `knowledge/`, or turning them into validators, is maintainer
  work: knowledge changes only by a deliberate edit with its provenance.

## Alternatives considered

- **`FIX_PLAN.md`, as AI Factory has it.** Put to the user and rejected: the verify gate fails a change
  with no plan, so a fix plan beside the branch plan would be a second scope the gate never reads.
- **Planless fixes.** Put to the user and rejected for the same reason: a change with no plan cannot pass
  the gate.
- **A prompt-only limit.** Put to the user and rejected: anyone who commits to the estate can write an
  override, and a sentence in the reader is the only thing between that file and the skill.
- **A writer-side script only.** Put to the user and rejected: a hand-written override never passes
  through `/dgf-evolve`, so only a check on the reading side catches it.
- **A reader list inside `check_override.py`.** Rejected: a shared script never knows its callers
  (`.ai-factory/ARCHITECTURE.md` §Dependency Rules). The contract test holds the list.
- **AI Factory's high-water-mark cursor.** Rejected: in one ledger shared by many branches, a patch dated
  before the mark can be merged after it, and would never be read.
- **Overrides that win outright**, as in AI Factory. Rejected: that is the spine's finding M2 — an
  override could relax the gate.
- **`/dgf-evolve` reading its own override.** Rejected: one file could steer every override it writes.
- **`/dgf-evolve` editing shipped skills**, as `aif-evolve` edits custom ones. Rejected: the plugin is
  installed read-only, and ADR 0001 keeps its skills its own.
- **A lexical check presented as a proof of tightening.** Rejected: a script cannot tell "run the check
  before STOP" from "do not STOP". The check is stated as a filter, and judgement and review do the rest.
- **The four new skills read no override.** Rejected: a skill that reads no override cannot learn from a
  patch, and these four are where DGF gotchas bite.
- **The header renumbered to `(ADR 0024)`.** Rejected: the header is an exact-match format, and every
  override an estate has committed would be refused until rewritten.

## Consequences

### Positive

- A hand-written override that grants a tool, narrows the gate or smuggles a gate block is never read.
- Every rule in an override traces to a patch, and every patch to the fix, the plan and the finding it
  records.
- The verify gate names the command that fixes a finding once the tasks are done.
- A gotcha no validator catches is recorded with `findings: none`, which marks it as a candidate for a
  new validator.
- The skills that author components, processes and the model learn from the estate's patches, as the
  spine does.

### Negative

- **The check is lexical.** A relaxation in plain words passes it, to the reader's judgement and the
  reviewer's diff.
- **A refused override leaves its skill on its shipped rules**, including every good rule in the same
  file. A false refusal is fixed by narrowing one named pattern.
- Every reader now runs a script before it reads its override, and an exit `3` STOPs it. **Ten skills
  pay that call**, where six did.
- The cursor can conflict when two branches evolve. One name per line keeps it a line-merge, and an
  unreadable cursor rescans every patch, which costs time, not wrong rules.
- A fix needs a plan first, even for a one-line correction.
- **A consumer that counted six readers meets ten**, and `/dgf-evolve` with no argument now evolves ten
  targets.
- **ADR 0021's live citations moved to this ADR**, while the override header still reads `(ADR 0021)`. A
  reader may take the header for a stale citation; §3 and the comment above `overrides.WRITTEN` say why
  it stays.

### Follow-ups

- Harvest patches into `knowledge/`, and turn `findings: none` patches into validators (maintainer
  work).
- `/dgf-transfer`, if estates ever share rules across roots.
- `/dgf-commit` could place a patch in its fix's Commit Plan group; today it asks, because a patch maps
  to no group.
- `/dgf-implement` could read patches through `check_patches.py`, and skip malformed ones.

## Errata

- **2026-09-27** — Context said "The first seventeen points are ADR 0021's … The last two were read on
  2026-09-27". ADR 0021's Context has twelve top-level points, and this one adds three — the readers as
  milestone 11 built them, the four new skills, and the override header — so it now says twelve and three.
  Source: the top-level bullets of both Contexts; found by `/aif-verify`.
- **2026-09-27** — Context said "The five override known-bad fixtures carry it". Six do: `override-forbidden`,
  `override-invisible-character`, `override-quoted-free-text`, `override-shape`, `override-source-missing`
  and `override-unreadable`, whose ISO-8859 `SKILL.md` a text grep skips as binary. It now says six.
  Source: `grep -la "ADR 0021"` over `tests/fixtures/known-bad/override-*`; found by `/aif-verify`.
- **2026-09-28** — The status paragraph said "Every section is ADR 0021's, unchanged, except three" (§3,
  §5, §6). More sections differ in text: Context dates its points, puts two sentences in the past tense
  and adds three points; the Decision's opening line adds "Ten skills read an override"; Alternatives
  adds two entries; Consequences adds one Positive point and two Negative ones, and extends a third.
  What the ADR decides still differs from ADR 0021 only in §3, §5 and §6, and the paragraph now says
  so. Source: a diff of the two ADRs' Context-to-Consequences text; found by the seventh `/aif-verify`.
