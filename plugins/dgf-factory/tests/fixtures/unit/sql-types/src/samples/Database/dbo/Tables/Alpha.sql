-- a comment with a comma, and (parentheses)
CREATE TABLE [dbo].[Alpha] (
    [Id]     INT             IDENTITY (1, 1) NOT NULL,
    [Name]   VARCHAR (50)    NOT NULL,
    [Title]  NVARCHAR (20)   NULL,
    [Note]   VARCHAR (MAX)   NULL,
    [Amount] DECIMAL (18, 2) CONSTRAINT [DF_Alpha_Amount] DEFAULT ((0)) NOT NULL,
    [Calc]   AS ([Id] * 2),
    CONSTRAINT [PK_Alpha] PRIMARY KEY CLUSTERED ([Id] ASC)
);
GO
