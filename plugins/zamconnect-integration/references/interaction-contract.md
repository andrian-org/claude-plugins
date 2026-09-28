# Interaction contract

Every zamconnect-integration skill that asks the developer anything follows these rules. Each skill defines
*what* it asks. This file defines *how*.

`AskUserQuestion` limits that shape the rules: 1–4 questions per call, 2–4 options per question.
**Other** (free text) is always added automatically and never has to be listed. `multiSelect` is
available. The tool does not exist inside a subagent, so a skill run by an agent gets every answer
as a flag.

## Rules

| Rule | Requirement |
|---|---|
| **R1 Flag parity** | Every question has a flag. When the flag is present, the question is not asked. When one skill runs another, it passes the answers as flags, so nothing is asked twice |
| **R2 Structured only** | Ask through `AskUserQuestion`, never with a plain-text question in the reply. There is one exception: a lone free-text value with nothing on disk to offer as options, such as the name of a brand-new tenant. Keep the option order fixed and move `(Recommended)` to the option it applies to. The header is ≤12 characters, e.g. `Step 2/6`, `Source`, `Auth` |
| **R3 Other is the text field** | **Other** is the only text input that works in both the CLI and VS Code, and it *replaces* the choice. Use it only for a value that can't be listed, such as a URL or path. Say so once, in the question text (e.g. "…or paste a URL or path in Other"), never in option descriptions. Read `annotations[q].notes` when present, but never make a note the only way to give a value |
| **R4 Required inputs in the gate** | If a step needs an input that has no safe default, ask it in the same call as the gate. Inputs that do have a default appear only under `Customize…` |
| **R5 Options from the repo** | Build options from what exists: files found on disk, the tenant's own modules, the agency register, the pipeline state. Generic labels are the last resort |
| **R6 Review before write** | Once every input is settled and before the first file is written, make one call. The question text holds the plan: files to create or change, routes, and the equivalent command. Options: `Apply (Recommended)`, `Adjust`, `Cancel`. `Adjust` asks a `multiSelect` listing the earlier questions, then re-asks only the ones picked |
| **R7 Echo the command** | After the step, print the fully-flagged command that reproduces it |
| **R8 State** | When run from `tenant-pipeline`, answers and the step result go to the state file (below). Earlier answers become the `(Recommended)` defaults on the next run |
| **R9 More than 4 choices** | Group first, then drill down (category, then items). Or spread the items over up to 4 `multiSelect` questions in one call (16 items). Offer `All …` as an option when it makes sense |
| **R10 Headless** | With `--auto`, every question takes its `(Recommended)` option. If a required input has no default, stop and name the flag: `missing --source <url|path>`. Never guess |
| **R11 Echo interpretation** | After parsing free text or a file, state what was understood before acting on it: "Read as: WSDL, SOAP 1.1, 5 operations". If it's ambiguous, re-ask only that question |
| **R12 Every option is a complete answer** | Selecting an option must be enough to act on. **No option may tell the user to pick another option** ("Pick Other and give the path" is forbidden). If the answer needs a value, either the value *is* the option (a discovered file, a detected header) or a follow-up question asks for it. Never ask for what can be detected: source type, protocol, SOAP version, existing modules, the current document version |
| **R13 Missing required arguments** | A skill invoked without a required argument asks for it before anything else, never guesses it and never falls back to a default the developer didn't pick. See [Missing arguments](#missing-arguments). Under `--auto` it stops instead and names the argument: `missing <TenantName>` |
| **R14 Help** | `--help` (or `-h`) anywhere in the arguments makes the skill print its own help and stop: the `argument-hint` line, then one row per argument with its default and whether it is required (and asked for under R13 when missing), then two or three example commands built from real tenant names in the repo. It wins over every other argument, asks nothing, runs no command that changes anything and writes nothing, the state file included. Gate-mode flags that only `tenant-pipeline` passes (`--gate`, `--recommend`) are listed last, marked internal |

## Missing arguments

Each skill lists its required arguments in its `## Arguments` section. When one is missing, and the
skill isn't running under `--auto`, ask for it first, in one `AskUserQuestion` call that holds
every missing required argument (≤4 questions), before any scan, gate or build.

**Existing tenant** (every skill except `tenant-init`). Header `Tenant`. Build the options from
the repo (R5), at most 3, in this order and without duplicates:

1. Tenants with a state file: `ls .claude/zamconnect/*.pipeline.json`
2. Tenants changed most recently:
   ```bash
   git log --name-only --format= -- src/Tenants | awk -F/ 'NF > 3 { print $3 }' | awk '!s[$0]++'      | while read t; do ls "src/Tenants/$t/$t.csproj" >/dev/null 2>&1 && echo "$t"; done | head -3
   ```

Only folders holding `<T>.csproj` count. The question text says "…or type another tenant name in
Other" (R3). A skill that also works on every tenant (`tenant-audit`) adds `All tenants` as the
fourth option. Check a typed name against `src/Tenants/<T>/<T>.csproj`: when it isn't there, name
the closest existing folders (case-insensitive prefix match) and ask again. Don't create the
tenant. Point to `/tenant-init <T>` instead.

**New tenant** (`tenant-init`). There's nothing on disk to offer, so ask in plain text (the R2
exception). Accept only a PascalCase name (`^[A-Z][A-Za-z0-9]*$`) with no existing
`src/Tenants/<T>/` folder. Otherwise say why and ask again.

**Other required inputs** (a source, a route) follow the skill's own question for that input,
asked right after the tenant is settled.

Once the arguments are settled, the skill echoes the command with them filled in (R7), so the
next run can pass them.

## The gate

A step run from `tenant-pipeline` opens with a gate. The options are always these four, in this order:

| Option | Meaning |
|---|---|
| `Proceed` | Run now with the defaults listed in the option's description |
| `Customize…` | Ask the step's optional questions first, then run |
| `Skip` | Leave the step undone and continue the chain |
| `Stop` | End the chain here. State is kept for `--resume` |

`(Recommended)` normally goes on `Proceed`, or on `Skip` for a step the intake says isn't needed.
The description of `Proceed` names the defaults, e.g. "Full coverage matrix, all modules, no live
fixture". A note on `Proceed` counts as a customization and is applied without another prompt.

When the step has a required input with no default (R4), that question goes in the **same call** as
the gate. If the gate answer is `Skip` or `Stop`, its answer is ignored.

### Gate mode

`tenant-pipeline` doesn't build gates itself. It runs each step skill with `--gate <n>/<N>`, and
the skill opens with its own gate. Each skill knows its defaults, its required inputs and its
`Customize…` questions, and those are listed in its `## Gate` section. The pipeline may also pass
`--recommend proceed|skip` to say where `(Recommended)` goes.

A skill in gate mode ends with exactly one of these lines, which the pipeline reads:

```
GATE-RESULT: ran
GATE-RESULT: skipped
GATE-RESULT: stopped
GATE-RESULT: failed <one-line reason>
```

With no `--gate`, a skill runs normally: no gate, just its own questions for whatever flags are missing.

## Dry run

Every skill that writes files accepts `--dry-run`. It runs up to the R6 review, prints the plan and
the equivalent command, and writes nothing, the state file included.

## State file

`.claude/zamconnect/<Tenant>.pipeline.json` in the ZamConnect repository. The first time the
directory is created, also write `.claude/zamconnect/.gitignore` containing `*`, so the state stays
local without editing the repository's own `.gitignore`. It lives outside `src/Tenants/<Tenant>/`
because the tenant `Dockerfile` copies that folder into the image.

```json
{
  "tenant": "PQPS",
  "updated": "2026-09-23T10:42:00Z",
  "answers": {
    "style": "carter",
    "integrates": ["soap"],
    "fullName": "Plant Quarantine and Phytosanitary Service",
    "integrations": [
      { "sources": ["src/Tenants/PQPS/Deliverables/Integration Requests/pqps.wsdl"], "system": "Pqps", "auth": "Basic", "role": "provide" }
    ]
  },
  "steps": [
    { "n": 1, "skill": "tenant-init", "status": "ran", "command": "/tenant-init PQPS --full-name \"Plant Quarantine and Phytosanitary Service\" --integrates soap" },
    { "n": 2, "skill": "tenant-integration", "status": "ran", "command": "/tenant-integration PQPS --source \"…/pqps.wsdl\" --auth Basic --role provide" },
    { "n": 3, "skill": "integrate-shared", "status": "skipped" },
    { "n": 4, "skill": "tenant-tests", "status": "stale" }
  ]
}
```

`status` is one of `ran`, `skipped`, `failed`, `stale`, `pending`. State holds answers and
commands only: never a credential, and never a host name, IP or identifier copied from a source
file or collection. The `Sensitive data` rules of every skill apply to it.
