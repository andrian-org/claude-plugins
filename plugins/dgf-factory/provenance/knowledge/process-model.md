---
sources:
  - path: src/Tools/dgf-mcp/Schemas/XSD/process.xsd
    sha256: 7adf1ea3f94f10e0606112d78e5dc49c528cd93bdfe41e7dc4251cc3546de121
  - path: src/Core/DGF.Domain/Process/StateProcess/Process.cs
    sha256: ac395a608a432d20caa57f7936f96d155aaa5eeafd477b41924cbc6001142f66
  - path: src/Core/DGF.Domain/Process/StateProcess/State.cs
    sha256: a1d9cf2bfed520f49ec144079060c7c335db78a45ec957cd0eeff99533a80bee
  - path: src/Core/DGF.Domain/Process/StateProcess/Transition.cs
    sha256: ac9423b24abe0a714e83a07d7550ea39a122aac7dc29abfca26361dd41ca3500
  - path: src/Core/DGF.Domain/Process/StateProcess/AbstractStateEvent.cs
    sha256: 19da1c4b1762bceefb1aa73a445c3be910fcee03123a8eacaeb978a17394945f
  - path: src/Core/DGF.Domain/Process/StateProcess/TimeoutStateEvent.cs
    sha256: ac3762187a76b8a3c8c5b14a03bb3540dcc24363d850c637ed83f81cad4d7585
  - path: src/Core/DGF.Domain/Process/StateProcess/InitStateEvent.cs
    sha256: da1675c75e725c4a7788a32fe889b9f65e77e19dad77618aa15f83b1fa97bbe9
  - path: src/Core/DGF.Domain/Process/StateProcess/FinalizeStateEvent.cs
    sha256: 95742ea3a846c56021f260bfb9016429fbdfbcfd81dcca762d4d610246f5fe2e
  - path: src/Core/DGF.Domain/Process/StateProcess/AbstractActivity.cs
    sha256: 16ea9157ad2a4c9d1bca467ba83eadfa5945626d915e2e06cb09f14fa66d039c
  - path: src/Core/DGF.Domain/Process/StateProcess/UpdateRecord.cs
    sha256: 0bedce31620bff142141ec35bebca7d9236684afead301ca1a95b21128cc2594
  - path: src/Core/DGF.Domain/Process/StateProcess/Task.cs
    sha256: 92a34555ba4d47a987cfba67f57b23833530d26000ae53c3c2c8a138b4bb2c8f
  - path: src/Core/DGF.Domain/Process/StateProcess/ModuleActivity.cs
    sha256: 05a558871f3a21e0165aafd52c6144617233ae9fdbf7d41ef2297f2323bc917b
  - path: src/Core/DGF.Domain/Process/StateProcess/SendMailActivity.cs
    sha256: 69a6465b66e49e5004c79308ecc4b893eaa9e7586cee2a4a05a8c07045ee7c96
  - path: src/Core/DGF.Domain/Process/StateProcess/StoredProcedureActivity.cs
    sha256: 8684f214d75dbb3727828f3b2486d653939a85e751518ff0fbf8d06894afe30f
  - path: src/Core/DGF.Domain/Process/StateProcess/MultiTask.cs
    sha256: 7feb07e986507f6855f3f06dfe4d89f8594f30bd54b3d645b8e24c7ae953c3ce
  - path: src/Core/DGF.Domain/Process/StateProcess/Field.cs
    sha256: 79c5460139014f4236cac190d31c9be4395494f18d59ed19c37bd1a19c9449a0
  - path: src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs
    sha256: c99435834fd8d306c833eef6f5cd09dc13fad8c0a02da8786c61bba1c99e3df0
  - path: src/Core/DGF.Domain/Process/StateProcess/MultiTaskSettings.cs
    sha256: b57b199c1a6fd2ba74e888cb1df2ac17d54c27f6c11e209867f0b3744eba5dd2
  - path: src/Core/DGF.Domain/Process/StateProcess/MultiTaskGroup.cs
    sha256: 9de7b1df1e82ae8fad72ccf058ac88e9405fc9d0d07a233ea5e593d2c6d2d1b5
  - path: src/Core/DGF.Kernel/WorkspaceSettings.cs
    sha256: 8c7f8c588fe93b14c88d098eed047d3de015340e79dd3d3d4ecb34e70bef7f30
  - path: src/Core/DGF.OM/Workflow/WorkflowManager.cs
    sha256: 35d431414bb516a828f72e867cb7f544106bdc9b8a90edf243b49bb290fe16b7
  - path: src/Core/DGF.DataViewer/Process/StateProcessClient.cs
    sha256: 1aa2feb464bb5a243626b31913e5fdbdf03062c0116e290efede71d7ef7dcc34
  - path: src/Core/DGF.DataViewer/Workflow/SequenceWorkflow.cs
    sha256: d383106a4e6020d6baa457bac455bf0e2946844929c7213d79ac757972419533
  - path: src/Components/Extensions/DGF.FlowComponents/WorkFlow/Engine/Core/StepExecution/Handlers/StateProcessStepHandler.cs
    sha256: 1436af91f93c38dd136c8949ca2a9f34b0253f624488e77ff09738b6eb3f6917
  - path: src/Core/DGF.OM/Process/StateProcess/InstanceHandler.cs
    sha256: e3b9bbfebc191659a9427405a7bf141f96c66de07479df110743616bb80cdce8
  - path: src/Core/DGF.DataViewer/Workflow/BackgroundWorkflowService.cs
    sha256: f7732f5f5c667288fa00f87e08083ba4c260700e27c57e592d47d6c128bfe4a3
---
# Provenance — `knowledge/process-model.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/process-model.md`](../../knowledge/process-model.md) were read from, with the digest of each file as
read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says
from where. The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md)
and [`knowledge/README.md`](../../knowledge/README.md) §1.

How the `process-divergence` table was derived and checked (2026-09-24): every
`[XmlAttribute]`, `[XmlElement]`, `[XmlArray]` and `[XmlArrayItem]` in the model classes above,
and in every class they reference, was diffed against `process.xsd`, and nothing else went into
the table. The 26 rows were then applied by hand to a scratch copy of the vendored `process.xsd`
(attributes as optional `xs:string`, elements as optional `xs:anyType`, enumerations relaxed to
`xs:string`) and the 23 `src/samples/workspaces/*/FM/_PROCESS/*/process.xml` files validated
against it: 0 failures under both `lxml` 6.1.3 (bundled libxml2 2.14.6) and `xmllint` 2.9.13,
against 2 failures (`webasm/…/PrintDeliver`, `dgf/…/DGF.Demo.EService`) under the unmodified XSD.
The list was not widened to make a sample pass.
