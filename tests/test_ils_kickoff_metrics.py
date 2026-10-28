"""The ILS kickoff analyses (build/ils_pipeline/kickoff/metrics/).

v5's own metrics test (v5 tests/test_ils_kickoff.py at 7ba1e63: the Reg E eligibility test held back
from the loader stage), with the import rewritten, plus the RPE side: the files are v5's, every
analysis computes on a small book, and the pandas 2 shim restores what pandas 3 changes.

Every test runs under kickoff/_v5/compat.legacy_strings(), as the entry points do.
"""
import pathlib

import pandas as pd
import pytest

from ils_pipeline.kickoff.core import io

KICKOFF = pathlib.Path(__file__).resolve().parents[1] / "build" / "ils_pipeline" / "kickoff"
MODULES = ["_common", "account_status", "business_split", "deposits", "nsf_strat", "od_limit",
           "od_status", "product_code", "reg_e"]


@pytest.fixture(autouse=True)
def _v5_pandas():
    """v5's code under the pandas 2 string semantics it was written for (kickoff/_v5/compat.py)."""
    from ils_pipeline.kickoff._v5.compat import legacy_strings
    with legacy_strings():
        yield


# ---- v5's test -------------------------------------------------------------

# ---- 8. a rule that matches EVERYTHING is as useless as one matching none

def test_an_eligibility_rule_matching_every_account_warns():
    """1840: every one of 6,218 rows had Stat Code '0'. Confirming '0' means
    eligible produces a fully eligible 'split' that splits nothing -- the same
    defect as 0%, and it warned on only one of them."""
    from ils_pipeline.kickoff.metrics import reg_e
    import pandas as pd
    df = pd.DataFrame({
        io.ACCT_NO: range(40),
        io.STAT_CODE: ["0"] * 40,
        io.REG_E_FLAG: ["Y"] * 20 + ["N"] * 20,
        io.ACCOUNT_STATUS: ["O"] * 40,
        io.BUSINESS_FLAG: ["P"] * 40,
    })
    _, warning = reg_e.with_eligibility(df, io.CodeConfig(eligible_stat_codes=["0"]))
    assert warning, "a rule matching 100% of accounts passed silently"
    assert "40" in warning


# ---- RPE side --------------------------------------------------------------

def test_every_metrics_file_is_v5_s_and_names_its_source():
    for name in ["__init__"] + MODULES:
        first = (KICKOFF / "metrics" / f"{name}.py").read_text(encoding="utf-8").splitlines()[0]
        assert first.startswith(
            f"# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/{name}.py at 7ba1e63."), name


def test_no_metrics_file_imports_ti_or_aaron_s_modules():
    for name in MODULES:
        src = (KICKOFF / "metrics" / f"{name}.py").read_text(encoding="utf-8")
        assert "ti." not in src and "ars_pipeline" not in src, name


def _book():
    """Six personal and three business open accounts, one closed one."""
    return pd.DataFrame({
        io.ACCT_NO: range(10),
        io.ACCOUNT_STATUS: ["O"] * 9 + ["C"],
        io.BUSINESS_FLAG: ["P"] * 6 + ["B"] * 3 + ["P"],
        io.STAT_CODE: ["A", "A", "A", "Z", "Z", "A", "A", "Z", "A", "A"],
        io.PRODUCT_CODE: ["01", "01", "02", "02", "02", "03", "B1", "B1", "B2", "01"],
        io.REG_E_FLAG: ["Y", "N", "Y", "Y", "N", "N", "Y", "N", "N", "Y"],
        io.TOTAL_ITEMS: [0, 3, 8, 15, 30, 60, 0, 5, 13, 2],
        io.PAID_ITEMS: [0, 3, 6, 10, 20, 30, 0, 5, 7, 2],
        io.OD_LIMIT: [500, 500, 1000, 1000, 1000, 500, 1500, 1500, 500, 500],
        io.DEPOSIT_COUNT: [0, 1, 2, 4, 8, 12, 3, 6, 11, 1],
        io.DEPOSIT_AMOUNT: [0.0, 100.0, 250.0, 900.0, 1800.0, 3000.0, 700.0, 4000.0, 9000.0, 50.0],
        io.SWIPES: [0, 5, 10, 20, 40, 2, 1, 0, 3, 9],
    })


def _total(table):
    return table[table.iloc[:, 0] == "Grand Total"].iloc[0]


def test_every_analysis_computes_and_totals_the_book():
    from ils_pipeline.kickoff.metrics import (account_status, business_split, deposits, nsf_strat,
                                              od_limit, od_status, product_code, reg_e)
    df, codes = _book(), io.CodeConfig(eligible_stat_codes=["A"])
    p, b = io.personal_open(df, codes), io.business_open(df, codes)
    assert (len(p), len(b)) == (6, 3)

    assert _total(account_status.compute(df))["# of Accounts"] == 10
    assert _total(product_code.compute(df))["# of Accounts"] == 10
    split = business_split.compute(df, codes)
    assert _total(split)["# of Accounts"] == 9 and _total(split)["# of Items"] == 134
    assert _total(deposits.compute(p))["Accounts"] == 6
    for level in ("basic", "pay_ratio", "full"):
        assert _total(nsf_strat.compute(p, level=level))["Total OD/NSF Items"] == 116
    assert _total(nsf_strat.compute(p, level="pay_ratio"))["Pay Ratio"] == round(69 / 116, 4)
    assert _total(od_status.compute(b))["# of Items Paid"] == 12
    assert _total(od_limit.compute(p))["# of Accounts"] == 6
    assert _total(reg_e.simple(p))["# of Accounts"] == 6
    table, warning = reg_e.with_eligibility(p, codes)
    assert warning is None and table.iloc[-1]["# of Accounts"] == 6
    assert _total(reg_e.annual(p))["Total NSF Items Paid"] == 69


def test_a_blank_code_is_counted_as_v5_counts_it():
    """Under pandas 3 `astype(str)` keeps a blank blank, so the field summary dropped the blank Business
    Flag from its counts and the Reg E check raised on the blank flag. Under the shim both read as v5."""
    import io as _io
    csv = ("AcctNo,Account Status,Business Flag,Stat Code,Total Items,Paid Items,Reg E Flag\n"
           "1,O,P,,3,2,Y\n2,O,,A,1,1,\n3,O,P,A,0,0,N\n4,C,B,A,2,0,Y\n")
    df = pd.read_csv(_io.StringIO(csv))
    summary = io.field_summary(df)
    assert ["nan", 1] in summary[io.BUSINESS_FLAG]
    assert ["nan", 1] in summary[io.REG_E_FLAG]
    assert io.rege_warnings(df, io.CodeConfig(rege_opt_in=["Y"])) == []
