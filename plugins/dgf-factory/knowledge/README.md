# The DGF Knowledge Base — how a fact is stamped, ranged and cited

This directory holds the DotGov Framework facts that more than one skill needs. Every file
in it except this one is a set of **facts about DGF**, and every such file carries a stamp
saying which DGF it describes and when it was read. Where it was read from is recorded too,
outside the shipped tree (§1). A fact without a stamp is not a fact; it is a guess with good
formatting.

This file is the operative contract. The decisions behind it are recorded in
[ADR 0013](../docs/adr/0013-version-gating-provenance-ledger.md), which superseded ADR 0008 on
2026-09-23, and [ADR 0012](../docs/adr/0012-no-dgf-paths-in-shipped-files.md), which keeps DGF
repository paths out of every shipped file, this directory included. This file and the ADRs
agree; if they ever disagree, **this file wins** until a new ADR settles it.

`tools/check_knowledge_stamps.py`, a maintainer check, enforces everything mechanically
checkable below.

## 1. The stamp — every file carries it

Frontmatter, on every `knowledge/**/*.md` except this README:

```yaml
---
dgf_version: "1.1.11"
read_date: 2026-09-22
---
```

| Field | Meaning | Rule |
|---|---|---|
| `dgf_version` | The DGF version the facts were read from | Quoted string. Read from DGF's `Directory.Build.props`, **never** from a git tag — see §1.1 |
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

### 1.1 Why `Directory.Build.props`, and why it lags

DGF's `Directory.Build.props` states `1.1.11`, under
`Condition="'$(Configuration)' == 'ClientDebug'"`. It is the only version the repository
states anywhere, and it lags: git tags reach `1.1.15` and release notes exist through
`1.1.15`. So a fact stamped `1.1.11` may well have been read from a tree that is
behaviourally `1.1.15`.

This is accepted. The superseded ADR 0003 gave "a stamp that lags is worse than no stamp"
as the reason to prefer the props file over a tag, and that reason does not survive — the
props file *is* the lagging source. The conclusion still holds, for a better reason, which
[ADR 0013](../docs/adr/0013-version-gating-provenance-ledger.md) §1 records: **determinism.** `git describe` on a DGF checkout returns a different value depending on
which branch is checked out (on one branch it returns `1.1.12-21-gaa1d5c4c2`, with `1.1.13`
and `1.1.15` unreachable), while the props file returns the same value regardless. The gate
in §4 must be reproducible, and a version source that shifts with branch state is not.

Do not "correct" a stamp to a tag value. Record the lag; do not hide it.

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

> Both conventions are decided in [ADR 0013](../docs/adr/0013-version-gating-provenance-ledger.md) §3,
> which also records why the superseded ADR 0003's reading of `until: null` ("still true at
> `dgf_version`") had to go: it made its own flagship TreeTable example incoherent.

## 4. Out-of-range behaviour — the gate

Tied to the exit-code contract: `0` clean, `1` blocked, `2` warnings, `3` usage error.
Reproduced here rather than linked, because the version gate is written against this file.

**The version gate** reads the stamps in this directory, and runs for a developer:

| Situation | Behaviour | Exit |
|---|---|---|
| Consumer version **below** a fact's `since` | **error** — the fact is not true of their DGF | `1` |
| Consumer version **above** a fact's `until` | **warn** — possibly stale, not proven wrong | `2` |
| Consumer DGF version **cannot be determined** | **warn**, and say so | `2` |

**The digest checks** read the provenance ledgers, and run for a maintainer only — never from
a skill:

| Situation | Behaviour | Exit |
|---|---|---|
| A ledger's upstream `sha256` no longer matches a DGF checkout | **warn** — a maintenance signal | `2` |
| A vendored schema no longer matches its recorded `shipped_sha256` | **error** — the shipped copy was edited by hand | `1` |

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

## See Also

- [ADR 0013 — Stamp every fact, gate only behavioural ones — provenance in a maintainer ledger](../docs/adr/0013-version-gating-provenance-ledger.md)
- [ADR 0012 — Shipped files carry no DGF repository paths](../docs/adr/0012-no-dgf-paths-in-shipped-files.md)
- [DGF Knowledge Sourcing](../docs/dgf-knowledge.md) — the reader-facing version of §5
- [DGF Schemas](../docs/dgf-schemas.md) — inventories, correspondence map, vendoring contract
- [`schemas/MANIFEST.md`](schemas/MANIFEST.md) — what the vendored set holds: directories, dialects, membership
