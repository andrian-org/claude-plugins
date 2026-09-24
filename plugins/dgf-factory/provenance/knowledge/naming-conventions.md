---
sources:
  - path: src/Core/DGF.Kernel/WorkspaceSettings.cs
    sha256: 8c7f8c588fe93b14c88d098eed047d3de015340e79dd3d3d4ecb34e70bef7f30
  - path: docs/wiki/AI-Authoring/format-coverage.md
    sha256: b2abde1173c4f6a9f36142705ec9a32ea1cd0deda73d7be9408a0fd4432f2fcd
  - path: src/Tools/dgf-mcp/Services/SchemaIndexService.cs
    sha256: 2558a66391ef4fbc8d5d7918ce9d66a4cf8aeb37dd8553a45807a11eb23df8c9
  - path: src/Components/DGF.Components.Shared/Enums/ComponentType.cs
    sha256: c4537aca552b01ed5b7f4fcae929db06913f002cce5386cf1f2084ab9e6384e1
  - path: src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs
    sha256: c99435834fd8d306c833eef6f5cd09dc13fad8c0a02da8786c61bba1c99e3df0
  - path: src/Core/DGF.OM/Workflow/WorkflowManager.cs
    sha256: 35d431414bb516a828f72e867cb7f544106bdc9b8a90edf243b49bb290fe16b7
  - path: src/Core/DGF.Domain/Data/Form/FormManager.cs
    sha256: 24b8018e502d2f5ce6967ad687cf2772062feb07ba6498ee007a6bb5cf59745a
  - path: src/Core/DGF.Domain/Data/Table/TableManager.cs
    sha256: 7956ab856905a77d4a34ba6331a34512c8af9587eb4a665ac60329beb93957e2
  - path: src/Core/DGF.Domain/Data/View/ViewManager.cs
    sha256: a8654d08ea30788938242ef19ad7079704df6e9c5342687b230a72b11df860a5
  - path: src/Core/DGF.Domain/Data/Lookup/LookUpViewManager.cs
    sha256: f47230cb79a77e3cad802c066ec597bcb4900463a1e670a4ce0be091c44f5d23
  - path: src/Core/DGF.Domain/Data/EditableGrid/EditableGridManager.cs
    sha256: 66941b29b2a35731aca24b532be267570dc666aae1e611bcb528c13591961f98
  - path: src/Core/DGF.Domain/Data/StaticOptionReader.cs
    sha256: 7062c1b433e5883303c6f42030675d3833607a60243d9f2d4ea58fa2cea29a34
  - path: src/Core/DGF.DataSources/DataSourceLoader.cs
    sha256: 24e3b570fcc4e533640f03370d8278e9b3eae461dc8ebb6860ac9f8b42eab8d6
  - path: src/Core/DGF.DataSources/Endpoints/EndpointFactory.cs
    sha256: d0f6f004156c4ba2b07960f263a1033cb6d95dd7799e44f85e77168bea3f060d
  - path: src/Components/DGF.Components.Shared/ComponentFileLoadService.cs
    sha256: 5d5ca13b8dd3f5b2192535776c2d5c0245c361677dc168247478733f17ad3b1d
  - path: src/Components/DGF.Components.Services/JsonConverters/ComponentConverter.cs
    sha256: 772d63668a13942df8b43bf4937fc255d12a5049129fbcb3816c75ca16ea78fd
  - path: src/Components/DGF.Services.Extensions/ComponentServiceProvider.cs
    sha256: 34530516d18b7b4b113c6c23eb172a7d7815a27e18215b9e1cb3c3d1efe12194
---
# Provenance — `knowledge/naming-conventions.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/naming-conventions.md`](../../knowledge/naming-conventions.md) were read from, with the digest of each file as
read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says
from where. The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md)
and [`knowledge/README.md`](../../knowledge/README.md) §1.
