"""The helper bundle ported v5 slide builders draw through (build/ars_pipeline/ti/deck/helpers.py).

A builder written against v5's `h` must land on RPE's slide anatomy and pass the validator;
every slide it makes carries a Source note; and a builder that declines becomes a stated slide
under its own title, never a missing one.
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
def test_a_v5_builder_lands_on_rpe_slides_and_validates(tmp_path, contacts, lens_key):
    prs = Presentation(TEMPLATE)
    G.build(prs, dict(PACK), lens_key, [_chapter(tmp_path)])
    out = tmp_path / cut.deck_name(CLIENT, "2026.10", NAME, lens_key)
    G.save(prs, out)
    deck = Presentation(str(out))
    titles = [G._title(s) for s in deck.slides]
    assert "Card spend sits with three merchant groups" in titles
    assert "Who they pay" in titles, "a declined slide is stated, not dropped"
    declined = deck.slides[titles.index("Who they pay")]
    assert "Not shown for this client: no fin_top_providers" in " ".join(
        sh.text_frame.text for sh in declined.shapes if sh.has_text_frame)
    assert "Recurring payments on the card" in titles, "a builder that drew nothing is stated, not dropped"
    for s in list(deck.slides)[4:-2]:
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
