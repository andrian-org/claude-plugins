[← Add functionality](add-functionality.md) · [Guides](README.md) · [Back to README](../../README.md) · [Upgrade the DGF version →](upgrade-dgf-version.md)

# Check the System

The estate's health, not one change's: the install, the configuration and its reference graph, the team rules,
the generated docs, and the application's security.

## When to use this

Before a release, at a periodic review, when you take over an estate, or in CI. Nothing here is a gate on a
change — that is `/dgf-verify` ([Add functionality](add-functionality.md) Step 5). These checks read the whole
estate as it is, and report.

| Check | Skill | Reads | Writes |
|---|---|---|---|
| The install | `/dgf-doctor` | the receipt and the installed files | nothing |
| The configuration's health | `/dgf-audit` | every workspace, the reference graph per application | nothing |
| The team rules | `/dgf-rules-check` | the rules file, the workspace layout, the branch's diff | nothing |
| The estate docs | `/dgf-docs --check` | the configuration, and `.dgf-factory/docs/` | nothing in check mode |
| The application's security | `/dgf-security` | lock files, Dockerfiles, source code, images, a test site | its reports under `.dgf-factory/security/` |

## What you need

- dgf-factory installed, and the root set up by `/dgf`.
- For the security scan: Docker, or the scanners installed (Trivy, Gitleaks, Semgrep, OWASP ZAP), and the
  network. Without either, every step is a skip and the run is a warning, never a pass.

## Step 1: The install

```text
/dgf-doctor
```

It checks every file the receipt lists, every skill for every harness, the portability of the shipped files and
the validators' environment, and ends with its own `dgf-gate-result` block (`"gate": "doctor"`).

| Exit | What to do |
|---|---|
| `0` | Go on. |
| `1` | `INSTALL_FILE_MISSING`, `INSTALL_HARNESS_INCOMPLETE`, `INSTALL_RECEIPT_UNREADABLE`, `RUNTIME_PATH_DANGLING` and the like: run `dgf-factory setup` again, then the doctor. A broken install is never `/dgf-fix`'s. |
| `2` | `VALIDATOR_DEPS_MISSING`: run the command it prints. `INSTALL_FILE_EDITED`: setup keeps your edit and will not update that file. `INSTALL_VERSION_DRIFT`: run `dgf-factory setup`. |
| `3` | The runtime is incomplete: run `dgf-factory setup` again. |

`dgf-factory status` gives the same comparison from the terminal — every installed file and MCP entry against
the receipt, per harness — and writes nothing.

## Step 2: The configuration's health

```text
/dgf-audit
```

One script, `audit_root.py`, runs every validator over the root, builds the reference graph of each application
— that application plus `webasm`, a `webasm` file read as that application reads it — and lists every role name in
use ([ADR 0027](../adr/0027-dgf-specific-skills-revised.md) §4–§5).

**What you will see**, on a copy of DGF's own samples:

```text
Audit
APPLICATIONS: dgf zims (base webasm)
GRAPH: dgf nodes=1550 edges=2689 resolved=2300 unresolved=323 case-only=10 dynamic=56
EDGE: dgf process-action resolved=55 unresolved=43 case-only=0 dynamic=0
…
VALIDATOR: validate_process.py files=362 ERROR CHANGE_STATE_PROCESS_UNRESOLVED=9 ERROR CHANGE_STATE_STATE_UNDECLARED=1 ERROR WORKFLOW_UNRESOLVED=2 WARN UNREACHABLE_STATE=15 …
VALIDATOR: validate_model.py files=1217 ERROR MODEL_CELL_UNBOUND=15 ERROR MODEL_REFERENCE_UNRESOLVED=14 …
ROLE: "Case Officer" profile-group=1 sitemap-roles=3
ROLE: "CaseOfficer" task-role=1
…
WARN AUDIT_REFERENCE_UNRESOLVED webasm/FM/_WORKFLOW/AX.MoveCaseTo/_workflow.xml:24 record-table: `ZIGS_Cases` resolves nowhere in dgf — …; no validator checks this reference
INFO AUDIT_WORKFLOW_UNREACHED …
LIMIT: static reach only — names assigned at run time (_WORKFLOWNAME_, _FORMNAME_, _TABLENAME_), processes chosen from the database, … are not traced (knowledge/reference-graph.md §3)
CHECKS RUN: graph, validators, roles
NOT RUN: drafts (2 JSON files outside every FM/, which no loader reads)
NOT RUN: role-check (nothing in the root declares roles (knowledge/permissions.md §1))
BLOCKED
```

How to read it:

- **`VALIDATOR:` lines** count each validator's findings by code; each `ERROR` is listed too.
- **`AUDIT_REFERENCE_UNRESOLVED`** is a reference no validator checks yet that resolves nowhere, with the
  application it fails in.
- **`AUDIT_WORKFLOW_UNREACHED`** is a shared workflow no traced reference reaches: a **candidate**, never proof
  of dead code — an entry point outside processes may start it.
- **`ROLE:` lines** are an inventory, never checked: nothing in the root declares a role
  (`knowledge/permissions.md` §1). Each name is quoted exactly. `"Case Officer"` beside `"CaseOfficer"` is the
  drift worth a look; the runtime splits `roles` on `,` without trimming, so `" B"` is not `"B"`.
- **`LIMIT:`** is always there: a static walk cannot see names set at run time.

| Exit | What to do |
|---|---|
| `0` | Clean, or INFO only. |
| `1` | A validator `ERROR` in the root. On a real estate this is common: the findings were there before you. Plan each fix with `/dgf-plan`; the gate will credit each as `FIXED`. |
| `2` | `AUDIT_REFERENCE_UNRESOLVED`, `CASE_ONLY_MATCH`, or `AUDIT_NARROWED` (see below). Read each. |
| `3` | `DEPENDENCY_MISSING`: run the command it prints. `SCHEMA_UNSELECTABLE` naming a schema dialect: the runtime's defect — `/dgf-doctor`, then `dgf-factory setup`. `AUDIT_CHECK_FAILED`: a check raised; the report so far is incomplete. |

On a large estate, `/dgf-audit --app zims` audits one application and `webasm` only, for speed. It says
`AUDIT_NARROWED`: the other applications were not audited. `/dgf-audit --reach <file>` is a single file's blast
radius ([Add functionality](add-functionality.md) Step 2).

## Step 3: The team rules

```text
/dgf-rules-check
```

It runs `check_rules.py --layout` first — the rules file checked before anything reads it, and the scripted rule
R7, `layout-case`, over every workspace — then reads the branch's diff through `show_change.py` and judges each
prompt-only rule against it. Pass `--files <path>…` to judge named files. On the base branch with nothing changed
it reports the rules and the layout alone.

**What you will see:**

```text
RULES CHECK
RULES: none — no .dgf-factory/RULES.md
RULE: R1 enforcement=script check=means-route source=default title="XML-always for the five legacy artifact types"
…
ENFORCED: R1 by the verify gate — check_plan.py PLAN_ROUTE_MISMATCH
ENFORCED: R2 by the verify gate — check_change.py CHANGE_CODE_UNPLANNED and CHANGE_CODE_FILE_NEW
ENFORCED: R3 by the verify gate — check_plan.py PLAN_BASE_REASON_MISSING
ENFORCED: R7 by check_rules.py --layout
LAYOUT: dgf folders=8
LAYOUT: webasm folders=11
LAYOUT: zims folders=9
CHECKS RUN: layout-case
CLEAN
```

`RULES: none` means there is no rules file, and the six shipped defaults apply. The report then gives the
scripted results, each prompt-only rule's **Judgement**, and the rules not enforced. It is not a gate: R1, R2 and
R3 are decided by `/dgf-verify`.

| Exit | What to do |
|---|---|
| `0` | Read the report. |
| `1` | `RULES_LAYOUT_CASE`: a folder whose case the runtime never reads on Linux — fix it under a plan (`/dgf-plan`). Any other code (`RULES_FORMAT_INVALID`, `RULES_FORBIDDEN`, …): the rules file was refused and the shipped defaults applied; repair it with `/dgf-rules`. |
| `2` | `RULES_TOUCHES_LIMIT`, `RULES_DEFAULT_EDITED`, `RULES_DEFAULT_MISSING`: read each. |
| `3` | A bad call, or the shipped defaults do not parse: `/dgf-doctor`. |

## Step 4: The estate docs

```text
/dgf-docs --check
```

`estate_docs.py` renders the inventory pages — `index.md` and one page per workspace: processes with their
states and transitions, workflows, entities and relations, components, forms, role names — and compares them with
`.dgf-factory/docs/`. Check mode writes nothing. Without `--check`, `/dgf-docs` writes the pages and a short
`overview.md` from `DESCRIPTION.md` and the index.

**What you will see** when the pages were never written:

```text
Estate docs
PAGE: .dgf-factory/docs/dgf.md stale
PAGE: .dgf-factory/docs/index.md stale
…
WARN DOCS_STALE .dgf-factory/docs/dgf.md the page is missing — a write regenerates it
…
WARNINGS
```

| Exit | What to do |
|---|---|
| `0` | The docs are current. |
| `1` | `DOCS_PAGE_NOT_GENERATED`: a page named like a generated one has no marker, so it is someone's own text. Move or delete it yourself, then run `/dgf-docs`. |
| `2` | `DOCS_STALE`: run `/dgf-docs` to regenerate, then commit. (In write mode, `DOCS_SOURCE_UNREADABLE` names a file that does not parse; `/dgf-audit` says why.) |
| `3` | `DEPENDENCY_MISSING`, `ROOT_NO_WORKSPACE`, or a `paths.docs` outside `.dgf-factory/`. |

**In CI**, from the project folder, after the validators' environment is built:

```bash
python3 .dgf-factory/runtime/scripts/estate_docs.py --workspaces-root <root> --out .dgf-factory/docs --check
```

`<root>` is the workspaces root (`.` when it is the project folder). Exit `2` means stale; `1` that a page without
the marker sits where a generated one goes.

## Step 5: The application's security

```text
/dgf-security
```

This is the application's security, not the configuration's: one script, `security-scan.sh`, runs eight steps over
the project folder — runtime and framework versions, NuGet and npm dependencies, secrets in the files and git
history, configuration (Dockerfiles, Kubernetes, Helm, Terraform, `web.config`), code (Semgrep), container images,
a running test site (OWASP ZAP baseline), and an SBOM ([ADR 0034](../adr/0034-usage-scenarios-security-scan.md)
§1). It uses each scanner when it is installed, otherwise its pinned Docker image.

Options, only when you ask for them:

| Ask for | Example |
|---|---|
| a running **test** site — never production; ZAP sends real requests | `/dgf-security --url https://permits.test.example` |
| built images to scan, and add to the SBOM | `/dgf-security --image permits-api:1.4.0` |
| an image built from the project's `Dockerfile` | `/dgf-security --build` |

**What you will see** — one row per step, the result, the report path, then the verdict:

```text
== Dependencies ==
  NuGet packages                     SKIP  dotnet SDK not installed
  …
== Container image ==
  not run: pass --build, or --image NAME[,NAME...], to scan the images you ship
…
RESULT: INCOMPLETE (no failures in the checks that ran)
INCOMPLETE: 1 check(s) skipped; see the SKIP rows above.
Report: <project>/.dgf-factory/security/<date>_<time>_security-report.md
WARNINGS
```

A step you did not ask for — the image without `--image` or `--build`, the running site without `--url` — prints
a `not run:` line, not a row. A `SKIP` row is a step that should have run and could not: a scanner or Docker was
missing.

The report is Markdown, with the raw scanner output in a `<date>_<time>_raw/` folder beside it. A report folder
the scan creates gets a `.gitignore` of `*`, so no report reaches a commit. The skill relays the report's
"What to do next" list in order: secrets first, then dependencies, images, runtimes, the running site,
configuration and code. A secret's value is never printed.

| Exit | Verdict | What to do |
|---|---|---|
| `0` | `CLEAN` | Every step that ran passed, and none was skipped. |
| `1` | `BLOCKED` | A `FAIL` row. Fix each as the report's "How to fix" says, then scan again. Rotate a real secret at its provider first: removing it from the code does not remove it from git history. |
| `2` | `WARNINGS` | A `WARN` row for a person to check, or a `SKIP` row — a check that did not run. Install what the row asks for (Docker, or the scanner it names) and scan again; until then the result is incomplete. |
| `3` | — | A usage error, or a run that could not start. |

The skill never installs a scanner and never skips a step you did not name. The scan runs on macOS, Linux and
WSL; there is no Windows-native version.

## See Also

- [The DGF-specific skills](../pipeline.md#the-dgf-specific-skills) — the audit's scripts and exits in full
- [The quality and authoring skills](../pipeline.md#the-quality-and-authoring-skills) — rules, docs, security
- [Add functionality](add-functionality.md) — fixing what the audit found, one plan at a time
