---
name: dgf-sync
description: Maintainer skill for the dgf-factory repository — bring a DGF knowledge pack up to a DotGov Framework release, add a pack for a new DGF release line, or report which lines moved. Use for "sync with DGF", "update to the latest DGF", "a new DGF release", "DGF 1.4 is out", "check DGF drift", "refresh the knowledge packs", "dgf sync".
argument-hint: "status | sync <X.Y> [--to <X.Y.Z>] | new-line <X.Y> | add-line <X.Y> --from <X.Y> | --all"
allowed-tools: Read Edit Write Grep Glob Bash(python3 tools/dgf_lines.py *) Bash(python3 tools/check_drift.py *) Bash(python3 tools/vendor_schemas.py *) Bash(python3 tools/restamp_knowledge.py *) Bash(python3 tools/check_knowledge_stamps.py *) Bash(python3 tools/run_known_good.py *) Bash(python3 tools/derive_sql_types.py *) Bash(python3 skills/dgf-doctor/scripts/doctor.py *) Bash(python3 -m unittest *) Bash(bash tools/check-dual-schema-docs.sh)
disable-model-invocation: false
version: 1.0.0
---

# DGF Sync — keep the knowledge packs at DGF's releases

A **maintainer** skill of the dgf-factory repository. It is not shipped: it lives in `.claude/skills/`,
never in `skills/`. It runs from the plugin root, `plugins/dgf-factory/`.

dgf-factory ships one **knowledge pack** per DGF release line (ADR 0036): the current line in `knowledge/`,
each older line in `packs/<X.Y>/`, all named in `packs/lines.json`. Each pack is read at an exact release
tag, and every fact it states is cited in a ledger under `provenance/`. This skill moves a pack to a newer
tag, or adds a pack for a new line.

**Scripts detect; you judge, and every judgement is logged.**

- **What the scripts decide.** Which sources drifted, which tag is newer, what the vendored schemas are, every
  digest and every stamp. You never compute or hand-edit any of these.
- **What you decide.** Whether a changed source changes a fact.
- **Where the decision goes.** Every one is written, per source, in the sync log.

Read `references/TRIAGE.md` before Step 4 and `references/SYNC-LOG-FORMAT.md` before Step 8.

## Inputs

| Argument | Meaning |
|---|---|
| `status` (or none) | Step 1 only: report, change nothing |
| `sync <X.Y> [--to <X.Y.Z>]` | bring line `X.Y`'s pack to `X.Y.Z` (default: the line's newest release tag) |
| `new-line <X.Y>` | a release line **newer** than the current one: freeze the current pack into `packs/`, then sync `knowledge/` to the new line's newest tag |
| `add-line <X.Y> --from <A.B>` | an **older or side** line: fork pack `A.B` into `packs/X.Y/`, then sync it |
| `--all` | every line `status` reports with `TAG_AVAILABLE` or `DRIFT`, then every `NEW_LINE`, one at a time, in the order status lists them |

`<dgf-root>` is the DGF repository checkout. Ask for it once with `AskUserQuestion` unless the user named it.
It is never edited: every line is read from its own cache checkout.

## Workflow

### Step 1: Status

```bash
python3 tools/dgf_lines.py status "<dgf-root>" --fetch --json "<scratch>/dgf-lines-status.json"
```

Capture the exit code before any pipe.

| Exit | Action |
|---|---|
| `0` | Every pack is at its line's newest tag with no drift. Say so and **STOP**. |
| `2` | Show every `WARN` line. With `status`, **STOP** here. Otherwise continue with the line(s) the argument names. |
| `1`, `3` | **STOP.** Relay the error. A registry error means `packs/lines.json` or `provenance/lines.json` is broken — fix that first, through this skill's tools or by hand with the user's agreement. |

**Refuse to target an unreleased tree.** A target must be a release tag `X.Y.Z` that `status` listed. The
unreleased commits and `.next` fragments that status reports as `INFO` are synced only once DGF tags them.

### Step 2: Prepare the pack

- **`sync`**: nothing to prepare.
- **`new-line <X.Y>`**: `python3 tools/dgf_lines.py freeze "<dgf-root>" <current> --next <X.Y> --tag <newest X.Y tag>`.
- **`add-line <X.Y> --from <A.B>`**: `python3 tools/dgf_lines.py fork "<dgf-root>" <X.Y> --from <A.B> --tag <newest X.Y tag>`.

Both refuse uncommitted changes under `knowledge/`, `packs/` and `provenance/`. On exit `1`, **STOP**: say
what to commit first. After either, the stamp check fails until Step 7 — that is the honest state of a sync
in progress.

### Step 3: Check out the target, and list what moved

```bash
python3 tools/dgf_lines.py checkout "<dgf-root>" <X.Y> --tag <X.Y.Z>
python3 tools/check_drift.py "<cache>" --pack <X.Y>
python3 tools/dgf_lines.py diff "<dgf-root>" <X.Y> --to <X.Y.Z> --stat
```

- The first prints the cache path, `<cache>`. Every later step reads DGF from there.
- `check_drift` lists every `DRIFT` and `DRIFT_MISSING` source with the knowledge file it feeds.
- `diff --stat` groups them per knowledge file.

### Step 4: Triage each drifted source

For each knowledge file with drift, in the order `diff --stat` lists them:

1. `python3 tools/dgf_lines.py diff "<dgf-root>" <X.Y> --to <X.Y.Z> --path <source>` for its sources.
2. Read the knowledge file's sections that cite those sources. The sections name a DGF type, a file name or
   an MCP call, never a path.
3. Classify each source **COSMETIC**, **FACT-CHANGE** or **NEW-FACT** by `references/TRIAGE.md`, and record
   it for the sync log: the source, the class, and what moved.

A `DRIFT_MISSING` source was moved or deleted. Find where its fact lives now in `<cache>`, and replace the
source with `--add-source` in Step 6. Never drop a fact silently: either re-source it, or remove it and say
why in the log.

### Step 5: Edit the facts

Edit only what Step 4 classified FACT-CHANGE or NEW-FACT, in `<pack>` — `knowledge/` or `packs/<X.Y>/`:

- **Read before you write.** Read the DGF runtime code path that implements a behaviour before stating it
  (`.ai-factory/RULES.md`). A schema or an XSD is no evidence of what the runtime accepts.
- **Machine-read tables.** Keep `knowledge/README.md` §7's format exactly: the marker line, the exact header
  cells, one row per key. Run the stamp check and the unit tests after each table edit.
- **`data-model.md` §6 `field-sql-types`.** When a `data-model` source drifted, run
  `python3 tools/derive_sql_types.py "<cache>"` and copy its tally into the table. Never edit the table by
  judgement.
- **A behaviour that changed inside the line** — between two tags of `X.Y` — gets an `applies:` range,
  `since` and `until`, per `knowledge/README.md` §2.1 and §3. A difference between two lines is two packs,
  not a range. Do not range everything.
- **No DGF paths.** No repository path, and no link out of the shipped set: `doctor.py` blocks on both.
- **Counts.** A count that changed (rows, members, registrations) changes everywhere the file states it.
  Grep the pack for the old number.

### Step 6: Re-vendor, then restamp

```bash
python3 tools/vendor_schemas.py "<cache>" --pack <X.Y>
python3 tools/restamp_knowledge.py "<cache>" --pack <X.Y> <file.md>… [--add-source <dgf-path>]…
python3 tools/restamp_knowledge.py "<cache>" --pack <X.Y> --all
```

- **Re-vendor.** It writes the pack's `schemas/`, its schema ledger and the stamp of `schemas/MANIFEST.md`.
  It refuses a HEAD that is not a tag of the line (exit `1`). After it, update every knowledge fact that
  counts or lists schema files.
- **Restamp the files you re-read.** Name each knowledge file you re-read or judged COSMETIC.
- **Restamp the whole pack.** `--all` restamps every fact file and records the pack in both registries. It
  refuses until the schema ledger is at the tag.

### Step 7: Check

Run each in turn. Every one must end CLEAN before Step 8:

```bash
python3 tools/check_knowledge_stamps.py
python3 tools/check_drift.py "<cache>" --pack <X.Y>
python3 tools/run_known_good.py "<cache>" --pack <X.Y>
python3 skills/dgf-doctor/scripts/doctor.py
python3 -m unittest discover -s tests -t .
```

- **`run_known_good`.** Settle every new error by `.ai-factory/RULES.md`: a validator fix with a test, or an
  `EXCEPTION` line citing the runtime code path in the pack's exceptions file. **Never add an exception to
  make a validator gap pass.** A stale `EXCEPTION` is removed.
- **`tests/test_knowledge.py`.** Add or update `EXPECTED_ROWS["<X.Y>"]` with the pack's table counts.
- **A validator change.** It must hold for every pack, not only this one. Re-run `run_known_good` with
  `--pack` for each registered line whose checkout you have.

On a failure you cannot settle, **STOP**. Leave the tree as it is, list what remains, and do not write the
sync log as complete.

### Step 8: The sync log

Write `provenance/sync-log/<YYYY-MM-DD>-<X.Y>-<X.Y.Z>.md` by `references/SYNC-LOG-FORMAT.md`, with one triage
row for every drifted source. Then run the contract check:

```bash
bash tools/check-dual-schema-docs.sh
```

### Step 9: Report

- **What moved.** The line, from which tag or commit to which tag.
- **Counts.** How many sources were COSMETIC, FACT-CHANGE and NEW-FACT, and the knowledge files edited.
- **Validators.** Any validator change.
- **Exceptions.** Exceptions added and removed.
- **Next.** Review the diff, then commit with `/aif-commit`. Never commit, push or merge yourself.

## Unattended runs

`tools/dgf_lines_watch.sh` may run this skill headless (`claude -p "/dgf-sync sync --all"`) in its own
worktree on a `chore/dgf-sync-<date>` branch:

- **Never ask.** Take the DGF root from `DGF_ROOT`.
- **Stop instead of guessing.** Stop at the first judgement you cannot make from the evidence, and write the
  sync log with that open question under `## Open`.
- **Leave everything uncommitted.** A maintainer reviews it.

## Rules

- ✅ Every digest, stamp, vendored file and registry entry comes from a tool
- ✅ Every drifted source gets a triage row in the sync log
- ✅ Read the runtime code path before stating a behaviour
- ✅ Target release tags only
- ❌ Never hand-edit a ledger's `sha256`, a vendored schema, or `provenance/lines.json`
- ❌ Never add a known-good exception to hide a validator gap
- ❌ Never commit, push, merge, or change the DGF checkout
