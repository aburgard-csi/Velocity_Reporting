"""Buy now, pay later in depth (James, 2026-11-05: "i think our BNPL section needs to be expanded and
improved. there are alot of gaps, especially around vendors/merchats").

Pinned: the providers real descriptors show are named; the merchant behind a card-rail BNPL
payment is read from the descriptor; comp_bnpl carries each provider's use, repeat use, stacking,
the merchants, who uses it by lens and users against non-users; the two new slides decline on an
empty book, draw for real on a full one, say only what their numbers show, and are registered in
the builder lists, the titles and slides.json.

    python -m pytest tests/test_ti_bnpl_expansion.py -q
"""
import json
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti import chapters_txn as X                                              # noqa: E402
from ti.deck import txn_compete as P, txn_slides                              # noqa: E402
from ti.transaction_intelligence import competition, financial_services      # noqa: E402
from test_ti_competition import ANCHOR, CLIENT_CFG, CONFIG_DIR, _rows, make_lenses  # noqa: E402
from test_ti_hotspot_slides import _Harness                                   # noqa: E402

SLIDES_JSON = HERE.parent / "build" / "ars_pipeline" / "ti" / "slides.json"
CHASE = "CHASE CREDIT CRD CHECK PYMT 000000000006182"
WALMART = "XX9999 PURCHASE-SIG 07/02 11:00 WALMART HYANNIS MA 12345678 0702"


@pytest.fixture(scope="module")
def spec():
    return competition.load_config(CONFIG_DIR, CLIENT_CFG)


# ---------------------------------------------------------------- providers

@pytest.mark.parametrize("text, provider", [
    ("APPLE PAY LATER", "Apple Pay Later"),
    ("CASH APP AFTERPAY", "Afterpay"),          # not Cash App: the longer pattern wins
    ("ZIP PAY", "Zip"),
    ("ZIPPAY", "Zip"),
    ("ZIP.CO*BESTBUY", "Zip"),
    ("PAYPAL PAY MONTHLY", "PayPal Credit"),
    ("PAYPAL PAY LATER", "PayPal Credit"),
    ("CREDOVA", "Credova"),
    ("AFFIRM.COM PAYMENTS", "Affirm"),
    ("KLARNA INC", "Klarna"),
    ("AFTERPAY US", "Afterpay"),
    ("SEZZLE INC", "Sezzle"),
])
def test_the_providers_real_descriptors_show_are_named(spec, text, provider):
    t = competition._classify(pd.Index([text]), spec)
    assert t.loc[text, "category"] == provider
    assert t.loc[text, "kind"] == "bnpl"


def test_a_secured_card_and_a_wallet_are_not_bnpl(spec):
    t = competition._classify(pd.Index(["CHIME CREDIT BUILDER", "APPLE CASH SENT MONEY"]), spec)
    assert t.loc["CHIME CREDIT BUILDER", "kind"] != "bnpl"
    assert t.loc["APPLE CASH SENT MONEY", "kind"] == "adjacency"


# ---------------------------------------------------------------- merchants

@pytest.mark.parametrize("text, merchant", [
    ("AFFIRM *PELOTON", "PELOTON"),
    ("AFFIRM *PELOTON 855-4233729 CA", "PELOTON"),
    ("KLARNA*TARGET", "TARGET"),
    ("KLARNA*TARGET.COM 844-552-7621 OH", "TARGET"),
    ("AFTERPAY* ULTA", "ULTA"),
    ("SEZZLE*FASHIONNOVA", "FASHIONNOVA"),
    ("ZIP.CO*BESTBUY", "BESTBUY"),
    ("AFFIRM INC *WAYFAIR.COM", "WAYFAIR"),
    ("KLARNA*BEST BUY MN", "BEST BUY"),
    ("AFTERPAY*FOREVER 21 SAN JOSE CA", "FOREVER 21"),
    ("AFFIRM * PAY 4ZE3UE", None),               # a payment code, not a merchant
    ("AFFIRM.COM PAYMENTS", None),               # the lender alone
    ("KLARNA INC", None),
    ("KLARNA* KLARNA.COM", None),
    ("WALMART HYANNIS MA", None),
])
def test_the_merchant_is_read_after_the_lender_and_a_star(spec, text, merchant):
    assert competition.bnpl_merchant_matcher(spec)(text) == merchant


def make_frame() -> pd.DataFrame:
    r = []
    for m in range(1, 5):                                            # A1: Affirm in 4 months
        r += _rows("A1", f"XX1234 PURCHASE-SIG 0{m}/10 10:00 AFFIRM *PELOTON 855-4233729 CA",
                   "SIG", [m], 50.0)
    r += _rows("A1", "KLARNA*TARGET.COM 844-552-7621 OH", "SIG", [5], 30.0)   # and Klarna: stacked
    r += _rows("A1", CHASE, "ACH", [7])
    r += _rows("A2", "AFFIRM.COM PAYMENTS 123456789", "ACH", [6, 7], 100.0)    # no merchant named
    r += _rows("A2", CHASE, "ACH", [7])
    r += _rows("A3", "AFTERPAY* ULTA", "SIG", [7], 40.0)
    r += _rows("A4", "KLARNA*TARGET", "SIG", [3, 6], 20.0)
    r += _rows("A5", CHASE, "ACH", [7])
    for a in ("A5", "A6", "A7", "A8"):
        r += _rows(a, WALMART, "SIG", [7], 70.0)
    r += _rows("B1", "SEZZLE*FASHIONNOVA", "SIG", [7], 60.0)                  # business, not the base
    return pd.DataFrame(r, columns=["transaction_date", "primary_account_num",
                                    "transaction_type", "amount", "merchant_name"])


@pytest.fixture(scope="module")
def bnpl(spec, tmp_path_factory):
    df, lenses = make_frame(), make_lenses()
    fin_rows = financial_services.classify_rows(df, financial_services.load_patterns(CONFIG_DIR, CLIENT_CFG))
    m, _ = competition.compute(df, lenses, spec, fin_rows, ANCHOR, tmp_path_factory.mktemp("lists"),
                               lambda *a: None, account_filter=lenses.ids("personal"),
                               key_prefix="comp_", base_label="personal accounts")
    return m["comp_bnpl"]


def test_reach_and_dollars_are_the_base_only(bnpl):
    assert bnpl["accounts"] == 4 and bnpl["dollars"] == 510       # B1's Sezzle is business
    assert bnpl["txns"] == 10 and bnpl["median_ticket"] == 50.0


def test_each_provider_carries_its_use(bnpl):
    cols = bnpl["providers_columns"]
    rows = {r[0]: dict(zip(cols, r)) for r in bnpl["providers"]}
    assert [r[0] for r in bnpl["providers"]] == ["Affirm", "Klarna", "Afterpay"]
    a = rows["Affirm"]
    assert (a["accounts"], a["txns"], a["dollars"], a["median_ticket"]) == (2, 6, 400, 50.0)
    assert (a["repeat_accounts"], a["repeat_pct"]) == (1, 50.0)       # A1 paid in 4 months, A2 in 2
    assert a["per_acct_month"] == round(400 / 2 / 7, 2)
    k = rows["Klarna"]
    assert (k["accounts"], k["txns"], k["dollars"], k["median_ticket"], k["repeat_accounts"]) == \
        (2, 3, 70, 20.0, 0)


def test_repeat_use_and_stacking(bnpl):
    assert (bnpl["repeat_accounts"], bnpl["repeat_pct"]) == (1, 25.0)
    assert (bnpl["stacked_accounts"], bnpl["stacked_pct"]) == (1, 25.0)
    assert bnpl["providers_per_account"] == [[1, 3], [2, 1], [3, 0]]


def test_the_merchants_behind_the_payments(bnpl):
    cols = bnpl["merchants_columns"]
    assert cols == ["merchant", "accounts", "pct_of_users", "txns", "dollars", "lender"]
    assert bnpl["merchants"] == [["PELOTON", 1, 25.0, 4, 200, "Affirm"],
                                 ["TARGET", 2, 50.0, 3, 70, "Klarna"],
                                 ["ULTA", 1, 25.0, 1, 40, "Afterpay"]]
    assert bnpl["merchants_by_accounts"][0][0] == "TARGET"
    assert bnpl["merchants_n"] == 3
    assert bnpl["merchant_named_dollars"] == 310
    assert bnpl["merchant_named_pct"] == round(100 * 310 / 510, 1)


def test_who_uses_it_by_lens_against_the_book(bnpl):
    rows = {r[0]: r for r in bnpl["by_lens"]}
    assert (bnpl["book_users"], bnpl["book_accounts"], bnpl["book_pct"]) == (5, 9, 55.6)
    assert rows["responders"][2:5] == [3, 2, 66.7]
    assert rows["business"][2:5] == [1, 1, 100.0]
    assert rows["personal"][2:5] == [8, 4, 50.0]
    assert rows["responders"][5] == round(66.7 / 55.6 * 100)


def test_users_against_non_users(bnpl):
    rows = {r[0]: r for r in bnpl["users_vs_nonusers"]}
    u, o = rows["BNPL users"], rows["Non-users"]
    assert u == ["BNPL users", 4, round(310 / 4 / 7, 2), 50.0, 2500]
    assert o == ["Non-users", 4, round(280 / 4 / 7, 2), 25.0, 6500]
    assert bnpl["users_vs_nonusers_base"] == "personal accounts"


# ---------------------------------------------------------------- slides

FULL = {
    "comp_accounts_total": 400,
    "lenses": [["all", "All accounts", 600], ["responders", "Responders", 120],
               ["mailed_nonresp", "Mailed non-responders", 300], ["business", "Business", 90],
               ["personal", "Personal", 500], ["new_accounts", "Opened last 12 mo", 80]],
    "comp_bnpl": {
        "accounts": 48, "pct": 12.0, "dollars": 24_000, "months": 12, "per_acct_month": 41.67,
        "providers": [["Affirm", 30, 7.5, 15_000, 41.67, 300, 50.0, 12, 40.0],
                      ["Klarna", 20, 5.0, 6_000, 25.0, 200, 30.0, 4, 20.0],
                      ["Afterpay", 8, 2.0, 3_000, 31.25, 80, 37.5, 1, 12.5]],
        "providers_columns": ["institution", "accounts", "pct_of_accounts", "dollars",
                              "per_acct_month", "txns", "median_ticket", "repeat_accounts",
                              "repeat_pct"],
        "txns": 580, "median_ticket": 41.0, "repeat_months": 3, "repeat_accounts": 15,
        "repeat_pct": 31.2, "stacked_at": 2, "stacked_accounts": 9, "stacked_pct": 18.8,
        "merchant_named_dollars": 14_400, "merchant_named_pct": 60.0, "merchant_named_txns": 300,
        "merchants_n": 14,
        "merchants": [["PELOTON", 6, 12.5, 40, 4_800, "Affirm"], ["TARGET", 11, 22.9, 60, 3_100, "Klarna"],
                      ["ULTA", 4, 8.3, 9, 900, "Afterpay"], ["WAYFAIR", 3, 6.2, 8, 850, "Affirm"],
                      ["BESTBUY", 2, 4.2, 4, 700, "Zip"], ["NIKE", 2, 4.2, 4, 400, "Sezzle"]],
        "merchants_by_accounts": [["TARGET", 11, 22.9, 60, 3_100, "Klarna"]],
        "by_lens": [["all", "All accounts", 600, 60, 10.0, 100],
                    ["responders", "Responders", 120, 18, 15.0, 150],
                    ["mailed_nonresp", "Mailed non-responders", 300, 24, 8.0, 80],
                    ["business", "Business", 90, 6, 6.7, 67],
                    ["personal", "Personal", 500, 54, 10.8, 108],
                    ["new_accounts", "Opened last 12 mo", 80, 11, 13.8, 138],
                    ["ics", "ICS accounts", 70, 2, 2.9, 29],
                    ["mrpc", "MRPC accounts", 12, 3, 25.0, 250]],      # under the group floor
        "book_accounts": 600, "book_users": 60, "book_pct": 10.0,
        "users_vs_nonusers": [["BNPL users", 48, 812.5, 45.0, 1_200],
                              ["Non-users", 352, 640.0, 30.0, 4_100]],
        "users_vs_nonusers_base": "personal accounts",
    },
}
NEW = [(P.what_bnpl_pays_for, "What buy now, pay later pays for", "comp_bnpl_merchants"),
       (P.who_uses_bnpl, "Who uses buy now, pay later", "comp_bnpl_groups")]
ALL_BNPL = NEW + [(P.buy_now_pay_later, "Buy now, pay later", "comp_bnpl")]


@pytest.mark.parametrize("build, title, chart", NEW, ids=[n[1] for n in NEW])
def test_each_new_slide_declines_on_an_empty_book(build, title, chart):
    why = build(_Harness(), {}, "personal accounts")
    assert why and why.startswith(title) and "(" in why


@pytest.mark.parametrize("build, title, chart", ALL_BNPL, ids=[n[1] for n in ALL_BNPL])
def test_each_slide_draws_for_real_and_never_says_a_year(build, title, chart, tmp_path):
    h = _Harness()
    h["RIGHT_EDGE"] = 12.0
    h["chart"] = lambda name, fn, *a, **k: fn(*a, tmp_path / f"{name}.png", **k)
    assert build(h, json.loads(json.dumps(FULL)), "personal accounts") is None
    (head, sub), got = h.slides[-1]
    assert got == title
    words = " ".join([head, sub] + [" ".join(map(str, r)) for r in h.rails[-1]])
    assert "None" not in words and "a year" not in words, words
    assert (tmp_path / f"{chart}.png").exists()


def test_the_merchant_slide_says_what_its_numbers_show():
    h = _Harness()
    P.what_bnpl_pays_for(h, FULL, "personal accounts")
    (head, sub), _ = h.slides[-1]
    assert head == ("Peloton is the merchant most paid for through buy now, pay later: "
                    "$4.8K from 6 accounts in the window")
    assert sub.startswith("60% of BNPL dollars name the merchant")
    rail = {r[0]: r[1:] for r in h.rails[-1]}
    assert rail["Most accounts"] == ("Target", "11 accounts")
    rows = h.charts[-1]["rows"]
    assert [r[1] for r in rows] == [4_800, 3_100, 900, 850, 700, 400]      # by dollars
    # four lenders take a colour of their own; the fifth is "other"
    assert [r[3] for r in rows] == ["Affirm", "Klarna", "Afterpay", "Affirm", "Zip", "_other"]


def test_the_group_slide_compares_each_group_with_the_book():
    h = _Harness()
    P.who_uses_bnpl(h, FULL, "personal accounts")
    (head, sub), _ = h.slides[-1]
    assert head == ("Responders: 15.0% use buy now, pay later, against 10.0% of all "
                    "transacting accounts")
    assert "$812 an account a month" in sub and "$640" in sub
    labels = [r[0] for r in h.charts[-1]["rows"]]
    # the lens list decides the groups (no ICS row in this deck), the floor drops MRPC, "all" is the line
    assert not any("ICS" in x or "MRPC" in x or x.startswith("All") for x in labels)
    assert labels[0].startswith("Responders") and len(labels) == 5
    rail = {r[0]: r[1:] for r in h.rails[-1]}
    assert rail["Also a competitor"] == ("45%", "of users; 30% of non-users")


def test_the_group_slide_follows_the_ics_lens_list():
    t = dict(FULL, lenses=[["all", "All accounts", 600], ["ics", "ICS accounts", 70],
                           ["ics_dm", "ICS direct mail", 40]])
    why = P.who_uses_bnpl(_Harness(), t, "personal accounts")
    assert why and why.startswith("Who uses buy now, pay later")       # one ICS group: declined


def test_the_provider_slide_carries_repeat_use_and_stacking():
    h = _Harness()
    P.buy_now_pay_later(h, FULL, "personal accounts")
    rail = {r[0]: r[1:] for r in h.rails[-1]}
    assert rail["Repeat users"] == ("31%", "paid in 3+ months")
    assert rail["Two or more"] == ("9", "providers, 19% of users")
    blocks = h.charts[-1]["rows"]
    assert "$50 median payment" in blocks[0][2] and "40% paid in 3+ months" in blocks[0][2]


def test_the_slides_are_registered_after_buy_now_pay_later():
    for names in ([b.__name__ for b in txn_slides.BUILDERS], [b.__name__ for b in X.COMP_BUILDERS]):
        i = names.index("buy_now_pay_later")
        assert names[i + 1:i + 3] == ["what_bnpl_pays_for", "who_uses_bnpl"]
    reg = json.loads(SLIDES_JSON.read_text(encoding="utf-8"))
    comp = reg["_by_chapter"]["Competition"]
    i = comp.index("Buy now, pay later")
    for build, title, _ in NEW:
        assert X.TITLES[build.__name__] == title
        assert reg["slides"][title] == "keep"
    assert comp[i + 1:i + 3] == [t for _, t, _ in NEW]
