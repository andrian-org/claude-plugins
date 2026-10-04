[Interview guide](interview-guide.md) · [Prep checklist](prep-checklist.md)

# Cheat Sheet — the 75-minute core

Second screen. T1 is Claude Code in `$APP`, T2 a shell in `$COMPOSE`, B the browser. ✂ marks a cut line.

**Checkpoints:** 0:17 doctor · 0:31 app healthy · 0:45 first commit · 1:00 gate failed once · 1:08 close.

## Opening 0:00 · Act 1 0:05

| Min | Where | Do |
|---|---|---|
| 0:05 | B | `https://dgf.localtest.me/components` |
| 0:06 | B | ProcessFlow → fill → **Next** ×3 |
| 0:09 | editor | `dgf/FM/_PROCESS/DGF.Demo.EService/process.xml`, the four FM folders, `webasm` |
| 0:11 | editor | `Issue` state `title` → `Decision issued`, save, new application on ProcessFlow, then `git checkout -- process.xml` |
| 0:13 | B | device toolbar, iPhone 14 Pro, a form page |
| 0:15 | — | ✂ Pay page · questions |

## Act 2 0:17

| Min | Where | Do |
|---|---|---|
| 0:17 | T1 | `/dgf-doctor` |
| 0:18 | T2 | `ls -A "$APP" "$APP/docs"` |
| 0:19 | T1 | the scaffold prompt, below |
| 0:20 | T1 | answers: **1.1.15** · the `webasm` path · **mount** |
| 0:21 | T1 | **generate** |
| 0:25 | editor | `FM/_DATA/Expense/settings.xml` beside `dbo/Tables/Expense.sql`; ✂ `docs/data-model.md` |
| 0:27 | T2 | `"$SB/apply-sql.sh" "$APP" "$COMPOSE"` |
| 0:28 | T2 | `docker compose -f docker-compose.yml -f docker-compose.splitbill.yml up -d splitbill-api splitbill-ui` |
| 0:29 | T2 | `curl -ks -o /dev/null -w '%{http_code}\n' https://splitbill-api.localtest.me/health/live` → `200` |
| 0:30 | B | `https://splitbill.localtest.me/home` → Sign In `admin` → Menu |
| 0:31 | B | Groups **+** *Lisbon trip*, *EUR* |
| 0:33 | B | ✂ Members **+** *Lisbon trip*, *Ana* |
| 0:34 | B | ✂ Expenses **+** *Lisbon trip*, *Ana*, *Dinner*, *90*, picker **Today** |
| 0:36 | T2 | `sqlrun "$SB/seed-demo.sql"` |
| 0:37 | B | phone view → `https://splitbill.localtest.me/expenses` |
| 0:39 | — | questions |

The scaffold prompt:

```text
/dgf-scaffold a split-bill web app for a group of friends: groups, their members, expenses one member paid and everyone splits equally, a settle-up request that a group organiser confirms, and a balances page — local sign-in, mobile friendly
```

## Act 3 0:42

| Min | Where | Do |
|---|---|---|
| 0:42 | T1 | `/dgf workspaces` → *Split Bill*, purpose · **1.1.15** · **main** · **feature/** · auth: *local basic sign-in* |
| 0:45 | T1 | `git add -A`, `/dgf-commit` → **Commit as is** |
| 0:46 | T1 | the plan prompt, below |
| 0:49 | T1 | `/dgf-commit` the plan · `/dgf-implement` tasks 1–2 |
| 0:52 | B | phone view → `https://splitbill.localtest.me/balances` → Ana 30.00 · Chloe 0.00 · Ben −30.00 |
| 0:53 | T1 | `/dgf-implement` task 3 |
| 0:56 | T1 | `/dgf-verify` → `pass` |
| 0:58 | editor | `SettleUp/process.xml`, Resend `state="Submitted"` → `Submited`; T1 `/dgf-verify` → `fail`, `DEAD_TRANSITION` |
| 1:00 | T1 | `/dgf-fix` |
| 1:02 | T1 | `/dgf-commit` |
| 1:04 | T1 | ✂ `/dgf-evolve` → write |
| 1:06 | editor | ✂ append a `--skip-validators` rule to the override → `OVERRIDE_FORBIDDEN`, then undo |

The plan prompt:

```text
/dgf-plan fast add a Balances page showing, per group and member, what they paid, their equal share and their balance, from a raw SQL data source; and make the settle-up process speak the domain: Requested, Sent, Confirming, Settled, Disputed, with a Resend transition from Disputed back to Sent
```

## Close 1:08

What scripts decided · the numbers · `claude plugin install dgf-factory@andrian-org` · what is next · Q&A.

## When something breaks

| Symptom | Do |
|---|---|
| a skill stalls | T2, from `$PLUGIN`: `python3 scripts/verify_gate.py --workspaces-root "$APP/workspaces" --plan "$APP/workspaces/.dgf-factory/PLAN.md" --base main` |
| app not answering | `docker compose logs --tail 80 splitbill-api` · re-run `apply-sql.sh` |
| blank page or 404 | enter through `/home` and Menu · `docker restart splitbill-api` |
| implement went wrong | restore `splitbill-implemented.tgz`, continue at `/dgf-verify` |
| validators exit 3 | the `.venv` is not active in the shell that started `claude` |
