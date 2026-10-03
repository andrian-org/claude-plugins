/*
  One aspnet_Applications row per instance. The API does not start without a row for its WorkspaceName:
  WorkspaceProvider looks the workspace up by LoweredApplicationName. SignType and IntranetSignType are
  left to their defaults.
*/
{{#each instances}}
IF NOT EXISTS (SELECT 1 FROM [dbo].[aspnet_Applications] WHERE [LoweredApplicationName] = '{{name}}')
BEGIN
    INSERT INTO [dbo].[aspnet_Applications]
        ([ApplicationId], [ApplicationName], [LoweredApplicationName], [ShortName], [IsAvailable], [SortOrder])
    VALUES
        ('{{application_id}}', '{{title}}', '{{name}}', '{{short_name}}', 1, {{number}});
    PRINT 'Seeded aspnet_Applications row for workspace ''{{name}}''.';
END
ELSE
    PRINT 'Workspace ''{{name}}'' already registered - left unchanged.';
GO
{{/each}}
