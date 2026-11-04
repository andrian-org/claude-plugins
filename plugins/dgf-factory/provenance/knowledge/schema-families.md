---
sources:
  - path: src/Tools/dgf-mcp/Services/SchemaIndexService.cs
    sha256: 61002f0c313cf63aa3a24e7a7ed3f373b4864dc5be1a381bf2cdd8b07826d8c3
  - path: docs/wiki/AI-Authoring/format-coverage.md
    sha256: d1e77ed0dd0d14680fe9d0df2af04534e689486a6b2b09e35d3720db01a8a01b
  - path: src/Tools/dgf-mcp/Schemas/XSD/form.xsd
    sha256: 8d3c592a3b0a7cc1dce808c60808f6335f925249cd1a2f2f0bd4ee9770b1e882
  - path: src/Tools/dgf-mcp/Schemas/XSD/grid-form.xsd
    sha256: 9e9216e7958f9ff51b7211d3864ba976cba53cd0d8f36ad797d2f2106181cf32
  - path: src/Tools/dgf-mcp/Schemas/XSD/lookup-view.xsd
    sha256: 033b0254342f2fb0d5146abcbe0457b3d1ece249cd17b1b66c6755bec960a36a
  - path: src/Tools/dgf-mcp/Schemas/XSD/options.xsd
    sha256: 9a2df54423350285013c670768eb0ec982152813add887c87f89799f48120ad4
  - path: src/Tools/dgf-mcp/Schemas/XSD/process.xsd
    sha256: f46988a29f38bd71fbb1d8fb771a8d3aa16fef543cadc8bf56ea05fd2ca86187
  - path: src/Tools/dgf-mcp/Schemas/XSD/profile.xsd
    sha256: e03f293d1230f4a3a8da55338461116c3eb1cc9285ab1e56ed35637315e16083
  - path: src/Tools/dgf-mcp/Schemas/XSD/settings.xsd
    sha256: 153b064884d2419d6ba5ca63b00a72fcc794d96f1fb396eca828520b022ca638
  - path: src/Tools/dgf-mcp/Schemas/XSD/table-view.xsd
    sha256: a85ab18f66e0dfa60a94f599a3f6c8beb7acede646010df1cb004e5b4f3c7c18
  - path: src/Tools/dgf-mcp/Schemas/XSD/workflow.xsd
    sha256: 6ab64e9c06d6c42bd18b7365cb3c69b3a23204fce4972d1f6a38c8c28263a622
  - path: src/Components/DGF.Components.Services/JsonConverters/ComponentConverter.cs
    sha256: 772d63668a13942df8b43bf4937fc255d12a5049129fbcb3816c75ca16ea78fd
  - path: src/Components/DGF.Components.Shared/Enums/ComponentType.cs
    sha256: 72b714d3b6fe8f7b5d9926262f04acc223ca6d24f58b75d863ce74f26469faac
  - path: src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs
    sha256: c99435834fd8d306c833eef6f5cd09dc13fad8c0a02da8786c61bba1c99e3df0
  - path: src/Core/DGF.Domain/Data/View/ViewManager.cs
    sha256: a8654d08ea30788938242ef19ad7079704df6e9c5342687b230a72b11df860a5
  - path: src/Core/DGF.Domain/Data/Lookup/LookUpViewManager.cs
    sha256: f47230cb79a77e3cad802c066ec597bcb4900463a1e670a4ce0be091c44f5d23
  - path: src/Core/DGF.Domain/Data/EditableGrid/EditableGridManager.cs
    sha256: 66941b29b2a35731aca24b532be267570dc666aae1e611bcb528c13591961f98
  - path: src/Tools/dgf-mcp/Schemas/XSD/application-sitemap.xsd
    sha256: 1b1864bd811d087f28195b103295eb4225042079004e74ab6d4438509a544857
  - path: src/Core/DGF.DataSources/JsonConverters/DataSourceConverter.cs
    sha256: fc5204bd8799da796b7dade09c8c3ffe9b77d1cbaf64f7ff3fbe35c8500628a1
---
# Provenance — `knowledge/schema-families.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/schema-families.md`](../../knowledge/schema-families.md) were read from, with the digest of each file as
read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says
from where. The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md)
and [`knowledge/README.md`](../../knowledge/README.md) §1.
