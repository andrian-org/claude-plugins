WITH cnt AS (SELECT GroupId, COUNT(*) AS Members FROM dbo.Member GROUP BY GroupId),
     paid AS (SELECT GroupId, PaidById AS MemberId, SUM(Amount) AS Paid FROM dbo.Expense GROUP BY GroupId, PaidById),
     share AS (SELECT e.GroupId, CAST(SUM(e.Amount) / c.Members AS DECIMAL(18,2)) AS Share FROM dbo.Expense e JOIN cnt c ON c.GroupId = e.GroupId GROUP BY e.GroupId, c.Members),
     settled AS (SELECT GroupId, FromMemberId AS MemberId, SUM(Amount) AS Paid FROM dbo.Settlement GROUP BY GroupId, FromMemberId),
     received AS (SELECT GroupId, ToMemberId AS MemberId, SUM(Amount) AS Received FROM dbo.Settlement GROUP BY GroupId, ToMemberId)
SELECT m.Id AS [key], g.Name AS [Group], m.Name AS [Member],
       ISNULL(p.Paid, 0) AS [Paid], ISNULL(s.Share, 0) AS [Share],
       ISNULL(p.Paid, 0) - ISNULL(s.Share, 0) + ISNULL(st.Paid, 0) - ISNULL(r.Received, 0) AS [Balance]
FROM dbo.Member m
JOIN dbo.BillGroup g ON g.Id = m.GroupId
LEFT JOIN paid p ON p.GroupId = m.GroupId AND p.MemberId = m.Id
LEFT JOIN share s ON s.GroupId = m.GroupId
LEFT JOIN settled st ON st.GroupId = m.GroupId AND st.MemberId = m.Id
LEFT JOIN received r ON r.GroupId = m.GroupId AND r.MemberId = m.Id
ORDER BY g.Name, [Balance] DESC
