---
name: dgf-qa
description: Write the manual test plan for a planned DGF change — one scenario per process the change reaches in each application, with the states to walk, the changed artefact to exercise, the roles to sign in as and the database work it needs, plus automated tests only for its script or style tasks. Writes only the plan's test-plan.md. Use for "test plan", "dgf qa", "what should I test", "QA this change", "write test scenarios", "how do I test this".
argument-hint: "[@<plan path>]"
allowed-tools: Read Write Glob Grep Bash(python3 "{{dgf_runtime}}/scripts/audit_root.py"*) Bash(python3 "{{dgf_runtime}}/scripts/check_plan.py"*) Bash(python3 "{{dgf_runtime}}/scripts/locate_plan.py"*) AskUserQuestion
disable-model-invocation: false
version: 0.1.0
---

# DGF QA — The Change's Test Plan

Answer one question: **what must a tester walk through to know this change works?** A DGF process cannot
run headlessly (ADR 0014 §5), so the answer is mostly manual: one scenario for every process the change
reaches, in every application that reaches it. The reach comes from `audit_root.py`, resolved the engine's
way per application; this skill turns each reached process into a scenario a tester can follow.

Automated tests are named only for a `kind: code` task — a form's `_form.js`, or a script or style file —
the one part of a change such a test can reach, in the estate's own test stack (ADR 0032 §6).

The skill writes **one file**: `<paths.qa>/<plan stem>/test-plan.md`, in the shape
`{{dgf_runtime}}/skills/dgf-qa/references/TEST-PLAN-FORMAT.md` gives. It changes nothing in a workspace,
writes no test code into the estate and no SQL, and emits no gate block.

It ports AI Factory's `/aif-qa`. Its change summary becomes the reach; its framework-agnostic test cases
become process walks.

## Workflow

### Step 0: Context

```bash
python3 "{{dgf_runtime}}/scripts/locate_plan.py" --root-only
```

| Exit | Action |
|---|---|
| `0` | The `ROOT:` line is `<root>`. Continue. |
| `1` | **STOP** with its message: `ROOT_NOT_SET_UP` → run `/dgf`; `ROOT_AMBIGUOUS` → name the root. |
| `3` | **STOP** and relay it: the call is wrong. |

Read `<root>/.dgf-factory/config.yaml` for `paths.plans`, `paths.plan`, `paths.description`, `paths.qa`
(default `.dgf-factory/qa/` when the key is absent), `git.enabled`, `git.base_branch`, `language.ui` and
`language.artifacts`. Read `{{dgf_runtime}}/skills/dgf-qa/references/TEST-PLAN-FORMAT.md` in full.

### Step 1: The plan

A plan given as `@<path>` is the plan. Otherwise:

```bash
python3 "{{dgf_runtime}}/scripts/locate_plan.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"
```

| Exit | Action |
|---|---|
| `0` | The `PLAN:` line is `<plan>`. |
| `1` | **STOP** with its message: `PLAN_NOT_FOUND` → a test plan belongs to a planned change; run `/dgf-plan`, or `/dgf-audit --reach <file>` for the blast radius alone. `PLAN_AMBIGUOUS` → ask with `AskUserQuestion` which plan; with no answer, **STOP**. |
| `2` | `PLAN_FALLBACK`: say which plan it chose and why, and ask before using it. Not confirmed → **STOP**. |
| `3` | **STOP** and relay it. |

The **plan stem** is the plan's name, by the table in the format file: `<stem>.md` and `<stem>/index.md`
are `<stem>`; the fast plan is its file name without `.md`.

### Step 2: The tasks

```bash
python3 "{{dgf_runtime}}/scripts/check_plan.py" "<plan>" --workspaces-root "<root>"
```

| Exit | Action |
|---|---|
| `0` | Continue. |
| `2` | Continue, and name every `WARN` line in the report. |
| `1` | **STOP** with the `ERROR` lines verbatim: a plan the check refuses has no task list to test. `/dgf-plan` fixes it. |
| `3` | **STOP** and relay it. |

Keep each `TASK:` line — its number, `kind=`, `files=` and `deletes=` — and read the plan's task text: it
says what each changed artefact should now do, which is what each scenario expects.

### Step 3: The reach

With `git.enabled` true — every file the change touched against the merge-base:

```bash
python3 "{{dgf_runtime}}/scripts/audit_root.py" --workspaces-root "<root>" --base "<git.base_branch>"
```

Without git — the plan's configuration files: every `files=` path of a `kind=config` task that exists on
disk, root-relative, in one call:

```bash
python3 "{{dgf_runtime}}/scripts/audit_root.py" --workspaces-root "<root>" --reach <file>
```

A file a task deletes cannot be reached without git: name it under "Not reached". Capture the exit code
before anything reads the output: a pipe would report the pipe's own.

| Exit | Action |
|---|---|
| `0` | Continue. |
| `1` | A validator `ERROR` in the root. Continue, and say in the report that the estate has errors `/dgf-verify` will name; a scenario over a file with an error may fail for that reason. |
| `2` | Warnings: `AUDIT_REFERENCE_UNRESOLVED`, `CASE_ONLY_MATCH`. Continue, and carry each into "Not reached" or the scenario it touches. |
| `3` | **STOP** and relay it: `AUDIT_REACH_NOT_ARTIFACT` (a `--reach` path that is not a configuration file — drop it, name it under "Not reached", and re-run), `DEPENDENCY_MISSING` with its install command verbatim (never run `pip`), `SCHEMA_UNSELECTABLE` (the installed runtime's defect: run `/dgf-doctor`, then `dgf-factory setup`), `AUDIT_CHECK_FAILED`, a branch with no merge-base, or a usage error. |

Read the reach per file and per application:

- `REACH: <path> artifact= name=` — a changed artefact.
- `APP: <app> processes=<n>`, then one `PROCESS: <app> <reference> via <file>:<line> > … > <path>` per
  process — each one is a scenario.
- `REFERRER:` — a direct referrer, one level deep: the scenario's "Also check".
- `NONE:`, `NOT AUDITED:`, `SKIP:` and each `AUDIT_REFERENCE_DYNAMIC` line — "Not reached", verbatim. A
  `NONE:` line means no *traced* reference reaches the file, never that nothing does.
- Every `LIMIT:` line — copied verbatim into the test plan and the report.

### Step 4: The scenarios

For each `PROCESS:` line, one scenario, by the format file's rules:

1. **States to walk.** Read the first hop's `process.xml` — the `<file>:<line>` after `via`. Name the state
   the instance starts in, the transitions that lead to the state or transition holding that line, and the
   way on to `End`, the reserved name (`{{dgf_runtime}}/knowledge/process-model.md` §3). A step you cannot
   read from the file is written as a question, never guessed.
2. **The changed artefact to exercise** at that step — the form, field, button, grid or workflow step the
   plan's task changed — and what the task says should now happen.
3. **The roles to sign in as.** The role names the process names — `Task/@role`, a MultiTask
   `TaskGroup/@role` — and the `roles` of the sitemap node that opens it, when one does
   (`{{dgf_runtime}}/knowledge/permissions.md` §2). Quote each exactly as the file spells it, with its file
   and line: `roles` is split on `,` with no trimming, so `" B"` is not `"B"` (§2.1 there). Nothing in the
   root declares a role (§1 there): when no name is found, say "no role is named for this process in the
   root" — never invent one.
4. **The database work.** When a task changes an entity's fields or relations
   (`FM/_DATA/<entity>/settings.xml`), name the column, table, view or junction table the database needs
   before the scenario can pass; it lives in the consumer's database project, outside the root
   (`{{dgf_runtime}}/knowledge/data-model.md` §5). **Never write SQL.**

### Step 5: The automated tests

Only for a `kind=code` task. The test stack is the "This estate" cell of the Test stack row in
`<paths.description>`'s Stack table when it is filled, else the default: xUnit + FluentAssertions +
Moq/NSubstitute (backend); Jest and Playwright (frontend) — ADR 0028 rule 6. For each code file name the test,
what it asserts and its stack: a unit test for a script function, a browser test for what a style or a form
script changes on the page. A new file under `js/`, `FM/js/` or `css/` is loaded by nothing until a
deployment mounts it (`{{dgf_runtime}}/knowledge/composition-specs.md` §5): say the browser test needs that
mount.

No `kind=code` task → the single line the format file gives. **Never write a test file**: the test plan
names the tests; the estate's own repository holds them.

### Step 6: Write

The target is `<root>/<paths.qa>/<plan stem>/test-plan.md`.

- It does not exist → write it.
- It exists → ask with `AskUserQuestion`: overwrite it with the new test plan, or keep it and **STOP**.
  Overwrite only on a clear yes.

Write it in `language.artifacts`, in the format file's shape, and nothing else: no other file, no folder
outside `<paths.qa>/<plan stem>/`.

### Step 7: Report

In `language.ui`: the file written, the number of scenarios per application, the automated tests named,
the "Not reached" entries, every `LIMIT:` line **verbatim**, and the database work named. Then next:

- Walk the scenarios by hand, signed in as the roles each names.
- `/dgf-verify` for the gate, then `/dgf-commit`.

## Execution Rules

### DO:

- ✅ One scenario per `PROCESS:` line, per application
- ✅ Quote every role name exactly as the file spells it, spaces included
- ✅ Read the states from the process file, and write what you cannot read as a question
- ✅ Name the database work; relay every `LIMIT:` line verbatim
- ✅ Ask before overwriting an existing test plan

### DON'T:

- ❌ Write any file other than `<paths.qa>/<plan stem>/test-plan.md`
- ❌ Write SQL, a test file, or any change to a workspace
- ❌ Name an automated test for a configuration task — the scenarios test it
- ❌ Invent a role, a state or an expected result the plan does not give
- ❌ Call a reach complete, or read a `NONE:` line as "nothing reaches it"
- ❌ Emit a `dgf-gate-result` block

## Artifact Ownership

- **Owns:** `<paths.qa>/<plan stem>/test-plan.md` — one per plan. No other skill writes it.
- **Reads:** `.dgf-factory/config.yaml`, the plan, `DESCRIPTION.md`, the reached process files, the
  scripts' output, and its format file.

## Critical Rules

1. **One file.** The test plan, under `<paths.qa>/<plan stem>/`, and nothing else — asked before it is
   overwritten.
2. **Manual first.** A process cannot run headlessly: every reached process is a scenario walked by hand.
3. **Automated tests only for code tasks**, in the estate's test stack, else the default.
4. **Exact role names**, never corrected; **database work named**, never written.
5. **A reach is never complete.** Every `LIMIT:` line is relayed verbatim.
6. **`{{dgf_runtime}}` always** for dgf-factory's own scripts, knowledge and references.
