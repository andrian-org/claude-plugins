---
name: dgf-scaffold
description: Create a new DGF application from scratch in an empty folder — the solution, the API hosts, Docker, the database with its SQL, the workspaces, authentication and the documentation, plus the register, service and page artefacts the request describes. Use for "new DGF application", "scaffold an app", "start a DGF project from scratch", "empty folder", "multi-tenant application", "bootstrap a DGF system".
argument-hint: "<what the application is>"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-scaffold/scripts/*) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__get_component_doc mcp__plugin_dgf-factory_dgf-mcp__get_json_schema_details
disable-model-invocation: false
version: 0.1.0
---

# DGF — Scaffold a New Application

Create one new DotGov Framework application in an **empty folder**: the solution with one or more API
hosts, Docker, the database project with its SQL, the workspaces, the sign-in configuration, the
documentation, and the workspace artefacts the request describes. It then hands the new workspaces root
to the pipeline: `/dgf` sets it up, and every later change is brownfield work for `/dgf-plan` and
`/dgf-implement`.

This skill never adds to an existing application, never overwrites, and writes nothing in a folder that
is not empty. The decision is ADR 0026 §2 and the design is ADR 0027 §7: no bootstrap template exists in DGF, so the application is generated from templates this plugin ships, DGF-generic, with no estate
content.

Two scripts decide everything a script can; you design, ask, and relay:

- `design.py` checks the design file and says what is open: the folder is empty, every name, reference and
  option, the data model and each column's SQL type. It prints one `SCAFFOLD_ASK` per open value and one
  `DEFAULT:` line per value it fills in.
- `generate.py` renders the whole application from the design, checks it, and refuses to run unless
  `design.py` exits 0.

You compute neither a default nor a SQL type, and you never write a generated file yourself. There is no
root and no plan yet, so this skill reads and writes no `.dgf-factory/` and runs no override check.

## Workflow

### Step 0: The folder

The folder is the working directory, unless the request names another, empty folder.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-scaffold/scripts/design.py" --folder "<folder>" --empty-only
```

Capture the exit code before any pipe.

| Exit | Meaning | Action |
|---|---|---|
| `0` | the folder holds nothing but a `.git` folder and possibly `docs/application.json` | Step 1 |
| `1`, `SCAFFOLD_DIR_NOT_EMPTY` | anything else is in it | **STOP.** Say: "this command only creates a new application; use `/dgf-plan` in an existing one." Name what the line lists, and suggest an empty folder |
| `3` | the folder is not a directory | **STOP** and relay it |

### Step 1: Write the design

Read [DESIGN-FORMAT.md](references/DESIGN-FORMAT.md) — every key, its rule and its default.

- If `docs/application.json` exists, this is a **resume**: read it, keep it, and go to Step 2.
- Otherwise, if the request reads as two different applications, ask which one before writing anything.
- Otherwise write `docs/application.json` from the request. Put in **only what the request states**, and
  record each such key under `sources` as `prompt`. Leave everything else out: `design.py` asks for it, and
  prints the rest as defaults. Never guess a version, a path or a sign-in provider to save a question.

What the request usually gives: the application's name; the instances it serves (each directorate, agency
or tenant is one); whether a front office and a back office are separate hosts; how users sign in; the
roles; the registers, services and pages it wants; the entities and their fields. Follow DESIGN-FORMAT.md's
rules for turning each into a key.

Use `get_component_doc` or `get_json_schema_details` only to answer a survey question about what a
component does. They change nothing about what is generated.

### Step 2: Check the design

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-scaffold/scripts/design.py" --folder "<folder>"
```

| Exit | Meaning | Action |
|---|---|---|
| `0` | nothing is open and nothing conflicts | Step 4 |
| `1` | a conflict: each `ERROR` line names the key and the rule | Show each line. Ask the user for a corrected value (Step 3's way), edit the design, and run this step again |
| `2` | `SCAFFOLD_ASK` lines: values are open | Step 3 |
| `3` | `SCAFFOLD_DESIGN_UNREADABLE`: the file cannot be read as a design | **STOP.** Relay the line. Fix the file only if the cause is plainly yours to fix — a missing brace you wrote; otherwise ask |

`DEFAULT:` lines may appear with exit `0` or `2`. Keep them for Step 4.

### Step 3: Survey

Turn every `SCAFFOLD_ASK` line into an `AskUserQuestion`, at most four per call. A line reads
`<key> — <rule> (candidates: …)`: the rule is the question, the candidates are the options, and "Other"
is always there. Ask about the consequence, not the key: "How should the two directorates share their
workspace?" — not "instance_model?".

- Write each answer into the design under its key, and record it under `sources` as `asked`.
- Then run Step 2 again.
- After **five rounds** that still leave a value open, **STOP**. Keep the design, and say that running
  `/dgf-scaffold` again in the same folder resumes it.

### Step 4: Confirm

Nothing has been generated yet. Show the user:

1. **Every `DEFAULT:` line** from the last Step 2 run, verbatim. A default is never silent: these are the
   decisions nobody made.
2. **The tree.**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-scaffold/scripts/generate.py" --folder "<folder>" --dry-run
```

| Exit | Action |
|---|---|
| `0` | show its `TARGET:` lines as a tree, and how many files |
| `3` | **STOP** and relay each code: `SCAFFOLD_DESIGN_INCOMPLETE` (the design changed since Step 2 — run Step 2 again), `SCAFFOLD_TEMPLATE_MISSING` (a defect of the plugin's templates) |
| `1`, `SCAFFOLD_TARGET_EXISTS` | **STOP.** The folder changed since Step 0; nothing was written |

Ask one question: **generate**, **change something**, or **cancel**. "Change something" returns to Step 1 with
the design kept. "Cancel" stops; the design stays in `docs/` for a later run.

### Step 5: Generate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-scaffold/scripts/generate.py" --folder "<folder>"
```

| Exit | Meaning | Action |
|---|---|---|
| `0` | every file is written: one `WROTE:` line each | Step 6 |
| `1`, `SCAFFOLD_TARGET_EXISTS` | the folder changed since the check; nothing was written | **STOP.** Say so |
| `3` | `SCAFFOLD_DESIGN_INCOMPLETE`, `SCAFFOLD_TEMPLATE_MISSING` or `SCAFFOLD_WRITE_FAILED`. After a failed write the folder is as it was | **STOP.** Relay each code and its message. Do not retry by hand |

### Step 6: Check what was generated

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-scaffold/scripts/generate.py" --folder "<folder>" --check
```

| Exit | Meaning | Action |
|---|---|---|
| `0` | the application is sound | Step 7 |
| `1` | the check found the application unsound: its `ERROR` lines are `SCAFFOLD_LITERAL_SECRET`, `SCAFFOLD_VAR_UNDECLARED`, `SCAFFOLD_STRUCTURE_INVALID`, `SCAFFOLD_ROUTE_UNRESOLVED` or `SCAFFOLD_VALIDATION_FAILED`, the last quoting a validator's own line | **STOP.** Say "a generator defect", and quote the lines. Never patch the output by hand: the templates are wrong, and a patched file hides that |
| `3`, `DEPENDENCY_MISSING` | the validators cannot run | Show the install command the line prints. When the user has run it, run this step again |
| `3`, any other | the design or the templates are wrong | **STOP.** Relay it |

### Step 7: Report

In English — no configuration exists yet to set another language. Say:

1. **What was generated**: the number of files, the solution, the hosts and their instances, the workspaces,
   the modules, the entities and the sign-in providers, as `docs/architecture.md` states them.
2. **How to run it**: the steps of `docs/README.md`. The application does not run until its variables are
   filled and four things are supplied that DGF pins no consumer artifact for: the base workspace, the
   framework's database baseline image, the DGF UI image, and a feed serving the `DGF.API` package.
3. **Every variable to fill**: name them from `docs/configuration.md`, and mark the secrets.
4. **What is not generated**, so nobody expects it: custom behaviour, integrations, documents, reports, Helm
   and pipelines. `docs/README.md` lists them as work for `/dgf-plan`.
5. **Next**: run `/dgf <folder>/workspaces` to set the new workspaces root up for the pipeline.

No summary file, no report file.

## Execution Rules

### DO

- Write the design from the request alone, and let `design.py` ask for the rest.
- Ask the survey questions in the user's terms, four at a time.
- Show every `DEFAULT:` line before anything is generated.
- Run every script with `${CLAUDE_PLUGIN_ROOT}`, and relay its lines verbatim.
- Keep `docs/application.json` on a STOP: a re-run in the same folder resumes it.

### DON'T

- Write, edit or delete a generated file, or patch the output of a failed check.
- Enter a value `design.py` has not accepted, or compute a default or a SQL type.
- Write a literal secret, a host, a feed, a registry or an image tag anywhere: each is a `${VAR}`.
- Write a `BASE:` reference: the generated application is self-contained, whatever base is supplied.
- Continue in a folder that is not empty, or add to an existing application.
- Run the pipeline's skills: `/dgf` and `/dgf-plan` are the user's next step.

## Artifact Ownership

- **Writes**: `docs/application.json`, and the application — through `generate.py` only.
- **Never writes**: a plan, anything under `.dgf-factory/`, or anything in a folder that is not empty.
- **Reads**: DESIGN-FORMAT.md, and the scripts' output.

## Critical Rules

1. Never overwrite. Never write into a folder `design.py --empty-only` does not accept.
2. No value enters the design that the user or the request did not give, and no generated file exists that
   `generate.py` did not write.
3. `generate.py` runs only after the user has seen the defaults and the tree, and said generate.
4. A failed check is a defect of the generator. Say so, quote it, and stop.
5. No literal secret and no `BASE:` reference in anything this skill produces.
6. Always `${CLAUDE_PLUGIN_ROOT}`, never a hand-typed plugin path.
