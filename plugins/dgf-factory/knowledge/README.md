# The DGF Knowledge Base — how a fact is stamped, ranged and cited

This directory holds the DotGov Framework facts that more than one skill needs. Every file
in it except this one is a set of **facts about DGF**, and every such file carries a stamp
saying which DGF it describes and when it was read. Where it was read from is recorded too,
outside the shipped tree (§1). A fact without a stamp is not a fact; it is a guess with good
formatting.

This file is the operative contract. The decisions behind it are recorded in
ADR 0036, which superseded ADR 0013 on
2026-11-04, and ADR 0030, which keeps DGF
repository paths out of every shipped file, this directory included. This file and the ADRs
agree; if they ever disagree, **this file wins** until a new ADR settles it.

`tools/check_knowledge_stamps.py`, a maintainer check, enforces everything mechanically
checkable below.

## 1. The stamp — every file carries it

Frontmatter, on every `knowledge/**/*.md` except this README:

```yaml
---
dgf_version: "1.3.0"
read_date: 2026-11-04
---
```

| Field | Meaning | Rule |
|---|---|---|
| `dgf_version` | The DGF release the facts were read at | Quoted `X.Y.Z`: the **exact release tag** at the checkout's HEAD — see §1.1. Every file in one pack carries the same value (§8) |
| `read_date` | When the sources were read | `YYYY-MM-DD`, unquoted |

**A shipped file never lists its sources.** Every DGF file a fact file was derived from is
recorded in its **provenance ledger**: a maintainer-only file at the same relative path under
`provenance/`, so `knowledge/composition-specs.md` has `provenance/knowledge/composition-specs.md`.
Each ledger entry has `path` (relative to the DGF repository root) and `sha256` (the digest of
that file as read). The ledger lives outside the shipped directories because those paths point
into the DGF repository, and a developer's install has no DGF checkout to resolve them against.
A `sources` key in a file under `knowledge/` is an error.

The per-source `sha256` is what makes drift detectable. Re-running the digest against the
upstream file answers "has this changed since we read it" without diffing prose. That is a
maintainer check, run against a DGF checkout (§4).

### 1.1 The release tag, and why not `Directory.Build.props`

A pack is read only from a DGF checkout whose HEAD is exactly a release tag, and its
`dgf_version` is that tag. A tag names one commit whichever branch is checked out, so the
stamp is reproducible. An unreleased branch tip is never stamped: its release does not exist
yet.

DGF's `Directory.Build.props` was the source until 2026-11-04 (superseded ADR 0013). It
states `<Version>` under a ClientDebug-only condition, and it stopped following the
releases: it reads `1.1.11` at the tags 1.1.12–1.1.15 and `1.1.15` at 1.1.16, 1.2.0 and
1.3.0. A source that gives one value for three release lines cannot tell them apart, so it is
no longer read. DGF itself versions its builds from tags: its release lines are support
branches whose tag is the release.

`git describe` without `--exact-match` stays rejected: it answers relative to the branch that
is checked out.

## 2. Three fact classes — stamp everything, range only what moved

| Class | What it describes | Frontmatter | Example |
|---|---|---|---|
| **Structural** | Shape that changes rarely and is caught by digest drift | Stamp only — **no** `applies:` block | `process.xsd` declares `State/@name`; `FM/_PROCESS` is the process directory |
| **Behavioural** | Runtime behaviour that changed between releases | Stamp + `applies:` with `since` and `until` | `paging` on an eager TreeTable is rejected; `expandAll: false` takes effect |
| **Policy** | A decision that changes by decision, not by release | Stamp + `review_date` | XML-always generation for the five legacy artifact types |

**Do not gate everything.** An over-gated fact base goes stale exactly as fast as an
unstamped one, because every fact then needs revisiting on every release and none of them
get it. Most facts are structural and cost one stamp. A `since` that nobody actually
verified is false precision, not safety.

### 2.1 A behavioural fact

```yaml
applies:
  since: "1.1.15"
  until: null
```

Both keys are **mandatory** whenever `applies:` is present. Each is a quoted version string
or the literal `null`. A file with `applies:` and only one of the two keys fails the check.

### 2.2 A policy fact

```yaml
review_date: 2026-09-22
```

The date the policy was last confirmed still in force. A policy fact's ledger also lists the
document that states the policy, so the digest catches a rewrite.

## 3. What `null` means in a range

Two conventions, both decided when this knowledge base was first stamped and both binding:

**`since: null` — no known lower bound.** Use it when a behavioural fact's origin is
unknown or predates `1.1.11`. Do **not** substitute a floor of `"1.1.11"`: that asserts a
boundary nobody verified and would wrongly block consumers on older releases for a fact that
was very likely true there too. Consequence, stated plainly: the below-`since` error in §4
never fires for such a fact, so it applies to every consumer version.

**`until: null` — no known end.** The range is open-ended: true from `since` onward until
proven otherwise. It is **not** "true through `dgf_version`".

> Both conventions are decided in ADR 0036 §5, carried forward from ADR 0013 §3,
> which also records why the superseded ADR 0003's reading of `until: null` ("still true at
> `dgf_version`") had to go: it made its own flagship TreeTable example incoherent.

## 4. Out-of-range behaviour — the gate

Tied to the exit-code contract: `0` clean, `1` blocked, `2` warnings, `3` usage error.
Reproduced here rather than linked, because the version gate is written against this file.

**The version gate** runs for a developer, in `/dgf-doctor`'s project mode. It reads the
estate's declared `dgf.version` in `.dgf-factory/config.yaml`, the installed pack's stamps,
and the line the install receipt records (§8):

| Situation | Behaviour | Exit |
|---|---|---|
| Consumer version **below** a fact's `since` | **error** — the fact is not true of their DGF | `1` |
| Consumer version **above** a fact's `until` | **warn** — possibly stale, not proven wrong | `2` |
| Consumer DGF version **cannot be determined** | **warn**, and say so | `2` |
| Consumer version's line is **not the installed pack's** | **warn**, naming `dgf-factory setup --dgf-version <v>` | `2` |
| Same line, consumer version **older than the pack's tag** | **warn** — the pack may describe a patch the estate lacks | `2` |
| The receipt records **no line** | **warn** — re-run `dgf-factory setup` | `2` |

**The digest checks** read the provenance ledgers, and run for a maintainer only — never from
a skill:

| Situation | Behaviour | Exit |
|---|---|---|
| A ledger's upstream `sha256` no longer matches its line's release tag | **warn** — a maintenance signal | `2` |
| A vendored schema no longer matches its recorded `shipped_sha256` | **error** — the shipped copy was edited by hand | `1` |
| A newer release tag exists on a pack's line, or a release line has no pack | **warn** — a maintenance signal | `2` |

Blocking below `since` is the default because of an asymmetry: applying a newer
*restriction* too early is merely over-strict and safe, while claiming a newer *capability*
too early is simply wrong — it tells an author to use something their runtime ignores, which
is how `expandAll` sat inert in real configurations for releases at a time. A fact that is
purely a restriction may opt out with `out_of_range: warn`, and must say why in a comment.

**Never proceed silently on an unknown version.** A comparison that quietly passes is the
failure this whole directory exists to prevent.

## 5. How to cite a fact

Every fact names where it came from. Acceptable sources, in order of preference:

1. **A specific file in the DotGov Framework repository.** Its path and digest go in the
   fact file's provenance ledger. In the fact file itself, name it by DGF type or file name,
   or by the MCP call that serves it — never by repository path.
2. **The DGF docs MCP** at `https://dgf-mcp.dotgov.uk/mcp` (declared in `.mcp.json`) —
   name the tool and the argument, for example
   `get_doc_page('AI-Authoring/format-coverage.md')`.
3. **A DGF ADR.** Recorded in the ledger like any other DGF file.

**Not acceptable:** inference from a name, analogy to another framework, or recall. A fact
that cannot be cited stays marked `[assume]` until it can, and an `[assume]` fact carries no
stamp because there is nothing to stamp.

### 5.1 Schemas — narrower sources

DGF ships two schema families and several disagreeing inventories, so for schemas the
acceptable sources are narrower:

| Family / topic | Acceptable source |
|---|---|
| Modern JSON component config | DGF's generated JSON schema set: the vendored copy in `schemas/json/`, or the MCP's `list_available_json_schemas` / `get_json_schema_details` |
| Legacy XML grammar | DGF's XSD set and its XML grammar reference `form.reference.json`: the vendored copy in `schemas/xsd/`, or `list_available_xsd_schemas` / `get_xsd_schema_details` |
| Runtime parity | DGF's format-coverage page, `get_doc_page('AI-Authoring/format-coverage.md')` — the **only** authority for whether the runtime actually reads a format for a component |

DGF's standalone contracts are **not** the generated set. There are three hand-authored
standalone contracts, vendored in `schemas/standalone/`, and only one of them is synced into
the MCP. Cite them only for those three.

## 6. What is exempt

Only this file. `knowledge/README.md` describes this plugin's convention, not a DGF fact, so
it has nothing to stamp and no ledger. Everything else under `knowledge/` — including
`schemas/MANIFEST.md`, the stamp for the vendored schema set — is stamped, has a ledger, and
is checked. The schema set's ledger also records each vendored file's upstream and shipped
digests, because ADR 0012 rewrites DGF paths in the shipped copies.

## 7. Machine-read tables

Some tables in this directory are read by the plugin's scripts as well as by people. Such a
table is marked, and its shape is a contract:

```markdown
<!-- machine-read: parity -->
| # | Row | ComponentType | Schema | Runtime | XML-only part |
|---|---|---|---|---|---|
| 1 | `Badge` | `Badge` | `BadgeConfiguration.schema.json` | ✓ | |
```

- **The marker.** A script reads a table only when the line **immediately** above its header
  row is `<!-- machine-read: <table-id> -->`. The comment is invisible when rendered. An unmarked
  table is prose, and no script reads it.
- **Exact headers.** The loader declares, per table id, the header cells it expects, in order.
  A renamed, added, dropped or reordered column is a malformed table — never a best guess.
- **Cells.** Leading and trailing whitespace is stripped, then **one** pair of surrounding
  backticks. Nothing else is interpreted: bold and links are read literally. A cell cannot
  contain `|`, escaped or not. An empty cell is the empty string, and `—` is read as itself.
- **Keys.** The first column is the key. Two rows with the same key are a malformed table.
- **Extent.** The table ends at a blank line or the end of the file. Any other line that is not
  a `| … |` row is a malformed table: Markdown still renders a row missing its closing pipe,
  and the loader must not silently drop it and the rows after it.
- **Multi-valued cells.** A table may declare that a cell holds several values. They sit inside the
  cell's one pair of backticks, separated by spaces, and each is an **alternative** — one value, and
  one row's worth of meaning, per value. `a+b` is **one composite value** whose parts are read in
  order. `—` is no value. So `` `UpdateRecord/Settings CreateRecord/Settings` `` is two alternatives, and
  `` `table+form` `` is one value of two parts. Never backtick each value separately: only one pair of
  backticks is removed, so `` `A` `B` `` reads as ``A` `B``.
- **A malformed table blocks.** Anything that reads one refuses to run and exits `3`, naming
  the table id, and the plugin's installation check loads every marked table and reports a
  malformed one as a blocking error. Nothing falls back to a stale copy or skips the table.

Edit a marked table like any other fact — with its stamp and provenance ledger updated in the
same change — and keep its header exactly as it is. The marker is the only coupling between a
knowledge file and the code that reads it: the file still states DGF facts and names no script — with
one exception. The `Checked by` column of `reference-edges` names the plugin validator that reports an
edge resolving nowhere, so that such a reference is reported once and by one script
(ADR 0027 §4–§5). It names a validator's file, never a skill
or a pipeline stage, and it is the plugin's own fact, not DGF's: it carries no provenance.

| Table id | File |
|---|---|
| `legacy-artifacts` | [`composition-specs.md`](composition-specs.md) §2 |
| `code-places` | [`composition-specs.md`](composition-specs.md) §5 |
| `component-classes` | [`json-reader.md`](json-reader.md) §2 |
| `datasource-discriminators` | [`json-reader.md`](json-reader.md) §3 |
| `component-folders` | [`json-reader.md`](json-reader.md) §4 |
| `enum-member-names` | [`json-reader.md`](json-reader.md) §1 |
| `layout-components` | [`json-reader.md`](json-reader.md) §2.1 |
| `dispatchable` | [`component-catalogue.md`](component-catalogue.md) §3 |
| `correspondence` | [`schema-families.md`](schema-families.md) §5 |
| `parity` | [`schema-families.md`](schema-families.md) §6 |
| `process-divergence` | [`process-model.md`](process-model.md) §1 |
| `reference-edges` | [`reference-graph.md`](reference-graph.md) §1 — `Element` and `Attribute` are multi-valued; `Checked by` names a validator |
| `run-time-names` | [`reference-graph.md`](reference-graph.md) §3.1 |
| `role-sources` | [`permissions.md`](permissions.md) §2 |
| `field-types` | [`data-model.md`](data-model.md) §6.1 |
| `db-types` | [`data-model.md`](data-model.md) §6.2 |
| `field-sql-types` | [`data-model.md`](data-model.md) §6.3 |
| `workspace-minimum` | [`application-layout.md`](application-layout.md) §1 — `Required` and `Rule` are space-separated tokens |
| `instance-models` | [`application-layout.md`](application-layout.md) §4 |
| `auth-schemes` | [`application-layout.md`](application-layout.md) §5 — `Keys` is space-separated |
| `solution-parts` | [`application-layout.md`](application-layout.md) §7 — `Verified values` and `Placeholders` are space-separated |

## 8. Packs — one per DGF release line

DGF maintains several release lines at once, and a developer works on estates that run
different ones. The knowledge base is therefore one **pack** per release line `X.Y`:

| Where | What |
|---|---|
| `knowledge/` | the **current** line's pack, plus this README |
| `packs/<X.Y>/` | each older line's pack: the same file names, no README |
| `packs/lines.json` | the registry: each line's `dir`, `dgf_version` (its tag), `read_date`, and which line is `current` |

- A pack is complete. It is never an overlay of another pack: an inherited file would carry a
  ledger read at another line's tag.
- Every file in a pack carries the pack's `dgf_version`, and the registry states it.
- Ranges (§2.1) mark a boundary **inside** a line, such as a fact that changed in a patch
  release. A difference between two lines is two packs.
- In a project, `dgf-factory setup` installs one pack into `.dgf-factory/runtime/knowledge/`
  (this README plus that line's files) and records the line as `dgfLine` in
  `.dgf-factory/install.json`. It is chosen with `--dgf-line X.Y` or `--dgf-version X.Y.Z`,
  or from the previous install and the estate's `dgf.version`. A version older than every
  pack is refused unless the line is named explicitly, because an older estate reading a newer
  pack would be told about capabilities its runtime lacks (§4).
- Each pack's ledgers live in the maintainer-only `provenance/` tree, beside a sync log for
  every time the pack was brought to a new tag.

## See Also

The ADRs and pages below are maintainer documentation in the dgf-factory repository (`docs/`); they are
not installed with the tool (ADR 0030).

- ADR 0036 — Knowledge packs per DGF release line, each pinned to a release tag; one pack installed per project (superseding ADR 0013)
- ADR 0030 — Shipped files are the npm package payload, and carry no DGF repository paths (superseding ADR 0012)
- DGF Knowledge Sourcing — the reader-facing version of §5
- DGF Schemas — inventories, correspondence map, vendoring contract
- [`schemas/MANIFEST.md`](schemas/MANIFEST.md) — what the vendored set holds: directories, dialects, membership
