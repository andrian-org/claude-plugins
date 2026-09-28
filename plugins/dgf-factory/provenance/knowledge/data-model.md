---
sources:
  - path: src/Tools/dgf-mcp/Schemas/XSD/settings.xsd
    sha256: 6c8265271620860ac3a607d2936266811b277b78fe069856214f46360e972bb9
  - path: src/Core/DGF.Domain/Data/Table/Table.cs
    sha256: 0df2bc142b45b51cf5f48e0e7eb5690c2a13ce2a39b689bb75c28dc10c4061ce
  - path: src/Core/DGF.Domain/Data/Table/TableDataSource.cs
    sha256: 5e35be80b3ce1d921497e7dd1df4924a68320bcab7782ea62575894f05a5e079
  - path: src/Core/DGF.Domain/Data/Field/Field.cs
    sha256: 51201542bb0bd1e4fa339745da5dfca0cf57c0d414ac6e6e09694fc1ffa1567e
  - path: src/Core/DGF.Domain/Data/Field/FieldTypeEnum.cs
    sha256: a737d97a9c93f782de4b4147ccf53cf0169b73cadb23f0c481ea281e46007917
  - path: src/Core/DGF.Domain/Data/Field/ExtractProperties.cs
    sha256: 9c6b6131131e393cfb12c22ea2a9457500bc79f9b6c1e77c65dd0f9b236e0a9e
  - path: src/Core/DGF.Domain/Data/Field/RelationProperties.cs
    sha256: b151eab0e71a5b7b919f9698faa033147b9ccfe1006c69c73497c02df4a2ab1f
  - path: src/Core/DGF.Domain/Data/Field/SlaveGridProperties.cs
    sha256: 2d3fb327ed0780b4fde394abf3e7ed65a6e2955642c494b8182f0f5476cee124
  - path: src/Core/DGF.Domain/Data/Field/BindingProperties.cs
    sha256: 557253bc5cbd6c05b6a9d799afe7780eaccaa302ec34f55539b7363ffca80478
  - path: src/Core/DGF.Domain/Data/Table/TableManager.cs
    sha256: 7956ab856905a77d4a34ba6331a34512c8af9587eb4a665ac60329beb93957e2
  - path: src/Core/DGF.Domain/Data/Table/ViewManagerBase.cs
    sha256: 8eac14d38a1d0f2cd2ec7991493717304c8ed08bd2de345926c6c31086935532
  - path: src/Core/DGF.Domain/Data/Lookup/LookUpViewManager.cs
    sha256: f47230cb79a77e3cad802c066ec597bcb4900463a1e670a4ce0be091c44f5d23
  - path: src/Core/DGF.Domain/Data/Lookup/LookUpDialogManager.cs
    sha256: 444249f55e6400e317b629f377bee3280c0f19605325a8c66eb3885e7d72a4a6
  - path: src/Core/DGF.Domain/Data/EditableGrid/EditableGridManager.cs
    sha256: 66941b29b2a35731aca24b532be267570dc666aae1e611bcb528c13591961f98
  - path: src/Core/DGF.Domain/Data/Form/FormManager.cs
    sha256: 24b8018e502d2f5ce6967ad687cf2772062feb07ba6498ee007a6bb5cf59745a
  - path: src/Core/DGF.Domain/Data/Form/Form.cs
    sha256: aff48740abbb867ebe709fc1972133ce6d481511b055e6bb173ccca2aeca76ad
  - path: src/Core/DGF.Domain/Data/Form/FormTab.cs
    sha256: a04469912daae8a605e9c6e272d8b56ff95769a99a93ff4a87e4bd9f8cac3298
  - path: src/Core/DGF.Domain/Data/Form/FormSection.cs
    sha256: 11e973521be98465b8597270429a4aa0f11d39525c1134d21deeeea95d409fd1
  - path: src/Core/DGF.Domain/Data/Form/FormRow.cs
    sha256: bab1b27314274532b42174d3f41f54f486db0ea485f9dc485e6bbf00eb4e6bcf
  - path: src/Core/DGF.Domain/Data/Form/FormCell.cs
    sha256: b557a35e4a76531861e3efcbbfd176bb8a3d5dffce656655be39ca693a062907
  - path: src/Core/DGF.Domain/Data/ContextCell.cs
    sha256: d8578247ef44838cefeb728443cbdaa6920cd3cf9725080494c0a16182e96b3c
  - path: src/Core/DGF.OM/Store/SqlQueryBuilder.cs
    sha256: 9e32372c940d1c342a2652bc7b4c6b40c97271ccf3e848cf54b2effbf6b12035
  - path: src/Core/DGF.OM/Providers/BaseDataRowProvider.cs
    sha256: aad537e34cab1b3606d47795387a3b187a23c9d7ebb52c6262b6782680ee9b25
  - path: src/Core/DGF.Kernel/Utils/Serialization/BaseFileSerializationService.cs
    sha256: 99766fdd066278a6e01b9bf5d1b9a8d5ae272a4a3285ebeeb516038a6e6ca73f
  - path: src/Core/DGF.Kernel/Utils/Serialization/XmlSerializationService.cs
    sha256: 85168e67666a025f0d788e92883555c8a0b899574f68823ae92f512badd07e6d
  - path: src/Core/DGF.Kernel/Utils/Serialization/BaseFileSerializationService.cs
    sha256: 99766fdd066278a6e01b9bf5d1b9a8d5ae272a4a3285ebeeb516038a6e6ca73f
  - path: src/Core/DGF.Kernel/WorkspaceSettings.cs
    sha256: 8c7f8c588fe93b14c88d098eed047d3de015340e79dd3d3d4ecb34e70bef7f30
  - path: src/samples/Database/readme.md
    sha256: e0469e257b09e4d0813562bfc5038d6d8405569bb02c117963f9a2257d22160a
---
# Provenance — `knowledge/data-model.md`

Maintainer-only. Not shipped: `provenance/` is outside the directories `doctor.py` lists in
`SHIPPED_DIRS`. This ledger records which DGF files the facts in
[`knowledge/data-model.md`](../../knowledge/data-model.md) were read from, with the digest of each file as
read. The stamp in that file (`dgf_version`, `read_date`) says which DGF; this ledger says
from where. The contract is [ADR 0013](../../docs/adr/0013-version-gating-provenance-ledger.md)
and [`knowledge/README.md`](../../knowledge/README.md) §1.

Read on 2026-09-27 at DGF `cccd4325b`. Two facts differ from what the milestone-12 plan's evidence
(E6, D11, D12) first drafted, and the knowledge file states what the code does:

- **A grid resolves like a lookup view.** `EditableGridManager.GetXmlFilePath` does not clean a table
  name itself, but every load goes through `LoadAsync(tableName, gridName)`, which loads the table with
  `TableManager.LoadAsync` first and then builds the grid path from `table.Name` — the cleaned name
  (`TableManager.cs:30-41`; `EditableGridManager.cs:22-26`, `:50-55`). The same holds for forms
  (`FormManager.cs:31-40`) and lookup views (`LookUpViewManager.cs:37-49`).
- **A bound cell that names no field throws.** `Form.InitFields` → `AddFields` throws `The form cell
  "…" does not exist in the form "…"` for every cell with a `name`, no `content`, and no field of that
  name (`Form.cs:58-82`). Only a cell with no `name` is the empty cell `FormCell.IsEmptyCell`
  describes, and the runtime skips it.

Re-read the same day, after `/aif-verify` found a sample whose missing view the model check had called
generated: **a generated view or form can throw.** `LookUpViewManager.CreateFromTemplateAsync` always
generates — it never copies `default` — and `GetXmlTemplate` takes `FirstOrDefault(f => f.Name != keyName
&& f.FieldType == FieldTypeEnum.Text)`, with `keyName = table.PrimaryKeys[0]`, then reads `field.Name`: a
null reference when no such field exists (`LookUpViewManager.cs:43-69`, `:100-105`; `Table.cs:39-51` for
`PrimaryKeys`). `FormManager.CreateFromTemplateAsync` copies `default` when its file exists and otherwise
calls `GetXmlTemplate`, which throws `Field "…" is not compatible with the version 1.5.` on the first
field whose `uiMask` is null (`FormManager.cs:55-70`, `:131-139`; `Field.cs:106-107`, an
`[XmlAttribute("uimask")]` string that an absent attribute leaves null). `EditableGridManager.GetXmlTemplate`
falls back to `table.PrimaryKey`, which `Table.InitFields` has set, so a generated grid always has a
column to show (`EditableGridManager.cs:99-119`) — though, as the next paragraph records, it can still
fail to parse. `FieldTypeEnum`'s first member is `PrimaryKey`, so a field with no
`type` is not `Text` (`FieldTypeEnum.cs:3-9`). The zims entity `CarModelHasCategory`, whose one `Text`
field is its key `ID`, names its own `default` view, which does not exist.

Re-read again after the third `/aif-verify`, which found a title the generators cannot paste: **every
generated file pastes names and titles unescaped, and `SaveXml` parses it back.** The view uses
`string.Format` and pastes the key, its display field's name (twice) and title — or, when that name is
`""`, the table's first field's (`LookUpViewManager.cs:100-141`, the fallback `:108`, `:125-126`; `SaveXml`
`:143-146`, `XmlDocument.LoadXml`). The grid uses an interpolated string and pastes one column's name and
title, chosen as the first `required` `Text` field besides the key, else the first `Text` field besides
it, else the key (`EditableGridManager.cs:99-119`, the string `:114-119`; `SaveXml` `:122-125`). The form
builds with a `StringBuilder` and interpolation: a row for each field
`(IsSystemRequired || IsRequiredForForm) && IsValidForForm` and a hidden cell's title for each of seven audit
fields it has (`FormManager.cs:55-115`, the row `:74-75`, the hidden cell `:104-105`; `SaveXml` `:117-120`);
`required` binds `IsSystemRequired`, an xsd:boolean (`Field.cs:86-87`), and the two flags are
`get_uiMask(1)` and `get_uiMask(3)`, which index the C# string in UTF-16 code units (`Field.cs:52`, `:113`,
`:119`). `AppendHiddenCellToXmlTemplate` finds an audit field with `Fields.TryGetValue`, on the dictionary
`InitFields` built with `Add`, so by exact name (`Table.cs:41-42`). XmlSerializer decodes `&amp;` to `&`
when it reads the title, so `A &amp; B` is pasted as `A & B` and the parse throws. No name or title in
DGF's samples holds `&`, `<` or `"` (a count over every `fields/field`, 2026-09-27).

Re-read a fourth time after the fourth `/aif-verify`, which checked these generators against a .NET build
of them. First, **the whole file is what parses**: a title's `"` closes its attribute, so `x" title="y`
repeats `title` and fails, while `x" a="y` parses. The check now builds each file as the runtime does and
parses all of it. Second, **the entity's own load throws in `Table.InitFields`**, which
`TableManager.LoadAsync` calls on every load (`TableManager.cs:25-44`, the call `:42`; `Table.cs:39-51`). It throws when
`Fields.Add` meets a field with no `name` or a second field of one name; when `primaryKeyString` is null or
empty (`The Primary Key not defined in the table`); and when `Fields[PrimaryKeys[0]]` finds no field.
`primaryKeyString` is an `[XmlElement("primarykey")]` string (`Table.cs:90-91`), which XmlSerializer binds
from the first such element and skips the rest as unknown nodes, confirmed with that .NET build. Third,
**the file is read whole, then parsed from the string**: `TryDeserializeFromFileAsync` reads it with
`File.ReadAllTextAsync` and hands the text to a `StringReader` while the configuration cache is on, as it is
unless `DGF_CONFIGURATION_CACHING_DISABLED` is set (`BaseFileSerializationService.cs:43-74`, the read `:33`,
the switch `:89-99`; `XmlSerializationService.cs:54-60`), and opens a `StreamReader` when it is off
(`XmlSerializationService.cs:40-52`). Either way XmlSerializer reads a `TextReader`, which takes a DTD and
gives U+FFFD for a byte that is not UTF-8. The check decodes the file the same way since the sixth re-read
below; it refuses a DTD, so its checks do not run on such a file (a follow-up). None of the samples' 429 entities has a field with no
name, two fields of one name, no key, or a key that names no field (a count, 2026-09-27).

Re-read a fifth time, 2026-09-28, after the fifth `/aif-verify` found two readings that were not the
runtime's. Neither is in DGF's code: both are .NET's, observed with a .NET 10 build of `Table` that
deserializes through a `TextReader` as the runtime does, and of the three generators. First, **XmlSerializer
drops a text node of whitespace alone** when it binds `primarykey`: any markup — a comment, a processing
instruction, a CDATA section — ends a node; a node of space, tab, CR or LF alone is dropped unless
`xml:space="preserve"` is in scope, inherited and reset by `default`; a CDATA section is kept; a decimal
character reference counts as text and a hexadecimal one as the whitespace it is; a `primarykey` in a
namespace is not bound. So `<primarykey> </primarykey>` has no key, and `<primarykey>` wrapped around a
CDATA `Id` on its own line has the key `Id` (65 fixed cases and 2,100 random ones agreed). Second,
**`XmlDocument.LoadXml` reads namespaces**, so a pasted `"` that adds an attribute with an unbound prefix, a
reserved one or a duplicate expanded name throws, and it takes only `preserve` or `default`, trimmed of
XML whitespace, as an `xml:space` value (3,000 random entities with such titles agreed).

Re-read a sixth time, 2026-09-28, after the sixth `/aif-verify` read each file as the runtime's cached path
does, with `File.ReadAllText` and a `StringReader`, beside the `StreamReader` of the uncached path; the two
never differed. Three more readings are .NET's. First, **`XmlTextReader` trims `xml:space`** of XML
whitespace, so `" preserve "` keeps the key's whitespace, and a `preserve` on an element that has closed
keeps nothing. Second, **the declaration's `encoding` plays no part**: the text is decoded by its byte-order
mark — UTF-8, UTF-16 or UTF-32 — else as UTF-8 with U+FFFD for a bad byte, before the reader sees it. So a
file declared `ISO-8859-1` is read as UTF-8, and one declaring an encoding nobody knows loads. Third,
**`XmlDocument.LoadXml` does not check characters**. A reference to one XML does not allow, `&#0;` or a lone
surrogate, passes it; `Save` then throws, or the load each generator runs on the saved file refuses it
(`LookUpViewManager.cs:65-69`, `SaveXml` `:143-152`; `FormManager.cs:117-139`; `EditableGridManager.cs:70-86`,
`:122-133`). A surrogate pair written as two references is joined into one character, and a prefix bound to
the XML namespace is let pass: both of those files load. The check now agrees on the key and the load for
6,193 fixed entities and 6,000 random ones in four encodings. Of 1,017 encoding cases 883 agree; the other
134 are the shared XML parse's refusals, and XML 1.1, which XmlSerializer refuses — both follow-ups.

Sample counts were measured over `src/samples/workspaces/*/FM/_DATA/*/settings.xml` and
`*/_forms/**/_form.xml` with Python's `xml.etree`, walking exactly the element paths the model
binds (`Table.FieldCollection`; `Form.Tabs`…`Rows`…`Cells` and `Form.HiddenCells`).
