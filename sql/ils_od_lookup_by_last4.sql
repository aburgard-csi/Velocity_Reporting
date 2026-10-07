-- ILS: are these customers OD users, and have their OD limits changed?
--
-- Run in ONE client's hosted ILS database (one database per client).
-- Use when the list has raw account numbers, which cannot be matched to
-- HASHED_ACCOUNT (the hash is made by VIP Secure Connect). Match on the last
-- 4 of the account number plus the last 4 of the tax ID instead, then CHECK
-- every match by name: 8 digits can collide.
--
-- Build the list in Excel (keep as text). Only these four values go into SQL,
-- never full account numbers or tax IDs:
--   OldLast4  =RIGHT(<old account>,4)
--   NewLast4  =RIGHT(<new account>,4)
--   TaxLast4  =RIGHT(<tax id>,4)
--   Name1     =SUBSTITUTE(<name>,"'","''")     doubles single quotes for T-SQL;
--             first =SUBSTITUTE(<name>,"’","'") if names carry curly apostrophes
--   one row   ="('"&G2&"','"&H2&"','"&I2&"','"&SUBSTITUTE(E2,"'","''")&"'),"
-- Paste the rows as VALUES, not formulas. A VALUES list holds at most 1,000
-- rows, so split a longer list into several INSERTs; end each with ';'.
--
-- The list and the results hold customer names and OD data: keep them out of
-- the repo. Schema: docs/ILS-schema.md.

CREATE TABLE #list (RowNum int IDENTITY(1,1), OldLast4 char(4), NewLast4 char(4),
                    TaxLast4 char(4), Name1 varchar(250));
INSERT INTO #list (OldLast4, NewLast4, TaxLast4, Name1) VALUES
 -- paste rows 2-1001 here
;
INSERT INTO #list (OldLast4, NewLast4, TaxLast4, Name1) VALUES
 -- paste the remaining rows here
;

-- Candidate matches: last4 SSN plus last4 of the old or new account number.
-- DELETED IS NULL keeps accounts in the current data import.
SELECT l.RowNum, a.AcctID
INTO #m
FROM #list l
JOIN accounts a ON a.DELETED IS NULL
               AND a.LAST_FOUR_SSN = l.TaxLast4
               AND a.Last4AcctNo IN (l.NewLast4, l.OldLast4);

-- 1) One row per list entry. MatchCount: 0 = not found (closed, dropped out of
--    the import, or a different last 4), >1 = ambiguous. Compare ListName with
--    IlsName on every matched row. ODCustomer = 1 means the account has access to the OD program;
--    it is NOT usage. HadNSFODItems = 1 means NSF/OD items this month, this year or in
--    the last 12 months.
SELECT l.RowNum, l.Name1 AS ListName,
       COUNT(m.AcctID) OVER (PARTITION BY l.RowNum) AS MatchCount,
       a.AcctID, a.FullName AS IlsName, t.NAME AS AccountType,
       a.ODCustomer,
       CASE WHEN COALESCE(a.MTDNSFODItems,0) + COALESCE(a.YTDNSFODItems,0)
                 + COALESCE(a.ROLL12NSFODItems,0) > 0 THEN 1 ELSE 0 END AS HadNSFODItems,
       a.MTDNSFODItems, a.YTDNSFODItems, a.ROLL12NSFODItems,
       a.ODLimit, a.PreviousODLimit, a.ODStatusCode, a.CanOverdraft
FROM #list l
LEFT JOIN #m m            ON m.RowNum = l.RowNum
LEFT JOIN accounts a      ON a.AcctID = m.AcctID
LEFT JOIN ACCOUNT_TYPES t ON t.ID = a.acctType
ORDER BY l.RowNum;

-- 2) Per list entry: the last OD limit before the account number change and the
--    latest limit. Batches from every matched AcctID for the entry are combined,
--    in case the old and new account numbers carry separate histories. A NULL
--    pre-conversion limit means no batch before the date. Depends on od_limit
--    keeping history; spot-check one account.
DECLARE @ConversionDate date = '2000-01-01';  -- SET: date of the account number change

WITH h AS (
    SELECT m.RowNum, b.BATCH_ID, b.CREATED AS BatchDate, o.[LIMIT]
    FROM #m m
    JOIN od_limit o       ON o.ACCTID = m.AcctID
    JOIN od_limit_batch b ON b.BATCH_ID = o.BATCH_ID
)
SELECT l.RowNum, l.Name1 AS ListName,
       pre.BatchDate AS PreConversionBatchDate, pre.[LIMIT] AS LastLimitBeforeConversion,
       lat.BatchDate AS LatestBatchDate,        lat.[LIMIT] AS LatestLimit
FROM #list l
LEFT JOIN (SELECT RowNum, BatchDate, [LIMIT],
                  ROW_NUMBER() OVER (PARTITION BY RowNum ORDER BY BatchDate DESC, BATCH_ID DESC) AS rn
           FROM h WHERE BatchDate < @ConversionDate) pre
       ON pre.RowNum = l.RowNum AND pre.rn = 1
LEFT JOIN (SELECT RowNum, BatchDate, [LIMIT],
                  ROW_NUMBER() OVER (PARTITION BY RowNum ORDER BY BatchDate DESC, BATCH_ID DESC) AS rn
           FROM h) lat
       ON lat.RowNum = l.RowNum AND lat.rn = 1
ORDER BY l.RowNum;

DROP TABLE #list, #m;
