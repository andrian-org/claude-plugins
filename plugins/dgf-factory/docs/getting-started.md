[Back to README](../README.md) · [Architecture →](architecture.md)

# Getting Started

This page covers working **on** `dgf-factory`. Installing it as a plugin is not yet
possible — the skill corpus does not exist, and the plugin is not registered in the
marketplace.

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Claude Code | current | The runtime that loads skills and agents |
| Node.js | ≥ 18 | AI Factory CLI and `.mjs` helper scripts |
| Python | 3.9+ | Validator scripts and the skill security scanner |
| Git | any | Azure DevOps remote; LF line endings enforced |
| uv | any | Only to regenerate `scripts/requirements.txt` |

Read access to the DotGov Framework repository is effectively required — the whole point
of this plugin is encoding DGF facts, and facts must be verified against the source.

## Clone and open

```bash
git clone https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins
cd dotgov-claude-plugins/plugins/dgf-factory
```

Open `plugins/dgf-factory/` as the working directory, not the repo root. The AI Factory
pipeline is installed at that level, and the project artifacts in `.ai-factory/` resolve
relative to it.

## What is already here

| Path | Contents |
|------|----------|
| `.claude/skills/aif-*` | 29 AI Factory skills — the pipeline that builds this plugin |
| `.claude/skills/plugin-structure/` | Claude Code plugin layout reference |
| `.claude/agents/` | 19 subagents — coordinators, workers, loop roles, sidecars |
| `.ai-factory/` | Project context: config, description, architecture, rules |
| `docs/` | This documentation |
| `.claude-plugin/plugin.json` | The manifest — what makes this a loadable plugin |
| `skills/dgf-doctor/` | The walking-skeleton slice: `SKILL.md` + `scripts/doctor.py` |
| `knowledge/` | The DGF knowledge base — `README.md` is the stamping convention (and §7 the machine-read table contract); six stamped facts files; `schemas/` holds the vendored JSON + XSD set with `MANIFEST.md`. Shipped, so it names no DGF repository path ([ADR 0012](adr/0012-no-dgf-paths-in-shipped-files.md)) |
| `scripts/` | The validators skills call: `validate_config.py`, `resolve_components.py`, `validate_process.py`, `route_means.py`, their shared `lib/`, and the hash-pinned `requirements.txt`. Shipped |
| `tests/` | Not shipped. The `unittest` suite and its fixtures, including the known-bad corpus under `fixtures/known-bad/` |
| `provenance/` | Not shipped. One ledger per knowledge file: the DGF files its facts were read from, each with a `sha256` |
| `tools/check-dual-schema-docs.sh` | Not shipped. Repo-maintenance check: documentation, decision-record, manifest and knowledge-stamp contracts; section 8 runs the unit tests |
| `tools/check_knowledge_stamps.py` | Not shipped. Checks stamps, ledgers and vendored schema digests; section 7 of the check invokes it |
| `tools/vendor_schemas.py` | Not shipped. Re-vendors DGF's schema set from a DGF checkout, rewriting DGF paths on the way in |
| `tools/run_known_good.py`, `tools/known-good-exceptions.txt` | Not shipped. Runs every validator over DGF's own samples; each error must be excused, with evidence, in the exceptions file |
| `tools/check_drift.py` | Not shipped. Compares every provenance ledger's digests against a DGF checkout |
| `tools/requirements.in` | Not shipped. The two validator dependencies, compiled into `scripts/requirements.txt` |
| `.mcp.json` | The hosted DGF docs MCP (`dgf-mcp`) |

Nothing under `.claude/skills/aif-*` is part of the plugin being built. It is the
toolchain, installer-managed and tracked in `.ai-factory.json`. Do not hand-edit it —
edits are detected and overwritten on update.

## Load it locally

The plugin loads for a single session without touching the marketplace:

```bash
claude --plugin-dir plugins/dgf-factory -p "/dgf-doctor"
```

Point `--plugin-dir` at `plugins/dgf-factory` specifically. A directory *of* plugins loads
every child, so aiming at `plugins/` would pull in the siblings too.

This is session-scoped. It proves the manifest and slice layout are correct; it does not
prove marketplace installation works — that claim belongs to the Marketplace Release
milestone.

`.mcp.json` now has two roles: the dev config for this working directory, **and** the
plugin's shipped MCP declaration. Anything added to it is declared to every user who
installs the plugin, which is why it lists only `dgf-mcp`. If a dev-only server is ever
needed, split the file rather than quietly adding an entry.

## Validators

The validators under `scripts/` run on Python 3.9 or later, with two pinned dependencies:
`lxml` (XSD validation) and `jsonschema` (JSON Schema). A validator run without them exits
`3` with the install command; `/dgf-doctor` checks for them too.

**Install, as a developer using the plugin** ([ADR 0015](adr/0015-validator-runtime-and-json-reader.md)):

```bash
python3 -m pip install --user --require-hashes -r "<plugin>/scripts/requirements.txt"
```

`<plugin>` is the installed plugin's directory. The doctor and the validators print the
command with the real path filled in.

**Work on the plugin in a `.venv/` at the plugin root.** It is ignored by git, the docs check
prefers it, and `--user` is not used inside it:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r scripts/requirements.txt
```

### The four scripts

| Script | Decides | Usage |
|---|---|---|
| `validate_config.py` | Resolves each file's family, validates it against its vendored schema the way the runtime reads it, and checks runtime parity | `<path>... [--component-type T] [--view-kind table\|lookup\|grid]` |
| `resolve_components.py` | Every component type is legal, and every component file a configuration references exists | same arguments as `validate_config.py` |
| `validate_process.py` | A `process.xml`'s structure and semantics (dead transitions, unreachable states, workflow references, `validationFlow`); a `_workflow.xml`'s `CHANGE_STATE` targets | `[--workspaces-root R] (--all \| <file>...)` |
| `route_means.py` | Whether a new piece of configuration is written as JSON or legacy XML | `<name>` |

`validate_config.py` and `resolve_components.py` walk a directory argument for the legacy
artifact files and for JSON under `FM/_COMPONENTS/`. They skip JSON elsewhere under `FM/`,
which no loader reads, but a file named on the command line is always checked. Every
script takes `--verbose` (or `DEBUG=1`), which traces to stderr.

```bash
.venv/bin/python scripts/validate_config.py <workspaces-root>/<app>/FM/_COMPONENTS
.venv/bin/python scripts/validate_process.py --all --workspaces-root <workspaces-root>
.venv/bin/python scripts/route_means.py Uploader
```

Each prints a header, a `FAMILY:` line per file, `CHECKS RUN:` and `NOT RUN:` lines, one line
per finding and a verdict, and exits `0`, `1`, `2` or `3` (see
[Skill Authoring](skill-authoring.md#reading-a-validators-output)).

### Tests and maintainer tools

```bash
.venv/bin/python -m unittest discover -s tests -t .      # the unit tests and the known-bad corpus
bash tools/check-dual-schema-docs.sh                     # section 8 runs the same tests
```

Without `lxml` and `jsonschema` the tests that need them skip, and the docs check warns.

Two tools need a DGF checkout, so they are run by hand and are not part of the docs check:

```bash
.venv/bin/python tools/run_known_good.py <dgf-root>   # every validator over DGF's own samples
python3 tools/check_drift.py <dgf-root>               # the provenance ledgers against the checkout
```

`run_known_good.py` passes only when every error it sees is excused in
`tools/known-good-exceptions.txt`. An excuse is an `EXCEPTION` line whose reason cites the
runtime code path, or an `EXPECTED_EXTERNAL` process. An exception never makes a validator
gap pass: a validator that disagrees with the runtime is fixed.

**Regenerating `scripts/requirements.txt`** after changing `tools/requirements.in` needs
[`uv`](https://docs.astral.sh/uv/):

```bash
uv pip compile tools/requirements.in --universal --python-version 3.9 --generate-hashes \
    --fork-strategy fewest -o scripts/requirements.txt
```

`--fork-strategy fewest` resolves one version of each package for every Python from 3.9 up,
rather than a different one per interpreter.

## What is not here yet

- The rest of `skills/dgf-*/` — the skill corpus beyond the `/dgf-doctor` skeleton
- `agents/` — coordinators and workers
- A marketplace entry in `../../.claude-plugin/marketplace.json`

## Build order

The blueprint is explicit that order matters here, because wrong framework facts are
expensive to unwind once they are baked into prompts:

1. **DGF knowledge references first.** Component catalogue, composition semantics, binding
   rules, naming conventions, common mistakes. Everything else depends on these.
2. **Deterministic validators next.** Config validation, component resolution and process
   verification, written against **both** schema families as vendored into
   `knowledge/schemas/json/` (modern component config) and `knowledge/schemas/xsd/` (legacy
   XML). They are re-vendored from DGF's `src/Tools/dgf-mcp/Schemas/`. DGF's own
   `docs/schemas/` holds only three hand-authored standalone contracts, not the generated
   set; they are vendored separately into `knowledge/schemas/standalone/`. See
   [DGF Schemas](dgf-schemas.md) for the inventories and the family-detection contract.
3. **Then the spine** — `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`.
4. **Then `dgf-gate-result`** wired into verify, then the rest.
5. **Then the learning loop** — `/dgf-fix` and `/dgf-evolve`, even if crude.
6. **Then DGF-specific skills** — `/dgf-component`, `/dgf-audit`.
7. **Parallelism last.** It is the flashiest part and the least load-bearing.

See [the blueprint](blueprint.md) for the reasoning behind each step.

## Working with the pipeline

The `aif-*` commands drive development of this plugin:

```bash
/aif-roadmap                    # break the build order into milestones
/aif-plan full "<task>"         # create a branch and a full plan
/aif-implement                  # work the plan's checkbox ledger
/aif-verify                     # check the work against the plan
/aif-commit                     # conventional commit
```

Plans are branch-scoped — `/aif-plan full` creates a `feature/…` branch off `main`.

## Verify your setup

```bash
node --version                                    # ≥ 18
python3 --version                                 # 3.9+
cat .ai-factory/config.yaml | head -20            # language and path settings
.venv/bin/python skills/dgf-doctor/scripts/doctor.py   # CLEAN once the validator dependencies are in .venv/
```

Confirm the DGF docs MCP is reachable in your Claude Code session — `.mcp.json` declares
`dgf-mcp` at `https://dgf-mcp.dotgov.uk/mcp`. It needs no credentials.

## See Also

- [Architecture](architecture.md) — where new skills, knowledge and scripts belong
- [Skill Authoring](skill-authoring.md) — the contract every `dgf-*` skill must follow
- [DGF Knowledge Sourcing](dgf-knowledge.md) — how to verify a fact before encoding it
