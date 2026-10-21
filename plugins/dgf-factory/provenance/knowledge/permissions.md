---
sources:
  - path: src/Core/DGF.Infrastructure/Persistence/Seed/ApplicationDbContextSeed.cs
    sha256: d0b8f980682d6fd180f4202a8b895fa77042d3395c253031ddc97d96f1d2984a
  - path: src/Core/DGF.Kernel/Constants/UserRoleConstants.cs
    sha256: 11dc32eef52095dbcda8a82cc6eb197671d9dc21d79d2449559ce785fb326c21
  - path: src/Core/DGF.Domain/Application/Map/ApplicationMap.cs
    sha256: 68b4fb41322ce3c746f743e6c02eb3d0e689835897b8988a8705d27ba053c20b
  - path: src/Core/DGF.Domain/Application/Map/ApplicationMapNode.cs
    sha256: b1f449c1871ccae04161e5cb3916fa0db94a1fea3a6e8c27c4cdab9461977c6a
  - path: src/Core/DGF.Domain/Application/Map/ApplicationMapService.cs
    sha256: a84b53bd4eb00dbc80a80b2e85a55f5ccd723a52c611a23d1bebf7c5ecdfde39
  - path: src/Components/Extensions/DGF.Sitemap/SiteMap/SiteMapManager.cs
    sha256: 514b1fc09da059629e13cbc95b2d3b9558c9e1dd2b719648fa15544a709fa7fd
  - path: src/Components/Extensions/DGF.Sitemap/SiteMap/Options/SiteMapOptions.cs
    sha256: 94f81b82b0396ddfc729d6743c2a8f854aba35ac1cf38b34e29e79411097e377
  - path: src/Components/DGF.Components.Shared/ComponentFileLoadService.cs
    sha256: 5d5ca13b8dd3f5b2192535776c2d5c0245c361677dc168247478733f17ad3b1d
  - path: src/Core/DGF.Domain/Profile/TreeManager.cs
    sha256: d62ccce401c7e81934ac1d76ead770217b78611f42b0d1f979b93719be293467
  - path: src/Core/DGF.DataViewer/ProfileHelper.cs
    sha256: 15f3eacc71e4776313cb5c531ebeaee0a4bf95e4c125fc01140dfacf644c7ec4
  - path: src/Core/DGF.Domain/Process/StateProcess/Task.cs
    sha256: 92a34555ba4d47a987cfba67f57b23833530d26000ae53c3c2c8a138b4bb2c8f
  - path: src/Core/DGF.Domain/Process/StateProcess/MultiTaskGroup.cs
    sha256: 9de7b1df1e82ae8fad72ccf058ac88e9405fc9d0d07a233ea5e593d2c6d2d1b5
---
# Provenance — `knowledge/permissions.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/permissions.md`](../../knowledge/permissions.md) were read from, with the digest of each file as
read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says from where.
The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md) and
[`knowledge/README.md`](../../knowledge/README.md) §1.

Read on 2026-09-27 at DGF `cccd4325b`. `CheckPermissions` is `SiteMapManager.cs:614-629`, called for each
`_application.sitemap` node in `CreateRouteAndLink` (`:443`); the claim filter is `FilterClaimBasedPaths`
(`:495-555`). The profile group is `ProfileHelper.GetUserProfileGroupOrDefault`, read by
`RouterMappingService` before `TreeManager.LoadTreeAsync`.

Sample counts were measured over `src/samples/workspaces` with Python's `xml.etree` and `grep`:
`_application.sitemap` exists in `dgf` and `zims` only; `requireClaims` appears in `webasm`'s and `zims`'s
`sitemap.json`, always naming `currentEntityId`; no `roles` or `deny` token has surrounding spaces; no
MultiTask `TaskGroup` names a role.
