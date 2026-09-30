[Back to README](../README.md) · [Pipeline Spine →](pipeline.md)

# Getting Started

This page covers working **on** `dgf-factory`, and trying its pipeline on a copy of DGF's
samples. Installing it from the marketplace is not yet possible: the plugin loads locally with
`--plugin-dir`, but it is not registered there.

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
| `skills/dgf`, `dgf-plan`, `dgf-implement`, `dgf-verify`, `dgf-commit` | The pipeline spine — set up, plan, implement, verify, commit. `dgf`, `dgf-plan`, `dgf-implement` and `dgf-verify` carry `references/` too. See [Pipeline Spine](pipeline.md) |
| `skills/dgf-fix`, `dgf-evolve` | The learning loop — fix inside the plan and record a patch; distil patches into overrides. Each carries its format in `references/`. See [The learning loop](pipeline.md#the-learning-loop) |
| `skills/dgf-component`, `dgf-process`, `dgf-model`, `dgf-audit` | The DGF-specific skills — components, processes and workflows, entities, and the audit with blast radius. `dgf-process` and `dgf-model` carry `templates/`. See [The DGF-specific skills](pipeline.md#the-dgf-specific-skills) |
| `knowledge/` | The DGF knowledge base — `README.md` is the stamping convention (and §7 the machine-read table contract); nine stamped facts files; `schemas/` holds the vendored JSON + XSD set with `MANIFEST.md`. Shipped, so it names no DGF repository path ([ADR 0012](adr/0012-no-dgf-paths-in-shipped-files.md)) |
| `scripts/` | The scripts skills call. The validators: `validate_config.py`, `resolve_components.py`, `validate_process.py`, `validate_model.py`, `route_means.py`, and the audit `audit_root.py`. The spine's: `locate_plan.py`, `inventory_root.py`, `check_plan.py`, `check_change.py`, and the verify gate `verify_gate.py`. The loop's: `check_patches.py` and `check_override.py`. Their shared `lib/` — `lib/gate_result.py` builds every gate block — and the hash-pinned `requirements.txt`. Shipped |
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

### The validators

| Script | Decides | Usage |
|---|---|---|
| `validate_config.py` | Resolves each file's family, validates it against its vendored schema the way the runtime reads it, and checks runtime parity | `<path>... [--component-type T] [--view-kind table\|lookup\|grid]` |
| `resolve_components.py` | Every component type is legal, and every component file a configuration references exists | same arguments as `validate_config.py` |
| `validate_process.py` | A `process.xml`'s structure and semantics (dead transitions, unreachable states, workflow references, `validationFlow`); a `_workflow.xml`'s `CHANGE_STATE` targets | `[--workspaces-root R] (--all \| <file>...)` |
| `validate_model.py` | An entity's and a form's references — each `extract`, `slavegrid` and form entity, resolved each loader's way — an entity's own load, and a form's bound cells | `[--workspaces-root R] (--all \| <settings.xml \| _form.xml>...)` |
| `route_means.py` | Whether a new piece of configuration is written as JSON or legacy XML | `<name>` |
| `audit_root.py` | The whole root's health, or the processes that reach a file in each application — a report, never a gate | `--workspaces-root R [--reach PATH... \| --base REF \| --changed S:PATH...] [--app NAME] [--skip-validators]` |

`validate_config.py` and `resolve_components.py` walk a directory argument for the legacy
artifact files and for JSON under `FM/_COMPONENTS/`. They skip JSON elsewhere under `FM/`,
which no loader reads, but a file named on the command line is always checked. Every
script takes `--verbose` (or `DEBUG=1`), which traces to stderr.

```bash
.venv/bin/python scripts/validate_config.py <workspaces-root>/<app>/FM/_COMPONENTS
.venv/bin/python scripts/validate_process.py --all --workspaces-root <workspaces-root>
.venv/bin/python scripts/route_means.py Uploader
.venv/bin/python scripts/validate_model.py --all --workspaces-root <workspaces-root>
.venv/bin/python scripts/audit_root.py --workspaces-root <workspaces-root> --reach webasm/FM/_WORKFLOW/AX.Notify/_workflow.xml
```

`validate_model.py` checks the references every entity and form makes, resolved each loader's way.
`audit_root.py` with no `--reach` audits the whole root; with it, it names the processes that reach
the file in each application, and ends with a `LIMIT:` line — a static reach is never complete.

Each validator prints a header, a `FAMILY:` line per file, `CHECKS RUN:` and `NOT RUN:` lines, one
line per finding and a verdict; `audit_root.py` prints its `ROOT:`, `GRAPH:` or `REACH:` lines in place of
`FAMILY:` lines. All of them exit `0`, `1`, `2` or `3` (see
[Skill Authoring](skill-authoring.md#reading-a-validators-output)).

### The spine's scripts

| Script | Decides |
|---|---|
| `locate_plan.py` | The workspaces root, and the active plan |
| `inventory_root.py` | Each workspace and its counts, and what is not a workspace |
| `check_plan.py` | Whether a plan is well formed, in scope and routed, whether its Commit Plan agrees with its tasks, and which other plans overlap it |
| `check_change.py` | Whether a branch's change stays inside its plan, and which validator findings it introduced |
| `verify_gate.py` | The gate: all of the above in one run, the status computed, and one `dgf-gate-result` block |

| `check_patches.py` | Whether each patch is well formed, and — with `--cursor` — which ones `/dgf-evolve` has not seen |
| `check_override.py` | Whether a skill may read its skill-context override: its shape, its sources, nothing forbidden, and which rules need judgement |

Their flags and exit codes are in [Pipeline Spine → The scripts](pipeline.md#the-scripts),
[The learning loop](pipeline.md#the-learning-loop) and, for `validate_model.py` and
`audit_root.py`, [The DGF-specific skills](pipeline.md#the-dgf-specific-skills).

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

## Trying the spine

The spine's scripts run on their own against any workspaces root. A disposable copy of DGF's
samples, made a git repository, is enough to watch a plan, a change and the gate:

```bash
cp -R <dgf-root>/src/samples/workspaces /tmp/estate
git -C /tmp/estate init -b main
git -C /tmp/estate add -A
git -C /tmp/estate commit -m "samples"
mkdir /tmp/estate/.dgf-factory
printf 'dgf:\n  version: "unknown"\n' > /tmp/estate/.dgf-factory/config.yaml
```

Set a local `user.name` and `user.email` in the copy first if git asks for them. Then, from the
plugin root:

```bash
.venv/bin/python scripts/inventory_root.py --workspaces-root /tmp/estate
.venv/bin/python scripts/locate_plan.py --workspaces-root /tmp/estate --root-only
```

Cut a branch in the copy (`git -C /tmp/estate checkout -b feature/try`), write a plan at
`/tmp/estate/.dgf-factory/plans/feature-try.md` from
`skills/dgf-plan/references/PLAN-FORMAT.md`, change the files it lists, and check both:

```bash
.venv/bin/python scripts/check_plan.py /tmp/estate/.dgf-factory/plans/feature-try.md --workspaces-root /tmp/estate --overlap
.venv/bin/python scripts/check_change.py --workspaces-root /tmp/estate --plan /tmp/estate/.dgf-factory/plans/feature-try.md --base main
```

Then gate it, as `/dgf-verify` does — every check in one run, ending with the block:

```bash
.venv/bin/python scripts/verify_gate.py --workspaces-root /tmp/estate --plan /tmp/estate/.dgf-factory/plans/feature-try.md --base main
```

`check_change.py` reports the samples' own findings as `INFO PRE_EXISTING` and only what the
branch introduced as `ERROR` or `WARN`. To drive the same flow through the skills, load the
plugin with `--plugin-dir` and run `/dgf /tmp/estate`, then `/dgf-plan`, `/dgf-implement`,
`/dgf-verify` and `/dgf-commit` inside the copy. See [Pipeline Spine](pipeline.md).

## Trying the loop

The loop's two scripts need no DGF checkout and no `config.yaml`. On a scratch root, write a patch
from the worked example in `skills/dgf-fix/references/PATCH-FORMAT.md`, and check it with the
cursor that tells `/dgf-evolve` what is new:

```bash
mkdir -p /tmp/loop/.dgf-factory/patches
# save the worked example as /tmp/loop/.dgf-factory/patches/2026-09-26-14.30-review-moves-to-undeclared-state.md
python3 scripts/check_patches.py --workspaces-root /tmp/loop --cursor .dgf-factory/evolutions/patch-cursor.json
```

`PATCH: … state=new`, exit `0`. Break a field or empty a section, and it exits `1` with the line.
Then write the worked override from `skills/dgf-evolve/references/OVERRIDE-FORMAT.md` to
`/tmp/loop/.dgf-factory/skill-context/dgf-plan/SKILL.md` and check it, as `/dgf-plan` does before
reading it:

```bash
python3 scripts/check_override.py --workspaces-root /tmp/loop --skill dgf-plan
```

Exit `0`. Add a rule telling the skill to pass `--skip-validators`, and it exits `1`,
`OVERRIDE_FORBIDDEN`: every reader would refuse the file unread. To drive the loop through the
skills, run `/dgf-fix` when `/dgf-verify` suggests it, then `/dgf-evolve`.

## What is not here yet

- `/dgf-scaffold` — a new application from an empty folder, designed in
  [ADR 0027](adr/0027-dgf-specific-skills-revised.md) §7 and not yet built
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
3. **Then the spine** — `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`, `/dgf-commit`.
4. **Then `dgf-gate-result`** wired into verify, then the rest.
5. **Then the learning loop** — `/dgf-fix` and `/dgf-evolve`, even if crude.
6. **Then DGF-specific skills** — `/dgf-component`, `/dgf-process`, `/dgf-model`, `/dgf-audit`.
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

- [Pipeline Spine](pipeline.md) — the five skills, the plan format, the change gate, and the learning loop
- [Architecture](architecture.md) — where new skills, knowledge and scripts belong
- [Skill Authoring](skill-authoring.md) — the contract every `dgf-*` skill must follow
- [DGF Knowledge Sourcing](dgf-knowledge.md) — how to verify a fact before encoding it
