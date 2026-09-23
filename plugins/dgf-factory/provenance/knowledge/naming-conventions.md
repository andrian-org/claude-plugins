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
---
# Provenance — `knowledge/naming-conventions.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/naming-conventions.md`](../../knowledge/naming-conventions.md) were read from, with the digest of each file as
read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says
from where. The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md)
and [`knowledge/README.md`](../../knowledge/README.md) §1.
