# Ported from ARS v5 02-Scripts/tests/test_txn_sections.py at a491b5c (James Gilmore); logic unchanged.
# Not yet here (they arrive with the flight overlay): test_overlay_joins_flight_to_named_destinations, test_overlay_declines_without_balance_columns, test_overlay_destinations_carry_the_deposit_decline.
"""merchants / card_behavior / relationship / lens families: hand-built frame,
every answer known.

    python -m pytest tests/test_txn_sections.py -q

Accounts: A1 heavy card user (recurring Netflix + groceries, both rails),
A2 card-only single-channel, A3 transfers-only with a recurring biller,
A4 card + ACH + P2P, B1 business card. WALMART fades (first 9 months only);
TEMU is new (last 2 months only).
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()

from ti.transaction_intelligence import card_behavior, financial_services, merchants, relationship  # noqa: E402
from ti.transaction_intelligence.lens import Lenses, family_table                                   # noqa: E402
from ti.transaction_intelligence.merchant import merchant_key                                       # noqa: E402

ANCHOR = pd.Timestamp("2026-07-31")


def _card(acct, merchant, month, day=10, amount=25.0, token="PURCHASE-SIG", typ="SIG", hour=13):
    desc = f"XX1056 {token} {month:02d}/{day:02d} {hour:02d}:17 {merchant} HYANNIS MA 69424885 0701"
    return (pd.Timestamp(2026, month, day) if month > 0 else pd.Timestamp(2025, 12 + month, day),
            acct, typ, amount, desc)


def _xfer(acct, desc, month, amount=100.0, typ="ACH"):
    return (pd.Timestamp(2026, month, 15) if month > 0 else pd.Timestamp(2025, 12 + month, 15),
            acct, typ, amount, desc)


def make_frame() -> pd.DataFrame:
    r = []
    for mth in range(1, 8):                                      # Jan..Jul 2026
        r.append(_card("A1", "NETFLIX.COM", mth, 3, 15.49, token="PURCHASE-RECUR", hour=6))
        r.append(_card("A1", "STOP SHOP 0552", mth, 12, 84.10, hour=18))
        r.append(_card("A1", "SHELL OIL 5751", mth, 20, 42.00, hour=8))
        r.append(_xfer("A1", "NATIONAL GRID vi CHECK PYMT 7017", mth, 180.0, "CHK"))
        r.append(_card("A2", "DUNKIN #336", mth, 5, 6.75, hour=7))
        r.append(_xfer("A3", "COMCAST XFINITY 555555", mth, 89.0))
        r.append(_card("A4", "MCDONALD'S F1234", mth, 8, 11.20, hour=12))
        r.append(_xfer("A4", "VENMO PAYMENT 888888888", mth, 50.0))
        r.append(_card("B1", "HOME DEPOT 271", mth, 9, 310.0, hour=10))
    for mth in range(-3, 5):                                     # Oct 2025..Apr 2026 only: fades
        r.append(_card("A1", "WALMART SC 2671", mth if mth > 0 else mth, 22, 60.0, hour=16))
    for mth in (6, 7):                                           # new merchant
        r.append(_card("A4", "TEMU.COM 999", mth, 25, 18.0, hour=21))
    r.append(_card("A1", "STOP SHOP 0552", 7, 13, 30.0, token="PURCHASE-PIN", typ="PIN", hour=17))
    df = pd.DataFrame(r, columns=["transaction_date", "primary_account_num", "transaction_type",
                                  "amount", "merchant_name"])
    df["mcc_code"] = None
    df["merchant_key"] = merchant_key(df["merchant_name"])
    return df


def make_lenses() -> Lenses:
    ids = pd.Index(["A1", "A2", "A3", "A4", "B1"])
    def mask(members):
        return pd.Series([i in members for i in ids], index=ids)
    masks = {"all": pd.Series(True, index=ids),
             "responders": mask({"A1", "A4"}),
             "mailed_nonresp": mask({"A2", "A3"}),
             "not_mailed": mask({"B1"}),
             "business": mask({"B1"}), "personal": ~mask({"B1"})}
    attrs = pd.DataFrame({"Branch": ["1", "1", "2", "2", "3"],
                          "Prod Desc": ["Free Checking", "Free Checking", "Premier",
                                        "Premier", "Business Checking"],
                          "Curr Bal": [1000.0, 2000.0, 3000.0, 4000.0, 5000.0]}, index=ids)
    return Lenses(key_column="Acct ID", accounts=ids, masks=masks, attrs=attrs)


@pytest.fixture(scope="module")
def ctx():
    df, lenses = make_frame(), make_lenses()
    personal = lenses.ids("personal")
    fin_spec = financial_services.load_patterns(CONFIG_DIR, {})
    fin_rows = financial_services.classify_rows(df, fin_spec)
    return df, lenses, personal, fin_rows


# ---------------------------------------------------------------------------
# merchants
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mch(ctx):
    df, lenses, personal, _ = ctx
    spec = merchants.load_categories(CONFIG_DIR)
    warnings = []
    m = merchants.compute(df, lenses, spec, ANCHOR, warnings.append,
                          account_filter=personal, key_prefix="mch_",
                          base_label="personal accounts")
    return m, warnings


def test_merchants_top_and_concentration(mch):
    m, _ = mch
    top = {r[0]: r for r in m["mch_top"]}
    assert "NETFLIX COM" in top and "STOP SHOP" in top
    assert "HOME DEPOT" not in top                       # business account excluded
    assert m["mch_card_accounts"] == 3                   # A1 A2 A4; A3 is transfers-only
    stop = top["STOP SHOP"]
    cols = m["mch_top_columns"]
    assert stop[cols.index("txns")] == 8                 # 7 SIG + 1 PIN
    # the masked token (XX1056 PURCHASE) is excluded from the NAME tables
    # but its dollars stay in the denominator -- unattributable-by-name
    # spend must not inflate named-merchant concentration
    assert "XX1056 PURCHASE" not in top
    assert 85.0 < m["mch_top15_share_pct"] < 99.0


def test_merchants_categories_use_keywords_without_mcc(mch):
    m, _ = mch
    assert m["mch_category_method"] == "keywords"
    cats = {r[0]: r for r in m["mch_by_category"]}
    assert "Grocery" in cats and "Subscriptions" in cats
    assert cats["Fuel"][1] == 1                          # one account buys fuel
    # keyword buckets and MCC groups share one taxonomy, so a no-MCC client
    # carries the same parents a client with MCC would
    assert cats["Grocery"][5] == "Everyday"
    assert cats["Subscriptions"][5] == "Lifestyle"


def test_merchants_new_and_faded(mch):
    m, _ = mch
    assert any(r[0].startswith("TEMU") for r in m["mch_new"])
    assert any(r[0].startswith("WALMART") for r in m["mch_faded"])
    assert not any(r[0].startswith("NETFLIX") for r in m["mch_faded"])


def test_merchants_by_lens_and_gap(mch):
    m, _ = mch
    by = {r[0]: r for r in m["mch_by_lens"]}
    assert by["business"][2] == 1
    assert by["responders"][2] == 2
    assert "mch_responder_spend_gap" in m


# ---------------------------------------------------------------------------
# card_behavior
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def beh(ctx):
    df, lenses, personal, _ = ctx
    warnings = []
    m = card_behavior.compute(df, lenses, ANCHOR, warnings.append,
                              account_filter=personal, key_prefix="beh_",
                              base_label="personal accounts")
    return m, warnings


def test_behavior_tickets_and_intensity(beh):
    m, _ = beh
    assert m["beh_ticket_median"] > 0
    bands = {b[0]: b[1] for b in m["beh_ticket_bands"]}
    assert bands["$5-15"] >= 7                            # DUNKIN + MCDONALD'S rows
    assert m["beh_txns_per_active_acct_mo"] > 0


def test_behavior_recurring_from_token(beh):
    m, _ = beh
    assert m["beh_recurring_txn_pct"] > 0
    top = [r[0] for r in m["beh_top_recurring"]]
    assert top and top[0].startswith("NETFLIX")
    assert m["beh_accounts_with_recurring"] == 1


def test_behavior_heat_grid_and_peak(beh):
    m, _ = beh
    assert len(m["beh_heat_grid"]) == 7
    assert sum(sum(r) for r in m["beh_heat_grid"]) > 0
    assert m["beh_peak"][2] >= 1


def test_behavior_responder_gaps_and_routing(beh):
    m, _ = beh
    by = {r[0]: r for r in m["beh_by_lens"]}
    assert by["responders"][2] == 2 and by["mailed_nonresp"][2] == 1
    assert "beh_responder_ticket_gap" in m
    assert m["beh_pin_share_pct"] > 0                     # both rails exist in this frame
    routed = {r[0]: r for r in m["beh_routing_by_merchant"]}
    assert "STOP SHOP" in routed


def test_behavior_declines_without_pin():
    df = make_frame()
    df = df[df["transaction_type"] != "PIN"]
    warnings = []
    m = card_behavior.compute(df, None, ANCHOR, warnings.append)
    assert "beh_routing_by_merchant" not in m
    assert any("single card rail" in w for w in warnings)


# ---------------------------------------------------------------------------
# relationship
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rel(ctx):
    df, lenses, personal, fin_rows = ctx
    warnings = []
    m = relationship.compute(df, lenses, fin_rows, ANCHOR, warnings.append,
                             account_filter=personal, key_prefix="rel_",
                             base_label="personal accounts")
    return m, warnings


def test_relationship_breadth(rel):
    m, _ = rel
    assert m["rel_accounts_total"] == 4
    dist = {r[0]: r[1] for r in m["rel_breadth"]}
    assert dist[1] == 2                                   # A2 card-only, A3 ACH-only
    assert dist[2] >= 1                                   # A1 card+CHK
    by_ch = {r[0]: r[1] for r in m["rel_by_channel"]}
    assert by_ch["card"] == 3 and by_ch["P2P"] == 1


def test_relationship_single_channel_mix(rel):
    m, _ = rel
    assert m["rel_single_channel"] == 2
    mix = dict(m["rel_single_channel_mix"])
    assert mix.get("card") == 1 and mix.get("ACH") == 1


def test_relationship_billers(rel):
    m, _ = rel
    assert m["rel_billers_mean"] > 0                      # COMCAST + NATIONAL GRID + NETFLIX recur
    bands = {r[0]: r[1] for r in m["rel_billers_bands"]}
    assert bands["0"] < 4                                 # someone has a biller


def test_relationship_by_lens_and_primary(rel):
    m, _ = rel
    by = {r[0]: r for r in m["rel_by_lens"]}
    assert by["business"][2] == 1
    assert m["rel_primary_like_n"] == 0                   # nobody hits 10 txns/mo in this tiny frame
    assert "rel_primary_like_note" in m


# ---------------------------------------------------------------------------
# lens families
# ---------------------------------------------------------------------------

def test_family_masks_and_table(ctx):
    df, lenses, _, _ = ctx
    fam = lenses.family("branch")
    assert set(fam) == {"1", "2", "3"}
    assert list(fam["3"]) == ["B1"]
    prod = lenses.family("product")
    assert "Free Checking" in prod
    assert lenses.family("swipe_tier") == {}              # no SwipeCat3 column
    rows = family_table(df, lenses, "branch")
    by = {r[0]: r for r in rows}
    assert by["1"][1] == 2 and by["3"][1] == 1
    assert family_table(df, lenses, "swipe_tier") == []


# ---------------------------------------------------------------------------
# overlay (deposit flight x competitor)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# report: family tables must not masquerade as deposit dollars
# ---------------------------------------------------------------------------

def test_family_lines_labeled_as_txn_dollars_not_deposits():
    """1441 regression: the by-branch/product/swipe-tier rows are gross
    transaction dollars over the load window, but they printed unlabeled
    directly under the DEPOSIT FLIGHT header and were read as deposit
    balances (Non-user 28,190 accts $11.6B)."""
    from ti.transaction_intelligence import sections_report
    m = {"ovl_flight_n": 2, "ovl_flight_threshold": 25_000,
         "ovl_flight_deposits": 70_000, "ovl_flight_decline": 6_000,
         "txn_window_months": 12,
         "txn_by_branch": [["1", 2, 10, 5_000]],
         "txn_by_swipe_tier": [["Non-user", 3, 12, 9_000]]}
    lines = sections_report.lines(m)
    text = "\n".join(lines)
    header_idx = [i for i, ln in enumerate(lines) if "TRANSACTION DOLLARS BY LENS" in ln]
    assert header_idx, "family tables need their own header naming what the dollars are"
    header = lines[header_idx[0]]
    assert "12-month" in header and "NOT deposit balances" in header
    flight_idx = next(i for i, ln in enumerate(lines) if "DEPOSIT FLIGHT" in ln)
    branch_idx = next(i for i, ln in enumerate(lines) if "by branch" in ln)
    # the family block starts after its own header, not inside the flight block
    assert flight_idx < header_idx[0] < branch_idx
    assert "Non-user" in text


def test_family_lines_header_absent_when_no_family_rows():
    from ti.transaction_intelligence import sections_report
    lines = sections_report.lines({"ovl_flight_n": 1, "ovl_flight_threshold": 25_000,
                                   "ovl_flight_deposits": 30_000, "ovl_flight_decline": 500})
    assert not any("TRANSACTION DOLLARS BY LENS" in ln for ln in lines)


# ---------------------------------------------------------------------------
# degenerate amounts: all-NaN medians must report None, never warn
# ---------------------------------------------------------------------------

def test_fin_category_of_zero_dollar_accounts_reports_none_not_nan():
    """1585's blank-amount rows land as $0: an account whose transfers are
    all $0 has wallet_share 0/0 = NaN. A category made only of such accounts
    must report None for its median -- and never emit numpy's 'Mean of empty
    slice' RuntimeWarning (the overnight-batch console spam, one per
    category)."""
    import warnings as w
    df = make_frame()
    extra = pd.DataFrame(
        [_xfer("Z1", "COINBASE.COM 12345", mth, 0.0) for mth in (5, 6, 7)],
        columns=["transaction_date", "primary_account_num",
                 "transaction_type", "amount", "merchant_name"])
    extra["mcc_code"] = None
    extra["merchant_key"] = merchant_key(extra["merchant_name"])
    df = pd.concat([df, extra], ignore_index=True)
    spec = financial_services.load_patterns(CONFIG_DIR, {})
    with w.catch_warnings():
        w.simplefilter("error", RuntimeWarning)
        m, _ = financial_services.compute(df, None, spec, ANCHOR, None,
                                          lambda _m: None)
    row = next(r for r in m["fin_by_category"]
               if r[0] == "Crypto/Digital Assets")
    assert row[8] is None            # median wallet share: absent, not NaN


def test_behavior_lens_of_blank_amount_txns_reports_none_median():
    """A lens whose card txns all carry blank amounts must get a None
    median ticket, silently."""
    import warnings as w
    df = make_frame()
    extra = pd.DataFrame(
        [_card("Z9", "MYSTERY SHOP 1", mth, 4, float("nan")) for mth in (6, 7)],
        columns=["transaction_date", "primary_account_num",
                 "transaction_type", "amount", "merchant_name"])
    extra["mcc_code"] = None
    extra["merchant_key"] = merchant_key(extra["merchant_name"])
    df = pd.concat([df, extra], ignore_index=True)

    class OneLens:
        def names(self):
            return ["blankers"]

        def label(self, _):
            return "blank-amount accounts"

        def ids(self, _):
            return pd.Index(["Z9"])

    with w.catch_warnings():
        w.simplefilter("error", RuntimeWarning)
        m = card_behavior.compute(df, OneLens(), ANCHOR, lambda _m: None)
    row = next(r for r in m["beh_by_lens"] if r[0] == "blankers")
    assert row[3] is None            # median ticket: absent, not NaN


# ---------------------------------------------------------------- ICS lens
# Regression: the ICS lens was gated on an "ICS Account" column, but every
# client stamped from the DM/referral lists carries "DM-REF Source" instead
# (ics_sources.py). The mask was therefore never built and the whole
# transaction chapter reported no ICS cut -- on 1776, 2,448 stamped accounts
# and 202 txn metrics, none of them ICS.

def _odd(**cols) -> pd.DataFrame:
    base = {"Acct Number": ["a1", "a2", "a3", "a4"]}
    base.update(cols)
    return pd.DataFrame(base).set_index("Acct Number")


def test_ics_lens_reads_the_dm_ref_source_stamp():
    from ti.transaction_intelligence.lens import ics_masks
    m = ics_masks(_odd(**{"DM-REF Source": ["DM", "REF", "", "DM+REF"]}))
    assert m["ics"].tolist() == [True, True, False, True]
    # an account on both lists counts in BOTH channels -- each program
    # claims its own acquisition, matching ics.py's ics_source_counts
    assert m["ics_dm"].tolist() == [True, False, False, True]
    assert m["ics_ref"].tolist() == [False, True, False, True]


def test_ics_lens_still_reads_the_documented_column():
    from ti.transaction_intelligence.lens import ics_masks
    m = ics_masks(_odd(**{"ICS Account": ["Y", "N", "YES", ""]}))
    assert m["ics"].tolist() == [True, False, True, False]
    assert "ics_dm" not in m          # no source column -> no channel split


def test_ics_lens_unions_both_flags_when_both_present():
    from ti.transaction_intelligence.lens import ics_masks
    m = ics_masks(_odd(**{"ICS Account": ["Y", "N", "N", "N"],
                          "DM-REF Source": ["", "REF", "", ""]}))
    assert m["ics"].tolist() == [True, True, False, False]


def test_ics_lens_absent_when_the_odd_carries_neither_flag():
    from ti.transaction_intelligence.lens import ics_masks
    assert ics_masks(_odd(**{"Branch": ["1", "2", "3", "4"]})) == {}
