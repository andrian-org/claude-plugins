---
name: dgf-docs
description: Generate or refresh the estate's documentation — an inventory page per workspace (processes, states and transitions, workflows, entities and relations, components, forms, role names) and an index, rendered by a script from the configuration itself, plus a short overview in prose — or check whether the docs are current. Use for "document the estate", "dgf docs", "generate docs", "update the docs", "estate documentation", "are the docs current", "docs check".
argument-hint: "[--check]"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "{{dgf_runtime}}/scripts/estate_docs.py"*) Bash(python3 "{{dgf_runtime}}/scripts/locate_plan.py"*) AskUserQuestion
disable-model-invocation: false
version: 0.1.0
---

# DGF Docs — The Estate's Inventory, and an Overview of It

Two kinds of page, in one folder, `paths.docs` (default `.dgf-factory/docs/`):

- **The inventory pages** — `index.md` and one page per workspace. `estate_docs.py` renders them from the
  configuration under the root, with the readers the validators use: processes with their states and
  transitions, workflows with their steps and `CHANGE_STATE` targets, entities with their datasource, fields and
  relations, components by folder, forms, and the role names in use. Each starts with a generated marker. The
  output is deterministic, so a page changes only when the estate does.
- **`overview.md`** — a short page of prose, written by this skill from the estate's `DESCRIPTION.md` and the
  generated `index.md`, and nothing else.

**The inventory is the script's, never the model's** (ADR 0032 §3): an inventory a prompt writes drifts
unseen. This skill never writes, edits or deletes an inventory page — it runs the script. A page without the
generated marker is never overwritten, by the script or by this skill.

`--check` writes nothing. It tells whether every inventory page matches what the estate renders now, so it
can run in CI.

It ports AI Factory's `/aif-docs`. Its README and docs pages become the estate's inventory, and its
documentation review becomes `--check`.

## Workflow

### Step 0: Context

```bash
python3 "{{dgf_runtime}}/scripts/locate_plan.py" --root-only
```

| Exit | Action |
|---|---|
| `0` | The `ROOT:` line is `<root>`. Continue. |
| `1` | **STOP** with its message: `ROOT_NOT_SET_UP` → run `/dgf` first; `ROOT_AMBIGUOUS` → ask which root, and run again from it. |
| `3` | **STOP** and relay it: the call is wrong. |

Read `<root>/.dgf-factory/config.yaml` for:

- `paths.docs` — `<paths.docs>`; `.dgf-factory/docs/` when the key is absent, as in a config older than this
  skill (ADR 0032 §5);
- `paths.description` — `<paths.description>`; `.dgf-factory/DESCRIPTION.md` when absent;
- `language.ui`, to talk, and `language.artifacts`, to write `overview.md`.

Every path is relative to `<root>`.

### Step 1: Mode

| Argument | Mode |
|---|---|
| (none) | **write** — Steps 2, 3 and 4 |
| `--check` | **check** — Step 2 with `--check`, then Step 4. Nothing is written. |

### Step 2: Render the inventory

Write mode:

```bash
python3 "{{dgf_runtime}}/scripts/estate_docs.py" --workspaces-root "<root>" --out "<paths.docs>"
```

Check mode:

```bash
python3 "{{dgf_runtime}}/scripts/estate_docs.py" --workspaces-root "<root>" --out "<paths.docs>" --check
```

Capture the exit code before anything reads the output: a pipe would report the pipe's own. Each page has a
`PAGE:` line — `wrote`, `unchanged`, `removed` (a generated page for a workspace that no longer exists),
`stale` (check mode) or `kept` (a page the script may not overwrite).

| Exit | Action |
|---|---|
| `0` | Write mode: every page written or already current → Step 3. Check mode: **the docs are current** → Step 4. |
| `1` | `DOCS_PAGE_NOT_GENERATED`: a page named like a generated one exists without the marker, so it is someone's own text, left as it is. **STOP.** Quote each `ERROR` line and its `PAGE: … kept` line. Never edit, move or delete that page yourself: ask the user to move or delete it, then run `/dgf-docs` again. |
| `2` | Write mode: `DOCS_SOURCE_UNREADABLE` — a configuration file does not parse, and its page lists it as not read. Surface each `WARN` line, say `/dgf-audit` reports why the file does not parse, and go on to Step 3. Check mode: `DOCS_STALE` — quote each `WARN` line (a page that is missing, differs from its rendering, or is an orphan) → Step 4. |
| `3` | **STOP** and relay it verbatim: `DEPENDENCY_MISSING` with its install command; `ROOT_NO_WORKSPACE` (no directory under the root has an exact-case `FM/`); `KNOWLEDGE_TABLE` or `SCHEMA_UNSELECTABLE` (the installed runtime's defect — run `/dgf-doctor`, then re-run `dgf-factory setup`); an `--out` refused because `paths.docs` is not a folder of its own under `.dgf-factory/` (correct `paths.docs` with `/dgf`); or a run that stopped, which wrote an incomplete set of pages. |

### Step 3: The overview (write mode only)

`<paths.docs>/overview.md` is this skill's own page. It says, in a few paragraphs, what the estate is and how
to read its inventory — from two sources only:

1. `<root>/<paths.description>` — `/dgf`'s description of the estate: its purpose, its DGF version, its stack.
2. `<root>/<paths.docs>/index.md` — the inventory the script just rendered: the workspaces with their roles and
   counts, the applications, the folders that are not workspaces, and its Limit section.

Read both in full. **No `<paths.description>`** → do not write the overview: say the inventory pages are
written and that `/dgf` writes the description the overview needs, then go to Step 4.

**When `overview.md` already exists**, read it. It is replaced whole. If it holds text that neither source
supports — a hand edit — ask with `AskUserQuestion` whether to replace it or keep it as it is; on keep, or no
answer, leave it untouched and go to Step 4.

Write it in `language.artifacts`, in this shape:

```markdown
# <the estate's name, from the description's title> — overview

> Written by /dgf-docs from <paths.description> and index.md; re-run /dgf-docs to refresh it. The inventory
> pages beside it are generated by estate_docs.py.

## Purpose
<the description's Purpose, restated briefly>

## Workspaces
<each workspace from the index — its role and its main counts — linking its page; the applications and the
base workspace they run with>

## Reading the inventory
<what each page lists, from the index's sections; that references are listed as written; that role names are an
inventory; then the index's LIMIT line, quoted verbatim>

## Stack
<the description's DGF version and Stack table, restated briefly>
```

The rules for every sentence:

- **Traceable to one of the two sources.** Each statement restates something `<paths.description>` or
  `index.md` says. A number is one the index prints; a name is one the index or the description prints.
- **No invented fact.** Nothing about what a process, workflow or entity *does*, who uses it, or why it exists,
  unless the description says so. No DGF fact beyond what the index already states with its citation; to
  explain a term, cite the section of the knowledge base the index cites (for the base workspace,
  `{{dgf_runtime}}/knowledge/process-model.md` §2.1; for role names, `{{dgf_runtime}}/knowledge/permissions.md` §1).
- **The index wins over the description on counts.** The description's workspace table is `/dgf`'s snapshot
  from setup; when its counts differ from the index, use the index's and say the description is older — `/dgf`
  refreshes it.
- **Relative links only**: `index.md`, each workspace's page as the index links it, and the description by its
  path relative to `<paths.docs>`. Never an absolute path, which the description's Workspaces root section may
  hold.
- **Estate names as the index prints them**, its escaping kept, so a name cannot break a link or a heading.
- **The LIMIT line verbatim.** A static inventory cannot see what is chosen at run time
  (`{{dgf_runtime}}/knowledge/reference-graph.md` §3).

Write the file with `Write`, then read it back once and check each sentence against the two sources; remove
any that neither supports.

### Step 4: Report

In `language.ui`:

- Every `PAGE:` line, as a short list: what was written, unchanged, removed, stale or kept.
- Every `ERROR` and `WARN` line verbatim, and the verdict line.
- Write mode: whether `overview.md` was written, kept, or not written for want of a description.
- Check mode: **current** (exit `0`) or **stale** (exit `2`, with the stale pages), and that `/dgf-docs` without
  `--check` regenerates them. `overview.md` is prose: `--check` does not judge it.
- The CI line, once, for an estate that wants its docs held current — after the validators' dependencies are
  installed, since the script exits `3` with `DEPENDENCY_MISSING` without them:

  ```bash
  python3 "{{dgf_runtime}}/scripts/estate_docs.py" --workspaces-root "<root>" --out "<paths.docs>" --check
  ```

  Exit `2` means the docs are stale, `1` that a page without the marker sits where a generated one goes.

Next: `/dgf-audit` for the estate's health — the inventory documents it, and checks nothing.

## Execution Rules

### DO:

- ✅ Run `estate_docs.py` for every inventory page, and capture its exit code before any pipe
- ✅ Quote every `PAGE:`, `ERROR` and `WARN` line, and the verdict
- ✅ Write `overview.md` from `<paths.description>` and `index.md` only, every sentence traceable to one of them
- ✅ Quote the index's LIMIT line verbatim in the overview
- ✅ Write nothing at all in check mode

### DON'T:

- ❌ Write, edit or delete an inventory page — `index.md`, a workspace page, or any page with the generated marker
- ❌ Touch a page the script reports `kept`, or any file in `<paths.docs>` other than `overview.md`
- ❌ Add to the overview a fact neither source states — about the estate or about DGF
- ❌ Write an absolute path into the overview
- ❌ Read a check that exited `3` as current, or a `DOCS_STALE` page as current
- ❌ Emit a `dgf-gate-result` block — the docs are a report, not a gate

## Artifact Ownership

- **Owns:** `<paths.docs>` (default `.dgf-factory/docs/`) — the inventory pages through `estate_docs.py` only,
  and `overview.md`, written by this skill (ADR 0032 §1).
- **Reads:** `.dgf-factory/config.yaml`, `<paths.description>` (`/dgf`'s), the generated `index.md`, and the
  script's output.
- Never writes the description, the configuration, a plan, or any file outside `<paths.docs>`.

## Critical Rules

1. **The inventory is the script's.** Every inventory page comes from `estate_docs.py`; none is written by hand.
2. **A page without the marker is someone's own.** Never overwritten — exit `1` stops this skill.
3. **The overview invents nothing.** Every sentence is traceable to the description or the index.
4. **Check mode writes nothing.** It reports current or stale.
5. **`{{dgf_runtime}}` always** for dgf-factory's own scripts and knowledge.
