---
archived: 2026-09-22
---
# Implementation Plan: DGF Knowledge Base

Branch: `feature/dgf-knowledge-base` — created from `develop` at `a7cd356`
Created: 2026-09-22
Base: `develop` (**not** `main` — see `## Branch Note`)

## Original Request

**DGF Knowledge Base** — `knowledge/` facts tree and the vendored JSON/XSD schema set; every fact stamped `dgf_version` + `read_date` + per-source `sha256`, behavioural facts additionally carrying a `since`/`until` range, with a `MANIFEST.md` recording the DGF commit SHA and a re-vendor process ([ADR 0003](../docs/adr/0003-version-gating.md))

## Branch Note

This branch was cut from `develop`, not from the configured `git.base_branch: main`.
`main` is 12 commits behind `develop` and does not contain milestone 6, so a branch off
`main` would lack the manifest, the `/dgf-doctor` slice and the contract check's manifest
section that this milestone builds on.

`origin/develop` does not exist — `develop` is local-only. Do not attempt
`git pull origin develop`; it will fail. Only `origin/main` and
`origin/feature/zamconnect-plugin` exist remotely.

`git.base_branch` in `.ai-factory/config.yaml` is still `main`, so `/aif-review` and
`/aif-verify` will diff against a base that lacks this work. Gather changed files from the
working tree or from `develop...HEAD` instead. Fixing the config is out of scope here.

## Settings

- Testing: yes — stamp validation only. A section in `scripts/check-dual-schema-docs.sh`
  asserting every `knowledge/**/*.md` file carries required frontmatter. The full drift
  check against a consumer's DGF checkout is milestone 8, per
  [ADR 0003](../docs/adr/0003-version-gating.md) §Follow-ups.
- Logging: verbose — the new check section honours `DEBUG=1` / `LOG_LEVEL=debug` with a
  per-file trace, matching the five existing sections.
- Docs: yes — mandatory documentation checkpoint at completion, routed through `/aif-docs`.
- Scope: the full milestone. Stamping convention, vendored schema set, `MANIFEST.md`, four
  facts files, and the stamp check.

## Roadmap Linkage

Milestone: "DGF Knowledge Base"
Rationale: This plan is the whole of that milestone. It is the last milestone before
milestone 8's deterministic validators, which read `knowledge/schemas/` and cannot be
written until the vendored set and its manifest exist.

Ticking the milestone in `.ai-factory/ROADMAP.md` is `/aif-roadmap`'s job, not this plan's.

## Task Ledger Note

`TaskCreate` / `TaskUpdate` are unavailable in this session. The checkbox list under
`## Tasks` is the **single** progress ledger for this plan.

---

## Verified Facts

Read from `~/workspaces/dotgov/_DotGovFramework/DotGovFramework` at commit `aa1d5c4c2` on
**2026-09-22**, and confirmed by direct count rather than taken from a summary. These are
the inputs the tasks below depend on; re-verify any that have drifted before using them.

| Fact | Value | Evidence |
|---|---|---|
| Generated JSON schemas | **69** files, **3.3 MB** | `src/Tools/dgf-mcp/Schemas/Json/*.schema.json` |
| JSON Schema dialects | **68 draft-04**, **1 draft-07** | the draft-07 file is `componentValidator.schema.json` |
| Schemas matching the MCP's glob | **57** | `*Configuration.schema.json` |
| Exposed by `SchemaIndexService` | **58** = 57 + `componentValidator` allow-list | `src/Tools/dgf-mcp/Services/SchemaIndexService.cs` |
| Present but unindexed (`$ref`-only) | **11** | excluded so they do not surface as bogus component types |
| XSDs | **9** | `Schemas/XSD/*.xsd` |
| XSD roots | `form`, `view` ×3, `options`, `Process`, `Tree`, `entity`, `Workflow` | `grid-form`/`lookup-view`/`table-view` all root at `view` |
| XML grammar reference | `README.md` + `form.reference.json` (~40 KB) | `Schemas/XmlReference/` |
| Hand-authored standalone contracts | **3** | `docs/schemas/{componentValidator,dataFetcherConfiguration,eventBase}.schema.json` |
| Shell-hazardous filename | ``NumberConfiguration`1.schema.json`` | backtick; also stale and unserved |
| Component service registrations | **34 calls across 31 files** | `ComponentServiceProvider.RegisterComponentService(` |
| `ComponentType` enum members | **67** | `src/Components/DGF.Components.Shared/Enums/ComponentType.cs` |
| Runtime parity source | `format-coverage.md`, `last_updated: 2026-09-09` | hand-maintained; 13 days stale at plan time |
| Parity legend | `✓ supported · ◐ partial · ✗ not supported today` | verbatim, line 95 |
| DGF version | **1.1.11** | `src/Directory.Build.props`, `Condition="'$(Configuration)' == 'ClientDebug'"` |
| DGF upstream sync flow | `src/Tools/dgf-mcp/sync-schemas.sh` | this plugin mirrors it; see `docs/dgf-schemas.md` §10 |

**Correction required.** `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` both
say "~40 component plugins". The verified figure is **34** registrations. Task 9 corrects
both.

---

## Design Decisions

Three decisions were taken with the user during planning. They are settled inputs to the
tasks below, not open questions.

### 1. `applies.since: null` means "no known lower bound"

[ADR 0003](../docs/adr/0003-version-gating.md) §Follow-ups parked this for milestone 7.
Decision: when a behavioural fact's origin predates 1.1.11 or is simply unknown, `since` is
`null` — not a floor value of `"1.1.11"`.

Consequence, stated plainly: §3's below-`since` **error** never fires for such a fact, so it
applies to every consumer version. That is the honest outcome. A floor of `1.1.11` would
assert a boundary nobody verified, and would wrongly block consumers on older releases for
facts that were very likely true there too.

### 2. `until: null` means "no known end", not "true through `dgf_version`"

ADR 0003 §2's example is internally inconsistent and must not be copied as written:

```yaml
dgf_version: "1.1.11"     # §1
applies:
  since: "1.1.15"         # §2
  until: null             # §2 comment claims "still true at dgf_version"
```

1.1.11 is below 1.1.15, so the fact is *not* true at `dgf_version` and the comment is wrong.
Decision: `until: null` is an **open-ended upper bound** — true from `since` onward until
proven otherwise.

This matters beyond wording. Under the other reading, a fact whose `since` exceeds
`dgf_version` could not use `until: null` at all, and the ADR's own flagship example — the
1.1.15 TreeTable change — would immediately need a special case.

`knowledge/README.md` (Task 1) records this reading as the convention and notes that ADR
0003 §2's inline comment is superseded by it. **Do not edit ADR 0003.** Decisions are
reversed by a new ADR, never by editing one in place; a superseding ADR is a reasonable
follow-up but is out of scope here.

### 3. `dgf_version` is stamped at 1.1.11 and will sit below some `since` values

Accepted, not worked around. `Directory.Build.props` is the only version the repository
states, and ADR 0003 §1 mandates it over a git tag. It lags: tags reach `1.1.15` and release
notes exist through `1.1.15`.

The ADR's stated reason for rejecting tags ("a stamp that lags is worse than no stamp") is
the one argument that does not survive contact with the evidence — the chosen source is the
lagging one. The *conclusion* still holds for a better reason, which `knowledge/README.md`
should record: `git describe` on a DGF checkout returns a value that depends on which branch
the consumer has checked out (it returns `1.1.12-21-gaa1d5c4c2` on the current one, where
`1.1.13` and `1.1.15` are not reachable), while `Directory.Build.props` returns the same
value regardless. Tags lose on **determinism**, not on lag — and §3's gate must be
reproducible.

---

## Tasks

### Phase 1 — The stamping convention

- [x] **Task 1 — Create `knowledge/README.md`**

  **File:** `plugins/dgf-factory/knowledge/README.md` (new)

  Write this **before** any fact file. It is the contract every other file in this milestone
  is validated against, and Task 8 encodes it as a check.

  Content:

  1. **The frontmatter contract**, exactly as [ADR 0003](../docs/adr/0003-version-gating.md)
     §1 specifies:

     ```yaml
     dgf_version: "1.1.11"
     read_date: 2026-09-22
     sources:
       - path: src/Tools/dgf-mcp/Schemas/XSD/process.xsd
         sha256: <digest of the file as read>
     ```

     `dgf_version` is read from `src/Directory.Build.props`, never from a git tag — and
     record Design Decision 3's reason (determinism, not lag), because the reason given in
     ADR 0003 is wrong and a reader who checks will notice.

  2. **The three fact classes** and their treatment, from ADR 0003 §2: structural
     (stamp only), behavioural (stamp + range), policy (stamp + review date). State the
     over-gating warning — an over-gated fact base goes stale exactly as fast as an
     unstamped one.

  3. **The range convention**, per Design Decisions 1 and 2:
     - `since: null` — no known lower bound; the below-`since` error does not fire
     - `until: null` — no known end; open-ended, **not** bounded by `dgf_version`
     - Note explicitly that ADR 0003 §2's inline comment reads otherwise and is superseded
       by this file

  4. **The out-of-range behaviour table** from ADR 0003 §3, tied to the 0/1/2/3 exit-code
     contract in `.ai-factory/rules/base.md`. Reproduce it rather than linking, because the
     validator in milestone 8 is written against this file.

  5. **How to cite a fact.** Reproduce `docs/dgf-knowledge.md` §"The rule" rather than
     pointing at it — this file is the operative contract. Acceptable sources, in order of
     preference: (1) a specific file path in the DotGov Framework repository, (2) the DGF
     docs MCP at `https://dgf-mcp.dotgov.uk/mcp`, (3) a DGF ADR under
     `DotGovFramework/docs/adr/`. **Not acceptable:** inference from a name, analogy to
     another framework, or recall. A fact that cannot be cited stays marked `[assume]`.
     For schemas the sources are narrower — `Schemas/Json/` or the MCP's JSON tools for the
     modern family, `Schemas/XSD/` + `XmlReference/form.reference.json` or the XSD tools for
     the legacy family, and `format-coverage.md` as the *only* runtime-parity authority.

  6. **What is exempt.** `knowledge/README.md` itself carries no stamp: it describes this
     plugin's convention, not a DGF fact. Every other `knowledge/**/*.md` — including
     `schemas/MANIFEST.md` — is stamped and is validated by Task 8.

  **Logging:** none (a Markdown document).

  *Depends on: nothing. Blocks Tasks 3-9; Task 2 may run in parallel.*

### Phase 2 — The vendored schema set

- [x] **Task 2 — Vendor the three schema sets**

  **Files:** `plugins/dgf-factory/knowledge/schemas/{json,xsd,standalone}/` (new, ~3.5 MB)

  Copy, per the vendoring contract in `docs/dgf-schemas.md` §9 — which already decides the
  scope, so do not re-litigate it:

  | Destination | Source | Count |
  |---|---|---|
  | `json/` | `src/Tools/dgf-mcp/Schemas/Json/*.schema.json` | 69 |
  | `xsd/` | `src/Tools/dgf-mcp/Schemas/XSD/*.xsd` + `XmlReference/form.reference.json` | 9 + 1 |
  | `standalone/` | `docs/schemas/*.schema.json` | 3 |

  Vendor the **complete** JSON set, all 69 — not the 58 the MCP exposes. A validator that
  resolves `$ref` needs the 11 sub-schemas even though they are never top-level entries.

  Three verified hazards, each with a required mitigation (`docs/dgf-schemas.md` §9.1-9.3):

  - **Case collision.** `docs/schemas/dataFetcherConfiguration.schema.json` (draft-07,
    5.6 KB) and `Schemas/Json/DataFetcherConfiguration.schema.json` (draft-04, 53 KB) differ
    only in the first letter's case. On macOS's case-insensitive default, writing both into
    one directory silently leaves one file. The `standalone/` split is what prevents this —
    **never flatten the two directories.** After copying, assert both files exist and their
    sizes differ.
  - **Shell-hazardous filename.** ``NumberConfiguration`1.schema.json`` contains a backtick.
    Quote every path in every command. Do not special-case the file; quoting is the rule.
  - **Do not copy** `Schemas/XSD/fixtures/`, `verify-xsd-coverage.sh`, or
    `xsd-sample-baseline.txt` — they sit in the XSD directory but are not schemas.

  **One file lands twice, and that is correct.** DGF's own `sync-schemas.sh` (lines 66-70)
  copies `docs/schemas/componentValidator.schema.json` *into* `Schemas/Json/` — which is why
  it is the lone draft-07 among the 69. Vendoring faithfully therefore puts a byte-identical
  `componentValidator.schema.json` in both `json/` and `standalone/`. Vendor both anyway:
  `json/` must remain a byte-faithful mirror of `Schemas/Json/` or the milestone 8 drift
  check cannot diff it. Task 3 records the duplicate so nothing flags it later.

  Verify after copying: 69 files in `json/`, 10 in `xsd/`, 3 in `standalone/`.

  **Logging:** none (a copy operation). Report the per-directory counts.

  *Depends on: nothing. Copying files needs no stamping convention — Task 3 is what needs
  it. Runs in parallel with Task 1.*

- [x] **Task 3 — Create `knowledge/schemas/MANIFEST.md`**

  **File:** `plugins/dgf-factory/knowledge/schemas/MANIFEST.md` (new)

  Records the five items `docs/dgf-schemas.md` §9.4 requires:

  1. **DGF commit SHA** the set was vendored from — `aa1d5c4c2` at plan time; re-read with
     `git rev-parse --short HEAD` in the DGF repo at vendor time, and record the full SHA
  2. **DGF version and vendored date** — `1.1.11`, and note it is `ClientDebug`-conditioned
  3. **Per-file `$schema` dialect** — 68 draft-04 and 1 draft-07 in `json/`, draft-07 for the
     standalone contracts. Generate the table; do not hand-type 69 rows
  4. **Provenance per file** — which came from `Schemas/Json/`, which from `Schemas/XSD/`,
     which from the hand-authored `docs/schemas/`
  5. **Membership deltas** — the 11 `$ref`-only schemas present but not served by the live
     MCP, named individually; any file the MCP serves that is absent here; the
     `componentValidator.schema.json` duplicate across `json/` and `standalone/` (see
     Task 2); and that only **1 of the 3** standalone contracts is synced upstream —
     `dataFetcherConfiguration` and `eventBase` exist in `docs/schemas/` alone
  6. **Per-file digests — the item §9.4 omits and ADR 0003 §1 requires.** MANIFEST.md
     carries the standard stamp frontmatter: `dgf_version`, `read_date`, and a `sources:`
     list with `path` and `sha256` for **every one of the 82 vendored files**. The schemas
     themselves are not Markdown and cannot carry frontmatter, so this is the only place
     their digests can live — and without it, milestone 8's drift warning ("vendored
     `sha256` no longer matches upstream") has nothing to compare. Generate the list with
     `shasum -a 256`; do not hand-type 82 entries. This makes MANIFEST.md conform to the
     stamp contract rather than sit outside it, so Task 8 validates it like any other fact
     file.

  Also record the **re-vendor process** from `docs/dgf-schemas.md` §10, including that
  DGF's own `/dgf-freshness-audit` does not see this plugin, and that step 2 must never be
  automated on a schedule.

  **Logging:** none (a Markdown document).

  *Depends on: Task 1 (the frontmatter contract MANIFEST.md conforms to) and Task 2 (the
  files it records).*

### Phase 3 — The facts tree

- [x] **Task 4 — Create `knowledge/schema-families.md`**

  **File:** `plugins/dgf-factory/knowledge/schema-families.md` (new)

  The resolution rules a validator needs, as facts rather than prose. Derived from
  `docs/dgf-schemas.md` and the parity source, both cited.

  - Family resolution: XML declaration or known XSD root → XSD family; parses as a JSON
    object → JSON family; ambiguous → exit 3, **never** fall back to JSON
  - The `SchemaIndexService` selection rules, as facts: the `*Configuration.schema.json`
    glob, the allow-list — verified as exactly
    `StandaloneJsonSchemas = ["componentValidator.schema.json"]` in
    `src/Tools/dgf-mcp/Services/SchemaIndexService.cs` — and the 11 excluded `$ref`-only
    sub-schemas named individually
  - **The XSD↔JSON correspondence map**, copied from `docs/dgf-schemas.md` §5 as a
    structural fact. `.ai-factory/rules/base.md` forbids inferring a counterpart from a
    filename — `options.xsd` is not `StaticOptionsDataSource` — and this file is where a
    validator looks up the verified pairing instead
  - Dialect selection per file from its own `$schema`
  - **Runtime parity**, the load-bearing part: `✓ supported · ◐ partial · ✗ not supported
    today`; `Workflow` and `ProcessFlow` are `✗` — schemas exist, runtime reads
    `_workflow.xml` / `_process.xml` only; seven components are `◐`. Classify this as a
    **policy** fact with a review date: `format-coverage.md` is hand-maintained, stamped
    `last_updated: 2026-09-09`, and regenerable from nothing

  **Logging:** none.

  *Depends on: Task 1.*

- [x] **Task 5 — Create `knowledge/component-catalogue.md`**

  **File:** `plugins/dgf-factory/knowledge/component-catalogue.md` (new)

  **The count is the hard part.** Five different component counts exist in DGF, each a
  different slice, and picking one silently is how a wrong fact enters the corpus:

  | Count | What it is | Source |
  |---|---|---|
  | **34** | `IComponentService<TSource>` registrations — what the runtime dispatches | `RegisterComponentService(` call sites |
  | **67** | `ComponentType` enum members — includes layout-only types with no service | `ComponentType.cs` |
  | **55** | lifecycle matrix entries | `src/Tools/dgf-mcp/Data/lifecycle/components.json` |
  | **59** | demo-app showcase examples | `Data/examples/components.json` |
  | **~66** | components with a generated JSON schema | `format-coverage.md` |

  State all five, say what each means, and name **34** as the answer to "which components
  does the runtime dispatch to a service", because that is the question a validator asks.
  Never write "~40" — it matches none of them.

  Derive the 34 name→type pairs statically from the `RegisterComponentService` call sites;
  they are not published as an artifact anywhere in DGF. Note that registration is
  two-stage: the explicit calls are the naming source of truth, and the
  `AppDomain.CurrentDomain.GetAssemblies()` reflection scan only filters DI wiring to types
  already registered.

  Structural fact class: stamp only.

  **Logging:** none.

  *Depends on: Task 1.*

- [x] **Task 6 — Create `knowledge/composition-specs.md`**

  **File:** `plugins/dgf-factory/knowledge/composition-specs.md` (new)

  How consumer apps compose DGF declaratively: the five legacy XML artifact types
  (`_form.xml`, `_workflow.xml`, `_process.xml`, `settings.xml`, `view.xml`), the DataFetcher
  `eventBase` verb dispatcher, and the workspace inheritance chain from
  `src/Core/DGF.Kernel/WorkspaceSettings.cs` — `FmPath` resolves in the selected workspace,
  `FmBasePath` in the base workspace (`webasm`), so a base artifact is live in every
  application.

  Record the **XML-always generation policy** for all five legacy types as a *policy* fact
  with a review date, not a structural one — `format-coverage.md` states it as a Wave 1
  decision that changes by decision rather than by release.

  **Logging:** none.

  *Depends on: Task 1.*

- [x] **Task 7 — Create `knowledge/naming-conventions.md`**

  **File:** `plugins/dgf-factory/knowledge/naming-conventions.md` (new)

  DGF's own naming rules as facts a generator must honour: the `FM/_PROCESS`, `_WORKFLOW`
  and `_COMPONENTS` workspace constants from `WorkspaceSettings.cs`, the `_form.xml` /
  `_workflow.xml` / `_process.xml` file-naming pattern, and the `control_xxx` custom-cell
  convention referenced in `format-coverage.md`'s Form row.

  This is the smallest of the four files. Keep it to verified rules; do not pad it with
  inferred conventions.

  **Logging:** none.

  *Depends on: Task 1.*

### Phase 4 — Verification

- [x] **Task 8 — Add the stamp validator and wire it in as section 7**

  **Files:** `plugins/dgf-factory/scripts/check_knowledge_stamps.py` (new, executable);
  `plugins/dgf-factory/scripts/check-dual-schema-docs.sh` (modify)

  **Why a Python helper and not more awk.** The knowledge frontmatter is *nested* —
  `sources:` is a list of maps, `applies:` is a map. The only frontmatter parsing the shell
  script does today is `adr_status()`, one `sed` for one flat key, and `doctor.py`'s scanner
  is explicitly flat-only. Asserting "every `sources[].path` has a `sha256` sibling" in awk
  is fragile in exactly the way this check exists to prevent.

  So: write `check_knowledge_stamps.py` at plugin-root `scripts/` — a repo-maintenance
  check per `docs/architecture.md` §"Two kinds of script", snake_case per `base.md`,
  standard library only, with a frontmatter scanner scoped to the known shape (flat scalars,
  one list-of-maps, one nested map) rather than arbitrary YAML. Same `fail()` / exit-code /
  ANSI / `trace()` conventions as `doctor.py`. Then `check_knowledge_stamps()` becomes
  section 7 of the shell script, registered in `main()` after `check_plugin_manifest`, and
  does exactly what section 6 does with `doctor.py`: invoke, capture the exit code before
  any pipe, map `1`→`error` / `2`→`warn` / `3`→`error`, echo findings once. One
  implementation; milestone 8's drift check is its second caller.

  The validator asserts the Task 1 contract mechanically:

  1. Every `knowledge/**/*.md` **except** `knowledge/README.md` carries frontmatter with
     `dgf_version`, `read_date`, and a non-empty `sources:` list → `error` on a miss.
     `schemas/MANIFEST.md` is **not** exempt — it is stamped per Task 3
  2. Every `sources[].path` entry has a `sha256` sibling → `error`
  3. `read_date` parses as `YYYY-MM-DD` → `error`
  4. A file declaring `applies:` has both `since` and `until` keys present, each either a
     quoted version or `null` → `error`. This is what enforces Design Decisions 1 and 2
  5. `dgf_version` is identical across all knowledge files → `warn` on divergence (a
     partially re-vendored tree is a maintenance signal, not a blocker)

  Two existing behaviours to respect rather than assume:

  - `owned_markdown()` prunes only `.claude`, `.git`, `node_modules` and `plans`, so every
    new `knowledge/**/*.md` is **already** swept into checks 1 and 4. Confirm the new files
    pass the absolute-path check before adding section 7, or section 7's failures will be
    confused with check 4's
  - The script is `set -eu` and avoids subshells so `ERRORS`/`WARNINGS` accumulate in the
    parent shell. Read findings from a here-doc, not a pipe

  Update the header comment: it currently says the script guards three contracts; this makes
  four.

  `doctor.py`'s portability check sweeps plugin-root `scripts/`, so the new Python file must
  not spell out a `/Users/`-style path even in a comment — the same trap milestone 6 hit.

  **Logging:** `check_knowledge_stamps.py` emits a `  · ` trace line per file scanned under
  `DEBUG=1` / `LOG_LEVEL=debug`, and documents **both** triggers in its usage docstring —
  `doctor.py` documents only one, which verification flagged.

  *Depends on: Tasks 1, 3, 4, 5, 6, 7 — there must be stamped files to validate, and
  MANIFEST.md is one of them.*

### Phase 5 — Documentation

- [x] **Task 9 — Documentation checkpoint (`/aif-docs`)**

  Two reader-facing documents state a component count that is wrong, and several describe
  `knowledge/` as not yet built.

  | File | Change |
  |---|---|
  | `.ai-factory/DESCRIPTION.md` | "~40 component plugins" → **34 registrations across 31 files**, citing `RegisterComponentService`. Move `knowledge/` from "Not yet created" into the inventory |
  | `.ai-factory/ARCHITECTURE.md` | Same "~40" correction in the `knowledge/` folder-structure comment |
  | `AGENTS.md` | Add `knowledge/` to the Project Structure tree and Key Entry Points; drop it from the "Not yet created" line |
  | `README.md` | Status blockquote: the knowledge base now exists |
  | `docs/getting-started.md` | Move `knowledge/` out of "What is not here yet" |
  | `docs/dgf-knowledge.md` | Line 91: "~40 self-contained component plugins" → **34** — the third occurrence, missed by the original table. Also point at `knowledge/README.md` as the operative contract |

  Then re-run the maintenance check and require a clean or warnings-only result:

  ```bash
  bash scripts/check-dual-schema-docs.sh
  ```

  Every edited document stays under the existing contracts: both schema families where
  schemas are mentioned, no absolute paths in link targets or fenced blocks,
  `docs/schemas/` never cited as the DGF schema location without its qualifier.

  **Logging:** report the check script's exit code and every finding, not just the verdict.

  *Depends on: Tasks 1-8.*

---

## Commit Plan

Nine tasks, so checkpoints rather than one commit. Each checkpoint leaves the tree in a
state where both checks still pass.

| Checkpoint | Tasks | Message |
|---|---|---|
| 1 | 1 | `feat: add the DGF knowledge stamping convention` |
| 2 | 2, 3 | `feat: vendor the DGF schema set with a provenance manifest` |
| 3 | 4, 5 | `feat: add schema-family and component-catalogue facts` |
| 4 | 6, 7 | `feat: add composition-spec and naming-convention facts` |
| 5 | 8 | `test: assert knowledge frontmatter stamps` |
| 6 | 9 | `docs: record the knowledge base across reader-facing docs` |

Checkpoint 5 is the one that turns red before checkpoint 6 lands, for the same reason
milestone 6's checkpoint 3 did: the check asserts documentation claims that Task 9 fixes.
If that matters, commit 8 and 9 together.

---

## Risks

- **3.5 MB vendored into a shipped plugin.** Every installer pays this. It is the decided
  trade in `docs/dgf-schemas.md` §9 — a validator that reaches outside the plugin breaks on
  install — but it is worth re-examining if the plugin is ever size-constrained.
- **`format-coverage.md` is hand-maintained and already 13 days stale.** Every parity claim
  in `knowledge/` inherits that staleness. Classifying it as a policy fact with a review
  date is the mitigation; it is not a fix.
- **The stamped `dgf_version` lags the framework.** 1.1.11 against tags reaching 1.1.15.
  Facts with `since: "1.1.15"` will sit above the plugin's own baseline. That is expected
  under Design Decision 3 and must not be "corrected" by stamping a tag.
- **Digest drift is silent until milestone 8.** Task 8 validates that stamps are
  *well-formed*, not that they still *match upstream*. Nothing catches a schema changing in
  DGF until the drift check is written.
- **The count correction has reach.** "~40" may appear in more places than Task 9's table.
  Grep before assuming the list is complete.

## Out of Scope

Named explicitly so `/aif-verify` does not read their absence as an omission:

- The drift check comparing stamps and digests against a consumer's DGF checkout —
  milestone 8, per [ADR 0003](../docs/adr/0003-version-gating.md) §Follow-ups
- Dual-schema, parity-aware config validators and the four process-semantic checks —
  milestone 8
- A superseding ADR correcting 0003 §2's `until` comment and its tag-rejection rationale —
  worth doing, but a decision record is not a knowledge-base task
- Fixing `git.base_branch: main` in `.ai-factory/config.yaml`
- `/dgf-*` skills that consume this knowledge — milestones 9 and 11
- The canonical service spec schema (`spec-schema-v0.9.md`) and its lint rules — explicitly
  out of scope per `docs/dgf-schemas.md` §11
