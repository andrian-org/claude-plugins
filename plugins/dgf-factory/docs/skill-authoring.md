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
allowed-tools: Read Write Glob Grep Bash(python3 *) AskUserQuestion
disable-model-invocation: false
version: 1.0.0
---
```

| Field | Rule |
|-------|------|
| `name` | Matches the directory name. kebab-case. |
| `description` | **Carries the trigger phrases.** It is the only thing deciding whether the skill fires — write it for matching, not for elegance. Include the literal phrases a user would type. |
| `argument-hint` | Present whenever the skill takes arguments |
| `allowed-tools` | An allowlist, not a formality. Narrow `Bash` to command prefixes — `Bash(git *)`, `Bash(python3 *)` — rather than granting bare `Bash`. |
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

`route_means.py` answers a question rather than checking files, so it prints a single
`ROUTE: json|xml <where> — <reason>` line in place of 2–4.

Each finding code has one fixed severity, and the exit code is the worst across all files,
with `3` beating everything. A skill quotes `ERROR` lines verbatim, surfaces every `WARN`, and
keeps `NOT RUN` visible. When `lxml` or `jsonschema` is missing, every validator that needs
them exits `3` with the install command. That is a setup problem to report, never a pass. The check ids
(`xsd-structure`, `dead-transition`, `json-schema`, `runtime-parity`, …) are stable, so a
gate block can carry them.

## Gate blocks

Quality skills keep their human-readable Markdown report, then append exactly one fenced
block as the last thing in the output:

````markdown
```dgf-gate-result
{
  "schema_version": 1,
  "gate": "verify",
  "status": "fail",
  "blocking": true,
  "blockers": [
    { "id": "verify-task-1", "severity": "error", "file": "src/example.cs",
      "summary": "Required behavior is missing." }
  ],
  "affected_files": ["src/example.cs"],
  "affected_components": [],
  "suggested_next": { "command": "/dgf-fix", "reason": "Blocking gaps remain." }
}
```
````

Rules:

- `schema_version: 1`, kept compatible with the AI Factory `aif-gate-result` contract
- **Last block wins.** Callers parse only the final such block, never the prose above it
- `status` is one of `pass` | `warn` | `fail`
- `suggested_next.command` comes from a fixed allowlist, not free text

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
