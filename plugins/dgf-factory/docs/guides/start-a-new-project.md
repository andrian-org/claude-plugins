[← Guides](README.md) · [Back to README](../../README.md) · [Add functionality →](add-functionality.md)

# Start a New Project

From an empty folder to a generated DGF application that the pipeline can work on, with its first plan.

## When to use this

You are starting a new DGF application and nothing exists yet. If the application already exists — even
partly — this is not your guide: use [Add functionality](add-functionality.md). `/dgf-scaffold` writes only
into an empty folder and never adds to an existing application
([ADR 0026](../adr/0026-authoring-entry-point-revised.md) §2).

## What you need

| Need | Why |
|---|---|
| Node.js 18.3 or later | the `dgf-factory` CLI |
| Python 3.9 or later | the validators every skill runs |
| Git | plans live on branches, and the gate compares your branch with its merge-base |
| A GitHub token with `read:packages` | the package is internal, on GitHub Packages |
| Claude Code, or another harness | it runs the skills |
| An empty folder | the scaffold refuses any other |
| An absolute path to a `webasm` folder that holds `FM/` | the base workspace: DGF's, or your estate's. dgf-factory ships none |
| The DGF version to target, such as `1.1.15` | the scaffold asks for it; the framework pins none |

To **run** the generated application later you also need Docker with Compose 2.23 or later, and four things
DGF pins no consumer artifact for: the base workspace, an image that publishes the framework's database
baseline, the DGF UI image, and a NuGet feed that serves `DGF.API`. The generated `docs/README.md` lists them.

## Step 1: Install the CLI (once per machine)

```bash
npm config set @andrian-org:registry https://npm.pkg.github.com
npm login --scope=@andrian-org --auth-type=legacy --registry=https://npm.pkg.github.com
npm install -g @andrian-org/dgf-factory
dgf-factory --version
```

The first command writes `@andrian-org:registry=https://npm.pkg.github.com` into your `~/.npmrc`; `npm login`
asks for your GitHub user name and the token, and stores the token there too. `dgf-factory --version` prints
the installed version.

If `npm install` fails to authenticate, run `npm login` again with a token that has `read:packages`.

## Step 2: Make the folder and install dgf-factory into it

```bash
mkdir permits-app
cd permits-app
git init
dgf-factory setup
```

`setup` asks which harnesses you use, previews every file, and asks before it writes. Without questions:
`dgf-factory setup --harness claude --yes`; to preview only: `--dry-run`.

**What you will see** — the preview, then what was written:

```text
Claude Code (.claude/skills/, .claude/agents/): 24 create
  create   .claude/agents/dgf-implement-coordinator.md
  create   .claude/skills/dgf-archive/SKILL.md
  …
MCP (dgf-mcp):
  register  .mcp.json (claude)

Python:
  …
Written: 257 file(s); removed: 0; unchanged: 0; receipt updated

Next:
  - in Claude Code: /dgf to set up the estate, then /dgf-doctor
  …
```

The skills go into the harness's folder (`.claude/skills/`, `.codex/skills/`, …), the validators and the
knowledge base into `.dgf-factory/runtime/`, and a receipt into `.dgf-factory/install.json`. Setup also builds
the validators' Python environment, `.dgf-factory/runtime/.venv/`, which git ignores
([ADR 0031](../adr/0031-validator-runtime-project-venv.md)). This install counts as nothing: the folder is
still empty to the scaffold ([ADR 0029](../adr/0029-npm-cli-delivery.md) §2).

| Exit | What to do |
|---|---|
| `0` | Go on. |
| `1` | An MCP settings file does not parse, or a write failed. The message names the file; fix it and run `setup` again — it resumes from what is on disk. |
| `2` | Read the lines. The Python step failed (run the command it prints), or a harness needs its MCP entry added by hand (Kilo Code, Devin Desktop, Zencoder), or a file was kept because you edited it. |
| `3` | A usage error — on a terminal that cannot answer questions, pass `--harness` and `--yes`. |

## Step 3: Check the install

Start Claude Code **in this folder**, then:

```text
/dgf-doctor
```

**What you will see** — the doctor's sections, a verdict and its own gate block:

```text
dgf-factory install check
1. Install
INFO  claude — all 22 skills installed
…
5. Validator runtime
INFO  validator dependencies — lxml and jsonschema import
…
CHECKS RUN: install, skill-slices, portability, line-endings, validator-runtime
CLEAN
```

| Exit | What to do |
|---|---|
| `0` | Go on. |
| `1` | The install is broken — `INSTALL_FILE_MISSING`, `INSTALL_HARNESS_INCOMPLETE`, `INSTALL_RECEIPT_UNREADABLE`. Run `dgf-factory setup` again, then `/dgf-doctor`. |
| `2` | Read every warning. `VALIDATOR_DEPS_MISSING` carries the exact install command: run it yourself. `INSTALL_FILE_EDITED` means setup will keep your edit and not update that file. `INSTALL_VERSION_DRIFT` means the CLI on your PATH is not the version that installed this project: run `dgf-factory setup`. |
| `3` | The runtime is incomplete. Run `dgf-factory setup` again. |

## Step 4: Generate the application

Describe the application in one request. Name what you know: the instances (each directorate, agency or tenant
is one), how users sign in, the roles, and the registers, services and pages it needs.

```text
/dgf-scaffold "an inspections application for the Lands directorate: a permit register and an approval service, local sign-in"
```

The skill works through the steps below, in order. Two scripts decide everything a script can; the model writes the design and asks
you what is open ([ADR 0027](../adr/0027-dgf-specific-skills-revised.md) §7).

### 4.1 The folder is empty

`design.py --empty-only` checks the folder. Only `.git/`, `docs/application.json` and the install from Step 2
are allowed.

| Exit | What to do |
|---|---|
| `0` | Nothing to do: the skill goes on. |
| `1`, `SCAFFOLD_DIR_NOT_EMPTY` | The skill stops and lists what is in the way. Use an empty folder — or, for an existing application, `/dgf-plan`. |
| `3` | The folder is not a directory, or `INSTALL_RECEIPT_UNREADABLE`: run `dgf-factory setup` again. |

### 4.2 The design, and its check

The skill writes `docs/application.json` from your request — **only what the request states** — and runs
`design.py`. Every key, its rule and its default is in the skill's
`references/DESIGN-FORMAT.md` (installed at `.dgf-factory/runtime/skills/dgf-scaffold/references/`).

**What you will see** — one `SCAFFOLD_ASK` per value still open, and one `DEFAULT:` line per value the script
filled in. For example, for a design that gave only the name, one register and its entity:

```text
Scaffold design
FOLDER: .
APPLICATION: Inspections
CHECKS RUN: folder, design, names, model, references, options, base
WARN SCAFFOLD_ASK docs/application.json dgf_version — the DGF.API package version to target, such as 1.1.15 — the framework pins none
WARN SCAFFOLD_ASK docs/application.json instances — the application's instances: at least one, each a lower-case name and a title (candidates: one instance named after the application)
WARN SCAFFOLD_ASK docs/application.json base.source — an absolute path to a directory named webasm: DGF's, or an estate's — the plugin pins no base
WARN SCAFFOLD_ASK docs/application.json base.supply — how the base reaches the application: `copy` puts it in workspaces/webasm; `mount` mounts it in compose from a path you set (candidates: copy, mount)

Summary
…
DEFAULT: roles = []
DEFAULT: modules[Permits].route = "/permits"
OPEN: 4

WARNINGS
```

| Exit | What to do |
|---|---|
| `0` | Nothing is open. The skill goes to 4.4. |
| `1` | A conflict — `SCAFFOLD_NAME_INVALID`, `SCAFFOLD_OPTION_INVALID`, `SCAFFOLD_REFERENCE_INVALID`, `SCAFFOLD_MODEL_INVALID`, `SCAFFOLD_SQL_TYPE_UNKNOWN`. Each line names the key and the rule. Give the corrected value when asked. |
| `2` | Values are open. Answer the questions (4.3). |
| `3` | `SCAFFOLD_DESIGN_UNREADABLE` — the file is not a design. The skill stops and quotes the line. |

### 4.3 Answer the questions

Each `SCAFFOLD_ASK` becomes a question, four at a time. **The DGF version** is chosen from the published
releases, with no default; if the docs MCP is unavailable, type it as `X.Y.Z`. **The base**: give the absolute
path of a `webasm` folder, and choose `copy` (it goes into `workspaces/webasm`) or `mount` (compose mounts it
from a path you set). Then the design is checked again. After five rounds that leave a value open, the skill
stops; run `/dgf-scaffold` again in the same folder and it resumes from `docs/application.json`.

### 4.4 Confirm

Nothing is written yet. The skill shows every `DEFAULT:` line — the decisions nobody made — and the tree from
`generate.py --dry-run`, one `TARGET:` line per file. Choose **generate**, **change something** or **cancel**.
Cancel keeps the design in `docs/` for a later run.

| Exit (dry run) | What to do |
|---|---|
| `0` | Read the tree and the defaults, then choose. |
| `1`, `SCAFFOLD_TARGET_EXISTS` | The folder changed since 4.1. Nothing was written. |
| `3` | `SCAFFOLD_DESIGN_INCOMPLETE` — the design changed since its check; the skill checks it again. `SCAFFOLD_TEMPLATE_MISSING` — a defect in dgf-factory's templates: report it. |

### 4.5 Generate, then check what was generated

`generate.py` writes every file (one `WROTE:` line each) and `generate.py --check` checks the result: secrets
and variables, the structure of the files no validator reads, the routes, and the validators over the generated
workspaces.

```text
Scaffold check
FOLDER: .
FILES: 36
WORKSPACES: inspections
CHECKS RUN: secrets, structure, routes, validators
…
CLEAN
```

| Exit | What to do |
|---|---|
| `0` (generate) | Every file is written. The skill runs the check. |
| `1` (generate), `SCAFFOLD_TARGET_EXISTS` | The folder changed; nothing was written. |
| `3` (generate) | `SCAFFOLD_DESIGN_INCOMPLETE`, `SCAFFOLD_TEMPLATE_MISSING` or `SCAFFOLD_WRITE_FAILED`. After a failed write the folder is as it was. |
| `0` (check) | The application is sound. The skill reports. |
| `1` (check) | `SCAFFOLD_LITERAL_SECRET`, `SCAFFOLD_VAR_UNDECLARED`, `SCAFFOLD_STRUCTURE_INVALID`, `SCAFFOLD_ROUTE_UNRESOLVED` or `SCAFFOLD_VALIDATION_FAILED`: a defect of the generator. Do not patch the output by hand — report it with the lines. |
| `3` (check), `DEPENDENCY_MISSING` | The validators cannot run. Run the command it prints, then ask the skill to check again. |

### 4.6 The report

The skill says what was generated, how to run it (the steps of the generated `docs/README.md`), every variable
to fill from `docs/configuration.md` with the secrets marked, and what is **not** generated: custom behaviour,
integrations, documents, reports, Helm and pipelines. Those are later work for `/dgf-plan`. It ends with the next
step: `/dgf <folder>/workspaces`.

A secret, a host, a feed, a registry and an image tag are never literal: each is a `${VAR}` declared in
`docker/.env.example` and `docs/configuration.md`.

## Step 5: Commit the generated application

Commit everything now, on your base branch, before you change anything. Every later gate compares a branch with
its merge-base, so this commit is what "already there" means
([ADR 0018](../adr/0018-change-relative-gates.md)).

```bash
git add -A
git commit -m "feat: generate the application with /dgf-scaffold"
```

`/dgf-commit` cannot do this one yet: it needs the root that `/dgf` sets up in the next step.

## Step 6: Set up the workspaces root

The generated workspaces are in `workspaces/`, so that folder is the root:

```text
/dgf workspaces
```

**What you will see** — the root, then the inventory of every workspace:

```text
Plan discovery
NEW ROOT: <folder>/workspaces
…
WORKSPACE: inspections role=application processes=0 workflows=0 components=5 forms=1 settings=1 views=2 …
WORKSPACE: webasm role=base processes=11 workflows=137 components=135 …
GIT: toplevel=<folder> branch=main root=workspaces
KNOWLEDGE: dgf_version=1.1.11
VALIDATORS: dependencies present
```

Then it asks: the estate's name and purpose; **the DGF version the estate runs** — from the published releases,
or `unknown`, never a default ([ADR 0019](../adr/0019-declared-dgf-version.md)); the base branch and the branch
prefix; the sign-in methods; and the test stack. The `KNOWLEDGE:` line is the release the shipped DGF facts were
read at. It is shown beside the question, and never offered as the answer. When the version you declare is newer,
`/dgf` says so and offers the release notes since that stamp.

It writes `workspaces/.dgf-factory/config.yaml` and `workspaces/.dgf-factory/DESCRIPTION.md`, and nothing else.

| Exit (inventory) | What to do |
|---|---|
| `0` | Answer the questions. |
| `2` | Read each `WARN`. `BASE_WORKSPACE_ABSENT`: you chose `mount`, so `webasm` is not in the root and `BASE:` references cannot be checked here. `VALIDATOR_DEPS_MISSING`: run the install command it prints. |
| `3`, `ROOT_NO_WORKSPACE` | You pointed `/dgf` at the application folder, not at `workspaces/`. Run `/dgf workspaces`. |

Then commit the configuration. Stage it, then let `/dgf-commit` write the message:

```bash
git add workspaces/.dgf-factory/
```

```text
/dgf-commit
```

With no plan yet it says so in one line and suggests `chore(dgf): set up dgf-factory`. It asks before it
commits, and before it pushes.

## Step 7: Seed the team rules

```text
/dgf-rules init
```

This skill runs only when you ask for it. It seeds `.dgf-factory/RULES.md` with the six shipped defaults — R1,
R2, R3, R4, R6 and R7 ([ADR 0028](../adr/0028-default-team-rules-revised.md)) — after you say **Write it**.
`check_rules.py` checks the file before and after the write.

**What you will see:**

```text
RULES CHECK
RULES: none — no .dgf-factory/RULES.md
RULE: R1 enforcement=script check=means-route source=default title="XML-always for the five legacy artifact types"
RULE: R2 enforcement=gate check=code-planned source=default title="Declarative behaviour only"
…
ENFORCED: R1 by the verify gate — check_plan.py PLAN_ROUTE_MISMATCH
ENFORCED: R7 by check_rules.py --layout
```

| Exit | What to do |
|---|---|
| `0` | Written, and accepted. Commit it: `git add workspaces/.dgf-factory/RULES.md`, then `/dgf-commit`. |
| `1` | The file was refused (`RULES_FORMAT_INVALID`, `RULES_FORBIDDEN`, …). The skill repairs its own write, at most three times, then restores the file and stops. Every reader applies the shipped defaults until the file is accepted. |
| `2` | `RULES_TOUCHES_LIMIT`, `RULES_DEFAULT_EDITED` or `RULES_DEFAULT_MISSING`: read each line. |
| `3` | A usage error, or the shipped defaults do not parse: run `/dgf-doctor`. |

Your own rules start at R8: `/dgf-rules add "<rule>"`. A rule may only add a constraint; it never relaxes a check.

## Step 8: Plan the first change

Everything after the scaffold is ordinary brownfield work. Plan what the generator did not make:

```text
/dgf-plan full "record the inspection date on each permit"
```

The skill reads the root, checks its override and the rules, inventories the workspaces, researches the change,
asks what the evidence has not settled, cuts the branch `feature/<slug>` from your base branch, writes
`.dgf-factory/plans/feature-<slug>.md`, and checks it.

**What you will see** — the plan check, for example:

```text
Plan check
PLAN: .dgf-factory/plans/feature-record-the-inspection-date-on-each-permit.md mode=full format=1 branch=feature/record-the-inspection-date-on-each-permit
AFFECTS: inspections
TASK: 1 [ ] kind=config files=inspections/FM/_DATA/Permit/settings.xml
PROGRESS: 0/1
CHECKS RUN: plan-header, plan-tasks, plan-commits, plan-files, plan-routes, plan-overlap
…
CLEAN
```

| Exit | What to do |
|---|---|
| `0` | Read the plan. A full plan stops here, so you review it before anything is written. |
| `1` | The plan is defective. The skill fixes its own plan, at most three times, then stops with the findings. |
| `2` | Read each `WARN`: `PLAN_OVERLAP` (another branch's plan shares a workspace — `webasm` is shared by every plan), `PARITY_PARTIAL`, `PLAN_NOT_AUTHORED`, `PLAN_COMMITS_MISSING`. |
| `3` | `ROOT_NOT_SET_UP` → run `/dgf` first. Otherwise the skill relays the error. |

Commit the plan so it travels with its branch — `git add workspaces/.dgf-factory/`, then `/dgf-commit`, which suggests a
`docs(plan): …` message. Then carry on with [Add functionality](add-functionality.md), from its Step 4.

A database column the change needs is never written by a skill: the plan names it under `## Scope`, and
`/dgf-model` names the database work ([ADR 0010](../adr/0010-dgf-implement-scope.md) §3).

## See Also

- [Starting an application](../pipeline.md#starting-an-application) — what the scaffold generates, and what it does not know
- [Add functionality](add-functionality.md) — the route every later change takes
- [ADR 0026](../adr/0026-authoring-entry-point-revised.md) and [ADR 0027](../adr/0027-dgf-specific-skills-revised.md) §7 — why the scaffold works this way
