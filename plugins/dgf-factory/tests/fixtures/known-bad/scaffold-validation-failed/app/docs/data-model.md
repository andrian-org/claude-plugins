# Data model

The entities of Inspections Portal. Each is one folder under `FM/_DATA/` in the workspace, with a `settings.xml`, and one
table in `Inspections.Database`; both are rendered from the same entry of `data_model` in
[application.json](application.json).

## PermitType

Key: `Id`.

| Field | Type | Dbtype | Column | Required |
|---|---|---|---|---|
| Id | Integer | Int32 | INT | true |
| Name | Text | String | VARCHAR(100) | true |

## Permit

Key: `Id`.

| Field | Type | Dbtype | Column | Required |
|---|---|---|---|---|
| Id | Integer | Int32 | INT | true |
| Reference | Text | String | VARCHAR(20) | true |
| Holder | Text | StringUnicode | NVARCHAR(200) | true |
| PermitTypeId | Picklist | Int32 | INT | true |
| IssuedOn | DateTime | DateTime | DATETIME | false |
| Fee | Money | Decimal | DECIMAL(18,2) | false |
| Active | Boolean | Boolean | BIT | false |

A column's SQL type comes from the samples DGF ships: no framework code turns a `settings.xml` into a table.
A decimal's precision and scale are never in the settings file, so they are the design's to state.
