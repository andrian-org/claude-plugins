[← DGF Knowledge Sourcing](dgf-knowledge.md) · [Back to README](../README.md) · [DGF Schemas →](dgf-schemas.md)

# DGF Lines — one knowledge pack per DGF release line, kept current

DotGov Framework ships several release lines at once (`1.1` on `master`, `1.2.x` and `1.3.x` as support
branches), and estates run different ones. dgf-factory therefore ships **one knowledge pack per DGF
release line**, and installs one pack into each project. Two projects on one machine can be on different
lines.

This page covers:

- **how a developer picks a line**;
- **how a maintainer brings a pack to a new DGF release**;
- **how to have that checked on a schedule.**

The decision is [ADR 0036](adr/0036-knowledge-packs-per-release-line.md). The operative contract is
[`knowledge/README.md`](../knowledge/README.md) §1, §4 and §8.

## The model

| Where | What |
|---|---|
| `knowledge/` | the **current** line's pack (the newest line tracked), plus the shared `README.md` |
| `packs/<X.Y>/` | each older line's pack: the same file names, no `README.md` |
| `packs/lines.json` | the **shipped** registry: per line its `dir`, `dgf_version` and `read_date`, and the `current` line |
| `provenance/lines.json` | the **maintainer** registry: per line its release `tag`, `commit` and `support_branch` |
| `provenance/knowledge/`, `provenance/packs/<X.Y>/` | each pack's ledgers, one per knowledge file, and its `known-good-exceptions.txt` |
| `provenance/sync-log/` | one triage log per sync |

- **A pack is read at an exact release tag.** `dgf_version` is that tag, never `src/Directory.Build.props`. That
  file's `<Version>` reads `1.1.15` at the tags 1.1.16, 1.2.0 and 1.3.0 alike.
- **Unreleased branch tips are never stamped.** They are reported, then synced once DGF tags them.
- **Packs are full copies, not overlays.** An inherited file would carry a ledger read at another line's tag.
- **`2.x` has no pack.** It carries no release tag, so it is not a release line.

## For a developer: which line a project gets

`dgf-factory setup` picks the pack, in this order:

1. `--dgf-line X.Y`, or `--dgf-version X.Y.Z` (the line of that version);
2. the line the project's receipt, `.dgf-factory/install.json`, recorded last time;
3. the estate's declared `dgf.version` in `.dgf-factory/config.yaml` (written by `/dgf`);
4. the current line. On a terminal setup asks, with that default.

| Declared version | Pack installed |
|---|---|
| its line has a pack | that pack |
| newer than every pack | the newest pack, with a note — it may understate the release |
| between two packs | the nearest older one, with a note |
| older than every pack | **refused** unless `--dgf-line` names one — a newer pack would describe capabilities the estate's runtime lacks |

To switch a project's line, re-run setup:

```bash
dgf-factory setup --dgf-version 1.3.0
```

- **Unchanged files move with the line.** Files that differ are updated, and files only the old pack had are
  removed.
- **Edited files stay put.** A file you edited is kept and reported, as always.

Then run `/dgf-doctor`. In a project it compares the installed line with the declared `dgf.version`:

| Finding | Meaning |
|---|---|
| `DGF_LINE_MISMATCH` | the estate runs another line; the finding names the setup command |
| `DGF_VERSION_BEHIND_PACK` | same line, but the pack was read at a later patch |
| `DGF_VERSION_UNKNOWN` | `dgf.version` is `unknown` |
| `DGF_LINE_UNRECORDED` | installed before lines existed |
| `VERSION_BELOW_SINCE`, `VERSION_ABOVE_UNTIL` | the version gate: an installed fact's `applies:` range against the declared version |

## For a maintainer: bringing a pack to a new release

The tools live in `tools/` and the skill in `.claude/skills/dgf-sync/`. Neither is shipped. Run everything from
`plugins/dgf-factory/`.

| Tool | Does |
|---|---|
| `tools/dgf_lines.py status <dgf> [--fetch] [--json f]` | per line: `TAG_AVAILABLE`, `DRIFT` per knowledge file, `SCHEMA_SET_CHANGED`; `NEW_LINE`; unreleased commits as INFO. Changes nothing |
| `tools/dgf_lines.py diff <dgf> <X.Y> --to <tag> [--path p]` | each drifted source's diff between the pack's commit and the tag, grouped by knowledge file |
| `tools/dgf_lines.py checkout <dgf> <X.Y> [--tag t]` | a `git clone --shared` cache detached at the tag, under `$DGF_LINES_CACHE`. The DGF working copy is never checked out |
| `tools/dgf_lines.py freeze <dgf> <cur> --next <X.Y> --tag t` | the current pack moves to `packs/<cur>/`; `<X.Y>` becomes current |
| `tools/dgf_lines.py fork <dgf> <X.Y> --from <A.B> --tag t` | a new older or side line, copied from `<A.B>` |
| `tools/vendor_schemas.py <cache> --pack <X.Y>` | the pack's vendored schema set, from a checkout at a tag |
| `tools/restamp_knowledge.py <cache> --pack <X.Y> (files… \| --all)` | re-digests ledgers and stamps after a re-read; `--all` records the pack in both registries |
| `tools/check_drift.py`, `tools/check_knowledge_stamps.py`, `tools/run_known_good.py` | each takes `--pack <X.Y>` |

`/dgf-sync` runs the whole flow and writes the sync log:

```text
/dgf-sync status
/dgf-sync sync 1.3 --to 1.3.1        # a new patch on a line
/dgf-sync new-line 1.4               # a new line, newer than the current one
/dgf-sync add-line 1.2 --from 1.3    # an older or side line
/dgf-sync --all                      # everything status reports
```

The skill judges whether each changed source changes a fact. Everything else is a tool's: digests, stamps,
vendored files, registries. The skill never commits; review its diff and commit with `/aif-commit`.

## On a schedule

`tools/dgf_lines_watch.sh <dgf-root>` is the entry for cron or launchd:

- **It runs `status --fetch`.** It logs to `$DGF_LINES_CACHE/watch.log` and posts a desktop notification when
  there is work.
- **It never edits anything by default.**
- **With `DGF_SYNC_AUTORUN=1`** it also adds a git worktree beside the repository, on
  `chore/dgf-sync-<date>` from `$DGF_SYNC_BASE` (default `main`), and runs `claude -p "/dgf-sync sync --all"`
  there.
- **It never commits, pushes or merges.** The sync's edits stay in that worktree for review.
- **One run at a time.** A held lock exits 3.

launchd, weekly on Monday at 09:00 — `~/Library/LaunchAgents/uk.dotgov.dgf-factory.watch.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>uk.dotgov.dgf-factory.watch</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>PLUGIN_ROOT/tools/dgf_lines_watch.sh</string>
    <string>DGF_ROOT</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    <key>DGF_SYNC_AUTORUN</key><string>0</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
</dict>
</plist>
```

Replace `PLUGIN_ROOT` and `DGF_ROOT` with absolute paths, then load it:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/uk.dotgov.dgf-factory.watch.plist
```

cron, the same schedule:

```text
0 9 * * 1  bash PLUGIN_ROOT/tools/dgf_lines_watch.sh DGF_ROOT
```

`--fetch` needs access to the DGF remote (Azure DevOps). Use a credential helper that works without a
terminal, or the run fails at the fetch and logs why.

### Why not CI

The DGF repository is on Azure DevOps (`dev.azure.com/dotgov/DotGovFramework`). This repository's GitHub CI
cannot read it without a personal access token, and deciding that secret's scope is a follow-up of ADR 0036.
Until then the watcher runs on a maintainer's machine.

## See also

- [ADR 0036](adr/0036-knowledge-packs-per-release-line.md) — the decision
- [DGF Knowledge Sourcing](dgf-knowledge.md) — stamping and citing a fact
- [`knowledge/README.md`](../knowledge/README.md) — the operative contract
