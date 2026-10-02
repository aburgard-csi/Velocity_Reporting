"""Sustained activity split by offer segment (Non-User / Threshold) — the opt-in test slide.

The split is computed in the SAME pass as the existing Sustained Respondent Activity bars
(sustained_split.by_mailing), so these tests pin three things: the segment rule, that the
split reconciles with the total the existing slide shows, and that the slide is opt-in.
"""
import os

import pytest

import sustained_split as SS
import sustained_split_slide as SSS

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ segment rule
@pytest.mark.parametrize("offer,resp,want", [
    ("NU", "NU 5+", "NU"),
    ("TH-10", "TH-10", "TH"),
    ("TH-25", "TH-15", "TH"),          # the OFFER decides, not the tier reached
    ("", "NU 5+", "NU"),               # blank offer falls back to the result
    ("", "TH-20", "TH"),
    ("XX", "NU 5+", "OTHER"),          # an unknown offer code is never guessed from the result
    ("", "", "OTHER"),
])
def test_segment_is_the_offer_sent(offer, resp, want):
    assert SS.segment(offer, resp) == want


# ------------------------------------------------------------------ hand-built cohort
MONTHS = ["Jan26", "Feb26", "Mar26", "Apr26", "May26", "Jun26"]
MET = {"NU 5+", "TH-10", "TH-15", "TH-20", "TH-25"}
GOAL = {"NU": 5, "TH-10": 10, "TH-15": 15, "TH-20": 20, "TH-25": 25}


def _row(offer, resp, sw):
    r = {"Feb26 Mail": offer, "Feb26 Resp": resp, "Jun26 Mail": offer, "Jun26 Resp": resp}
    r.update({f"{m} sw": sw for m in MONTHS})
    return r


def _g(r, f):
    return r.get(f, "")


def _sw(r, m):
    return r[f"{m} sw"]


def _ask(r, m):
    return GOAL.get(_g(r, f"{m} Mail"), 5)


def _split(rows, mailings=("Feb26", "Jun26"), act=MONTHS):
    return SS.by_mailing(rows, list(mailings), MONTHS, list(act), _g, _sw, _ask, MET)


def test_split_counts_and_shares():
    rows = ([_row("NU", "NU 5+", 6)] * 3 + [_row("NU", "NU 5+", 2)]          # NU 3/4 sustained
            + [_row("TH-10", "TH-10", 12)] + [_row("TH-20", "TH-20", 12)]      # TH 1/2 (20 > 12)
            + [_row("NU", "NU 1-4", 9)])                                       # not a responder
    feb = _split(rows)[0]
    assert feb["post"] == 3                     # Apr, May, Jun: mailing + 2 onward
    assert (feb["NU"]["n"], feb["NU"]["ok"], feb["NU"]["pct"]) == (4, 3, 75.0)
    assert (feb["TH"]["n"], feb["TH"]["ok"], feb["TH"]["pct"]) == (2, 1, 50.0)
    assert (feb["all"]["n"], feb["all"]["ok"]) == (6, 4)
    assert feb["OTHER"] == {"n": 0, "ok": 0, "pct": None}


def test_a_mailing_with_no_month_after_reads_100_for_every_segment():
    rows = [_row("NU", "NU 5+", 0), _row("TH-15", "TH-15", 0)]
    jun = _split(rows)[1]
    assert jun["post"] == 0
    assert jun["NU"]["pct"] == jun["TH"]["pct"] == jun["all"]["pct"] == 100.0


def test_an_incomplete_month_is_not_in_the_window():
    """Complete months only: Jun26 left out of the activity months shortens Feb's window."""
    rows = [_row("NU", "NU 5+", 6)]
    feb = _split(rows, act=MONTHS[:-1])[0]
    assert feb["post"] == 2


def test_total_rows_keep_the_existing_slide_shape():
    rows = [_row("NU", "NU 5+", 6), _row("TH-10", "TH-10", 1)]
    sp = _split(rows)
    assert SS.total_rows(sp) == [["Feb26", 2, 50.0, 3], ["Jun26", 2, 100.0, 0]]


def test_pooled_ignores_the_mailing_with_no_month_after():
    rows = [_row("NU", "NU 5+", 6), _row("NU", "NU 5+", 1)]
    p = SS.pooled(_split(rows), "NU")
    assert (p["n"], p["ok"], p["pct"]) == (2, 1, 50.0)


# ------------------------------------------------------------------ against metrics_gen
def test_split_reconciles_with_the_existing_slide(metrics):
    """NU + TH + other == the bar the existing slide draws, in responders and sustained."""
    sp = metrics["sustained_split"]
    assert SS.total_rows(sp) == metrics["sustained"]
    SSS.check_reconciles(sp)
    for e in sp:
        assert e["NU"]["n"] + e["TH"]["n"] + e["OTHER"]["n"] == e["all"]["n"]
    assert sum(e["NU"]["n"] for e in sp) and sum(e["TH"]["n"] for e in sp)


def test_a_broken_split_stops_the_build(metrics):
    sp = [dict(e) for e in metrics["sustained_split"]]
    sp[0] = dict(sp[0], NU=dict(sp[0]["NU"], n=sp[0]["NU"]["n"] + 1))
    with pytest.raises(SystemExit):
        SSS.check_reconciles(sp)


# ------------------------------------------------------------------ wording
def test_caption_states_the_left_out_mailing_and_flags_small_segments(metrics):
    sp = metrics["sustained_split"]
    cap = SSS.caption_text(sp)
    pend = [e for e in sp if not e["post"]]
    assert pend, "fixture should carry a mailing with no month after it"
    assert f"{pend[0]['m']} is left out" in cap
    assert "100% by definition" in cap
    # the fixture's NU segments are all under 30 responders
    assert any(s == "NU" for _, s, _ in SSS.small_segments(sp))


def test_slide_is_placed_after_the_existing_one_with_a_source_note(metrics, tmp_path):
    from pptx import Presentation
    import shapes as SH
    prs = Presentation(os.path.join(REPO, "templates", "ars_template.pptx"))
    n0 = len(prs.slides)
    ctx = {"odd_src": "ODD extract 999 Union Financial (Jul23-forward, pull 070126), Jun 2026 snapshot",
           "as_of_long": "June 2026", "assets": str(tmp_path)}
    s = SSS.add_sustained_split_slide(prs, metrics, ctx)
    titles = [SH.slide_title(x) for x in prs.slides]
    assert len(prs.slides) == n0 + 1
    i = titles.index(SSS.TITLE)
    assert titles[i - 1].startswith(SSS.ANCHOR)
    notes = s.notes_slide.notes_text_frame.text
    assert "Source: ODD extract 999 Union Financial" in notes
    assert "Small segments" in notes
    for e in metrics["sustained_split"]:
        assert f"{e['m']}: Non-User {e['NU']['ok']:,}/{e['NU']['n']:,}" in notes
    assert (tmp_path / "sustained_split.png").exists()


def test_the_slide_is_opt_in():
    src = open(os.path.join(REPO, "build", "ars_pipeline", "build_ars_gen.py"), encoding="utf-8").read()
    assert ('if os.environ.get("RPE_TEST_SLIDES") == "1" or '
            'os.environ.get("RPE_JAMES_SLIDES") == "1":\n    import sustained_split_slide') in src
