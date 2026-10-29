"""The pre-go-live codes as the ILS system holds them (build/ils_pipeline/pre_go_live/dump_codes.py, 2026-10-28).

Pinned: OD-eligible is the matrix's CAN_OVERDRAFT = 1 codes; open and Reg E opt-in are offered only when one
value's live count equals the integrity check's figure, and the reason is said when none does; a blank code
is never offered; a status the dump prints as NULL is named, so the deck's unmapped-codes line builds.
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build")]
from ils_pipeline.pre_go_live import dump_codes, system_view  # noqa: E402

COLS = ["type", "total", "open", "open_pct", "can_overdraft", "can_od_pct", "rege_optin", "rege_pct"]


def _sysv(open_=(3, 1), rege=(1, 1), smap=(["Y", 1, 1], ["8", 1, 0], ["null", 1, 1])):
    return {"sysv_matrix_status_map": [list(r) for r in smap],
            "sysv_accounts_columns": COLS,
            "sysv_accounts": [["Business", 0, open_[0], 0, 0, 0, rege[0], 0],
                              ["Personal", 0, open_[1], 0, 0, 0, rege[1], 0]]}


def _df():
    return pd.DataFrame({"Account Status Code": ["O", "O", "O", "O", "C", "X"],
                         "OD Status Code (from Core)": ["Y", "Y", "8", None, "Y", "8"],
                         "Reg-E Opt-In Value": ["Y", "Y", "N", "N", "N", "Y"],
                         "Deleted": [None, None, None, None, None, pd.Timestamp(2026, 1, 1)]})


def test_od_eligible_is_the_matrix_can_overdraft_codes_and_never_a_blank():
    d = dump_codes.derive(_df(), _sysv())["pgl_dump_codes"]
    assert d["od_eligible"]["codes"] == ["Y"]
    assert "blank status" in d["od_eligible"]["basis"]


def test_open_and_rege_are_matched_on_live_counts():
    d = dump_codes.derive(_df(), _sysv(open_=(1, 3), rege=(0, 2)))["pgl_dump_codes"]
    assert d["open_status"]["codes"] == ["O"] and "4 live accounts" in d["open_status"]["basis"]
    assert d["rege_opt_in"]["codes"] == ["Y"]          # the deleted row's Y is not counted
    assert d["rege_opt_out"]["codes"] == ["N"]


def test_no_exact_match_offers_nothing_and_says_why():
    d = dump_codes.derive(_df(), _sysv(open_=(1, 1)))["pgl_dump_codes"]
    assert d["open_status"]["codes"] == [] and "no Account Status value" in d["open_status"]["basis"]


def test_a_null_status_in_the_dump_is_named():
    text = """=== OD STATUS CODE BREAKOUT ===

STATUS_CODE ILS_CALC CAN_OVERDRAFT ACCOUNTS
----------- -------- ------------- --------
Y           1        1             10340
NULL        NULL     NULL          123
"""
    m = system_view.parse_integrity(text)
    assert m["sysv_od_status_unmapped"] == [["NULL", 123]]
    assert ", ".join(c for c, _ in m["sysv_od_status_unmapped"]) == "NULL"   # what the deck joins
