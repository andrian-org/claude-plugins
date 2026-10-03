---
dgf_version: "1.1.11"
read_date: 2026-09-30
---

# Data model — entities, fields, relations, and what the loaders do with a reference

Structural facts: stamp only. What an entity is in a workspaces root, how its fields and relations
are read, how each loader turns a reference into a file, and what it does when that file is
missing. The files read are in the maintainer provenance ledger for this file. Everything here is
read from the engine's model classes and managers, never from what the shipped samples happen to
contain; sample counts are given only to show how common a construct is.

## 1. An entity

An entity is the folder `FM/_DATA/<Entity>/`. Its `settings.xml` is read by `XmlSerializer` into the
`Table` model, whose root element is `entity`.

- **The file is read as text first.** It is decoded by its byte-order mark — UTF-8, UTF-16 or UTF-32
  — and as UTF-8 when it has none, a byte that is not UTF-8 read as U+FFFD. The serializer reads that
  text, so the XML declaration's `encoding` plays no part: a file declared `ISO-8859-1` is read as
  UTF-8, and one declaring an encoding .NET does not know loads all the same.
- **The folder name is the logical entity.** `TableManager` names the loaded table after the
  reference it was asked for, cleaned (§3.1), not after anything inside the file.
- **`datasource` is the physical object.** `TableDataSource` binds `name`, `type`, `sqltable`,
  `sqlview`, `sqllookupview`, `sqlquery` and a `parameters` list. `type` is `DB` — `name` is a
  database table or view — or `Provider` — `name` is an `Assembly,Type` data provider. The SQL table
  is `sqltable` when set and `name` otherwise; the SQL view is `sqlview`, then `sqltable`, then
  `name`. None of these is a file in the workspaces root.
- **`primarykey`** is a comma-separated list of field names, split on `,` and not trimmed. Only the
  first `primarykey` element in no namespace binds; a second is skipped. Its text is what the
  serializer's reader gives: any markup — a comment, a processing instruction, a CDATA section — ends a
  text node, and a node of whitespace alone is dropped unless `xml:space`, trimmed of XML whitespace,
  is `preserve` there: set on the element or an ancestor, and reset by `default`. A CDATA
  section is kept, and a decimal character reference such as `&#32;` counts as text, a hexadecimal one
  as whitespace. So `<primarykey> </primarykey>` holds no key, while `Id` in a CDATA section on a line of
  its own is the key `Id`.
- **Every load initialises the fields** (`Table.InitFields`), and so throws — the entity loads
  nowhere — in this order:
  - on a field with no `name`, or a second field with the same name, since it adds every field to a
    dictionary by name;
  - on a table with no primary key, or an empty one: `The Primary Key not defined in the table`;
  - when the key's first name is no field's.

  None of the samples' 429 entities does any of these.
- **Other children:** `header`, `description`, `watermark`, `audittrail`, `wfevents`, `attachment`,
  and `fields`, a list of `field`. The root's `version` attribute is the generator's version.
- **`sqlquery="[SQLCODE]"`** reads `sqlcode.sql` beside `settings.xml`, and throws when it is
  missing.

In DGF's samples: `webasm` has 194 entities and 3255 fields, `zims` 223 and 5044, `dgf` 12 and 103.
400 datasources are `DB` and 29 `Provider`.

## 2. A field

`Field` binds these attributes: `name`, `type`, `dbtype`, `format`, `displayFormat`, `title`,
`pageSize`, `description`, `size`, `accuracy`, `required`, `readonly`, `maxValue`, `minValue`,
`disabledDates`, `allowFilter`, `uimask`, `pattern` and `patternValidationMessage`. Its child elements
are `extract`, `relation`, `slavegrid`, any number of `binding`, and `binaryfields`.

- **`type` is a `FieldTypeEnum` member**, read by `XmlSerializer`, which accepts the exact member
  names only: `PrimaryKey`, `Lookup`, `Picklist`, `Checkboxlist`, `Text`, `Html`, `Integer`, `Float`,
  `Money`, `Boolean`, `DateTime`, `EditableGrid`, `Image`. Any other value fails deserialization, and
  the table does not load (§3.6). One sample entity uses `Decimal` and `Memo`, which are not members.
- **Sample counts by `type`:** Text 3987, DateTime 1000, Lookup 931, Integer 832, Picklist 802,
  Boolean 567, EditableGrid 146, Money 55, Image 51, Float 25, Decimal 4, Html 1, Memo 1.
- **Which types carry which child**, in the samples: `extract` under `Lookup` (929), `Picklist` (567),
  `Text` (249) and `Integer` (1); `slavegrid` only under `EditableGrid` (146); `relation` only under
  `Lookup` (14); `binding` under `Picklist` (176) and `Lookup` (42). The model does not tie a child to
  a type: `IsExtractable` is simply "has an `extract`".
- **`uimask`** is a string of flags, one character each: required for grid, required for form, valid
  for grid, valid for form, allow create, valid for report. A `1` sets the flag. The positions count
  UTF-16 code units, as a .NET string does, so a character outside the Basic Multilingual Plane takes
  two.

## 3. Relations, and how each reference resolves

### 3.1 A table name

`TableManager` loads `<entity folder>/settings.xml`:

1. **The name is cleaned first**: everything up to and including the last `.` is dropped
   (`ViewManagerBase.GetCleanTableName`). So `dbo.X` is `X`.
2. **Then `BASE:` is tested, in any case** (`InvariantCultureIgnoreCase`). `BASE:X` is `webasm`'s
   `FM/_DATA/X`. Because cleaning comes first, **`BASE:dbo.X` is `X` in the selected workspace**, not
   in `webasm`.
3. **Otherwise the name is the selected workspace's** `FM/_DATA/<name>`. There is no fallback to
   `webasm`. From an entity in `webasm`, an unprefixed name resolves in whichever application is
   running.
4. **A missing table throws**: `Settings file for the table "…" not found.` An empty name throws too.

Existence is a file read on the built path, case-sensitive on Linux.

### 3.2 `extract` — N:1

`ExtractProperties` binds `table`, `view` and `dialog`. A field with an `extract` is a lookup.

- **With a non-empty `table`**, the lookup view is `table` + `view`, and `dialog` is ignored
  (`LookUpViewManager.LoadDefaultView`). The table loads first (§3.1) and throws when missing.
- **The view** is `<table folder>/_lookupviews/<view>/_view.xml`, in the folder the table resolved to.
  An empty `view` is `default`. **A missing view is generated** from the table's fields
  (`LookUpViewManager.CreateFromTemplateAsync`) and **written into the workspace** — never copied from
  `default`. The template shows the first field whose `type` is exactly `Text` and whose name is not the
  first primary key, and reads that field's name (`GetXmlTemplate`), or shows the table's first field
  instead when that name is empty (`name=""`). **So a table with no such field
  throws** a null reference instead: its one `Text` field is its key, or it has none. 18 of the
  samples' 429 entities are of that kind; any missing view of theirs throws. The view pastes the key,
  that field's name and its title, and can fail to parse (§3.6).
- **With no `table`**, the `dialog` is loaded, and its first view's table and view are used. A lookup
  with neither throws `Lookup table/view or dialog not defined`.
- **A dialog** is `FM/_LOOKUP/<dialog>/_dialog.xml` in the **selected workspace only**
  (`LookUpDialogManager`): it has no `BASE:` form, and its name is not cleaned. **A missing dialog
  throws** `Lookup Dialog "…" not found.` From an entity in `webasm`, a dialog resolves in each
  application's `_LOOKUP`.

In the samples every one of the 1746 `extract` elements names a `table`; two also name a `dialog`,
which the runtime ignores.

### 3.3 `relation` — M:N

`RelationProperties` binds `table`, `tableKey`, `filter` and a list of `column` elements whose `type`
is `parentkey`, `childkey`, `typekey` or an extra column. **Its `table` is a database junction table**
(`DataSourceTable`), used in SQL: not a `_DATA` entity, and not a file in the workspaces root. A
`relation` sits beside the field's `extract`, which names the related entity. 14 in the samples.

### 3.4 `slavegrid` — 1:N

`SlaveGridProperties` binds `table`, `grid`, a `relationtype` element and `column` elements (one
`parentkey`). It loads through `EditableGridManager.LoadAsync(table, grid)`:

- **The table loads first** (§3.1), and throws when missing.
- **The grid** is `<table folder>/_gridforms/<grid>/_grid.xml`, and an empty `grid`, or one of only
  spaces, is `default` (`LoadAsync` tests it with `IsNullOrWhiteSpace`). The
  path is built from the **loaded** table's name, which `TableManager` has already cleaned — so
  although `EditableGridManager`'s own path builder does not clean a name, a grid resolves exactly as
  a lookup view does.
- **A missing grid is copied** from the table's `default` grid when one exists, and generated from the
  table's fields otherwise, and **written into the workspace**. The generated grid shows one field: the
  first `Text` field besides the key that is `required`, else the first `Text` field besides the key,
  else the key. It needs no particular field, but it pastes that field's name and title, and can fail to
  parse (§3.6).

146 in the samples.

### 3.5 `binding` — a cascade

`BindingProperties` binds `from`, `to` and `useInSubQuery`. `from` is a column of the host entity and
`to` a column of the extract's table; with `useInSubQuery`, the lookup's SQL join gains
`AND [host].[from] = lookup.[to]` (`SqlQueryBuilder`). **It names columns, not files**, so it is not a
reference to anything in the workspaces root. 231 in the samples.

### 3.6 What every loader shares

- **A file that exists but does not deserialize is treated as missing.** The serialization service's
  `TryDeserializeFromFileAsync` returns failure on any exception. A table then throws `not found`; a
  view, grid or form is regenerated as if missing.
- **Copying a `default` into a folder that already exists throws** `The form directory exists, but
  setting are missing!` (forms) or `The editable grid directory exists, but settings are missing!`
  (grids). So a folder whose file is missing or unreadable throws when the table has a `default`, and
  is overwritten by a generated file when it has none.
- **A generated view, grid or form can throw before anything is written.** A view needs a `Text` field
  besides the key (§3.2); a form generated with no `default` to copy needs a `uimask` on every field
  (§4). And every generator pastes the values it uses — each field's `name` and `title` as read,
  entities already decoded, and the view's key — into its XML **unescaped**: the view with
  `string.Format`, the grid and the form with string interpolation. `SaveXml` then parses the whole
  result with `XmlDocument.LoadXml`, and the load throws when the pasted values leave it unparsable. A
  bare `&` or a `<` does — `A &amp; B` in the file is pasted as `A & B`. A `"` closes its attribute, so
  what follows must still parse: `x" title="y` repeats an attribute and fails, while `x" a="y` parses.
  `LoadXml` reads namespaces and takes only `preserve` or `default`, trimmed, as an `xml:space`, so
  `x" p:a="y`, whose prefix nothing declares, fails too, and so does `x" xml:space="y`.
  `LoadXml` does not check characters: a reference to one XML does not allow, `&amp;#0;` pasted as
  `&#0;`, or a lone surrogate, passes it, and then `Save` throws, or writes a file the load that
  follows (`CreateFromTemplateAsync`) refuses — so the reference throws all the same. A surrogate pair
  written as two references, `&amp;#xD83D;&amp;#xDE00;`, it joins into one character, and it lets a
  prefix or the default namespace be bound to the XML namespace: both files load.
  A value that still parses once pasted, such as `&amp;amp;` pasted as `&amp;`, is harmless. No name or
  title in the samples holds `&`, `<` or `"`. So a missing view, grid or form throws on some tables, and
  is generated on the rest.
- **Generated files are written into the workspace** — the selected application's folder or
  `webasm`'s, wherever the table resolved.

## 4. A form binds to its entity

- **A form belongs to the entity whose folder holds it.** A `_form.xml` at
  `FM/_DATA/<Entity>/_forms/<form>/_form.xml` is `<Entity>`'s: `FormManager` builds the path from the
  table's folder (§3.1), and loads the table first, which throws when missing. A form name may contain
  `/`, which is a nested folder under `_forms/`.
- **An empty form name is `default`.** A missing form is copied from `default`, or generated from the
  table's fields, and **written into the workspace** (`FormManager.CreateFromTemplateAsync`).
  **Generation throws** `Field "…" is not compatible with the version 1.5.` on the first field whose
  `uimask` is absent (`GetXmlTemplate`). A copy needs no `uimask`. Every field in the samples carries
  one. The generated form holds a row for each field that is `required` or required for the form, and
  valid for the form (the second and fourth `uimask` characters, §2), and a hidden cell for each of `CreatedBy`, `CreatedIP`,
  `CreatedOn`, `ModifiedBy`, `ModifiedIP`, `ModifiedOn` and `ApplicationId` the table has. It pastes those
  fields' names and titles (§3.6).
- **The cells the runtime binds** are `form/tabs/tab/sections/section/rows/row/cell` and
  `form/hidden/cell` (`Form.InitFields`). A section's own `cells` list is not bound.
- **A form with no `tabs` element binds no cell at all.** `Form.InitFields` returns before binding
  anything when `Tabs` is null, which is what the serializer leaves for an absent `tabs` element, so the
  `hidden` cells go unbound too. An empty `<tabs/>` is a list, and the `hidden` cells are bound.
- **A bound cell must name a field.** For every such cell that has a `name` and no `content` element,
  `Form.AddFields` looks the name up in the table's fields — exactly, case-sensitive — and **throws**
  `The form cell "…" does not exist in the form "…"` when it is not one. The form then fails to load.
- **A cell with no `name` is an empty cell** (`FormCell.IsEmptyCell`), and **a cell with a `content`
  element is custom** (`FormCell.IsCustom`). The runtime skips both.

In the samples: 785 forms, 11876 bound cells, and 15 bound cells whose name is no field of their
entity.

## 5. Where the schema lives

- **The database schema is not in the workspaces root.** Framework tables come from DGF's own database
  project (`DGF.Database`, a DACPAC); a consumer's application tables come from that consumer's own
  SSDT database project. No EF migration touches application tables.
- **A change to an entity's fields or relations needs database work outside the root**: a column, a
  table, a view or a junction table, in the consumer's database project.
- **`_DATACALLS` is read by nothing.** `WorkspaceSettings` has no constant for it, and no loader opens
  it.
- **Roles and the `aspnet_Applications` row** that registers a workspace are database rows too; see
  [`permissions.md`](permissions.md).

## 6. Field types, `dbtype`, and the SQL type of a column

Unlike §1–§5, this section is derived from the samples, because nothing else answers it: **no DGF code
turns a `settings.xml` into a `CREATE TABLE`**, and the runtime reads `dbtype` as a free string
(`Field.DbTypeName`) — it uses it only to tell a database field from a user-defined one (an empty
`dbtype`), and in one diagnostic that expects a `*By` field to be `Int32`. So the mapping below is a
tally of the entities that DGF's own samples pair with a table script, not a rule the engine enforces.

### 6.1 The field types

`type` is a `FieldTypeEnum` member (§2); the counts below are §2's, over three workspaces. The vendored `settings.xsd` declares eleven of the thirteen,
plus two names the runtime does not have, `Decimal` and `Memo`; it lacks `PrimaryKey` and `Checkboxlist`,
so every file using either warns `XSD_LAGS_RUNTIME`.

<!-- machine-read: field-types -->
| Type | In settings.xsd | Fact |
|---|---|---|
| `PrimaryKey` | no | 0 fields in the samples, which type a key as Text and Guid, or Integer and Int32 |
| `Lookup` | yes | 931 fields; carries an extract, and may carry a relation |
| `Picklist` | yes | 802 fields; carries an extract, and may carry a binding |
| `Checkboxlist` | no | 0 fields in the samples |
| `Text` | yes | 3987 fields; the type of a string, of a Guid and of the key of most tables |
| `Html` | yes | 1 field |
| `Integer` | yes | 832 fields |
| `Float` | yes | 25 fields |
| `Money` | yes | 55 fields |
| `Boolean` | yes | 567 fields |
| `DateTime` | yes | 1000 fields |
| `EditableGrid` | yes | 146 fields; carries the slave grid, and has no column of its own |
| `Image` | yes | 51 fields |

### 6.2 The `dbtype` values

`dbtype` names the column's .NET type. An empty `dbtype` is a field with no column of its own — a
lookup's display, an editable grid, a user-defined field; 200 fields in the two workspaces' entities
have one. These are the values the samples use with a table script, counted over the `webasm` and `dgf`
entities.

<!-- machine-read: db-types -->
| Dbtype | Fact |
|---|---|
| `String` | 1093 fields |
| `StringUnicode` | 117 fields |
| `Boolean` | 236 fields |
| `DateTime` | 356 fields |
| `DateTimeOffset` | 2 fields |
| `Decimal` | 29 fields |
| `Double` | 10 fields |
| `Guid` | 521 fields |
| `Int16` | 451 fields |
| `Int32` | 240 fields |
| `Int64` | 81 fields |
| `Byte[]` | 19 fields |

Four spellings occur once or twice and are not a sound basis for a column: `Text` (2 fields, one of
which sits on a `BIT` column), `Integer` (1, on a `SMALLINT`), `smallint` (1) and the empty string above.

### 6.3 The SQL type of a column

The tally pairs every `FM/_DATA/<T>/settings.xml` in the `webasm` and `dgf` sample
workspaces with the baseline's `dbo/Tables/<T>.sql` by exact case, and reads each field's `dbtype` and
`size` and the column's declared type. **86 pairs; 1752 fields; 1627 of them have a column, 13 of which
are computed (`AS`) and skipped, leaving 1614 tallied.** Per `dbtype` it reports the majority SQL type
and its share.

The size rule says how the column's length relates to the field's `size`:

| Size rule | Meaning |
|---|---|
| `size` | the column length is the field's `size`; a `(MAX)` column has the size `2147483647` |
| `none` | the column has no length, precision or scale |
| `precision` | a `DECIMAL` column; precision and scale are never in the settings file |
| `fixed` | the column has a length or precision that no field attribute gives |
| `max` | a `(MAX)` column whose field has no `size` |

<!-- machine-read: field-sql-types -->
| Dbtype | Size rule | SQL type | Evidence |
|---|---|---|---|
| `String` | size | VARCHAR(size) | 468/551 fields; alternatives NVARCHAR(size) 77, NCHAR(size) 6 |
| `StringUnicode` | size | NVARCHAR(size) | 55/55 fields |
| `Boolean` | none | BIT | 130/130 fields |
| `DateTime` | none | DATETIME | 168/176 fields; alternatives DATE 4, SMALLDATETIME 4; 10 more fields are DATETIME2(7) |
| `DateTimeOffset` | fixed | DATETIMEOFFSET(7) | 1/1 fields |
| `Decimal` | precision | DECIMAL(18,2) | 13/14 fields; alternative DECIMAL(18) 1; 3 more fields are MONEY |
| `Double` | fixed | FLOAT(53) | 6/6 fields |
| `Guid` | none | UNIQUEIDENTIFIER | 246/246 fields |
| `Int16` | none | SMALLINT | 243/244 fields; alternative TINYINT 1 |
| `Int32` | none | INT | 125/126 fields; alternative SMALLINT 1 |
| `Int64` | none | BIGINT | 26/27 fields; alternative SMALLINT 1 |
| `Byte[]` | max | VARBINARY(MAX) | 4/4 fields; 5 more fields are IMAGE |

Two facts the tally shows and a reader would otherwise guess:

- **A unicode string is spelled `StringUnicode`**, not `String` with a flag: all 55 of those fields sit on
  `NVARCHAR`. `String` is `VARCHAR` in 468 of 551 fields and `NVARCHAR` in 77, so a string that must hold
  non-Latin text is `StringUnicode`.
- **A decimal's precision and scale are never in the settings file**; the columns hold `DECIMAL (18, 2)`
  in 13 of 14 cases. A column of any other precision is a choice the settings file cannot state.

## See Also

- [`README.md`](README.md) — the stamping convention and the machine-read table contract (§7)
- [`reference-graph.md`](reference-graph.md) — every reference as an edge, with its `When absent`
- [`composition-specs.md`](composition-specs.md) — where `settings.xml`, `_form.xml` and the views live
- [`process-model.md`](process-model.md) — how process and workflow references resolve
