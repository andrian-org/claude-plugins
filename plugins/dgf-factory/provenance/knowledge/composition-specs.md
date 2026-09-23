---
sources:
  - path: src/Core/DGF.Kernel/WorkspaceSettings.cs
    sha256: 8c7f8c588fe93b14c88d098eed047d3de015340e79dd3d3d4ecb34e70bef7f30
  - path: docs/wiki/AI-Authoring/format-coverage.md
    sha256: b2abde1173c4f6a9f36142705ec9a32ea1cd0deda73d7be9408a0fd4432f2fcd
  # hand-authored standalone contract, not the generated set
  - path: docs/schemas/eventBase.schema.json
    sha256: ecbfecefe9c3ab22b6eb0af104c62f8ccbd1d96dc4a741f145440f1c6734caeb
  # hand-authored standalone contract, not the generated set
  - path: docs/schemas/dataFetcherConfiguration.schema.json
    sha256: 61995e23dd027aa43f52ca3455967b944fedf856955ca29751ff98c0c110d76e
---
# Provenance — `knowledge/composition-specs.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/composition-specs.md`](../../knowledge/composition-specs.md) were read from, with the digest of each file as
read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says
from where. The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md)
and [`knowledge/README.md`](../../knowledge/README.md) §1.
