[← Upgrade the DGF version](upgrade-dgf-version.md) · [Guides](README.md) · [Back to README](../../README.md) · [Pipeline Spine →](../pipeline.md)

# Migrate to DGF

Rebuild an old, non-DGF system on DotGov Framework.

> **There is no migration skill.** No `/dgf-migrate` exists, by decision
> ([ADR 0034](../adr/0034-usage-scenarios-security-scan.md) §2). An old system can be anything, and dgf-factory
> has no reader for its schema, so no script could check what a migration skill produced against its source. This
> guide is an **assessment route**: you read the old system, the skills check what you build from that reading.
> A migration skill will be reconsidered when a source system with a machine-readable model recurs across
> estates.

## When to use this

An existing system — a custom web application, a case-management product, a set of spreadsheets — is to be
replaced by a DGF application, or folded into an existing DGF estate.

This guide is not about converting a DGF file from legacy XML to JSON. That is a planned task of its own:
`/dgf-plan` gives it its own task and `route_means.py` decides the family, and `/dgf-implement` never converts a
file as a side effect of another task.

## What you need

- Access to the old system: its database schema, its screens, its case or approval flows, its user roles.
- Someone who knows what the old system is used for. The skills cannot tell you which of its features matter.
- dgf-factory installed ([Start a new project](start-a-new-project.md) Steps 1–3).

## The route at a glance

| Step | Who | Skill |
|---|---|---|
| 1. Inventory the old system | **you, by hand** | none |
| 2. See what is already DGF | the skills | `/dgf`, `/dgf-audit`, `/dgf-docs` |
| 3. Research how DGF does each piece | the skills, cited | `/dgf-explore`, `/dgf-grounded` |
| 4. Write the target | you, then the skills | `/dgf-scaffold` (a new application) or `/dgf-plan` (an existing estate) |
| 5. Build and check each piece | the skills | the [Add functionality](add-functionality.md) route |
| 6. Move the data, compare behaviour | **you, by hand** | none |

## Step 1: Inventory the old system (by hand)

No skill reads the old system. Write down, for each part of it, what it is and where it would go in DGF:

| In the old system | In DGF | Written by |
|---|---|---|
| A table you keep records in | an entity: `FM/_DATA/<Entity>/settings.xml`, and a table in the database project | `/dgf-scaffold` (`data_model.entities[]`) or `/dgf-model add` |
| A list-and-edit screen over one table | a `register` module: settings, a default form, a lookup view, a data source, a data table, a page, a route | `/dgf-scaffold` (`modules[]`, `pattern: register`) |
| A case that moves through approval states | a `service` module: a register plus a case process, a workflow per transition and a task per reviewing role | `/dgf-scaffold` (`pattern: service`), or `/dgf-process author` |
| A content page | a `page` module | `/dgf-scaffold` (`pattern: page`) |
| A user role | a role name, used in sitemaps, tasks and profile folders | `/dgf-scaffold` (`roles[]`); nothing in a root declares a role (`knowledge/permissions.md` §1) |
| The sign-in | `basic`, `dgpass` or `azure` per deployment | `/dgf-scaffold` (`auth[]`), recorded by `/dgf` |
| Custom behaviour, integrations, documents, reports | — | **not generated.** Each becomes a `/dgf-plan` plan later; what needs C#, SQL or a plugin assembly is out of scope for every plan ([ADR 0010](../adr/0010-dgf-implement-scope.md) §3) |

For each table, map its columns to a field `type` and `dbtype`. The SQL type each `dbtype` becomes is the
`field-sql-types` table of `knowledge/data-model.md` §6.3, derived from DGF's own samples:

| Old column | `type` | `dbtype` | Becomes |
|---|---|---|---|
| `VARCHAR(n)` | `Text` | `String`, `size: n` | `VARCHAR(n)` |
| `NVARCHAR(n)` | `Text` | `StringUnicode`, `size: n` | `NVARCHAR(n)` |
| `INT` | `Integer` | `Int32` | `INT` |
| `BIGINT` | `Integer` | `Int64` | `BIGINT` |
| `DECIMAL(p,s)` for money | `Money` | `Decimal`, `precision`, `scale` | `DECIMAL(p,s)` |
| `BIT` | `Boolean` | `Boolean` | `BIT` |
| `DATETIME` | `DateTime` | `DateTime` | `DATETIME` |
| a foreign key | `Lookup` or `Picklist` | the target key's `dbtype`, with `extract: {entity: …}` | the target key's type |

Every entity needs an `Integer` key and a `Text` field besides it. `PrimaryKey`, `Checkboxlist`, `EditableGrid`
and `Image` are not generated. The skill's `references/DESIGN-FORMAT.md` has every rule.

## Step 2: See what is already DGF

When part of the system already runs on DGF, set its root up and read it:

```text
/dgf <workspaces root>
/dgf-audit
/dgf-docs
```

`/dgf` inventories the workspaces (`WORKSPACE:` lines with their counts). `/dgf-audit` gives the validators'
findings, the reference graph per application and every role name in use. `/dgf-docs` writes an inventory page
per workspace — processes with their states, workflows, entities and relations, components, forms, roles — into
`.dgf-factory/docs/`. Compare those pages with your Step 1 inventory: what exists, what is missing, and where a
role name differs from the old system's.

| Exit | What to do |
|---|---|
| `/dgf`, `3`, `ROOT_NO_WORKSPACE` | Nothing here is DGF yet. Go to Step 4a. |
| `/dgf-audit`, `1` | Validator errors the estate already has. They are not the migration's; plan their fixes separately. |
| `/dgf-docs`, `2`, `DOCS_SOURCE_UNREADABLE` | A file does not parse; `/dgf-audit` says why. |

## Step 3: Research each piece

For each row of your inventory whose DGF form you are unsure of:

```text
/dgf-explore "how does DGF model a case with a two-step approval and a returned-to-applicant state?"
```

Every claim is cited — a knowledge section, a file and line in your root, or a docs MCP page — and anything no
source answers is listed as open. Save the answers: `.dgf-factory/RESEARCH.md` is what `/dgf-plan` reads later.
Use `/dgf-grounded "<question>"` when you need one answer held strictly to what can be cited.

## Step 4a: A new application — write the target as a design

Turn your inventory into one request, and let `/dgf-scaffold` write and check the design:

```text
/dgf-scaffold "a licensing application for two agencies, each its own workspace: a licence register, an application service reviewed by Licensing Officers, DGPass sign-in; entities Licence (Reference, Holder, IssuedOn, Fee) and LicenceType (Name)"
```

`design.py` checks every name, reference, field type and SQL type, asks for what is open, and prints every
default it applies. Follow [Start a new project](start-a-new-project.md) from Step 4. What the design cannot hold —
the custom behaviour, integrations and documents of the old system — the generated `docs/README.md` lists as
work for `/dgf-plan`.

## Step 4b: An existing estate — one plan per migrated piece

```text
/dgf-plan full "add the licence register migrated from the old system: entity Licence with Reference, Holder, IssuedOn and Fee"
```

One plan per entity, process or screen keeps each gate small. Cite the `RESEARCH.md` section each rests on. Follow
[Add functionality](add-functionality.md) from Step 3.

## Step 5: Build and check each piece

Every piece goes through `/dgf-implement` and `/dgf-verify`, like any change. `/dgf-model` names the database
work each entity needs and never writes SQL. `/dgf-qa` writes the manual test plan per reached process: use it to
compare each DGF process with the old system's flow.

## Step 6: Move the data and compare behaviour (by hand)

No skill moves data. Moving the old system's rows into the new tables is SQL, which no plan task writes
([ADR 0010](../adr/0010-dgf-implement-scope.md) §3). With more than one instance, each generated table carries the
framework's `ApplicationId` column, and isolation between instances is by that column alone: set it for every
migrated row. Then walk each `/dgf-qa` scenario against the old system's behaviour.

## See Also

- [ADR 0034](../adr/0034-usage-scenarios-security-scan.md) §2 — why there is no migration skill
- [ADR 0026](../adr/0026-authoring-entry-point-revised.md) — the scaffold, and brownfield after it
- [Start a new project](start-a-new-project.md) and [Add functionality](add-functionality.md) — the two routes this one feeds
