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
| `.claude/skills/aif-*` | 30 AI Factory skills — the pipeline that builds this plugin |
| `.claude/skills/plugin-structure/` | Claude Code plugin layout reference |
| `.claude/agents/` | 19 subagents — coordinators, workers, loop roles, sidecars |
| `.ai-factory/` | Project context: config, description, architecture, rules |
| `docs/` | This documentation |
| `.claude-plugin/plugin.json` | The manifest — what makes this a loadable plugin |
| `skills/dgf-doctor/` | The walking-skeleton slice: `SKILL.md` + `scripts/doctor.py` |
| `knowledge/` | The DGF knowledge base — `README.md` is the stamping convention; four stamped facts files; `schemas/` holds the vendored JSON + XSD set with `MANIFEST.md`. Shipped, so it names no DGF repository path ([ADR 0012](adr/0012-no-dgf-paths-in-shipped-files.md)) |
| `provenance/` | Not shipped. One ledger per knowledge file: the DGF files its facts were read from, each with a `sha256` |
| `tools/check-dual-schema-docs.sh` | Not shipped. Repo-maintenance check: documentation, decision-record, manifest and knowledge-stamp contracts |
| `tools/check_knowledge_stamps.py` | Not shipped. Checks stamps, ledgers and vendored schema digests; section 7 of the check invokes it |
| `tools/vendor_schemas.py` | Not shipped. Re-vendors DGF's schema set from a DGF checkout, rewriting DGF paths on the way in |
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

## What is not here yet

- The rest of `skills/dgf-*/` — the skill corpus beyond the `/dgf-doctor` skeleton
- The deterministic dual-schema validators and the drift check that compares
  `knowledge/` stamps against a consumer's DGF checkout (milestone 8)
- `agents/` — coordinators and workers
- A marketplace entry in `../../.claude-plugin/marketplace.json`

## Build order

The blueprint is explicit that order matters here, because wrong framework facts are
expensive to unwind once they are baked into prompts:

1. **DGF knowledge references first.** Component catalogue, composition semantics, binding
   rules, naming conventions, common mistakes. Everything else depends on these.
2. **Deterministic validators next.** Spec well-formedness, component resolution, binding
   completeness — written against **both** committed schema sets:
   `DotGovFramework/src/Tools/dgf-mcp/Schemas/Json/` (modern component config) and
   `Schemas/XSD/` (legacy XML). Note that `DotGovFramework/docs/schemas/` holds only three
   hand-authored standalone contracts, not the generated set. See
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
```

Confirm the DGF docs MCP is reachable in your Claude Code session — `.mcp.json` declares
`dgf-mcp` at `https://dgf-mcp.dotgov.uk/mcp`. It needs no credentials.

## See Also

- [Architecture](architecture.md) — where new skills, knowledge and scripts belong
- [Skill Authoring](skill-authoring.md) — the contract every `dgf-*` skill must follow
- [DGF Knowledge Sourcing](dgf-knowledge.md) — how to verify a fact before encoding it
