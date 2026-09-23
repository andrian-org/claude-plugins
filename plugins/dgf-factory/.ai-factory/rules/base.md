# Project Base Rules — dgf-factory

> Auto-detected conventions from codebase analysis. Edit as needed.
>
> Evidence base: the AI Factory 2.18.1 corpus in `.claude/skills/aif-*`, the helper
> scripts in `.claude/skills/aif/references/` and `.claude/skills/aif-skill-generator/scripts/`,
> and the sibling plugin `plugins/doc-coverage-audit/`.

## Naming Conventions

- **Directories:** kebab-case (`aif-skill-generator/`, `doc-coverage-audit/`, `plugin-structure/`)
- **Skill directories:** kebab-case, prefixed by the skill family (`dgf-*`, `aif-*`)
- **Skill entry file:** exactly `SKILL.md`, uppercase — auto-discovery matches this name only
- **Supporting directories inside a skill:** `references/`, `scripts/`, `templates/`, `examples/`
- **Markdown docs:** kebab-case (`manifest-reference.md`, `component-patterns.md`);
  top-level project documents are SCREAMING-CASE (`README.md`, `ARCHITECTURE-BLUEPRINT.md`, `AGENTS.md`)
- **Shell/Node scripts:** kebab-case (`update-config.mjs`, `validate.sh`, `graph_helper.sh` is the outlier)
- **Python scripts:** the corpus is split — `aif-*` helpers use kebab-case filenames
  (`security-scan.py`, `cleanup-blocked-skill.py`), `doc-coverage-audit` uses snake_case
  (`walk_tree.py`, `render_report.py`). **For new code: use snake_case for Python files**
  so they stay importable as modules, kebab-case for everything else.
- **JavaScript identifiers:** camelCase functions and locals, SCREAMING_SNAKE_CASE module constants
  (`SECTION_KEYS`, `ALLOWED_PATHS`, `SECTION_ORDER`)
- **Python identifiers:** snake_case functions, leading underscore for private helpers
  (`_add`, `_normalize_rel_path`), SCREAMING_SNAKE_CASE constants (`THREAT_PATTERNS`, `ALL_EXTENSIONS`)

## Module Structure

- `<plugin>/.claude-plugin/plugin.json` — the manifest. Must live in `.claude-plugin/`;
  every component directory must live at plugin root, never nested inside it.
- `<plugin>/skills/<name>/SKILL.md` — one directory per skill, auto-discovered
- `<plugin>/agents/*.md` — subagent definitions, auto-discovered
- `<plugin>/scripts/` — shared runtime validators that skills call. **Shipped.**
- `<plugin>/knowledge/` — stamped DGF facts and the vendored schema set. **Shipped.**
- `<plugin>/tools/` — repo-maintenance checks and the schema vendoring tool that
  contributors run by hand. **Not shipped.** A maintenance tool never goes in `scripts/`.
- `<plugin>/provenance/` — one ledger per knowledge file: the DGF files its facts came from,
  each with a `sha256`. **Not shipped.**
- `.ai-factory/` — pipeline artifacts, single-writer ownership per command
- Intra-plugin paths use `${CLAUDE_PLUGIN_ROOT}`. Never hardcode absolute paths,
  `~/` shortcuts, or working-directory-relative paths.
- **No DGF repository paths in shipped files.** "Shipped" is `SHIPPED_DIRS` in
  `skills/dgf-doctor/scripts/doctor.py`. A developer's install has no DGF checkout, so a
  shipped file names a DGF source by knowledge file, DGF docs MCP call
  (`get_doc_page('<page>')`) or type name, never by path. A fact's source paths go in its
  `provenance/` ledger, never in `knowledge/`. Workspace layout paths such as
  `FM/_COMPONENTS/` are fine. `doctor.py` reports a violation as `DGF_PATH`, exit `1`
  ([ADR 0012](../../docs/adr/0012-no-dgf-paths-in-shipped-files.md)).
- **Re-vendor schemas only with `tools/vendor_schemas.py`.** Never copy or hand-edit a file
  under `knowledge/schemas/`. The tool rewrites DGF paths and regenerates the digests, and a
  hand edit fails `tools/check_knowledge_stamps.py`.

## Skill Authoring

Skills are written **prompt-as-program**, not as prose descriptions: numbered steps,
explicit gates, mandatory outputs, and "STOP and report" conditions.

Required frontmatter:

```yaml
---
name: <skill-name>            # matches the directory name
description: <trigger phrases — this is what makes the skill fire>
argument-hint: "[...]"        # when the skill takes arguments
allowed-tools: <explicit allowlist, narrowed with Bash(cmd *) where possible>
disable-model-invocation: false
version: 1.0.0
---
```

- `allowed-tools` is an allowlist, not a formality. Narrow `Bash` to specific command
  prefixes (`Bash(git *)`, `Bash(shasum -a 256 *)`) rather than granting bare `Bash`.
- `description` carries the trigger phrases. It is the only thing that decides whether
  the skill fires, so write it for matching, not for elegance.

## Error Handling

- **Single exit helper.** Scripts define one `fail(code, message)` / `sys.exit(code)`
  path rather than scattering exits. Errors go to stderr; normal output to stdout.
- **Exit codes are a contract** consumed by the skills that call these scripts:

  | code | meaning |
  |---|---|
  | 0 | clean / success |
  | 1 | blocked — refuse to proceed (unsafe structure, critical finding) |
  | 2 | warnings — proceed, but surface them to the user |
  | 3 | usage error — bad arguments or invalid payload |

  Never reuse a code for a different meaning, and never let a pipe mask it
  (`cmd | tail` returns `tail`'s status — capture the real code before piping).
- **Validate input before acting.** Reject unknown keys, unsupported value types and
  malformed payloads up front instead of writing a partial result.
- **Never silently fall back.** If a helper reports an unsafe structure, STOP and report;
  do not hand-roll the output the helper refused to produce.

## DGF Schema Handling

DGF supports two configuration formats — modern JSON component config and legacy XML —
because it still runs systems written against the older one. These rules are expressed
through the exit codes above.

- **Resolve the family before parsing.** XML declaration or a known XSD root element →
  XSD family. Parses as a JSON object → JSON family.
- **Unknown or ambiguous family → exit 3 (usage error).** Never fall back to JSON.
  Defaulting to JSON makes every legacy XML config look like malformed JSON.
- **Valid against neither family → exit 1 (blocked)**, reporting which families were
  attempted.
- **Parity gate.** After a successful family match, consult runtime parity. A config in a
  family the runtime does not parse for that component — `Workflow`, `ProcessFlow`, and
  every `◐` row in DGF's `format-coverage.md` — is **exit 2 (warning)** at minimum,
  reporting `schema-valid but not runtime-supported`. Passing schema validation is not
  proof of runtime support.
- **Never infer a counterpart from a filename.** `options.xsd` is not
  `StaticOptionsDataSource`. Use the verified correspondence map in `docs/dgf-schemas.md`.
- **Resolve JSON schemas the way `SchemaIndexService` does, not by globbing.** Honour the
  standalone allow-list, the DataSource discriminators (`table`, `rawsql`, `static`, …),
  and the exclusion of `$ref`-only sub-schemas (`RowConfig`, `SectionConfig`,
  `IDataSource`, `InputGroupConfig`).
- **Select the JSON Schema dialect per file** from its own `$schema` — the vendored set
  mixes draft-04 (generated) and draft-07 (hand-authored).
- **Quote every schema path.** One filename contains a backtick
  (``NumberConfiguration`1.schema.json``), which triggers command substitution unquoted.

## Control Flow

- Prefer flat, readable control flow over deeply nested conditionals. Use guard clauses,
  early `return`/`continue`, small named helper methods, or explicit classification logic
  when they make the code easier to follow. Handle edge cases and irrelevant branches
  early so the main path stays visible.
- Small single-purpose functions. The helper scripts average well under 30 lines per
  function; keep new ones in that range.

## Determinism

- Anything a script can decide must never be left to the model. Prefer a validator
  script over a prompt instruction wherever the question is statically answerable.
- Validators are pure: read input, emit a report, exit with a contract code. No network
  calls, no mutation of the thing being validated.

## Logging

- No logging framework. Scripts print directly to stdout/stderr.
- Structured, labelled report sections with an explicit summary block and a final verdict
  line (`CLEAN`, `BLOCKED`, `WARNINGS`), as in `security-scan.py`.
- ANSI colour constants are defined once at module top (`RED`, `YELLOW`, `GREEN`, `BOLD`, `NC`).

## Security

- Every externally sourced skill is scanned before use — automated scan plus a manual
  read of every file — and a blocked result means removal, not a judgement call.
- Credentials in MCP configuration are `${VAR}` placeholders. Never commit literal
  secrets; `.gitignore` already excludes `gtok.txt`, `aztok.txt`, `dc.json`.

## Files and Encoding

- **LF line endings, enforced repo-wide** by `.gitattributes`. CRLF breaks shebangs and
  heredocs in plugin scripts on macOS/Linux.
- UTF-8, no BOM.
