# dgf-factory

> A deterministic build pipeline for Claude Code that already knows the DotGov Framework.

`dgf-factory` ports the [AI Factory](https://github.com/lee-to/ai-factory) prompt-and-artifact
pipeline into a DGF-specific agent factory. AI Factory is deliberately framework-agnostic and
learns your stack at setup time; `dgf-factory` arrives already knowing DGF — its component
catalogue, its composition specs, its two schema families (modern JSON config and legacy XML
grammar) — and then learns the *system you build with it*.

> **Status: the spine, the learning loop and four DGF-specific skills landed.** The five spine
> skills — `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`, `/dgf-commit` — the learning loop's
> two — `/dgf-fix`, `/dgf-evolve` — and `/dgf-component`, `/dgf-process`, `/dgf-model` and
> `/dgf-audit` exist beside `/dgf-doctor`, on top of the stamped **DGF knowledge base** (with its
> vendored JSON and legacy XSD schema set) and the **validators**. Plans, scope, routes,
> change-relative gates, the data model, blast radius, patches and overrides are decided by scripts,
> checked against DGF's own samples and a known-bad corpus. `/dgf-scaffold` waits on the estate's
> bootstrap template. The plugin **loads locally** with
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
- **Deterministic validation** — spec well-formedness, component resolution and the data model's
  references are decided by scripts against DGF's own JSON Schemas and XSDs and the engine's own
  resolution rules, never by a model's judgement
- **Blast radius** — which processes reach a changed file, in each application, from one reference
  graph resolved the way the engine resolves it — and a plain statement of what a static walk cannot
  see
- **Durable state on disk** — every stage writes an artifact the next stage reads, so you can
  `/clear`, crash, or return days later and resume exactly where you were
- **Machine-readable gates** — quality commands end with a fenced `dgf-gate-result` block that
  orchestrators parse instead of scraping prose
- **Planner/executor split** — a strong model writes an indexed phase bundle once; a cheap model
  executes it many times, and is forbidden from re-deciding architecture
- **A learning loop** — every DGF gotcha caught in practice becomes a patch, and patches distil
  into project-specific skill overrides that can only tighten a skill, never relax its gates. A
  script checks every override before a skill reads it

## Example

### The pipeline, run from a workspaces root

```bash
/dgf                      # inventory the root, record the estate's DGF version
/dgf-plan full "add applicant eligibility check to the permits process"
/dgf-implement            # compose each task, validate it, tick the checkbox; resumable
/dgf-verify               # whole-root gate against the merge-base; ends with dgf-gate-result
/dgf-fix                  # when the gate suggests it: fix inside the plan, record a patch
/dgf-commit               # conventional commits, scoped by workspace
/dgf-evolve               # now and then: distil the patches into rules that tighten the skills
```

Every plan declares the workspaces it touches and, per task, whether it composes configuration
or writes a little JavaScript or CSS, and why. The gate blocks only on findings the branch
introduced; the estate's existing ones are reported as `PRE_EXISTING`. See
[Pipeline Spine](docs/pipeline.md).

`/dgf-doctor` answers "is this plugin installed correctly?", and the scripts behind every skill
also run on their own — see [Getting Started](docs/getting-started.md#trying-the-spine):

```bash
claude --plugin-dir plugins/dgf-factory -p "/dgf-doctor"
```

When the gate finds a new error once every task is done, it suggests `/dgf-fix`: it reproduces
the finding, fixes it inside the plan's scope, confirms the fix with the same check, and writes a
patch — what went wrong, why DGF behaved that way, how to prevent it. `/dgf-evolve`, run when
you ask, turns the patches into skill-context rules. Each rule may only tighten a skill, and a
script refuses an override that would grant a tool, narrow the gate or install anything, before
any skill reads it. See [The learning loop](docs/pipeline.md#the-learning-loop).

### Working on the configuration itself

```bash
/dgf-component inspect DataTable/CaseList      # family, parity, findings, and what reaches it
/dgf-component scaffold DataTable Pending       # one new component, inside the plan's scope
/dgf-process modify app/FM/_WORKFLOW/Submit/_workflow.xml   # the reach first, then the edit
/dgf-model add Orders                           # an entity, and the database work it needs
/dgf-audit                                      # the whole root: validators, graph, roles
/dgf-audit --reach webasm/FM/_WORKFLOW/AX.Notify/_workflow.xml   # blast radius, per application
```

Inspect and validate run anywhere; every write stays inside the active plan's scope, and each kind
of file has one writing skill. See [The DGF-specific skills](docs/pipeline.md#the-dgf-specific-skills).

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Prerequisites, repo layout, working on the plugin, trying the spine and the loop |
| [Pipeline Spine](docs/pipeline.md) | The five skills, `.dgf-factory/`, the plan format, the change gate, the learning loop, the DGF-specific skills and blast radius |
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
