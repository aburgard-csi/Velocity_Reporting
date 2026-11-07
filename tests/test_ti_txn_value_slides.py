# Ported from ARS v5 02-Scripts/tests/test_txn_value_slides.py at a491b5c (James Gilmore); logic unchanged; month labels expected in
# RPE's MMM'YY house format.
"""The six routing-mix and relationship-shape slides (#258, group 4): each
declines with a reason on an empty book, registers under its catalogue id
on a full one, draws its chart for real, and sits in BUILDERS after the
card-tenure slide.

    python -m pytest tests/test_txn_value_slides.py -q
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import txn_slides, txn_value as V                     # noqa: E402
from test_ti_hotspot_slides import _Harness                            # noqa: E402

FULL = {
    "ic_routing_available": True, "ic_rails": ["PIN", "SIG"],
    "ic_card_accounts": 1_240, "ic_card_spend": 1_860_000,
    "ic_sig_share_pct": 58.3, "ic_sig_share_of_swipes_pct": 49.1,
    "ic_pin_ticket": 61.2, "ic_sig_ticket": 38.7,
    "ic_monthly": [["2025-09", 60_000, 80_000, 57.1, 900], ["2025-10", 62_000, 84_000, 57.5, 920],
                   ["2025-11", 61_000, 88_000, 59.1, 940], ["2025-12", 70_000, 100_000, 58.8, 1_010],
                   ["2026-01", 58_000, 90_000, 60.8, 960], ["2026-02", 55_000, 92_000, 62.6, 970]],
    "ic_sig_shift_pp": 3.0, "ic_sig_direction": "improving",
    "ic_account_mix": [["0-20%", 210, 16.9, 240_000], ["20-40%", 180, 14.5, 300_000],
                       ["40-60%", 300, 24.2, 480_000], ["60-80%", 330, 26.6, 520_000],
                       ["80-100%", 220, 17.7, 320_000]],
    "ic_pin_heavy_n": 210, "ic_pin_heavy_pct": 16.9, "ic_pin_heavy_spend": 240_000,
    "ic_pin_heavy_spend_pct": 12.9, "ic_pin_heavy_spend_per_acct_mo": 190,
    "ic_by_merchant": [["WALMART", 4_100, 210_000, 90_000, 30.0],
                       ["COSTCO", 1_900, 150_000, 40_000, 21.1],
                       ["AMAZON", 6_200, 0, 180_000, 100.0],
                       ["SHELL", 2_400, 60_000, 50_000, 45.5],
                       ["TARGET", 1_800, 40_000, 60_000, 60.0]],
    "ic_by_lens": [["responders", "Responders", 400, 63.0, 700_000],
                   ["mailed_nonresp", "Mailed, no response", 500, 55.0, 800_000]],
    "ic_by_age": [["18-25", 90, 71.0, 80_000], ["26-35", 240, 66.0, 380_000],
                  ["36-45", 300, 60.0, 520_000], ["46-55", 280, 55.0, 460_000],
                  ["56-64", 200, 50.0, 280_000], ["65+", 130, 44.0, 140_000]],
    "ic_by_product": [["Free Checking", 700, 62.0, 1_100_000], ["Premier Checking", 300, 58.0, 500_000],
                      ["Student Checking", 120, 38.0, 90_000]],
    "ic_pin_default_products": [["Student Checking", 120, 38.0, 90_000]],
    "rel_single_rail": False,
    "rel_channel_pairs": {"rows": ["card", "ACH", "CHK", "P2P"], "cols": ["card", "ACH", "CHK", "P2P"],
                          "cells": [[None, 48.0, 12.0, 30.0], [70.0, None, 20.0, 35.0],
                                    [80.0, 90.0, None, 25.0], [85.0, 60.0, 10.0, None]]},
    "rel_next_channel": [["card", 610, "ACH", 48.0], ["ACH", 140, "card", 70.0],
                         ["CHK", 10, "ACH", 90.0], ["P2P", 0, "card", 85.0]],
    "rel_depth_by_breadth": [[1, 760, 9.4, 610], [2, 380, 21.0, 1_450],
                             [3, 90, 34.5, 2_600], [4, 10, 41.0, 3_100]],
}
BASE = "transacting personal accounts"

SLIDES = [
    (V.pin_or_signature, "PIN or signature", "ic_monthly"),
    (V.who_routes_pin, "Who routes PIN", "ic_by_group"),
    # the merchants' PIN and signature dollars are this slide's chart since Sheila's 1798 slide
    # review (2026-10-30, group D: four routing slides to two); the account mix is its fallback
    (V.pin_heavy_accounts, "PIN-heavy accounts", "ic_pin_merchants"),
    (V.where_pin_gets_pressed, "Where PIN gets pressed", "ic_by_merchant"),
    (V.channels_used_together, "Channels used together", "rel_channel_pairs"),
    (V.what_a_second_channel_is_worth, "What a second channel is worth", "rel_depth"),
]


def _h():
    h = _Harness()
    h["RIGHT_EDGE"] = 12.0
    return h


@pytest.mark.parametrize("fn,title,_chart", SLIDES)
def test_declines_with_a_reason_on_an_empty_book(fn, title, _chart):
    h = _h()
    why = fn(h, {}, BASE)
    assert isinstance(why, str) and why.startswith(title) and "(" in why
    assert h.slides == []


@pytest.mark.parametrize("fn,title,chart", SLIDES)
def test_registers_its_literal_id_and_names_the_number(fn, title, chart):
    h = _h()
    assert fn(h, FULL, BASE) is None
    (headsub, got), = h.slides
    assert got == title
    assert "None" not in headsub[0] and "None" not in headsub[1]
    assert h.charts[0]["name"] == chart


@pytest.mark.parametrize("fn,title,chart", SLIDES)
def test_draws_its_chart_for_real(tmp_path, fn, title, chart):
    h = _h()
    h["chart"] = lambda name, f, *a, **k: f(*a, tmp_path / f"{name}.png", **k)
    assert fn(h, FULL, BASE) is None
    png = tmp_path / f"{chart}.png"
    assert png.exists() and png.stat().st_size > 5_000


def test_the_six_slides_follow_card_tenure_in_builders():
    names = [getattr(b, "__name__", "") for b in txn_slides.BUILDERS]
    start = names.index("card_use_by_account_tenure") + 1
    assert names[start:start + 6] == [
        "pin_or_signature", "who_routes_pin", "pin_heavy_accounts",
        "where_pin_gets_pressed", "channels_used_together", "what_a_second_channel_is_worth"]


def test_the_mix_slides_decline_on_a_single_rail_file():
    single = {"ic_routing_available": False, "ic_rails": ["SIG"], "ic_base_label": BASE}
    assert V.pin_or_signature(_h(), single, BASE) == \
        "PIN or signature (file carries SIG only; the mix is an artefact of the extract)"
    for fn in (V.who_routes_pin, V.pin_heavy_accounts, V.where_pin_gets_pressed):
        assert "no PIN/SIG mix" in fn(_h(), single, BASE)


def test_where_pin_gets_pressed_declines_when_no_merchant_carries_pin():
    # issue #89: PIN at $0 for every merchant means no usable indicator, not a signature-only market
    t = dict(FULL, ic_by_merchant=[[n, c, 0, d, 100.0] for n, c, _p, d, _s in FULL["ic_by_merchant"]])
    assert "no PIN/SIG mix" in V.where_pin_gets_pressed(_h(), t, BASE)


def test_the_headlines_carry_the_numbers():
    h = _h()
    V.pin_or_signature(h, FULL, BASE)
    assert h.slides[0][0][0] == \
        "58% of card dollars route as signature, and the share is rising 3.0 points"
    # the holder-age spread joined the rail ("Who routes PIN" folded in, Sheila's 1798 slide
    # review, 2026-10-30, group D); the two tickets share one tile
    assert [r[1] for r in h.rails[0]] == ["58%", "49%", "44-71%", "$61", "$1.9M"]
    assert h.rails[0][2] == ("By holder age", "44-71%", "signature, 65+ lowest, 18-25 highest")
    assert h.rails[0][3][2] == "PIN, against $39 signature"
    # RPE's house month format, MMM'YY (v5 drew "Sep 25"; periods.install_month_axis_guard)
    assert h.charts[0]["rows"][0] == ["Sep'25", 900, 57.1]     # grey base = accounts observed
    h = _h()
    V.who_routes_pin(h, FULL, BASE)
    assert h.slides[0][0][0] == "Signature routing runs from 44% (65+) to 71% (18-25) by holder age"
    assert h.rails[0][0][0] == "Student Checking" and "PIN-defaulted" in h.rails[0][0][2]
    h = _h()
    V.where_pin_gets_pressed(h, FULL, BASE)
    assert h.slides[0][0][0] == "Walmart carries the most PIN dollars, $210K at 70% PIN"
    h = _h()
    V.channels_used_together(h, FULL, BASE)
    assert h.slides[0][0][0] == \
        "610 accounts use card alone; their multi-channel peers most often add ACH (48%)"
    assert h.charts[0]["rows"]["rows"] == ["Card", "ACH", "Check", "P2P"]
    assert [r[0] for r in h.rails[0]] == ["Card only", "ACH only", "Check only"]
    h = _h()
    V.what_a_second_channel_is_worth(h, FULL, BASE)
    assert h.slides[0][0][0] == "An account on 4 channels moves $3.1K a month against $610 on 1, 5.1x"


def test_relationship_slides_decline_on_a_single_rail_feed():
    single = {"rel_single_rail": True}
    assert V.channels_used_together(_h(), single, BASE).startswith("Channels used together (feed")
    assert V.what_a_second_channel_is_worth(_h(), single, BASE) == \
        "What a second channel is worth (feed carries one rail)"


def test_v5_month_keys_reach_the_axis_in_house_format():
    """1798's ic_monthly carries v5's "Jan24" keys; _month_label read only "2026-02", so the label
    went out as "Jan24", the month-axis guard refused the chart, and "PIN or signature" shipped
    with a blank chart area (Sheila's 1798 slide review, 2026-10-30, slide 34)."""
    assert V._month_label("Jan24") == "Jan'24"
    assert V._month_label("2026-02") == "Feb'26"
    assert V._month_label("Dec25") == "Dec'25"
    h = _h()
    t = dict(FULL, ic_monthly=[["Jan24", 60_000, 80_000, 57.1, 900], ["Feb24", 62_000, 84_000, 57.5, 920],
                               ["Mar24", 61_000, 88_000, 59.1, 940]])
    V.pin_or_signature(h, t, BASE)
    assert [r[0] for r in h.charts[0]["rows"]] == ["Jan'24", "Feb'24", "Mar'24"]


def test_v5_month_keys_draw_the_signature_chart_for_real(tmp_path):
    h = _h()
    h["chart"] = lambda name, f, *a, **k: f(*a, tmp_path / f"{name}.png", **k)
    t = dict(FULL, ic_monthly=[["Jan24", 60_000, 80_000, 57.1, 900], ["Feb24", 62_000, 84_000, 57.5, 920],
                               ["Mar24", 61_000, 88_000, 59.1, 940], ["Apr24", 61_000, 88_000, 59.9, 940]])
    assert V.pin_or_signature(h, t, BASE) is None
    assert (tmp_path / "ic_monthly.png").stat().st_size > 5_000


def test_pin_heavy_names_the_merchant_and_falls_back_to_the_mix():
    h = _h()
    V.pin_heavy_accounts(h, FULL, BASE)
    assert h.slides[0][0][0] == ("210 accounts (17%) put 80% or more of their card dollars through "
                                 "PIN; Walmart carries the most PIN dollars")
    assert h.rails[0][-1] == ("Most PIN dollars", "Walmart", "$210K at 70% PIN")
    h = _h()
    V.pin_heavy_accounts(h, dict(FULL, ic_by_merchant=FULL["ic_by_merchant"][:2]), BASE)
    assert h.charts[0]["name"] == "ic_account_mix"
    assert h.rails[0][-1][0] == "All signature"
