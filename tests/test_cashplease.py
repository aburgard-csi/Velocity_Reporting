"""CashPlease extractor and roster invariants.

Each test here is a defect that shipped or nearly did. They run against fixtures, not
against the live workbook: a test that needs this week's file from Bradford stops being
a test the week it does not arrive.
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "build"))
sys.path.insert(0, str(REPO / "build" / "cashplease_pipeline"))
sys.path.insert(0, str(REPO / "scripts"))

import cp_extract
import dda_counts
from build_month import read_cashplease_roster, read_roster


# ------------------------------------------------------------------ sheet names
@pytest.mark.parametrize("sheet,cid,expect_truncated", [
    # Exactly 30 chars AND cut mid-word — resolved by NAME_OVERRIDES.
    ("1539-Marine Federal Credit Uni", "1539", False),
    ("1803-First Source Federal Cred", "1803", False),
    # Exactly 30 chars but COMPLETE. Length cannot tell these from the ones above,
    # which is why every 30-char name needs an override entry rather than a rule.
    ("1711-Coosa Valley Credit Union", "1711", False),
    ("1526-Clark County Credit Union", "1526", False),
    # Short names are never suspect.
    ("1632-WesBanco Bank, Inc.", "1632", False),
])
def test_sheet_names_resolve_without_a_truncation_flag(sheet, cid, expect_truncated):
    got_cid, name, truncated = cp_extract.split_sheet_name(sheet)
    assert got_cid == cid
    assert truncated is expect_truncated
    assert not name.endswith(" ")


def test_an_unknown_30_char_name_is_flagged_not_guessed():
    """A new client at the cap must FAIL loudly, not ship a name cut mid-word."""
    cid, name, truncated = cp_extract.split_sheet_name("1999-Some Very Long Client Nam")
    assert cid == "1999"
    assert truncated is True, "a 30-char name with no override must be flagged"


# ------------------------------------------------------------------ the window
def _pack(monthly):
    return {"monthly": [{"loans": n} for n in monthly]}


def test_window_is_capped_at_twelve_months():
    loans, months = cp_extract.loans_in_window(_pack(list(range(24))), 12)
    assert months == 12
    assert loans == sum(range(12))          # newest first, so the first twelve


def test_a_short_history_reports_the_window_it_actually_has():
    """Not padded to 12 and not annualised — the deck names the real window."""
    loans, months = cp_extract.loans_in_window(_pack([5, 4, 3]), 12)
    assert (loans, months) == (12, 3)


def test_no_completed_month_is_zero_months_not_zero_loans():
    loans, months = cp_extract.loans_in_window(_pack([]), 12)
    assert months == 0


# ------------------------------------------------------------------ the DDA rate
def _metrics(monthly, dda_rec, gen="9/6/2026 6:35:45 AM"):
    pack = {
        "monthly": [{"loans": n} for n in monthly],
        "total": {"loans": 100, "principal": 50000.0, "interest": 3000.0},
        "status": {k: {"loans": 0, "principal": 0.0, "interest": 0.0}
                   for k in cp_extract.STATUSES},
        "charge_off_pct": 0.05,
        "report_generated": gen,
    }
    pack["status"]["Funded"] = {"loans": 10, "principal": 5000.0, "interest": 300.0}
    return cp_extract.client_metrics(pack, dda_rec)


def test_l8_is_never_carried_into_the_metrics():
    """`Percentage of Active Accounts with Loans` must not reach a slide.

    An account can take more than one CashPlease loan, so a loan count over an account
    base is not the share of accounts that borrowed, and the workbook does not state its
    denominator. It stays on the pack for audit and out of `metrics`.
    """
    m = _metrics([10] * 12, {"dda_accounts": 1000, "last_updated": "2026-09-04"})
    assert "pct_active_accounts_with_loans" not in m


def test_no_dda_count_means_no_rate_and_a_stated_reason():
    m = _metrics([10] * 12, None)
    assert m["loans_per_1k_dda"] is None
    assert m["dda_accounts"] is None, "absence must not become a zero"
    assert m["dda_missing_reason"]
    assert m["peer_comparable"] is False


def test_the_rate_is_loans_over_ddas_per_thousand():
    m = _metrics([10] * 12, {"dda_accounts": 1000, "last_updated": "2026-09-04"})
    assert m["window_loans"] == 120
    assert m["loans_per_1k_dda"] == pytest.approx(120.0)
    assert m["peer_comparable"] is True


def test_a_short_history_is_held_out_of_the_peer_comparison():
    """Otherwise the client loses the comparison on tenure, not performance."""
    m = _metrics([10] * 5, {"dda_accounts": 1000, "last_updated": "2026-09-04"})
    assert m["loans_per_1k_dda"] is not None, "the client still gets its own rate"
    assert m["window_months"] == 5
    assert m["peer_comparable"] is False


def test_a_stale_denominator_is_measured_not_ignored():
    m = _metrics([10] * 12, {"dda_accounts": 1000, "last_updated": "2026-04-09"})
    assert m["dda_stale_days"] > 45


# ------------------------------------------------------------------ DDA parsing
DDA_SAMPLE = """
Sent: Thursday, September 10, 2026 6:16:25 AM (UTC-06:00) Central Time (US & Canada)

Client Name                          DDA Accounts   Last Updated On
------------------------------------ -------------- ----------------
1002 - Republic Bank                 183679                09/04/2026
1044 - Trustmark                     305328                04/09/2026
1836 - Dieterich Bank                NULL
1840- FNB Kentucky                   NULL
1842-bankcda                         NULL
"""


def test_dda_rows_parse_including_the_odd_separators():
    pack = dda_counts.parse(DDA_SAMPLE)
    assert pack["sent"] == "2026-09-10"
    assert pack["clients"]["1002"]["dda_accounts"] == 183679
    assert pack["clients"]["1044"]["last_updated"] == "2026-04-09"


def test_a_null_count_is_not_a_zero():
    pack = dda_counts.parse(DDA_SAMPLE)
    assert "1836" not in pack["clients"], "NULL must not become a client with 0 DDAs"
    assert len(pack["null_counts"]) == 3, "'1840- x' and '1842-x' must parse too"


# ------------------------------------------------------------------ the roster
def test_the_cashplease_roster_reads_from_clients_md():
    rows = read_cashplease_roster()
    assert rows, "the roster table must not read as empty"
    assert all(r["client_id"] and r["client_name"] for r in rows)


def test_a_cancelled_client_is_kept_with_its_reason_not_dropped():
    """1658 Truliant's tab arrives every week with 8,296 loans on it."""
    rows = {r["client_id"]: r for r in read_cashplease_roster()}
    assert "1658" in rows, "a skipped client must stay visible, not vanish"
    assert rows["1658"]["build"] is False
    assert rows["1658"]["note"], "a skip row carries its reason"


def test_the_cashplease_table_does_not_leak_into_the_rpe_roster():
    """It sits after the ICS-only table, and `read_roster` classifies rows by the
    section above them — so every CashPlease client was briefly read as an ICS client,
    1658 included, which has no RPE program at all."""
    rpe_ids = {row[0] for row in read_roster()[0]}
    cp_only = {"1131", "1564", "1750", "1770", "1771"}
    assert not (rpe_ids & cp_only), "CashPlease-only clients must not be RPE clients"
    assert "1658" not in rpe_ids
