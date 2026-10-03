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
    sha256: 9bd0a62cd055f6d15cd05691b54940bd4ff10a57eb9ae0d0d3eae9bcfb135537
  # §5 — the UI shell's three custom files, their defaults and how they are served
  - path: src/DGF.UI/src/app/components/app/app.component.ts
    sha256: 11f7bb00e06264662f9d594ed4ed67d081854b3b268d1bf0cf0bed3d307bde4d
  - path: src/DGF.UI/angular.json
    sha256: e36da92c9b0ae83bc7bd9863540f5773c7e19a056d08f73404077660d49971c1
  - path: src/DGF.UI/nginx-ng.conf
    sha256: b85033b82705cf2b61b35c09d870343a2b78cf1a4e167b7ef31aa72bdcea40f6
  - path: src/DGF.UI/src/assets/js/formhelper.js
    sha256: 4884a131c72113cf4dc8d3926cd36093f5ac1d59ae7bcfb26b58c850fcb309c5
  - path: src/DGF.UI/src/assets/js/formshared.js
    sha256: f6e8a117096f18b3ea9e64b85b58305114482d8b77fd21d8ea408bfd35ff1be8
  - path: src/DGF.UI/src/assets/styles/custom.css
    sha256: 77bab74088530734c42b312a38865fd5b818fa807b126b0ea6e733637c7a3e5f
  # §5 — the /application and /webasm static-file mounts
  - path: src/DGF.API/ConfigureServices.cs
    sha256: 2b9414f21ee3e8817bad0e53da83a42e12de93edadf84312638106ded7337d8a
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
