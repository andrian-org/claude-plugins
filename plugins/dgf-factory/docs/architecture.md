[← Getting Started](getting-started.md) · [Back to README](../README.md) · [Skill Authoring →](skill-authoring.md)

# Architecture

A reader-facing summary. The canonical, enforceable version lives in
[`.ai-factory/ARCHITECTURE.md`](../.ai-factory/ARCHITECTURE.md) — when the two disagree,
that file wins.

**Pattern: Structured Modules (Vertical Slices).** One skill is one self-contained slice.
Shared DGF facts live in `knowledge/`, shared validators in `scripts/`.

## Why this pattern

Every skill is auto-discovered and fires on its own `description`. Nothing calls a skill
as a function, so feature independence is very high and slices that own their material
end-to-end match that reality. A technical-layer split would scatter one skill's prompt,
facts and validator across three trees for no benefit.

Explicit Architecture was considered and rejected: its value is enforcing domain purity
across a dependency-inverted runtime, and there is no runtime here to invert.

## Layout

```text
plugins/dgf-factory/
├── .claude-plugin/plugin.json   # manifest — must live here
├── skills/<name>/               # SLICES — SKILL.md + references/ + scripts/ + templates/
├── agents/*.md                  # subagents
├── knowledge/                   # SHARED DOMAIN — versioned DGF facts + vendored schemas
│   └── schemas/{json,xsd,standalone}/   # both families, kept in separate directories
├── scripts/                     # SHARED INFRASTRUCTURE — cross-slice validators
└── .mcp.json                    # MCP servers
```

Folder names are Claude Code plugin names rather than the reference pattern's
`src/[Module]/Slices/` names. Auto-discovery only loads components from the plugin's
mandated paths; a tree that ignores them is a tree Claude Code never loads. The pattern's
boundary and dependency rules are kept in full — only the vocabulary is translated.

`knowledge/` and `scripts/` are deliberately **not** auto-discovered. They are plain
files, reached as `${CLAUDE_PLUGIN_ROOT}/knowledge/…` and `${CLAUDE_PLUGIN_ROOT}/scripts/…`.

## Dependency direction

One way only:

```text
SKILL.md → own references/ + scripts/ → shared knowledge/ + scripts/ → nothing
```

| | Rule |
|---|---|
| ✅ | A skill reads its own `references/` and `templates/`, calls its own `scripts/` |
| ✅ | A skill reads `${CLAUDE_PLUGIN_ROOT}/knowledge/` and calls `${CLAUDE_PLUGIN_ROOT}/scripts/` |
| ✅ | A shared script reads `knowledge/schemas/json/`, `.../xsd/` and `.../standalone/` |
| ❌ | A validator or skill that handles only one schema family |
| ❌ | A slice reads another slice's `references/`, `scripts/` or `templates/` |
| ❌ | Anything in `knowledge/` names a skill, a step number or a pipeline stage |
| ❌ | A shared script imports from a slice, or branches on who called it |
| ❌ | Circular invocation — A invokes B, B invokes A |
| ❌ | Absolute paths, `~/`, or working-directory-relative paths |

**Promote on the second use.** Facts and validators stay local to a slice until a second
slice needs them, then move up to `knowledge/` or `scripts/`. Not in anticipation.

## Two schema families

DGF configurations come in two formats — modern JSON component config and legacy XML —
because the framework still runs systems written against the older one. Both have
committed schemas, and the DGF MCP serves them through separate tool families.

Two rules follow, and both are enforceable architecture rather than advice. Any consumer
of a component schema **resolves the family before parsing** and never defaults to JSON.
And because a JSON schema existing does not mean the runtime reads it — `Workflow` and
`ProcessFlow` are validated by JSON schemas the runtime ignores in favour of
`_workflow.xml` and `_process.xml` — a passing validation in an unsupported family is a
warning, not a success.

Full inventories, the correspondence map, the detection contract and the vendoring rules
are in [DGF Schemas](dgf-schemas.md).

## How slices communicate

Skills never call each other as functions. Three mechanisms only:

- **Artifacts.** Each `.dgf-factory/` artifact has exactly one owning slice; every other
  slice treats it as read-only. `/dgf-plan` writes the plan, `/dgf-implement` updates only
  the checkbox ledger, `/dgf-verify` reads both.
- **Gate blocks.** A quality slice ends its report with one fenced `dgf-gate-result` JSON
  block. Callers parse the **last** such block and nothing else — never the prose above it.
- **Command invocation.** A slice may invoke another as a command, but never reaches into
  its files.

## Single-writer ownership

Two slices writing the same file silently destroy each other's work across sessions. The
ownership table is the thing that makes multi-session, multi-agent work non-chaotic.

| Artifact | Owner | Others |
|---|---|---|
| `DESCRIPTION.md` | `/dgf` | read-only |
| `ARCHITECTURE.md` | `/dgf-architecture` | structure notes only |
| `plans/<id>/` | `/dgf-plan` | `/dgf-implement` updates only the ledger in `index.md` |
| `patches/` | `/dgf-fix` | consumed by `/dgf-evolve` |
| `knowledge/` | deliberate human edit with a cited source | read-only to every slice |

## See Also

- [Skill Authoring](skill-authoring.md) — the contract a slice's `SKILL.md` must follow
- [DGF Knowledge Sourcing](dgf-knowledge.md) — the rules governing `knowledge/`
- [DGF Schemas](dgf-schemas.md) — the two schema families and the rules for consuming them
- [Architecture Blueprint](blueprint.md) — why these five ideas were carried over from AI Factory
