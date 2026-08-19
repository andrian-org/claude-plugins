---
name: doc-coverage-audit
description: Audit which documents exist for a given system, product, or project against a deliverables/requirements checklist, and produce a verified checklist-to-document mapping table with gap analysis. Use when the user asks to "find all documents for X", "map deliverables to documents", "check documentation coverage", "what's missing for hand-over", "build a deliverables index", or wants SharePoint/Graph/Confluence/Drive/local docs located and matched to a numbered list of required items. Also use for project close-out, due-diligence, audit-evidence, or knowledge-transfer document sweeps.
---

# Documentation Coverage Audit

Locate every document that exists for a **target system** across a document repository, map
those documents onto a **checklist of required deliverables**, and report honestly on what is
missing.

The deliverable is a table: `deliverable | link(s) + document name(s) | comments`, followed by a
gap analysis. Every link must be verified before you hand it over.

## The one rule that matters

**Gaps are the most valuable output.** Anyone can list files. The reason this audit exists is to
find the items with *nothing* behind them. Never pad a row to look complete — never map a
plausible-sounding document to a deliverable it does not actually satisfy. An honest
`— none found —` with a note on where the evidence probably lives is worth more than a
confident wrong link.

## Phase 0 — Pin down the scope

Get these four things before searching. Ask only if you cannot infer them.

1. **The checklist** — the numbered list of required deliverables. Read it fully first; its
   vocabulary tells you which search terms will hit.
2. **The target system** — the thing being audited (`ZamConnect`, `PaymentsAPI`, …), plus its
   aliases, codenames, predecessors and misspellings. Systems get renamed; old docs keep old names.
3. **The repository root** — where to start.
4. **Output location** — where the report file goes.

Then set expectations: **the target's own named folder will not contain most of its documents.**
Plan for a repository-wide sweep from the start.

## Phase 1 — Get read access

Work down this ladder and stop at the first rung that works. Full command-level detail,
error strings and fixes: `references/graph-auth.md`.

1. **Already-working CLI/API access** — try it before assuming anything.
2. **An existing token or session** on the machine.
3. **A pre-consented first-party app** — check what the tenant *already* trusts before proposing
   any change. This is usually the answer and it is invisible unless you look.
4. **A new grant, app registration, or connector** — a real change to someone's tenant.
   **Stop and ask** before doing this; present the options and their blast radius.

Two hard-won points:

- **Never work around a blocked credential action.** If the sandbox or a hook blocks an auth
  call, that is a signal to surface the situation to the user, not to find another route to the
  same secret. Explain what you need and let them decide.
- **Tokens expire mid-audit** (typically ~1 h). Write a refresh helper *before* the long
  enumeration, not after it fails halfway through.

## Phase 2 — Find the footprint

Run these in parallel; each finds things the others miss.

| Probe | Finds |
|---|---|
| Filename search for the target + each alias | The obvious core documents |
| Site/space/project search for the target name | **Dedicated sites you did not know existed** |
| Full-text search | Documents that never name the target in the filename |
| Checklist-vocabulary search (`"test strategy"`, `"architecture"`, …) | Docs that cover the target without naming it |
| Group/team membership of the current user | Site names that hint at where work happened |

Then **look at the shape of the folder tree**. Repositories built for hand-over often name
folders after the checklist itself (`3. System-administration guides…`). When you see that,
you have found the curated set — and any such folder that is **empty is a finding**, not an error.

Tips that save a lot of time:

- **Filename search beats full-text search** for building a candidate pool. Full-text matched
  1000+ noisy hits in the session this skill came from; filename search returned ~35 usable ones.
- **Search results often omit the parent path.** Derive the path from each result's URL instead.
- **Distinguish curated from working copies.** A closeout/deliverables tree is what the client
  gets; a drafts/WIP tree usually holds far more (and the only copy of some things). Cite the
  curated copy as primary and the working copy as supporting.

## Phase 3 — Enumerate

Recursively walk each promising subtree and record `path`, `name`, `url`, `size`, `modified`
into one consolidated index. Use `scripts/walk_tree.py`.

- **Walks are slow — run them in the background** (`nohup … &`) and keep working while they run.
  A large tree can take many minutes; a foreground walk will hit a tool timeout.
- **Cap recursion depth** so a pathological tree cannot hang the audit.
- Cheap, high-value counts to pull from the index: total files, files per subtree, extension
  histogram, distinct filenames. These become the quantitative claims in your report
  ("60 institution folders, 384 files, 201 JSON") — far more useful than prose.
- **Note anything sensitive you pass** (`.pfx`, `.jks`, `.pem`, `.env`, credential
  spreadsheets). Do not include them as deliverables; list them as an exclusion warning.

## Phase 4 — Map checklist to documents

For each checklist item, decide honestly which of three states it is in:

| State | Meaning |
|---|---|
| ✅ **Covered** | A document exists whose actual purpose is this deliverable |
| ⚠️ **Partial** | Content exists but is embedded in a broader document, is a *register* where a *procedure* was asked for, or covers the platform rather than this system |
| ❌ **Missing** | Nothing found. Say so, and say where the evidence probably lives |

Recurring patterns to test for explicitly — each one produced a real finding last time:

- **Per-component vs per-system.** Test strategies, UAT reports and requirements often exist for
  every *sub-service* but never for the *integration layer* itself. Check both altitudes.
- **Register ≠ procedure.** A spreadsheet of security routes is not a security procedure.
  Grade it ⚠️, not ✅.
- **Tooling ≠ documented process.** A folder of runnable API test collections does not satisfy
  "API testing procedures".
- **Tracker-resident evidence.** Defect registers, work items and CI pipeline configs usually
  live in Jira/Azure DevOps/GitHub, not the document repo. A zero-result search for "defect" is
  a finding: name the tracker as the required export.
- **Stateless components.** Do not invent a database deliverable for something that stores
  nothing — state that it is stateless and where the data model actually lives.
- **Multiple versions.** Prefer the newest, but say which you chose and that currency needs
  confirming against production.

Multi-item documents are normal: one architecture spec can legitimately serve several rows.

## Phase 5 — Verify every link, then write

**Non-negotiable: programmatically check that every URL resolves before delivering.** Use
`scripts/verify_links.py`. In the source session, 2 of 112 links were silently wrong — both
paths reconstructed by hand from search output rather than taken from an enumeration result.
Take paths from the index; never retype them.

Then generate the report with `scripts/render_report.py`, or write it directly. Structure:

1. **Header** — target system, date, how it was searched.
2. **Scope table** — each repository root actually swept, as a link. Makes the audit reproducible.
3. **Main table** — `# Deliverable | Links & document names | Comments`.
   Put multiple documents in one cell, one per line. Keep comments substantive: which document
   is authoritative, what is only partial, what the gap is.
4. **Summary** — counts by ✅ / ⚠️ / ❌ with item numbers, and empty folders found.
5. **Follow-up actions** — numbered, specific, each naming who or which system must supply the
   missing artefact.
6. **Exclusions** — secrets and anything else that must not ship to the client.

Prefer **clean path-based URLs** over API-returned viewer URLs (`…/_layouts/…?sourcedoc={GUID}`)
where the repository supports both: they are readable, stable and reviewable in a diff.

## Reporting back

Lead with the gaps and the numbers, not the process. State the link-verification result
explicitly. If you corrected anything mid-flight, say so plainly and move on. Do not attempt to
fill the gaps by authoring the missing documents unless asked — flag them and let the user scope
that work.

## Files

- `references/graph-auth.md` — SharePoint/Microsoft Graph auth ladder, exact errors, fixes,
  KQL search syntax, path-vs-viewer URL construction. **Read this before touching SharePoint.**
- `references/environment-notes.md` — macOS/sandbox gotchas that break naive shell commands.
- `scripts/graph_helper.sh` — token acquisition, refresh, authenticated GET.
- `scripts/walk_tree.py` — recursive drive enumeration to JSON.
- `scripts/search_graph.py` — filename/full-text search with paging.
- `scripts/verify_links.py` — resolve every URL in a report; exit non-zero on any break.
- `scripts/render_report.py` — turn a mapping spec into the final markdown table.

Adapt these for non-SharePoint repositories; the five phases and the honesty rule do not change.
