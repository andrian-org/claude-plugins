# The design file — `docs/application.json`

The design is the generator's only input. The `/dgf-scaffold` skill writes it from the request and the
survey; `scripts/design.py` (in this skill) checks it and says what is still open; `generate.py` renders the
whole application from it, and refuses to run unless the check exits 0. It stays in `docs/` as the record of
what was generated: run `generate.py` from it into a new empty folder and the same application comes out.

**Write only what the request and the survey gave.** Leave every other key out. The check asks for what it
cannot default, and prints every default it applies, so nothing is decided silently.

## What the check does with it

| Result | Meaning | Exit |
|---|---|---|
| nothing printed but the verdict | the design is complete | `0` |
| `SCAFFOLD_DIR_NOT_EMPTY`, `SCAFFOLD_NAME_INVALID`, `SCAFFOLD_OPTION_INVALID`, `SCAFFOLD_REFERENCE_INVALID`, `SCAFFOLD_MODEL_INVALID`, `SCAFFOLD_SQL_TYPE_UNKNOWN` | a conflict; each line names the key and the rule | `1` |
| `SCAFFOLD_ASK` | a value is open; each line is `<key> — <rule> (candidates: …)` | `2` |
| `SCAFFOLD_DESIGN_UNREADABLE` | the file cannot be read as a design | `3` |
| `DEFAULT: <key> = <value>` | a value the check filled in; shown, never silent | (with `0` or `2`) |

A conflict beats a question: the exit is `1` while any conflict remains, then `2` while any value is open.

The file must be a regular file of at most 1 MiB, UTF-8 without a byte-order mark, one JSON object with no
duplicate key. `design_format` is `1`. **Every key is checked for its JSON type before it is used**, and an
unknown key at any level is `SCAFFOLD_OPTION_INVALID`.

**Defaults that print no line.** A title left out is its name (an instance's is its name capitalised), and a
field's `required` left out is `false`. These echo a name or state the neutral case, so they are not decisions.

## The keys

| Key | Holds | Rule | If left out |
|---|---|---|---|
| `design_format` | `1` | exactly the number 1 | unreadable (exit 3) |
| `application.name` | the application's name | a letter, then letters, digits and underscores; at most 64 characters | asked |
| `application.title` | free text | one line, at most 200 characters | the name |
| `dgf_version` | the `DGF.API` package version to target | a version such as `1.1.15`; the framework pins none | asked |
| `instances[]` | `name`, `title` | a name is a lower-case letter then lower-case letters and digits, at most 40; unique ignoring case | asked (at least one) |
| `instance_model` | `shared-workspace` or `own-workspace` | a row of the `instance-models` table | with one instance `own-workspace`, printed; with several, asked |
| `workspace` | the one workspace directory of `shared-workspace` | a lower-case name; forbidden with `own-workspace`, which names each directory after its instance | the application name, lower-cased and stripped to letters and digits, printed |
| `apis[]` | `name`, `deployments[]` | an API name is an identifier; unique ignoring case | one `Api` with a deployment per instance, printed |
| `apis[].deployments[]` | `name`, `instance`, `auth[]` | one API process for one instance; names unique within the API; every instance has at least one deployment | a name is the instance's, capitalised, printed; `instance` is defaulted only with one instance |
| `apis[].deployments[].auth` | the sign-in providers | each a row of the `auth-schemes` table: `basic`, `dgpass`, `azure`; at least one | asked, always |
| `roles[]` | role names | no comma, no leading or trailing space, none of `/ \ : * ? " < > |`, no trailing dot, one line, at most 100 characters; unique ignoring case. A role is also the name of a profile folder | none, printed |
| `base.source` | an absolute path to a directory named `webasm` | it exists, matched by exact case, and holds an `FM` directory | asked |
| `base.supply` | `copy` or `mount` | `copy` puts the base in `workspaces/webasm`; `mount` mounts it in compose from a path you set | asked |
| `modules[]` | `name`, `pattern`, `title`, `entity`, `route`, `roles[]` | see below | none |
| `data_model.entities[]` | `name`, `title`, `key`, `fields[]` | see below | none, printed |
| `sources` | for each value, `prompt`, `asked` or `default` | the record of where each value came from | none |

An instance is a `WorkspaceName` with its own row in the framework database, and the framework partitions
its rows by that row's id. A deployment is one API process for one instance; a front office and a back
office are one host deployed twice, with different settings.

**Sign-in.** Cookie authentication is always on. `basic` is DGF's own local username and password;
`dgpass` and `azure` are OpenID Connect providers whose settings are placeholders you fill in. A login page
that lists exactly one method starts a DGPass login from the header's sign-in item, whatever that method
is, so the generated header links a `basic`-only application to its login page directly.

## Modules

A module is one workspace artefact pattern, rendered from the design:

| Pattern | Needs | Generates |
|---|---|---|
| `register` | `entity` | the entity's settings, default form and lookup view; a data source and a data table; a list page; its route; a profile node for its roles |
| `service` | `entity` and at least one review role in `roles` | a `register`, plus a case process — draft, submitted, in review, approved or rejected — with a workflow per transition and a task per reviewing role |
| `page` | nothing | a content page and its route |

- A module's name is an identifier, unique ignoring case, and not `home`, `login` or `loginPage`, which
  every workspace already has.
- `route` is a path such as `/permits`: never `/`, not `/login`, `/home`, `/user-profile` or `/app-menu` (the
  workspace's menu), unique. Left out, it is `/` followed by the module's name in lower case, printed.
- `roles` name entries of `roles` or a built-in role (`Administrators`, `Members`, `Anonymous`,
  `Registered Users`, `PortalUser`). Left out, a `register` or `page` is open to `Members`, any signed-in
  user; a `service` asks.
- An entity belongs to at most one module.

What falls outside these patterns — custom behaviour, integrations, documents — is not generated. It is
written into the application's `docs/README.md` as work for `/dgf-plan` after `/dgf`.

## The data model

`data_model.entities[]`: `name` (an identifier), `title`, `key` (the name of an `Integer` field) and
`fields[]`. The same entry renders the entity's `settings.xml` and its table script, so the two agree.

An entity name must not start like a table the framework database owns: `AX_`, `AspNet`, `ZIGS_`, `prc_` or
`DGF_Demo_`, in any case.

A field has `name`, `title`, `type`, `dbtype`, `size`, `required`, `precision`, `scale` and `extract`:

| `type` | `dbtype` it takes | Notes |
|---|---|---|
| `Text` | `String`, `StringUnicode` | needs `size`: a number, or `"MAX"` |
| `Html` | `String`, `StringUnicode` | needs `size` |
| `Integer` | `Int16`, `Int32`, `Int64` | takes no size |
| `Float` | `Double`, `Decimal` | |
| `Money` | `Decimal` | `precision` and `scale`, else `DECIMAL(18,2)` |
| `Boolean` | `Boolean` | |
| `DateTime` | `DateTime`, `DateTimeOffset` | |
| `Lookup`, `Picklist` | `Guid`, `Int16`, `Int32`, `Int64`, `String`, `StringUnicode` | needs `extract` (`entity`, and `view`, default `default`); the `dbtype` is the target key's |

- **A unicode string is `StringUnicode`**, which becomes `NVARCHAR`; `String` becomes `VARCHAR`. A size is at
  most 8000 for `String` and 4000 for `StringUnicode`, or `"MAX"`.
- **The SQL type comes from the `field-sql-types` table of the knowledge base**, derived from DGF's own
  samples. A `dbtype` with no row there is `SCAFFOLD_SQL_TYPE_UNKNOWN`: a column type is never guessed. A
  decimal's precision and scale are never in the settings file, so they are this design's to state.
- **The key** is an `Integer` field of `Int16`, `Int32` or `Int64`, and becomes an identity column.
- **Every entity needs a `Text` field of dbtype `String` or `StringUnicode` besides its key**, since the lookup
  view the runtime generates reads that field's name and throws when it has none.
- **Not generated in version 1:** `PrimaryKey` and `Checkboxlist` (the vendored `settings.xsd` lacks both, so
  every file would warn `XSD_LAGS_RUNTIME`), `EditableGrid` and `Image`. Each is `SCAFFOLD_MODEL_INVALID`.
- With more than one instance, every generated table gets the `ApplicationId` column exactly as the
  framework's own tables declare it. Isolation between instances is by that column alone, and the generated
  documentation says so.

## What the design never holds

- **An instance's `ApplicationId`.** `generate.py` derives it as a `uuid5` of the application and instance
  names, so a re-generation from the same design reproduces it.
- **A secret, a host, a feed, a registry or an image tag.** Each is a `${NAME}` placeholder in the generated
  files, declared in `docker/.env.example` and `docs/configuration.md`.

## A complete example

Two instances of one shared workspace, two APIs (a public one signing in with DGPass, a staff one with Azure
AD and local sign-in), a register and a service. `workspace` and the About page's `route` are left out, so
the check prints them as defaults.

```json
{
  "design_format": 1,
  "application": {"name": "Inspections", "title": "Inspections Portal"},
  "dgf_version": "1.1.15",
  "instance_model": "shared-workspace",
  "instances": [
    {"name": "lands", "title": "Lands Directorate"},
    {"name": "deeds", "title": "Deeds Directorate"}
  ],
  "apis": [
    {"name": "PublicApi", "deployments": [
      {"name": "LandsPublic", "instance": "lands", "auth": ["dgpass"]},
      {"name": "DeedsPublic", "instance": "deeds", "auth": ["dgpass"]}
    ]},
    {"name": "StaffApi", "deployments": [
      {"name": "LandsStaff", "instance": "lands", "auth": ["azure", "basic"]},
      {"name": "DeedsStaff", "instance": "deeds", "auth": ["azure", "basic"]}
    ]}
  ],
  "roles": ["Inspector", "Supervisor"],
  "base": {"source": "/path/to/webasm", "supply": "copy"},
  "modules": [
    {"name": "Permits", "pattern": "register", "title": "Permit register", "entity": "Permit",
     "route": "/permits", "roles": ["Inspector", "Supervisor"]},
    {"name": "Approval", "pattern": "service", "title": "Approval service", "entity": "Approval",
     "route": "/approval", "roles": ["Supervisor"]},
    {"name": "About", "pattern": "page", "title": "About this service"}
  ],
  "data_model": {"entities": [
    {"name": "PermitType", "key": "Id", "fields": [
      {"name": "Id", "type": "Integer", "dbtype": "Int32", "required": true},
      {"name": "Name", "type": "Text", "dbtype": "String", "size": 100, "required": true}
    ]},
    {"name": "Permit", "key": "Id", "fields": [
      {"name": "Id", "type": "Integer", "dbtype": "Int32", "required": true},
      {"name": "Reference", "type": "Text", "dbtype": "String", "size": 20, "required": true},
      {"name": "Holder", "type": "Text", "dbtype": "StringUnicode", "size": 200, "required": true},
      {"name": "PermitTypeId", "type": "Picklist", "dbtype": "Int32", "required": true,
       "extract": {"entity": "PermitType"}},
      {"name": "IssuedOn", "type": "DateTime", "dbtype": "DateTime"},
      {"name": "Fee", "type": "Money", "dbtype": "Decimal", "precision": 18, "scale": 2},
      {"name": "Active", "type": "Boolean", "dbtype": "Boolean"}
    ]},
    {"name": "Approval", "key": "Id", "fields": [
      {"name": "Id", "type": "Integer", "dbtype": "Int32", "required": true},
      {"name": "Applicant", "type": "Text", "dbtype": "StringUnicode", "size": 200, "required": true},
      {"name": "Summary", "type": "Text", "dbtype": "String", "size": "MAX"},
      {"name": "SubmittedOn", "type": "DateTime", "dbtype": "DateTime"}
    ]}
  ]},
  "sources": {"application.name": "prompt", "dgf_version": "asked", "base.source": "asked", "base.supply": "asked"}
}
```
