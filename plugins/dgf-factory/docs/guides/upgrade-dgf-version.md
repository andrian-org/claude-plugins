[← Check the system](check-the-system.md) · [Guides](README.md) · [Back to README](../../README.md) · [Migrate to DGF →](migrate-to-dgf.md)

# Upgrade the DGF Version

Move an estate's configuration to a newer DGF release, and record that it runs there.

> **There is no upgrade skill.** No `/dgf-upgrade` exists, by decision
> ([ADR 0034](../adr/0034-usage-scenarios-security-scan.md) §3). This guide is a route through the skills that do
> exist: update dgf-factory, read the breaking changes, declare the new version, then one plan per breaking
> change, each through the gate. The parts no skill does are marked **by hand**.

## When to use this

The estate is moving from one DGF release to a newer one — new `DGF.API` packages, a new UI image — and its
configuration must keep working there.

## What dgf-factory can and cannot do here

| Part of the upgrade | Who does it |
|---|---|
| Know which release the estate runs | `/dgf` records it as `dgf.version`, declared by you, never inferred ([ADR 0019](../adr/0019-declared-dgf-version.md)) |
| Know which release the shipped DGF facts describe | the knowledge stamp, printed as `KNOWLEDGE: dgf_version=…` |
| Read what changed between two releases | `/dgf-explore`, over the docs MCP's release notes, every claim cited |
| Change the configuration for each breaking change | `/dgf-plan` → `/dgf-implement` → `/dgf-verify`, one plan per change |
| Move the hosts to the new `DGF.API` package, the UI image, the database baseline | **By hand.** C#, SQL and deployment configuration are never a plan task ([ADR 0010](../adr/0010-dgf-implement-scope.md) §3). A plan names them under `## Scope` |
| Compare each fact with the declared version, and warn or block | **Nobody yet.** The version gate is a follow-up: no shipped fact carries an `applies:` range, so nothing compares `dgf.version` with a fact today ([ADR 0019](../adr/0019-declared-dgf-version.md), `knowledge/README.md` §4) |

## What you need

- dgf-factory installed, the root set up by `/dgf`, and git.
- The target release number, `X.Y.Z`.
- The DGF docs MCP reachable: `dgf-factory setup` registers it as `dgf-mcp`. The release notes come from it.

## Step 1: See where you are

Two numbers matter. The **declared version** is `dgf.version` in `.dgf-factory/config.yaml`. The **knowledge
stamp** is the release the shipped facts were read at. From the project folder:

```bash
python3 .dgf-factory/runtime/scripts/inventory_root.py --workspaces-root <root>
```

**What you will see** (among the `WORKSPACE:` lines):

```text
KNOWLEDGE: dgf_version=1.1.11
```

The stamp is read from DGF's `Directory.Build.props`, which lags the release tags: a stamp of `1.1.11` may describe
a tree that behaves like a later release (`knowledge/README.md` §1.1). Read it as "no newer than", not as exact.

| Exit | What to do |
|---|---|
| `0`, `2` | Note the stamp and your declared version. A `WARN` here (`BASE_WORKSPACE_ABSENT`, `VALIDATOR_DEPS_MISSING`) does not change them. |
| `3` | `ROOT_NO_WORKSPACE`: `<root>` is not the workspaces root. |

## Step 2: Update dgf-factory

A newer dgf-factory may ship knowledge stamped nearer your target.

```bash
npm update -g @andrian-org/dgf-factory
dgf-factory --version
dgf-factory setup
```

Re-running `setup` is the update. Each file is decided against the receipt
([ADR 0029](../adr/0029-npm-cli-delivery.md) §5): a file you never edited is rewritten; one you edited is kept and
reported; one changed on both sides is kept and shown as a diff — never overwritten. Then, in your harness:

```text
/dgf-doctor
```

| Exit (`setup`) | What to do |
|---|---|
| `0` | Go on. |
| `1` | A settings file does not parse, or a write failed. Fix the file it names and run `setup` again. |
| `2` | A file was kept as edited, or a conflict was shown. Decide for each: keep your edit, or delete the file and run `setup` again to take the new one. |
| `3` | A usage error: pass `--harness` and `--yes` where no terminal can answer. |

| Exit (`/dgf-doctor`) | What to do |
|---|---|
| `0` | Go on. |
| `1` | The install is broken: run `dgf-factory setup` again. |
| `2` | `INSTALL_VERSION_DRIFT` means the CLI on your PATH and the install differ — run `setup` in this project. `INSTALL_FILE_EDITED` is a file setup will not update. |
| `3` | Run `dgf-factory setup` again. |

Commit the updated `.dgf-factory/runtime/`, `.dgf-factory/install.json` and harness folders, on their own, so
the upgrade's own changes stay readable. Then run Step 1 again for the new stamp.

**If the stamp is still older than your target**, the shipped facts were read at an older release than the one
you are moving to. Every fact a plan rests on must then be re-verified through the docs MCP: `/dgf-grounded`
warns before each answer that the knowledge was read at the stamp while the estate declares another release,
and cites the release note when it bears on a claim.

## Step 3: Read the breaking changes

```text
/dgf-explore "what changed in DGF since <declared version> that affects this estate's configuration?"
```

The skill reads the release notes through the docs MCP (`list_release_notes`, `get_release_notes("since:…")`),
the knowledge base and your workspaces, and cites every claim. Its answer ends with:

```text
Sources: …
Open: <each claim no source answered>
Version: 1.1.11 vs dgf.version <declared> — differs: facts may have moved
```

Say yes when it asks to save: the answer is appended to `.dgf-factory/RESEARCH.md`, which `/dgf-plan` reads as
cited background. List the breaking changes it found that touch your configuration — a component property that
now does something, a property now rejected, a changed default. **By hand:** decide which of them apply to your
estate; `/dgf-audit --reach <file>` tells you which processes reach a file that uses one.

| Exit (root lookup) | What to do |
|---|---|
| `0` | Read the answer, and save it. |
| `1` | No root: it answers from the knowledge base and the docs MCP alone and cannot save. Run `/dgf`. |
| `3` | A bad call: it stops and relays it. |

When the docs MCP is unavailable, the skill lists each release-note claim as open. Do not plan from memory: wait
for the MCP, or read the release notes yourself.

## Step 4: Audit before you change anything

```text
/dgf-audit
```

Keep the `VALIDATOR:` lines and the `AUDIT_REFERENCE_UNRESOLVED` count: they are the estate's health before the
upgrade, to compare with Step 8. The exits are those of [Check the system](check-the-system.md) Step 2; exit `1` on
an estate's existing errors is normal.

## Step 5: Declare the new version

```text
/dgf
```

On a re-run, `/dgf` asks only what you want to change, shows the current values, and shows a diff of what it will
edit. Choose the new release; it edits `dgf.version` and the version section of `DESCRIPTION.md`, and leaves every
other line alone. When the new version is newer than the knowledge stamp it says so, and offers
`get_release_notes("since:<stamp>")`.

Declare the version when the estate runs it — on the branch that moves it there, or on the base branch once it
has moved. Nothing checks the declared value against a deployment, so a wrong one stays wrong until `/dgf` is
run again ([ADR 0019](../adr/0019-declared-dgf-version.md), Consequences).

| Exit (root lookup) | What to do |
|---|---|
| `0`, `ROOT:` | A re-run: answer the questions you want to change. |
| `1`, `ROOT_AMBIGUOUS` | Several roots below this folder: run `/dgf <root>`. |
| `3` | The argument is not a directory. |

Stage `.dgf-factory/config.yaml` and `.dgf-factory/DESCRIPTION.md`, then `/dgf-commit`.

## Step 6: One plan per breaking change

For each breaking change that applies, take the [Add functionality](add-functionality.md) route from its Step 3:

```text
/dgf-plan full "adapt the eager TreeTables to <release>: <the breaking change, as the release note states it>"
```

Cite the `RESEARCH.md` section the plan rests on. One change per plan keeps each gate small and each fix
attributable. A plan that also needs a host, package or image change names it under `## Scope`, as out of scope:
that part is yours, by hand.

Then `/dgf-implement`, `/dgf-verify`, `/dgf-review`, `/dgf-qa` and `/dgf-commit`, with the exit tables of that
guide. Use `/dgf-qa` especially: a release that changes behaviour without changing the schema is invisible to
every validator, so the reached processes must be walked by hand.

## Step 7: The gate covers the whole root

You do not narrow `/dgf-verify`. It always runs every validator over the whole root, against the merge-base,
including every application that inherits a `webasm` file
([ADR 0026](../adr/0026-authoring-entry-point-revised.md) §3). A finding the upgrade introduced blocks; the
estate's existing ones are `PRE_EXISTING`.

What the gate cannot see: a configuration that validates against the same schema in two releases and behaves
differently in them. That is what the release notes in Step 3, and the test plans in Step 6, are for.

## Step 8: Audit after

```text
/dgf-audit
```

Compare with Step 4. New `ERROR` or `AUDIT_REFERENCE_UNRESOLVED` lines are work for another plan.

## See Also

- [ADR 0034](../adr/0034-usage-scenarios-security-scan.md) §3 — the decision behind this route
- [ADR 0019](../adr/0019-declared-dgf-version.md) — the declared version, and the gate that is not built yet
- [ADR 0013](../adr/0013-version-gating-provenance-ledger.md) — why every fact is stamped, and why the stamp lags
- [The declared DGF version](../pipeline.md#the-declared-dgf-version) — in the pipeline reference
