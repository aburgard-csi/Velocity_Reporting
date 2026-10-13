"""Debit spend per cardholder, cards in use and per eligible account (Aaron, 2026-10-12).

Brooks Bank's Spend YTD YoY tile read n/a because its workbook series starts in Feb 2025. The
like-for-like window compares the months of this year to date that the prior year also carries
(Feb-Sep against Feb-Sep there; Jan-Sep against Jan-Sep for a full series), and no window at all
when the series does not reach a year back. The wording follows the +/-2% band.
"""
import csv
import io
import os
import sys
import zipfile

import pytest

import spend_trend as ST

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rows(start, end, spend=20.0, cards=13500, step=0.5):
    """Key Trends rows from 'Mon YYYY' start to end inclusive, spend rising by `step` a month."""
    y, m = int(start[-4:]), ST.MONTH_ABBR.index(start[:3]) + 1
    ey, em = int(end[-4:]), ST.MONTH_ABBR.index(end[:3]) + 1
    out, k = [], 0
    while (y, m) <= (ey, em):
        out.append((f"{ST.MONTH_ABBR[m - 1]} {y}", spend + step * k, cards))
        k += 1
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return out


# ------------------------------------------------------------------ windows
def test_a_series_starting_in_february_compares_february_onward():
    w = ST.windows([r[0] for r in rows("Feb 2025", "Sep 2026")])
    assert w["prior_name"] == "Feb–Sep 25" and w["current_name"] == "Feb–Sep 26"
    assert w["prior"][0] == "Feb 2025" and w["prior"][-1] == "Sep 2025" and w["months"] == 8


def test_a_full_series_compares_year_to_date():
    w = ST.windows([r[0] for r in rows("Nov 2023", "Sep 2026")])
    assert w["prior_name"] == "Jan–Sep 25" and w["current_name"] == "Jan–Sep 26" and w["months"] == 9


def test_a_january_latest_month_is_a_single_month_window():
    w = ST.windows([r[0] for r in rows("Mar 2025", "Jan 2027")])
    assert w["prior_name"] == "Jan 26" and w["current_name"] == "Jan 27" and w["months"] == 1


def test_a_series_too_short_for_a_year_back_has_no_window():
    assert ST.windows([r[0] for r in rows("Nov 2025", "Sep 2026")]) is None
    assert ST.windows([r[0] for r in rows("Oct 2025", "Sep 2026")]) is None   # Oct 25 is after Sep
    assert ST.windows([]) is None


def test_a_gap_inside_a_window_means_no_window():
    labels = [r[0] for r in rows("Feb 2025", "Sep 2026") if r[0] != "May 2025"]
    assert ST.windows(labels) is None


# ------------------------------------------------------------------ figures and words
def test_per_card_and_the_comparison_use_the_window_averages():
    data = rows("Feb 2025", "Sep 2026", spend=20.0, cards=10000, step=0.0)
    data = [(m, (22.0 if m.endswith("2026") else 20.0), c) for m, _, c in data]
    out = ST.compute(data)
    assert out["per_card"][0][3] == pytest.approx(2000.0)
    c = out["per_card_cmp"]
    assert c["prior"] == pytest.approx(2000.0) and c["current"] == pytest.approx(2200.0) and c["pct"] == pytest.approx(10.0)
    assert ST.movement("Spend per cardholder", c) == "Spend per cardholder rose from $2,000 to $2,200 a month (+10.0%)."


@pytest.mark.parametrize("pct,phrase", [
    (1.9, "was almost flat"), (-1.9, "was almost flat"), (2.1, "rose from"), (-2.1, "did not have an impact")])
def test_movement_follows_the_two_percent_band(pct, phrase):
    cmp = {"prior": 1000.0, "current": 1000.0 * (1 + pct / 100), "pct": pct}
    assert phrase in ST.movement("Spend per cardholder", cmp)


def test_no_window_is_stated_not_substituted():
    out = ST.compute(rows("Nov 2025", "Sep 2026"))
    assert out["windows"] is None and out["per_card_cmp"] is None
    assert "no like-for-like comparison" in ST.movement("Spend per cardholder", None)


# ------------------------------------------------------------------ the ODD
def _odd_zip(tmp_path):
    hdr = ["Acct ID", "Business?", "Debit?", "Date Opened", "Date Closed", "Sep26 Elig",
           "Jan26 Sig $", "Jan26 PIN $", "Feb26 Sig $", "Feb26 PIN $", "Mar26 Sig $", "Mar26 PIN $"]
    data = [
        ["a", "No", "Yes", "01/15/2020", "", "Yes", "100", "50", "0", "0", "200", "0"],     # eligible card, idle in Feb
        ["b", "No", "Yes", "01/15/2020", "", "Yes", "300", "0", "300", "0", "300", "0"],    # eligible card, steady
        ["c", "No", "Yes", "02/10/2026", "", "Yes", "0", "0", "80", "0", "80", "0"],        # eligible, opened in Feb
        ["d", "No", "No", "01/15/2020", "", "Yes", "0", "0", "0", "0", "0", "0"],           # eligible, no card
        ["e", "No", "Yes", "01/15/2020", "02/20/2026", "No", "500", "0", "500", "0", "0", "0"],  # not eligible, closed Feb
        ["f", "Yes", "Yes", "01/15/2020", "", "No", "900", "0", "900", "0", "900", "0"],    # business: never counted
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["1", "Test - OD Data Dump"]); w.writerow([]); w.writerow(hdr); w.writerows(data)
    p = tmp_path / "9999_ODDD.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("9999-test-ODD.csv", buf.getvalue())
    return str(p)


def test_from_odd_counts_cards_in_use_and_eligible_accounts_open_in_the_month(tmp_path):
    o = ST.from_odd(_odd_zip(tmp_path), through="Mar 2026")
    assert o["months"] == ["Jan 2026", "Feb 2026", "Mar 2026"]
    assert o["cards_in_use"] == [3, 3, 3]                      # Jan: a, b, e; Feb: b, c, e; Mar: a, b, c
    assert o["spend_per_card_in_use"][0] == pytest.approx((150 + 300 + 500) / 3)
    assert o["eligible_open"] == [3, 4, 4]                     # c opens in Feb; d is open with no card
    assert o["spend_per_eligible"][1] == pytest.approx((0 + 300 + 80 + 0) / 4)
    assert o["eligible_active_share"][1] == pytest.approx(50.0)
    assert o["cards_snapshot"] == 4 and o["eligible_snapshot"] == 4   # business account f is outside both


def test_from_odd_is_capped_at_the_complete_month(tmp_path):
    o = ST.from_odd(_odd_zip(tmp_path), through="Feb 2026")
    assert o["months"] == ["Jan 2026", "Feb 2026"]


# ------------------------------------------------------------------ the slides
def test_the_slides_go_after_swipes_and_spend_with_their_notes(tmp_path):
    from pptx import Presentation
    import spend_trend_slides as SL
    prs = Presentation(os.path.join(ROOT, "templates", "ars_template.pptx"))
    n0 = len(prs.slides)
    data = rows("Feb 2025", "Sep 2026", spend=20.0, cards=13500, step=0.3)
    st = ST.compute(data, _odd_zip(tmp_path), through="Sep 2026")
    made = SL.add_spend_trend_slides(prs, st, {"wb_src": "wb.xlsx", "odd_src": "odd.zip",
                                               "as_of_long": "September 2026", "assets": str(tmp_path)})
    titles = [next(sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()) for s in prs.slides]
    i = next(k for k, t in enumerate(titles) if t.startswith(SL.ANCHOR))
    assert titles[i + 1] == SL.TITLE_1 and titles[i + 2] == SL.TITLE_2 and len(prs.slides) == n0 + 2
    for s in made:
        notes = s.notes_slide.notes_text_frame.text
        assert "Source:" in notes and "RPE_SPEND_SLIDES" in notes
    assert "Feb–Sep 25" in made[0].notes_slide.notes_text_frame.text
    assert "today's book" in made[1].notes_slide.notes_text_frame.text    # the ODD caveat is stated
