---
sources:
  - path: src/Core/DGF.Kernel/WorkspaceSettings.cs
    sha256: 8c7f8c588fe93b14c88d098eed047d3de015340e79dd3d3d4ecb34e70bef7f30
  - path: docs/wiki/AI-Authoring/format-coverage.md
    sha256: d1e77ed0dd0d14680fe9d0df2af04534e689486a6b2b09e35d3720db01a8a01b
  # hand-authored standalone contract, not the generated set
  - path: docs/schemas/eventBase.schema.json
    sha256: ecbfecefe9c3ab22b6eb0af104c62f8ccbd1d96dc4a741f145440f1c6734caeb
  # hand-authored standalone contract, not the generated set
  - path: docs/schemas/dataFetcherConfiguration.schema.json
    sha256: 61995e23dd027aa43f52ca3455967b944fedf856955ca29751ff98c0c110d76e
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
    sha256: 2028ec64dda6d6dac67ca01bc02163bb9aabd79380586bd76869931b4d74d40e
  - path: src/Core/DGF.DataSources/DataSourceLoader.cs
    sha256: 24e3b570fcc4e533640f03370d8278e9b3eae461dc8ebb6860ac9f8b42eab8d6
  - path: src/Core/DGF.DataSources/Endpoints/EndpointFactory.cs
    sha256: d0f6f004156c4ba2b07960f263a1033cb6d95dd7799e44f85e77168bea3f060d
  - path: src/Components/DGF.Components.Shared/ComponentFileLoadService.cs
    sha256: 5d5ca13b8dd3f5b2192535776c2d5c0245c361677dc168247478733f17ad3b1d
  # §1.2 — the applibs* folders and where the base workspace is mounted from
  - path: src/samples/workspaces/readme.md
    sha256: 25a0d3dbd73d5cca2af538a7200037b421b1e517664fb3141fdc38c155cc07db
  - path: src/Core/DGF.Kernel/Configuration/ApplicationConfig.cs
    sha256: b0a5cbcbf1b5f0f1e6577cc57f8a0613476916abf0b285334537a1ed837ad9e3
  - path: src/Core/DGF.Kernel/Extensions/AssemblyLoader.cs
    sha256: 0fd85b34de7ce07070701a2a1384beaa3401ca2d4575b1784438b6c4e9822c00
  # §1.2 and §5 — the sample deployments' workspace and asset bind-mounts
  - path: src/samples/DGF.Compose/docker-compose.zims.yml
    sha256: 1d371e0eae65c91755a251606492a531e37a616c239835068a0cdebae8f1c2b9
  - path: src/samples/DGF.Compose/docker-compose.ecouncil.yml
    sha256: 3dfef1f50a12e949b8c64c684a75b1854a18d5f37b765bed7496713896f6b80c
  # §5 — the UI shell's three custom files, their defaults and how they are served
  - path: src/DGF.UI/src/app/components/app/app.component.ts
    sha256: 2a231e0692b683b6d33f5bcdb4e26f1d268e3ae99df351aa42c6a96f95d91d99
  - path: src/DGF.UI/angular.json
    sha256: 53cfbd09744983f409eea28eec5c986f19c2e5cc7ca07673f102c189f0560c7e
  - path: src/DGF.UI/nginx-ng.conf
    sha256: 310c00cbe781524898827cc255d6ad3beadf5fe183eadb69220f689e91b204fc
  - path: src/DGF.UI/src/assets/js/formhelper.js
    sha256: 4884a131c72113cf4dc8d3926cd36093f5ac1d59ae7bcfb26b58c850fcb309c5
  - path: src/DGF.UI/src/assets/js/formshared.js
    sha256: f6e8a117096f18b3ea9e64b85b58305114482d8b77fd21d8ea408bfd35ff1be8
  - path: src/DGF.UI/src/assets/styles/custom.css
    sha256: 77bab74088530734c42b312a38865fd5b818fa807b126b0ea6e733637c7a3e5f
  # §5 — the /application and /webasm static-file mounts
  - path: src/DGF.API/ConfigureServices.cs
    sha256: 219b5e33610ee2339d4fd67661abff6281168ca69d3d197e13dc7bf3254eb7a3
  - path: src/DGF.UI/src/index.html
    sha256: c492af0365ca05b5fc0007b9164c2c9b85ff80d4810ad4caf3ee869b89749458
  - path: src/DGF.UI/src/app/services/theme.service.ts
    sha256: 6688dbc54c5e785859f805ae94390632ed7429724952b783072f4f55e932a3ac
  - path: docs/wiki/Release-notes/RELEASE-1.3.0.md
    sha256: e52f588bb4ec45dabf79061c89353235ef7f746e578d4aade938ff37cddb568c
---
# Provenance — `knowledge/composition-specs.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/composition-specs.md`](../../knowledge/composition-specs.md) were read from, with the digest of each file as
read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says
from where. The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md)
and [`knowledge/README.md`](../../knowledge/README.md) §1.

§1.2 and §5 were read on 2026-09-25 at DGF `aa1d5c4c2` (`develop`), the same commit as the rest
of this file; `FormManager.cs` and `WorkspaceSettings.cs` were re-read then and their digests are
unchanged. The five `applibs*` folders were inventoried by listing
`src/samples/workspaces/applibs*/` (only `.dll` files, no `FM/`); a directory listing has no
digest, so the samples' readme stands for it here.
