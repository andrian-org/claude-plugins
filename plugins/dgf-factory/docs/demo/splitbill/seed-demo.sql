/*
  The rest of the demo data, after the presenter has created three rows by hand in the browser:
  the group "Lisbon trip", the member Ana, and the expense "Dinner" (90.00, paid by Ana).

  Adds Ben and Chloe to the group, and the expenses "Taxi" (30.00, paid by Ben) and "Tickets"
  (60.00, paid by Chloe). The equal share is then 60.00 each: Ana +30.00, Ben -30.00, Chloe 0.00.

  Idempotent: a row that already exists by name or title is left alone, so a rehearsal can run it twice.
  If the hand-made rows are missing it creates them too, so it also works as a full seed.
*/
SET NOCOUNT ON;

IF NOT EXISTS (SELECT 1 FROM [dbo].[BillGroup] WHERE [Name] = N'Lisbon trip')
    INSERT INTO [dbo].[BillGroup] ([Name], [Currency], [CreatedOn]) VALUES (N'Lisbon trip', 'EUR', GETDATE());

DECLARE @group INT = (SELECT TOP (1) [Id] FROM [dbo].[BillGroup] WHERE [Name] = N'Lisbon trip' ORDER BY [Id]);

IF NOT EXISTS (SELECT 1 FROM [dbo].[Member] WHERE [GroupId] = @group AND [Name] = N'Ana')
    INSERT INTO [dbo].[Member] ([GroupId], [Name]) VALUES (@group, N'Ana');
IF NOT EXISTS (SELECT 1 FROM [dbo].[Member] WHERE [GroupId] = @group AND [Name] = N'Ben')
    INSERT INTO [dbo].[Member] ([GroupId], [Name]) VALUES (@group, N'Ben');
IF NOT EXISTS (SELECT 1 FROM [dbo].[Member] WHERE [GroupId] = @group AND [Name] = N'Chloe')
    INSERT INTO [dbo].[Member] ([GroupId], [Name]) VALUES (@group, N'Chloe');

DECLARE @ana INT   = (SELECT [Id] FROM [dbo].[Member] WHERE [GroupId] = @group AND [Name] = N'Ana');
DECLARE @ben INT   = (SELECT [Id] FROM [dbo].[Member] WHERE [GroupId] = @group AND [Name] = N'Ben');
DECLARE @chloe INT = (SELECT [Id] FROM [dbo].[Member] WHERE [GroupId] = @group AND [Name] = N'Chloe');

IF NOT EXISTS (SELECT 1 FROM [dbo].[Expense] WHERE [GroupId] = @group AND [Title] = N'Dinner')
    INSERT INTO [dbo].[Expense] ([GroupId], [PaidById], [Title], [Amount], [SpentOn]) VALUES (@group, @ana, N'Dinner', 90.00, GETDATE());
IF NOT EXISTS (SELECT 1 FROM [dbo].[Expense] WHERE [GroupId] = @group AND [Title] = N'Taxi')
    INSERT INTO [dbo].[Expense] ([GroupId], [PaidById], [Title], [Amount], [SpentOn]) VALUES (@group, @ben, N'Taxi', 30.00, GETDATE());
IF NOT EXISTS (SELECT 1 FROM [dbo].[Expense] WHERE [GroupId] = @group AND [Title] = N'Tickets')
    INSERT INTO [dbo].[Expense] ([GroupId], [PaidById], [Title], [Amount], [SpentOn]) VALUES (@group, @chloe, N'Tickets', 60.00, GETDATE());

SELECT m.[Name] AS [Member], COUNT(e.[Id]) AS [Expenses], ISNULL(SUM(e.[Amount]), 0) AS [Paid]
FROM [dbo].[Member] m
LEFT JOIN [dbo].[Expense] e ON e.[PaidById] = m.[Id]
WHERE m.[GroupId] = @group
GROUP BY m.[Name]
ORDER BY m.[Name];
GO
