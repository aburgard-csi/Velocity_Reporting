"""MRPC Program to Date and Current Program Status (Aaron, 2026-10-02).

Both slides read the MRPC Enrollment Summary weekly. They replaced Card Portfolio and Key
Metrics, whose VIP figures — Active Enrollments 4,396 and Total Cards Billed 6,729 for Marine
FCU — did not reconcile with each other or with any current count. These pin what each figure
is, that the windows are complete months, that the retired VIP figures survive in the notes
with the reason, and that a client missing from the weekly is stated rather than zeroed.

Synthetic weekly; no client data.
"""
import datetime

import pytest
from pptx import Presentation

import mrpc_charts_gen as CH
import status_slides as SS


def month_rows(n, per=10, end=(2026, 8)):
    """n complete months of enrollments, oldest first, `per` Platinum + 2 Gold each."""
    y, m = end
    rows = []
    for _ in range(n):
        rows.append({"month": f"{y}-{m:02d}", "platinum": per, "gold": 2, "business": 0,
                     "primary": per + 1, "joint": 1, "new": 6, "existing": per - 4})
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return rows[::-1]


def weekly(**over):
    w = {
        "file": "260927_044839-MRPCEnrollmentSummary_v3_13.xlsx", "tab": "9999-Union Financial",
        "report_generated": "9/27/2026 5:46:09 AM",
        "open_with_debit": 40_000, "all_mrpc_accounts": 8_000, "take_rate_all": 0.2,
        "active_mrpc_accounts": 3_000, "take_rate_active": 0.075,
        "all_cardholders": 8_500, "active_cardholders": 3_100,
        "new_account_take": {"ptd_opened": 20_000, "ptd_enrolled": 2_000,
                             "cur_label": datetime.datetime(2026, 8, 1),
                             "cur_opened": 400, "cur_enrolled": 50},
        "totals": {"platinum": 7_000, "gold": 1_500, "business": 0, "primary": 8_000,
                   "joint": 500, "new": 3_500, "existing": 5_000, "employees": 200},
        "cardholders_active_buckets": {"1-90": 400, "91-180": 300, "180+": 2_400,
                                       "inactive": 5_400},
        "monthly": month_rows(14),
    }
    w.update(over)
    return w


def test_program_to_date_is_the_weeklys_cumulative_figures():
    f = SS.figures(weekly())
    assert (f["cardholders"], f["accounts"]) == (8_500, 8_000)
    assert f["take_rate_all"] == pytest.approx(20.0)
    assert f["tiers"] == [("Platinum", 7_000), ("Gold", 1_500)], "a zero tier is not drawn"
    assert (f["primary"], f["joint"], f["new"], f["existing"]) == (8_000, 500, 3_500, 5_000)


def test_current_status_is_the_weeklys_active_figures():
    f = SS.figures(weekly())
    assert (f["active_accounts"], f["active_cardholders"]) == (3_000, 3_100)
    assert f["still_active_pct"] == pytest.approx(3_100 / 8_500 * 100)
    assert [n for n, _v in f["buckets"]] == ["Active, 1–90 days", "Active, 91–180 days",
                                             "Active, over 180 days", "Inactive"]


def test_the_twelve_month_window_is_the_last_twelve_complete_months():
    f = SS.figures(weekly())
    assert f["window"] == ("2025-09", "2026-08") and f["window_n"] == 12
    assert f["enrolled_12"] == 12 * 12                   # 10 Platinum + 2 Gold a month


def test_a_months_take_rate_is_shown_only_once_that_month_has_ended():
    ok = SS.figures(weekly())
    assert (ok["cur_month"], ok["cur_enrolled"], ok["cur_opened"]) == ("2026-08", 50, 400)
    take = dict(weekly()["new_account_take"], cur_label=datetime.datetime(2026, 9, 1))
    assert SS.figures(weekly(new_account_take=take))["cur_month"] is None


def test_the_retired_vip_figures_are_kept_in_the_notes_with_the_reason():
    vip = {"key_metrics": {"active_enrollments": 4_396, "ptd_total": 6_330,
                           "enrollments_trailing_12": 1_293},
           "card_billing": {"total_accounts": 6_729, "monthly_billing": 98_870.0,
                            "by_fee": [{"label": "Platinum", "accounts": 5_549}]}}
    note = SS._vip_not_shown(vip)
    for figure in ("4,396", "6,330", "1,293", "6,729", "5,549", "$98,870"):
        assert figure in note
    assert note.startswith("NOT SHOWN, and why")


def test_both_slides_draw_and_a_missing_client_is_stated(tmp_path):
    prs = Presentation()
    prs.slide_width, prs.slide_height = 12192000, 6858000
    w = weekly()
    f = SS.figures(w)
    a, b, c, d = (prs.slides.add_slide(prs.slide_layouts[6]) for _ in range(4))
    n1 = SS.fill_program_to_date(a, f, w, str(tmp_path), "Union Financial")
    n2 = SS.fill_current_status(b, f, w, str(tmp_path), "Union Financial", {})
    assert "9999-Union Financial" in n1 and "Report Generated 9/27/2026" in n2
    text = " ".join(sh.text_frame.text for sh in b.shapes if sh.has_text_frame)
    assert "3,000" in text and "3,100" in text and "36%" in text
    SS.fill_program_to_date(c, None, None, str(tmp_path), "Union Financial")
    missing = " ".join(sh.text_frame.text for sh in c.shapes if sh.has_text_frame)
    assert "has no tab in the MRPC Enrollment Summary weekly" in missing
    assert "0" not in missing.replace("2026", ""), "a missing client is stated, never zeroed"


def test_the_charts_draw_at_their_slot_size(tmp_path):
    CH.chart_tier_donut(["Platinum", "Gold"], [7_000, 1_500], "8,500", "cardholders",
                        str(tmp_path / "t.png"), CH.DIMS["tiers"])
    CH.chart_status_bars(["Active, 1–90 days", "Inactive"], [400, 5_400],
                         str(tmp_path / "s.png"), CH.DIMS["status"])
    assert (tmp_path / "t.png").exists() and (tmp_path / "s.png").exists()
    for key in ("tiers", "status"):
        w_in, h_in = CH.SLOT_IN[key]
        px_w, px_h = CH.DIMS[key]
        assert px_w / px_h == pytest.approx(w_in / h_in, rel=0.01), "the canvas keeps the slot's shape"


def test_a_month_with_no_enrollments_still_counts_toward_the_twelve():
    """The weekly lists only months that had an enrollment. Capital Bank 1502's last twelve
    rows ran Jul'25-Aug'26 — fourteen months — and the tile said so."""
    rows = [r for r in month_rows(14) if r["month"] not in ("2026-01", "2026-03")]
    f = SS.figures(weekly(monthly=rows))
    assert f["window"] == ("2025-09", "2026-08") and f["window_n"] == 12
    assert f["enrolled_12"] == 10 * 12


def test_past_the_trial_is_active_cardholders_enrolled_more_than_90_days_ago():
    """The 2026-07-25 definition of an active enrollment: past the 90-day trial."""
    assert SS.figures(weekly())["past_trial"] == 300 + 2_400
