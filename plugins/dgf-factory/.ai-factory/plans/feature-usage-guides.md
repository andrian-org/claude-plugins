# Implementation Plan: Usage Guides (and the security scan's place)

Branch: none (worked on `main`'s working tree; the user commits)
Created: 2026-11-03

## Original Request

"plan, improve, implement, and verify each unresolved roadmap item … do it yourself without asking me" — roadmap
milestone **Usage Guides**: one guide per scenario under `docs/`, each a step-by-step route through the skills with
the gates you will see and what to do on each exit; where a scenario has no skill, say so and give the manual
route. Its fifth bullet asks first to decide where `scripts/security-scan.sh` lives and how a skill calls it.

## Roadmap Linkage

Milestone: "Usage Guides"

## Decisions

[ADR 0034](../../docs/adr/0034-usage-scenarios-security-scan.md): the scan ships in the runtime and conforms to the
exit contract (`0`/`1`/`2` with a skipped step a warning/`3`), claims no Windows twin, ignores its own reports, and
runs behind `/dgf-security`, which writes only `paths.security`; no migration skill (an assessment route); upgrade
is a guided route through `/dgf-explore`, `/dgf`, `/dgf-audit`, `/dgf-plan` and `/dgf-verify`.

## Tasks

### Phase 1: The scan (independent of the other milestones)

- [x] Task 1: `scripts/security-scan.sh` — usage errors exit `3`; a run that cannot start (not a folder, no
  `docker` and no scanner for a step is a SKIP, not this) exits `3`; final exit `1` on any FAIL, else `2` on any
  WARN or SKIP, else `0`; the last line is `CLEAN`, `WARNINGS` or `BLOCKED`; the header comment says macOS, Linux
  and WSL; when it creates the `--out` folder it writes a `.gitignore` of `*` there; `--help` says all of this.
  Keep everything else byte-for-byte. `bash -n` clean; `shellcheck` if installed.
- [x] Task 2: `tests/test_security_scan.py` — `--help` exit 0 and lists every option; an unknown option and
  `--history x` exit 3; `--path` to a missing folder exits 3; a run with `--skip` of every step over a scratch
  folder exits 2 with `WARNINGS` last and writes a report and the `.gitignore` (no Docker needed: every step
  skipped). Skip the run test when `bash` is absent.
- [x] Task 3: `skills/dgf-security/SKILL.md` — read-only toward the estate; `allowed-tools: Read Glob Grep
  Bash(bash "{{dgf_runtime}}/scripts/security-scan.sh" *) AskUserQuestion`; Step 0 `locate_plan.py --root-only` is
  NOT needed — the scan targets the project folder (the git toplevel or the current folder), so it asks which
  folder when not given and takes `paths.security` from `.dgf-factory/config.yaml` when present; options: `--url`
  only when the user names a **test** URL (never production — ask), `--image`, `--build`; exit table for 0/1/2/3;
  relays the step table, `RESULT:`, `Report:` and the "what to fix first" list; DON'T: install scanners, pass
  `--skip` unasked, scan a URL the user did not name as a test environment. `tests/test_skill_contracts.py`:
  `dgf-security` in `READ_ONLY`? No — it writes reports through the script, not with a write tool, so it is
  read-only for tools: add it to `READ_ONLY` and `NO_GIT`; extend `PLUGIN_PYTHON`-style matching so a
  `bash "{{dgf_runtime}}/scripts/…"` call must match a Bash rule too.

### Phase 2: The guides (after the Quality & Authoring Skills and Parallel Execution milestones)

- [ ] Task 4: `docs/guides/README.md` — the index: five scenarios, who each is for, the skills each uses.
- [ ] Task 5: `docs/guides/start-a-new-project.md` — `npm`/`.npmrc` install, `dgf-factory setup`, `/dgf-doctor`,
  `/dgf-scaffold` in an empty folder (design file, its checks, the generated root), `/dgf`, `/dgf-rules init`,
  the first `/dgf-plan`.
- [ ] Task 6: `docs/guides/migrate-to-dgf.md` — no migration skill (ADR 0034 §2): the assessment route.
- [ ] Task 7: `docs/guides/upgrade-dgf-version.md` — the version-delta route (ADR 0034 §3).
- [ ] Task 8: `docs/guides/add-functionality.md` — `/dgf-explore` → `/dgf-audit --reach` before a shared
  workflow → `/dgf-plan` → `/dgf-implement` (or the parallel coordinator) with `/dgf-component`, `/dgf-process`,
  `/dgf-model` → `/dgf-verify` → `/dgf-review`, `/dgf-qa` → `/dgf-commit` → `/dgf-archive`; `/dgf-fix` on a new
  finding.
- [ ] Task 9: `docs/guides/check-the-system.md` — `/dgf-audit`, `/dgf-rules-check --layout`, `/dgf-docs --check`,
  `/dgf-security`.
- Every guide: the nav header the doc check requires; per step the command, what you will see (the script's
  lines and exit), and a table "exit → what to do"; cites ADRs and knowledge sections; no DGF repository path;
  claims nothing the code does not do — every command, flag and code quoted is checked against the scripts.
- [ ] Task 10: README and AGENTS.md link the guides; `docs/getting-started.md` points to them; ROADMAP tick.
- [ ] Task 11: verify — the doc check, the suite, a pass over every guide's quoted commands and codes against
  `--help` and `report.CODES`.
