/*
  One aspnet_Applications row per instance. The API does not start without a row for its WorkspaceName:
  WorkspaceProvider looks the workspace up by LoweredApplicationName. SignType and IntranetSignType are
  left to their defaults.
*/
IF NOT EXISTS (SELECT 1 FROM [dbo].[aspnet_Applications] WHERE [LoweredApplicationName] = 'lands')
BEGIN
    INSERT INTO [dbo].[aspnet_Applications]
        ([ApplicationId], [ApplicationName], [LoweredApplicationName], [ShortName], [IsAvailable], [SortOrder])
    VALUES
        ('D9238E4A-8645-5245-8711-3755A7B486B6', 'Lands Directorate', 'lands', 'LANDS', 1, 1);
    PRINT 'Seeded aspnet_Applications row for workspace ''lands''.';
END
ELSE
    PRINT 'Workspace ''lands'' already registered - left unchanged.';
GO
