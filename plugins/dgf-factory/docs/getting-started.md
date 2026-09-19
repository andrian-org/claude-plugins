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
| `.mcp.json` | MCP servers: filesystem and the hosted DGF docs MCP |

Nothing under `.claude/skills/aif-*` is part of the plugin being built. It is the
toolchain, installer-managed and tracked in `.ai-factory.json`. Do not hand-edit it —
edits are detected and overwritten on update.

## What is not here yet

- `.claude-plugin/plugin.json` — the manifest
- `skills/dgf-*/` — the skill corpus
- `knowledge/` — the DGF knowledge base
- `scripts/` — the deterministic validators
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
