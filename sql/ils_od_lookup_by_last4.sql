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
--    IlsName on every matched row. ODCustomer = 1 means the account has NSF/OD items.
SELECT l.RowNum, l.Name1 AS ListName,
       COUNT(m.AcctID) OVER (PARTITION BY l.RowNum) AS MatchCount,
       a.AcctID, a.FullName AS IlsName, t.NAME AS AccountType,
       a.ODCustomer, a.MTDNSFODItems, a.YTDNSFODItems, a.ROLL12NSFODItems,
       a.ODLimit, a.PreviousODLimit, a.ODStatusCode, a.CanOverdraft
FROM #list l
LEFT JOIN #m m            ON m.RowNum = l.RowNum
LEFT JOIN accounts a      ON a.AcctID = m.AcctID
LEFT JOIN ACCOUNT_TYPES t ON t.ID = a.acctType
ORDER BY l.RowNum;

-- 2) OD limit changes for matched accounts, one row per change between
--    consecutive limit batches. Depends on od_limit keeping history; spot-check
--    one account known to have changed.
SELECT m.RowNum, m.AcctID, b.CREATED AS BatchDate, h.PriorLimit, h.[LIMIT] AS NewLimit
FROM #m m
JOIN (SELECT o.ACCTID, o.BATCH_ID, o.[LIMIT],
             LAG(o.[LIMIT]) OVER (PARTITION BY o.ACCTID ORDER BY ob.CREATED) AS PriorLimit
      FROM od_limit o JOIN od_limit_batch ob ON ob.BATCH_ID = o.BATCH_ID) h
  ON h.ACCTID = m.AcctID
JOIN od_limit_batch b ON b.BATCH_ID = h.BATCH_ID
WHERE h.PriorLimit IS NOT NULL AND h.PriorLimit <> h.[LIMIT]
ORDER BY m.RowNum, b.CREATED;

DROP TABLE #list, #m;
