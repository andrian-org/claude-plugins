---
id: 0016
title: Legacy XSDs other than process lag the runtime; their failures warn until each has a divergence list
status: accepted
date: 2026-09-24
deciders: [Andrian Mamei]
supersedes: []
tags: [validation, xsd, legacy-xml, gates]
---

# 0016 — Legacy XSDs other than process lag the runtime; their failures warn until each has a divergence list

[ADR 0014](0014-process-verification-runtime-resolution.md) §1 decides how a **process** XSD
failure is judged: a failure on a construct the runtime deserializer binds is a warning, and any
other failure blocks. That needs a divergence list derived from the runtime model, and milestone 8
writes one for `process.xsd` only. The other legacy grammars — workflow, form, settings, the three
view grammars and options — are validated by the same validators, and this ADR decides what their
failures mean until each has its own list.

## Context

Read on **2026-09-24**. DGF paths are relative to the DGF repository root at `aa1d5c4c2`.
Validated with `lxml` 6.1.3 and its bundled libxml2 2.14.6
([ADR 0015](0015-validator-runtime-and-json-reader.md) §2), against the XSDs vendored under
`knowledge/schemas/xsd/`, over every matching file in `src/samples/workspaces/`. Every file parsed.

| grammar | files | fail | rate | errors |
|---|---|---|---|---|
| `workflow.xsd` — `_workflow.xml` | 341 | **211** | 62% | 675 |
| `grid-form.xsd` — `_DATA/<t>/_gridforms/<g>/_grid.xml` | 177 | 96 | 54% | 131 |
| `table-view.xsd` — `_DATA/<t>/_views/<v>/_view.xml` | 559 | 242 | 43% | 540 |
| `lookup-view.xsd` — `_DATA/<t>/_lookupviews/<v>/_view.xml` | 333 | 44 | 13% | 67 |
| `process.xsd` — `_PROCESS/<p>/process.xml` | 23 | 2 | 9% | 5 |
| `options.xsd` — `_DATA/<t>/_options.xml` | 85 | 5 | 6% | 14 |
| `form.xsd` — `_DATA/<t>/_forms/<f>/_form.xml` | 785 | 46 | 6% | 118 |
| `settings.xsd` — `_DATA/<t>/settings.xml` | 429 | 3 | 0.7% | 6 |

**The workflow grammar is far behind the runtime.** Its most frequent errors are `Field/@source`
not allowed (169), `Next` not expected (108), `Field/@text` not allowed (80),
`Invoke/@controlInfo` not allowed (41), `Case/@source` not allowed (32) and `XmlIsland/@control`
not allowed (31). `workflow.xsd` does not declare `StateProcess` or `ForeachRecord` at all, yet
the samples hold 40 `StateProcess` steps, and the engine runs them
(`src/Core/DGF.DataViewer/Workflow/SequenceWorkflow.cs` L510-560).

**DGF itself treats the form failures as a baseline, not as defects.**
`src/Tools/dgf-mcp/Schemas/XSD/verify-xsd-coverage.sh` check 11b validates the 785 sample forms
and compares the failures with `src/Tools/dgf-mcp/Schemas/XSD/xsd-sample-baseline.txt`. That file
lists exactly the same **46** forms, says "a file leaving this list is progress; a file joining it
is a regression", and excuses whatever is on it. No equivalent exists for the other grammars.

**A per-grammar divergence list is real work.** The process list comes from five model classes
and the classes they reference. The workflow model is a step hierarchy with dozens of step types,
and the view, grid and form models are larger still. Each list is derived from
`XmlSerializer` bindings, never from what the samples use (ADR 0014 §1), so each costs a full read
of its model.

## Decision

**For every legacy grammar except `process.xsd`, an XSD failure is a warning (exit `2`), reported
as `XSD_LAGS_RUNTIME` with the grammar's own message. The check still runs and is recorded in
`checks_run` as `xsd-structure`, and the report says the result is advisory. A grammar moves to
ADR 0014 §1's blocking-with-allowance rule when its divergence list exists.**

- The grammars covered are workflow, form, settings, table-view, lookup-view, grid-form and
  options. `profile.xsd` does not compile and is not validated at all (ADR 0015 §9).
- A document that is not well-formed XML is still an error: the runtime cannot read it either.
  So is an unknown component type in a `_form.xml`, which is checked against `form.xsd`'s
  component-type enumeration separately from the grammar as a whole.
- A warning names the file, the line and the grammar's message, so a real defect among the lag is
  still visible to the reader.
- The rule is per grammar, not per error. Until a grammar's divergence list exists, the validator
  cannot tell a lag from a defect in that grammar, so it does not pretend to.

## Alternatives considered

- **Block on every XSD failure.** Rejected: it fails 211 of DGF's own 341 workflows and 242 of its
  559 table views, every one of which the runtime loads. A gate that fails most of the estate is
  bypassed, and then it protects nothing.
- **Write a divergence list for every grammar now.** Rejected for this milestone: the workflow,
  view, grid and form models are each larger than the process model, and none of the lists could
  be verified in the time the process list takes. Kept as the follow-up, in order of failure rate.
- **Adopt DGF's baseline approach** — record today's failing files and block only new ones.
  Rejected. It excuses whatever the samples happen to contain, which ADR 0014 §1 rejects for
  process, and it says nothing about a developer's own files, which are not in any baseline.
- **Skip XSD validation for these grammars.** Rejected: a warning with a line number still finds
  typos and misplaced elements, and `checks_run` would otherwise have to say the check never ran.

## Consequences

### Positive

- **The validators run over the whole legacy estate without blocking what the runtime reads.**
- **A lagging grammar is visible as lag.** Each warning says the grammar is behind the runtime,
  rather than implying the file is wrong.
- **The upgrade path is mechanical.** A grammar moves to the process rule when its list lands; no
  new decision is needed.

### Negative

- **A real structural defect in a workflow, form, view or settings file does not block.** It is
  one warning among many, and in workflow the lag is 675 errors across the samples. Common
  warnings get ignored.
- **The validator is weaker than it looks for these grammars.** `checks_run` says `xsd-structure`
  ran, and it did, but its result decides nothing.
- **Each divergence list is its own maintenance burden** once it exists, as the process list is.

### Follow-ups

- **A divergence list per grammar**, ordered by failure rate: workflow first, then grid-form,
  table-view and lookup-view; form, options and settings last. Each moves its grammar to the
  process rule, and each needs its own known-good expectations.
- **Report upstream to DGF:** `workflow.xsd` lacks `StateProcess`, `ForeachRecord`, `Field/@source`,
  `Field/@text`, `Next` in more positions and more; and the view and grid grammars lag their
  models.
- **Revisit this ADR** if DGF regenerates the legacy XSDs from the runtime model, as it does the
  JSON schemas: then the lag, and this ADR, may disappear.
