# Ported from ARS v5 02-Scripts/tests/test_mailer_detail.py at a491b5c (James Gilmore); logic unchanged.
"""Per-offer segment behavior ('combo lines') -- the client-facing detail
James's legacy decks carried: for every offer, each mailed segment's
swipes and spend around the mail month."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import ti_v5_harness as harness  # noqa: E402
from ti.core.odd_transform import transform_odd  # noqa: E402
from ti_v5_harness import compute  # noqa: E402


def test_every_completed_offer_gets_segment_lines():
    enriched, _ = transform_odd(harness.make_odd("Jul26"))
    m, _w = compute(enriched, harness.CONFIG)
    detail = m["mailer_detail"]
    assert detail, "no offers produced detail"
    completed_tags = {str(r[0]) for r in m["campaign_rates"]}
    assert set(detail) <= completed_tags | set(detail)  # only real offers
    for tag, d in detail.items():
        assert d["segments"], tag
        assert 0 in d["offsets"]                       # mail month present
        for s in d["segments"]:
            assert len(d["swipes"][s]) == len(d["offsets"])
            assert len(d["spend"][s]) == len(d["offsets"])
            assert d["counts"][s] >= 25


def test_per_offer_window_runs_the_full_horizon():
    """James (2026-08-24, repeated ask): each individual mailing's combo
    chart must run the LONG window like the pooled trajectory (-12..+36),
    clipped to the months the file actually has -- not a fixed +-6."""
    from ti.monthly_analysis import mailer_detail
    assert mailer_detail.WINDOW_BEFORE == 12
    assert mailer_detail.WINDOW_AFTER == 36
    enriched, _ = transform_odd(harness.make_odd("Jul26"))
    m, _w = compute(enriched, harness.CONFIG)
    md = m["mailer_detail"]
    # the oldest completed offer has >6 months of post-mail file history:
    # its offsets must extend beyond the old +6 crop
    oldest = md[list(md)[0]]
    assert max(oldest["offsets"]) > 6, oldest["offsets"]
    # and never beyond the file: offsets stay within actual months
    assert max(oldest["offsets"]) <= 36


def test_combo_lines_thin_ticks_on_the_long_window():
    """49 offsets at slot width is unreadable tick soup: past ~20 offsets
    the axis labels every 6th month (0 always kept)."""
    import matplotlib.pyplot as plt
    from ti.deck import charts
    detail = {"offsets": list(range(-12, 37)),
              "segments": ["a", "b"],
              "counts": {"a": 100, "b": 80},
              "swipes": {"a": [5.0] * 49, "b": [4.0] * 49},
              "spend": {"a": [100.0] * 49, "b": [90.0] * 49}}
    fig, meta = charts._combo_fig(detail)
    try:
        assert 0 in meta["ticks"]
        assert len(meta["ticks"]) <= 12
        assert all(t % 6 == 0 for t in meta["ticks"])
    finally:
        plt.close(fig)


def test_each_offer_gets_per_segment_responder_series():
    """James (corrected): per CHALLENGE SEGMENT within each mailer --
    that segment's responders vs that segment's own non-responders."""
    enriched, _ = transform_odd(harness.make_odd("Jul26"))
    m, _w = compute(enriched, harness.CONFIG)
    rd = m["mailer_resp_detail"]
    assert rd, "no per-segment responder detail produced"
    for tag, d in rd.items():
        assert d["segments"], tag
        for seg in d["segments"]:
            sd = d["data"][seg]
            assert sd["counts"]["Responders"] >= 10
            assert sd["counts"]["Non-responders"] >= 10
            for key in ("swipes", "spend"):
                for grp in ("Responders", "Non-responders"):
                    assert len(sd[key][grp]) == len(d["offsets"])


def test_seg_resp_grid_renders_two_rows_per_segment(tmp_path):
    from ti.deck import charts
    import matplotlib.pyplot as plt
    det = {"offsets": [-2, -1, 0, 1],
           "segments": ["NU 5+", "TH-10"],
           "data": {seg: {"counts": {"Responders": 30, "Non-responders": 200},
                          "swipes": {"Responders": [5, 5, 6, 8],
                                     "Non-responders": [5, 5, 5, 5]},
                          "spend": {"Responders": [100, 102, 110, 130],
                                    "Non-responders": [99, 98, 97, 96]}}
                    for seg in ("NU 5+", "TH-10")}}
    fig, meta = charts._seg_resp_fig(det)
    plt.close(fig)
    assert meta["panels"] == 4
    charts.segment_resp_grid(det, tmp_path / "g.png")
    assert (tmp_path / "g.png").exists()


@__import__("pytest").mark.skip(reason="v5's deck harness (test_deck_layout) is not ported; "
                                 "the offer-detail slides are covered by test_ti_campaign_chapter.py")
def test_responder_slides_render_per_offer():
    from test_ti_deck_layout import _build_fixture, _new_slide_metrics
    mm = _new_slide_metrics()
    det = {"offsets": [-2, -1, 0, 1, 2],
           "segments": ["TH-10"],
           "data": {"TH-10": {
               "counts": {"Responders": 60, "Non-responders": 440},
               "swipes": {"Responders": [10, 10, 11, 14, 15],
                          "Non-responders": [9, 9, 9, 9, 9]},
               "spend": {"Responders": [200, 205, 210, 260, 270],
                         "Non-responders": [180, 181, 180, 179, 178]}}}}
    mm["mailer_detail"] = {"May25": {
        "offsets": [-2, -1, 0, 1, 2], "segments": ["1-5"],
        "counts": {"1-5": 30}, "swipes": {"1-5": [1] * 5},
        "spend": {"1-5": [9] * 5}}}
    mm["mailer_resp_detail"] = {"May25": det}
    d = _build_fixture(mm)
    text = d.storyboard.read_text(encoding="utf-8")
    assert "May25: responders versus their segment" in text
