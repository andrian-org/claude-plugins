/*
  Undo apply-sql.sh, so a rehearsal can start again from an empty database for Split Bill.

  Drops the four application tables (children first), the Organiser role with its user links, and the
  aspnet_Applications row for 'splitbill' together with the rows the framework wrote under its
  ApplicationId while the API ran (process instances, events). Nothing of the showcase is touched:
  every delete is filtered on the Split Bill ApplicationId or on the role name.

  Run through sqlcmd in dgf-sqlserver (the prep checklist has the command). Stop splitbill-api first.
*/
SET NOCOUNT ON;

DECLARE @app UNIQUEIDENTIFIER =
    (SELECT [ApplicationId] FROM [dbo].[aspnet_Applications] WHERE [LoweredApplicationName] = 'splitbill');

IF OBJECT_ID(N'dbo.Settlement', N'U') IS NOT NULL DROP TABLE [dbo].[Settlement];
IF OBJECT_ID(N'dbo.Expense',    N'U') IS NOT NULL DROP TABLE [dbo].[Expense];
IF OBJECT_ID(N'dbo.Member',     N'U') IS NOT NULL DROP TABLE [dbo].[Member];
IF OBJECT_ID(N'dbo.BillGroup',  N'U') IS NOT NULL DROP TABLE [dbo].[BillGroup];
PRINT 'Split Bill tables dropped.';

DELETE ur FROM [dbo].[AspNetUserRoles] ur
JOIN [dbo].[AspNetRoles] r ON r.[Id] = ur.[RoleId]
WHERE r.[NormalizedName] = N'ORGANISER';
DELETE FROM [dbo].[AspNetRoles] WHERE [NormalizedName] = N'ORGANISER';
PRINT 'Organiser role removed.';

IF @app IS NOT NULL
BEGIN
    -- Rows the framework partitions by application id, written while splitbill-api ran. Each delete is
    -- guarded: a row another table still references is reported and left, never forced.
    BEGIN TRY DELETE FROM [dbo].[AX_UserEvents] WHERE [ApplicationId] = @app; END TRY
    BEGIN CATCH PRINT 'AX_UserEvents left: ' + ERROR_MESSAGE(); END CATCH
    BEGIN TRY DELETE FROM [dbo].[AX_WF_StateInstances] WHERE [ApplicationId] = @app; END TRY
    BEGIN CATCH PRINT 'AX_WF_StateInstances left: ' + ERROR_MESSAGE(); END CATCH
    BEGIN TRY DELETE FROM [dbo].[AX_WF_ProcessSteps] WHERE [ApplicationId] = @app; END TRY
    BEGIN CATCH PRINT 'AX_WF_ProcessSteps left: ' + ERROR_MESSAGE(); END CATCH
    BEGIN TRY DELETE FROM [dbo].[AX_WF_Processes] WHERE [ApplicationId] = @app; END TRY
    BEGIN CATCH PRINT 'AX_WF_Processes left: ' + ERROR_MESSAGE(); END CATCH
    BEGIN TRY DELETE FROM [dbo].[aspnet_Applications] WHERE [ApplicationId] = @app; END TRY
    BEGIN CATCH PRINT 'aspnet_Applications row left: ' + ERROR_MESSAGE(); END CATCH
    PRINT 'aspnet_Applications row for splitbill removed.';
END
ELSE
    PRINT 'No aspnet_Applications row for splitbill.';
GO
