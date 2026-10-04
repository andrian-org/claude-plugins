[Interview guide](interview-guide.md) · [Cheat sheet](cheat-sheet.md)

# Prep Checklist — Split Bill interview demo

What has to be true before the room, how to get there, and how to reset after a rehearsal. Every command
below ran on the demo machine on 2026-10-04.

## Variables

Set these once, in every terminal you will use. Nothing else in these pages names a path.

```bash
export DGF="$HOME/workspaces/dotgov/_DotGovFramework/DotGovFramework"
export COMPOSE="$DGF/src/samples/DGF.Compose"
export PLUGIN="$HOME/workspaces/dotgov/dotgov-claude-plugins/plugins/dgf-factory"
export SB="$PLUGIN/docs/demo/splitbill"
export APP="$HOME/demo/splitbill"

# Run one SQL file against the stack's database, inside the SQL Server container.
sqlrun() {
  docker cp "$1" dgf-sqlserver:/tmp/run.sql >/dev/null &&
  docker exec dgf-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa \
    -P "$(grep -E '^MSSQL_SA_PASSWORD=' "$COMPOSE/.env" | cut -d= -f2-)" -C -I -W -d DGF -b -i /tmp/run.sql
}
```

`-I` matters: `AspNetRoles` has a filtered index, and SQL Server refuses an insert into it with
`Msg 1934` unless quoted identifiers are on.

## Decision: S1 — the generated application runs on the showcase stack

Decided 2026-10-04, about 25 minutes into a 75-minute spike. Fallback F, which would have put Split Bill
inside the `dgf` workspace, is not needed.

DGF publishes no consumer API image, UI image, NuGet feed or database baseline yet, so the application's own
`docker/docker-compose.yml` cannot start on this machine. Instead, one compose override runs its workspace on
the images the showcase stack builds from source, against the same SQL Server and Redis. That is how DGF's
consumer stacks already run.

What the spike ran, in order, with what each step printed:

| Step | Result |
|---|---|
| `generate.py` into `$APP` from the answered design | `WROTE: 68 files, 0 copied`; `--check` CLEAN |
| `"$SB/apply-sql.sh" "$APP" "$COMPOSE"` | `Seeded aspnet_Applications row for workspace 'splitbill'.`, one role row, then `Created table dbo.BillGroup.`, `dbo.Member`, `dbo.Settlement` and `dbo.Expense`, in foreign-key order |
| the override's `up -d splitbill-api splitbill-ui` | both containers started |
| `https://splitbill-api.localtest.me/health/live` | `200` within 3 seconds |
| `https://splitbill.localtest.me/home`, then Sign In as `admin` | signed in as "Local Administrator"; no role change needed |
| Menu, Groups, the create button | the generated `FORM:default` opens in a modal; *Lisbon trip* saved |
| Members, create | the Group lookup lists *Lisbon trip*; *Ana* saved; the list shows the group by name |
| Expenses, create | both lookups, the money field and the date picker work; *Dinner* 90.00 saved |
| `/expenses` and `/balances` at 393 × 852 | full width, every row; the balances read Ana 30.00, Chloe 0.00, Ben −30.00 |

## What the spike taught

- **`up.sh` may stop at step 6** with `container dgf-demo-seed exited (0)`. That is `--wait` treating the
  one-shot seed container as a failure. The stack is up anyway; check the health URL directly.
- **The menu follows the user's current role.** `admin`'s current role is `Administrators`, which has no
  profile folder, so the tree falls back to `Members`: Groups, Members and Expenses. The `Organiser` folder
  holds the Settle-up node, and it stays hidden even after `admin` is given that role. The settle-up process is
  shown in the pipeline act, as XML the gate checks, not in the browser.
- **Type no date.** The date field ignores typed text. Open the picker and press **Today**.
- **Switch to the phone view first, then enter through Home.** Changing the viewport reloads the page, and a
  reload on a child route such as `/app-menu/expenses` shows a 404. Top-level routes such as `/expenses` and
  `/balances` reload fine.
- **Two kinds of list page.** The menu's legacy grid (`/app-menu/...`) keeps the sidebar beside the table on
  a phone, so the table scrolls sideways. The generated JSON list pages (`/groups`, `/members`, `/expenses`)
  and the balances page use the full width. Show the phone view on those.
- **The create form's heading reads `default`**, the form's name. It is cosmetic and comes from the
  generator's form template.
- **A lookup shows the target entity's first text field**, so `Name` stays the first text field of
  `BillGroup` and `Member`.
- **Never start `splitbill-api` before the application is generated.** Docker creates a missing bind-mount
  source as an empty folder, and `$APP/workspaces/splitbill` appearing early makes the scaffold refuse the
  folder as not empty.

## Night before

1. **Plugin clean.** In `$PLUGIN`, on branch `feature/hackathon-demo-guide`:

   ```bash
   .venv/bin/python skills/dgf-doctor/scripts/doctor.py | tail -3     # CLEAN
   ```

   If it warns `ABSOLUTE_PATH` under `skills/dgf-scaffold/templates/solution/`, an IDE build left `obj/` or
   `bin/` there: `git clean -fdX skills/dgf-scaffold/templates/solution/` removes only ignored files.
2. **Stack up.** `cd "$COMPOSE" && ./up.sh`. Warm, it takes about 10 seconds. Then
   `curl -ks -o /dev/null -w '%{http_code}\n' https://dgf-api.localtest.me/health/live` prints `200`.
   Never `./up.sh --clean`: re-publishing the database on emulated SQL Server is the slow path.
3. **Hosting files in place.** They were copied during the spike; re-copy after any change to them:

   ```bash
   cp "$SB/docker-compose.splitbill.yml" "$COMPOSE/docker-compose.splitbill.yml"
   mkdir -p "$COMPOSE/configs/splitbill"
   cp "$SB/appsettings.splitbill.json" "$COMPOSE/configs/splitbill/appsettings.json"
   cp "$SB/ui-appsettings.splitbill.json" "$COMPOSE/dgf-ui/appsettings.splitbill.json"
   grep '^SPLITBILL_APP=' "$COMPOSE/.env"     # SPLITBILL_APP=<your home>/demo/splitbill
   ```

   If the last line prints nothing: `printf 'SPLITBILL_APP=%s\n' "$APP" >> "$COMPOSE/.env"`.
4. **Plugin loads.** From a shell with the validators' environment active:

   ```bash
   source "$PLUGIN/.venv/bin/activate"
   cd "$APP" && claude --plugin-dir "$PLUGIN"
   ```

   Type `/dgf-doctor`. Note whether the skills appear as `/dgf-doctor` or `/dgf-factory:dgf-doctor`, and
   write that on the cheat sheet. The skills call a bare `python3`, so a shell without the `.venv` active makes
   every validator exit `3`, `DEPENDENCY_MISSING`.
5. **The scaffold's base path, copied.** The survey asks for an absolute path; print it now and keep it on
   the second screen: `echo "$DGF/src/samples/workspaces/webasm"`.
6. **One full rehearsal** from the reset state below, against the clock. Then reset again.

## T-30

1. `docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'dgf-(api|ui|sqlserver|redis|traefik)'` — all up.
2. `https://dgf.localtest.me/components` loads; run the e-service on the ProcessFlow page once.
3. The reset state, checked:

   ```bash
   ls -A "$APP" "$APP/docs"                   # .git and docs; application.json
   docker ps --format '{{.Names}}' | grep splitbill || echo "no splitbill containers running"
   ```

4. Terminal 1: `source "$PLUGIN/.venv/bin/activate"`, `cd "$APP"`, `claude --plugin-dir "$PLUGIN"`,
   `/dgf-doctor` once, then `/clear`.
5. Terminal 2: the variables above, `cd "$COMPOSE"`.
6. Browser: tabs on `https://dgf.localtest.me/components` and Seq at `https://dgf-logs.localtest.me`. Close
   any `splitbill.localtest.me` tab. Device toolbar preset: iPhone 14 Pro (393 × 852).
7. Editor: windows on `$APP` and on `$DGF/src/samples/workspaces/dgf/FM`. Font sizes up.

## Reset recipe

Run it after every rehearsal. It removes the Split Bill rows, role, tables and generated files, and leaves the
showcase untouched.

```bash
cd "$COMPOSE"
docker compose -f docker-compose.yml -f docker-compose.splitbill.yml stop splitbill-api splitbill-ui
sqlrun "$SB/reset.sql"                      # tables dropped, role removed, row removed
mv "$APP" "$APP.used-$(date +%H%M)"         # keep the run for reference; delete it later
tar xzf "$HOME/demo/splitbill-empty.tgz" -C "$HOME/demo"
```

`splitbill-empty.tgz` holds the pre-demo state: an empty `main` repository and the unanswered design. Check it
with `python3 "$PLUGIN/skills/dgf-scaffold/scripts/design.py" --folder "$APP"`: three `SCAFFOLD_ASK` lines and
`DEFAULT: instance_model = "own-workspace"`. If the browser still holds a Split Bill session, sign out or
close the tab.

## Restore points

| File in `$HOME/demo` | State |
|---|---|
| `splitbill-empty.tgz` | before the demo: `.git` and the unanswered design |
| `splitbill-generated.tgz` | right after generation, nothing committed |
| `splitbill-implemented.tgz` | after the three changes, before the break; its database needs `apply-sql.sh` and `seed-demo.sql` |
| `splitbill-final.tgz` | the end state: five commits, the patch and the override |

The rehearsed repository carries tags at each step: `demo/1-set-up`, `demo/2-planned`, `demo/4-committed`,
`demo/5-evolved`.

## Never on screen

- `$COMPOSE/.env`: the SQL `sa` password, the admin password and the Registration Authority's private key.
- `docker exec … sqlcmd … -P …` with the password expanded: use `sqlrun` or `apply-sql.sh`, which read it.
- The admin password itself. Type it with the screen share paused, or let the browser fill it.

## Files the demo adds outside this repository

All untracked, all removable:

| Where | What |
|---|---|
| `$COMPOSE/docker-compose.splitbill.yml` | copy of [splitbill/docker-compose.splitbill.yml](splitbill/docker-compose.splitbill.yml) |
| `$COMPOSE/configs/splitbill/appsettings.json` | copy of [splitbill/appsettings.splitbill.json](splitbill/appsettings.splitbill.json) |
| `$COMPOSE/dgf-ui/appsettings.splitbill.json` | copy of [splitbill/ui-appsettings.splitbill.json](splitbill/ui-appsettings.splitbill.json) |
| `$COMPOSE/.env` | one appended line, `SPLITBILL_APP=` |
| `$HOME/demo/` | the application folder and the four restore points |
| database `DGF` | while running: the `splitbill` row, the `Organiser` role, four tables; [splitbill/reset.sql](splitbill/reset.sql) removes them |
