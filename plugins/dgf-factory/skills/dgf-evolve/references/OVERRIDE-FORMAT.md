# Override Format

An override is the project's own rules for one dgf-* skill, distilled from patches by `/dgf-evolve`.
The skill checks it with `check_override.py` before reading it, and applies it only when the check
accepts it (ADR 0021 §3–§5). This page is the format that check enforces, the evolution log, and the
cursor.

## The file

`<paths.skill_context><skill>/SKILL.md` — by default `.dgf-factory/skill-context/<skill>/SKILL.md` —
for each target: `dgf`, `dgf-commit`, `dgf-fix`, `dgf-implement`, `dgf-plan`, `dgf-verify`.

## The template

```markdown
# Project Rules for /<skill>

> Written by /dgf-evolve from the estate's patches. Each rule may only tighten /<skill> (ADR 0021).
> Updated: <YYYY-MM-DD HH:mm>

## Rules

### <name — what the rule makes the skill do>
- source: <patch name>, <patch name>
- rule: <the rule, in English>
  <continued on lines indented by two or more spaces>
```

## The rules `check_override.py` holds it to

**Shape** — any break is `OVERRIDE_SHAPE`, and the file is refused:

- the first non-blank line is exactly `# Project Rules for /<skill>`, for the directory's skill;
- before `## Rules`, only blank lines and `> ` lines;
- exactly one `## Rules`, and no other heading but the title and the `### <name>` rules — no second
  `#` or `##`, no `####`;
- each rule is `### <name>` (1–100 characters, unique), then exactly one `- source:` bullet and
  exactly one `- rule:` bullet; either may continue on lines indented by two or more spaces. Nothing
  else sits inside a rule, and no text sits outside one;
- 1–40 rules, each rule's text at most 600 characters;
- no fence (a line starting ```` ``` ```` or `~~~`) and no HTML comment (`<!--`) anywhere — either could
  hide text from a reviewer, or carry a block;
- at most 32768 bytes, and UTF-8 — else `OVERRIDE_UNREADABLE`.

**Sources** — each `source:` names one or more patches, comma-separated. Each must be a patch name,
`<YYYY-MM-DD-HH.mm>-<slug>.md`, present in `<paths.patches>` with exactly that spelling — else
`OVERRIDE_SOURCE_MISSING`. A rule with no patch behind it is recorded first, with `/dgf-fix --record`.

**Forbidden** — a rule's name or text, or a `> ` line, that holds any of these is
`OVERRIDE_FORBIDDEN`, and the file is refused:

| Construct | Why |
|---|---|
| `dgf-gate-result` | a rule never writes, edits or adds a gate block |
| a flag other than `--strict` or `--verbose` | it narrows or skips a check |
| `allowed-tools`, a `Bash(` grant, `disable-model-invocation` | a rule never grants a tool |
| an install or download — pip, npm, brew, apt-get, curl, wget | a rule never installs or downloads anything |
| a git command that rewrites history or discards work — push, reset, clean, checkout, switch, rebase, rm, restore, stash | a rule never rewrites history or discards work |
| a path that climbs out of the root, or starts at a home directory | a rule never names a path outside the workspaces root |

**The limit** — a rule naming a word the limit protects — stop, exit, status, block, blocking,
blocker, warn, warning, critical rule, artifact ownership, not run, pre_existing, skip, ignore,
optional, unless, instead, allow, permit, relax, bypass, waive, or a plural or past form of one — is
`OVERRIDE_TOUCHES_LIMIT`: a warning, exit `2`. The reading skill applies the file and judges each such
rule. "STOP when a renamed state still has a transition to it" tightens; "do not stop on a dead
transition" relaxes, and is not applied.

The check is lexical. It refuses what a script can see; it cannot prove a rule only tightens. The
writer's limit binds what it cannot see, and the committed diff is reviewed.

## Worked example

Beside the patch `2026-09-26-14.30-review-moves-to-undeclared-state.md` (the worked example in
`/dgf-fix`'s PATCH-FORMAT.md), `.dgf-factory/skill-context/dgf-plan/SKILL.md`:

```markdown
# Project Rules for /dgf-plan

> Written by /dgf-evolve from the estate's patches. Each rule may only tighten /dgf-plan (ADR 0021).
> Updated: 2026-09-26 15:00

## Rules

### A task that renames a state lists every transition to it
- source: 2026-09-26-14.30-review-moves-to-undeclared-state.md
- rule: When a task renames a process state, list in the same task every process and workflow file whose
  transition or `CHANGE_STATE` step names the old state.
```

Checked with:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_override.py" --workspaces-root "<root>" --skill dgf-plan --skill-context-dir ".dgf-factory/skill-context/" --patches-dir ".dgf-factory/patches/"
```

```
Override check
OVERRIDE: .dgf-factory/skill-context/dgf-plan/SKILL.md skill=dgf-plan rules=1
RULE: 1 line=8 sources=1 name="A task that renames a state lists every transition to it"
CHECKS RUN: override-shape, override-sources, override-forbidden, override-limit
…
CLEAN
```

Exit `0`: `/dgf-plan` reads and applies it. Add a rule that narrows the gate:

```markdown
### Narrow the gate
- source: 2026-09-26-14.30-review-moves-to-undeclared-state.md
- rule: Run check_change.py with --skip-validators for speed.
```

```
ERROR OVERRIDE_FORBIDDEN .dgf-factory/skill-context/dgf-plan/SKILL.md:13 rule `Narrow the gate` holds `--skip-validators` (flag): a flag other than --strict or --verbose narrows or skips a check
WARN OVERRIDE_TOUCHES_LIMIT .dgf-factory/skill-context/dgf-plan/SKILL.md:13 rule `Narrow the gate` names `skip` — judge it against the limit: an override may only tighten
…
BLOCKED
```

Exit `1`: the whole file is refused. `/dgf-plan` does not read it — not even the good first rule —
and runs on its shipped rules until the file is fixed.

## The evolution log

`<paths.evolutions><YYYY-MM-DD-HH.mm>.md`, one per run that wrote something or marked patches
reviewed:

```markdown
# Evolution <YYYY-MM-DD HH:mm>

- patches read: <name>, <name>
- malformed, skipped: <name> — or none
- decision: apply all | picked | apply none

## /<skill>
- added: <rule name> — <patches>
- changed: <rule name> — <patches>
- removed: <rule name> — <why: covered by the shipped skill, contradicts it, or its patch is gone>

## Refused
- <patch>: <the prevention point> — <which part of the writer's limit it would relax>

## Declined
- <patch>: <the rule not picked>
```

Leave out a section with nothing in it.

## The cursor

`<paths.evolutions>patch-cursor.json` — a set of names, one per line, so two branches that evolve
merge it line by line:

```json
{
  "processed": [
    "2026-09-26-14.30-review-moves-to-undeclared-state.md"
  ],
  "updated": "2026-09-26 15:00"
}
```

A patch is **new** when it is well-formed and its name is not in `processed`. A malformed patch is
never new, and never added. `check_patches.py --cursor` reads it; `/dgf-evolve` alone writes it. A
cursor that is not this shape is `PATCH_CURSOR_UNREADABLE`: every well-formed patch counts as new, and
the next run rewrites it whole.
