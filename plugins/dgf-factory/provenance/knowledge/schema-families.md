---
sources:
  - path: src/Tools/dgf-mcp/Services/SchemaIndexService.cs
    sha256: 2558a66391ef4fbc8d5d7918ce9d66a4cf8aeb37dd8553a45807a11eb23df8c9
  - path: docs/wiki/AI-Authoring/format-coverage.md
    sha256: b2abde1173c4f6a9f36142705ec9a32ea1cd0deda73d7be9408a0fd4432f2fcd
  - path: src/Tools/dgf-mcp/Schemas/XSD/form.xsd
    sha256: 382980eda2104aad8bcad8e42ffb9b185d08290d27d91dc9380c59da2764a685
  - path: src/Tools/dgf-mcp/Schemas/XSD/grid-form.xsd
    sha256: 59df49ce2fd0756410b6386f870bcd3e0066dbc994b39f83a6f5751a064e3459
  - path: src/Tools/dgf-mcp/Schemas/XSD/lookup-view.xsd
    sha256: 2e5c31ae7c00093e6288c9975d4ae5ca92f6897d04c63e275f30c1677fa82d76
  - path: src/Tools/dgf-mcp/Schemas/XSD/options.xsd
    sha256: 9a2df54423350285013c670768eb0ec982152813add887c87f89799f48120ad4
  - path: src/Tools/dgf-mcp/Schemas/XSD/process.xsd
    sha256: 7adf1ea3f94f10e0606112d78e5dc49c528cd93bdfe41e7dc4251cc3546de121
  - path: src/Tools/dgf-mcp/Schemas/XSD/profile.xsd
    sha256: 884dcc5a04e343513a499b0e861e6a1a8cf67928c401e64f3c5f6bafcb0b65a4
  - path: src/Tools/dgf-mcp/Schemas/XSD/settings.xsd
    sha256: 6c8265271620860ac3a607d2936266811b277b78fe069856214f46360e972bb9
  - path: src/Tools/dgf-mcp/Schemas/XSD/table-view.xsd
    sha256: afd9befe47332b1cd1a9fdc9d8e893bfcde2b5382babe9cf054c88771c5ff783
  - path: src/Tools/dgf-mcp/Schemas/XSD/workflow.xsd
    sha256: afc3eb4f23c379012f8fb23609f03daedffeaadff08527b0990507c6c41cdff8
  - path: src/Components/DGF.Components.Services/JsonConverters/ComponentConverter.cs
    sha256: 772d63668a13942df8b43bf4937fc255d12a5049129fbcb3816c75ca16ea78fd
  - path: src/Components/DGF.Components.Shared/Enums/ComponentType.cs
    sha256: c4537aca552b01ed5b7f4fcae929db06913f002cce5386cf1f2084ab9e6384e1
  - path: src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs
    sha256: c99435834fd8d306c833eef6f5cd09dc13fad8c0a02da8786c61bba1c99e3df0
  - path: src/Core/DGF.Domain/Data/View/ViewManager.cs
    sha256: a8654d08ea30788938242ef19ad7079704df6e9c5342687b230a72b11df860a5
  - path: src/Core/DGF.Domain/Data/Lookup/LookUpViewManager.cs
    sha256: f47230cb79a77e3cad802c066ec597bcb4900463a1e670a4ce0be091c44f5d23
  - path: src/Core/DGF.Domain/Data/EditableGrid/EditableGridManager.cs
    sha256: 66941b29b2a35731aca24b532be267570dc666aae1e611bcb528c13591961f98
---
# Provenance — `knowledge/schema-families.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/schema-families.md`](../../knowledge/schema-families.md) were read from, with the digest of each file as
read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says
from where. The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md)
and [`knowledge/README.md`](../../knowledge/README.md) §1.
