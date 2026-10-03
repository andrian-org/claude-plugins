-- Approval: generated from docs/application.json by /dgf-scaffold; this table and the entity's settings.xml
-- in the workspace are rendered from one data_model entry, so they agree.
CREATE TABLE [dbo].[Approval] (
    [Id] INT IDENTITY (1, 1) NOT NULL,
    [Applicant] NVARCHAR(200) NOT NULL,
    [Summary] VARCHAR(MAX) NULL,
    [SubmittedOn] DATETIME NULL,
    [ApplicationId] UNIQUEIDENTIFIER NULL,
    CONSTRAINT [PK_Approval] PRIMARY KEY CLUSTERED ([Id] ASC)
);
GO
