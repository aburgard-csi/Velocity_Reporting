"""The helper bundle ported v5 slide builders draw through (build/ars_pipeline/ti/deck/helpers.py).

A builder written against v5's `h` must land on RPE's slide anatomy and pass the validator;
every slide it makes carries a Source note; a builder that declines is hidden from the client's
deck and listed, title and reason, in the build log and the pack's `hidden_declined` (James signed
off overriding "never drop slides automatically" for the TI cut, Sheila's 1798 slide review,
2026-10-30: 22 "Not shown for this client" pages); a chapter with every slide declined loses its
divider and agenda row; and a chart that fails to draw fails the build instead of leaving a gap.
"""
import os
import sys

import pytest
from pptx import Presentation

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("build", "build/ars_pipeline", "validation"):
    sys.path.insert(0, os.path.join(REPO, p))

import build_ti_gen as G  # noqa: E402
import validate_deck as vd  # noqa: E402
from test_ti_shell import CLIENT, NAME, PACK, TEMPLATE, contacts  # noqa: E402,F401
from ti import cut  # noqa: E402
from ti.deck.helpers import Deck  # noqa: E402


def where_the_money_goes(h, t, base):
    """A v5-shaped builder: headline pair, chart left of a rail, table under it."""
    s, top = h["slide"](("Card spend sits with three merchant groups", f"{base}, last 12 months"),
                        "Where the money goes")
    path = h["chart"]("money", h["charts"].rate_bars,
                      [[g, n, None, r] for g, n, r in t["rows"]])
    right = h["rail"](s, [("Accounts", f"{t['n']:,}", base), ("Top group", t["rows"][0][0], None)], top=top)
    if path:
        h["chart_left"](s, path, top, right, max_h=3.2)
    h["table"](s, [["Group", "Accounts", "Rate"]] + [[g, f"{n:,}", f"{r:.1f}%"] for g, n, r in t["rows"]],
               h["MARGIN_L"], top + 3.4, 6.0, col_widths=[3.0, 1.5, 1.5])
    return None


def who_they_pay(h, t, base):
    return "no fin_top_providers"


def recurring_on_the_card(h, t, base):
    """v5 declines some slides by returning None without drawing (1776's two card slides)."""
    return None


def _chapter(tmp_path):
    t = {"n": 12345, "rows": [["Groceries", 4000, 38.2], ["Fuel", 3000, 21.4], ["Dining", 2000, 12.9]]}

    def build(ctx):
        d = Deck(ctx, "the ODD extract and the transaction files", tmp_path / "charts")
        return d.run([where_the_money_goes, who_they_pay, recurring_on_the_card],
                     {"who_they_pay": "Who they pay",
                      "recurring_on_the_card": "Recurring payments on the card"}, t, "eligible accounts")

    return cut.Chapter("TI_TXN", "Transaction Intelligence", "Spend · Merchants · Channels",
                       "Where card spend goes", lambda pack, ln: [], build, lambda ctx: {})


@pytest.mark.parametrize("lens_key", ["ars", "ics"])
def test_a_v5_builder_lands_on_rpe_slides_and_validates(tmp_path, contacts, lens_key, capsys):
    prs = Presentation(TEMPLATE)
    pack = dict(PACK)
    G.build(prs, pack, lens_key, [_chapter(tmp_path)], art_dir=str(tmp_path / "art"))
    out = tmp_path / cut.deck_name(CLIENT, "2026.10", NAME, lens_key)
    G.save(prs, out)
    deck = Presentation(str(out))
    titles = [G._title(s) for s in deck.slides]
    assert "Card spend sits with three merchant groups" in titles
    # a declined slide is hidden for this client, never a "Not shown for this client" page
    assert "Who they pay" not in titles and "Recurring payments on the card" not in titles
    assert not any("Not shown for this client" in sh.text_frame.text
                   for s in deck.slides for sh in s.shapes if sh.has_text_frame)
    # ...and never silent: the log and the pack name each one with its reason
    log = capsys.readouterr().out
    assert "Who they pay: no fin_top_providers" in log
    assert "Recurring payments on the card" in log
    hidden = pack["hidden_declined"][lens_key]
    assert {(h["title"], h["reason"]) for h in hidden} >= {("Who they pay", "no fin_top_providers")}
    assert {h["title"] for h in hidden} == {"Who they pay", "Recurring payments on the card"}
    import json
    assert json.loads((tmp_path / "art" / "hidden_declined.json").read_text(encoding="utf-8"))[lens_key] == hidden
    for s in list(deck.slides)[3:-3]:
        assert "Source:" in s.notes_slide.notes_text_frame.text and CLIENT in s.notes_slide.notes_text_frame.text
    fails = [f for f in vd.run(str(out)) if f[0] == "FAIL"]
    assert fails == [], fails


def test_a_count_of_one_takes_the_singular_for_months_too():
    """"1 months" shipped on the economics headline (1075, 2026-10-28); the guard knew accounts and the
    like but not months."""
    from pptx import Presentation
    from pptx.util import Inches
    from ti.deck.helpers import Deck
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1)).text_frame.text = \
        "The program has earned $0 of program profit in 1 months, 1 mailings and 12 months"

    class Fake:
        slides = [s]
    Deck._singulars(Fake())
    assert s.shapes[0].text_frame.text == "The program has earned $0 of program profit in 1 month, 1 mailing and 12 months"


def _all_declined_chapter(tmp_path):
    def build(ctx):
        d = Deck(ctx, "the client's deposits extract", tmp_path / "charts_dep")
        return d.run([who_they_pay], {"who_they_pay": "Deposits by month"}, {}, "accounts")

    return cut.Chapter("TI_DEP", "Deposits", "Inflow · Outflow", "Where deposits go",
                       lambda pack, ln: [], build, lambda ctx: {})


def test_a_chapter_with_every_slide_declined_loses_its_divider_and_agenda_row(tmp_path, contacts):
    prs = Presentation(TEMPLATE)
    pack = dict(PACK)
    G.build(prs, pack, "ars", [_chapter(tmp_path), _all_declined_chapter(tmp_path)])
    out = tmp_path / cut.deck_name(CLIENT, "2026.10", NAME, "ars")
    G.save(prs, out)
    deck = Presentation(str(out))
    titles = [G._title(s) for s in deck.slides]
    assert "Deposits" not in titles, "no divider for an empty chapter"
    agenda = " ".join(sh.text_frame.text for sh in deck.slides[1].shapes if sh.has_text_frame)
    assert "Transaction Intelligence" in agenda and "Deposits" not in agenda
    assert ("Deposits", "Deposits by month") in {(h["chapter"], h["title"]) for h in pack["hidden_declined"]["ars"]}
    fails = [f for f in vd.run(str(out)) if f[0] == "FAIL"]
    assert fails == [], fails


def test_a_chart_that_fails_to_draw_fails_the_build(tmp_path, contacts, capsys):
    """Deck.chart swallowed a chart's exception into `declines`, which nothing read: five charts went
    missing from 1798's deck and it still validated 0 FAIL (Sheila's slide review, 2026-10-30)."""
    from ti.deck import helpers as H

    def broken(out):
        raise ValueError("bad axis")

    def builder(h, t, base):
        s, top = h["slide"](("A slide with a chart", base), "Where the money goes")
        h["chart"]("broken", broken)
        h["text"](s, 0.6, top, 6, 1, "Body")
        return None

    def build(ctx):
        return Deck(ctx, "the ODD extract", tmp_path / "charts").run([builder], {}, {}, "accounts")

    ch = cut.Chapter("TI_TXN", "Transaction Intelligence", "Spend", "Where card spend goes",
                     lambda pack, ln: [], build, lambda ctx: {})
    with pytest.raises(H.ChartFailed, match=r"1 chart\(s\) failed to draw.*broken \(ValueError: bad axis\)"):
        G.build(Presentation(TEMPLATE), dict(PACK), "ars", [ch])
    assert "chart broken failed to draw: ValueError: bad axis" in capsys.readouterr().out
