[Back to README](../../README.md) · [Getting Started](../getting-started.md) · [Start a new project →](start-a-new-project.md)

# Usage Guides

These guides are for developers on a DGF delivery team who use dgf-factory on their own estate. You know
DotGov Framework. You do not need to know how dgf-factory is built.

Each guide is one scenario, walked step by step. Every step gives the command you type, what you will see
(the script's lines and its exit code), and a short table: for each exit, what to do next. Where no skill
exists for a step, the guide says so and gives the manual route.

## The five scenarios

| Guide | Use it when | Who it is for | Skills it uses |
|---|---|---|---|
| [Start a new project](start-a-new-project.md) | You have an empty folder and a request for a new DGF application | A team starting a new system | `dgf-factory setup`, `/dgf-doctor`, `/dgf-scaffold`, `/dgf`, `/dgf-rules`, `/dgf-plan`, `/dgf-commit` |
| [Add functionality](add-functionality.md) | You change an estate that already runs on DGF — a new form, a process step, a field, a fix | Every developer, every day | `/dgf-explore`, `/dgf-audit --reach`, `/dgf-plan`, `/dgf-implement` (or `dgf-implement-coordinator`), `/dgf-component`, `/dgf-process`, `/dgf-model`, `/dgf-verify`, `/dgf-fix`, `/dgf-review`, `/dgf-qa`, `/dgf-commit`, `/dgf-archive` |
| [Check the system](check-the-system.md) | You want the estate's health, not a change's: before a release, at a review, in CI | Leads, reviewers, release owners | `/dgf-doctor`, `/dgf-audit`, `/dgf-rules-check`, `/dgf-docs --check`, `/dgf-security` |
| [Upgrade the DGF version](upgrade-dgf-version.md) | The estate moves to a newer DGF release | The developer who owns the upgrade | **No upgrade skill.** A guided route: `dgf-factory setup`, `/dgf-explore`, `/dgf`, `/dgf-audit`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify` |
| [Migrate to DGF](migrate-to-dgf.md) | An old, non-DGF system is to be rebuilt on DGF | The analyst or lead who plans the migration | **No migration skill.** An assessment route: `/dgf-audit`, `/dgf-explore`, `/dgf-grounded`, `/dgf-scaffold` or `/dgf-plan` |

Upgrade and migration have no skill of their own, by decision
([ADR 0034](../adr/0034-usage-scenarios-security-scan.md) §2, §3). Their guides use the skills that exist and
say plainly which part is yours to do by hand.

## Before any guide

- **Install once.** dgf-factory is an npm CLI. [Start a new project](start-a-new-project.md) Step 1 installs it;
  [Getting Started](../getting-started.md#installing-it-in-a-project) has the detail.
- **Start your harness from the project folder.** The installed skills call their scripts through the
  project-relative `.dgf-factory/runtime/`, so the harness must run where `dgf-factory setup` ran.
- **One workspaces root.** The unit of work is the whole workspaces root — every workspace, `webasm` included —
  and `.dgf-factory/` sits once at that root ([ADR 0026](../adr/0026-authoring-entry-point-revised.md) §3).

## Typing the commands

The guides write each command as you type it in Claude Code. The installed skills are rewritten for the
harness you chose ([ADR 0029](../adr/0029-npm-cli-delivery.md) §3):

| Harness | You type |
|---|---|
| Claude Code | `/dgf-plan full "…"` — the form these guides use |
| Codex (CLI and app) | `$dgf-plan full "…"` |
| Qwen Code | `/skills dgf-plan full "…"` |
| Any other harness | The skill text keeps `/dgf-plan`; invoke the `dgf-plan` skill the way that harness invokes skills |

The scripts still print the Claude Code form — a gate block suggests `/dgf-fix`, not `$dgf-fix`
([ADR 0029](../adr/0029-npm-cli-delivery.md) §8). Read it as your harness's form.

Two things are Claude Code's alone. The skills ask their questions with `AskUserQuestion`; other harnesses read
those questions as plain instructions, so you answer them in the chat. And the parallel
`dgf-implement-coordinator` agent runs only in Claude Code; everywhere else, `/dgf-implement` does the tasks one
at a time.

## Reading what a step prints

Every script prints the same shape, so you can read any step the same way:

1. a header line, then the script's own lines — `ROOT:`, `PLAN:`, `CHANGE:`, `PROCESS:` and so on;
2. `CHECKS RUN: …` — only these ran;
3. `NOT RUN: <check> (<reason>)` — a check that did not run. It is never a pass;
4. one line per finding: `ERROR`, `WARN` or `INFO`, a code such as `DEAD_TRANSITION`, the file, the message;
5. a `Summary`, then the verdict word: `CLEAN`, `WARNINGS` or `BLOCKED`.

The exit code says the same thing as a number:

| Exit | Meaning | In general |
|---|---|---|
| `0` | clean | Go on. |
| `1` | blocked | Something is wrong. The `ERROR` lines say what, and the skill stops or tells you which skill fixes it. |
| `2` | warnings | Go on, but read every `WARN` line. |
| `3` | usage error, or the check could not run | Fix the call or the install. `DEPENDENCY_MISSING` prints the command that installs the validators. |

`INFO PRE_EXISTING` marks a finding the estate already had before your branch. It never blocks, and no skill
fixes it unless you ask ([ADR 0018](../adr/0018-change-relative-gates.md)).

Two skills end with a `dgf-gate-result` block: `/dgf-verify` (the gate on a change) and `/dgf-doctor` (the
install). Every other skill is a report. Its findings matter, but it never passes or fails a change.

## See Also

- [Pipeline Spine](../pipeline.md) — every skill, every script, and every exit table in one page
- [Getting Started](../getting-started.md) — installing, and running the scripts on their own
- [Decision Records](../adr/README.md) — why each step works the way it does
