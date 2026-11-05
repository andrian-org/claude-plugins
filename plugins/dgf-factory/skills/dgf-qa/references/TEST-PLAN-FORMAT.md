# Test plan format

The file `/dgf-qa` writes: `<paths.qa>/<plan stem>/test-plan.md`, under the workspaces root. `paths.qa` is
`.dgf-factory/qa/` when the config has no such key. One folder per plan, so a plan's test plan is found by the
plan's own name, with git or without, and for the fast plan too (ADR 0032 §1).

**The plan stem** is the plan's name without its folder and extension:

| Plan | Stem |
|---|---|
| `<paths.plans>/<stem>.md` (a full plan) | `<stem>` |
| `<paths.plans>/<stem>/index.md` (an ultra bundle) | `<stem>` |
| `<paths.plan>` (the fast plan, `PLAN.md` by default) | its file name without `.md`: `PLAN` |

The file is written in `language.artifacts`. Headings, labels and prose are translated; every path, code,
process reference, state name, role name and script line stays exactly as it is in the estate or the script's
output.

## Shape

````markdown
# Test plan — <plan stem>

> Written by /dgf-qa from <plan path> on <YYYY-MM-DD>. A process cannot run headlessly, so every scenario
> below is walked by hand. Re-run /dgf-qa after the change moves; this file is regenerated, not edited.

- Plan: <plan path> — <done>/<total> tasks checked
- Change: <the BASE: line, or "no git — the plan's configuration files, reached with --reach">
- Applications: <each application the reach covered>

## Changed artefacts

| File | Artifact | Change | Task |
|---|---|---|---|
| <root-relative path> | <artifact= from the REACH: line> | <A, M, D, or "planned"> | <task number> |

## Manual scenarios

### S1 — <application> / <process reference>

- **Reached via:** `<the PROCESS: line's chain, verbatim>`
- **Sign in as:** `"<role>"`, … — each name quoted exactly as the file spells it, with the file and line
  that names it; or "no role is named for this process in the root"
- **States to walk:** <state> → <state> → … → <the state whose action, or the transition whose action, runs
  the chain's first hop> → … → `End`
- **Exercise:** <what to do with the changed artefact at that step: the form to open, the field to fill, the
  button to press, the record to create>
- **Expected:** <what the change says should happen, from the plan's task>
- **Database work:** <the column, table, view or junction table the change needs before the scenario can
  pass, named only; or "none">
- **Also check:** <each REFERRER: line for this application, one level deep>

### S2 — …

## Not reached

- `<each NONE: and NOT AUDITED: line, verbatim>` — no traced reference reaches the file here; an entry point
  outside processes still may. Name how a tester reaches it by hand, when the plan says.
- `<each AUDIT_REFERENCE_DYNAMIC line, verbatim>` — the step may load another file at run time.
- `<each SKIP: line, verbatim>` — not a configuration file; no process was walked for it.

## Automated tests

Only for a `kind: code` task: its `_form.js`, or its script or style under `js/`, `FM/js/` or `css/`. A
configuration change has none: it is tested by the scenarios above.

| Task | File under test | Test | Stack |
|---|---|---|---|
| <N> | <root-relative path> | <what the test asserts, one line> | <the estate's test stack, or the default> |

Or the single line: "No `kind: code` task — no automated test applies."

## Limits

- `<each LIMIT: line, verbatim>`
````

## Rules

- **One scenario per reached process, per application.** A `PROCESS:` line is one scenario; the same process
  reached through two chains is one scenario that names both chains. A `webasm` file reached in two
  applications is two scenarios, because each application resolves it its own way.
- **Role names are quoted exactly**, spaces included: a sitemap splits `roles` on `,` with no trimming
  (`{{dgf_runtime}}/knowledge/permissions.md` §2.1). A name is never corrected, merged or normalised. Nothing
  in the root declares a role (§1 there), so a role is a name to sign in as, not a checked one.
- **The states come from the process file**, read from the `PROCESS:` line's first hop. A state the walk
  needs but the file does not name is written as a question, never guessed. `End` is the reserved state, spelled
  exactly (`{{dgf_runtime}}/knowledge/process-model.md` §3).
- **Database work is named, never written.** No SQL in the file
  (`{{dgf_runtime}}/knowledge/data-model.md` §5).
- **The test stack** is the "This estate" cell of the Test stack row in `DESCRIPTION.md`'s Stack table when it
  is filled, else the default: xUnit + FluentAssertions + Moq/NSubstitute (backend); Jest and Playwright
  (frontend) — ADR 0028 rule 6.
- **Every `LIMIT:` line is copied verbatim.** A static reach is never complete
  (`{{dgf_runtime}}/knowledge/reference-graph.md` §3).
- **No result is recorded here.** The file is the plan of what to test; whether a scenario passed is the
  tester's to record elsewhere.
