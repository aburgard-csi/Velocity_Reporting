"""ics_charts_gen — month axes.

The referral trend takes its months straight from the VIP dashboard, which we do
not control; the Monthly Detail charts take theirs from the ICS workbook. Both
used to render whatever string arrived — the per-account grid cut it down to a
bare month word, on a cohort series that routinely spans a year boundary. They
go through axis.month_ticks now, which renders one form or refuses.
"""
import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

import ics_charts_gen as CH
from periods import MONTH_ABBR, is_axis_label

MONTH_FORMS = ["Jul 25", "Jul 2025", "Jul25", "2025-07"]


def months_in(form, n):
    """`n` consecutive months written the way `form` writes July 2025."""
    out, y, mo = [], 2025, 7
    for _ in range(n):
        out.append({"Jul 25": f"{MONTH_ABBR[mo-1]} {y % 100:02d}",
                    "Jul 2025": f"{MONTH_ABBR[mo-1]} {y}",
                    "Jul25": f"{MONTH_ABBR[mo-1]}{y % 100:02d}",
                    "2025-07": f"{y}-{mo:02d}"}[form])
        mo += 1
        if mo > 12:
            mo, y = 1, y + 1
    return out


def ticks_from(call):
    """Render through a chart function and read back the ticks it set."""
    seen = {}
    real = CH.month_ticks

    def spy(ax, x, months, **kw):
        labels = real(ax, x, months, **kw)
        seen["ticks"] = [t.get_text() for t in ax.get_xticklabels()]
        return labels
    CH.month_ticks = spy
    try:
        call()
    finally:
        CH.month_ticks = real
        plt.close("all")
    return seen.get("ticks", [])


def detail(months, n=None):
    n = n or len(months)
    return {"monthly_detail": {
        "months": months,
        "accounts_opened": [10 + i for i in range(n)],
        "cumulative_accounts": [10 * (i + 1) for i in range(n)],
        "avg_balance": [1200.0 + 10 * i for i in range(n)],
        "interchange": [300.0 + i for i in range(n)],
        "nsf_od": [200.0 + i for i in range(n)],
        "other_fees": [50.0 + i for i in range(n)],
        "spread": [400.0 + i for i in range(n)],
    }}


# --- referral trend (VIP) -------------------------------------------------
@pytest.mark.parametrize("form", MONTH_FORMS)
def test_referral_trend_renders_one_form(form, tmp_path):
    m = months_in(form, 12)
    d = {"referrals": {"trend": {"months": m,
                                 "referrals": [5 + i for i in range(12)],
                                 "partial_last": True}}}
    ticks = ticks_from(lambda: CH.c_referral_trend(d, str(tmp_path / "t.png")))
    assert ticks and all(is_axis_label(t) for t in ticks), ticks
    assert ticks[0] == "Jul'25"


def test_a_vip_month_we_cannot_read_stops_the_build(tmp_path):
    d = {"referrals": {"trend": {"months": ["Jul 25", "Aug 25", "TBD"],
                                 "referrals": [1, 2, 3], "partial_last": False}}}
    with pytest.raises(ValueError) as e:
        CH.c_referral_trend(d, str(tmp_path / "t.png"))
    assert "referrals.trend.months[2]" in str(e.value)


# --- monthly detail (workbook) --------------------------------------------
@pytest.mark.parametrize("form", MONTH_FORMS)
def test_monthly_detail_renders_one_form(form, tmp_path):
    d = detail(months_in(form, 9))
    ticks = ticks_from(lambda: CH._monthly_bar(d, "interchange",
                                               str(tmp_path / "m.png"), False))
    assert ticks and all(is_axis_label(t) for t in ticks), ticks


def test_the_per_account_grid_keeps_the_year(tmp_path):
    """Cohorts run Nov'25 -> Jul'26 and the grid exists to show that the older
    ones have had longer to earn. It was rendering the month word alone."""
    d = detail(months_in("Jul 25", 9))
    ticks = ticks_from(lambda: CH.c_perref(d, str(tmp_path / "g.png")))
    assert ticks, "no ticks rendered"
    assert len({t[-2:] for t in ticks}) > 1, f"the year boundary is invisible: {ticks}"
    assert all(is_axis_label(t) for t in ticks), ticks


def test_axis_tokens_win_over_the_prose_label(tmp_path):
    """A sheet refreshed since the extractor started emitting them uses them."""
    d = detail(months_in("Jul 25", 9))
    d["monthly_detail"]["axis_months"] = months_in("Jul25", 9)
    assert CH._detail_months(d) == d["monthly_detail"]["axis_months"]


def test_a_sheet_written_before_axis_months_still_renders(tmp_path):
    """ICS sheets are pulled quarterly and live in Drive, so older ones are still
    in use. Their "%b %y" labels parse — the fallback reads the same fact."""
    d = detail(months_in("Jul 25", 9))
    assert "axis_months" not in d["monthly_detail"]
    ticks = ticks_from(lambda: CH.c_composition(d, str(tmp_path / "c.png")))
    assert ticks and all(is_axis_label(t) for t in ticks), ticks


def test_the_partial_month_legend_comes_from_the_axis(tmp_path):
    """The legend used to format the newest month a second, different way."""
    m = months_in("Jul 2025", 6)
    d = {"referrals": {"trend": {"months": m, "referrals": [1, 2, 3, 4, 5, 6],
                                 "partial_last": True}}}
    fig_labels = []
    real = CH.month_ticks

    def spy(ax, x, months, **kw):
        labels = real(ax, x, months, **kw)
        fig_labels.extend(labels)
        return labels
    CH.month_ticks = spy
    try:
        CH.c_referral_trend(d, str(tmp_path / "t.png"))
    finally:
        CH.month_ticks = real
        plt.close("all")
    assert fig_labels[-1] == "Dec'25"
