-- {{entity.name|sqlid}}: generated from docs/application.json by /dgf-scaffold; this table and the entity's settings.xml
-- in the workspace are rendered from one data_model entry, so they agree.
CREATE TABLE [dbo].[{{entity.name|sqlid}}] (
{{#each entity.fields}}
    [{{name|sqlid}}] {{sql_type}}{{sql_identity}} {{sql_null}},
{{/each}}
{{#if entity.has_application_id}}
    [ApplicationId] UNIQUEIDENTIFIER NULL,
{{/if}}
{{#each entity.fields}}
{{#if has_extract}}
    CONSTRAINT [FK_{{entity.name|sqlid}}_{{name|sqlid}}] FOREIGN KEY ([{{name|sqlid}}]) REFERENCES [dbo].[{{extract_entity|sqlid}}] ([{{extract_key|sqlid}}]),
{{/if}}
{{/each}}
    CONSTRAINT [PK_{{entity.name|sqlid}}] PRIMARY KEY CLUSTERED ([{{entity.key|sqlid}}] ASC)
);
GO
