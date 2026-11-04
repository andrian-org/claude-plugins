---
sources:
  - path: src/Tools/dgf-mcp/Services/SchemaIndexService.cs
    sha256: f421f5e81d77eddfcc8f2f59dbab187049a41e2b6bff031a07ff8f06387306de
  - path: docs/wiki/AI-Authoring/format-coverage.md
    sha256: d1e77ed0dd0d14680fe9d0df2af04534e689486a6b2b09e35d3720db01a8a01b
  - path: src/Tools/dgf-mcp/Schemas/XSD/form.xsd
    sha256: e12bf90d5a01f82d4dff0e92b6b4d7bf81fce069bc825cc11852a8da6b8da04e
  - path: src/Tools/dgf-mcp/Schemas/XSD/grid-form.xsd
    sha256: 9e9216e7958f9ff51b7211d3864ba976cba53cd0d8f36ad797d2f2106181cf32
  - path: src/Tools/dgf-mcp/Schemas/XSD/lookup-view.xsd
    sha256: 51feca68ad2c0eea61a7ff852b414dc78de12bc199194d3c262336ed1e082593
  - path: src/Tools/dgf-mcp/Schemas/XSD/options.xsd
    sha256: 9a2df54423350285013c670768eb0ec982152813add887c87f89799f48120ad4
  - path: src/Tools/dgf-mcp/Schemas/XSD/process.xsd
    sha256: f46988a29f38bd71fbb1d8fb771a8d3aa16fef543cadc8bf56ea05fd2ca86187
  - path: src/Tools/dgf-mcp/Schemas/XSD/profile.xsd
    sha256: c67be101c915bc9e1da513de21512634fd909e56d82e88ed859ec5cfc37569c7
  - path: src/Tools/dgf-mcp/Schemas/XSD/settings.xsd
    sha256: ce32b274b92d2dfd1134ad4ffd1b1ea5d6e1c51621660a43b5f262becf004fc9
  - path: src/Tools/dgf-mcp/Schemas/XSD/table-view.xsd
    sha256: ab2d3956fd5a2e4247f4ddc88f2068d3e2e3a30f59288f80735beafc1fee8e89
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
