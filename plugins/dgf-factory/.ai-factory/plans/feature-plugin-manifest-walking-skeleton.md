# Implementation Plan: Plugin Manifest & Walking Skeleton

Branch: `feature/plugin-manifest-walking-skeleton` — **not yet created, see `## Branch Blocker`**
Created: 2026-09-21
Base: `main` at `0e28010`

## Original Request

**Plugin Manifest & Walking Skeleton** — `.claude-plugin/plugin.json` plus one loadable skill, so Claude Code can discover the plugin at all

## Branch Blocker

**Do not run `/aif-implement` until this is resolved.**

`git log --oneline main..HEAD` is empty and `git status` shows the whole of milestone 5
("Open Decisions Closed") sitting uncommitted in the working tree: modifications to
`DESCRIPTION.md`, `AGENTS.md`, `README.md`, `docs/blueprint.md`, `docs/dgf-knowledge.md`
and `scripts/check-dual-schema-docs.sh`, plus untracked `docs/adr/`, `.ai-factory/`
artifacts, `.claude/`, `.mcp.json`, `.ai-factory.json` and `skills-lock.json`.

So `/aif-plan` did **not** create a branch. Checking out `main` with that tree would drag
milestone 5's uncommitted work onto the new branch and blur two milestones into one diff.

Before implementing:

1. Commit milestone 5 on `feature/open-decisions-closed` (`/aif-commit`), and merge or
   fast-forward it into `main`.
2. Then cut the branch this plan is named for:

   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/plugin-manifest-walking-skeleton
   ```

The plan filename stem (`feature-plugin-manifest-walking-skeleton`) already matches that
branch name with `/` replaced by `-`, which is how `/aif-implement`, `/aif-verify` and
`/aif-improve` locate a plan. Creating the branch under any other name breaks discovery.

## Settings

- Testing: yes — extend `scripts/check-dual-schema-docs.sh` with a manifest section, and
  ship `doctor.py` as the runtime structural check
- Logging: verbose — `doctor.py` honours `DEBUG=1` / `LOG_LEVEL=debug` with a per-check
  trace, matching `check-dual-schema-docs.sh`
- Docs: yes — mandatory documentation checkpoint at completion, routed through `/aif-docs`
- Scope: installability only. No DGF knowledge base, no dual-schema validators, no spine
  skills. This milestone proves the delivery path works; milestones 7-9 fill it.

## Roadmap Linkage

Milestone: "Plugin Manifest & Walking Skeleton"
Rationale: This plan is the whole of roadmap milestone 6 — it is the first milestone that
produces a loadable plugin rather than a document, and every later milestone ships its
output through the manifest and slice layout established here.

Ticking the milestone in `.ai-factory/ROADMAP.md` is `/aif-roadmap`'s job, not this plan's —
the roadmap has a single owning command.

## Task Ledger Note

`TaskCreate` / `TaskUpdate` are unavailable in this session. The checkbox list under
`## Tasks` is the **single** progress ledger for this plan. `/aif-implement` updates the
checkboxes here and nowhere else.

---

## Design Decisions

Four decisions were taken with the user during planning. They are settled inputs to the
tasks below, not open questions.

### 1. The walking-skeleton skill is `/dgf-doctor`

A diagnostic slice that answers "is this plugin installed correctly, and what can it see?".
It was chosen over starting the spine (`/dgf`) or a knowledge slice (`/dgf-schemas`) because:

- It exercises **every architectural seam** the rest of the corpus depends on —
  auto-discovery, `${CLAUDE_PLUGIN_ROOT}` resolution, a skill calling a script, the
  0/1/2/3 exit-code contract, and the `dgf-gate-result` block — while needing **zero DGF
  facts**, which do not exist yet (milestone 7).
- It does not collide with a later milestone. `/dgf` and `/dgf-plan` belong to "Pipeline
  Spine"; a schema slice belongs to "DGF Knowledge Base". Building either here would move
  scope forward rather than prove the skeleton.
- It stays useful after the skeleton is gone. "The plugin isn't loading" is the first
  support question every plugin gets.

### 2. The doctor checks installability, not completeness

This is the distinction that keeps the exit code meaningful:

| Finding | Severity | Why |
|---|---|---|
| Manifest missing, unparseable, or `name` mismatched | **1 — blocked** | The plugin cannot load |
| A declared component path is absolute, `../`-relative, or missing | **1 — blocked** | Breaks on install |
| A `SKILL.md` has no frontmatter, or `name` ≠ its directory | **1 — blocked** | The skill will not register |
| An absolute or `~/` path in a shipped file | **2 — warning** | Loads, but breaks for other users |
| CRLF line endings in a shipped file | **2 — warning** | Breaks shebangs and heredocs |
| `knowledge/`, `scripts/`, other `dgf-*` slices absent | **INFO only** | Not yet built — milestone 7+ |

Build progress is reported as `INFO` lines that **do not affect the exit code**. A
correct-but-incomplete plugin must exit `0`, otherwise the doctor never reads CLEAN until
milestone 15 and nothing can assert on it in the meantime.

### 3. The plugin ships `dgf-mcp` only

Adding `plugin.json` changes what `.mcp.json` means. Today it is a dev config for this
working directory; the moment a manifest exists, Claude Code auto-loads `./.mcp.json` and
declares its servers to **every user who installs the plugin**.

`filesystem` (`npx @modelcontextprotocol/server-filesystem .`) duplicates the built-in
Read/Glob/Write tools and costs tool-schema tokens in every session — which
`DESCRIPTION.md` § Non-Functional Requirements already argues against under "Token budget".
The hosted `dgf-mcp` is a genuine plugin capability. So `.mcp.json` is trimmed to
`dgf-mcp` alone and ships at the default path, with no `mcpServers` key in the manifest.

### 4. The maintenance script calls the doctor rather than reimplementing it

`scripts/` holds two kinds of thing (`.ai-factory/ARCHITECTURE.md` § Folder Structure):
runtime validators that skills call, and repo-maintenance checks that only contributors
run. `doctor.py` is the first; `check-dual-schema-docs.sh` is the second.

Their manifest checks would otherwise overlap and drift apart. Instead, the shell script's
new section **invokes `doctor.py` and asserts exit 0**, then adds only what is genuinely a
documentation contract: that the reader-facing docs no longer claim the manifest is missing.
One implementation, two callers.

### File placement

`doctor.py` lives at `skills/dgf-doctor/scripts/doctor.py`, not in the plugin-root
`scripts/`. Architecture Key Principle 1: "Promote on the second use, not in anticipation
of it." Exactly one skill calls it today. When `/dgf-verify` wants the gate emitter, that
is the second use and `gate_result.py` moves up to `scripts/lib/`.

---

## Tasks

### Phase 1 — Manifest and MCP surface

- [x] **Task 1 — Create `.claude-plugin/plugin.json`**

  **File:** `plugins/dgf-factory/.claude-plugin/plugin.json` (new)

  The manifest must live in `.claude-plugin/` at the plugin root; Claude Code recognises it
  nowhere else. Mirror the field set of `../doc-coverage-audit/.claude-plugin/plugin.json`
  for marketplace consistency:

  ```json
  {
    "name": "dgf-factory",
    "version": "0.1.0",
    "description": "<50-200 chars: a DGF-aware plan/implement/verify pipeline with deterministic, dual-schema, parity-aware validators>",
    "author": { "name": "dotGov Solutions", "email": "andrian.mamei@dotgovsolutions.net" },
    "homepage": "https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins",
    "license": "UNLICENSED",
    "keywords": ["dgf", "dotgov-framework", "dotnet", "angular", "validation", "json-schema", "xsd"]
  }
  ```

  Constraints:
  - `name` must equal the plugin directory name (`dgf-factory`) and match
    `/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/`
  - `version` is `0.1.0` — initial development, not `1.0.0`. This is milestone 6 of 15 and
    the plugin is not installable from the marketplace yet
  - **Declare no component-path keys.** `skills`, `agents`, `commands`, `hooks` and
    `mcpServers` all have working defaults (`./skills/`, `./agents/`, `./commands/`,
    `./hooks/hooks.json`, `./.mcp.json`). Adding a key that restates its default is noise
    the doctor then has to validate
  - The description must name both schema families or scope itself explicitly — it is
    reader-facing text under the dual-schema rule

  **Logging:** none (a static JSON file).

- [x] **Task 2 — Trim `.mcp.json` to the shipped server set**

  **File:** `plugins/dgf-factory/.mcp.json` (modify)

  Remove the `filesystem` entry; keep `dgf-mcp` unchanged. See Design Decision 3.

  After this change the file is both the dev config for this directory and the plugin's
  shipped MCP declaration — the same file in two roles, which is only safe because the two
  sets are now identical. Add a top-level comment is not possible in JSON, so record the
  dual role in `docs/getting-started.md` under Task 7 instead.

  Verify the hosted server still resolves after the edit; a broken URL here fails for every
  installer, not just locally.

  **Logging:** none (a static JSON file).

  *Depends on: nothing. Independent of Task 1, but both must land before Task 6.*

### Phase 2 — The walking-skeleton slice

- [x] **Task 3 — Create `skills/dgf-doctor/scripts/doctor.py`**

  **File:** `plugins/dgf-factory/skills/dgf-doctor/scripts/doctor.py` (new, executable)

  Write the script **before** the SKILL.md that calls it, so the prompt documents real exit
  codes rather than intended ones.

  Signature: `doctor.py [<plugin-root>]`. With no argument, resolve the plugin root from
  `Path(__file__).resolve().parents[3]` — never from the working directory. A supplied path
  that is not a plugin root (no `.claude-plugin/`) is exit 3.

  Checks, in order, with the severities fixed by Design Decision 2:

  1. **Manifest** — `.claude-plugin/plugin.json` exists, parses as JSON, `name` matches the
     directory name and the kebab-case regex, `version` is semver if present
  2. **Component paths** — every `skills`/`agents`/`commands`/`hooks`/`mcpServers` value, if
     declared, is relative, starts with `./`, contains no `../`, uses forward slashes, and
     resolves to an existing path
  3. **Skill slices** — each `skills/*/` holds a `SKILL.md` whose YAML frontmatter carries
     `name` (equal to its directory), a non-empty `description`, and `allowed-tools`
  4. **Portability** — no `/Users/`, `/home/` or `~/` path in any shipped file
     (`skills/`, `agents/`, `scripts/`, `knowledge/`, `.claude-plugin/`). Exclude `.claude/`
     — the installer-managed `aif-*` corpus is not shipped with the plugin
  5. **Line endings** — no CRLF in any shipped file
  6. **Build progress** — report presence/absence of `knowledge/`, plugin-root `scripts/`,
     `agents/`, and each expected `dgf-*` slice as `INFO`. **Never** let these touch the
     exit code

  Structure, per `.ai-factory/rules/base.md`:
  - One `fail(code, message)` exit path; errors to stderr, report to stdout
  - ANSI colour constants defined once at module top (`RED`, `YELLOW`, `GREEN`, `BOLD`,
    `NC`), disabled when stdout is not a terminal
  - `error()` / `warn()` / `info()` / `trace()` / `section()` helpers matching
    `check-dual-schema-docs.sh` so the two reports read alike
  - Functions under ~30 lines; guard clauses over nesting
  - Pure: reads and reports, never edits the thing it validates, no network
  - Standard library only — no `jsonschema`, no `pyyaml`. Parse the frontmatter with a
    small line scanner; the contract is four flat keys, not arbitrary YAML

  Final verdict line `CLEAN` / `WARNINGS` / `BLOCKED`, then — as the **last** thing on
  stdout — exactly one fenced `dgf-gate-result` block:

  ````
  ```dgf-gate-result
  {
    "schema_version": 1,
    "gate": "verify",
    "status": "pass",
    "blocking": true,
    "blockers": [],
    "affected_files": [],
    "affected_processes": [],
    "affected_components": [],
    "suggested_next": { "command": "/dgf-fix", "reason": "..." }
  }
  ```
  ````

  `status` maps `pass`/`warn`/`fail` from exit `0`/`2`/`1`. Each blocker carries `id`,
  `severity`, `file` and `summary`. Omit `schema_family` — this gate reads no DGF
  configuration, and emitting a family it did not resolve would be exactly the false claim
  the gate contract exists to prevent.

  **Logging:** verbose. `DEBUG=1` or `LOG_LEVEL=debug` emits a `  · ` trace line per check
  with the resolved path and outcome, matching `check-dual-schema-docs.sh`'s `trace()`.
  Default output is the labelled section report plus the summary block.

  *Depends on: Task 1 (there must be a manifest to check).*

- [x] **Task 4 — Create `skills/dgf-doctor/SKILL.md`**

  **File:** `plugins/dgf-factory/skills/dgf-doctor/SKILL.md` (new)

  The first prompt-as-program in this corpus. It sets the house style, so it must follow
  `docs/skill-authoring.md` exactly rather than approximately.

  Frontmatter:

  ```yaml
  ---
  name: dgf-doctor
  description: Check that the dgf-factory plugin is installed correctly and report what it can see. Use for "is dgf-factory working", "plugin not loading", "check plugin install", "dgf doctor".
  allowed-tools: Read Bash(python3 *)
  disable-model-invocation: false
  version: 0.1.0
  ---
  ```

  - No `argument-hint` — the skill takes no arguments
  - `allowed-tools` narrowed to `Bash(python3 *)`, never bare `Bash`
  - `description` carries the literal phrases a user would type; it is the only thing that
    decides whether the skill fires

  Body — numbered steps, resumable, with state on disk not in context:

  - **Step 1: Run the structural check.**
    ```bash
    python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-doctor/scripts/doctor.py"
    ```
    `${CLAUDE_PLUGIN_ROOT}` always, never an absolute or working-directory-relative path.
  - **Step 2: Act on the exit code**, with the contract table from
    `docs/skill-authoring.md` — 0 continue, 1 **STOP** and report findings verbatim without
    repairing, 2 continue and surface every warning, 3 **STOP**, the invocation is wrong.
  - **Step 3: Relay the report.** Pass the script's output through **verbatim**, including
    its `dgf-gate-result` block, and write **nothing after it**. Last block wins: a second
    block authored by the prompt would silently override the deterministic one.
  - `## Execution Rules` with `### DO:` / `### DON'T:`
  - `## Artifact Ownership` — this skill owns no artifact; it reads and reports only
  - `## Critical Rules` — never diagnose by reading files instead of running the script;
    never repair what the script reported; never claim a check the script did not run

  **Logging:** the skill states that `DEBUG=1` yields a per-check trace, and surfaces it
  when the user asks why a check failed.

  *Depends on: Task 3 (the exit codes and output shape must be real before they are documented).*

### Phase 3 — Verification

- [x] **Task 5 — Extend `scripts/check-dual-schema-docs.sh` with a manifest section**

  **File:** `plugins/dgf-factory/scripts/check-dual-schema-docs.sh` (modify)

  Add `check_plugin_manifest()` as section 6, registered in `main()` after
  `check_decision_records`. Per Design Decision 4 it does **not** reimplement the structural
  checks:

  1. Run `python3 "${PLUGIN_ROOT}/skills/dgf-doctor/scripts/doctor.py"`, capture the exit
     code **before** any pipe (`cmd | tail` returns `tail`'s status — the header comment in
     this script already warns about exactly this), map `1` to `error`, `2` to `warn`, `3`
     to `error`, and echo the doctor's own findings so a contributor sees them once
  2. Assert the reader-facing docs no longer claim the manifest is missing — grep
     `README.md`, `AGENTS.md`, `.ai-factory/DESCRIPTION.md` and `docs/getting-started.md`
     for "not yet created", "is not here yet" and "cannot be installed" in the same region
     as `plugin.json`, and `error` on a hit. This is the documentation contract, which is
     what this script is for

  Two existing behaviours to check rather than assume:

  - `owned_markdown()` prunes only `.claude`, `.git`, `node_modules` and `plans`, so the new
    `skills/dgf-doctor/SKILL.md` is now swept into checks 1 and 4. That is wanted — but
    check 4 flags `/Users/` and `/home/` inside fenced blocks, so the SKILL.md must not
    quote an absolute path even as a counter-example
  - The script is `set -eu` and deliberately avoids subshells so `ERRORS`/`WARNINGS`
    accumulate in the parent shell. Read the doctor's output from a here-doc, not a pipe,
    for the same reason the other sections do

  Update the header comment: the name/scope mismatch note already admits the script guards
  more than dual-schema docs — add the manifest contract to that list.

  **Logging:** `trace` lines for the doctor invocation and each doc scanned, gated on
  `DEBUG=1` like every other section.

  *Depends on: Tasks 3 and 4.*

- [x] **Task 6 — Verify discovery with a real local install**

  **File:** none produced — this is a verification gate, and its evidence goes in the
  `/aif-verify` report.

  The milestone's claim is "so Claude Code can discover the plugin at all". Nothing short
  of loading it proves that. `claude --plugin-dir <path>` loads a plugin for one session
  without touching the marketplace, which keeps registration inside milestone 15:

  ```bash
  claude --plugin-dir plugins/dgf-factory -p "/dgf-doctor"
  ```

  Point `--plugin-dir` at `plugins/dgf-factory` specifically — a directory **of** plugins
  loads each child, so aiming at `plugins/` would pull in `doc-coverage-audit` and
  `claude-plugin-creator` too.

  Confirm, and record in the verify report:
  - the plugin loads with no manifest error
  - `/dgf-doctor` appears as an invocable skill
  - invoking it runs the script and returns exit 0 with a `dgf-gate-result` block whose
    `status` is `pass`
  - only `dgf-mcp` is declared — `filesystem` is gone

  **Do not** add `dgf-factory` to `.claude-plugin/marketplace.json`. That is roadmap
  milestone 15 ("Marketplace Release"), and doing it here would ship a plugin with one
  diagnostic skill and no DGF knowledge.

  If discovery fails, **STOP** and report — do not work around it by editing the
  marketplace or by hardcoding a path.

  **Logging:** capture the full session output as verification evidence.

  *Depends on: Tasks 1-5.*

### Phase 4 — Documentation

- [x] **Task 7 — Documentation checkpoint (`/aif-docs`)**

  Four reader-facing documents currently assert the manifest does not exist. Leaving them is
  the drift Task 5's second check exists to catch, so this task is what makes that check
  pass.

  | File | Change |
  |---|---|
  | `README.md` | Line ~12: "not registered in the marketplace and cannot be installed" — now loadable with `--plugin-dir`, still unregistered. Keep those two facts distinct |
  | `AGENTS.md` | § Project Structure tree: add `.claude-plugin/`, `skills/dgf-doctor/`, and the already-existing `scripts/`. § Key Entry Points: add the manifest and the doctor slice. Drop `plugin.json` from the "Not yet created" line |
  | `.ai-factory/DESCRIPTION.md` | § Current State: move `.claude-plugin/plugin.json` from "Not yet created" to the inventory; note the skeleton slice |
  | `docs/getting-started.md` | § What is already here / § What is not here yet — both are now wrong (they also omit the existing `scripts/`). Add a "Load it locally" section with the `--plugin-dir` command from Task 6, and record `.mcp.json`'s dual role from Task 2 |

  Then re-run the maintenance check and require a clean or warnings-only result:

  ```bash
  bash scripts/check-dual-schema-docs.sh
  ```

  Every edited document stays under the existing contracts: both schema families where
  schemas are mentioned, no absolute paths in link targets or fenced blocks, `docs/schemas/`
  never cited as the DGF schema location without its qualifier.

  **Logging:** report the check script's exit code and every finding, not just the verdict.

  *Depends on: Tasks 1-6.*

---

## Commit Plan

Seven tasks, so checkpoints rather than one commit at the end. Each checkpoint leaves the
tree in a state that loads.

| Checkpoint | Tasks | Message |
|---|---|---|
| 1 | 1, 2 | `feat: add plugin manifest and trim shipped MCP surface to dgf-mcp` |
| 2 | 3, 4 | `feat: add /dgf-doctor walking-skeleton slice with structural validator` |
| 3 | 5, 6 | `test: assert plugin manifest contract and verify local discovery` |
| 4 | 7 | `docs: record the manifest and skeleton slice across reader-facing docs` |

Checkpoint 2 is the one that must not be split: a `SKILL.md` referencing a script that does
not exist is a plugin that loads and then fails on first use.

---

## Risks

- **`.mcp.json`'s two roles.** It is now both the dev config for this directory and the
  plugin's shipped declaration. Anyone adding a dev-only server to it ships that server to
  every installer. If a dev-only server is ever needed, split the file per the option
  weighed and rejected in Design Decision 3 rather than quietly adding an entry.
- **The doctor's severity split is a contract, not a preference.** If build-progress INFO
  lines ever start affecting the exit code, `check-dual-schema-docs.sh` section 6 turns red
  for every milestone between now and 15, and contributors will learn to ignore it.
- **First skill sets the house style.** `skills/dgf-doctor/SKILL.md` is the template the
  next twenty slices get copied from. Frontmatter shortcuts taken here propagate.
- **`--plugin-dir` is session-scoped.** A passing Task 6 proves the manifest and slice
  layout are correct; it does not prove marketplace installation works. That claim belongs
  to milestone 15 and must not be made in this milestone's docs.

## Out of Scope

Named explicitly so `/aif-verify` does not read their absence as an omission:

- The `knowledge/` tree and vendored schemas — milestone 7
- Dual-schema, parity-aware validators and the process-semantic checks — milestone 8
- `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`, `/dgf-commit` — milestone 9
- Wiring `dgf-gate-result` across the corpus — milestone 10. This plan emits one block from
  one script; it does not establish the plugin-wide contract
- `agents/`, `hooks/`, `commands/` — no component of those kinds exists yet, and the
  manifest defaults already cover them when they do
- The marketplace entry — milestone 15
