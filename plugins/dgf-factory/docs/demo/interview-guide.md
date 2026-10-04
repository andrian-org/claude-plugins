[Prep checklist](prep-checklist.md) · [Cheat sheet](cheat-sheet.md) · [Back to README](../../README.md)

# Interview Guide — Split Bill on DGF, built live with dgf-factory

A presenter's script for one to two hours with a hiring team. It shows two things you built: **DGF**, a
runtime for government services, and **dgf-factory**, a Claude Code plugin that builds on it. The story is
one application, *Split Bill*, made from an empty folder, run in the browser at phone width, then changed,
broken and fixed through the pipeline.

**The story in three sentences.** DGF is a runtime built from scratch: one Angular shell, one API, one
dispatcher, and an application is a folder of configuration it reads at request time. dgf-factory is a
Claude Code plugin that already knows that runtime: it generates an application from one design file, plans
and executes changes as configuration, and lets scripts, not the model, decide whether a change is sound.
Tonight it builds a split-bill app from nothing, the app runs, and the gate catches a deliberate mistake.

## How to read this guide

- **The core is 75 minutes.** A 60-minute cut and extensions up to 120 are in
  [Timeline and cut lines](#timeline-and-cut-lines).
- **Each act is a table.** *Min* is the minute mark. *Do* is what you type or click. *Say* is one or two
  sentences. *They see* is what is on screen. Every quoted output is copied from the rehearsal run on
  2026-10-04.
- **Checkpoints.** Where you should be: **0:17** doctor done · **0:31** the app answers its health URL ·
  **0:45** first commit · **1:00** the gate has failed once · **1:08** closing.
- **Two terminals.** Terminal 1 is Claude Code in `$APP`. Terminal 2 is a plain shell in `$COMPOSE`, with the
  variables from the [prep checklist](prep-checklist.md#variables) set.
- **Skill names.** If the night-before check showed namespaced names, type `/dgf-factory:dgf-scaffold` where
  this guide says `/dgf-scaffold`, and so on.

## Act 0 — The state of the room

Done before anyone arrives (the [T-30 list](prep-checklist.md#t-30)):

- The showcase stack is up, the catalogue has loaded once, and one e-service run has completed.
- `$APP` holds only `.git/` and `docs/application.json`, the unanswered design. The Split Bill tables, role and
  row are absent, and no `splitbill` container runs.
- Terminal 1 runs Claude Code in `$APP` with `--plugin-dir`, the `.venv` active, `/dgf-doctor` run once, then
  `/clear`.
- Browser tabs: the catalogue and Seq. The device toolbar preset is iPhone 14 Pro.
- The editor has `$APP` and the `dgf` workspace's `FM` folder open.

## Opening (0:00–0:05)

Who you are, in one breath. Then the two sentences everything rests on:

> "DGF is a runtime I built from scratch: one Angular shell, one API, one dispatcher, and a government service
> is a folder of configuration it reads at request time."
>
> "dgf-factory is a Claude Code plugin that already knows that runtime: it generates an application from one
> design file, plans and executes changes as configuration, and lets scripts, not the model, decide whether a
> change is sound."

What the next hour holds: a split-bill app from an empty folder, run on a phone-sized screen, changed through
the pipeline, broken on purpose, caught by the gate.

Draw one picture, on a whiteboard or one slide:

```text
browser ── Angular shell ── one API dispatcher ── component services (34, registered statically)
                                     │
                                     ▼
                     workspace  FM/_COMPONENTS   JSON pages, data sources, tables
                                FM/_DATA         XML entities, forms, views
                                FM/_PROCESS      XML state processes
                                FM/_WORKFLOW     XML workflows
                                     │ BASE:
                                     ▼
                     base workspace  webasm  (shared by every application)
```

## Act 1 — DGF running (0:05–0:17, questions included)

| Min | Do | Say | They see |
|---|---|---|---|
| 0:05 | Open `https://dgf.localtest.me/components` | "DGF's own showcase: one page per component, each a rendered example beside the configuration that produced it. Everything on screen is files." | The catalogue, about 60 entries in the sidebar |
| 0:06 | Sidebar: **ProcessFlow**. Fill Your reference, Full name, Email; **Next**; **Next** on Fee payment; **Next** on Review and sign | "A real state process over a real table: apply, pay, sign, decision. Each Next writes the case row and the state instance. Pay and sign go through stubbed government services." | The steps rail moving Apply → Pay → Sign → Decision; an invoice number `DGFINV…`; Paid flips to Yes |
| 0:09 | Editor: `dgf/FM/_PROCESS/DGF.Demo.EService/process.xml`, then `_WORKFLOW`, `_DATA`, `_COMPONENTS`, and `webasm` beside `dgf` | "Two tiers: the application over the base, and `BASE:` reaches down explicitly. Components are JSON; forms, views, workflows and processes are XML. Two schema families, both live, and a schema existing is not the runtime reading it." | The tree |
| 0:11 | In `process.xml`, change the `Issue` state's `title` to `Decision issued`; save; on the ProcessFlow page start a new application and look at the rail; then `git checkout -- process.xml` | "Read at request time, caching off in this stack: no build, no restart. And nothing checked that edit. That is the problem the builder solves." | The last step renamed |
| 0:13 | Device toolbar on, iPhone 14 Pro; reload `/components`, open a form page | "One grid, one mobile threshold, touch pickers below it. A workspace gets this without a line of CSS." | The phone layout |
| 0:15 | *(If the room is service-minded and time allows: the **Pay** page, a stub payment portal, the button settling on Paid.)* Pause | "Questions on the runtime before we build on it?" | — |

**Fallback.** If the stack is down, skip the browser rows and walk the `process.xml` and the folder tree in the
editor.

## Act 2 — From an empty folder to a running app (0:17–0:42, questions included)

| Min | Do | Say | They see |
|---|---|---|---|
| 0:17 | Terminal 1: `/dgf-doctor` | "Every quality command ends in a machine-readable block. A script computes the status; the model relays it." | `CLEAN`, then a `dgf-gate-result` block with `"status": "pass"` |
| 0:18 | Terminal 2: `ls -A "$APP" "$APP/docs"` | "An empty folder, a git repository, and one design file I wrote from the request. The skill would have written it from my sentence; I pre-wrote it to save your time." | `.git`, `docs`; `application.json` |
| 0:19 | Terminal 1: the scaffold prompt from the [cheat sheet](cheat-sheet.md) | "DGF ships no generator. A script checks the design, the skill asks only what is open, and every default is printed. Nothing is guessed." | Three questions |
| 0:20 | Answer: DGF version **1.1.15**; base path: the `webasm` path you printed the night before; supply: **mount** | "Mount: the base workspace is shared, so the app references it instead of copying three thousand files." | `DEFAULT: instance_model = "own-workspace"` |
| 0:21 | The skill shows the tree; answer **generate** | "The tree first, then it writes: a .NET solution, the database project, a compose stack, and the workspace — four entities with forms, views and data sources, five pages, and a settle-up process with one workflow per state." | `TARGETS: 68`, then `WROTE: 68 files, 0 copied` |
| 0:23 | The skill runs the post-generation check and reports | "Secrets are variables, the structure matches what the runtime needs, every route has a page, and the validators pass over what was generated." | `FILES: 68`, `WORKSPACES: splitbill`, `CHECKS RUN: secrets, structure, routes, validators`, `CLEAN` |
| 0:25 | Editor: `workspaces/splitbill/FM/_DATA/Expense/settings.xml` beside `database/SplitBill.Database/dbo/Tables/Expense.sql`; then `docs/data-model.md` | "One design entry, two files that agree: the entity the runtime reads and the table the database gets. `Paid by` is a lookup to Member, and it is a foreign key." | The two files |
| 0:27 | Terminal 2: `"$SB/apply-sql.sh" "$APP" "$COMPOSE"` | "DGF does not publish consumer images yet, so tonight the app runs on the framework's locally built images and its live database: the application row, one role, four tables." | `Seeded aspnet_Applications row for workspace 'splitbill'.`; `Created table dbo.BillGroup.` and three more |
| 0:28 | Terminal 2: `docker compose -f docker-compose.yml -f docker-compose.splitbill.yml up -d splitbill-api splitbill-ui`, then `curl -ks -o /dev/null -w '%{http_code}\n' https://splitbill-api.localtest.me/health/live` | "A second API and UI on the same stack, pointed at the generated workspace. Same images DGF's own consumer stacks use." | Two containers started; `200` |
| 0:30 | Browser: `https://splitbill.localtest.me/home` → **Sign In** → `admin` → **Menu** | "The generated home, login and menu. Nobody wrote a page." | Groups, Members, Expenses in the sidebar |
| 0:31 | **Groups** → **+** → Name *Lisbon trip*, Currency *EUR* → **Save and Close** | "A generated register: list, create, open." | Row 1 |
| 0:33 | **Members** → **+** → Group *Lisbon trip* from the lookup, Name *Ana* → **Save and Close** | "The group is a lookup. The list shows its name, not its id." | Row 1, *Lisbon trip*, *Ana* |
| 0:34 | **Expenses** → **+** → Group, Paid by *Ana*, Title *Dinner*, Amount *90*, Spent on: picker → **Today** → **Save and Close** | "Money and date fields, two lookups, all from the design." | Row 1, *Dinner*, *90* |
| 0:36 | Terminal 2: `sqlrun "$SB/seed-demo.sql"` | "Two more members and two more expenses by script, to save your time." | Ana 90.00, Ben 30.00, Chloe 60.00 |
| 0:37 | Device toolbar on → `https://splitbill.localtest.me/expenses` | "Same files, phone width. This is the generated JSON list page." | Three expenses, full width |
| 0:39 | Pause | "Questions on the scaffold or the runtime?" | — |

**Fallbacks.**

- **The scaffold skill misfires or asks something unexpected** → Terminal 2, from `$PLUGIN`:
  `python3 skills/dgf-scaffold/scripts/generate.py --folder "$APP"` after writing the three answers into
  `docs/application.json`; or restore `splitbill-generated.tgz`.
- **The app does not answer** → `docker compose logs --tail 80 splitbill-api`. A missing row or table: run
  `apply-sql.sh` again. Anything else: keep going in the editor; Act 3 needs no browser.
- **A page renders blank or 404** → enter through `/home` and the menu. A reload on a child route such as
  `/app-menu/expenses` shows a 404 by design. `docker restart splitbill-api` takes about 15 seconds.
- **The date will not take** → it ignores typed text; use the picker's **Today**.

## Act 3 — The pipeline on the new application (0:42–1:07)

| Min | Do | Say | They see |
|---|---|---|---|
| 0:42 | Terminal 1: `/dgf workspaces`. Answers: estate *Split Bill*, one sentence of purpose; version **1.1.15**; base branch **main**; prefix **feature/**; stack: override auth with *local basic sign-in* | "Set-up inventories the root and records which DGF version this estate runs, against the version the plugin's knowledge was read at. The mismatch is on record from day one." | `WORKSPACE: splitbill role=application processes=1 workflows=5 components=12 forms=4 settings=4 views=8`; a warning that the base is mounted, not present |
| 0:45 | `git add -A`, then `/dgf-commit` → **Commit as is** | "First commit. Conventional commits, scoped by workspace." | `chore(dgf): set up dgf-factory` |
| 0:46 | `/dgf-plan fast` with the change request from the [cheat sheet](cheat-sheet.md) | "The plan declares the workspace it touches and, per task, configuration or code and why. A script routes each new file — JSON for the data source and the page, XML for the process — and checks the plan before anything is written." | `.dgf-factory/PLAN.md`: three `kind: config` tasks; the plan check `CLEAN` |
| 0:49 | `/dgf-commit` the plan; `/dgf-implement` tasks 1 and 2 | "A raw SQL data source computing paid, share and balance, and a table on the balances page. Each task is validated against the last commit before its box is ticked." | `DataSource/Balances.json` (`"type": "rawsql"`, key aliased `[key]`); the page's `dataTable` with Group, Member, Paid, Balance |
| 0:52 | Browser, phone view: `https://splitbill.localtest.me/balances` | "Ana paid 90 of 180: she is owed 30. Ben paid 30: he owes 30. Chloe is square. No build, no restart." | Ana 30.00, Chloe 0.00, Ben −30.00 |
| 0:53 | `/dgf-implement` task 3 | "A legacy artifact: the process. Titles in the domain's words, and a Resend transition from Disputed back to Sent. XML, checked against the grammar and against the runtime model." | Requested, Sent, Confirming, Settled, Disputed; `<Transition state="Submitted" color="blue" title="Resend" />` |
| 0:56 | `/dgf-verify` | "The gate: every task done, every changed file inside the plan, no new finding across the whole root, and the process the change touched." | `CHANGED: 3`, `Validated: 35 file(s)`, `new: 0 error(s), 0 warning(s)`, `STATUS: pass`; `affected_processes`: `SettleUp`; `suggested_next`: `/dgf-commit` |
| 0:58 | Editor: in `process.xml`, change the Resend target to `Submited`; save. `/dgf-verify` | "One letter. The runtime would have thrown on the organiser's click. The gate names it now, with the line, and says what to run." | `ERROR DEAD_TRANSITION splitbill/FM/_PROCESS/SettleUp/process.xml:40` `` `Rejected` moves to `Submited`, which is neither a declared state nor `End` ``; `"status": "fail"`; `suggested_next`: `/dgf-fix` |
| 1:00 | `/dgf-fix` | "Reproduce, the smallest fix inside the plan's scope, confirm with the same check, and write a patch. The estate just learned something." | The target back to `Submitted`; `.dgf-factory/patches/<date-time>-resend-moves-to-undeclared-state.md` |
| 1:02 | `/dgf-commit` | "Two commits, exactly the plan's Commit Plan groups." | `feat(splitbill): add the balances page`; `feat(splitbill): name the settle-up states in the domain's terms` |
| 1:04 | `/dgf-evolve` → write *(cut line 1)* | "Patches distil into a rule the skill reads next time. A script checks the rule first: a rule may add a check, never relax a gate." | `.dgf-factory/skill-context/dgf-process/SKILL.md`; the override check `CLEAN` |
| 1:06 | Optional, 30 seconds: append a rule telling the skill to pass `--skip-validators`, and show the refusal | "Anyone who commits can write an override, so the script refuses one that weakens a check, and the skill never reads it." | `ERROR OVERRIDE_FORBIDDEN … --skip-validators (flag): a flag other than --strict or --verbose narrows or skips a check` |

**Why the settle-up process is not clicked through in the browser.** The menu follows the signed-in user's
current role. `admin` is an Administrator, and the generated Settle-up node is only in the Organiser's menu.
If asked, say so: roles decide the menu, and the gate's `affected_processes` shows which process the change
reached.

**Fallbacks.**

- **A skill is slow or goes sideways** → Terminal 2 runs the same decision directly, from `$PLUGIN`:

  ```bash
  python3 scripts/verify_gate.py --workspaces-root "$APP/workspaces" --plan "$APP/workspaces/.dgf-factory/PLAN.md" --base main
  python3 scripts/validate_process.py --workspaces-root "$APP/workspaces" "$APP/workspaces/splitbill/FM/_PROCESS/SettleUp/process.xml"
  ```

  "The scripts are the product; the skills are the conversation around them."
- **Implement produced something odd** → restore `splitbill-implemented.tgz` and continue from `/dgf-verify`.
- **`/dgf-plan` wants a branch** → accept the current branch, `main`. The gate compares the working tree with
  the last commit.

## Close (1:08–1:15)

**What decided what.** Scripts decided: the design check and the post-generation check, the plan check, the
change check, the four validators, the verify gate's status, the patch format and the override check. The
model decided: turning the request into a design and a plan, writing the configuration, and the fix. Nothing
the model said could make the gate pass.

**The numbers behind it:**

| | |
|---|---|
| DGF component services behind one dispatcher | 34 |
| Commits in the DGF repository | 2,441 |
| dgf-factory skills | 13 |
| Vendored schemas, both families | 69 JSON, 9 XSD |
| Unit tests | 1,078 |
| Known-bad cases, one per blocking finding | 95 |
| Architecture decision records | 27 |

Every DGF fact the plugin ships is stamped with the DGF version and the digest of the source it was read
from, and a maintainer tool re-checks those digests against a checkout.

**Where to get it.** `claude plugin marketplace add andrian-org/claude-plugins`, then
`claude plugin install dgf-factory@andrian-org`.

**What is next**, in your own words: for DGF, published consumer images and a NuGet feed, so a generated app
runs on its own compose file; for dgf-factory, the review, rules and QA skills, and refreshing the knowledge
base to the current DGF release.

### Q&A crib

| Question | One-line answer |
|---|---|
| Is this BPMN? | No. A state machine whose states run XML workflows; `process.xml` is the runtime format ([ADR 0014](../adr/0014-process-verification-runtime-resolution.md)). |
| JSON or XML? | Both, by design. Components are JSON, the five legacy artifacts are XML, and the runtime-parity table says which the runtime actually reads (`knowledge/schema-families.md` §6). |
| Can it write C#? | Out of scope by decision. A plan may name code under Scope, but no task writes C#, SQL or TypeScript ([ADR 0010](../adr/0010-dgf-implement-scope.md)). |
| Does the generated app run on its own? | It builds and checks clean. DGF does not yet publish the four artifacts its own compose file needs: base, database baseline, UI image, feed. That is why it ran on the showcase's images tonight. |
| What if the model is wrong? | The gate does not trust it. Scripts compute the status, and the known-bad corpus is the proof each blocking finding fires ([ADR 0022](../adr/0022-gate-block-contract-revised.md)). |
| How do you keep the knowledge current? | Every fact is stamped and ledgered; `tools/check_drift.py` compares the ledgers with a DGF checkout and names what moved ([ADR 0013](../adr/0013-version-gating-provenance-ledger.md)). |
| Why Python for the validators? | No standard library validates XSD or JSON Schema, and a plugin cannot install its own dependencies. Python with `lxml` and `jsonschema`, missing ones reported as exit 3 ([ADR 0015](../adr/0015-validator-runtime-and-json-reader.md)). |
| Why would a gate block on old problems? | It does not. It blocks only on findings the change introduced, against the merge-base ([ADR 0018](../adr/0018-change-relative-gates.md)). |
| Can the learning loop make things worse? | An override may only tighten. A script refuses a weakening rule before any skill reads it ([ADR 0024](../adr/0024-learning-loop-revised.md)). |
| Roles? | Global by name, partitioned by application id. The scaffold writes each role once and documents why (`knowledge/application-layout.md` §3.1). |

## Timeline and cut lines

| Version | Segments | Minutes |
|---|---|---|
| **75** (core) | Opening 5 · Act 1 12, with 2 of questions · Act 2 25, with 3 of questions · Act 3 26 · Close 7 | 75 |
| **60** | The core minus: `/dgf-evolve` and the override refusal (3), the Pay row and the catalogue phone view (3), the hand-entered Members and Expenses rows — seed them all with `seed-demo.sql` (4), the editor walk in Act 2 shortened to the two files (2), the questions merged into the close (3) | 60 |
| **120** | The core plus the six extensions below | 120 |

**Cut lines, in order:** `/dgf-evolve`; the override refusal; the Pay row; the catalogue phone view; the
hand-entered member and expense; the tree walk in Act 2.

### Extensions to 120 (+45)

| After | Min | What |
|---|---|---|
| Act 1 | 10 | **How DGF is built.** The one dispatcher (`ComponentsController`), the static component registry (`ComponentServiceProvider` — why a validator is possible at all), `WorkspaceSettings` (`webasm`, `FmPath`, `FmBasePath`), and the parity table: `Workflow` and `ProcessFlow` have JSON schemas the runtime ignores. |
| Act 1 | 5 | The **Pay** page and the **Monitor** page: a stub payment portal, a receipt, and the process diagram drawn from `FM/_PROCESS`. |
| Act 3 | 6 | `/dgf-audit` over the new root, then `/dgf-audit --reach splitbill/FM/_WORKFLOW/SettleUp.InReview/_workflow.xml`: blast radius before a change, and the `LIMIT:` line saying what a static walk cannot see. |
| Act 3 | 8 | **How it is kept honest.** Start the unit suite in Terminal 2 at the top of Act 3 (`.venv/bin/python -m unittest discover -s tests -t .` from `$PLUGIN`, about a minute, 1,078 tests); open `tests/fixtures/known-bad/process-dead-transition/expected.json`; run `tools/check_drift.py "$DGF"`; the ADR index. |
| Act 3 | 10 | **A card layout for phones.** Ask `/dgf-plan fast` for a `listBox` of `card` items over the same Balances data source, one column on small screens, and take it through implement and verify once more, with the room predicting the gate's verdict. Not rehearsed: use it only with time to spare. |
| Close | 6 | Longer Q&A. |

## What to expect at the end

- **In the browser.** `https://splitbill.localtest.me`, signed in as the administrator. Groups holds *Lisbon
  trip*; Members holds Ana, Ben and Chloe; Expenses holds Dinner 90.00, Taxi 30.00 and Tickets 60.00. At phone
  width, `/balances` shows Ana 30.00, Chloe 0.00 and Ben −30.00. The showcase at
  `https://dgf.localtest.me/components` is unchanged.
- **In `$APP`.** The generated application: `SplitBill.slnx`, `src/Api/`, `database/SplitBill.Database/` with
  four table scripts and two seed scripts, `docker/`, and `docs/` with the design — 68 generated files plus the
  design. Under `workspaces/splitbill/`: the pages, four entities, the settle-up process and its five
  workflows, and the new `DataSource/Balances.json`. Under `workspaces/.dgf-factory/`: `config.yaml`,
  `DESCRIPTION.md`, `PLAN.md` with three ticked tasks, one patch, and the `dgf-process` override.
- **In git.** Five commits on `main`:

  ```text
  chore(dgf): evolve a rule for /dgf-process from the Resend patch
  feat(splitbill): name the settle-up states in the domain's terms
  feat(splitbill): add the balances page
  docs(plan): plan the balances page and the settle-up states
  chore(dgf): set up dgf-factory
  ```

  The messages `/dgf-commit` and `/dgf-evolve` propose may be worded slightly differently.
- **In the terminal.** The doctor's block (`pass`), the scaffold check (`CLEAN`), two verify blocks — `pass`,
  then `fail` naming `DEAD_TRANSITION` with `suggested_next: /dgf-fix` — a third `pass` after the fix, and the
  override check `CLEAN`.
- **In the database.** One `aspnet_Applications` row for `splitbill`, the `Organiser` role, and four tables
  holding the entered rows. The [reset recipe](prep-checklist.md#reset-recipe) removes all of it.

## Rehearsal log

| Date | What | Result |
|---|---|---|
| 2026-10-04 | Showcase stack start, warm | about 10 seconds; `up.sh` stopped at step 6 on the seed container's exit, the stack was healthy |
| 2026-10-04 | E-service run on the ProcessFlow page | Apply → Pay → Sign → Decision; the case row paid, signed, at status 4 |
| 2026-10-04 | Scaffold scripts: design check, dry run, generate, check | exit 2 with three questions, then 0; `TARGETS: 68`; `WROTE: 68 files, 0 copied`; `CLEAN` |
| 2026-10-04 | Hosting, sign-in, three registers, phone view | all worked; see the [spike's findings](prep-checklist.md#what-the-spike-taught) |
| 2026-10-04 | Act 3 through the scripts the skills call | plan check `CLEAN`; gate `pass`, `fail` (`DEAD_TRANSITION`), `pass`; patch check `CLEAN`; override check `CLEAN`, then `OVERRIDE_FORBIDDEN` |
| 2026-10-04 | Reset recipe | database clean (0 rows, 0 roles, 0 tables); folder restored; design check back to three questions |
| 2026-10-04 | Act 2's terminal commands, from the reset state, as the cheat sheet prints them | generate and check 1 s; `apply-sql.sh`, both containers, health `200` and `seed-demo.sql` 5 s; the seed run twice changes nothing |
| 2026-10-04 | The reset recipe, as written | database clean, folder restored, design check back to three questions |
| — | The whole core through the skills in Claude Code, against the clock | **not yet run.** Do it the night before: follow the cheat sheet only, write the stopwatch time at each checkpoint here, and note every question a skill asked that the cheat sheet does not answer |
