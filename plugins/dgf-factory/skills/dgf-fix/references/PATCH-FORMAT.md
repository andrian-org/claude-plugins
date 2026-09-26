# Patch Format

A patch records one fix: what went wrong, why DGF behaved that way, what changed, and how the next
run avoids it. `/dgf-fix` writes one after every fix, and `--record` writes one without a fix.
`/dgf-implement` reads the latest ten as cautions; `/dgf-evolve` distils them into skill-context
rules. `check_patches.py` checks every rule below (ADR 0021 §1).

A patch is **append-only**. Once written, it is never edited or deleted — a later fix writes a
later patch.

## The file

`<paths.patches>/<YYYY-MM-DD-HH.mm>-<slug>.md` — by default under `.dgf-factory/patches/`.

- The timestamp sorts the patches by time, so "the last ten by name" are the latest ten.
- The slug keeps two fixes made in the same minute, on two branches of one shared ledger, from
  colliding when they merge: a few lowercase words from the title, joined by single hyphens, at
  most 50 characters.
- UTF-8, LF line endings, a regular file of at most 65536 bytes; a leading byte-order mark is fine.

## The template

```markdown
# <title — one line, at most 120 characters>

- date: <YYYY-MM-DD HH:mm>
- plan: <the plan's root-relative path, or none>
- workspaces: <ws>, <ws> — or none
- files: <ws>/<path>, <ws>/<path> — or none
- findings: <CODE>, <CODE> — or none
- dgf_version: <X.Y.Z, or unknown>
- severity: <low | medium | high | critical>

## Problem
<what was seen>

## Root Cause
<why DGF behaved that way>

## Solution
<what changed>

## Prevention
<how the next plan, implementation or check avoids it>

## Tags
#<tag> #<tag>
```

The keys and the headings are English, always: scripts read them. The title and the prose are
written in the estate's `language.artifacts`.

## The fields

Each key appears once, in any order, as a `- <key>: <value>` bullet between the title and the first
section.

| Key | Value | Rule |
|---|---|---|
| `date` | `YYYY-MM-DD HH:mm` | a real date and time, equal to the name's timestamp |
| `plan` | the plan's path, or `none` | a plain root-relative path under `.dgf-factory/`; it need not still exist, because plans are archived |
| `workspaces` | comma-separated names, or `none` | each one plain name — never `applibs*`, never `.dgf-factory` |
| `files` | comma-separated paths, or `none` | each a plain root-relative path in a listed workspace; `none` whenever `workspaces` is |
| `findings` | comma-separated codes, or `none` | each a finding code a script emits — the codes Step 2 reproduced; `none` when no validator reports the problem |
| `dgf_version` | `X.Y.Z`, or `unknown` | the config's `dgf.version` |
| `severity` | `low`, `medium`, `high` or `critical` | how bad the problem would have been in production |

A plain root-relative path uses `/`, is not absolute, names no drive, and has no empty, `.` or `..`
segment.

## The sections

Exactly these five, in this order, each with text. A `## ` line inside a fence is text, not a
heading.

- **Problem** — what was seen: the finding, the symptom, the gate's blocker. One or two sentences.
- **Root Cause** — **the most valuable section.** What about DGF surprised you: the rule the
  runtime follows that the configuration broke. "The runtime resolves a transition's `state` by
  exact name" teaches the next run; "I fixed the typo" does not.
- **Solution** — what changed, in which file. Short: the diff holds the detail.
- **Prevention** — how the next run avoids it: what a plan should list, what an implementation
  should check, which script shows it earlier. This is what `/dgf-evolve` turns into a rule, so
  make it specific and checkable.
- **Tags** — words for grouping: each `#` then lowercase letters, digits and hyphens, separated by
  spaces.

## Worked example

`.dgf-factory/patches/2026-09-26-14.30-review-moves-to-undeclared-state.md`:

```markdown
# `Review` moves to a state the process never declares

- date: 2026-09-26 14:30
- plan: .dgf-factory/plans/feature-zims-fee.md
- workspaces: zims
- files: zims/FM/_PROCESS/Apply/process.xml
- findings: DEAD_TRANSITION
- dgf_version: 1.1.15
- severity: high

## Problem
The gate blocked the branch: `Review` moved to `Archive`, which is neither a declared state nor `End`.

## Root Cause
The state was renamed `Archived` in the process, but the transition kept the old name. The runtime resolves a
transition's `state` by exact name, so the case would stop at `Review`.

## Solution
The transition now names `Archived`.

## Prevention
A task that renames a state lists every file with a transition to it; `validate_process.py` over the process
folder shows a dead transition before the gate does.

## Tags
#process #transition #rename
```

Checked with:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_patches.py" --workspaces-root "<root>" --patches-dir ".dgf-factory/patches/" "<root>/.dgf-factory/patches/2026-09-26-14.30-review-moves-to-undeclared-state.md"
```

```
Patch check
PATCHES: .dgf-factory/patches/ total=1 malformed=0
PATCH: 2026-09-26-14.30-review-moves-to-undeclared-state.md severity=high findings=DEAD_TRANSITION title="`Review` moves to a state the process never declares"
CHECKS RUN: patch-name, patch-fields, patch-sections
…
CLEAN
```

Exit `0`. What each mistake reports, exit `1` (the path shortened to `…`):

| Mistake | Line |
|---|---|
| `severity: urgent` | ``ERROR PATCH_FIELD_INVALID …:9 `severity` is `urgent`: not one of low, medium, high, critical`` |
| the Prevention text deleted | ``ERROR PATCH_SECTION_INVALID …:21 `## Prevention` is empty`` |
| the name `2026-09-26-14.30.md`, with no slug | ``ERROR PATCH_NAME_INVALID … `2026-09-26-14.30.md` is not `<YYYY-MM-DD-HH.mm>-<slug>.md`, with a lowercase slug of letters, digits and single hyphens`` |
| `date: 2026-09-26 14:31` | ``ERROR PATCH_FIELD_INVALID …:3 `date` is `2026-09-26 14:31`: it disagrees with the name's timestamp, 2026-09-26 14:30`` |
| a `- owner: me` bullet after `severity` | ``ERROR PATCH_FIELD_INVALID …:10 `owner` is not a patch field; the fields are date, plan, workspaces, files, findings, dgf_version, severity`` |
| a byte that is not UTF-8 | ``ERROR PATCH_UNREADABLE … not UTF-8 at byte 46`` — nothing more is checked |

`check_patches.py --cursor` adds `state=new`, `processed` or `malformed` to each `PATCH:` line. A
malformed patch is never `new`: `/dgf-evolve` does not read it, nor mark it processed, until a person
repairs it.
