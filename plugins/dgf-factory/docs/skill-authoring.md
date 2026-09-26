[← Architecture](architecture.md) · [Back to README](../README.md) · [DGF Knowledge Sourcing →](dgf-knowledge.md)

# Skill Authoring

Skills are written **prompt-as-program**: numbered steps, explicit gates, mandatory
outputs and "STOP and report" conditions. They are not descriptions of what a skill does.
A mature skill in this family reads like a state machine, not documentation.

## File layout

One directory per skill. The entry file is named exactly `SKILL.md` — auto-discovery
matches that name only, uppercase.

```text
skills/dgf-component/
├── SKILL.md              # the prompt-program
├── references/           # facts only this skill cites
├── scripts/              # validators only this skill calls
└── templates/            # output shapes this skill emits
```

## Frontmatter contract

```yaml
---
name: dgf-component
description: Scaffold, inspect or validate a DGF component against the catalogue. Use for "add component", "check component", "is this component valid".
argument-hint: "[scaffold | inspect | validate] <component-name>"
allowed-tools: Read Write Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion
disable-model-invocation: false
version: 1.0.0
---
```

| Field | Rule |
|-------|------|
| `name` | Matches the directory name. kebab-case. |
| `description` | **Carries the trigger phrases.** It is the only thing deciding whether the skill fires — write it for matching, not for elegance. Include the literal phrases a user would type. |
| `argument-hint` | Present whenever the skill takes arguments |
| `allowed-tools` | What the skill may run **without a prompt** — it pre-approves, it never restricts: a command no rule matches still runs after the user approves it. So list only what the skill runs. `${CLAUDE_PLUGIN_ROOT}` is substituted inside Bash rules, so a skill that runs the plugin's scripts lists `Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*)`, never `Bash(python3 *)`, which also pre-approves `python3 -c …`. A skill that runs no git command lists no git rule. `git -C "<root>" <subcommand>` cannot be narrowed below `Bash(git *)`: a rule with `*` before the subcommand draws a startup warning. `tests/test_skill_contracts.py` holds every skill's script calls to its own rules. |
| `disable-model-invocation` | `false`, so the skill fires on its description — except a skill that rewrites what other skills do (`/dgf-evolve`, which writes their overrides): `true`, so it runs only when the user asks for it. |
| `version` | Semver. Bump when behaviour changes. |

## Body structure

```markdown
# <Title>

## Workflow
### Step 0: Check Current State
### Step 0.1: Load Project Context
### Step 1: …
### Step 2: …

## Execution Rules
### DO:
### DON'T:

## Artifact Ownership

## Critical Rules
```

Write steps so they can be resumed. State lives in files on disk, not in the context
window — a user can `/clear` mid-run and pick up where they left off, but only if each
step reads its state rather than assuming it.

## The exit-code contract

Validators are called from skills, so their exit codes are a public interface:

| Code | Meaning | What the skill does |
|------|---------|---------------------|
| `0` | clean / valid | continue |
| `1` | blocked | **STOP.** Report findings verbatim. Do not repair silently. |
| `2` | warnings | continue, surface every warning to the user |
| `3` | usage error | **STOP.** The invocation is wrong. |

Never reuse a code for a different meaning. Never let a pipe mask one — `cmd | tail`
returns `tail`'s status, so capture the real code before piping.

Scripts define a single `fail(code, message)` exit path rather than scattering exits.
Errors go to stderr, normal output to stdout.

### Reading a validator's output

The validators under `scripts/` print, in this order, so a skill never has to guess what ran:

1. a header line;
2. `FAMILY: json|xsd|unresolved <file>` for each file;
3. `CHECKS RUN: <ids>` — only these were checked;
4. `NOT RUN: <id> (<reason>)`, repeated — never report these as passed;
5. one line per finding: `ERROR|WARN|INFO <CODE> <file>[:<line>] <message>`;
6. a summary, then the verdict: `CLEAN`, `WARNINGS` or `BLOCKED`.

Every finding is exactly one line. Control and line-separator characters in a file name or a
message — text that can come from a workspace or another branch — print escaped (`\x0a`,
` `), so no content can forge a line or a verdict.

`route_means.py` answers a question rather than checking files, so it prints a single
`ROUTE: json|xml <where> — <reason>` line in place of 2–4.

The pipeline spine's scripts read plans and roots rather than configuration files, so they
print their own lines in place of 2. `check_plan.py`, `check_change.py` and `verify_gate.py` then
print the same `CHECKS RUN:` and `NOT RUN:` lines; all five print findings and a verdict:

| Script | Lines in place of `FAMILY:` |
|---|---|
| `locate_plan.py` | `ROOT: <path>`; `PLAN: <path> mode=<m> source=branch\|lone\|fast`, or with `--list` one `PLAN: <path> mode=<m> progress=<done>/<total>` per plan |
| `inventory_root.py` | `ROOT:`; `WORKSPACE: <name> role=base\|application <count>=<n> …`; `NOT A WORKSPACE: <name> (<why>)`; `GIT:`; `KNOWLEDGE: dgf_version=<v>`; `VALIDATORS:` |
| `check_plan.py` | `PLAN: <path> mode= format= branch=`; `AFFECTS: <ws>, …`; one `TASK: <N> [x\| ] kind=<k> depends=… files=… deletes=…` per task; `PROGRESS: <done>/<total>`; with `--overlap`, `OVERLAP SOURCES: <n> refs scanned …` |
| `check_change.py` | `PLAN:`; `BASE: <sha> (<ref>)`; `CHANGED: <n>`; one `CHANGE: <A\|M\|D\|R> <path> class=<class> workspace=<ws>` per changed file |
| `verify_gate.py` | `ROOT:`; `check_plan.py`'s lines; `check_change.py`'s lines after its `PLAN:`; one `CODE TASK: <N> reason="<reason>"` per `kind: code` task. Its summary adds `Shown: 20 of <n> PRE_EXISTING — …` when it cuts them, and `STATUS: pass\|warn\|fail`; then the verdict, a blank line, and the gate block |

`check_change.py` compares the validators' findings with the merge-base
([ADR 0018](adr/0018-change-relative-gates.md)). A finding the branch introduced keeps its own
code and severity. One that was already there prints as `INFO PRE_EXISTING <file> [<CODE>]
<message>`, and one the branch removed as `INFO FIXED <file> [<CODE>] <message>`; neither
affects the exit. Its summary adds `new: <e> error(s), <w> warning(s); pre-existing: <p>;
fixed: <f>`. A skill reports new findings verbatim, counts pre-existing ones, and never fixes
them unasked.

Only a whole-root run records the check `validators` as run. A `check_change.py --files` run —
`/dgf-implement`'s per-task pre-check — prints `NOT RUN: validators (narrowed to <n> file(s) by
--files; …)`, so a narrowed run can never read as a gate pass
([ADR 0004](adr/0004-authoring-entry-point.md) §3, [ADR 0022](adr/0022-gate-block-contract-revised.md) §4).

Each finding code has one fixed severity, and the exit code is the worst across all files,
with `3` beating everything. A skill quotes `ERROR` lines verbatim, surfaces every `WARN`, and
keeps `NOT RUN` visible. When `lxml` or `jsonschema` is missing, every validator that needs
them exits `3` with the install command. That is a setup problem to report, never a pass. The check ids
(`xsd-structure`, `dead-transition`, `json-schema`, `runtime-parity`, …) are stable, so a
gate block can carry them.

## Gate blocks

Quality skills keep their human-readable Markdown report, then end with exactly one fenced
`dgf-gate-result` block. **A script builds it**, through the one builder
`scripts/lib/gate_result.py` ([ADR 0022](adr/0022-gate-block-contract-revised.md)); the skill relays the
script's output verbatim and writes nothing after it. A prompt never writes or edits a block.

````markdown
```dgf-gate-result
{
  "schema_version": 1,
  "gate": "verify",
  "status": "fail",
  "blocking": true,
  "blockers": [
    { "id": "DEAD_TRANSITION", "severity": "error", "file": "zims/FM/_PROCESS/Apply/process.xml",
      "line": 41, "schema_family": "xsd", "summary": "`Review` moves to `Archive`, which is neither a declared state nor `End`" }
  ],
  "warnings": [
    { "id": "not-run-baseline", "severity": "warning", "file": ".dgf-factory/plans/feature-x.md",
      "line": null, "schema_family": null, "summary": "baseline did not run: --changed gives no base tree; every finding counts as new" }
  ],
  "affected_files": [".dgf-factory/plans/feature-x.md", "zims/FM/_PROCESS/Apply/process.xml"],
  "checks_run": ["plan-header", "plan-tasks", "…", "validators", "xsd-structure"],
  "schema_family": { "json": 212, "xsd": 364 },
  "affected_components": [],
  "affected_processes": [ { "workspace": "zims", "name": "Apply", "reference": "Apply" } ],
  "suggested_next": { "command": "/dgf-implement", "reason": "1 new blocking finding(s)" }
}
```
````

Rules:

- `schema_version: 1`, kept compatible with the AI Factory `aif-gate-result` contract.
- **The status is computed, from two lists.** `blockers` holds only what blocks; `warnings` holds
  every non-blocking warning and every required check that did not run, as `not-run-<check>`.
  `status` is `fail` with any blocker, else `warn` with any warning, else `pass`, and `blocking`
  is `true` exactly on `fail`. The builder takes no status; it refuses a contradictory block.
- An entry is `{id, severity, file, line, schema_family, summary}`, its summary cut to 240
  characters. `affected_files` is every file an entry names, plus the plan for `verify`.
- **Never claim a check that did not run.** `checks_run` lists what ran; each gate's required
  checks are in `checks_run` or have a `not-run-<check>` entry, never both.
- **Absent means not computed; `[]` means none.** A field the gate did not compute is left out:
  the doctor reads no estate, so its block has no `schema_family`, `affected_components` or
  `affected_processes`.
- **Each gate has its own allowlist.** `verify`: `/dgf-plan`, `/dgf-implement`, `/dgf-commit`
  or `null`. `doctor`: `null` only — a broken install is fixed by hand. `/dgf-fix` joins them when
  it is built.
- **The doctor's block** is gate `doctor`: errors in `blockers`, warnings and each section that
  could not run (`not-run-<section>`) in `warnings`, and `checks_run` naming its six sections.
- **Last block wins.** Callers parse only the final such block, never the prose above it. **A
  missing block is a gate that did not run** — a script prints none for a usage error, or when its
  builder cannot load.

The verify gate's full contract — the entry table, the required checks, the `suggested_next`
order — is `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`.

## Determinism before prompting

If a JSON Schema, an XSD, or a script can decide a question, write the script. A
statically checkable rule encoded as a prompt instruction is a defect — the model can
forget it, a script cannot.

| Leave to a script | Leave to the model |
|---|---|
| Does every referenced component exist? | Is this the right component for the job? |
| Does the spec validate against the schema for its family? | Is this decomposition sensible? |
| Are all bindings complete? | Does this match the user's intent? |

DGF configurations come in two families — modern JSON and legacy XML — so a script that
handles only one silently passes everything in the other. And a passing validation in a
family the runtime does not parse is not a success: `Workflow` and `ProcessFlow` validate
against JSON schemas the runtime ignores. Resolve the family, then check parity. See
[DGF Schemas](dgf-schemas.md).

This is the highest-leverage deviation from AI Factory, which has almost no deterministic
validators.

## The executor never re-decides

When a plan bundle conflicts with the current code, the executing skill **stops and
reports the drift**. It does not silently make the architectural choice that the planning
stage existed to pre-commit. Expensive thinking happens once; cheap execution happens
many times.

## Before you ship a skill

- [ ] `description` contains the phrases a user would actually type
- [ ] `allowed-tools` is narrowed to what the skill really needs
- [ ] A skill-context override is read with the shared limit sentence: it may only tighten
- [ ] Every DGF fact is cited from `knowledge/`, not inlined in the prompt
- [ ] Every statically checkable rule is a script, not an instruction
- [ ] Exit codes follow the table above
- [ ] Artifact ownership is stated, and nothing writes another skill's artifact
- [ ] Paths use `${CLAUDE_PLUGIN_ROOT}`, never absolute or `~/` paths
- [ ] LF line endings

## See Also

- [DGF Knowledge Sourcing](dgf-knowledge.md) — where the facts a skill cites must come from
- [DGF Schemas](dgf-schemas.md) — the two schema families a skill must handle, and how to detect them
- [Architecture](architecture.md) — where a new skill's files belong and what it may read
- [Architecture Blueprint](blueprint.md) — Part 1 §"The five architectural ideas that actually matter"
