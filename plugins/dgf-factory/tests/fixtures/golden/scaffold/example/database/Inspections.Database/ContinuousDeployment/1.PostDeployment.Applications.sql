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
IF NOT EXISTS (SELECT 1 FROM [dbo].[aspnet_Applications] WHERE [LoweredApplicationName] = 'deeds')
BEGIN
    INSERT INTO [dbo].[aspnet_Applications]
        ([ApplicationId], [ApplicationName], [LoweredApplicationName], [ShortName], [IsAvailable], [SortOrder])
    VALUES
        ('929541C2-6DC0-52A7-B7FA-0492F31C2D96', 'Deeds Directorate', 'deeds', 'DEEDS', 1, 2);
    PRINT 'Seeded aspnet_Applications row for workspace ''deeds''.';
END
ELSE
    PRINT 'Workspace ''deeds'' already registered - left unchanged.';
GO
