# tables

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
| `Byte[]` | max | VARBINARY(MAX) | 4/4 fields; 5 more fields are IMAGE |
