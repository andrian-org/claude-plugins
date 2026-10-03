/*
  The roles of the application, once each. AspNetRoles has one unique index, on NormalizedName alone, so a
  role name exists once across all applications: the rows belong to the first instance. The framework seeds
  its built-in roles in code only when AspNetRoles is empty, so these rows include the built-ins, and the
  code seed then creates none. NormalizedName is the upper-cased name, as ASP.NET Identity's default does.
*/
DECLARE @applicationId UNIQUEIDENTIFIER = '{{first_instance.application_id}}';
{{#each roles}}
IF NOT EXISTS (SELECT 1 FROM [dbo].[AspNetRoles] WHERE [NormalizedName] = N'{{normalized}}')
    INSERT INTO [dbo].[AspNetRoles] ([Id], [ApplicationId], [Name], [NormalizedName], [ConcurrencyStamp])
    VALUES (NEWID(), @applicationId, N'{{name}}', N'{{normalized}}', CONVERT(NVARCHAR(36), NEWID()));
{{/each}}
GO
