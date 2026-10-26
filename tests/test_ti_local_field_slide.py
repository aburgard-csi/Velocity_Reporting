# Ported from ARS v5 02-Scripts/tests/test_local_field_slide.py at a491b5c (James Gilmore); logic unchanged.
"""The local field slide (#245): every configured local competitor, seen
or not, and the review queue of bank-looking names nothing matched. The
19 August chapter carried a local tile; the 27 August rewrite dropped it.

    python -m pytest tests/test_local_field_slide.py -q
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import txn_compete as P, txn_slides         # noqa: E402
from ti.deck import txn_leakage as L                     # noqa: E402
from test_ti_hotspot_slides import _Harness                  # noqa: E402

LOCAL = {"configured": ["Sesloc Credit Union", "Golden 1", "Mechanics Bank",
                        "American Riviera Bank"],
         "accounts": 84, "pct": 0.3, "dollars": 93_166,
         "institutions": [["Golden 1", 62, 91_700, ["Transfer / other"]],
                          ["Sesloc Credit Union", 17, 810, []],
                          ["Mechanics Bank", 5, 656, []]]}
QUEUE = [["AMER RIVIERA BK", 40, 12_000], ["SLO CU LOAN PMT", 12, 4_000]]


def test_local_field_slide_names_seen_missing_and_the_queue():
    h = _Harness()
    t = {"comp_local": LOCAL, "comp_review_queue": QUEUE,
         "comp_review_queue_dollars": 16_000}
    assert P.the_local_field(h, t, "personal accounts") is None
    (head, sub), title = h.slides[-1]
    assert title == "The local field"
    assert "3 of 4" in head
    assert "American Riviera Bank" in sub          # configured, not seen
    rows = h.charts[-1]["rows"]
    assert [r[0] for r in rows] == ["Golden 1", "Sesloc Credit Union", "Mechanics Bank"]
    rail = "\n".join(" ".join(str(x) for x in item) for item in h.rails[-1])
    assert "AMER RIVIERA BK" in rail and "16" in rail


def test_local_field_slide_still_builds_when_nothing_was_seen():
    h = _Harness()
    t = {"comp_local": dict(LOCAL, accounts=0, pct=0.0, dollars=0, institutions=[]),
         "comp_review_queue": QUEUE, "comp_review_queue_dollars": 16_000}
    assert P.the_local_field(h, t, "personal accounts") is None
    (head, sub), _ = h.slides[-1]
    assert "0 of 4" in head
    assert not h.charts                            # nothing to draw, text carries it


def test_local_field_chart_draws_for_real(tmp_path):
    """The harness above records the chart call; this one lets it run, so
    the row shape handed to branch_bars is proven, not assumed."""
    h = _Harness()
    h["chart"] = lambda name, fn, *a, **k: fn(*a, tmp_path / f"{name}.png", **k)
    t = {"comp_local": LOCAL, "comp_review_queue": QUEUE,
         "comp_review_queue_dollars": 16_000}
    assert P.the_local_field(h, t, "personal accounts") is None
    assert (tmp_path / "comp_local_bars.png").exists()


def test_local_field_slide_declines_without_a_configured_list():
    h = _Harness()
    why = P.the_local_field(h, {"comp_local": {"configured": []}}, "personal accounts")
    assert why and "LocalCompetitors" in why
    assert not h.slides


def test_local_field_is_in_the_chapter_after_who_competes():
    names = [getattr(b, "__name__", "") for b in txn_slides.BUILDERS]
    assert names.index("the_local_field") == names.index("who_competes") + 1


def test_where_the_money_goes_names_card_rails_when_transfers_are_absent():
    h = _Harness()
    t = {"fin_by_category": [["Credit Cards", 10, 5.0, 40, 1000, 100, "leakage",
                              True, None, 100.0]],
         "fin_leaking_pct": 5.0, "fin_leakage_dollars": 1000,
         "fin_leakage_pct_of_transfer_dollars": None,
         "fin_addressable_accounts": 4, "fin_addressable_dollars": 400}
    L.where_the_money_goes(h, t, "personal accounts", lambda *a, **k: None)
    (_, sub), _ = h.slides[-1]
    assert "card rails only" in sub
    assert "None" not in sub
