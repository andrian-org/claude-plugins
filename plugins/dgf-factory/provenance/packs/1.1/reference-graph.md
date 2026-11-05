---
sources:
  - path: src/Core/DGF.Domain/Workflow/AbstractSequence.cs
    sha256: 893a7a10e5900baa9f2b917575ede4b0529e549ab163d3bf61b64cc2f4887059
  - path: src/Core/DGF.Domain/Workflow/AbstractStep.cs
    sha256: 91a48007895e88fdc0cad49c3c3a725bd7f5bf53c5d25175e66af0b641d1ba29
  - path: src/Core/DGF.Domain/Workflow/Invoke.cs
    sha256: a684ba7cfffa2b1bd7077c18e90d5b4ebf7c5a847bd07d2d364ef220f8295e90
  - path: src/Core/DGF.Domain/Workflow/SubWorkflow.cs
    sha256: 9c1970199adde2ea2a69a2f926defa20aa6086f62b2711cf24a575fdff0f3cd2
  - path: src/Core/DGF.Domain/Workflow/UpdateRecord.cs
    sha256: f38aca1b0f8e28b800b291b8c0adda6e0cc38279be01356b589801373b3001b3
  - path: src/Core/DGF.Domain/Workflow/CreateRecord.cs
    sha256: 733b13af02a94af7a42bef29235be699c5d7db93145262bb552b759bb0b9ab43
  - path: src/Core/DGF.Domain/Workflow/XmlIsland.cs
    sha256: 7970aa21fdf4ac8e7717cfaca89600c8aa0d50876f9650ba44d42be26e8a5da1
  - path: src/Core/DGF.Domain/Workflow/DataSourceStep.cs
    sha256: daa28c6264dbe5613e7d88ea529e3ea33a3e21fef2c80acd64f58e37c1b6ce10
  - path: src/Core/DGF.Domain/Workflow/StartProcess.cs
    sha256: e8b3b7e4892a291b174f1877bf76adbdfea7f7f7b7cdf54a950db20bff7f1ca3
  - path: src/Core/DGF.Domain/Workflow/Assign.cs
    sha256: cc292a94100eae2199ab294127ed52679453f0e49a059b1e3eb6f9233cae7c3d
  - path: src/Core/DGF.Domain/Workflow/AssignState.cs
    sha256: f5c915f9687772c27b804d5d9b50881fe483794fa76a382ae5ef230b64b7830e
  - path: src/Core/DGF.Domain/Workflow/Settings/FormSettings.cs
    sha256: 777628d3a9b662cf7d06730e8d06c4cf9f9928c9ce2f8b93d364169a9da65012
  - path: src/Core/DGF.Domain/Workflow/Settings/WorkflowSettings.cs
    sha256: 34afbd5abe78849200afb1933d96c1ec92564b2e57fd1008b35f2af85abd3f4a
  - path: src/Core/DGF.OM/Workflow/RoundTrip.cs
    sha256: 6c34c2228f092a3cc73935a69659691093bcf7bc1f827633c33b1d1a5b661f77
  - path: src/Core/DGF.OM/Workflow/WorkflowManager.cs
    sha256: 35d431414bb516a828f72e867cb7f544106bdc9b8a90edf243b49bb290fe16b7
  - path: src/Core/DGF.DataViewer/Workflow/HumanWorkflow.cs
    sha256: 73bd74fd86bed58fb40ecc75939cdf75dbfbc00caddef6a4b7f541ea40ab6e30
  - path: src/Core/DGF.DataViewer/Workflow/SequenceWorkflow.cs
    sha256: d383106a4e6020d6baa457bac455bf0e2946844929c7213d79ac757972419533
  - path: src/Core/DGF.DataViewer/Workflow/WorkflowFormContainer.cs
    sha256: 4701b6eea214b35ea176052436f708a16594428387d731c64953049b7b074a93
  - path: src/Core/DGF.DataViewer/Form/FormControl.cs
    sha256: 8ac5df7931162041265a535bbce83e73ca1e6adb51374beda93530b0699ed0ed
  - path: src/Core/DGF.DataViewer/Process/StateProcessClient.cs
    sha256: 1aa2feb464bb5a243626b31913e5fdbdf03062c0116e290efede71d7ef7dcc34
  - path: src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs
    sha256: c99435834fd8d306c833eef6f5cd09dc13fad8c0a02da8786c61bba1c99e3df0
  - path: src/Core/DGF.Domain/Process/StateProcess/OpenHandler.cs
    sha256: 2dbc192700b901463ffe6a35a3c772ffd56a94e7a125470d3fe222f6d59611bb
  - path: src/Core/DGF.OM/Process/StateProcess/InstanceHandler.cs
    sha256: e3b9bbfebc191659a9427405a7bf141f96c66de07479df110743616bb80cdce8
  - path: src/Core/DGF.DataSources/DataSourceLoader.cs
    sha256: 24e3b570fcc4e533640f03370d8278e9b3eae461dc8ebb6860ac9f8b42eab8d6
  - path: src/Components/DGF.Components.Shared/ComponentFileLoadService.cs
    sha256: 5d5ca13b8dd3f5b2192535776c2d5c0245c361677dc168247478733f17ad3b1d
  - path: src/Components/Extensions/DGF.FlowComponents/ProcessFlow/ProcessFlowComponentService.cs
    sha256: 025fb3751ebfef8bcd1e1a0b67b0b61908ada5aae63672fe527dd544a60f79b9
  - path: src/Core/DGF.Domain/Data/Lookup/LookUpViewManager.cs
    sha256: f47230cb79a77e3cad802c066ec597bcb4900463a1e670a4ce0be091c44f5d23
  - path: src/samples/Database/dbo/Stored Procedures/prc_WF_StartProcess.sql
    sha256: 4c04606f9ede9df1594c430284618af6b648fa443cab721ce28763fcde955426
---
# Provenance — `knowledge/reference-graph.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/reference-graph.md`](../../knowledge/reference-graph.md) were read from, with the digest of each file
as read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says from where.
The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md) and
[`knowledge/README.md`](../../knowledge/README.md) §1. The table rows that cite `data-model.md` rest on that
file's ledger.

Read on 2026-09-27 at DGF `cccd4325b`. How each row of `reference-edges` was read:

- **Which elements are steps**: `AbstractSequence.Sequence`'s `[XmlArrayItem]` types — steps nest inside
  `Switch`/`Case` and `ForeachRecord` sequences, so an element is matched anywhere in the file.
- **What each step loads, and when**: `RoundTrip`'s step switch (each step's own `Assign` evaluated for
  it), `HumanWorkflow.ProcessInvokeAsync` (`control.ToUpper() == "FORM"`; `_TABLENAME_`/`_FORMNAME_` fill
  the table and form), `HumanWorkflow.OnSubWorkflow` (`_WORKFLOWNAME_` replaces the target; loaded
  verbatim with `raiseException: true`), `SequenceWorkflow` (`XmlIsland` loads its table only with a
  non-empty `FieldSet`; `UpdateRecord`/`CreateRecord` through `FormManager.LoadAsync`; `StateProcess`
  catches per id; `ExecDataSourceStepAsync` returns on an empty name; `WriteErrorMessage` rethrows unless
  `hideExceptions`), `WorkflowFormContainer` → `FormControl.InitFormFromConfigurationAndCreateRowHandler`
  (cuts `/READONLY`), and `DataSourceLoader` (throws `FileNotFoundException`).
- **Where the plan's first draft differed**: the `state-process` row became `change-state-process` and
  `start-process`, because `validate_process.py` checks only `CHANGE_STATE` steps, and a missing process is
  `caught`, not thrown; `multitask-settings` was added so a walk reaches a MultiTask file from its process;
  `invoke-form` has its own rule for the `/READONLY` suffix; `run-time-names` holds which `Assign` names
  make which edges dynamic, so no script lists edge kinds.
- **`When empty`**, added after `/aif-verify` found an empty reference passing where the runtime throws:
  `throws` for `extract-dialog` (`BaseDataRowProvider` throws `Lookup table/view or dialog not defined`
  when both `table` and `dialog` are empty), and for `slavegrid-table` and `slavegrid-grid`
  (`SlaveGridProperties.InitAsync` → `EditableGridManager.LoadAsync(tableName, gridName)` →
  `TableManager.LoadAsync`, which throws `ArgumentNullException` on an empty name); `none` for
  `extract-table` and `extract-view` (an empty `table` takes the dialog branch) and for
  `datasource-step` (`ExecDataSourceStepAsync` returns on an empty name). Every other row is `unknown`:
  what its step does with an empty value was not read. The copy exception under `When absent` is
  `FormManager.Copy` and `EditableGridManager.Copy`, which throw when the target folder exists and run only
  when the table's `default` file exists. The files are in `data-model.md`'s ledger, at the same digests.

Sample counts (§3) were measured over `src/samples/workspaces` with `grep` and Python's `xml.etree`:
Invoke `control` values upper-cased — `FORM` 370, `SERVERCONTROL` 45, `HTML` 2, `PROFILE` 1; every empty
`Invoke` table (14) is filled by a `_TABLENAME_` in its own `Assign`. No sample form name carries
`/READONLY`.
