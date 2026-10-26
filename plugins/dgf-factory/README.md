# dgf-factory

> A deterministic build pipeline for Claude Code, Codex, Gemini and other AI harnesses that already
> knows the DotGov Framework.

`dgf-factory` ports the [AI Factory](https://github.com/lee-to/ai-factory) prompt-and-artifact
pipeline into a DGF-specific agent factory. AI Factory is deliberately framework-agnostic and
learns your stack at setup time; `dgf-factory` arrives already knowing DGF — its component
catalogue, its composition specs, its two schema families (modern JSON config and legacy XML
grammar) — and then learns the *system you build with it*.

> **Status: the spine, the learning loop and the DGF-specific skills landed.** The five spine
> skills — `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`, `/dgf-commit` — the learning loop's
> two — `/dgf-fix`, `/dgf-evolve` — and `/dgf-component`, `/dgf-process`, `/dgf-model`, `/dgf-audit`
> and `/dgf-scaffold` exist beside `/dgf-doctor`, on top of the stamped **DGF knowledge base** (with its
> vendored JSON and legacy XSD schema set) and the **validators**. Plans, scope, routes,
> change-relative gates, the data model, blast radius, patches and overrides are decided by scripts,
> checked against DGF's own samples and a known-bad corpus. `/dgf-scaffold` creates a new application
> from an empty folder, from templates the tool ships. It is delivered as an **npm CLI**,
> `@andrian-org/dgf-factory`, whose `dgf-factory setup` installs it into a project for each AI harness
> you use ([ADR 0029](docs/adr/0029-npm-cli-delivery.md)). See [the blueprint](docs/blueprint.md) for the
> build order.

## Quick Start

You need Node 18.3+ and Python 3.9+. The package is internal, published to GitHub Packages, so tell npm
where `@andrian-org` packages live — once per machine, with a GitHub token that has `read:packages`:

```bash
npm config set @andrian-org:registry https://npm.pkg.github.com
npm login --scope=@andrian-org --auth-type=legacy --registry=https://npm.pkg.github.com
npm install -g @andrian-org/dgf-factory
```

Then, in your workspaces root:

```bash
cd /path/to/your/workspaces-root
dgf-factory setup                 # choose your harnesses; it previews every file, then asks
git add .dgf-factory .claude .mcp.json && git commit -m "chore: install dgf-factory"
```

`setup` copies each skill into each chosen harness's folder (`.claude/skills/`, `.codex/skills/`,
`.gemini/skills/`, …), the validators and the knowledge base into `.dgf-factory/runtime/`, registers
the dgf-mcp server where the harness keeps MCP servers, and builds `.dgf-factory/runtime/.venv` for the
validators. A receipt, `.dgf-factory/install.json`, records every file it wrote. Then run `/dgf` in
Claude Code (`$dgf` in Codex).

- **Updating:** install the new version, then run `dgf-factory setup` again. A file you edited is kept
  and reported, never overwritten; a file that changed on both sides is shown as a diff.
- **Teammates** who clone a set-up project need no CLI: the skills and the runtime are committed. Only
  the ignored `.dgf-factory/runtime/.venv` is missing — `dgf-factory setup`, or the command the doctor
  prints, builds it.
- **Harnesses** setup knows: Claude Code, Codex, Cursor, GitHub Copilot, Gemini CLI, Junie, Qwen Code,
  Windsurf, Warp, Zencoder, Roo Code, Kilo Code, Antigravity, OpenCode and `.agents/`. For Kilo Code,
  Windsurf and Zencoder it prints the dgf-mcp registration as a manual step. Codex reads its project
  `.codex/config.toml` only once you trust the project.
- **Non-interactive:** `dgf-factory setup --harness claude,codex --yes`; `--dry-run` previews only;
  `--no-python` skips the virtual environment.
- **What is installed:** `dgf-factory status` compares every installed file and MCP entry with the
  receipt, per harness, and the receipt's version with the CLI's. It writes nothing.
- **Removing it:** `dgf-factory uninstall [--harness <id>]` previews, then removes only files that are
  still exactly what setup wrote, and the `dgf-mcp` entry only while it is unchanged and no other
  installed harness uses that file. The runtime and its `.venv` go when no harness is left. It never
  touches `config.yaml`, `DESCRIPTION.md`, `plans/`, `patches/`, `skill-context/` or `evolutions/`,
  and lists what it left behind: edited files, and MCP settings files it merged into.

To work **on** dgf-factory, clone the repo and open `plugins/dgf-factory/` — the AI Factory
pipeline that builds it is already installed there — and try your change in a scratch project with
`node bin/dgf-factory.mjs setup --root <scratch project> --harness claude`. See
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

`/dgf-doctor` answers "is dgf-factory installed correctly here?" — every file the receipt lists, every
skill for every harness, the validators' environment — and the scripts behind every skill also run on
their own — see [Getting Started](docs/getting-started.md#trying-the-spine):

```bash
python3 .dgf-factory/runtime/skills/dgf-doctor/scripts/doctor.py
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
| [Getting Started](docs/getting-started.md) | Prerequisites, installing, repo layout, working on dgf-factory, trying the spine and the loop |
| [Pipeline Spine](docs/pipeline.md) | The five skills, `.dgf-factory/`, the plan format, the change gate, the learning loop, the DGF-specific skills and blast radius |
| [Architecture](docs/architecture.md) | Slice structure, dependency rules, communication |
| [Skill Authoring](docs/skill-authoring.md) | The SKILL.md contract, gates, exit codes |
| [DGF Knowledge Sourcing](docs/dgf-knowledge.md) | Citing, dating and version-stamping DGF facts |
| [DGF Schemas](docs/dgf-schemas.md) | The two schema families — JSON and XSD — runtime parity, vendoring |
| [Decision Records](docs/adr/README.md) | Why dgf-factory is shaped this way — delivery model, verification, validator runtime, versioning, scope |
| [Architecture Blueprint](docs/blueprint.md) | The full design: AI Factory teardown + DGF mapping |
| [Interview Demo](docs/demo/interview-guide.md) | A 75-minute live demo: a Split Bill app generated from an empty folder, run, changed and gated — with a prep checklist and a cheat sheet |

Project context for AI agents lives in [AGENTS.md](AGENTS.md) and `.ai-factory/`.

## Related

- [`doc-coverage-audit`](../doc-coverage-audit/) — a Claude Code plugin in the same repository
- [Marketplace README](../../README.md) — the `andrian-org` marketplace, which dgf-factory left for npm
- DotGov Framework — the framework this plugin encodes knowledge of

## License

UNLICENSED — internal to dotGov Solutions.
