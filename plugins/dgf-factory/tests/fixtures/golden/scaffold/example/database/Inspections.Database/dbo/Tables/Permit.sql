-- Permit: generated from docs/application.json by /dgf-scaffold; this table and the entity's settings.xml
-- in the workspace are rendered from one data_model entry, so they agree.
CREATE TABLE [dbo].[Permit] (
    [Id] INT IDENTITY (1, 1) NOT NULL,
    [Reference] VARCHAR(20) NOT NULL,
    [Holder] NVARCHAR(200) NOT NULL,
    [PermitTypeId] INT NOT NULL,
    [IssuedOn] DATETIME NULL,
    [Fee] DECIMAL(18,2) NULL,
    [Active] BIT NULL,
    [ApplicationId] UNIQUEIDENTIFIER NULL,
    CONSTRAINT [FK_Permit_PermitTypeId] FOREIGN KEY ([PermitTypeId]) REFERENCES [dbo].[PermitType] ([Id]),
    CONSTRAINT [PK_Permit] PRIMARY KEY CLUSTERED ([Id] ASC)
);
GO
