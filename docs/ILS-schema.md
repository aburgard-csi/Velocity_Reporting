# ILS database schema (column inventory)

Source: `select top 10 * from <table>` run by Aaron on an active ILS SQL Server database
(2026-10-07). **Column names only.** The sample rows held real customer data and are not
kept here. Table order follows the query list; `notices` was queried twice.

Companion references (not in the repo): *VIP Data Specification.pdf* (what each import-file
field means, in VIP terms) and *ILS 26.4 Due Diligence Implementation Guide.pdf* (hosting,
server sizing, file watcher; no table layouts).

## How the tables fit together (inferred, not confirmed)

- `accounts.AcctID` is the account key. `balance_history`, `declines`, `notices`,
  `od_limit` (`ACCTID`), `OD_STATUS_CODE_HISTORY`, `REF_CHARGE_OFF`,
  `REG_E_RESPONSE_HISTORY` and `TRANSACTIONS` all carry an `AcctID`. `accounts.AcctNo` is
  encrypted and `AcctID` is a surrogate: join on `AcctID`.
- `accounts.CIF` links to `customer.CIF`. `accounts.Branch` / `LocationCode` link to
  `branch.BRANCHNUMBER`. `accounts.ProdCode` links to `PRODUCT_CODES.ProdCode`.
  `accounts.MailCode` links to `mail_codes.MailCode`. `accounts.ODStatusCode` links to
  `STATUS_CODE_MAPPING.STATUS_CODE`.
- Limit calculation: `matrix` -> `matrix_repositories` -> `matrix_trends` ->
  `matrix_repository_rules`; `matrix` -> `matrix_categories` -> `matrix_ranges` ->
  `matrix_factors`; `matrix_exclusions` and `matrix_fields` hang off the matrix.
  `od_limit` holds the computed limit per account per `od_limit_batch`;
  `od_limit_component` / `OD_LIMIT_COMPONENT_NAME` break a limit into parts, and
  `OD_LIMIT_OVERRIDES` records which matrix/override applied.
- `accounts` mirrors the DDA Master File plus ILS-calculated fields, so most of its
  columns map to a VIP Data Specification field.

## Facts from the VIP Data Specification

- `accounts.acctType` is `ACCOUNT_TYPES.ID` (confirmed from a sample of `ACCOUNT_TYPES`, 2026-10-07):
  1 = Personal (`P`), 2 = Business (`B`), 3 = A Plus Personal (`P`). Match on the
  `ACCOUNT_TYPE` letter to get personal vs business; ID 3 is a second personal type, so
  `acctType = 1` alone misses it. Flags on the table: DDA, Savings, TimeDeposit, Personal,
  CreditCard (all 0/1), plus ACTIVE, ORDER_INDEX, PARALLEL_ENABLED, ACCOUNT_TYPE_GROUP_ID.
- Account Status (file field): `O` Open/Active, `C` Closed, `X` Charged-Off, `I` Inactive,
  `F` Frozen, `R` Restricted, `D` Dormant, `Z` Other.
- Reg E Opt-In Value: `Y` opted in, `N` opted out, `D` no response (default opt-out);
  NULL is treated as default opt-out. `RegEResponseDate` is the opt-in or opt-out date and
  is blank for `D`.
- Business Flag: `P` personal, `B` business/non-consumer.

## accounts: keys, types and indexes (from `sp_help accounts`, 2026-10-07)

- Primary key: `AcctID` (int, clustered). **The only declared foreign key** is
  `acctType` -> `ACCOUNT_TYPES(ID)`. Nothing else is enforced, so the other joins above are
  convention (confirmed by Aaron), not constraints. Each client has its own database, and
  the FK names it in the reference, so a query must run in the right client's database.
- Types worth knowing: money columns are `money`; flags (`business`, `Active`, `ODCustomer`,
  `CanOverdraft`, `MailFlag`, `DebitCard`, `MRPC_Eligible`, `Loan_Eligible`, `EStatements`,
  `Employee`) are `bit`; `acctStatus` is varchar(50); `ODStatusCode`, `ExportedStatus` and
  `LocationCode` are varchar(10); `Branch` is varchar(20); `ProdCode` is varchar(50);
  `RegEOptInValue` is varchar(32); `DaysOpen` is `money` (not int).
- Encrypted or hashed text: `AcctNo`, `TaxID`, `CIF`, `ARS_ACCTNO`, `MICR`,
  `ReassignAccount`. Use `AcctID` for joins, `CIF` only to reach `customer`, and do not
  select the identifying columns into anything that leaves the machine.
- Indexed (cheap to filter or join on): `DELETED`, `acctType`, `CIF` (with `DELETED`),
  `ODStatusCode`, `MailCode` (with `DELETED`), `CanOverdraft`, `ODCustomer`,
  `(OpenDate, LastUpdate)`, `LastUpdate`, `DaysOD`, `(ProdCode, ODStatusCode, ...)`.
  `RegEOptInValue`, `Branch` and `ClassCode` are not indexed.

## Confirmed by Aaron (2026-10-07)

- The joins listed above are correct.
- `accounts.DELETED IS NULL` keeps the accounts in the current data import; a non-NULL
  `DELETED` means the account dropped out of the import (closed accounts in the sample).
- `accounts.Active` is not used. On the code tables (`ACCOUNT_TYPES`, status codes) an
  active flag shows whether a code is enabled, in case one is disabled later.
- `accounts.ODCustomer` = 1 marks accounts with access to the overdraft program (corrected by
  Aaron 2026-10-07; it does NOT mean the account has NSF/OD items). To find accounts that
  actually had NSF/OD items, use `MTDNSFODItems`, `YTDNSFODItems` or `ROLL12NSFODItems` > 0.
- `accounts` is one row per account.
- No table is too large to scan.

## Still unknown

- `accounts.business` was NULL in the sample; its meaning is unconfirmed. Use
  `ACCOUNT_TYPES.ACCOUNT_TYPE` (P/B) for personal vs business.

## Tables
### accounts (213 columns)
Full list is long; groups below, then the verbatim list.

```
AcctID, Institution, AcctNo, FullName, FirstName, LastName, NameAddr1, NameAddr2, NameAddr3, NameAddr4, NameAddr5, NameAddr6, NameAddr7, NameAddr8, HomePhone, WorkPhone, WorkExt, EmailAddr, TaxID, Officer, Branch, OpenDate, ClosedDate, ChargeOffDate, acctStatus, ODSinceDate, LastDepDate, LastUpdate, DaysOD, Balance, AvgCollectedBalance, LastDepAmt, MTDODItems, MTDFees, YTDODItems, YTDFees, YTDDaysOD, PriorYTDDaysOD, LocationCode, BranchName, ClassCode, ProdCode, AutoDeposit, Employee, business, acctType, Active, MailFlag, DailyDepAmt, RegEOptInValue, ODStatusCode, ExportedStatus, ODCustomer, ODLimit, MTDNSFODItems, YTDNSFODItems, MTDNSFODItemsPaid, YTDNSFODItemsPaid, MTDNSFODItemsReturned, YTDNSFODItemsReturned, MTDNSFODFeesCharged, YTDNSFODFeesCharged, MTDNSFODFeesWaived, YTDNSFODFeesWaived, MTDDebitDeclines, YTDDebitDeclines, MTDNSFODWaiverRatio, YTDNSFODWaiverRatio, MTDNSFODPayRatio, YTDNSFODPayRatio, MTDNSFODAltPayRatio, YTDNSFODAltPayRatio, NSFODFeesToDepositsRatio90Days, NSFODFeesToDepositsRatioRolling12Months, FDICOccasionsSinceLastContact, FDICOccasionsRolling12Months, AvgDaysBetweenDeposits, AvgRepaymentRate, CREATED, CREATEDBY, MODIFIED, MODIFIEDBY, DELETED, DELETEDBY, FirstImportDate, CanOverdraft, DateOfBirth, OutstandingLoanAmount, RestrictedFlag, HASHED_ACCOUNT, MASKED_ACCOUNT, LAST_FOUR_SSN, MASKED_ARS_ACCTNO, HASHED_ARS_ACCTNO, ARS_ACCTNO, ACCT_PLUS_ACTIVE_ACCT, ACCT_PLUS_ACTIVE_LOAN, ACCOUNT_PLUS_ID, CARD_LEVEL, ROLL12NSFODItems, ROLL12NSFODFeesCharged, ODLOCAmount, CIF, DISCLOSED_LIMIT, DISCLOSED_LIMIT_RECOVERY_ELIGIBLE, DailyACHDebitAmount, DailyCHKDebitAmount, DailyMiscDebitAmount, DISCLOSED_LIMIT_MIDCYCLE_ZERO, MRPC_Eligible, ROLL12Refunds, ROLL12RefundedFees, ROLL12Waivers, ROLL12FeesWaived, CYCLE_FLAG, NameAddr9, EStatements, ReturnedDeposit, CellPhone, IntermediateODLimit, PreviousODLimit, Loan_Eligible, APPROVED_LOAN_AMOUNT, AvgBalance33Days, ParallelODLimit, IntermediateParallelODLimit, PreviousParallelODLimit, Deposits30Days, DaysOpen, LimitSuspensionDate, LimitReinstatementDate, UnderwritingRelationshipTenure, UnderwritingFeesToDeposits, UnderwritingDirectDeposit, UnderwritingAnnualFeeCap, UnderwritingYTDODFees, DateOfUnderwriting, DateOfUnderwritingEvaluation, ChallengerValue, MTDODPaidItems, MTDODPaidItemFees, SODFlag, DynamicLimitResumptionDate, STRATEGIC_REFUNDS_FACTOR, STRATEGIC_REFUNDS_ACTION, Strategic_Refund_Eligible, ISMLA, Deposit_Score, MobileDepAmt, PreferredContactTime, Onboarding_Status, Account_Activity_Score, Onboarding_Score, IsTempAccount, Service_Score_HHD, PreferredContactPhone, PreferredContactName, Personalize_Letter_Text, OfficerField, MASKED_CIF, RegEResponseDate, UnutilizedServices, CYCLE_DATE, DISCLOSED_LIMIT_DATE, DISCLOSED_RECOVERY_AMOUNT, CCCL_AcctID, ExcessiveODMonitoringEndDate, ExcessiveODMonitoringProjectedEndDate, ExcessiveODZeroLimitStartDate, ExcessiveODZeroLimitEndDate, ExcessiveODNormalLimitStartDate, BrandingCode, Last4AcctNo, MICR, Appl, ReassignAccount, MailCode, ProdCodeDescription, Balance_Avail, Balance_Ledger, AvgBalMTD, AvgBalYTD, CurrRate, PaidInterest, SvcCharges, ExcessTranFees, LowBalFees, OtherCharges, DebitCard, NSFODPriorMonth, NSFODPriorMonthFees, NSFODItemsNoExclusionsYTD, NSFODItemsPYTD, UserDefined1, UserDefined2, UserDefined3, UserDefined4, UserDefined5, WF_Numerator, WF_Divisor, HASHED_ACCTNO_REASSIGN, MASKED_ACCTNO_REASSIGN, HSC_Eligible, HSC_Matrix_ID, RDI90Days, Deposit_Score_Id, HSC_Enrollment, LOAN_TYPE_ID, STRATEGIC_REFUNDS_SERVICEFEES_FACTOR, STRATEGIC_REFUNDS_SERVICEFEES_ACTION, HNBRiskAttribute2, NumberOfODs, NumberOfPreviousCPLoans
```

### balance_history (4 columns)
```
AcctID, Balance, LastUpdate, ID
```

### branch (11 columns)
```
BRANCHNUMBER, BRANCHNAME, BRANCHPHONE, ID, BranchManager, BranchManagerSignature, OnboardingEnabled, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### customer (45 columns)
```
Institution, Branch, CIF, FullName, NameAddr1, NameAddr4, NameAddr5, NameAddr6, NameAddr7, NameAddr8, NameAddr9, FirstName, LastName, HomePhone, WorkPhone, CellPhone, EmailAddr, DateOfBirth, TaxID, MailCode, EStatements, EntityType, CIFStatus, RelationshipOfficer, EmployeeFlag, DirectorRegO, ISMLA, OnlineBanking, MobileBanking, EmailOptIn, SMS_OptIn, FullyOptedIn, CustomerSinceDate, UserDefined1, UserDefined2, UserDefined3, UserDefined4, UserDefined5, LastUpdate, Created, CreatedBy, Updated, UpdatedBy, Deleted, DeletedBy
```

### declines (8 columns)
```
DECLINE_DATE, AcctID, TRANSACTION_TYPE, TRANSACTION_AMOUNT, MCC_CODE, TERMINAL_LOCATION, IMPORT_ID, ID
```

### notices (21 columns)
```
AcctID, NoticeDate, ItemDesc, ItemAmt, ItemPaid, FeeAmt, Balance, ItemStatus, TransactionType, FeeAssessed, IMPORT_ID, PRINT_BATCH_ID, PrintNotice, WaiverReason, ID, MCC, Strategic_Refunds_Service_Fees_Risk_Factor, Strategic_Refunds_Risk_Factor_NSFOD, ODLimit, ParallelODLimit, Limit_Batch_Exported
```

### institution (5 columns)
```
INSTITUTIONNUMBER, INSTITUTIONAME, ID, DefaultAccountRepresentative, DefaultAccountRepresentativeSignature
```

### mail_codes (3 columns)
```
ID, MailCode, MailFlag
```

### matrix (37 columns)
```
ID, CODE, CALC_LIMIT, MIN_LIMIT, MAX_LIMIT, ACCOUNT_TYPE, APPLY_TIER, CREATED_DATE, CREATED_USER, MODIFIED_DATE, MODIFIED_USER, ASSIGN_DEFAULT, CRITICAL, DISCLOSED_LIMITS, DL_CYCLE_ZERO, DL_CYCLE_RECOVER, CYCLE_LIMIT_ON, PARALLEL_MIN_LIMIT, PARALLEL_MAX_LIMIT, evalMaxLimitAfterOverrides, evalMinLimitAsOverride, MaxPercentOfODLimit, MaxDolarAmount, MRPC_CP_Eligible, DL_ODP_REINSTATEMENT, ConditionXML, OD_Repayment_Loan_Eligible, Days_Overdrawn, Balance_LessThanOrEqual, ODMaxDollarAmount, CP_Chargeoff_Eligibility, CP_Chargeoff_Eligibility_All_Accounts, DL_Reduction_OutstandingLoanAmount, Allow_Reduction_To_MatrixMinimum, Allow_Reduction_To_Minimum, Reduction_To_Minimum, Apply_Tiering_Rounding
```

### matrix_categories (11 columns)
```
ID, MATRIX_ID, NAME, CALC, CALC_REVIEW, ENABLE, TABLE_NAME, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### matrix_exclusions (10 columns)
```
ID, MATRIX_ID, NAME, CALC, ENABLE, DESCRIPTION, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### matrix_factors (7 columns)
```
ID, RANGE_ID, VALUE, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### matrix_fields (11 columns)
```
ID, NAME, REPOSITORY_ID, CALC, CALC_REVIEW, ENABLE, TABLE_NAME, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### matrix_ranges (14 columns)
```
ID, NAME, CATEGORY_ID, MIN_VALUE, MIN_UNIT, MIN_CONVERTED, MAX_VALUE, MAX_UNIT, MAX_CONVERTED, ENABLE, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### MATRIX_REPOSITORIES (8 columns)
```
ID, MATRIX_ID, NAME, ENABLE, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### MATRIX_REPOSITORY_RULES (12 columns)
```
ID, TREND_ID, CALC, VALUE, ENABLE, STOP_PROCESS, ORDER_INDEX, DESCRIPTION, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### matrix_trends (9 columns)
```
ID, REPOSITORY_ID, MIN_DEPOSIT_AMOUNT, MIN_DEPOSIT_COUNT, MIN_OVERDRAFT_COUNT, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### matrix_units (2 columns)
```
ID, NAME
```

### od_limit (7 columns)
```
LIMIT_ID, BATCH_ID, ACCTID, LIMIT, LIMIT_TIER, EXPORTABLE, APPROVED_LOAN_AMOUNT
```

### od_limit_batch (6 columns)
```
BATCH_ID, USER_ID, CREATED, EXPIRATION, EXPORTED, DELETED
```

### od_limit_component (5 columns)
```
ID, LIMIT_ID, COMPONENT_TYPE, COMPONENT_LIMIT, COMPONENT_VALUE
```

### OD_LIMIT_COMPONENT_NAME (2 columns)
```
ID, COMPONENT_NAME
```

### OD_LIMIT_OVERRIDES (4 columns)
```
ID, LIMIT_ID, MATRIX_ID, OVERRIDE_ID
```

### OD_STATUS_CODE_HISTORY (4 columns)
```
AcctID, ODStatusCode, Modified, ID
```

### PRODUCT_CODES (13 columns)
```
ID, ProdCode, Description, MRPC_Eligible, Loan_Eligible, Strategic_Refund_Eligible, Deposit_Score_Eligible, OnboardingEnabled, OD_Repayment_Eligibility, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### products (4 columns)
```
ID, PRODUCT_NAME, CREATED_USER, CREATED_DATE
```

### REF_CHARGE_OFF (12 columns)
```
CORecoveryID, AcctID, Principal, Fees, NsfOdFees, SodFees, MiscFees, TotalAmount, Type, Date, Reason, IMPORT_ID
```

### REG_E_RESPONSE_HISTORY (5 columns)
```
ID, AcctID, RegEResponseDate, RegEOptInValue, Modified
```

### STATUS_CODE_MAPPING (14 columns)
```
STATUS_CODE, DESCRIPTION, CRITERIA, EXPORTED_STATUS, ILS_CALC, CAN_OVERDRAFT, MRPC_Eligible, Loan_Eligible, ID, OD_Repayment_Eligibility, CREATED_USER, CREATED_DATE, UPDATED_USER, UPDATED_DATE
```

### TRANSACTIONS (14 columns)
```
ID, TRANSACTION_DATE, AcctID, TYPE, AMOUNT, MCC, DESCRIPTION, DESCRIPTION2, TERMINAL_ID, MERCHANT_ID, INSTITUTION, IMPORT_ID, CARD_PRESENT, TRANCODE
```

### ACCOUNT_TYPES (17 columns)
```
ID, ACCOUNT_TYPE, NAME, ORDER_INDEX, ACTIVE, CREATED_DATE, UPDATED_DATE, CREATED_USER, UPDATED_USER, PARALLEL_ENABLED, ACCOUNT_TYPE_GROUP_ID, DDA, Savings, TimeDeposit, Personal, CreditCard
```
