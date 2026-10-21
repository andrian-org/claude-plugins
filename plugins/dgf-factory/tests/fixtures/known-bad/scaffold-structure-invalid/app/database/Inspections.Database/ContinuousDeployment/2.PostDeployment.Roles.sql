/*
  The roles of the application, once each. AspNetRoles has one unique index, on NormalizedName alone, so a
  role name exists once across all applications: the rows belong to the first instance. The framework seeds
  its built-in roles in code only when AspNetRoles is empty, so these rows include the built-ins, and the
  code seed then creates none. NormalizedName is the upper-cased name, as ASP.NET Identity's default does.
*/
DECLARE @applicationId UNIQUEIDENTIFIER = 'D9238E4A-8645-5245-8711-3755A7B486B6';
IF NOT EXISTS (SELECT 1 FROM [dbo].[AspNetRoles] WHERE [NormalizedName] = N'ADMINISTRATORS')
    INSERT INTO [dbo].[AspNetRoles] ([Id], [ApplicationId], [Name], [NormalizedName], [ConcurrencyStamp])
    VALUES (NEWID(), @applicationId, N'Administrators', N'ADMINISTRATORS', CONVERT(NVARCHAR(36), NEWID()));
IF NOT EXISTS (SELECT 1 FROM [dbo].[AspNetRoles] WHERE [NormalizedName] = N'MEMBERS')
    INSERT INTO [dbo].[AspNetRoles] ([Id], [ApplicationId], [Name], [NormalizedName], [ConcurrencyStamp])
    VALUES (NEWID(), @applicationId, N'Members', N'MEMBERS', CONVERT(NVARCHAR(36), NEWID()));
IF NOT EXISTS (SELECT 1 FROM [dbo].[AspNetRoles] WHERE [NormalizedName] = N'ANONYMOUS')
    INSERT INTO [dbo].[AspNetRoles] ([Id], [ApplicationId], [Name], [NormalizedName], [ConcurrencyStamp])
    VALUES (NEWID(), @applicationId, N'Anonymous', N'ANONYMOUS', CONVERT(NVARCHAR(36), NEWID()));
IF NOT EXISTS (SELECT 1 FROM [dbo].[AspNetRoles] WHERE [NormalizedName] = N'REGISTERED USERS')
    INSERT INTO [dbo].[AspNetRoles] ([Id], [ApplicationId], [Name], [NormalizedName], [ConcurrencyStamp])
    VALUES (NEWID(), @applicationId, N'Registered Users', N'REGISTERED USERS', CONVERT(NVARCHAR(36), NEWID()));
IF NOT EXISTS (SELECT 1 FROM [dbo].[AspNetRoles] WHERE [NormalizedName] = N'PORTALUSER')
    INSERT INTO [dbo].[AspNetRoles] ([Id], [ApplicationId], [Name], [NormalizedName], [ConcurrencyStamp])
    VALUES (NEWID(), @applicationId, N'PortalUser', N'PORTALUSER', CONVERT(NVARCHAR(36), NEWID()));
IF NOT EXISTS (SELECT 1 FROM [dbo].[AspNetRoles] WHERE [NormalizedName] = N'INSPECTOR')
    INSERT INTO [dbo].[AspNetRoles] ([Id], [ApplicationId], [Name], [NormalizedName], [ConcurrencyStamp])
    VALUES (NEWID(), @applicationId, N'Inspector', N'INSPECTOR', CONVERT(NVARCHAR(36), NEWID()));
IF NOT EXISTS (SELECT 1 FROM [dbo].[AspNetRoles] WHERE [NormalizedName] = N'SUPERVISOR')
    INSERT INTO [dbo].[AspNetRoles] ([Id], [ApplicationId], [Name], [NormalizedName], [ConcurrencyStamp])
    VALUES (NEWID(), @applicationId, N'Supervisor', N'SUPERVISOR', CONVERT(NVARCHAR(36), NEWID()));
GO
