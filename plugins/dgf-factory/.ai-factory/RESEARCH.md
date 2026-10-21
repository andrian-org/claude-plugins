# Research

Updated: 2026-09-29 22:55
Status: active

## Active Summary (input for /aif-plan)
<!-- aif:active-summary:start -->
Topic: `/dgf-scaffold` for the Zambia estate — what is common and what is specific across ZamOffice (`webasm`), eCouncils, ZILAS, ZMA and ZIMS, and which of it becomes a scaffold option.

The first finding is that this is not "drive an existing template". There is no generator. All four apps are clones of the ZamOffice repo shape, so `/dgf-scaffold` would be the first generator the estate has, and that conflicts with ADR 0004 §2. Everything below comes from the five reports. I spot-checked these numbers myself: 308, 1,015 and 888 files. I also confirmed ZMA's three tenant rows, its `WorkspaceName` per instance, and 8 files with hard-coded tenant GUIDs.

## Three layers, not one

```
 SOLUTION (identical shape in all 4)             WORKSPACE overlay              BASE (webasm)
 Web/ (DGE host, ~empty)                         FM/{_DATA,_WORKFLOW,           supplied at image build:
 EServices.API/ ── runs twice: front + back        _PROFILE,_PROCESS,             COPY --from=zamoffice image
 Components/{External,...}                         _COMPONENTS,Templates}         /workspaces/webasm   (pinned tag)
 Database/ (SSDT + StaticTables seeds)           _application.sitemap           local: bind-mount a ZamOffice
 Compose/  azure-pipelines  helm values          js/forms.shared.js             checkout
                                                 BASE:Name → webasm
```

The `BASE:` resolution is the only extension contract, and it is real. `zamoffice` uses it in 308 files, ZIMS in 450, ZILAS in 817 and eCouncils in 1,015.

## Common core (safe as defaults)

- **Solution:**
  - `Web` host with `BuildDotGovEngine()`.
  - `EServices.API` with `AddZamPay`, `AddDgNotify` and `AddDgNotifyOtp`, plus the job scheduler.
  - `Components/External`, an SSDT `Database/`, Compose and Helm values.
  - The `ZamCloud/pipeline-templates` pipeline.
- **appsettings blocks:** DGPass OIDC, Notify and OTP, ZamPay, DgSign, RegistrationAuthority, NIR/ZamConnect (with a `t/<name>` path), PinCodeSign, the distributed cache and Seq.
- **Workspace:** the FM skeleton, `_application.sitemap` with `BASE:_Portal*` links, `NirUserRegistrationPreRegIntranet`, the Workplace grid set, and the `Standard.Review_*` process family.

## Scaffold options (the axes that actually differ)

| Axis | Values seen |
|---|---|
| **Base supply** | Pinned image (ZIMS, ZILAS, ZMA). eCouncils forked it: 888 drifted files, and the intended `COPY --from` is commented out. A scaffold should offer only the pinned image. |
| **Instances** | Single (ZIMS, ZamOffice). Multi-instance (ZILAS with 4 departments, ZMA with 3 directorates). |
| **Org model** | Flat. Or an `AspNetTeams` council hierarchy (eCouncils). |
| **Designer host** | The `Web` builder is empty in ZIMS, ZILAS and ZMA, and commented out of their pipelines. It should default to off. |
| **Integrations** | ZRA, PowerBI, Gotenberg documents and ArcGIS maps are each optional. |
| **Reports** | SSRS and/or PowerBI. |

Two corrections to the framing:
- **ZMA is not runtime multi-tenancy.** It is multi-instance. ZILAS uses the same mechanism: the `WORKSPACE_NAME` build argument renames `_application-<ws>.sitemap`, and the pipeline builds N images. ZMA adds a shared database keyed by an `ApplicationId` column, with one `aspnet_Applications` row per instance. Isolation is by convention only, since there is no row-level security and by-name role lookups have caused real bugs. So there are two options here, not three: multi-instance, with or without the shared-database partition.
- **eCouncils' 34 `councils/` folders are not runtime config.** They are records for the AI harness in that repo. Per-council variation is done by forking forms, so `BuildingPermit<Council>` exists in about 20 copies.

## What every app gets wrong (never copy)

- **Secrets in git in all five, plus the ZMA `.mcp.json` and `Web/readme.md`.** They include OIDC secrets, SQL passwords, an Azure DevOps token, the PKI private key and the NuGet feed password. Every app's Helm values already use `__Token__` placeholders, so the scaffold should emit placeholders in appsettings too.
- **Environment URLs in base appsettings**, and `IgnoreSSLCertificateValidation=true`.
- **A duplicated, broken `Web/Dockerfile`** (two `final` stages).
- **Near-identical appsettings per instance.** Lands and Deeds differ by about 12 lines.
- **Stray `BASE:` references.** ZILAS has some that resolve to nothing, and one on a locally-defined table. The agent's check was name-based, so some may be false positives. I haven't checked any yet.
- **`webasm` isn't a clean base.** It holds Zambia-domain content (`ZIGS_*`, NIR). The scaffold shouldn't try to fix that.

## Open questions (they change the design)

1. **ADR 0004 §2 no longer holds for Zambia.** It says the skill "drives a template; does not emit files". There is no template. Options: a new ADR that supersedes §2 for this scope, or a "clone-and-parameterise" design.
2. **Where does Zambia knowledge live?** You said this is feasible for Zambian projects only. Estate specifics such as `ZamCloud/pipeline-templates`, ZamPay and NIR probably don't belong in a general DGF plugin, so consider a separate pack or plugin. It would also need ledgers that cite estate repositories, not DGF ones.
3. **Which base tag is authoritative?** The pinned tags disagree across repos (`alpha.3` and `alpha.4`). The scaffold has to ask, or read a single source of truth.
4. **How much does it generate?** Solution plus a minimal workspace is clearly in scope. The domain is not: no `ZIGS_*` content, no per-app modules.

Two things I haven't verified: how the engine maps `WorkspaceName` to `ApplicationId` (it is inside the NuGet packages), and ZILAS's unresolved `BASE:` references.
<!-- aif:active-summary:end -->

## Sessions
<!-- aif:sessions:start -->
### 2026-09-29 22:55 — Zambia estate survey for /dgf-scaffold
What changed: Five read-only agents surveyed ZamOffice (`webasm`), eCouncils, ZILAS, ZMA and ZIMS. The synthesis above was written to this file verbatim at the user's request.
Key notes: Spot-checked by hand: 308 `BASE:` files in `zamoffice`; 1,015 in `ecouncil`; 888 differing same-path files between the two `webasm` copies (191 only in eCouncils); ZMA's three tenant rows in `aspnet_Applications`; `WorkspaceName` `zma`, `lm` and `sim` per API instance; 8 `_DATA` files with the ZMA tenant GUID hard-coded. Not verified: the engine's `WorkspaceName` to `ApplicationId` mapping, ZILAS's unresolved `BASE:` references, and the ZIMS and ZILAS override counts (agent-reported).
Links (paths): docs/adr/0004-authoring-entry-point.md, docs/adr/0023-dgf-specific-skills.md §7, /Users/andrianmamei/workspaces/zambiazigs/ZamOffice/ZamOfficeDGF, /Users/andrianmamei/workspaces/zambiazigs/eCouncil/eCouncil, /Users/andrianmamei/workspaces/zambiazigs/ZamOffice/ZILAS, /Users/andrianmamei/workspaces/zambiazigs/ZamOffice/ZMA, /Users/andrianmamei/workspaces/zambiazigs/ZamOffice/ZambiaZIMS
<!-- aif:sessions:end -->
