# Implementation Plan: DGF Version Packs — align with DGF 1.3, support several DGF lines, sync periodically

Branch: feature/dgf-version-packs (stacked on `feature/quality-skills-parallel-execution` at f95563c — that branch
is 4 commits ahead of `main` and unmerged; branching from `main` would plan against stale code)
Created: 2026-11-04

## Original Request

full analyse the updates made in DGF and update the dgf-factory to be aligned with latest version of DGF. 
As a result i need a skill, script or something else that ill update to DGF periodically.
Ideally it will be to support multiple DGF versions at the same time. The same developer cand work on different projects with different version of DGF.

DGF PWD: /Users/andrianmamei/workspaces/dotgov/_DotGovFramework/DotGovFramework

## Settings

- Testing: yes — unittest for every new/changed tool and script (synthetic git repositories with tags and
  branches for the line tools, as `tests/test_check_drift.py` builds its fixtures); `node --test` for the
  installer; per-pack table-load tests; `tools/run_known_good.py --pack <line>` over DGF's samples per line
- Logging: verbose — `report.debug` / `DEBUG=1` traces on stderr in Python (`DEBUG [<module>.<event>] k=v`),
  `log.debug` in `cli/`; every tool prints a labelled summary and a final verdict line (`CLEAN`, `WARNINGS`,
  `BLOCKED`)
- Docs: yes — mandatory docs checkpoint at completion
- Mode: Handoff non-interactive (`HANDOFF_MODE=1`, no task id, branch not prepared) — preferences above are the
  declared defaults, not user answers

## Roadmap Linkage

Milestone: "none"
Rationale: "Skipped — non-interactive Handoff default (no milestone selected)"

## Evidence — what changed in DGF (read 2026-11-04)

DGF checkout `…/DotGovFramework`, branch `1.3.x` at `9a376eb37`. Knowledge base read at `aa1d5c4c2`
(develop, 2026-09-11), stamped `1.1.11`.

**Version source is broken.** `src/Directory.Build.props` `<Version>` (ClientDebug-only) reads `1.1.11` at tags
1.1.12–1.1.15 and `1.1.15` at tags 1.1.16, 1.2.0, 1.3.0 and every branch tip. The release version is GitVersion
from tags (`GitVersion.yml`: support branches `^\d+\.\d+\.x$`; PR 7788: 1.3.x → 1.3.1-n, 1.2.x → 1.2.1-n). The
knowledge base is really ≈1.1.15 content (it contains RELEASE-1.1.12…1.1.15), not 1.1.11.

**Release lines** (`git merge-base --is-ancestor`):

| Line | Released tag(s) | Where | Status |
|---|---|---|---|
| 1.1 | 1.1.16 (10-02), 1.1.15 | `master` (not an ancestor of 1.2/1.3) | final release of the line |
| 1.2 | 1.2.0 (10-27) | `origin/1.2.x` (tip a5c22295f, unreleased 1.2.1-n) | supported |
| 1.3 | 1.3.0 (11-03) | `origin/1.3.x` (tip 9a376eb37, unreleased 1.3.1: 30 `.next` fragments) | latest |
| 2.x | none | `origin/2.x`, stale since 10-22, NEXT reads v1.1.17 | **not a release line — excluded** |

No `RELEASE-1.2.0.md` exists; `RELEASE-1.3.0.md` collates 1.2.0 and 1.3.0.

**Drift** (`tools/check_drift.py`, exit 2): 151 of 565 ledger sources changed, 0 missing, across all 11 ledgers.
Triage (source diffs read against the knowledge text):

| Knowledge file | Verdict | The facts that move |
|---|---|---|
| schema-families.md | re-read | §6 parity 67 → 69 rows (AutoComplete ✓, Chart ✓ "JSON forms only", renumbering); §3 `SchemaIndexService` now indexes 6 DataSource files under 9 discriminators (unindexed 11 → 5); §1/§3/§5 **10 XSDs** (`application-sitemap.xsd`, root `map`); JSON files 69 → 71 |
| component-catalogue.md | re-read | `ComponentType` 67 → 69; `RegisterComponentService` 34 → 36 (AutoComplete, Chart); lifecycle 56 → 58; examples 59 → 68 |
| json-reader.md | re-read | SchemaExporter emits **camelCase properties and camelCase string enums** (commit b1fcf0f61, shipped 1.1.16); `enum` now lists JSON names, `x-enumNames` keeps C# names; `component-classes` + 2 rows; Row `BackgroundColor` removed (1.2.0) |
| application-layout.md | re-read | sign-in menu rule; `RoleDisplayName` (1.3.0); `NormalizeKey` role check; local stack: gotenberg removed, demo accounts officer/registrar/applicant, new `.env` keys, BFF Dockerfile fonts, secrets count |
| process-model.md | targeted | `OnInit` is `xs:choice` 0..n incl. `StoredProcedureActivity` → delete the `process-divergence` row |
| data-model.md | targeted | `settings.xsd` `FieldTypeEnum` drops `Decimal`/`Memo`, adds `displayFormat`; tab `@visible`/`propertyConvertor` |
| permissions.md | targeted | `roles="A, B"` now trims (1.3.0) |
| naming-conventions.md | targeted | 69 members; camelCase `type`; DataSource indexed by discriminator |
| composition-specs.md | targeted | 34 → 36; `profile.xsd` now compiles |
| reference-graph.md | re-digest | cosmetic only |
| schemas/ | full re-vendor | 2 new JSON schemas, 1 new XSD, 8 XSDs tightened (workflow adds ExecuteRequest, DataSourceStep, CreateRecord, OutputMapping, Break, Goto, StateProcess, ForeachRecord), every `*Configuration.schema.json` regenerated |

**Behavioural changes with a version boundary**, inside the knowledge topics: TreeTable `expandAll`/eager `paging`
(1.1.15); `roles`/`deny` trimming (1.3.0); components inside tabs need `${form.comp}` (1.3.0);
`onbeforesave="false"` no longer suppresses `onsavescript` (1.3.0); unknown legacy cell type keeps the field
(1.2.0); Row `backgroundColor` removed (1.2.0); `allowUnauthorizedAccess` enforced (unreleased 1.3.1).

**Validator risks found in this repository:**
- `scripts/lib/json_validate.py:145-167` `enum_accepts` assumes "a string enum lists no values, and the reader
  takes any integer for it". The regenerated schemas list camelCase values in string enums.
- `tests/test_knowledge.py:14-21` hard-codes 67 parity rows, 67 component classes and 34 dispatchable.

## Decisions

1. **One knowledge pack per DGF release line**, pinned to a **release tag**. A pack is a full knowledge tree:
   the fact files, `schemas/`, the stamps. The repository keeps:
   - `knowledge/` — the **current** line (1.3 after this plan). Every existing path, skill reference and test
     keeps working.
   - `packs/<line>/` — each frozen older line. Same file names as `knowledge/`, without `README.md`, which stays
     shared.
   - `packs/lines.json` — the **shipped** registry: line, `dir`, `dgf_version` (the tag), `read_date`, `current`.
   - `provenance/lines.json` — the **maintainer** registry: line → `tag`, `commit`, `support_branch`.
   - `provenance/packs/<line>/` — that line's ledgers plus its `known-good-exceptions.txt`.

   No size-saving overlay: three full packs are about 11 MB unpacked, and a project installs one (about 3.6 MB).
2. **Several DGF versions at once = one pack per project.**
   - `dgf-factory setup` installs exactly one pack into `.dgf-factory/runtime/knowledge/`: the shared `README.md`
     plus that line's files.
   - The receipt records `dgfLine`.
   - Skills and scripts are unchanged in a project: they still read `{{dgf_runtime}}/knowledge/…`.
   - Two projects on one machine can hold different lines, because the runtime is per project (ADR 0029).
   - The toolchain — `scripts/`, `skills/`, `cli/` — is one codebase and must work against every pack.
3. **A pack's version is its release tag.** This supersedes the `Directory.Build.props` rule of ADR 0013 §1 and
   `knowledge/README.md` §1.1. A pack is read only from a checkout whose HEAD is exactly a release tag
   (`git describe --exact-match --tags`, matching `^\d+\.\d+\.\d+$`):
   - `dgf_version` = that tag;
   - the schema ledger records `dgf_commit` and `dgf_tag`.

   This is deterministic: tag → commit. ADR 0013 rejected `git describe` because it was branch-relative; an
   exact-match tag is not. Unreleased branch tips are never stamped.
4. **Version → line** is major.minor of `dgf.version`. The asymmetry of ADR 0013 §4 decides the fallbacks:

   | Declared version | Pack used |
   |---|---|
   | newer than every registered line | the newest pack, with a warning — it understates capability, which is safe |
   | older than every registered line | refused, unless `--dgf-line` is given explicitly — it would overstate capability |
   | within a line but below the pack's tag | warning `DGF_VERSION_BEHIND_PACK` plus `get_release_notes("since:<v>")` |
5. **Within-line differences** use the existing file-level `applies:` ranges. The ADR 0013 §4 version gate
   finally gets built, in the doctor's project mode: it reads `dgf.version` only, as ADR 0019 requires.
   Row-level ranges in machine-read tables are out of scope, and stated as a limitation.
6. **Periodic update** is deterministic detection plus a maintainer skill. Neither is shipped.
   - **Detection:** `tools/dgf_lines.py status --fetch` is read-only on knowledge and safe to schedule.
   - **Edits:** `.claude/skills/dgf-sync/` is a project-local maintainer skill — not `aif-*`, not in the
     payload. It triages drift with `git diff`, edits facts, re-digests through tools, re-vendors, runs the
     checks and writes a sync log.
   - **Scheduling:** `tools/dgf_lines_watch.sh` is the cron/launchd entry. With `DGF_SYNC_AUTORUN=1` it runs the
     skill headless (`claude -p`) in a dedicated worktree on branch `chore/dgf-sync-<date>`. It never commits to
     `main` and never pushes; a human reviews and merges.
   - **No GitHub Action:** DGF lives on Azure DevOps (`dev.azure.com/dotgov/DotGovFramework`), which this
     repository's CI cannot read without a PAT. This is recorded as a follow-up, not built.
7. **Line checkouts never disturb the DGF working copy.**
   - `tools/dgf_lines.py checkout` makes `git clone --shared` caches under
     `${DGF_LINES_CACHE:-$XDG_CACHE_HOME/dgf-factory/lines}/<line>`, detached at the tag's commit.
   - The existing tools — `check_drift`, `vendor_schemas`, `run_known_good` — run against that cache unchanged.
   - `--fetch` (`git fetch --tags origin`) is the only write to the DGF repository, and it touches remote-tracking
     refs only.
8. **ADR 0036** records 1–7 and **supersedes ADR 0013 in full**: it restates every still-valid section — stamp
   classes, `null` semantics, the gate table, the ledger. ADR 0019 stays accepted: its key is still the gate's
   only input, and setup reads it only as a default. `2.x` is excluded until it carries a tag.
9. **"Latest version of DGF" = tag `1.3.0`**, the latest release. **Confirmed by the user on 2026-11-04.** The
   1.3.1 fragments are unreleased; `status` reports them and the sync happens once `1.3.1` is tagged. The plan
   does not stamp unreleased content (Decision 3).
10. **Content alignment is a chain:** `aa1d5c4c2` → `1.1.16`, freeze `packs/1.1` → `1.2.0`, freeze `packs/1.2` →
    `1.3.0` = `knowledge/`. Drift is computed by digest, so ancestry does not matter: 1.1.16 lives on `master`.
    Each step's drift is smaller than one jump, and each step exercises the sync skill end to end.

## Requirements Reconciliation

Authority, highest first:
1. the user's request;
2. ADR 0029 / ADR 0030 — delivery, shipped payload, no DGF paths;
3. ADR 0013 and `knowledge/README.md` — stamps;
4. ADR 0019 — `dgf.version`;
5. `.ai-factory/RULES.md` and `rules/base.md`.

| Point | Sources | Relation | Resolution |
|---|---|---|---|
| Version source | ADR 0013 §1, README §1.1 ("never from a git tag") vs DGF evidence (props ≠ releases) | **conflict** | New ADR 0036 supersedes 0013 in full; README is rewritten to agree. Never edit 0013's decision: status only |
| Gate input | ADR 0019 ("the version gate reads only `dgf.version`") vs setup choosing a line | refines | The gate (doctor) reads only `dgf.version`; setup's line choice is an install option, which may default from `dgf.version` |
| No DGF paths | ADR 0030 vs registries naming tags/branches | agree | Tag names are not paths. `support_branch` and `commit` stay in `provenance/lines.json` (not shipped); `packs/` joins `SHIPPED_DIRS` and the package check |
| Determinism | rules/base.md vs triage of drift | refines | Detection, digests, vendoring, freeze and restamp are scripts. Only "does this diff change a fact" is judgement, logged per source in the sync log |
| Single-writer | AGENTS.md | constraint | `.ai-factory/DESCRIPTION.md` and `ARCHITECTURE.md` are updated by their owners at the docs checkpoint, not by implement tasks |

**Setup line selection** — material combinations:

| `--dgf-line` / `--dgf-version` | Prior receipt `dgfLine` | Config `dgf.version` | Result | Verification |
|---|---|---|---|---|
| `--dgf-line 1.2` (registered) | any | any | install 1.2 | node test |
| `--dgf-line 9.9` (unregistered) | any | any | exit 3, lists lines | node test |
| both flags | any | any | exit 3 | node test |
| `--dgf-version 1.2.0` | any | any | 1.2 | node test |
| `--dgf-version 1.4.2` (above all) | any | any | 1.3 + warning "understates" | node test |
| `--dgf-version 1.0.9` (below all) | any | any | exit 1, suggests `--dgf-line` | node test |
| `--dgf-version 1.x` (malformed) | any | any | exit 3 | node test |
| none, `--yes` | 1.2 | 1.3.0 | **1.2** (receipt wins; doctor then warns `DGF_LINE_MISMATCH`) | node test |
| none, `--yes` | none | 1.2.0 | 1.2 | node test |
| none, `--yes` | none | `unknown` / absent | current line + note | node test |
| none, interactive | any | any | prompt; default = receipt → config → current | node test with scripted stdin |
| re-run, different line | 1.1 | — | old pack's files update/remove per ADR 0029 §5; an edited knowledge file → keep-edited/conflict | node test + smoke |

**Doctor in a project** — receipt `dgfLine` × config `dgf.version`:

| Situation | Finding | Exit |
|---|---|---|
| receipt has no `dgfLine` (installed ≤ 0.2.0) | `DGF_LINE_UNRECORDED` — re-run setup | 2 |
| no config yet | INFO, no finding | 0 |
| config `unknown` | `DGF_VERSION_UNKNOWN` | 2 |
| line(config) ≠ `dgfLine` | `DGF_LINE_MISMATCH`, with the exact `dgf-factory setup --dgf-version <v>` | 2 |
| same line, config < pack tag | `DGF_VERSION_BEHIND_PACK` | 2 |
| installed fact `applies.since` > config | `VERSION_BELOW_SINCE` (unless `out_of_range: warn`) | 1 |
| installed fact `applies.until` < config | `VERSION_ABOVE_UNTIL` | 2 |

**Real-artifact verification:** the content tasks run against the real DGF checkout's tags `1.1.16`, `1.2.0`
and `1.3.0`. The smoke install sets up two scratch projects on different lines.

Meaning preservation: PASS. "Aligned with latest version" is read as the latest *release*, with the reason
stated in Decision 9. "Ideally … multiple versions" is treated as a goal and implemented, not weakened.
"Periodically" is met by a schedulable detector plus an opt-in headless run. Nothing auto-merges.

## Interfaces

### Registries

`packs/lines.json` (shipped; Node and Python read it):
```json
{"format": 1, "current": "1.3",
 "lines": [{"line": "1.3", "dir": "knowledge", "dgf_version": "1.3.0", "read_date": "2026-11-…"},
           {"line": "1.2", "dir": "packs/1.2", "dgf_version": "1.2.0", "read_date": "…"},
           {"line": "1.1", "dir": "packs/1.1", "dgf_version": "1.1.16", "read_date": "…"}]}
```
`provenance/lines.json` (maintainer): `{"format":1,"lines":{"1.3":{"tag":"1.3.0","commit":"<sha>","support_branch":"1.3.x"},…}}`.

The two registries agree on the set of lines. Each pack's stamps all equal its `dgf_version`.
`check_knowledge_stamps.py` enforces both.

### `tools/packs.py` (maintainer module, stdlib)
`load_registry()`, `lines()`, `current()`, `pack_dir(line) -> Path`, `ledger_dir(line) -> Path`,
`exceptions_file(line) -> Path`, `line_of(version) -> "X.Y"`, `parse_version(s) -> (int,int,int)` (strict
`^\d+\.\d+\.\d+$`). The single place a tool learns where a pack lives.

### `scripts/lib/knowledge.py` (shipped)
- `KNOWLEDGE_DIR` stays the single seam. Tests already replace it (`tests/test_graph.py:328`,
  `tests/test_validate_model.py:384`).
- At import it is `$DGF_KNOWLEDGE_DIR` when set, else the existing `parents[2]/knowledge`.
- `knowledge_dir()` returns the attribute.
- `use_dir(path)` sets it and clears every resolver cache:
  - `json_resolve`: `_RAW`, `_MERGED`, `_MEMBERS`;
  - `xsd`: `_COMPILED`, `_UNCOMPILABLE`, `_ROOTS`, `_EXTENDED`;
  - `knowledge._CACHE` is already keyed by directory.
- `json_resolve` and `xsd` derive their directories from `knowledge.knowledge_dir()` at each use.
  `xsd.XSD_DIR` / `json_resolve.SCHEMA_DIR` remain as module-level properties via a `__getattr__`, so
  `tests/test_xsd.py:156` keeps working.
- Why not the environment variable alone: `run_known_good.py` runs the validators in-process
  (`scripts/lib/runner.py:59-69`), so a variable set after import changes nothing and the caches would serve the
  previous pack.

`scripts/lib/dgf_version.py` (stdlib): parse, compare, `line_of`,
`select_line(version, lines)` → `(line, note)` per Decision 4 — the Python twin of the Node selector, with
shared test vectors in `tests/fixtures/unit/dgf-lines/selection.json`.

### `tools/dgf_lines.py`
```
dgf_lines.py status   <dgf-root> [--fetch] [--json <out>] [--line <l>] [--verbose]
dgf_lines.py checkout <dgf-root> <line> [--tag <tag>]          # prints the cache path; default tag = registry's
dgf_lines.py freeze   <line>                                    # knowledge/ → packs/<line>/, ledgers too; registers
dgf_lines.py fork     <new-line> --from <line>                  # copy a pack to start a new older/side line
```

`status`, per registered line:
- the pinned tag and commit;
- the newest release tag on the line — `^X\.Y\.\d+$`, compared numerically: `TAG_AVAILABLE`, warn;
- unreleased commits on `origin/<support_branch>` since the newest tag: INFO;
- `.next` fragment count: INFO;
- drift of the pack's ledgers at the newest tag, through a checkout cache and `check_drift.py --pack`:
  `DRIFT`, warn, with a per-knowledge-file count;
- schema files added or removed upstream: `SCHEMA_SET_CHANGED`, warn.

`status` across lines: an `X.Y.0` tag or `origin/X.Y.x` branch with no registered line is `NEW_LINE`, warn;
`2.x` without a tag is INFO only.

Exit codes: `0` nothing to do, `2` work available, `3` usage error — not a DGF root, a bad registry.
`--json` writes `{line: {tag, newest_tag, drift: {file: n}, …}, new_lines: […]}` for the skill and the
watcher.

`freeze` and `fork` refuse an existing target and an unclean `knowledge/`/`provenance/` (`git status`). They copy
files, never edit facts. Besides the fact files and the ledgers, they copy the source line's known-good exceptions
— `tools/known-good-exceptions.txt` for the current line, `provenance/packs/<from>/known-good-exceptions.txt`
otherwise — to `provenance/packs/<line>/known-good-exceptions.txt`.

### `tools/restamp_knowledge.py`
```
restamp_knowledge.py <dgf-checkout> --pack <line> (<knowledge-file>… | --all) [--add-source <dgf-path>]… [--read-date D] [--dry-run]
```
- Re-digests the named knowledge files' ledgers from the checkout.
- Sets `dgf_version` to the checkout's exact tag, and `read_date`.
- Refuses (exit 1) a checkout that is not exactly at a release tag, a tag whose line differs from `--pack`, a
  dirty cited file, or a source missing upstream.
- `--all` also updates `packs/lines.json` and `provenance/lines.json` for that line.
- It is the only writer of ledger digests besides `vendor_schemas.py`.

### Existing tools gain `--pack <line>` (default: the current line)
| Tool | Change |
|---|---|
| `check_drift.py` | ledgers from `provenance/packs/<line>/` (or `provenance/knowledge/`). Version check: the checkout's exact tag vs the pack's stamp; the props check is dropped. `<Version>` is reported as INFO only |
| `vendor_schemas.py` | writes `<pack>/schemas/`, that pack's ledger. `dgf_version` from the exact tag (refuses a non-tag HEAD, exit 1). The ledger gains `dgf_tag` |
| `check_knowledge_stamps.py` | checks **every** pack by default (`--pack` narrows). Stamps equal the registry's `dgf_version`; registries agree; every pack has every ledger; no `README.md` in a pack |
| `run_known_good.py` | calls `knowledge.use_dir(<pack dir>)` before `runner.run` (in-process — not an env var); uses the pack's exceptions file; checks the checkout's tag is the pack's |

### Installer
- `cli/lines.mjs` (new): `loadLines(packageRoot)`, `selectLine({flagLine, flagVersion, receiptLine, configVersion, lines})`
  → `{line, note}` or throws `usageError` / `blockedError`. It reads `<project>/.dgf-factory/config.yaml`'s
  `dgf.version` with a minimal line scan, with no YAML library.
- `cli/commands/setup.mjs`: `--dgf-line <l>` / `--dgf-version <v>`; the prompt after the harness choice. The
  preview header gains `DGF line: 1.2 (knowledge read at 1.2.0)`.
- `cli/plan.mjs`: `desiredFiles(packageRoot, harnesses, line)` maps runtime `knowledge/<rel>` from the pack
  dir. `knowledge/README.md` always comes from `knowledge/`. `packs/` is never installed except through this
  mapping. The receipt's `source` holds the real package path (`packs/1.2/schema-families.md`).
- `cli/receipt.mjs` + `scripts/lib/install_receipt.py`: optional top-level `dgfLine` (string `X.Y`). It is
  validated in both; an older receipt without it still loads.
  - `dgfLine` joins `TOP` in `cli/receipt.mjs:24`. `keysOnly(data, TOP)` (`:69`) refuses unknown keys, so a 0.2.0
    CLI refuses a 0.3.0 receipt — documented: update the CLI first.
  - The Python reader does not check top-level keys. It only gains validation of `dgfLine`'s form.
- `package.json` `files` + `packs`; version `0.3.0`. `tools/check_package.py` expects `packs/`.
  `doctor.py` `SHIPPED_DIRS` + `packs`.

## Tasks

### Phase 1 — Decision

- [x] **Task 1: ADR 0036 and the stamping contract.**
  - **Deliverable:**
    - `docs/adr/0036-knowledge-packs-per-release-line.md` (status `accepted`, supersedes `[0013]`). It restates
      every still-valid section of 0013 and decides Decisions 1–9. Its Context cites the evidence above with
      DGF paths: maintainer file, allowed.
    - ADR 0013 frontmatter `status: superseded-by-0036` — status only, decision text untouched.
    - `docs/adr/README.md` index row.
    - Rewrite `knowledge/README.md` §1, §1.1 (the tag rule, the props history kept as context), §4 (the gate
      lives in the doctor's project mode), plus a new §8 "Packs".
    - Update `docs/dgf-knowledge.md`.
  - **Logging:** none (docs).
  - **Check:** `tools/check-dual-schema-docs.sh` §5/§5b (frontmatter, supersession integrity, index) passes.
  - **Files:** docs/adr/0036-knowledge-packs-per-release-line.md, docs/adr/0013-version-gating-provenance-ledger.md,
    docs/adr/README.md, knowledge/README.md, docs/dgf-knowledge.md

### Phase 2 — Pack-aware maintainer tooling

- [x] **Task 2: Registries, `tools/packs.py`, and a knowledge root that can move.** (depends: 1)
  - **Registries:** `packs/lines.json` and `provenance/lines.json`, seeded with one line: `"1.1"` →
    `dir: knowledge`, pinned to commit `aa1d5c4c2` with no tag. It is marked `"legacy": true` with
    `dgf_version` left at `"1.1.11"`. `check_knowledge_stamps` accepts a non-tag pin and the props-era stamp
    only for a legacy entry. Task 9 re-pins it to tag `1.1.16` and removes the flag.
  - **Code:**
    - `tools/packs.py` per Interfaces.
    - `scripts/lib/knowledge.py`: keep `KNOWLEDGE_DIR` as the seam (initialised from `DGF_KNOWLEDGE_DIR` at
      import); add `knowledge_dir()` and `use_dir(path)`, which clears the `json_resolve` caches (`_RAW`,
      `_MERGED`, `_MEMBERS`) and the `xsd` caches (`_COMPILED`, `_UNCOMPILABLE`, `_ROOTS`, `_EXTENDED`).
    - `json_resolve.py` and `xsd.py` derive their directories from `knowledge.knowledge_dir()` at each use,
      keeping `SCHEMA_DIR` / `XSD_DIR` readable through a module `__getattr__`.
    - `scripts/lib/dgf_version.py`.
  - **Logging:** `DEBUG [knowledge.dir] source=env|default|use_dir path=…`,
    `DEBUG [knowledge.use_dir] cleared=json_resolve,xsd`, `DEBUG [packs.registry] lines=…`.
  - **Tests:**
    - `tests/test_packs.py` — registry load, malformed registry → exit-3 error, `line_of`, `parse_version`.
    - `tests/test_dgf_version.py` — every row of the selection table, from `tests/fixtures/unit/dgf-lines/selection.json`.
    - `tests/test_knowledge.py`:
      - the env override sets the initial directory;
      - `use_dir()` switches all three resolvers;
      - a schema loaded before `use_dir()` is not served after it;
      - `tests/test_graph.py`, `tests/test_validate_model.py` and `tests/test_xsd.py` still pass unchanged.
    - In `tests/test_knowledge.py`, replace the hard-coded table counts (`:14-21`) with a per-pack expectation
      keyed by line, loaded from the registry: the legacy pack's 67/67/34 now; Tasks 9–11 add theirs.
  - **Files:** packs/lines.json, provenance/lines.json, tools/packs.py, scripts/lib/knowledge.py,
    scripts/lib/json_resolve.py, scripts/lib/xsd.py, scripts/lib/dgf_version.py, tests/test_packs.py,
    tests/test_dgf_version.py, tests/test_knowledge.py, tests/fixtures/unit/dgf-lines/selection.json

- [x] **Task 3: Existing tools learn `--pack`; the version comes from the exact tag.** (depends: 2)
  - **Deliverable:** the four tools per the Interfaces table. `check_drift.py` keeps one drift implementation:
    the ledger parser still comes from `check_knowledge_stamps.py`. The props `<Version>` is reported only as
    INFO `PROPS_VERSION`.
    - `run_known_good.py` calls `knowledge.use_dir(<pack dir>)` before `runner.run` — the validators run
      in-process, so an environment variable would not reach them.
    - It reads exceptions from `tools/known-good-exceptions.txt` for the current line and
      `provenance/packs/<line>/known-good-exceptions.txt` otherwise.
  - **Logging:** `DEBUG [<tool>.pack] line=… knowledge=… ledgers=…`; one INFO line naming the pack and the tag
    in each summary.
  - **Tests:**
    - Extend `tests/test_check_drift.py`: `--pack` picks the pack's ledgers; a non-tag HEAD is a version
      warning; a tag mismatch warns. Fixtures are git repos with tags.
    - `tests/test_check_knowledge_stamps.py` (new or extended): two packs, stamp ≠ registry → error; a ledger
      missing in a pack → error; `README.md` inside a pack → error; registries disagreeing → error.
    - Extend `tests/test_run_known_good.py` for `--pack` exception selection.
  - **Files:** tools/check_drift.py, tools/vendor_schemas.py, tools/check_knowledge_stamps.py,
    tools/run_known_good.py, tests/test_check_drift.py, tests/test_check_knowledge_stamps.py,
    tests/test_run_known_good.py

- [x] **Task 4: `tools/dgf_lines.py` and `tools/restamp_knowledge.py`.** (depends: 3)
  - **Deliverable:** both per Interfaces.
    - `status` composes `checkout` with `check_drift.py --pack`, imported, not shelled.
    - `checkout` uses `git clone --shared --no-checkout` once, then `git -C <cache> checkout --detach <sha>`. The
      sha is resolved in the DGF repo, so remote-tracking refs work without cloning them.
    - Tag ordering is numeric.
    - `freeze` and `fork` copy with `shutil.copy2`, excluding `README.md`. They also copy the source line's
      known-good exceptions file into `provenance/packs/<line>/`, and update both registries.
  - **Logging:** `DEBUG [dgf_lines.status] line=… tag=… newest=… unreleased=…`,
    `DEBUG [dgf_lines.checkout] cache=… sha=…`, `DEBUG [restamp.source] path=… old=… new=…`. Each subcommand ends
    with a verdict line.
  - **Tests:** `tests/test_dgf_lines.py` and `tests/test_restamp_knowledge.py` over a synthetic DGF repo with
    tags `1.1.16` (side branch), `1.2.0`, `1.3.0`, `1.3.1`, branches `1.2.x`/`1.3.x`/`2.x`, `.next` fragments and
    a ledger-cited file changed between tags.
    - `status`: `TAG_AVAILABLE` for 1.3.1, `NEW_LINE` for an unregistered `1.4.0`, `2.x` INFO, `--json` shape,
      exit codes.
    - `freeze`/`fork`: refusals (existing target, dirty tree); the exceptions file is copied.
    - The synthetic repo reuses `tests/helpers.py`'s `git`, `make_repo` and `commit_all`, adding only `tag()` and
      `branch()` helpers.
    - `restamp`: refusals (non-tag HEAD, wrong line, missing source).
    - `--add-source` adds a source.
    - The DGF repo's HEAD and working tree are unchanged after `status`/`checkout`.
  - **Files:** tools/dgf_lines.py, tools/restamp_knowledge.py, tests/test_dgf_lines.py,
    tests/test_restamp_knowledge.py, tests/helpers.py (`tag()`, `branch()` beside the existing git helpers)

### Phase 3 — Install one pack per project

- [x] **Task 5: Setup selects a line; the receipt records it.** (depends: 2)
  - **Deliverable:** per the Installer interface and the setup combination table, every row.
    - Usage text documents both flags.
    - The `Next:` lines say which line was installed and how to switch (`dgf-factory setup --dgf-version <v>`).
    - `dgf-factory status` shows `dgfLine`.
    - Python `install_receipt.py` accepts `dgfLine` and exposes `line(root)`.
  - **Logging:** `log.debug('lines.select', {flagLine, flagVersion, receiptLine, configVersion, chosen, note})`,
    `log.debug('plan.pack', {line, dir, files})`.
  - **Tests:**
    - `tests/cli/lines.test.mjs`: the shared selection vectors plus the config scan.
    - Extend `tests/cli/setup.test.mjs` / `plan.test.mjs`: a pack → runtime mapping; README always from
      `knowledge/`; switching line removes files only in the old pack; an edited knowledge file is kept.
    - The node tests build a fake package root with `knowledge/` and two `packs/<line>/` trees plus a
      `packs/lines.json`; they never depend on the real packs' content.
    - `tests/cli/receipt.test.mjs`: `dgfLine` in `TOP`; an invalid form → usage error; an old receipt loads.
    - `tests/cli/status.test.mjs`: `status` prints `dgfLine`, or `unrecorded` for an old receipt.
    - `tests/test_install_receipt.py`.
    - Extend `tools/smoke_install.sh`: two scratch projects, `--dgf-line 1.1` and the default, then assert each
      runtime's stamps.
  - **Files:** cli/lines.mjs, cli/commands/setup.mjs, cli/commands/status.mjs, cli/plan.mjs, cli/receipt.mjs,
    scripts/lib/install_receipt.py, package.json, tools/check_package.py, tools/smoke_install.sh,
    tests/cli/lines.test.mjs, tests/cli/setup.test.mjs, tests/cli/plan.test.mjs, tests/cli/receipt.test.mjs,
    tests/cli/status.test.mjs, tests/test_install_receipt.py

- [x] **Task 6: The doctor checks the line and gates ranged facts; skills say which pack they read.** (depends: 5)
  - **`doctor.py`:**
    - `SHIPPED_DIRS` + `packs`.
    - **Package mode:** the registry is valid; every pack dir exists and loads every machine-read table
      (`check_knowledge_tables` per pack, through `knowledge.load(table, pack_dir)`); no DGF path in `packs/`.
    - **Project mode:** the doctor-in-a-project table, every row. The config is read with the same minimal scan.
    - Every finding ID goes through doctor's own `error`/`warn`.
  - **`inventory_root.py`:** the `KNOWLEDGE:` line becomes `KNOWLEDGE: dgf_version=<v> line=<l>`, with the line
    from the installed stamps.
  - **`skills/dgf/SKILL.md` Step 4:** compare the declared version with the installed line. On a mismatch, give
    the setup command — do not edit knowledge. Keep ADR 0019's `unknown` and newer-than-stamp behaviour.
  - **`dgf-grounded` / `dgf-explore`:** name the line beside the stamp.
  - **`skills/dgf-scaffold/scripts/design.py`:** `dgf_version`'s line ≠ installed line → warning
    `SCAFFOLD_LINE_MISMATCH`, registered in `report.py`.
  - **Logging:** `DEBUG [doctor.line] receipt=… config=… pack_version=…`,
    `DEBUG [doctor.gate] file=… since=… until=… declared=…`.
  - **Tests:**
    - `tests/test_doctor.py`: each project-mode row, plus a package-mode broken pack.
    - `tests/test_inventory_root.py`: the line.
    - `tests/test_scaffold_design.py`: the mismatch.
    - `tests/test_skill_contracts.py` still passes (no bare `knowledge/` path, `{{dgf_runtime}}` only).
    - Walk `/dgf` Step 4's worked example against the doctor/inventory output — RULES.md "a skill that STOPs on
      a script's exit code".
  - **Files:** skills/dgf-doctor/scripts/doctor.py, skills/dgf-doctor/SKILL.md, scripts/inventory_root.py,
    scripts/lib/report.py, skills/dgf/SKILL.md, skills/dgf/references/description-template.md,
    skills/dgf-grounded/SKILL.md, skills/dgf-explore/SKILL.md, skills/dgf-scaffold/scripts/design.py,
    tests/test_doctor.py, tests/test_inventory_root.py, tests/test_scaffold_design.py

### Phase 4 — The periodic update

- [x] **Task 7: The maintainer skill `/dgf-sync`.** (depends: 4)
  - **Deliverable:** `.claude/skills/dgf-sync/SKILL.md`, prompt-as-program, the house style of
    `skills/dgf-doctor/SKILL.md`.
    - **Frontmatter:** `allowed-tools` narrowed to `Bash(python3 tools/dgf_lines.py *)`,
      `Bash(python3 tools/check_drift.py *)`, `Bash(python3 tools/vendor_schemas.py *)`,
      `Bash(python3 tools/restamp_knowledge.py *)`, `Bash(python3 tools/check_knowledge_stamps.py *)`,
      `Bash(python3 tools/run_known_good.py *)`, `Bash(python3 tools/derive_sql_types.py *)`,
      `Bash(python3 -m unittest *)`,
      `Bash(git -C <dgf> diff *)`/`log`/`show` (read-only forms only — ADR 0035's lesson: no bare `git *`),
      Read, Edit, Write.
    - **Modes:**
      - `status`;
      - `sync <line> [--to <tag>]`;
      - `new-line <line>` — a newer line: `freeze <current>`, register, then sync `knowledge/` to the new tag;
      - `add-line <line> --from <line>` — an older or side line: `fork`, then sync;
      - `--all` — every line with `TAG_AVAILABLE`/`DRIFT`.
    - **Steps:** status → checkout → `check_drift --pack` → for each drifted source, `git diff <ledger commit>
      <tag> -- <path>`, classified COSMETIC / FACT-CHANGE / NEW-FACT against the knowledge text → edit only
      FACT-CHANGE/NEW-FACT facts, with machine-read tables per `knowledge/README.md` §7. When a `data-model`
      source drifted, regenerate the `field-sql-types` table (data-model §6) from `derive_sql_types.py <cache>`'s
      tally — never hand-edit it → `restamp_knowledge`
      → `vendor_schemas --pack` → read the release notes between tags for behavioural facts inside the line and
      add `applies:` only where the boundary is within the line → `check_knowledge_stamps` → `run_known_good
      --pack` (each new error settled per RULES.md: a validator fix or an EXCEPTION citing the runtime path —
      never an exception to hide a gap) → unit tests → the sync log → a summary.
    - **STOP rules:** any tool exit 1/3; a FACT-CHANGE in a validator-relevant table with no failing test to
      prove the validator still holds; an unreleased tip as a target; a dirty repo.
    - **References:** `references/SYNC-LOG-FORMAT.md` (the per-source triage table: source, classification,
      fact moved, knowledge section, evidence line) and `references/TRIAGE.md` (what counts as a fact change,
      the asymmetry rule, the "read the runtime path first" rule from RULES.md, the RULES.md exact-case rule).
  - **Logging:** the skill relays each tool's verdict line and writes the sync log at
    `provenance/sync-log/<YYYY-MM-DD>-<line>-<tag>.md`.
  - **Check:** `tests/test_maintainer_skill.py` asserts frontmatter shape, that every `allowed-tools` Bash rule
    names one script (ADR 0035), no bare `git *`, and that every referenced tool exists.
  - **Files:** .claude/skills/dgf-sync/SKILL.md, .claude/skills/dgf-sync/references/SYNC-LOG-FORMAT.md,
    .claude/skills/dgf-sync/references/TRIAGE.md, provenance/sync-log/README.md, tests/test_maintainer_skill.py

- [x] **Task 8: The scheduled watcher.** (depends: 4, 7)
  - **Deliverable:** `tools/dgf_lines_watch.sh <dgf-root>`.
    1. Runs `dgf_lines.py status --fetch --json "$DGF_LINES_CACHE/last-status.json"`.
    2. Exit 0 → done.
    3. Exit 2 → prints the summary. With `DGF_SYNC_AUTORUN=1` and `claude` on PATH:
       `git worktree add ../<repo>-dgf-sync-<date> -b chore/dgf-sync-<date> main`, then
       `claude -p "/dgf-sync sync --all"` in it, then `osascript` / `notify-send` when available.
    4. Never commits, pushes or merges.
    5. A lock file prevents overlapping runs.
    6. The real exit code is captured before any pipe — rules/base.md.
  - **Docs:** `docs/dgf-lines.md` — the pack model, the maintainer flow, a launchd plist (weekly, Monday 09:00)
    and a crontab line, the Azure DevOps CI follow-up, and how a developer picks a line.
  - **Logging:** timestamped lines to `$DGF_LINES_CACHE/watch.log`; `DEBUG=1` passes through.
  - **Tests:** `tests/test_dgf_lines_watch.py` — a stub `dgf_lines.py` and `claude` on PATH. Exit 0 → nothing
    runs. Exit 2 without autorun → no worktree. With autorun → the worktree is created on the right branch and
    `claude -p` is invoked with the skill. A held lock → exit 3.
  - **Files:** tools/dgf_lines_watch.sh, docs/dgf-lines.md, tests/test_dgf_lines_watch.py

### Phase 5 — Align the content with DGF (runs the new flow three times)

- [x] **Task 9: Bring `knowledge/` to tag `1.1.16`, then freeze it as `packs/1.1`.** (depends: 3, 4, 7)
  (Done 2026-11-04. The freeze takes `--next`, so it ran as the first step of Task 10's `new-line 1.2`.)
  - **Deliverable:** run `/dgf-sync sync 1.1 --to 1.1.16` against the real checkout. The triage above is the
    expected result; verify every row, do not copy it:
    - **re-read:** schema-families, component-catalogue, json-reader, application-layout;
    - **targeted edits:** process-model, data-model, permissions, naming-conventions, composition-specs — only
      what changed by 1.1.16, since the roles trim, `RoleDisplayName`, Row `backgroundColor` and the tab fields
      are 1.2/1.3;
    - **re-digest:** reference-graph;
    - **full re-vendor**, which picks up `application-sitemap.xsd` if present at 1.1.16.
  - **Validator fixes the new content forces**, each with a test first:
    - `json_validate.enum_accepts` with camelCase string enums that now list values. The runtime still takes an
      integer or any-case name: read the runtime enum converter before encoding it (RULES.md rule 1).
    - Property-name folding against camelCase schemas.
    - XSD discovery and family resolution for a 10th XSD (root `map`, `_application.sitemap`) if it ships at
      1.1.16.
    - `validate_process.py` without the deleted `process-divergence` row.
    - `XSD_LAGS_RUNTIME` for `settings.xsd` with the new enum.
  - Confirm the 1.1.16 notes' "unknown properties rejected" is the MCP's validator and not the runtime reader,
    by reading `ConfigureJsonOptions` and the converter. `json-reader.md`'s "unknown property is a warning"
    stands or changes on that evidence.
  - Regenerate data-model §6's `field-sql-types` with `tools/derive_sql_types.py` against the 1.1.16 cache: the
    samples moved from 429 to 432 `settings.xml`.
  - Settle `run_known_good.py` against the 1.1.16 samples.
  - Update the per-pack expected counts in `tests/test_knowledge.py`.
  - Remove the registry's `legacy` flag.
  - Then `dgf_lines.py freeze 1.1`.
  - **Logging:** the sync log `provenance/sync-log/2026-11-…-1.1-1.1.16.md` with every one of the drifted
    sources classified.
  - **Check:** `check_knowledge_stamps.py` (all packs), `check_drift.py --pack 1.1` against the 1.1.16 cache
    (CLEAN), `run_known_good.py --pack 1.1` (CLEAN), the full unittest suite and node tests.
  - **Files:** knowledge/**, provenance/knowledge/**, packs/1.1/**, provenance/packs/1.1/**, packs/lines.json,
    provenance/lines.json, scripts/lib/json_validate.py, scripts/lib/xsd.py, scripts/lib/family.py,
    scripts/validate_process.py, tools/known-good-exceptions.txt, tests/test_json_validate.py, tests/test_xsd.py,
    tests/test_validate_process.py, tests/test_knowledge.py, provenance/sync-log/*

- [x] **Task 10: Sync `knowledge/` to tag `1.2.0`, then freeze it as `packs/1.2`.** (depends: 9)
  (Done 2026-11-04. The 1.2 freeze ran as the first step of Task 11's `new-line 1.3`.)
  - **Deliverable:** `/dgf-sync new-line 1.2`.
    - Expected: Row `backgroundColor` removed; tab `hidden`/`disabled`/`propertyConverters`; ComboBox
      `emptyOption.position`; DataTable `maxVisible*`/`stickyColumns`; legacy GRID `MaxVisible*`; unknown
      legacy cell keeps the field; `codeViewer`/`comboBox` cell types; `<view totalCount="window">`; the
      DataFetcher `onDataLoadFail` order; the sign-in/deep-link routing — only where a knowledge file states
      the topic.
    - Validator changes only if a test proves one is needed.
    - Settle known-good for 1.2.0; per-pack counts.
    - `freeze 1.2`.
  - **Logging:** its sync log.
  - **Check:** as in Task 9, `--pack 1.2`.
  - **Files:** knowledge/**, provenance/knowledge/**, packs/1.2/**, provenance/packs/1.2/**, packs/lines.json,
    provenance/lines.json, tests/test_knowledge.py, provenance/sync-log/*

- [x] **Task 11: Sync `knowledge/` to tag `1.3.0` — the current line.** (depends: 5, 6, 10)
  - **Deliverable:** `/dgf-sync new-line 1.3`.
    - Expected: `roles`/`deny` trimming (permissions §2.1); `RoleDisplayName` (application-layout §3.1,
      data-model); components inside tabs need `${form.comp}` (reference-graph / composition); `onbeforesave`
      no longer suppresses `onsavescript` (process-model, if stated); the disabled-converter rule; the
      local-stack facts as of 1.3.0. The gotenberg removal and `allowUnauthorizedAccess` are **1.3.1,
      unreleased — not in this pack**.
    - `packs/lines.json` `current: "1.3"`.
    - Settle known-good for 1.3.0; per-pack counts.
    - `dgf_lines.py status` against the real checkout ends with only `TAG_AVAILABLE`-free lines, plus INFO for
      the 1.3.x and 1.2.x unreleased commits.
  - **Logging:** its sync log.
  - **Check:** as in Task 9, `--pack 1.3`; `tools/smoke_install.sh` installs 1.1 and 1.3 projects side by
    side; `tools/check_package.py`; `doctor.py` package mode CLEAN.
  - **Files:** knowledge/**, provenance/knowledge/**, packs/lines.json, provenance/lines.json,
    tests/test_knowledge.py, tools/known-good-exceptions.txt, provenance/sync-log/*

### Phase 6 — Documentation and contracts

- [ ] **Task 12: Docs, repository contracts, release.** (depends: 11)
  - **`tools/check-dual-schema-docs.sh`:**
    - §6 install-and-package: `packs/` is in `files`, `SHIPPED_DIRS` and the package check.
    - §7 stamps: runs `check_knowledge_stamps.py` over all packs.
    - New check: `packs/lines.json` and `provenance/lines.json` agree.
  - **`README.md`:** status, "one DGF line per project".
  - **`docs/getting-started.md`:** `--dgf-version` / `--dgf-line`, switching lines; update the CLI before
    re-running setup, since a 0.2.0 CLI refuses a 0.3.0 receipt.
  - **`docs/guides/upgrade-dgf-version.md`:**
    - add a step: `dgf-factory setup --dgf-version <new>` installs the new line's pack;
    - the doctor's `DGF_LINE_MISMATCH` / `DGF_VERSION_BEHIND_PACK`;
    - replace the "Nobody yet" version-gate row with the doctor's gate;
    - the `KNOWLEDGE:` line now shows `line=`.
  - **`docs/guides/start-a-new-project.md`, `docs/guides/add-functionality.md`:** replace the 1.1.11 stamp
    mentions with the line model.
  - **`docs/pipeline.md`:** the doctor's line findings and the gate.
  - **`docs/dgf-schemas.md`:** 10 XSDs; camelCase schemas.
  - **`docs/architecture.md`:** packs.
  - **`AGENTS.md`:** the structure tree (`packs/`, `provenance/packs/`, `provenance/sync-log/`, `tools/packs.py`,
    `tools/dgf_lines.py`, `tools/restamp_knowledge.py`, `tools/dgf_lines_watch.sh`, `.claude/skills/dgf-sync/`),
    Key Entry Points, Agent Rules (ADR 0036 in the decisions list; 0013 into the superseded list).
  - **Release:** `package.json` version `0.3.0`.
  - **Docs checkpoint:** route `.ai-factory/DESCRIPTION.md` (stamp, delivery) and `.ai-factory/ARCHITECTURE.md`
    (packs folder) to their owner commands (`/aif-docs` checkpoint); `.ai-factory/ROADMAP.md` via
    `/aif-roadmap`.
  - **Check:** `tools/check-dual-schema-docs.sh` CLEAN (it runs the unittest suite, §8);
    `npm test`; `tools/smoke_install.sh`.
  - **Files:** tools/check-dual-schema-docs.sh, README.md, AGENTS.md, docs/getting-started.md, docs/pipeline.md,
    docs/dgf-schemas.md, docs/architecture.md, docs/dgf-knowledge.md, docs/guides/upgrade-dgf-version.md,
    docs/guides/start-a-new-project.md, docs/guides/add-functionality.md, package.json

## Commit Plan

- **Commit 1** (after Tasks 1–4): `feat(dgf-factory): pack-aware knowledge tooling and ADR 0036 — versions from release tags`
- **Commit 2** (after Tasks 5–6): `feat(dgf-factory): setup installs one DGF line per project; doctor checks the line and gates ranged facts`
- **Commit 3** (after Tasks 7–8): `feat(dgf-factory): /dgf-sync maintainer skill and the scheduled DGF line watcher`
- **Commit 4** (after Task 9): `feat(knowledge): align with DGF 1.1.16 and freeze the 1.1 pack`
- **Commit 5** (after Tasks 10–11): `feat(knowledge): DGF 1.2.0 pack; knowledge/ tracks DGF 1.3.0`
- **Commit 6** (after Task 12): `docs(dgf-factory): DGF line packs, the sync flow and setup's line choice; 0.3.0`

## Done means

- `dgf_lines.py status <dgf> --fetch` against the real checkout: 1.1, 1.2, 1.3 each at their newest tag, no
  `DRIFT`; INFO for unreleased commits; `2.x` INFO only.
- `check_knowledge_stamps.py`, `check_drift.py --pack <l>` (against each line's cache) and
  `run_known_good.py --pack <l>` are CLEAN for 1.1, 1.2 and 1.3.
- Two scratch projects installed on different lines hold different stamps.
  - Project on 1.1 with `dgf.version: "1.3.0"` → `DGF_LINE_MISMATCH` with the setup command.
  - After `dgf-factory setup --dgf-version 1.3.0` → clean.
- `tools/check-dual-schema-docs.sh`, the unittest suite and `npm test` pass.
- The watcher, scheduled per `docs/dgf-lines.md`, does nothing on a quiet week. When DGF tags `1.3.1`, it reports
  `TAG_AVAILABLE`, and with autorun it leaves an unmerged `chore/dgf-sync-<date>` branch with a sync log for
  review.

## Follow-ups (not in this plan)

- A CI job against Azure DevOps (needs a PAT and a decision on secrets).
- Row-level `applies:` ranges in machine-read tables.
- Report upstream: `Directory.Build.props` `<Version>` is ClientDebug-only and two releases stale.
- The 1.3.1 fragments disagree on `RenderType Internal`.
