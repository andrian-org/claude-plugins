# Plugin Installation Specification

Status: **draft** · 2026-10-05 · applies to every plugin in `.claude-plugin/marketplace.json`

This specification sets how a plugin in the `andrian-org` marketplace is installed, set up in a project,
updated and removed. It follows the model of [AI Factory](https://github.com/lee-to/ai-factory): a tool
on the machine, and everything a project depends on recorded in the project. Where AI Factory's
installer has a gap, this specification closes it, and §4 lists each deviation.

The AI Factory facts below were read from the AI Factory 2.19.0 CLI source
(`dist/cli/commands/*.js`, `dist/core/*.js`). The Claude Code facts come from the Claude Code plugin
documentation (`plugins/install.md`, `plugins/marketplace-reference.md`, `plugins/loading.md`) and
from `claude plugin … --help`.

The keywords **MUST**, **MUST NOT**, **SHOULD** and **MAY** are used as in RFC 2119.

## 1. The model

AI Factory installs in two layers, and a Claude Code plugin has the same two layers:

| Layer | AI Factory | A plugin in this marketplace |
|---|---|---|
| **Machine:** the tool itself, shared by every project | `npm install -g ai-factory` puts the CLI and its bundled skills in the global `node_modules` | Claude Code puts the plugin in its cache, `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, exposed as `${CLAUDE_PLUGIN_ROOT}` |
| **Project:** what this project uses, committed | `ai-factory init` copies skills into `.claude/skills/`, and records them in `.ai-factory.json` | `claude plugin install … --scope project` writes `enabledPlugins` to `.claude/settings.json`; the plugin's setup skill writes the project's own files and records them in a receipt (§3.3) |

One difference shapes the rest. AI Factory **copies** its skills into the project. A plugin's skills
**stay in the cache**, and the project only enables them. A plugin MUST NOT copy its skills into the
project as well, because a second registration of the same skill name collides with the first.

## 2. Terms

- **Project:** the folder a team opens in Claude Code, holding `.claude/settings.json`.
- **Setup skill:** the plugin's skill that prepares a project (for dgf-factory, `/dgf`). AI Factory's
  equivalent is `ai-factory init`.
- **Project folder of the plugin:** the one directory inside the project that the plugin owns, named
  after the plugin (for dgf-factory, `.dgf-factory/`). AI Factory's equivalent is `.ai-factory/`.
- **Managed file:** a file the setup skill wrote from a template the plugin ships. AI Factory's
  equivalent is an entry under `managedSkills` or `managedAgentFiles`.
- **Receipt:** the file that records what the plugin installed in the project. AI Factory's
  equivalent is `.ai-factory.json`.

## 3. Requirements

### 3.1 Scope and location

**INS-01. Project scope only.** A plugin is installed with `--scope project` (the team's project) or
`--scope local` (one developer, uncommitted). Docs MUST NOT show an install command without a scope or
with `--scope user`.

| Scope | Written to | Committed |
|---|---|---|
| `project` | `<project>/.claude/settings.json` | yes |
| `local` | `<project>/.claude/settings.local.json` | no |

*AI Factory:* `init` writes only inside `process.cwd()`, and every target path is checked against
escaping the project (`core/installer.js`).
*Check:* every `claude plugin install` and `claude plugin marketplace add` line in the plugin's docs
carries `--scope project` or `--scope local`.

**INS-02. No other global writes.** Outside the project, a plugin writes only to the places Claude
Code manages for it: its cache, and `${CLAUDE_PLUGIN_DATA}` (`~/.claude/plugins/data/<plugin-id>/`).

A plugin MUST NOT:
- write to `~/.claude/settings.json`, `~/.claude/skills/` or anywhere else in the home directory;
- run a global package install (`npm install -g`, `pip install` outside a virtual environment, `brew`);
- update itself.

*AI Factory deviation:* its `update` checks npm and runs `npm install -g ai-factory@<latest>` after a
prompt (`cli/commands/update.js`).

**INS-03. Project state stays in the project.** Anything that belongs to one project (config, plans,
patches, overrides) lives in the plugin's project folder. `${CLAUDE_PLUGIN_DATA}` is shared by every
project on the machine. It MAY hold caches that are safe to share, and MUST NOT hold project state.

**INS-04. One project folder, named after the plugin.** A plugin writes in the project only to its
project folder, plus files the user asked it to create. It MUST NOT write to another plugin's folder or
to `.claude/`, apart from what the `claude plugin` CLI writes itself.

### 3.2 Install and onboarding

**INS-05. Quick Start runs from the project folder.** The plugin's README starts its install section
with `cd /path/to/your/project`, then shows:

```bash
claude plugin marketplace add andrian-org/claude-plugins --scope project
claude plugin install <plugin>@andrian-org --scope project
```

It then tells the reader to commit `.claude/settings.json`.

**INS-06. Teammates' step is documented.** Claude Code does not fetch a plugin that only a project's
settings enable. A teammate who opens the project sees *"enabled in project settings but isn't
installed here"* and runs the install command themselves. The README MUST give that command, and
SHOULD tell readers that `/plugin` shows the error.

**INS-07. Setup is separate from install.** Installing makes the skills available. The setup skill
prepares a project, and it MUST be run explicitly. A plugin MUST NOT write project files the moment it
is installed, or from a hook.

*AI Factory:* `ai-factory init` is a separate, explicit step.

**INS-08. Setup previews before it writes.** The setup skill lists every file it will create or change,
with its path, and writes only after the user agrees.

*AI Factory deviation:* it has no dry run.

**INS-09. Moving off a global install is documented.**
```bash
claude plugin uninstall <plugin>@andrian-org --scope user
claude plugin marketplace remove andrian-org --scope user
```

### 3.3 The receipt

**INS-10. A plugin that writes managed files keeps a receipt.** The receipt is at
`<project folder>/install.json`, is committed, and is written last (INS-22). A plugin that writes no
managed files needs no receipt. Its schema:

```json
{
  "plugin": "dgf-factory",
  "version": "0.1.0",
  "managedFiles": {
    ".dgf-factory/config.yaml": {
      "template": "skills/dgf/references/config-template.yaml",
      "sourceHash": "<sha256>",
      "installedHash": "<sha256>"
    }
  }
}
```

- `version` is the `version` in the plugin's `.claude-plugin/plugin.json` that wrote the files.
- `managedFiles` keys are project-relative paths with forward slashes.
- `template` is relative to `${CLAUDE_PLUGIN_ROOT}`. It MUST NOT be absolute, because the cache path
  differs per machine.

*AI Factory:* `.ai-factory.json` holds `version`, `agents[].managedSkills` and `managedAgentFiles`,
each entry being `{sourceHash, installedHash}`.

**INS-11. How the hashes are computed.** Both are SHA-256 hex, one per file.
- `sourceHash` is the hash of the template's bytes.
- `installedHash` is the hash of the file as written, after rendering.
- Text files are normalised before hashing: CRLF becomes LF, and trailing whitespace at the end of the
  file is trimmed. Binary files are hashed raw.

*AI Factory:* the same normalisation for `.md` files (`core/installer.js`). It hashes a skill per
directory; here a managed file is hashed per file.

**INS-12. Unmanaged files are never touched.** A plugin changes or deletes only the files listed in its
receipt, plus files the user named in the current request. A user's own file, even one inside the
plugin's project folder, is never overwritten or removed by setup, update or uninstall.

*AI Factory deviation:* re-running `init` without an agent deletes that agent's whole skills directory,
user skills included. `upgrade` deletes skills by name (`docs`, `commit` and others) without checking
who owns them.

### 3.4 Versions and pinning

**INS-13. Every change ships with a new version.** `plugin.json` `version` MUST be bumped (semver) for
every change released to the marketplace's default branch. The cache is keyed by version.

**INS-14. Projects can pin, and the docs show how.** A plugin with a relative `source` has no version
field of its own. It resolves from the marketplace at the commit the project's marketplace source
points to. A project pins by setting `sha` (exact) or `ref` (a tag) on that source:

```json
{
  "extraKnownMarketplaces": {
    "andrian-org": {
      "source": { "source": "github", "repo": "andrian-org/claude-plugins", "sha": "<40-char commit>" }
    }
  },
  "enabledPlugins": { "<plugin>@andrian-org": true }
}
```

The README MUST show this form. A team that needs reproducible results SHOULD pin. A pin covers the
whole marketplace, so every plugin from it moves together.

*AI Factory:* a project is reproducible because the copied skills are committed. The recorded version
is only printed, never compared.

**INS-15. Version drift is reported.** The plugin's doctor (or setup skill) compares the receipt's
`version` with the running plugin's `version`, and reports a difference as a warning that names both.

*AI Factory deviation:* it records the version but never compares it.

### 3.5 Update

**INS-16. Update is explicit and per managed file.** The setup skill (or a dedicated update mode)
re-renders each managed file and decides per file:

| Template changed (`sourceHash`) | File edited (`installedHash`) | Action |
|---|---|---|
| no | no | leave it |
| yes | no | rewrite it, and record both new hashes |
| no | yes | keep the user's file, and report it as edited |
| yes | yes | keep the user's file, and report a conflict: name the file and show the new template's diff |
| file missing | — | report it; recreate it only if the user agrees |
| template removed from the plugin | — | report it; delete the file only if it is unedited and the user agrees |

A file is rewritten over the user's edits only when the user names that file and says to.

*AI Factory deviation:* `update` overwrites a locally edited skill after a warning. When the upstream
copy also changed, it overwrites with no warning at all. Only its Codex `config.toml` is preserved when
edited, and that is the behaviour this table adopts for every file.

**INS-17. A new template is opt-in.** A managed file that a new plugin version adds is offered, not
written. AI Factory offers new skills the same way (pre-checked on a terminal, skipped without one).

### 3.6 MCP servers and secrets

**INS-18. MCP servers are declared, not written.** A plugin declares its servers in its own `.mcp.json`,
which loads only where the plugin is enabled. A plugin MUST NOT add servers to the project's `.mcp.json`,
to `.claude/settings*.json` or to user config, and its docs MUST NOT tell users to run `claude mcp add`.

*AI Factory deviation:* it merges servers into the project's `.mcp.json`. If that file is not valid
JSON, it replaces the file without warning.

**INS-19. Secrets are placeholders.** A secret appears only as `${VAR}` in `.mcp.json` or in a managed
file. The receipt and managed files never hold a secret value.

*AI Factory:* the same; it writes `${GITHUB_TOKEN}` and `${DATABASE_URL}` placeholders.

**INS-20. Existing files are parsed, not overwritten.** If a plugin must edit a file it does not own (for
example, a project's JSON or YAML), it parses it first. On a parse error it stops and reports, and never
falls back to writing a fresh file.

### 3.7 Runtime dependencies

**INS-21. Dependencies go into the project where they can.** Python and Node dependencies SHOULD be
installed into the project (`.venv/`, `node_modules/`). A plugin MUST NOT install them itself. It
reports a missing dependency with the exact command, and the user runs it. If the command installs at
user level (for example `pip install --user`), the docs MUST say so and why.

### 3.8 Failure

**INS-22. Setup and update leave a known state.** Each managed file is written to a temporary file and
renamed into place. The receipt is written last, so it only ever lists files that were fully written.
If a step fails, the skill reports which files were written and which were not, and the next run
resumes from the receipt.

*AI Factory deviation:* `init` has no transaction. A failure partway leaves files with a missing or
stale `.ai-factory.json`.

### 3.9 Uninstall

**INS-23. Uninstall is documented completely.** The README MUST give:

```bash
claude plugin uninstall <plugin>@andrian-org --scope project
```

It MUST also list what the uninstall leaves behind, and how to remove each item:
- the plugin's entries in `.claude/settings.json`, if any remain;
- the plugin's project folder and its receipt, which the user deletes by hand if they no longer want them;
- `${CLAUDE_PLUGIN_DATA}`, which Claude Code deletes when the plugin is uninstalled from its last scope,
  unless `--keep-data` is given.

*AI Factory deviation:* it has no uninstall command, and leaves `.ai-factory.json`, `.ai-factory/`, the
skill and agent files, and MCP entries behind.

### 3.10 Contributors and checks

**INS-24. Contributors test with local scope.** Testing a plugin from a clone of this repository uses
`--scope local`:

```bash
claude plugin marketplace add /path/to/this/repo --scope local
claude plugin install <plugin>@andrian-org --scope local
```

`project` scope would change this repository's committed `.claude/settings.json`.

**INS-25. The rules are checked by a script.** A check at the repository root runs over every plugin and
the root `README.md`, and fails on:
- an install or `marketplace add` command without `--scope project` or `--scope local` (INS-01);
- an absolute path in a receipt template (INS-10);
- a `claude mcp add` in the docs (INS-18);
- a skill name present in a plugin and also under the repository's own `.claude/skills/`.

It reports each offender as `file:line`.

## 4. Deviations from AI Factory

| Topic | AI Factory 2.19.0 | This specification |
|---|---|---|
| Global writes | `update` may run `npm install -g` | none beyond Claude Code's cache and data directory (INS-02) |
| Skills in the project | copied into `.claude/skills/` | stay in the cache; the project only enables them (§1) |
| Locally edited file on update | overwritten, with a warning | kept, and reported (INS-16) |
| Upstream and local both changed | overwritten, with no warning | kept, and reported as a conflict (INS-16) |
| User files | deleted by agent deselect and by `upgrade` | never touched (INS-12) |
| Recorded version | printed, never compared | compared, and drift reported (INS-15) |
| Pinning | committed copies | marketplace `sha` or `ref` in project settings (INS-14) |
| MCP | merged into the project's `.mcp.json`; an invalid file is replaced | declared in the plugin's `.mcp.json` only (INS-18, INS-20) |
| Dry run | none | preview before writing (INS-08) |
| Partial failure | no transaction | atomic writes, receipt last (INS-22) |
| Uninstall | none | documented, with what is left behind (INS-23) |

## 5. Current conformance

| Requirement | dgf-factory | doc-coverage-audit |
|---|---|---|
| INS-01, INS-05, INS-09, INS-24 | no: docs install at user scope; `.ai-factory/PLAN.md` fixes it | not checked |
| INS-02, INS-03, INS-04 | yes: state lives in `.dgf-factory/` (to confirm across all skills) | not checked |
| INS-10 to INS-17 (receipt, pinning, update) | no: `/dgf` writes `config.yaml` and `DESCRIPTION.md` without a receipt | not checked |
| INS-18, INS-19 | yes: `dgf-mcp` is declared in the plugin's `.mcp.json` | not checked |
| INS-21 | yes, by disclosure: `pip install --user`, decided by its ADR 0015 | not checked |
| INS-23, INS-25 | no | no |

## 6. Open questions

1. **Does a relative-path plugin load for a teammate without an install?** The Claude Code docs say a
   plugin that only project settings enable is not fetched, but they also mention an exception for
   relative-path sources. Every plugin here has a relative source. The root `README.md` currently says
   "a fresh clone is then ready to go". Test this before INS-06 is final.
2. **Does a new `version` reach a project that does not pin?** The docs say an unpinned marketplace
   auto-updates from the default branch. Check whether the cache refreshes without a
   `claude plugin update`.
3. **Where does the INS-25 check live?** The repository root has no tooling yet. Options: a script
   under the root plus a CI job, or one test per plugin.
