"""R6 (2026-11-05): the MCC codes ranked three ways -- by card dollars, by transactions and by
members (distinct accounts) -- and the slide that shows the three lists side by side.

The user: "mcc code should be included / we should see mcc code by spend, transactions, # of
members/customers". Ranked by dollars alone, a code with many members and small tickets (fast
food, transit) never showed.

    python -m pytest tests/test_ti_mcc_three_ways.py -q
"""
import pathlib
import sys

import pandas as pd
import pytest
from pptx import Presentation

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "build" / "ars_pipeline"))

from ti import chapters_txn as X                                            # noqa: E402
from ti.deck import helpers, txn_cards as C, txn_slides                     # noqa: E402
from ti.transaction_intelligence import merchant_profiles as MP, merchants  # noqa: E402
from test_ti_hotspot_slides import _Harness                                 # noqa: E402

CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()
ANCHOR = pd.Timestamp("2026-07-31")
TITLE = "MCC codes by spend, transactions and members"
FILLERS = [4900, 5541, 5912, 5995, 5999, 6300, 7011, 7230, 7832, 8220]   # 2 accounts, $600 each


def make_frame() -> pd.DataFrame:
    rows = []

    def add(acct, mcc, amount, day):
        rows.append((pd.Timestamp(2026, 6 + day % 2, 1 + day), acct, "SIG", amount,
                     f"M{mcc}", f"M{mcc}", str(mcc)))
    for d in range(5):                                   # one big grocery spender: $5,000, 5 txns
        add("G1", 5411, 1000.0, d)
    for i in range(15):                                  # fast food: 15 members, $5 each
        add(f"D{i}", 5814, 5.0, i)
    for k, code in enumerate(FILLERS):
        add("F1", code, 300.0, k)
        add("F2", code, 300.0, k + 1)
    rows.append((pd.Timestamp(2026, 7, 2), "G1", "ACH", 9_999.0, "PAYROLL", "PAYROLL", None))
    return pd.DataFrame(rows, columns=["transaction_date", "primary_account_num",
                                       "transaction_type", "amount", "merchant_name",
                                       "merchant_key", "mcc_code"])


@pytest.fixture(scope="module")
def m():
    return MP.compute(make_frame(), None, merchants.load_categories(CONFIG_DIR), ANCHOR,
                      lambda _w: None)


def test_three_rankings_each_carry_every_measure_and_rank(m):
    cols = m["mch_mcc_by_dollars_columns"]
    assert cols == ["mcc", "group", "accounts", "txns", "dollars", "avg_ticket",
                    "pct_of_card_accounts", "rank_dollars", "rank_txns", "rank_accounts"]
    assert m["mch_mcc_by_txns_columns"] == cols == m["mch_mcc_by_accounts_columns"]
    for key in ("mch_mcc_by_dollars", "mch_mcc_by_txns", "mch_mcc_by_accounts"):
        assert len(m[key]) == 10
    # 18 card accounts: G1, D0-D14, F1, F2 (the ACH row is not a card transaction)
    assert m["mch_mcc_card_accounts"] == 18
    assert m["mch_mcc_by_dollars"][0] == [5411, "Grocery", 1, 5, 5000, 1000.0, 5.6, 1, 2, 12]
    assert m["mch_mcc_by_accounts"][0] == [5814, "Dining", 15, 15, 75, 5.0, 83.3, 12, 1, 1]
    assert m["mch_mcc_by_txns"][:2] == [m["mch_mcc_by_accounts"][0], m["mch_mcc_by_dollars"][0]]
    # ties break on the lower code
    assert [r[0] for r in m["mch_mcc_by_dollars"][1:4]] == [4900, 5541, 5912]


def test_dollars_alone_hides_the_many_member_code(m):
    assert 5814 not in [r[0] for r in m["mch_mcc_by_dollars"]]
    assert 5411 not in [r[0] for r in m["mch_mcc_by_accounts"]]
    # the old dollar table is unchanged and still only ranks by dollars
    assert m["mch_mcc_top"][0][0] == 5411


def test_standouts_name_codes_that_rank_very_differently(m):
    assert m["mch_mcc_standouts_columns"] == ["mcc", "group", "top_on", "rank_top_on",
                                              "outside_on", "rank_outside_on"]
    assert m["mch_mcc_standouts"] == [
        [5814, "Dining", "accounts", 1, "dollars", 12],
        [5814, "Dining", "txns", 1, "dollars", 12],
        [5411, "Grocery", "dollars", 1, "accounts", 12],
        [5411, "Grocery", "txns", 2, "accounts", 12]]


def test_the_base_is_stated(m):
    note = m["mch_mcc_ways_note"]
    assert m["mch_mcc_ways_window"] == "Jun26-Jul26"
    assert "card transactions" in note and "distinct accounts with a card transaction" in note
    assert "18 accounts with any card transaction" in note


def test_no_mcc_column_writes_no_rankings():
    df = make_frame().drop(columns=["mcc_code"])
    out = MP.compute(df, None, merchants.load_categories(CONFIG_DIR), ANCHOR, lambda _w: None)
    assert not any(k.startswith("mch_mcc_by_") for k in out)


class _TableHarness(_Harness):
    def __init__(self):
        super().__init__()
        self.tables = []
        self["MARGIN_L"] = 0.6
        self["table"] = lambda s, rows, left, top, width, **k: self.tables.append((rows, k))


def test_slide_shows_the_three_lists_side_by_side_and_shades_the_standouts(m):
    h = _TableHarness()
    assert C.mcc_codes_three_ways(h, dict(m), "personal accounts") is None
    (head, sub), title = h.slides[-1]
    assert title == TITLE
    assert head == "Dining (5814) is #1 by members but #12 by card dollars"
    assert "Jun26-Jul26" in sub and "personal accounts" in sub
    assert "year" not in head + sub and "None" not in head + sub
    rows, kw = h.tables[-1]
    assert rows[0] == ["#", "By card dollars", "By transactions", "By members"]
    assert len(rows) == 11
    assert rows[1][1] == "Grocery (5411)  $5.0K"
    assert rows[1][2] == "Dining (5814)  15"
    assert rows[1][3] == "Dining (5814)  15 (83%)"
    shaded = [(r, c) for r in range(1, 11) for c in range(1, 4) if kw["cell_fill"](r, c)]
    assert shaded == [(1, 1), (1, 2), (1, 3), (2, 2)]
    rail = h.rails[-1]
    assert rail[0] == ("Card accounts", "18", "with a card transaction Jun26-Jul26")
    assert rail[1] == ("Dining (5814)", "#1 by members", "#12 by card dollars")
    assert rail[2] == ("Grocery (5411)", "#1 by card dollars", "#12 by members")


def test_without_standouts_the_headline_names_the_leaders(m):
    t = dict(m, mch_mcc_standouts=[])
    h = _TableHarness()
    assert C.mcc_codes_three_ways(h, t, "personal accounts") is None
    (head, _sub), _title = h.slides[-1]
    assert head == ("Grocery (5411) leads on card dollars; "
                    "Dining (5814) leads on transactions and members")
    assert not any(kw["cell_fill"](r, c) for rows, kw in h.tables
                   for r in range(1, 11) for c in range(1, 4))


def test_slide_declines_with_a_reason():
    assert C.mcc_codes_three_ways(_TableHarness(), {}, "x") == f"{TITLE} (no mch_mcc_by_dollars)"
    why = C.mcc_codes_three_ways(_TableHarness(), {"mch_mcc_coverage_pct": 0.0}, "x")
    assert why.startswith(TITLE + " (MCC on 0% of card rows")


def test_slide_renders_on_a_real_slide(m):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    h = _TableHarness()
    h["slide"] = lambda headsub, title: (slide, 1.6)
    h["rail"] = helpers._rail
    h["table"] = helpers._table
    assert C.mcc_codes_three_ways(h, dict(m), "personal accounts") is None
    tables = [s for s in slide.shapes if s.has_table]
    assert len(tables) == 1 and len(tables[0].table.rows) == 11


def test_registered_in_both_builder_lists_and_kept():
    import json
    assert C.mcc_codes_three_ways in X.TI_BUILDERS and C.mcc_codes_three_ways in txn_slides.BUILDERS
    assert X.TITLES["mcc_codes_three_ways"] == TITLE
    sel = json.loads((HERE.parent / "build" / "ars_pipeline" / "ti" / "slides.json")
                     .read_text(encoding="utf-8"))
    assert sel["slides"][TITLE] == "keep"
    assert TITLE in sel["_by_chapter"]["Transaction Intelligence"]
