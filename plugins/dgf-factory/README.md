# dgf-factory

> A deterministic build pipeline for Claude Code that already knows the DotGov Framework.

`dgf-factory` ports the [AI Factory](https://github.com/lee-to/ai-factory) prompt-and-artifact
pipeline into a DGF-specific agent factory. AI Factory is deliberately framework-agnostic and
learns your stack at setup time; `dgf-factory` arrives already knowing DGF — its component
catalogue, its composition specs, its two schema families (modern JSON config and legacy XML
grammar) — and then learns the *system you build with it*.

> **Status: knowledge base landed.** The plugin manifest, one walking-skeleton skill
> (`/dgf-doctor`), and the **DGF knowledge base** exist — stamped facts on both schema
> families, the component catalogue, composition and naming, plus the vendored JSON/XSD
> schema set with a per-file digest manifest. The validators that consume it and the rest
> of the `dgf-*` corpus do not exist yet. The plugin **loads locally** with
> `claude --plugin-dir plugins/dgf-factory`; it is **not registered in the marketplace**.
> See [the blueprint](docs/blueprint.md) for the build order.

## Quick Start

Once published, teammates install it from the internal `dotgov` marketplace:

```bash
claude plugin marketplace add https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins
claude plugin install dgf-factory@dotgov
```

To work **on** the plugin, clone the repo and open `plugins/dgf-factory/` — the AI Factory
pipeline that builds it is already installed there. See
[Getting Started](docs/getting-started.md).

## Key Features

- **Pre-loaded framework knowledge** — the DGF component catalogue and composition rules ship
  *in* the plugin as versioned, cited references, instead of being re-derived per project
- **Deterministic validation** — spec well-formedness and component resolution are decided by
  scripts against DGF's own JSON Schemas and XSDs, never by a model's judgement
- **Durable state on disk** — every stage writes an artifact the next stage reads, so you can
  `/clear`, crash, or return days later and resume exactly where you were
- **Machine-readable gates** — quality commands end with a fenced `dgf-gate-result` block that
  orchestrators parse instead of scraping prose
- **Planner/executor split** — a strong model writes an indexed phase bundle once; a cheap model
  executes it many times, and is forbidden from re-deciding architecture
- **A learning loop** — every DGF gotcha caught in practice becomes a patch, and patches distil
  into project-specific skill overrides

## Example

### What runs today

One skill exists — `/dgf-doctor`, the walking skeleton. It answers "is this plugin
installed correctly, and what can it see?", and needs no DGF knowledge to do it:

```bash
claude --plugin-dir plugins/dgf-factory -p "/dgf-doctor"
```

It reports `CLEAN`, `WARNINGS` or `BLOCKED`, exits `0`/`2`/`1` accordingly, and closes with
a `dgf-gate-result` block. Unbuilt milestones are `INFO` lines that never affect the
verdict, so an unfinished-but-correct plugin still reads `CLEAN`.

### What the pipeline will look like

The intended workflow, once the skill corpus exists:

```bash
/dgf                      # detect DGF version, module layout, existing components
/dgf-plan full "add applicant eligibility check to the permits process"
/dgf-implement            # work the checkbox ledger; resumable across sessions
/dgf-verify               # emits dgf-gate-result — blocking findings stop the pipeline
/dgf-commit               # conventional commit
```

When verification fails, `/dgf-fix` writes a patch; `/dgf-evolve` distils accumulated patches
into rules that sharpen the next run.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Prerequisites, repo layout, working on the plugin |
| [Architecture](docs/architecture.md) | Slice structure, dependency rules, communication |
| [Skill Authoring](docs/skill-authoring.md) | The SKILL.md contract, gates, exit codes |
| [DGF Knowledge Sourcing](docs/dgf-knowledge.md) | Citing, dating and version-stamping DGF facts |
| [DGF Schemas](docs/dgf-schemas.md) | The two schema families — JSON and XSD — runtime parity, vendoring |
| [Decision Records](docs/adr/README.md) | Why the plugin is shaped this way — delivery model, verification, validator runtime, versioning, scope |
| [Architecture Blueprint](docs/blueprint.md) | The full design: AI Factory teardown + DGF mapping |

Project context for AI agents lives in [AGENTS.md](AGENTS.md) and `.ai-factory/`.

## Related

- [`doc-coverage-audit`](../doc-coverage-audit/) — sibling plugin in the same marketplace
- [Marketplace README](../../README.md) — installing plugins from the `dotgov` marketplace
- DotGov Framework — the framework this plugin encodes knowledge of

## License

UNLICENSED — internal to dotGov Solutions.
