# Implementation Plan: npm CLI delivery for dgf-factory

Branch: none (fast plan; create `feature/npm-cli-delivery` before `/aif-implement`)
Created: 2026-10-26

## Original Request
Deliver dgf-factory as an npm CLI on the AI Factory model, in place of the Claude Code plugin.

## The goal

1. `npm install -g dgf-factory` installs a CLI, `dgf-factory`, on the machine.
2. In a project folder, `dgf-factory setup` installs everything the project needs for the AI harnesses
   the user picks (Claude Code, Codex, Gemini CLI, Cursor, Copilot and the others AI Factory supports):
   - each harness's own artefacts go to that harness's folders: skills (and, where a harness has them,
     subagents and commands) to `.claude/skills/`, `.codex/skills/`, `.gemini/skills/` and so on;
   - everything else dgf-factory needs (validator scripts, `knowledge/`, schemas, skill references
     and templates, the Python requirements) goes inside the project's `.dgf-factory/` folder.
3. From then on the dgf-* skills (`/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`, `/dgf-commit`,
   `/dgf-fix`, `/dgf-evolve`, `/dgf-component`, `/dgf-process`, `/dgf-model`, `/dgf-audit`,
   `/dgf-scaffold`, `/dgf-doctor`) run in each harness that was installed, reading only from the project.
   Nothing reads from the global npm folder at run time.

## The reference implementation

AI Factory does exactly this, and it is installed at `/opt/homebrew/lib/node_modules/ai-factory/`. Read
its `dist/core/agents.js` (the harness registry: configDir, skillsDir, agentsDir, settingsFile,
supportsMcp per harness), `dist/core/installer.js`, `dist/core/transformers/` (per-harness rewriting of
a skill) and `dist/cli/commands/` (init, update, upgrade). Take the harness list and folders from that
registry; do not hard-code a shorter one. This repo's `.ai-factory.json` is a real receipt it wrote.
`docs/plugin-installation-spec.md` (repo root, draft) records where AI Factory's installer falls short.
Carry over its rules that still apply:
- a receipt with source and installed hashes per managed file (INS-10, INS-11);
- never overwrite or delete a file the user edited or owns (INS-12, INS-16);
- preview before writing (INS-08);
- atomic writes, with the receipt written last (INS-22);
- parse files the tool does not own, never replace them (INS-20);
- secrets only as `${VAR}` placeholders (INS-19).

Drop the rules that assume the Claude Code plugin cache.

## Facts the plan must account for (verify each, do not take them on trust)

- `${CLAUDE_PLUGIN_ROOT}` appears 167 times in 18 files under `skills/`, `scripts/` and `knowledge/`,
  including `allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*)` frontmatter. After
  install every one must resolve to a path inside the project's `.dgf-factory/`. Decide whether setup
  rewrites the token at install time (a transformer) or the source changes to a project-relative path.
- Skills call the dgf-mcp tools as `mcp__plugin_dgf-factory_dgf-mcp__*` (11 tool names). That prefix
  exists only for a plugin-provided server. Configured at project level the names change, and differ
  per harness. Setup must register `dgf-mcp` (`https://dgf-mcp.dotgov.uk/mcp`, now in `.mcp.json`)
  in each harness's MCP settings file that supports MCP, and the skills must use matching names.
- `allowed-tools`, `disable-model-invocation` and `argument-hint` are Claude Code frontmatter. Decide
  per harness what is kept, rewritten or dropped (AI Factory's transformers show the pattern).
- `.dgf-factory/` already exists as the project's committed pipeline state at the workspaces root:
  `config.yaml`, `DESCRIPTION.md`, `PLAN.md`, `plans/`, `patches/`, `skill-context/`, `evolutions/`
  (docs/pipeline.md §".dgf-factory/"). Installed runtime files must not mix with that state. Put them
  in a dedicated subfolder (for example `.dgf-factory/runtime/`) with the receipt at
  `.dgf-factory/install.json`, and say which parts are committed and which are gitignored.
- `/dgf` writes `config.yaml` and `DESCRIPTION.md`. `dgf-factory setup` installs files. Keep them
  separate: the CLI never runs the `/dgf` interview, and `/dgf` never installs files.
- The validators need Python 3.9+ with `lxml` and `jsonschema`, hash-pinned in
  `scripts/requirements.txt`. ADR 0015 currently tells users to `pip install --user`. Decide whether
  setup creates a virtual environment inside `.dgf-factory/` (gitignored) and the skills call its
  interpreter, or only reports the command. Either way, setup never installs anything outside the
  project except what `npm -g` itself does.
- `/dgf-doctor` (`skills/dgf-doctor/scripts/doctor.py`) checks the Claude plugin's structure:
  `.claude-plugin/plugin.json`, `SHIPPED_DIRS`, and that every `${CLAUDE_PLUGIN_ROOT}` path exists.
  It must instead check an installed project: the receipt, the files it lists, version drift between
  the receipt and the installed CLI, and the Python dependencies.
- ADR 0012 (no DGF repository paths in shipped files) still holds, now over the npm package's
  `files`. Maintainer material (`docs/`, `tests/`, `tools/`, `provenance/`, `.ai-factory/`,
  `.claude/`) must not ship in the package.
- `tests/` has a unittest suite (`tools/check-dual-schema-docs.sh` section 8 runs it). It must still
  pass, and the installer needs its own tests.

## Decisions the plan must make, each with a recommendation

1. Supersede ADR 0001 (delivery model: an independent Claude Code plugin) with a new ADR. Follow the
   rules in `docs/adr/README.md`: a superseding record restates in full, and nothing is edited in place.
   Also decide whether the Claude Code marketplace entry (`../../.claude-plugin/marketplace.json`) and
   `.claude-plugin/plugin.json` are removed or kept as a second channel. Decide what happens to
   `docs/plugin-installation-spec.md`.
2. The package name and registry. `license` is `UNLICENSED` and the content is internal, so decide
   between public npm `dgf-factory`, a scoped `@andrian-org/dgf-factory`, and GitHub Packages.
   State the install command that results.
3. The CLI's language: Node, to match AI Factory and `npm -g`. The skills' scripts stay Python.
4. Which commands ship first. `setup` is required. Re-running `setup` (or an `update`) must follow
   the receipt rules above. Plan `uninstall` (removes only managed files) and `status` as later tasks
   if they are not in the first cut.
5. Where the harness-neutral source lives. Keep `skills/`, `scripts/` and `knowledge/` as the single
   source, and produce each harness's copy at install time. Never keep one hand-maintained copy per
   harness.

## Constraints from this repo

- Read AGENTS.md, `.ai-factory/rules/base.md`, `docs/architecture.md` and `docs/skill-authoring.md`
  first.
- Determinism before prompting: whatever a script can check (receipt, hashes, path tokens), a script
  checks.
- LF line endings only. Do not edit `aif-*` skills under `.claude/skills/`.
- One shell operation per call.
- Update README.md, AGENTS.md, docs/getting-started.md and docs/pipeline.md for the new install flow.
  Add an "npm delivery" milestone to `.ai-factory/ROADMAP.md`, replacing the "Marketplace Release"
  item.

## Done means

In an empty temp folder:
- `npm pack` and a global install of the tarball give a working `dgf-factory` command;
- `dgf-factory setup` for Claude Code, Codex and Gemini writes each harness's skills and MCP config,
  plus `.dgf-factory/` runtime and receipt, after a preview;
- a second `setup` changes nothing;
- a hand-edited managed file survives a re-run and is reported;
- `/dgf-doctor` is clean;
- `/dgf` runs in Claude Code from the installed copy with no `${CLAUDE_PLUGIN_ROOT}` left anywhere
  under the project;
- the existing unittest suite passes.

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes  # mandatory docs checkpoint in /aif-implement

## Roadmap Linkage
Milestone: "none"
Rationale: Skipped by default (Handoff mode); Task 18 adds the "npm delivery" milestone this plan delivers.

## Verified facts this plan rests on (2026-10-26)

From AI Factory 2.19.0 (`/opt/homebrew/lib/node_modules/ai-factory/`):
- **Harness registry.** `dist/core/agents.js:7-174` has 16 harnesses: claude, cursor, codex, codex-app,
  copilot, gemini, junie, qwen, windsurf, warp, zencoder, roocode, kilocode, antigravity, opencode,
  universal.
  - Each entry has `configDir`, `skillsDir` and `settingsFile`, and some have `agentsDir`.
  - Only claude and codex have `agentsDir`.
  - `gemini` has `settingsFile: null` and `supportsMcp: false`.
  - `codex-app` and `universal` share `.agents/skills` with different transformers, and
    `transformer.js:79-102` refuses to install the two together.
- **Transformers.** These live in `dist/core/transformer.js:47-68` and `transformers/*.js`.
  - The default transformer is the identity.
  - codex and codex-app rewrite `/aif-x` to `$aif-x` in the body only.
  - qwen rewrites `/aif-x` to `/skills aif-x`.
  - kilocode and antigravity flatten only their own `WORKFLOW_SKILLS` list into `workflows/`. None of
    the dgf-* skills is on that list.
  - No transformer touches the `allowed-tools`, `argument-hint` or `version` frontmatter.
- **Install-time tokens.** `dist/core/template.js:3-43` rewrites `{{skills_dir}}`, `{{config_dir}}`
  and four other tokens, in `*.md` files only.
- **AI Factory's installer gaps.** These are the ones this plan must not copy:
  - Its MCP writer handles stdio servers only (`mcp.js:6-27` rejects `url` and `type`).
  - It silently replaces an MCP settings file that is not valid JSON (`fs.js:36-44`).
  - Its writes are not atomic.
  - `update` overwrites a skill the user edited (`installer.js:663-699`).
  - `init` wipes a deselected harness's whole skills directory (`init.js:68-103`).
  - `init` has no guard for a non-interactive terminal.

From this plugin:
- **`${CLAUDE_PLUGIN_ROOT}` appears 174 times in 20 files.** About 163 are in Markdown under `skills/`:
  - all 13 `SKILL.md` files, plus `dgf-plan/references/{PLAN,ULTRA}-FORMAT.md`,
    `dgf-evolve/references/OVERRIDE-FORMAT.md` and `dgf-fix/references/PATCH-FORMAT.md`;
  - `doctor.py`, 4 times;
  - `tests/test_doctor.py` and `tests/test_skill_contracts.py`, 7 times between them.
  - `scripts/`, `knowledge/` and `tools/` have none.

  The forms are:
  - one `allowed-tools` rule per skill;
  - 103 `python3 "${CLAUDE_PLUGIN_ROOT}/…"` command lines;
  - 32 prose paths into `knowledge/`, `references/` and `templates/`.

  About 30 more prose lines name `knowledge/…`, `references/…` or `templates/…` without the token.
- **How scripts find their files.** No script reads the `CLAUDE_PLUGIN_ROOT` environment variable.
  Every path comes from `__file__`:
  - `scripts/lib/knowledge.py:20`, `json_resolve.py:21` and `xsd.py:29` use `parents[2]`;
  - `deps.py:17` uses `parent.parent`;
  - `doctor.py:719`, `dgf-scaffold/scripts/design.py:40` and `check.py:30` use `parents[3]`.

  So the layout `<root>/{scripts,knowledge,skills/<s>/{scripts,references,templates}}` must be
  installed intact.
- **MCP tool names.** `mcp__plugin_dgf-factory_dgf-mcp__*` appears 28 times, all in `allowed-tools`.
  That is 11 distinct tools. Bodies use the bare names.
  - `.mcp.json` declares `dgf-mcp` as `{"type":"http","url":"https://dgf-mcp.dotgov.uk/mcp"}`.
  - The same server registered in a project's `.mcp.json` is exposed as `mcp__dgf-mcp__*`.
- **What the estate checks already skip, and what they don't.**
  - `.dgf-factory/` changes are ignored (`scripts/lib/plan.py:47,436`,
    `scripts/check_change.py:181`).
  - Dot-directories are skipped by the validators' walk (`scripts/lib/cli.py:62`), the inventory
    (`inventory_root.py:62,87`) and root discovery (`locate_plan.py:74`).
  - **Not skipped:** a changed `.claude/skills/dgf-plan/SKILL.md`, `.mcp.json` or
    `.gemini/settings.json`. `plan.classify` gives it `other` with no workspace, and `check_scope`
    reports `CHANGE_OUTSIDE_WORKSPACE` (`check_change.py:206-213`). Re-running setup on a branch would
    therefore fail `/dgf-verify` (Task 6).
- **The scaffold refuses a non-empty folder.** It accepts only `.git/` and `docs/application.json`
  (`skills/dgf-scaffold/scripts/design.py:170-190`, `SCAFFOLD_DIR_NOT_EMPTY`). After
  `dgf-factory setup` the folder also holds `.dgf-factory/`, the harness folders and the MCP files
  (Task 7).
- **Entry scripts are also imported as modules.** Tests do `import verify_gate`
  (`tests/test_verify_gate.py:14`). Four lib modules import `lxml` or `jsonschema` at top level:
  `lib/xsd.py:25`, `family.py:20`, `process_checks.py:32` and `json_validate.py:27`. A venv
  re-exec must run before those imports, and only under `__main__` (Task 5).
- **The interview demo installs as a plugin.**
  - `docs/demo/interview-guide.md:37,175-176` and `docs/demo/prep-checklist.md:105,126,147` use
    `--plugin-dir` and `claude plugin install`.
  - `plans/feature-interview-demo-guide.md` Task 9, the stopwatch rehearsal, is still open and relies
    on `--plugin-dir` (Task 17).
- **Relative links that leave the shipped set.** `knowledge/README.md` links `../docs/…` nine times,
  and `skills/dgf-doctor/SKILL.md:143-144` links `../../docs/…` (Task 15).
- **ADR 0022 names the doctor's manifest check.** ADR 0022:228 says the doctor checks "the installed
  plugin — its manifest, …" (Task 1 erratum).
- **Docs check sections that break.**
  - Section 6 of `tools/check-dual-schema-docs.sh` runs `doctor.py`. That exits `3` without
    `.claude-plugin/` (`doctor.py:724-725`).
  - Section 8 runs `python -m unittest discover -s tests -t .`.
  - Sections 5 and 5b enforce the ADR index, supersession and the blueprint's ANSWERED links.
    `docs/blueprint.md:390` links ADR 0012.
- **Other repo facts.**
  - The repo has no `package.json`, `.npmrc` or `.github/` anywhere.
  - The root `.gitignore` ignores `.venv/` but not `node_modules/`, `*.tgz` or `.dgf-factory/runtime/`.
  - `skills/dgf-scaffold/templates/solution/{obj,bin}/` holds untracked build output.
  - The payload (`skills/`, `scripts/`, `knowledge/`) is about 4.4 MB raw, about 1.1 MB gzipped. The
    schemas make up 3.1 MB of it.
- **Claude-only features the skills use.**
  - `AskUserQuestion` is used in 12 skills.
  - `Agent` with `subagent_type: Explore` is used in `dgf-plan`.
  - `/dgf-*` slash commands are baked into scripts: `scripts/lib/gate_result.py:34` is a validated
    enum, and `verify_gate.py:414-427` uses them.
  - Other harnesses will read these as plain instructions. That is a known limitation, not something
    this plan changes.

## Decisions (recommended; confirm before Task 1)

1. **Delivery (ADR 0029, supersedes 0001).**
   - dgf-factory ships only as an npm CLI.
   - **Remove the Claude Code plugin channel**:
     - `.claude-plugin/plugin.json`;
     - the `dgf-factory` entry in `../../.claude-plugin/marketplace.json`;
     - `"dgf-factory@andrian-org"` in `../../.claude/settings.json`.

     Two channels would mean two layouts for the doctor and the tests. They would also mean a
     duplicate skill registration whenever both are present.
   - Keep `docs/plugin-installation-spec.md` for the marketplace's other plugins. Add a scope note
     that dgf-factory left the marketplace (ADR 0029), and drop its dgf-factory column. The rules this
     plan carries over from the spec are restated in ADR 0029.
   - ADR 0029 restates 0001's still-valid "AI Factory-derived architecture" half in full.
2. **Package and registry.**
   - Publish as `@andrian-org/dgf-factory` on GitHub Packages (`publishConfig.registry:
     https://npm.pkg.github.com`), with the bin name `dgf-factory`.
   - Install with `npm install -g @andrian-org/dgf-factory`, after one `.npmrc` line
     (`@andrian-org:registry=https://npm.pkg.github.com`) and a token with `read:packages`.
   - A public unscoped `dgf-factory` would publish internal content. Publishing itself is not in this
     plan: done means `npm pack` plus a global install of the tarball.
3. **CLI language and dependencies.**
   - Plain ESM Node `.mjs` with **no build step and no runtime dependencies**: `node:util` `parseArgs`,
     `node:readline/promises`, `node:crypto` and `node:fs`.
   - `engines.node >= 18`, as in AI Factory.
   - Tests run with `node --test`. The repo has no compile step, and this keeps it that way.
4. **Layout in a project.**
   - `.dgf-factory/runtime/` mirrors the package payload exactly: `scripts/`, `knowledge/`, and
     `skills/<s>/…` with every file, `SKILL.md` included, untransformed. The untransformed copy is
     what `/dgf-evolve` reads as a target skill's text. This keeps every `parents[N]` lookup working
     unchanged.
   - Each harness gets only `<skillsDir>/<skill>/SKILL.md`, transformed.
   - The receipt is `.dgf-factory/install.json`.
   - **Committed:** the runtime, the harness `SKILL.md` files and the receipt. A clone works without
     npm, as AI Factory's committed skills do.
   - **Ignored:** `.dgf-factory/runtime/.venv/` and `__pycache__/`. A managed file,
     `.dgf-factory/runtime/.gitignore`, ignores them. The project's own `.gitignore` is never edited.
5. **Paths.**
   - The source changes `${CLAUDE_PLUGIN_ROOT}` to a harness-neutral install token,
     `{{dgf_runtime}}`, following AI Factory's `{{…}}` convention.
   - Setup rewrites the token to the project-relative `.dgf-factory/runtime` in every installed `*.md`
     file.
   - Paths are relative because skills run from the project root, which is where the harness found
     `.claude/skills/` and the rest. Absolute paths would break once the project is committed.
   - Tests resolve the token to the source root.
6. **MCP.**
   - The source names tools `mcp__dgf-mcp__*`, the project-level Claude name.
   - Setup writes an **HTTP** `dgf-mcp` entry in each MCP-capable harness's settings file, in that
     harness's own shape.
   - **Gemini** gets `.gemini/settings.json` even though AI Factory marks it `supportsMcp: false`,
     because the request asks for it.
   - Every shape is verified against that harness's documentation before it is written (Task 12). A
     harness whose shape cannot be verified gets a printed manual step instead of a write.
7. **Frontmatter.** It is kept as it is for every harness, as AI Factory does: other harnesses ignore
   Claude's keys. Only the body's invocation form is rewritten (codex, codex-app and qwen).
8. **Python (ADR 0031, supersedes 0015).**
   - Setup creates `.dgf-factory/runtime/.venv` and installs the hash-pinned
     `scripts/requirements.txt` into it. `--no-python` skips this and prints the command instead.
   - Skills keep calling `python3 ".dgf-factory/runtime/scripts/x.py"`.
   - A stdlib-only `scripts/lib/runtime.py` re-executes into `<runtime>/.venv` when that venv exists
     and is not the running interpreter. The same rule picks up the contributor `.venv` at the source
     root.
   - Nothing is ever installed outside the project.
9. **Shipped set (ADR 0030, supersedes 0012).**
   - "Shipped" becomes the npm package payload: `bin/`, `cli/`, `skills/`, `scripts/` and `knowledge/`.
   - `tools/check_package.py` checks it against `npm pack --dry-run --json`.
   - The DGF-path ban is unchanged.
10. **Commands in the first cut.**
    - `setup`. Re-running it is the update, following the receipt rules.
    - `--version` and `--help`.
    - `status` and `uninstall` follow as Phase 6.

## Commit Plan
- **Commit 1** (after tasks 1-3): "docs(adr): deliver dgf-factory as an npm CLI (0029-0031)"
- **Commit 2** (after tasks 4-7): "refactor(skills): harness-neutral runtime token, project venv, install footprint"
- **Commit 3** (after tasks 8-10): "feat(cli): package, harness registry, receipt and atomic writer"
- **Commit 4** (after tasks 11-14): "feat(cli): dgf-factory setup with preview, MCP and Python"
- **Commit 5** (after tasks 15-16): "feat(doctor): check an installed project; package and smoke checks"
- **Commit 6** (after tasks 17-18): "docs: npm install flow; remove the Claude Code plugin channel"
- **Commit 7** (after tasks 19-20): "feat(cli): status and uninstall"

## Tasks

### Phase 1: Decisions

- [x] **Task 1: ADR 0029, delivery as an npm CLI (supersedes 0001).**
  Write `docs/adr/0029-npm-cli-delivery.md` in the format `docs/adr/README.md` sets out:
  - frontmatter `supersedes: [0001]`;
  - a "Supersedes ADR 0001" intro;
  - Context, Decision, Alternatives and Consequences.

  The Decision states the following:
  - Decisions 1-7 and 10 above.
  - The project layout and what is committed or ignored.
  - **The install footprint:** everything under `.dgf-factory/`, plus every path in `install.json`
    `files` and every `mcp[*].file`. The estate checks (Task 6) and the scaffold's empty-folder rule
    (Task 7) both ignore it.
  - The receipt schema:
    ```
    {tool, version, harnesses[], files{<rel>: {source, sourceHash, installedHash}},
     mcp{<harness>: {file, key, entryHash}}}
    ```
    A harness dropped from a later selection keeps its entries until `uninstall`.
  - Hashing: SHA-256. A file is text when it decodes as UTF-8 with no NUL byte. Text is normalised
    with CRLF→LF and the trailing whitespace at end of file trimmed. Anything else is hashed raw.
  - The INS-16 update table, verbatim.
  - Preview before writing, `--yes`, and a non-interactive terminal without `--harness` as exit `3`.
  - Atomic writes, with the receipt written last.
  - Parse-and-stop for files the tool does not own: invalid JSON is reported and never replaced. TOML
    is append-only, and an existing `[mcp_servers.dgf-mcp]` that differs is a reported conflict.
  - The known limitations:
    - `AskUserQuestion`, `Agent` and the `/dgf-*` slash commands baked into scripts, on non-Claude
      harnesses;
    - skills assume the harness was started at the project root;
    - a harness with no verified project-level MCP file, possibly the Codex CLI, gets a printed
      manual step.

  It also restates 0001 §2 (the AI Factory-derived architecture) in full.

  Then make the other edits this ADR requires:
  - In 0001, change `status: superseded-by-0029` and its `date` only.
  - Add the index row and update row 0001 in `docs/adr/README.md`.
  - In `docs/blueprint.md` §"What changes: delivery layer" (lines 219-254), add a dated `Revised`
    sentence pointing at 0029. That table says to drop `agents.ts`, the transformers and the receipts,
    which this ADR now adopts.
  - Add a dated `## Errata` entry to **ADR 0022**: line 228's "its manifest" now reads "its install
    receipt". The doctor checks an installed project (Task 15); the decision is unchanged.

  Logging: none, documentation only. Gate: `bash tools/check-dual-schema-docs.sh` sections 5 and 5b
  pass. Files: `docs/adr/0029-npm-cli-delivery.md`, `docs/adr/0001-*.md` (frontmatter only),
  `docs/adr/0022-*.md` (errata only), `docs/adr/README.md`, `docs/blueprint.md`.

- [x] **Task 2: ADR 0030, shipped files are the npm package payload (supersedes 0012).** (depends on 1)
  Restate 0012 in full.
  - "Shipped" becomes the package payload: `bin/`, `cli/`, `skills/`, `scripts/`, `knowledge/`.
  - In an installed project, it is `.dgf-factory/runtime/` plus the harness `SKILL.md` files.
  - `SHIPPED_DIRS` becomes `("bin", "cli", "skills", "scripts", "knowledge")`.
  - `tools/check_package.py` is the authority on what the tarball contains.
  - Fold in the drifted citation: `doctor.py:47` is now `:79`.
  - A relative link from a shipped file must not leave the shipped set. `knowledge/README.md` links
    `../docs/…` nine times, and `skills/dgf-doctor/SKILL.md:143-144` links `../../docs/…`.

  Then:
  - Set `status: superseded-by-0030` in 0012.
  - Update the index.
  - Move the ANSWERED link at `docs/blueprint.md:390` to 0030 with a `Revised (2026-10-26)` sentence.

  Gate: docs-check 5 and 5b. Files: `docs/adr/0030-shipped-package-payload.md`, `docs/adr/0012-*.md`,
  `docs/adr/README.md`, `docs/blueprint.md`.

- [x] **Task 3: ADR 0031, the validator runtime in a project venv (supersedes 0015).** (depends on 1)
  Restate 0015 in full: Python 3.9+, lxml and jsonschema, the JSON reader read the runtime's way, and
  a missing dependency as exit `3`. Then change these items:
  - Context: the premise "a plugin cannot install its own dependencies" (0015:49-54) no longer holds.
  - Decision 6: `dgf-factory setup` installs the pinned requirements into
    `.dgf-factory/runtime/.venv` and nowhere else. `--no-python` prints the command instead.
  - `scripts/lib/runtime.py` re-executes into that venv, only when the script runs as `__main__`.
  - Decision 8: `doctor.py` and the scaffold's `design.py` stay stdlib-only.

  Then:
  - Set `status: superseded-by-0031` in 0015.
  - Update the index.
  - Add a dated `## Errata` entry in **0024** (lines 84 and 95) and **0027** (line 170). Each records
    that the permission-rule shape now reads `Bash(python3 "{{dgf_runtime}}/scripts/*)`, which the
    install rewrites to `.dgf-factory/runtime`. The decision is unchanged. Do not touch 0021 or 0023:
    a superseded ADR takes no errata.

  Gate: docs-check 5 and 5b. Files: `docs/adr/0031-validator-runtime-project-venv.md`,
  `docs/adr/0015-*.md`, `docs/adr/0024-*.md`, `docs/adr/0027-*.md`, `docs/adr/README.md`.

<!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: Harness-neutral source

- [ ] **Task 4: Replace the plugin token and the plugin MCP names in the skills.** (depends on 1)
  - In every file under `skills/`, replace `${CLAUDE_PLUGIN_ROOT}` with `{{dgf_runtime}}`. That
    covers 13 `SKILL.md` files and 4 reference files.
  - Turn the about 30 bare prose paths (`knowledge/…`, `references/…`, `templates/…`) into
    `{{dgf_runtime}}/…` paths, so they resolve after install.
  - Replace `mcp__plugin_dgf-factory_dgf-mcp__` with `mcp__dgf-mcp__` in the 28 `allowed-tools`
    entries.
  - Reword the prose that assumes a plugin:
    - "reinstall the plugin" becomes "re-run `dgf-factory setup`" in `dgf-doctor`, `dgf-audit`,
      `dgf-component`, `dgf-model`, `dgf-process` and `scripts/verify_gate.py:87`;
    - "the plugin is installed read-only" in `dgf-evolve:23` becomes "the installed runtime is managed
      by `dgf-factory setup`; never edit it";
    - `skills/dgf/SKILL.md:19,216` says `dgf-factory setup` registers the MCP server and `/dgf`
      never writes MCP config.
  - Bump each touched skill's `version` (minor).

  Update the tests:
  - `tests/test_skill_contracts.py`: `SCRIPT_CALL` (line 22), `PLUGIN_PYTHON` (line 173), the
    scaffold rule (line 274) and `LIST_RELEASES` (line 288). Resolve `{{dgf_runtime}}` to the source
    root.
  - Add `test_no_plugin_root_token_remains` and `test_no_bare_runtime_path_in_prose`. The second
    checks for lines naming `knowledge/`, `references/` or `templates/` without the token, with an
    explicit allowlist of workspace-layout paths such as `FM/_COMPONENTS/`.

  The doctor's `SKILL_FRONTMATTER_YAML` check reads only a value's start (`doctor.py:138,427`). An
  `allowed-tools` value starting `Read …` that contains `{{` stays YAML-safe; confirm this with the
  doctor run.

  Logging: none; this is a text change. Gate: `python3 -m unittest discover -s tests -t .` and
  `python3 skills/dgf-doctor/scripts/doctor.py` pass. Files: `skills/*/SKILL.md`,
  `skills/*/references/*.md`, `scripts/verify_gate.py`, `tests/test_skill_contracts.py`.

- [ ] **Task 5: Re-execute into the project venv; the dependency command.** (depends on 3)
  Create `scripts/lib/runtime.py`, stdlib only, with no imports from `lib/` (`lib/__init__.py`
  imports nothing), so `doctor.py` and `design.py` can load it by path.
  - `runtime_root()` is `Path(__file__).resolve().parents[2]`.
  - `venv_python(root)` returns `.venv/bin/python` on POSIX and `.venv\Scripts\python.exe` on Windows,
    or `None` when it is absent.
  - `use_project_venv()` does the following:
    - If that interpreter exists and `Path(sys.executable).resolve()` differs, it re-runs the same
      `argv` under it: `os.execv` on POSIX. On Windows, where `execv` loses the exit code, it uses
      `subprocess.run`, then `sys.exit(returncode)`.
    - `DGF_NO_VENV=1` disables it.
    - It guards against a loop with `DGF_IN_VENV=1`.

  In every entry script in `scripts/*.py` (those with a `__main__` block), the **first lines** are:
  ```python
  if __name__ == "__main__":
      from lib import runtime; runtime.use_project_venv()
  ```
  They come before any other `from lib import …`, because `lib/xsd.py`, `family.py`,
  `process_checks.py` and `json_validate.py` import lxml and jsonschema at top level. They run only
  under `__main__`, because tests import entry scripts as modules (`import verify_gate`). A contract
  test enforces both points.

  Change `scripts/lib/deps.py:install_command()`, and its stdlib duplicate at
  `doctor.py:533-536`:
  - in an installed runtime (`<root>/../install.json` exists), it returns only
    `"<root>/.venv/<bin>/python" -m pip install --require-hashes -r "<root>/scripts/requirements.txt"`,
    and the finding's message adds "or re-run `dgf-factory setup`";
  - otherwise it keeps today's command.

  Update `tests/test_deps.py`, and add `tests/test_runtime.py`. It covers the exec target, no venv,
  the loop guard, `DGF_NO_VENV`, the Windows branch with `os.name` mocked, and that importing an entry
  script does not exec.

  Logging: when `DEBUG=1` or `LOG_LEVEL=DEBUG`, print `[runtime] re-exec into <path>` or
  `[runtime] no project venv at <path>; using <sys.executable>` to stderr. Never print to stdout,
  because scripts' stdout is parsed. Files: `scripts/lib/runtime.py`, `scripts/*.py` (entry
  scripts), `scripts/lib/deps.py`, `skills/dgf-doctor/scripts/doctor.py`, `tests/test_runtime.py`,
  `tests/test_deps.py`, `tests/test_skill_contracts.py`.

- [ ] **Task 6: The change checks ignore the install footprint.** (depends on 1)
  Create `scripts/lib/install_receipt.py`, stdlib only and loadable by path. Its function
  `footprint(root)` returns the set of root-relative POSIX paths:
  - every key of `.dgf-factory/install.json` `files`;
  - every `mcp[*].file`.

  It returns an empty set when there is no receipt. An unreadable receipt is exit `3`
  (`INSTALL_RECEIPT_UNREADABLE`), reported in `lib/report.py`'s table.

  Extend `plan.is_pipeline(rel)` (`scripts/lib/plan.py:436`), or `check_change.own_changes()`
  (`check_change.py:180`), to drop footprint paths. A changed `.claude/skills/dgf-plan/SKILL.md`
  or `.mcp.json` then no longer reaches `check_scope`'s `CHANGE_OUTSIDE_WORKSPACE`
  (`check_change.py:206-213`). The skip is decided by the receipt, not by guessing harness folder
  names.

  The file walks already skip dot-directories (`lib/cli.py:62`, `inventory_root.py:62,87`,
  `locate_plan.py:74`); pin that with regression tests rather than changing the code.

  Add a fixture root, `tests/fixtures/unit/installed-root/`, holding:
  - one workspace;
  - `.dgf-factory/runtime/skills/dgf-scaffold/templates/workspace/…`;
  - `.claude/skills/dgf-plan/SKILL.md`;
  - `.mcp.json`;
  - `.dgf-factory/install.json` listing them.

  `tests/test_installed_root.py` checks that:
  - inventory, audit and the verify gate count only the real workspace;
  - `check_change` on a git fixture that changed the `SKILL.md` and `.mcp.json` reports no
    `CHANGE_OUTSIDE_WORKSPACE`;
  - an unlisted `.claude/other.md` still is reported.

  Logging: `DEBUG` `[check_change.own_changes] footprint skip <path>` per skipped path, and a count at
  INFO under `--verbose`. Files: `scripts/lib/install_receipt.py`, `scripts/lib/plan.py` or
  `scripts/check_change.py`, `scripts/lib/report.py`, `tests/test_installed_root.py`, the fixture.

- [ ] **Task 7: The scaffold's empty folder allows the install footprint.** (depends on 1, 6)
  `skills/dgf-scaffold/scripts/design.py:170-190` treats a folder as empty when it holds only `.git/`
  and `docs/application.json`. After `dgf-factory setup` it also holds `.dgf-factory/`, the harness
  folders and the MCP files, so `SCAFFOLD_DIR_NOT_EMPTY` would refuse every installed folder.
  - Change the check to also skip `.dgf-factory/` and every top-level entry made up only of footprint
    paths. Load `scripts/lib/install_receipt.py` by path, as `design.py` already does for
    `report.py` and `knowledge.py` (`_load`, lines 44-52).
  - A harness folder that also holds a file outside the footprint still counts as not empty, and the
    message names that file.
  - Confirm that `generate.py` writes none of the footprint paths and that `check.py` validates the
    generated workspaces only. A generated root `.gitignore` must not ignore `.dgf-factory/runtime/`,
    which the project commits.
  - Record the rule in ADR 0029, under the install footprint. Add a dated `## Errata` entry to ADR
    0027 §7: "empty" excludes the install footprint, and the decision is unchanged.
  - Update `skills/dgf-scaffold/SKILL.md` and `references/DESIGN-FORMAT.md` where they define an
    empty folder.

  Tests (`tests/test_scaffold_design.py`):
  - an installed empty folder passes `--empty-only`;
  - an installed folder with `.claude/skills/mine/SKILL.md` (not in the receipt) is not empty, and the
    message names it;
  - a folder without a receipt behaves exactly as today.

  Logging: `--verbose` DEBUG lists each entry skipped as footprint. Files:
  `skills/dgf-scaffold/scripts/design.py`, `skills/dgf-scaffold/SKILL.md`,
  `skills/dgf-scaffold/references/DESIGN-FORMAT.md`, `docs/adr/0027-*.md` (errata only),
  `tests/test_scaffold_design.py`.

<!-- Commit checkpoint: tasks 4-7 -->

### Phase 3: CLI core

- [ ] **Task 8: The package skeleton.** (depends on 2)
  Create `package.json` at the plugin root (`plugins/dgf-factory/`):
  - `name: @andrian-org/dgf-factory`;
  - `version: 0.2.0`;
  - `type: module`;
  - `bin: {"dgf-factory": "bin/dgf-factory.mjs"}`;
  - `engines.node: ">=18"`;
  - `license: UNLICENSED`;
  - `publishConfig.registry: https://npm.pkg.github.com`;
  - no `dependencies`;
  - `scripts.test: "node --test tests/cli"`.

  Its `files` allowlist is `bin`, `cli`, `skills`, `scripts`, `knowledge`, with negations for
  `**/__pycache__`, `**/*.pyc` and `skills/dgf-scaffold/templates/solution/{obj,bin}`.

  Create:
  - `bin/dgf-factory.mjs`: a shebang plus `import('../cli/main.mjs')`.
  - `cli/main.mjs`: `parseArgs` dispatch to `setup`, `--version` and `--help`. Unknown commands and
    flags are exit `3`.
  - `cli/log.mjs`: levels DEBUG, INFO, WARN and ERROR, from `LOG_LEVEL` (default INFO) or `DEBUG=1`.
    Everything goes to stderr in the form `[dgf-factory:<area>] message {json}`. User-facing results
    go to stdout.
  - `cli/paths.mjs`: `packageRoot()` from `import.meta.url`.

  Exit codes follow `.ai-factory/rules/base.md`: 0, 1, 2, 3. Add `node_modules/` and `*.tgz` to the
  repo root `.gitignore`.

  Tests (`tests/cli/main.test.mjs`): `--version` prints the package version, unknown flags exit `3`,
  and `--help` lists the commands.

  Logging: DEBUG on the argv parse and the resolved package root. ERROR with the usage text on exit
  `3`. Files: `package.json`, `bin/dgf-factory.mjs`, `cli/main.mjs`, `cli/log.mjs`, `cli/paths.mjs`,
  `../../.gitignore`, `tests/cli/main.test.mjs`.

- [ ] **Task 9: The harness registry and transformers.** (depends on 8)
  `cli/harnesses.mjs` holds all 16 entries from AI Factory 2.19.0 `dist/core/agents.js:7-174`, with
  the same id, displayName, configDir, skillsDir, agentsDir and settingsFile. A comment cites the
  version and lines.
  - Add `mcpFormat` (the id of the writer Task 12 uses) and `transform` (`default`, `codex` or `qwen`).
  - Gemini's `settingsFile` is `.gemini/settings.json`, as in Decision 6.
  - Port AI Factory's collision guard: refuse two harnesses that share a `skillsDir` with different
    transforms, so codex-app with universal is exit `3` and names both.

  `cli/transform.mjs` provides:
  - `renderSkill(harness, text)`: replaces `{{dgf_runtime}}` with `.dgf-factory/runtime` everywhere,
    then applies the harness's invocation rewrite to the body only, never the frontmatter. The
    rewrite is `/dgf(-x)?` to `$dgf…` for codex, and to `/skills dgf…` for qwen. It uses AI Factory's
    boundary regex adapted to `dgf` (`transformer.js:42`).
  - `renderRuntimeFile(rel, bytes)`: for `*.md`, the same token replacement with no invocation
    rewrite; everything else passes through untouched.

  Tests:
  - every harness id renders;
  - no `{{dgf_runtime}}` or `${CLAUDE_PLUGIN_ROOT}` remains in any rendered skill;
  - codex rewrites body invocations but not `allowed-tools`;
  - `~/x/dgf-plan` and `a/dgf-plan` are not rewritten;
  - the collision guard works;
  - a parity test against AI Factory's registry, found only through `npm root -g` with no hard-coded
    path, compares the folder fields. It is skipped when `ai-factory` is not installed.

  Logging: DEBUG per rendered file, with harness, path and the number of token replacements. WARN if a
  skill renders with zero replacements but contains `python3`. Files: `cli/harnesses.mjs`,
  `cli/transform.mjs`, `tests/cli/harnesses.test.mjs`, `tests/cli/transform.test.mjs`.

- [ ] **Task 10: Hashing, the receipt and the atomic writer.** (depends on 6, 8)
  - `cli/hash.mjs` implements the ADR 0029 hashing rule. Its Python twin, `hash_file`, is added to
    `scripts/lib/install_receipt.py` (Task 6) for the doctor.
  - Both are tested against one shared fixture, `tests/fixtures/hash/` (CRLF text, a trailing-newline
    variant, binary, empty, non-UTF-8), with expected digests in `expected.json`. The Node and Python
    suites must each match it.
  - `cli/receipt.mjs` reads and writes `.dgf-factory/install.json`. It validates the schema, and an
    unknown key or a bad type is exit `3` with the path. Keys use POSIX separators. It refuses an
    absolute path or one containing `..`. The Python `footprint()` from Task 6 reads the same
    schema; a shared fixture keeps the two readers in agreement.
  - `cli/fsops.mjs` provides:
    - `writeAtomic(path, bytes, mode)`: write a temp file in the same directory, `fsync`, then
      `rename`;
    - `ensureWithinRoot(root, rel)`: no `..`, no absolute path, no symlinked root, as in AI Factory
      `installer.js:27-38,112-127`;
    - a journal of written and failed paths for the end-of-run report.

  Tests: the hash parity, a receipt round-trip, a rejected path escape, and a simulated rename
  failure that leaves the old file and an unwritten receipt.

  Logging: DEBUG per hash (path, text or binary, digest prefix) and per atomic write. ERROR on a
  failed write, with the path and errno. Files: `cli/hash.mjs`, `cli/receipt.mjs`, `cli/fsops.mjs`,
  `scripts/lib/install_receipt.py`, `tests/fixtures/hash/*`, `tests/cli/hash.test.mjs`,
  `tests/cli/receipt.test.mjs`, `tests/cli/fsops.test.mjs`, `tests/test_install_receipt.py`.

<!-- Commit checkpoint: tasks 8-10 -->

### Phase 4: `dgf-factory setup`

- [ ] **Task 11: The install planner and the preview.** (depends on 9, 10)
  `cli/plan.mjs` provides
  `planInstall({projectRoot, harnesses, receipt, packageRoot}) → actions[]`.
  - **Runtime files.** Every package payload file under `skills/`, `scripts/` and `knowledge/` maps
    to `.dgf-factory/runtime/<same path>`. Add the managed
    `.dgf-factory/runtime/.gitignore` (`.venv/`, `__pycache__/`).
  - **Harness files.** Each harness gets `<skillsDir>/<skill>/SKILL.md`, rendered.
  - Each action is decided by the ADR 0029 table, from `sourceHash` and `installedHash` in the
    receipt against the file on disk:
    - `create`;
    - `update` (template changed, file unedited);
    - `keep-edited`;
    - `conflict` (both changed), which carries a unified diff of the new rendering against the file;
    - `missing` (offer to recreate);
    - `remove` (template gone, file unedited; asks);
    - `unchanged`.
  - A file at a target path that the receipt does not list, and that differs from what would be
    written, is `conflict-unmanaged`. It is never overwritten (INS-12).
  - A harness dropped from the selection is **not** removed by `setup`, and the receipt **keeps** its
    `files` and `mcp` entries and its id in `harnesses`, marked `selected: false`. `uninstall`
    (Task 20) can then find them, and a user's own skills there are never touched.

  `cli/preview.mjs` renders the actions grouped by harness and runtime, with counts per kind and
  every path that will be written or removed. Conflicts come first.

  Tests cover every row of the table, the unmanaged-file case, a dropped harness that keeps its
  receipt entries, and a deterministic ordering of the preview.

  Logging: INFO with the summary counts. DEBUG per action, with path, kind and reason. WARN per
  `keep-edited` or `conflict`. Files: `cli/plan.mjs`, `cli/preview.mjs`, `tests/cli/plan.test.mjs`.

- [ ] **Task 12: The MCP writers, HTTP, per harness.** (depends on 9)
  First verify each harness's remote/HTTP MCP entry shape and file from that harness's current
  documentation, through the docs MCP or WebFetch. Record the table, with source URL and date, in
  ADR 0029 §MCP as a dated erratum or in its body if Task 1 is not committed yet.

  The starting assumptions, all to be verified:

  | Harness | Assumed entry |
  |---|---|
  | claude, universal | `.mcp.json` `mcpServers.dgf-mcp = {type:"http", url}` |
  | cursor | `.cursor/mcp.json` `mcpServers.dgf-mcp = {url}` |
  | copilot | `.vscode/mcp.json` `servers.dgf-mcp = {type:"http", url}` |
  | gemini | `.gemini/settings.json` `mcpServers.dgf-mcp = {httpUrl}` |
  | qwen | `.qwen/settings.json` `mcpServers.dgf-mcp = {httpUrl}` |
  | roocode, kilocode | `mcpServers.dgf-mcp = {type:"streamable-http", url}` |
  | opencode | `opencode.json` `mcp.dgf-mcp = {type:"remote", url}` |
  | codex-app | `.codex/config.toml` `[mcp_servers.dgf-mcp] url = "…"` |

  The remaining harnesses get a printed manual step unless a project-level file is verified. These
  include the codex CLI, which AI Factory marks `settingsFile: null` and `supportsMcp: false`, and
  junie, windsurf, warp, zencoder and antigravity.

  `cli/mcp.mjs` behaves as follows:
  - **JSON:** parse it. A parse error, or a non-object, stops with exit `1`, the path and the parse
    message, and the file untouched. This includes JSONC with comments. An existing identical entry
    is `unchanged`. A different existing `dgf-mcp` entry is `conflict`, never overwritten. Otherwise
    merge the key, preserve every other key, and write atomically with a 2-space indent and a
    trailing newline.
  - **TOML:** append the table only if no `[mcp_servers.dgf-mcp]` header exists. If one exists and
    differs, report a conflict.
  - Record `{file, key, entryHash}` in the receipt.

  Tests: each format, invalid JSON left byte-identical, a conflict, preserved sibling keys, TOML
  append and conflict, and no secret value ever written.

  Logging: INFO per harness (`registered`, `unchanged`, `conflict`, `manual`). ERROR on a parse
  failure, with the file and position. Files: `cli/mcp.mjs`, `tests/cli/mcp.test.mjs`,
  `docs/adr/0029-npm-cli-delivery.md`.

- [ ] **Task 13: The Python step.** (depends on 5, 8)
  `cli/python.mjs`:
  - Find an interpreter: `python3`, then `python` on Windows. Require 3.9 or later via
    `--version`; below that, WARN with the version found.
  - Create `.dgf-factory/runtime/.venv` with `-m venv` if it is absent.
  - Run `<venv python> -m pip install --require-hashes -r .dgf-factory/runtime/scripts/requirements.txt`.
  - Report the exact command on failure. A failure does not undo the installed files, and setup exits
    `2` with a WARN telling the user to re-run setup or run the command.

  `--no-python` skips the step and prints the command. The step never runs pip outside the venv.

  Tests: mock `spawn` for no Python, an old Python, a venv already present, and a pip failure.

  Logging: INFO when the venv is created and the packages are installed. DEBUG with the full command
  lines. ERROR with pip's stderr tail on failure. Files: `cli/python.mjs`,
  `tests/cli/python.test.mjs`.

- [ ] **Task 14: The `setup` command, end to end.** (depends on 11, 12, 13)
  `cli/commands/setup.mjs` runs these steps:
  1. **Resolve the project root.** It is the current directory, or `--root`. Refuse `$HOME` and `/`
     with exit `3`.
  2. **Choose harnesses.** `--harness a,b` validates ids against the registry; an unknown id is
     exit `3` with the list. Otherwise, on a TTY, show a numbered list (`readline/promises`) with the
     receipt's harnesses preselected. Without a TTY and without `--harness`, exit `3` with
     `pass --harness`.
  3. **Plan, then preview.**
  4. **Confirm.** `--dry-run` stops after the preview with exit `0`. `--yes` accepts creates,
     updates and unedited removals; it never accepts conflicts. Otherwise ask `Apply? [y/N]`.
  5. **Apply.** Write the runtime files, the harness files and the MCP entries atomically. Run the
     Python step. Write the receipt last.
  6. **Report.** Print written, unchanged, kept-edited, conflicts and manual steps. Exit `0` when
     clean, `2` when there are conflicts, kept edits or manual steps, `1` on a write failure (listing
     the written and unwritten paths).

  Never write outside `projectRoot` or touch the project's own `.gitignore`. End with the next steps:
  `/dgf` in Claude Code (or `$dgf` in Codex), `/dgf-doctor`, and committing `.dgf-factory/` and the
  harness folders.

  End-to-end tests in a temp directory (`tests/cli/setup.test.mjs`):
  - `--harness claude,codex,gemini --yes` writes:
    - `.claude/skills/*/SKILL.md`, `.codex/skills/*/SKILL.md`, `.gemini/skills/*/SKILL.md`;
    - `.mcp.json` and `.gemini/settings.json`;
    - for Codex, either its verified project MCP file or a `manual` line in the report naming the
      step (Task 12);
    - the runtime and `install.json`.
  - A second run reports all unchanged and changes no byte.
  - Editing `.claude/skills/dgf-plan/SKILL.md`, then re-running with a bumped fake package version,
    keeps the edit and reports it.
  - `grep -r '\${CLAUDE_PLUGIN_ROOT}\|{{dgf_runtime}}'` under the temp project finds nothing.
  - A non-TTY run without `--harness` exits `3`.
  - A run in a folder that is not a git repository behaves the same as in one.
  - All of these run with `--no-python`.

  If the Codex CLI has no verified project-level MCP file, the request's "MCP config for Codex" is
  delivered as a reported manual step. Say so in the README (Task 18).

  Logging: INFO per phase (`plan`, `preview`, `apply`, `python`, `receipt`), WARN per conflict,
  DEBUG of the full action list. Files: `cli/commands/setup.mjs`, `cli/main.mjs`,
  `tests/cli/setup.test.mjs`.

<!-- Commit checkpoint: tasks 11-14 -->

### Phase 5: Doctor, checks and the plugin channel's removal

- [ ] **Task 15: `/dgf-doctor` checks an installed project.** (depends on 5, 10, 14)
  Rework `skills/dgf-doctor/scripts/doctor.py`, keeping it stdlib-only.
  - **Root resolution is unchanged:** `parents[3]` is the runtime root in an install, or the source
    root in this repo.
  - **Replace checks 1-2 (manifest, component paths) with an `install` check.**
    - When `<root>/../install.json` exists, load it via `scripts/lib/install_receipt.py`, loaded by
      path.
    - Every listed file must exist (`INSTALL_FILE_MISSING`, an error).
    - Hash every file. A mismatch is `INSTALL_FILE_EDITED`, a warning.
    - Every selected harness in the receipt must have all 13 skills.
    - Version drift: if `dgf-factory` is on `PATH`, run `dgf-factory --version` with a timeout. A
      difference from the receipt is `INSTALL_VERSION_DRIFT`, a warning naming both versions. A
      missing CLI is INFO only, because a teammate who cloned the project needs no CLI.
    - With no receipt (the source tree), the check is `not-run` with a warning, so the source still
      runs sections 3-6.
  - **Portability (check 4).**
    - In the source tree, `PLUGIN_PATH_DANGLING` becomes `RUNTIME_PATH_DANGLING`, checking
      `{{dgf_runtime}}/…` paths.
    - In an install, it checks the `.dgf-factory/runtime/…` paths in the harness `SKILL.md` files
      **and** in the runtime's own Markdown, resolved against the project root.
    - **New, `LINK_LEAVES_SHIPPED`:** no relative Markdown link may leave the shipped set (ADR 0030).
      Fix the existing offenders in this task, before the check lands:
      - the nine `../docs/…` links in `knowledge/README.md`;
      - `skills/dgf-doctor/SKILL.md:143-144`.

      Replace each with the knowledge file or the DGF docs MCP page that carries the same fact, or
      with plain text naming the maintainer doc.
    - `SHIPPED_DIRS` is set per ADR 0030.
  - **Validator runtime (check 6)** prefers `<root>/.venv` when it exists.
  - Update `skills/dgf-doctor/SKILL.md`: what the doctor checks, and "re-run `dgf-factory setup`" as
    the remedy. `suggested_next` stays `null` (ADR 0022 §8).
  - Rework `tests/test_doctor.py`. The `setUp` copies a source tree without `.claude-plugin/`. Add an
    installed-project fixture built by running the Node `setup` (`--no-python`) into a temp
    directory, skipped when `node` is absent. Assert the six check names and statuses, and that a
    link out of the shipped set blocks.

  Logging: the existing `DEBUG=1` path, adding `[install]` lines per receipt entry. Files:
  `skills/dgf-doctor/scripts/doctor.py`, `skills/dgf-doctor/SKILL.md`, `knowledge/README.md`,
  `tests/test_doctor.py`, `tests/test_known_bad.py` (the `SHIPPED_DIRS` assertion).

- [ ] **Task 16: The package check, the docs-check wiring and the smoke test.** (depends on 8, 15)
  - **`tools/check_package.py`** (maintainer only). It runs `npm pack --dry-run --json` and checks
    the tarball's file list:
    - an allowlist of prefixes: `package.json`, `bin/`, `cli/`, `skills/`, `scripts/`, `knowledge/`;
    - none of `tests/`, `tools/`, `provenance/`, `docs/`, `.ai-factory/`, `.claude/`, `.venv/`,
      `obj/`, `bin/Debug`, `__pycache__`;
    - the `package.json` fields from Task 8.

    It exits 0, 1 or 3 and reports offenders one per line.
  - **`tools/check-dual-schema-docs.sh`.**
    - Section 6 runs `doctor.py` (now valid without `.claude-plugin/`) and `tools/check_package.py`.
      Drop the `plugin.json` wording scan, or retarget it to `package.json`.
    - Section 8 also runs `node --test tests/cli` when `node` is present, and warns otherwise.
    - `owned_markdown()` keeps pruning `node_modules`.
  - **`tools/smoke_install.sh`** checks "done means" end to end without touching the real global
    prefix:
    1. `npm pack`.
    2. `npm install -g --prefix "$TMP/npm" <tgz>`.
    3. `"$TMP/npm/bin/dgf-factory" setup --harness claude,codex,gemini --yes` in `"$TMP/project"`.
    4. A second run, asserting exit `0` and all unchanged.
    5. Edit one `SKILL.md`, re-run, and assert it is kept and reported.
    6. `python3 .dgf-factory/runtime/skills/dgf-doctor/scripts/doctor.py`, which must be exit `0`, or
       `2` with only `INSTALL_FILE_EDITED` from step 5.
    7. Assert there is no `${CLAUDE_PLUGIN_ROOT}` under `$TMP/project`.
    8. **Optional, guarded.** When `claude` is on `PATH`, run
       `cd "$TMP/project" && claude -p "/dgf-doctor"` and assert the output's last
       `dgf-gate-result` block has `status` `pass` or `warn`. Otherwise print `MANUAL: open Claude
       Code in $TMP/project and run /dgf-doctor, then /dgf`.

    One operation per line; stop on the first failure.

  Logging: each tool prints labelled sections and a final `CLEAN`, `WARNINGS` or `BLOCKED` line, as in
  `.ai-factory/rules/base.md` §Logging. Files: `tools/check_package.py`,
  `tools/check-dual-schema-docs.sh`, `tools/smoke_install.sh`.

<!-- Commit checkpoint: tasks 15-16 -->

- [ ] **Task 17: Remove the Claude Code plugin channel, and switch the demo.** (depends on 14, 15, 16)
  **Precondition:** `plans/feature-interview-demo-guide.md` Task 9 (the stopwatch rehearsal, which
  relies on `--plugin-dir`) is done, or the demo is switched in this task, below. Ask the user which
  before starting.
  - Delete `.claude-plugin/plugin.json` and the directory.
  - Remove the `dgf-factory` entry from `../../.claude-plugin/marketplace.json`.
  - Remove `"dgf-factory@andrian-org"` from `../../.claude/settings.json` `enabledPlugins`. Read the
    file first and edit only that key.
  - Keep `.mcp.json` at the plugin root as the contributor's dev config, and say so in AGENTS.md. The
    shipped MCP declaration now lives in `cli/mcp.mjs`.
  - In `../../docs/plugin-installation-spec.md`, add a scope note: dgf-factory is delivered by npm
    per ADR 0029, and the spec governs the marketplace's other plugins. Remove dgf-factory from §5,
    and the mentions of dgf-factory from INS-07 and INS-10.
  - In `../../README.md`, remove the dgf-factory install lines (24-26) and its `enabledPlugins` example
    (63-66). Its plugins-table row (79) points to the plugin's README for the npm install.
  - **Switch the interview demo to the CLI.**
    - In `docs/demo/prep-checklist.md:105,126,147` and `docs/demo/interview-guide.md:37`,
      `claude --plugin-dir "$PLUGIN"` becomes `dgf-factory setup --harness claude --yes` in `$APP`,
      run before `/dgf-scaffold`, followed by plain `claude`.
    - `interview-guide.md:90`: `ls -A` now shows `.dgf-factory`, `.claude` and `.mcp.json` beside
      `.git` and `docs`. Reword the line: "empty except the install".
    - `interview-guide.md:175-176`: the "where to get it" lines become the npm install.
    - `cheat-sheet.md` follows the same changes.

  Gate: `bash tools/check-dual-schema-docs.sh` is clean, and `bash tools/smoke_install.sh` passes.
  Files: `.claude-plugin/`, `../../.claude-plugin/marketplace.json`, `../../.claude/settings.json`,
  `../../docs/plugin-installation-spec.md`, `../../README.md`, `docs/demo/interview-guide.md`,
  `docs/demo/prep-checklist.md`, `docs/demo/cheat-sheet.md`.

- [ ] **Task 18: Documentation and the roadmap.** (depends on 17) Route the docs through `/aif-docs`.
  - **README.md:** a Quick Start with the `.npmrc` line, `npm install -g @andrian-org/dgf-factory`,
    `cd <workspaces root>`, `dgf-factory setup`, commit, then `/dgf`. Add:
    - the teammate path: clone, and if `.dgf-factory/runtime/.venv` is absent, run
      `dgf-factory setup` or the printed command;
    - a contributor path: `node bin/dgf-factory.mjs setup --harness claude --root <tmp project>`;
    - a per-harness MCP note covering any manual step (Task 12).

    Fix the "dotgov marketplace" mentions.
  - **AGENTS.md:** the tech stack (Node CLI, no dependencies), the structure tree (`bin/`, `cli/`,
    `package.json`, `tests/cli/`, the tools), key entry points, the ADR 0029-0031 rule text,
    and the ADR 0012 to 0030 rule.
  - **docs/getting-started.md:** prerequisites (Node 18+, Python 3.9+), installing, setup, the venv,
    and loading for contributors. Remove the stale "marketplace entry does not exist" lines (5-7 and
    271-275).
  - **docs/pipeline.md** §".dgf-factory/": add `runtime/` and `install.json` (committed) and
    `runtime/.venv` (ignored), with `dgf-factory setup` as their single writer. Add the install
    footprint that the change checks and the scaffold ignore.
  - **docs/architecture.md** (lines 26, 87-93, 128) and **docs/skill-authoring.md** (lines 31, 42,
    260): `{{dgf_runtime}}` replaces `${CLAUDE_PLUGIN_ROOT}`, and `mcp__dgf-mcp__*`. Entry scripts
    open with the guarded `use_project_venv()`.
  - **Through their owning commands:**
    - `.ai-factory/DESCRIPTION.md` via `/aif`: the delivery model, packaging, the ADR count (now 31),
      and the stale marketplace line 97.
    - `.ai-factory/ARCHITECTURE.md` via `/aif-architecture`.
    - `.ai-factory/rules/base.md` via `/aif-rules`: the module-structure and path rule at lines
      29-40.
    - `.ai-factory/ROADMAP.md` via `/aif-roadmap`: replace "Marketplace Release" with
      **"npm delivery"**, which this plan delivers. Move its `Bash(git *)` question to Follow-ups.
      Add follow-ups for:
      - publishing to GitHub Packages;
      - harness-specific invocation in script output;
      - `AskUserQuestion` and `Agent` on non-Claude harnesses;
      - Codex CLI MCP, if it stayed a manual step.

  Gate: docs-check is clean. Files: as listed.

<!-- Commit checkpoint: tasks 17-18 -->

### Phase 6: Later commands

- [ ] **Task 19: `dgf-factory status`.** (depends on 14)
  A read-only command:
  - It loads the receipt and prints each harness (selected or dropped), the version, and the counts of
    unchanged, edited and missing files and MCP entries.
  - It prints drift between the receipt and the CLI version.
  - `--json` gives machine output.
  - Exit `0` clean, `2` with drift or edits, `3` with no receipt.

  Tests in `tests/cli/status.test.mjs`. Logging: DEBUG per checked file. Files:
  `cli/commands/status.mjs`, `cli/main.mjs`, `tests/cli/status.test.mjs`.

- [ ] **Task 20: `dgf-factory uninstall`.** (depends on 14)
  - `--harness a,b` removes only those harnesses, dropped ones included; with no flag, it removes all.
  - It previews, then removes only managed files whose hash still matches. Edited files are kept and
    reported.
  - It removes the `dgf-mcp` key only when it still equals the receipt's `entryHash`. JSON is parsed
    and the rest of the file is preserved; for TOML, only our table is removed.
  - It removes empty directories it created.
  - It removes `.dgf-factory/runtime/` only when everything is uninstalled.
  - It updates the receipt, or deletes it at the end.
  - It **never** touches `config.yaml`, `DESCRIPTION.md`, `plans/`, `patches/`, `skill-context/`,
    `evolutions/` or `baseline.json`.
  - It prints what is left behind.
  - `--yes` and `--dry-run` behave as in `setup`.

  Tests: a partial uninstall, an edited file kept, an MCP sibling key preserved, and the pipeline
  state untouched. Logging: INFO per removed path, WARN per kept path. Files:
  `cli/commands/uninstall.mjs`, `cli/main.mjs`, `tests/cli/uninstall.test.mjs`, and the README
  uninstall section.

<!-- Commit checkpoint: tasks 19-20 -->
