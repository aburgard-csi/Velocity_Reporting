"""ILS pre-go-live system view (build/ils_pipeline/pre_go_live/system_view.py).

v5's system-view tests (v5 tests/test_pgl_system_view.py): the miniature vendor dumps in the
fixed-width format, copied unchanged, the two parser tests, and the reconcile / waterfall /
core_state tests on a hand-built extract.
"""
import pandas as pd
import pytest

from ils_pipeline.pre_go_live import system_view
from ils_pipeline.pre_go_live.bases import Bases
from ils_pipeline.pre_go_live.codes import Codes
from ils_pipeline.pre_go_live.sections import core_state, reconcile, waterfall

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


@pytest.fixture()
def ctx():
    # 5 live accounts: 4 open (3 can-OD 001, 1 status 003 unmapped), 1 closed.
    df = pd.DataFrame({
        "AcctNo": ["1", "2", "3", "4", "5"],
        "Personal_Business": ["PERSONAL"] * 5,
        "Account Status Code": ["O", "O", "O", "O", "C"],
        "OD Status Code (from Core)": ["001", "001", "001", "003", "1"],
        "Eligible_For_Scoring": ["YES", "YES", "YES", pd.NA, pd.NA],
        "Initial OD Limit (from Core)": [600, 600, 0, 600, 0],
        "Reg-E Opt-In Value": ["Y", "N", "Y", "N", "N"],
        "Exported Status Code (from ILS)": ["0"] * 5,
        "YTDODItems": [3, 0, 1, 0, 0],
        "Days OD": [0, 0, 2, 0, 0],
        "Deposit Count Last 33 days": [4, 0, 2, 1, 0],
        "Deposit Amount Last 33 days": [1000.0, 0.0, 400.0, 50.0, 0.0],
    })
    codes = Codes(open_status=["O"], od_eligible=["001"], rege_opt_in=["Y"])
    masks = {"all": pd.Series(True, index=df.index),
             "personal": pd.Series(True, index=df.index),
             "open": df["Account Status Code"] == "O"}
    system = {**system_view.parse_matrix(MATRIX), **system_view.parse_integrity(INTEGRITY)}
    # miniature integrity numbers sized to this frame: calc=3 scorable
    system["sysv_calc_latest"]["accounts"] = 3
    inputs = {"codes": codes, "system": system, "deleted_rows": 1}
    return df, Bases(masks=masks), inputs


def test_reconcile_matches_and_findings(ctx):
    df, b, inputs = ctx
    warns = []
    m = reconcile.compute(df, b, inputs, warns.append)
    rows = {r[0]: r for r in m["pgl_reconcile"]}
    assert rows["live accounts (extract minus deleted) vs ILS book"][4] is True
    assert m["pgl_reconcile_misses"] == 0
    finds = " ".join(m["pgl_reconcile_findings"])
    assert "shadow mode" in finds
    assert "NO mapping" in finds


def test_reconcile_declines_without_dump(ctx):
    df, b, inputs = ctx
    warns = []
    m = reconcile.compute(df, b, {"codes": inputs["codes"]}, warns.append)
    assert m == {}
    assert any("no integrity-check dump" in w for w in warns)


def test_waterfall_steps_confirmed(ctx):
    df, b, inputs = ctx
    m = waterfall.compute(df, b, inputs, lambda _w: None)
    steps = {s[0]: s for s in m["pgl_waterfall"]}
    assert steps["Rows received"][1] == 6                        # 5 live + 1 deleted
    assert steps["Live accounts"][1] == 5
    assert steps["Open accounts (status O)"][1] == 4
    assert steps["ILS calculates a limit"][1] == 3
    assert "003" in steps["ILS calculates a limit"][3]
    assert steps["Can overdraft today (core status 001)"][1] == 3
    assert m["pgl_waterfall_confirmed"] >= 3


def test_core_state_on_core_limits(ctx):
    df, b, inputs = ctx
    warns = []
    m = core_state.compute(df, b, inputs, warns.append)
    dist = {r[0]: r for r in m["pgl_core_limits"]}
    assert dist[600][1] == 3 and dist[600][3] == 2               # two 001 at $600
    assert m["pgl_core_can_od_zero"] == 1                        # acct 3
    assert m["pgl_core_exposure"] == 1200                        # can-OD core dollars
    odd = {r[0]: r for r in m["pgl_core_odd_pockets"]}
    assert odd["003"][1] == 1 and odd["003"][3] == 600
    assert any("outside the ILS mapping" in w for w in warns)
