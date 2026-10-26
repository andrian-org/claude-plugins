---
id: 0029
title: Delivered as an npm CLI that installs into a project, with an AI Factory-derived architecture
status: accepted
date: 2026-10-26
deciders: [Andrian Mamei]
supersedes: [0001]
tags: [delivery, architecture, provenance, install]
---

# 0029 — Delivered as an npm CLI that installs into a project, with an AI Factory-derived architecture

Restates [ADR 0001](0001-independent-plugin-with-ai-factory-derived-architecture.md) in full. One
half changes: **delivery.** `dgf-factory` stops being a Claude Code plugin in the marketplace. It becomes
an npm CLI that copies what a project needs into that project, for every AI harness the user picks, as
AI Factory does. The other half — the pipeline architecture derived from AI Factory, and the independence
from any other DGF agent-tooling effort — is unchanged.

## Context

**What ADR 0001 decided, and why it no longer fits.** ADR 0001 (2026-09-21) shipped `dgf-factory`
"as an independent Claude Code plugin in the `dotgov` marketplace" through
`.claude-plugin/plugin.json` and an entry in `../../.claude-plugin/marketplace.json`
(`0001-…:37-48`). On **2026-10-26** the user decided the delivery instead:

> i want to install this plugin with `npm install -g dgf-factory`. after that inside a folder in
> terminal run `dgf-factory setup`, this command must install all necessary skills, commands, scripts,
> etc. inside the folder for claude, gemini, codex, other LLM providers. … everything that this plugin
> need will be inside installation folder `.dgf-factory`, except skills, commands, and other claude code
> or other ai-harness artefacts.

ADR 0001's reversal trigger — a named requirement to share a skill corpus or install path with another
dotGov effort (`0001-…:120-123`) — is not this. This is a change of channel, decided by its owner, and
recorded here rather than argued.

**What the plugin channel ties to Claude Code**, read on 2026-10-26:

- `${CLAUDE_PLUGIN_ROOT}` appears in every `SKILL.md`: one `allowed-tools` rule per skill, 103
  `python3 "${CLAUDE_PLUGIN_ROOT}/…"` command lines, and 32 prose paths into `knowledge/`, `references/`
  and `templates/`. No script reads it: every path in `scripts/` is derived from `__file__`
  (`scripts/lib/knowledge.py:20`, `json_resolve.py:21`, `xsd.py:29`, `deps.py:17`, and `parents[3]` in
  `skills/dgf-doctor/scripts/doctor.py:719`, `skills/dgf-scaffold/scripts/design.py:40`, `check.py:30`).
- The dgf-mcp tools are granted as `mcp__plugin_dgf-factory_dgf-mcp__*`, 28 times in `allowed-tools`.
  That prefix exists only for a server a plugin declares. The same server in a project's `.mcp.json` is
  `mcp__dgf-mcp__*`.
- `/dgf-doctor` checks a plugin manifest (`doctor.py:263-326`) and exits `3` without `.claude-plugin/`
  (`doctor.py:724-725`).

**What AI Factory does**, read from AI Factory 2.19.0 under `<npm root -g>/ai-factory/` on 2026-10-26:

- A registry of 16 harnesses, each with a `configDir`, `skillsDir` and `settingsFile`
  (`dist/core/agents.js:7-174`). Two of them, `codex-app` and `universal`, share `.agents/skills` with
  different transformers, and the installer refuses them together (`dist/core/transformer.js:79-102`).
- Per-harness transformers that rewrite a skill's body only: `/aif-x` becomes `$aif-x` for Codex and
  `/skills aif-x` for Qwen (`dist/core/transformers/codex.js`, `qwen.js`). No transformer touches
  `allowed-tools`, `argument-hint` or `version`.
- Install-time tokens, `{{skills_dir}}` and five more, rewritten in `*.md` files only
  (`dist/core/template.js:3-43`).
- A receipt, `.ai-factory.json`, holding a `sourceHash` and an `installedHash` per installed skill.

It also has gaps this decision must not copy, each read from the same source:

- the MCP writer accepts stdio servers only, and rejects `url` and `type` (`dist/core/mcp.js:6-27`), but
  dgf-mcp is an HTTP server;
- an MCP settings file that is not valid JSON is read as `{}` and overwritten (`dist/utils/fs.js:36-44`);
- writes are not atomic;
- `update` overwrites a skill the user edited, after a warning (`dist/core/installer.js:663-699`);
- re-running `init` without a harness deletes that harness's whole skills directory, the user's own
  skills included (`dist/cli/commands/init.js:68-103`);
- `init` has no guard for a terminal that cannot answer questions.

The marketplace's draft installation specification (`../../docs/plugin-installation-spec.md`,
2026-10-05) catalogues the same gaps as requirements INS-01 to INS-25. Its model assumed the Claude Code
plugin cache, so its rules about scope and the cache do not carry over. Its rules about the receipt,
user edits, previews, atomic writes and files the tool does not own do, and are restated below.

**`.dgf-factory/` already exists** in an estate, as the pipeline's committed state at the workspaces
root: `config.yaml`, `DESCRIPTION.md`, `PLAN.md`, `plans/`, `patches/`, `skill-context/`, `evolutions/`
(`docs/pipeline.md` §".dgf-factory/"). Every estate check ignores it (`scripts/lib/plan.py:47,436`,
`scripts/check_change.py:181`).

## Decision

**`dgf-factory` ships as an npm CLI. `dgf-factory setup`, run in a project, installs the skills into
each chosen harness's own folder and everything else into `.dgf-factory/runtime/`, records what it wrote
in a receipt, and never overwrites a file the user changed. Its pipeline architecture derives from
AI Factory, and it depends on no other DGF agent-tooling effort.**

### 1. Delivery

- **One channel.** The Claude Code plugin channel is removed: `.claude-plugin/plugin.json`, the
  `dgf-factory` entry in `../../.claude-plugin/marketplace.json`, and `"dgf-factory@andrian-org"` in
  `../../.claude/settings.json`. Two channels would mean two layouts for the doctor and the tests, and a
  second registration of every skill name wherever both are present.
- **The package.** `@andrian-org/dgf-factory`, published to GitHub Packages
  (`publishConfig.registry: https://npm.pkg.github.com`), with the bin `dgf-factory`. The content is
  internal (`license: UNLICENSED`), and an unscoped name on the public registry would publish it. A
  developer adds `@andrian-org:registry=https://npm.pkg.github.com` to `~/.npmrc` with a token that has
  `read:packages`, then runs `npm install -g @andrian-org/dgf-factory`.
- **The CLI.** Plain ESM Node (`.mjs`), `engines.node >= 18`, **no build step and no runtime
  dependencies**: `node:util` `parseArgs`, `node:readline/promises`, `node:crypto`, `node:fs`. Tests run
  with `node --test`. The skills' scripts stay Python.
- **The first commands.** `setup` — re-running it is the update — plus `--version` and `--help`.
  `status` and `uninstall` follow.
- **`/dgf` is not setup.** The CLI installs files and never runs the `/dgf` interview. `/dgf` writes
  `config.yaml` and `DESCRIPTION.md` and never installs anything.

### 2. The layout in a project

| Path | What | Committed |
|---|---|---|
| `.dgf-factory/runtime/` | the package payload, mirrored exactly: `scripts/`, `knowledge/`, `skills/<s>/…` with every file, `SKILL.md` included | yes |
| `.dgf-factory/runtime/.gitignore` | a managed file ignoring `.venv/` and `__pycache__/` | yes |
| `.dgf-factory/runtime/.venv/` | the validators' Python environment ([ADR 0031](0031-validator-runtime-project-venv.md)) | no |
| `.dgf-factory/install.json` | the receipt | yes |
| `<skillsDir>/<skill>/SKILL.md` | one rendered `SKILL.md` per skill, per chosen harness | yes |
| the harness's MCP settings file | a `dgf-mcp` entry, merged into the file | the project's choice |

The runtime keeps the source layout because three scripts find their siblings by position
(`parents[3]`). It keeps every `SKILL.md` untransformed because `/dgf-evolve` reads a target skill's
text there. A clone works without npm, as AI Factory's committed skills do. The project's own
`.gitignore` is never edited.

**The install footprint** is everything under `.dgf-factory/`, plus every path in `install.json` `files`
and every `mcp[*].file`. The change checks ignore it (`scripts/lib/install_receipt.py` `footprint()`),
and `/dgf-scaffold` counts a folder holding only the footprint as empty.

### 3. Sources and rendering

- **One source.** `skills/`, `scripts/` and `knowledge/` in this repository are the only source. Each
  harness's copy is produced at install time; no copy per harness is kept by hand.
- **The runtime token.** The source writes `{{dgf_runtime}}` where it wrote `${CLAUDE_PLUGIN_ROOT}`,
  following AI Factory's `{{…}}` convention. Setup rewrites it to the project-relative
  `.dgf-factory/runtime` in every installed `*.md` file. Relative, because a skill runs from the project
  root, where the harness found its skills folder; an absolute path would break once committed.
- **MCP tool names.** The source grants `mcp__dgf-mcp__*`, the name a project-level server has in
  Claude Code.
- **Frontmatter is kept** for every harness, as AI Factory keeps it; other harnesses ignore Claude Code's
  keys. Only the body's invocation form is rewritten: `/dgf-x` becomes `$dgf-x` for `codex` and
  `codex-app`, and `/skills dgf-x` for `qwen`.
- **The harness list** is AI Factory 2.19.0's 16 entries, with the same folders. `gemini` additionally
  gets `.gemini/settings.json` for MCP. Two harnesses that share a `skillsDir` with different
  transforms are refused together.

### 4. The receipt and hashing

```
{tool, version, harnesses[{id, selected}],
 files{<rel>: {source, sourceHash, installedHash}},
 mcp{<harness>: {file, key, entryHash}}}
```

- Keys are project-relative POSIX paths. An absolute path, or one containing `..`, is refused.
- `sourceHash` is the hash of the package file; `installedHash` of the file as written.
- A harness dropped from a later selection keeps its entries, with `selected: false`, until `uninstall`.
- **Hashing** is SHA-256 per file. A file is text when it decodes as UTF-8 and holds no NUL byte; text is
  normalised by turning CRLF into LF and trimming trailing whitespace at the end of the file. Anything
  else is hashed raw. The Node CLI and the Python doctor implement it twice and are held to one shared
  fixture.

### 5. Update: decided per file

| Template changed (`sourceHash`) | File edited (`installedHash`) | Action |
|---|---|---|
| no | no | leave it |
| yes | no | rewrite it, and record both new hashes |
| no | yes | keep the user's file, and report it as edited |
| yes | yes | keep the user's file, and report a conflict: name the file and show the new template's diff |
| file missing | — | report it; recreate it only if the user agrees |
| template removed from the package | — | report it; delete the file only if it is unedited and the user agrees |

A file at a target path that the receipt does not list, and that differs from what would be written, is
an unmanaged conflict: never overwritten. A file is rewritten over the user's edits only when the user
names it and says to.

### 6. Writing

- **Preview first.** Setup lists every file it will create, change or remove, conflicts first, and writes
  only after the user agrees. `--dry-run` stops after the preview. `--yes` accepts creates, updates and
  unedited removals, never a conflict.
- **No silent prompts.** A terminal that cannot answer questions, without `--harness`, is a usage error
  (exit `3`).
- **Atomic writes, receipt last.** Each file is written to a temporary file in the same directory and
  renamed into place. The receipt is written last, so it lists only files fully written. A failure
  reports what was and was not written, and the next run resumes from the receipt.
- **Files the tool does not own are parsed, never replaced.** A JSON settings file that does not parse,
  or is not an object, stops setup with its path; the file is untouched. A TOML file is only appended to,
  and an existing `[mcp_servers.dgf-mcp]` that differs is a reported conflict.
- **Nothing outside the project** is written, apart from what `npm -g` itself installs.
- **Secrets** appear only as `${VAR}` placeholders. dgf-mcp needs none.

### 7. MCP

Setup writes an HTTP `dgf-mcp` entry (`https://dgf-mcp.dotgov.uk/mcp`) into each chosen harness's
MCP settings file, in that harness's own shape. Each shape is verified against the harness's own
documentation before it is written, and recorded in this ADR. A harness with no verified project-level
file gets a printed manual step instead of a write.

### 8. Known limitations

- `AskUserQuestion` (12 skills) and `Agent` with `subagent_type: Explore` (`/dgf-plan`) are Claude Code
  tools. Other harnesses read them as plain instructions.
- The scripts print `/dgf-*` commands (`scripts/lib/gate_result.py:34`, `scripts/verify_gate.py`).
  A Codex user reads `/dgf-fix` where they type `$dgf-fix`.
- Skills assume the harness was started at the project root.

### 9. The architecture: derived from AI Factory, depending on nothing else

Restated from ADR 0001 §2, unchanged. The pipeline architecture is carried over from AI Factory 2.18.1.
Named explicitly, from [`docs/blueprint.md`](../blueprint.md) §"What stays: all five core ideas":

1. **Single-writer artifact ownership** — every artifact has exactly one owning command; everything else
   treats it as read-only input.
2. **Planner/executor split** — `index.md` + phase-file bundles, with checkboxes living only in
   `index.md`, and an executor forbidden from re-deciding architecture.
3. **Machine-readable gate blocks** — a final fenced `dgf-gate-result` block with `schema_version: 1`
   and last-block-wins parsing.
4. **Worktree-isolated parallel workers** under a coordinator.
5. **The learning loop** — fix → patch → evolve → skill-context override.

Plus config-as-relocation, warmup/resume, the archive lifecycle and the grounded gate.

**This is a derivation, not a dependency.** The `aif-*` corpus under `.claude/` is installer-managed
reference material used to *build* this tool; it is not shipped with it. Nothing at runtime requires
AI Factory to be installed. Now that the delivery mechanism is AI Factory's as well, the installer's
registry, transformers and receipt are re-implemented here, not imported.

`dgf-factory` takes **no dependency** on any other DGF agent-tooling effort: no shared artifacts, no
shared skill corpus, no obligation to track another repository's ADR series, and no requirement that
another tool be installed for this one to work. Other repositories' ADRs are not constraints on this
tool. Where their reasoning is useful it may be read, but it is not binding and is not cited as
authority.

## Alternatives considered

- **Keep the Claude Code plugin, add npm as a second channel.** Keeps the marketplace install for Claude
  Code users. Rejected: two layouts for the doctor and the tests, and duplicate skill registrations
  wherever both are installed.
- **Change the source to literal `.dgf-factory/runtime/…` paths instead of a token.** Simpler rendering.
  Rejected: the contract tests resolve every script call against the source tree, and a literal path
  ties the source to one install layout.
- **Install the skills' extra files into each harness folder.** Mirrors AI Factory, which copies whole
  skill directories. Rejected: `scripts/` and `knowledge/` must sit beside `skills/` for the `parents[N]`
  lookups, and copying `references/` and `templates/` once per harness only duplicates them.
- **Publish `dgf-factory` unscoped on the public registry**, matching the user's literal command.
  Rejected: it would publish internal content. The bin name, and so `dgf-factory setup`, is the same.
- **Build the CLI on inquirer and commander**, as AI Factory does. Rejected: the CLI needs a list prompt
  and an argument parser, which Node's standard library provides, and every dependency is one more
  thing to pin and audit.
- **Ship as an extension of a generic agent-factory pipeline**, or **vendor an existing DGF skill
  corpus.** Restated from ADR 0001: both make this tool's roadmap depend on another effort, and the
  second imports decisions whose evidence this repository does not hold.

## Consequences

### Positive

- **Every harness AI Factory supports can run the pipeline**, from one source.
- **A project is reproducible from its own commit.** The runtime, the rendered skills and the receipt are
  committed; a teammate who clones needs no CLI, only Python for the virtual environment.
- **Edits survive an update.** Every file is decided against the receipt, and nothing the user changed is
  overwritten without being named.
- **The validators' dependencies install themselves**, inside the project ([ADR 0031](0031-validator-runtime-project-venv.md)).
- **Evidence stays self-contained.** Every fact this tool relies on is sourced from first-party DGF.

### Negative

- **The marketplace install is gone.** A Claude Code user who installed the plugin must uninstall it and
  run `dgf-factory setup` in each project.
- **A Node toolchain is now required** to install, beside Python to validate.
- **About 4.4 MB is committed into every project**, mostly the vendored schemas, and every update of the
  CLI shows up as a change to commit.
- **The installer is now this repository's code.** The registry, the transformers, the receipt and the
  MCP writers are re-implemented, tested and maintained here, and the registry must follow AI Factory's
  by hand.
- **Non-Claude harnesses run degraded skills** (§8), and skills break if the harness starts in a
  subfolder.
- **Pipeline mechanics are duplicated, not shared**, restated from ADR 0001: a fix to AI Factory's
  pipeline does not propagate here; it has to be ported deliberately, or not at all. There is no
  `injections` mechanism, and the knowledge base and validators are built, not vendored.

### Follow-ups

- Publish to GitHub Packages, and document the `.npmrc` and token steps.
- Make the scripts' printed commands harness-aware.
- Decide how `AskUserQuestion` and `Agent` degrade on other harnesses.
- `../../docs/plugin-installation-spec.md` stays for the marketplace's other plugins, with a note that
  dgf-factory left the marketplace under this ADR.
- **What would reverse this:** a named requirement that `dgf-factory` and another dotGov agent-tooling
  effort share a single skill corpus or install path, or a decision to return to a single-harness
  plugin.
