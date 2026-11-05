"""peer_compare: the one arithmetic Live Review and the Executive Review decks share, and what a deck is allowed to see."""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build"), os.path.join(REPO, "scripts")]

import peer_compare as PC                                        # noqa: E402
from review_page import peer_pool, peers                         # noqa: E402
from review_page.trace import Tracer                             # noqa: E402

PEER_IDS = [str(7000 + i) for i in range(1, 10)]
SPEC = {"key": "x", "label": "Share of widgets", "fmt": "pct1", "higher": True, "month": False}


def collected(me=20.0, vals=(10, 12, 14, 16, 18, 22, 24, 26, 28)):
    return {"n_pool": len(vals), "me": {"point": {"x": me}, "series": {}},
            "peers": [{"id": i, "point": {"x": v}, "series": {}} for i, v in zip(PEER_IDS, vals)], "pull": "2026-10-01"}


def test_the_names_the_page_has_always_used_still_resolve():
    assert peers.quantile is PC.quantile and peers.rank_among is PC.rank_among and peers.align_month is PC.align_month
    assert peers.MIN_PEERS == PC.MIN_PEERS == 5


def test_compare_values_keeps_ids_only_when_given():
    c = PC.compare_values(SPEC, 20.0, [10, 12, 14, 16, 18, 22], PEER_IDS[:6])
    assert c["dot_ids"] == PEER_IDS[:6] and c["rank"] == 2 and c["total"] == 7 and c["n"] == 6
    assert PC.compare_values(SPEC, 20.0, [10, 12, 14, 16], None) is None
    assert PC.compare_values(SPEC, None, [10, 12, 14, 16, 18]) is None
    assert PC.compare_values(SPEC, 20.0, [10, 12, 14, 16, 18])["dot_ids"] is None


def test_a_deck_comparison_carries_no_client_number(monkeypatch):
    monkeypatch.setitem(peer_pool.PROGRAMS, "ARS", (lambda ctx: collected(), [SPEC], "ARS"))
    ev = PC.for_deck("ARS", "9999", period="2026.10")
    assert len(ev["items"]) == 1 and ev["items"][0]["c"]["dot_ids"] is None
    text = repr(ev)
    assert not any(pid in text for pid in PEER_IDS)
    assert ev["items"][0]["c"]["dots"] == sorted([10, 12, 14, 16, 18, 22, 24, 26, 28])


def test_the_deck_and_live_review_say_the_same_thing(monkeypatch):
    coll = collected()
    ev = PC.evaluate(coll, [SPEC], "ARS")
    screen = peers.peers_screen(Tracer(), "ARS", "ARS", coll, [SPEC], pull_dates="2026-10-01")
    strip = next(b for b in screen["blocks"] if b["t"] == "peerstrip")
    assert strip["sentence"] == ev["items"][0]["sentence"]
    assert strip["median"] == ev["items"][0]["c"]["median"] and strip["q1"] == ev["items"][0]["c"]["q1"]
    assert screen["headline"] == ev["items"][0]["sentence"]


def test_a_program_with_too_few_other_clients_is_stated_not_shown():
    ev = PC.evaluate({"n_pool": 3, "me": {"point": {"x": 1.0}, "series": {}}, "peers": []}, [SPEC], "ICS")
    assert ev["items"] == [] and "at least 5 other clients on ICS; this book has 3" in ev["unavailable"]


def test_a_metric_the_client_has_no_figure_for_is_named_in_left():
    c = collected()
    c["me"]["point"] = {}
    ev = PC.evaluate(c, [SPEC], "ARS")
    assert ev["items"] == [] and ev["left"] == ["Share of widgets: this client has no current figure for it"]


def test_the_two_percent_band_words():
    c = PC.compare_values(SPEC, 20.0, [19, 19.5, 20, 20.5, 21, 20.2])
    assert PC.sentence(SPEC, c, "ARS").endswith("almost flat against the peer median (20.1%).")
    c2 = PC.compare_values(SPEC, 30.0, [19, 19.5, 20, 20.5, 21])
    assert "above the peer median" in PC.sentence(SPEC, c2, "ARS") and c2["rank"] == 1
