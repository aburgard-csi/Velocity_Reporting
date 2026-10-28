"""ILS pre-go-live system view (build/ils_pipeline/pre_go_live/system_view.py).

v5's system-view tests (v5 tests/test_pgl_system_view.py): the miniature vendor dumps in the
fixed-width format, copied unchanged, and the two parser tests. The reconcile / waterfall /
core_state tests arrive with the sections.
"""
from ils_pipeline.pre_go_live import system_view

MATRIX = """\
=== OD STATUS CODE MAPPING ===

STATUS_CODE DESCRIPTION  EXPORTED_STATUS ILS_CALC CAN_OVERDRAFT
----------- ------------ --------------- -------- -------------
0           0                            1        0
001         001                          1        1

(2 rows affected)

=== ACCCOUNT TYPES AND MIN/MAX LIMITS ===

Account Type  Matrix Code  Calc? Min         Max         Enabled? Matrix Modified Date
------------- ------------ ----- ----------- ----------- -------- -----------------------
Personal      P            Y     0           1750        Y        2026-04-01 10:08:46.440

(1 rows affected)

=== OVERRIDES ===

Account Type  Matrix Code  Override Criteria                  Override Value  Stop Process Order Index
------------- ------------ ---------------------------------- --------------- ------------ -----------
Personal      P            [Days OD] >= 30                    0               1            0

(1 rows affected)

=== RANGES AND FACTORS ===

Account Type  Matrix Code  Category                 Range                      Factor
------------- ------------ ------------------------ -------------------------- -----------
Personal      P            Age of Account           [01] - 0 to 30 (0, 30)     0
Personal      P            Age of Account           [02] - 31+ (31, 999)       450

(2 rows affected)

=== TIERS AND ROUNDING ===

Account Type  Matrix Code  Min Value  Max Value  Limit Value
------------- ------------ ---------- ---------- ------------
Personal      P            0.00       24.99      0.00
Personal      P            25.00      49.99      25.00

(2 rows affected)
"""

INTEGRITY = """\
=== ACCOUNT METRICS SUMMARY ===

Acct Type  RegE Opt-In RegE Opt-In % Open/Active Open %  Can Overdraft Eligible % Total Accts
---------- ----------- ------------- ----------- ------- ------------- ---------- ------------
Personal   2           40.0          4           80.0    3             60.0       5

=== PROCESS CALCULATION HISTORY ===

ID  ProcessCalculationStart ProcessCalculationEnd   ProcessCalculationSuccess ProcessAccounts ProcessAvg AcctsReceivingZeroLimit TotalOverrid
--- ----------------------- ----------------------- ------------------------- --------------- ---------- ----------------------- ------------
1   2026-08-07 06:00:00.000 2026-08-07 06:00:20.000 1                         4               400.00     1                       1

=== OD STATUS CODE BREAKOUT ===

STATUS_CODE DESCRIPTION  ILS_CALC CAN_OVERDRAFT ACCOUNTS
----------- ------------ -------- ------------- --------
001         001          1        1             3
1           NULL         NULL     NULL          1

=== COUNT OF DELETED ACCOUNTS ===

DELETED                 Count of Accounts Marked Deleted
----------------------- --------------------------------
2025-07-01 06:02:27.690 1
"""


def test_parse_matrix():
    out = system_view.parse_matrix(MATRIX)
    assert out["sysv_matrix_status_map"] == [["0", 1, 0], ["001", 1, 1]]
    assert out["sysv_matrix_types"][0][:4] == ["Personal", "P", 0, 1750]
    assert out["sysv_matrix_overrides"][0] == ["Personal", "[Days OD] >= 30", "0", 1, 0]
    assert out["sysv_matrix_factors"] == [["Personal", "Age of Account", 2, 0, 450]]
    assert out["sysv_matrix_rounding_step"] == 25


def test_parse_integrity():
    out = system_view.parse_integrity(INTEGRITY)
    assert out["sysv_accounts"] == [["Personal", 5, 4, 80.0, 3, 60.0, 2, 40.0]]
    assert out["sysv_calc_latest"]["accounts"] == 4
    assert out["sysv_calc_latest"]["zero_limit"] == 1
    assert out["sysv_od_status_unmapped"] == [["1", 1]]
    assert out["sysv_deleted_total"] == 1
