# Data model

The entities of {{app.title}}. Each is one folder under `FM/_DATA/` in the workspace, with a `settings.xml`, and one
table in `{{database.project}}`; both are rendered from the same entry of `data_model` in
[application.json](application.json).

{{#unless has_entities}}
The design defines no entity.
{{/unless}}
{{#each entities}}
## {{name}}

Key: `{{key}}`.

| Field | Type | Dbtype | Column | Required |
|---|---|---|---|---|
{{#each fields}}
| {{name}} | {{type}} | {{dbtype}} | {{sql_type}} | {{required_attr}} |
{{/each}}

{{/each}}
A column's SQL type comes from the samples DGF ships: no framework code turns a `settings.xml` into a table.
A decimal's precision and scale are never in the settings file, so they are the design's to state.
