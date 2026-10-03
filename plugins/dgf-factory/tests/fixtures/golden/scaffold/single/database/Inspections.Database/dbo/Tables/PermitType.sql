-- PermitType: generated from docs/application.json by /dgf-scaffold; this table and the entity's settings.xml
-- in the workspace are rendered from one data_model entry, so they agree.
CREATE TABLE [dbo].[PermitType] (
    [Id] INT IDENTITY (1, 1) NOT NULL,
    [Name] VARCHAR(100) NOT NULL,
    CONSTRAINT [PK_PermitType] PRIMARY KEY CLUSTERED ([Id] ASC)
);
GO
