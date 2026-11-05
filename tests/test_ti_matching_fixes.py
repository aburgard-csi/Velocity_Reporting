"""Financial services and competition matching fixes (RPE, James 2026-11-05).

The readiness review put realistic descriptors through both matchers and found the town, the venue,
the refund and the client's own loan all read as institutions. Each rule below is pinned on the
descriptor that showed it.

    python -m pytest tests/test_ti_matching_fixes.py -q
"""
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti import dictionaries  # noqa: E402
from ti.transaction_intelligence import competition as comp  # noqa: E402
from ti.transaction_intelligence import financial_services as fs  # noqa: E402

CONFIG = dictionaries.folder()
CLIENT = {"SelfNames": ["FirstLight FCU"], "LocalCompetitors": ["First National Bank"]}


@pytest.fixture(scope="module")
def fin_spec():
    return fs.load_patterns(CONFIG, CLIENT)


@pytest.fixture(scope="module")
def comp_spec():
    return comp.load_config(CONFIG, CLIENT)


def _fin(spec, descriptor):
    got = fs.classify_strings(pd.Index([descriptor]), spec).loc[descriptor]
    return (None if pd.isna(got["category"]) else got["category"],
            None if pd.isna(got["provider"]) else got["provider"])


def _comp(spec, descriptor):
    got = comp._classify(pd.Index([descriptor]), spec).loc[descriptor, "category"]
    return None if pd.isna(got) else got


# ---------------------------------------------------------------------------
# the false positives from the review: nothing on either side
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("descriptor", [
    "MARCUS THEATRES MADISON WI",            # the two-word town strip took THEATRES with it
    "KOHLS #0123 SAN JOSE CA",               # shopping, not the store card
    "CAPITAL ONE ARENA WASHINGTON DC",
    "US BANK STADIUM MINNEAPOLIS MN",
    "PNC PARK PITTSBURGH PA",
    "CITI TRENDS 0456 MEMPHIS TN",
    "SHELL OIL 5744 LIVE OAK FL",            # Live Oak Bank, in the town
    "SHELL OIL HUNTINGTON BEACH CA",         # Huntington, in the town
    "GREAT LAKES BREWING CO CLEVELAND OH",   # Great Lakes student loans, a brewery
    "ALLIANT ENERGY PAYMENT",                # Alliant CU, a utility
    "IRS TREAS 310 TAX REF",                 # money coming back
    "TRAVELERS REST SC",                     # a town
    "FIDELITY BANK",                         # not Fidelity Investments
])
def test_a_false_positive_from_the_review_matches_nothing(fin_spec, comp_spec, descriptor):
    assert _fin(fin_spec, descriptor)[0] is None
    assert _comp(comp_spec, descriptor) is None


# ---------------------------------------------------------------------------
# what must still match, and the lenders, insurers and issuers the real packs missed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("descriptor,category,institution", [
    ("CHASE CREDIT CRD AUTOPAY", "Credit Cards", "Chase"),
    ("VENMO NEW YORK NY", "P2P Transfers", "Venmo"),
    ("SYNCB/AMAZON PMT", "Credit Cards", "Synchrony"),          # AMAZON no longer kills it
    ("COINBASE", "Crypto/Digital Assets", "Coinbase"),
    ("AFFIRM *PELOTON NEW YORK NY", "Buy Now Pay Later", "Affirm"),   # processor before the star
    ("WORLD FINANCE R 104 S MAIN ST GREENVILLE SCUS", "Personal Loans", "World Finance"),
    ("HEIGHTS FINANCE 101 N MAIN ST GREENVILLE SCUS", "Personal Loans", "Heights Finance"),
    ("TOWER LOAN OF M 406 LIBERTY PARK FLOWOOD MSUS", "Personal Loans", "Tower Loan"),
    ("PNM*SUN LOAN COMPANY", "Personal Loans", "Sun Loan"),
    ("OPC*REPUBLIC FINANCE", "Personal Loans", "Republic Finance"),
    ("360 SHEFFIELD FI TRANS PMT 60", "Auto Loans", "Sheffield Financial"),
    ("APPLECARD GSBANK", "Credit Cards", "Goldman Sachs / Marcus"),
    ("DISCOVER CAP", "Credit Cards", "Discover"),
    ("RH BROKERAGE DE 85 WILLOW RD MENLO PARK CAUS", "Investment/Brokerage", "Robinhood"),
    ("DEBIT LPL", "Investment/Brokerage", "LPL Financial"),
    ("ROCKET MORTGAGE LOAN", "Mortgage/HELOC", "Rocket Mortgage"),
])
def test_the_real_thing_still_matches_on_both_sides(fin_spec, comp_spec, descriptor, category,
                                                   institution):
    assert _fin(fin_spec, descriptor)[0] == category
    assert _comp(comp_spec, descriptor) == institution


@pytest.mark.parametrize("descriptor,line", [
    ("FRED LOYA INSURANCE", "Auto"),
    ("DAIRYLAND *INSURANCE", "Auto"),
    ("TESLA INSURANCE COMPANY", "Auto"),
    ("FIC*FOREMOST INSURANCE", "Home & property"),
    ("FOREMOST EPM PYMT", "Home & property"),
    ("CSAA INSURANCE G P PRS", "Auto & home"),
])
def test_the_missed_insurers_match_and_carry_their_line(fin_spec, descriptor, line):
    cat, provider = _fin(fin_spec, descriptor)
    assert cat == "Insurance"
    subtypes = fin_spec["categories"]["Insurance"]["subtypes"][line]
    assert provider in subtypes


def test_a_lone_store_name_is_shopping_and_a_store_card_payment_is_the_card(fin_spec):
    assert _fin(fin_spec, "KOHLS #0123 SAN JOSE CA")[0] is None
    assert _fin(fin_spec, "KOHLS PAYMENT")[0] == "Credit Cards"


def test_the_tax_payment_still_reads_as_tax(fin_spec):
    assert _fin(fin_spec, "IRS USATAXPYMT")[0] == "Tax & Accounting"
    assert _fin(fin_spec, "LIBERTY TAX SERVICE")[0] == "Tax & Accounting"   # off the FP list


def test_a_false_positive_cancels_only_the_match_it_overlaps(fin_spec):
    assert _fin(fin_spec, "AMAZON MKTPL SEATTLE WA")[0] is None
    assert _fin(fin_spec, "SYNCB/AMAZON PMT")[0] == "Credit Cards"


# ---------------------------------------------------------------------------
# the client's own names
# ---------------------------------------------------------------------------

def test_self_names_carry_every_depository_spelling(fin_spec, comp_spec):
    for spelling in ("FIRSTLIGHT FCU", "FIRSTLIGHT CU", "FIRSTLIGHT CREDIT UNION",
                     "FIRSTLIGHT FEDERAL CREDIT UNION"):
        assert spelling in fin_spec["self_names"]
        assert spelling in comp_spec["self_names"]
    assert fin_spec["self_names_configured"] == ["FIRSTLIGHT FCU"]


@pytest.mark.parametrize("descriptor", ["FIRSTLIGHT CU LOAN PMT", "FIRSTLIGHT FEDERAL CREDIT UNION",
                                        "TO LOAN 1234"])
def test_the_members_own_loan_is_never_leakage(fin_spec, comp_spec, descriptor):
    assert _fin(fin_spec, descriptor)[0] is None
    assert _comp(comp_spec, descriptor) is None


def test_a_generic_local_name_gets_no_short_family():
    v = comp.depository_variants("First National Bank")
    assert "FIRST BANK" not in v and "FIRST BK" not in v
    assert "FIRST NATIONAL BANK" in v
    assert "SCHOOLSFIRST CU" in comp.depository_variants("SchoolsFirst FCU")


def test_a_first_bank_loan_is_not_the_local_first_national_bank(comp_spec):
    assert _comp(comp_spec, "FIRST BANK LOAN PMT") is None


# ---------------------------------------------------------------------------
# the town
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("descriptor,town", [
    ("MARCUS THEATRES MADISON WI", ["MADISON", "WI"]),
    ("SHELL OIL HUNTINGTON BEACH CA", ["HUNTINGTON", "BEACH", "CA"]),
    ("VENMO NEW YORK NY", ["NEW", "YORK", "NY"]),
    # ST starts town names (ST LOUIS), so the street's ST goes with the town: address noise either way
    ("WORLD FINANCE 104 S MAIN ST GREENVILLE SCUS", ["ST", "GREENVILLE", "SCUS"]),
    ("PAYPAL SAN JOSE CA US", ["SAN", "JOSE", "CA", "US"]),
    ("PROGRESSIVE INS OH", ["OH"]),          # INS is never a town
    ("UPLIFT DESK CO", []),                  # CO is a corporate tail here, not Colorado
])
def test_city_block_takes_one_word_unless_the_pair_is_shaped_like_a_town(descriptor, town):
    keep = frozenset({"INS", "CO", "INC", "LLC"})
    toks = descriptor.split()
    assert [toks[i] for i in sorted(fs.city_block(toks, keep))] == town


# ---------------------------------------------------------------------------
# refunds, short data, a blank file
# ---------------------------------------------------------------------------

def _frame(descs, days_back=0, n_days=1):
    dates = pd.date_range(end=pd.Timestamp("2026-09-30") - pd.Timedelta(days=days_back),
                          periods=n_days, freq="D")
    rows = []
    for i, d in enumerate(descs):
        for dt in dates:
            rows.append({"transaction_date": dt, "primary_account_num": f"A{i % 7}",
                         "transaction_type": "ACH", "amount": 100.0, "merchant_name": d})
    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def test_refund_wording_is_counted_apart_and_never_leaks(fin_spec):
    df = _frame(["ROCKET MORTGAGE LOAN", "ROCKET MORTGAGE REFUND", "IRS TREAS 310 TAX REF"])
    out, _ = fs.compute(df, None, fin_spec, pd.Timestamp("2026-09-30"), None, lambda m: None)
    assert out["fin_inbound_excluded"]["txns"] == 2
    assert out["fin_leakage_dollars"] == 100


def test_a_file_with_no_descriptions_declines_both_sections(fin_spec, comp_spec):
    df = _frame([""] * 50 + ["ROCKET MORTGAGE LOAN"])
    warns = []
    fin, _ = fs.compute(df, None, fin_spec, pd.Timestamp("2026-09-30"), None, warns.append)
    assert "no description" in fin["fin_declined"]
    assert "fin_leakage_dollars" not in fin and "fin_by_category" not in fin
    cmp_, _ = comp.compute(df, None, comp_spec, None, pd.Timestamp("2026-09-30"), None, warns.append)
    assert "comp_declined" in cmp_ and "comp_competitor_dollars" not in cmp_
    assert len(warns) == 2


def test_growth_and_winback_need_six_months(comp_spec):
    short = _frame(["CHASE CREDIT CRD AUTOPAY", "DISCOVER E-PAYMENT", "CAPITAL ONE AUTOPAY"],
                   n_days=90)
    out, _ = comp.compute(short, None, comp_spec, None, pd.Timestamp("2026-09-30"), None,
                          lambda m: None)
    assert "comp_growth_note" in out
    assert out["comp_winback"] == [] and out["comp_depth_growth"] == []
    assert all(r[4] is None for r in out.get("comp_threat") or [])
    long = _frame(["CHASE CREDIT CRD AUTOPAY", "DISCOVER E-PAYMENT", "CAPITAL ONE AUTOPAY"],
                  n_days=200)
    out, _ = comp.compute(long, None, comp_spec, None, pd.Timestamp("2026-09-30"), None,
                          lambda m: None)
    assert "comp_growth_note" not in out
    assert all(r[4] is not None for r in out.get("comp_threat") or [])


def test_self_name_rows_are_counted_by_position_not_label(fin_spec):
    df = _frame(["FIRSTLIGHT CU TRANSFER", "ROCKET MORTGAGE LOAN"])
    df.index = np.arange(len(df)) * 10 + 5          # labels that are not 0..n-1
    out, _ = fs.compute(df, None, fin_spec, pd.Timestamp("2026-09-30"), None, lambda m: None)
    by_name = out["fin_self"]["by_name"]
    assert sum(r[2] for r in by_name) == out["fin_self"]["txns"] == 1


# ---------------------------------------------------------------------------
# the second pass: real descriptors the first version of these rules dropped (1100, 1075, 1798, 1776)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("descriptor,institution", [
    ("CITIBANK, N.A. 701 E 60TH ST NO SIOUX FALLS SDUS", "Citi"),           # 1100, $4.2M
    ("PNM*SANTANDER 1601 ELM STREET SUI8882224227 TXUS", "Santander"),      # 1100, $3.7M
    ("PNM SANTANDER", "Santander"),                                         # 1075: no star
    ("COINBASE 248 3RD ST OAKLAND CAUS", "Coinbase"),
    ("CHIME 77 MAIDEN LN-SIXTH SAN FRANCISCO CAUS", "Chime"),               # 1100, $1.8M
    ("COMENITY CAPITA 3075 LOYALTY CIR COLUMBUS OHUS", "Comenity / Bread"),
    ("SYNCB/JCPENNEY 4125 WINDWARD PLZA ALPHARETTA GAUS", "Synchrony"),
    ("SYNCB PHONE PAYM ALPHARETTA GA", "Synchrony"),
    ("ROBINHOOD DEBITS", "Robinhood"),
    ("TRUIST MORTG OLB MTGPMT", "Truist"),
    ("ONEMAIN FINANCI 601 NW 2ND ST EVANSVILLE INUS", "OneMain"),
    ("OPC*AVANT 222 N LA SALLE STE CHICAGO ILUS", "Avant"),
    ("AFFIRM.COM PAYM 650 CALIFORNIA ST. SAN FRANCISCO CAUS", "Affirm"),
    ("KLARNA TIKTOK SHOP", "Klarna"),
    ("KLARNA KLARNA", "Klarna"),
    ("VENMO *MARINA DIAZ", "Venmo"),
    ("CASH APP*MARINA 1955 BROADWAY OAKLAND CAUS", "Cash App"),
    ("ACM UPRISE UPSTART NETWORK FM", "Upstart"),
])
def test_real_payments_the_rules_must_keep(comp_spec, descriptor, institution):
    assert _comp(comp_spec, descriptor) == institution


@pytest.mark.parametrize("descriptor", [
    "BROWNSVILLE PUB 1425 ROBINHOOD DRIVBROWNSVILLE TXUS",   # a street, $778k at 1100
    "CVS/PHARMACY #0 02391--15607 CHASE SAN ANTONIO TXUS",
    "SQ *LA EATS AT SOFI STADI",
    "BMO STADIUM CONCESSION",
    "TRUIST PARK CON 755 BATTERY AVE SE ATLANTA GAUS",
    "AVANT DANCE 5017 SARATOGA BLVD CORPUS CHRIST TXUS",
    "ALLY OUTDOORS MIDLAND TXUS",
    "VANGUARD ANESTH 4818 EVERHART ROAD CORPUS CHRIST TXUS",
    "DFS ROCKPORT 1106 TEXAS 35 ROCKPORT TXUS",               # duty free, not Discover
    "FIDELITY EXPRESS M.O. SOLD",                              # money orders, not Fidelity
    "SQ *DISCOVER YOUR NORTHWE",                               # a card processor's shop
    "HOSP SANTANDER FCO I MADERO NO 600REYNOSA TAMPS MXMX",
    "CHIME BELL PLANTATION",
])
def test_names_inside_other_businesses_stay_unmatched(comp_spec, descriptor):
    assert _comp(comp_spec, descriptor) is None
