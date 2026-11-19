"""The Competition layers slides (ti/deck/txn_layers.py, ti/deck/charts_layers.py).

Synthetic `cl_*` figures only. Every builder declines with a reason on an empty client, draws for real on a full
one (its chart written, no "None" in a headline), keeps its headline within two title lines, uses no banned word,
and the whole set runs through the real Deck helpers into a presentation.

    python -m pytest tests/test_ti_competition_layers_slides.py -q
"""
import os
import pathlib
import re
import sys

import pytest
from pptx import Presentation

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti import chapters_txn as X  # noqa: E402
from ti.deck import txn_layers as LAYERS  # noqa: E402
from ti.deck.helpers import Deck  # noqa: E402

TIERS = ["National", "Digital", "Local", "Regional (district)", "Other (outside district)", "Card-issuing banks (review)"]
ARS = ["responders", "mailed_nonresp", "mailed_nonresp_nu1_4", "mailed_nonresp_none", "not_mailed"]
ARS_LABELS = {"responders": "Responders", "mailed_nonresp": "Mailed, non-response", "mailed_nonresp_nu1_4": "Mailed, NU 1-4",
              "mailed_nonresp_none": "Mailed, no response", "not_mailed": "No mail"}
ICS_LABELS = {"ics": "ICS account", "ics_dm": "ICS direct mail", "not_ics": "Not ICS"}
BANNED = ("robust", "comprehensive", "leverage", "seamless", "delve", "engine", "lever", "lift", "ramping", "healthy",
          "predominantly", "companion", "seasoned book", "annuity")


def make_figures(groups=ARS, labels=ARS_LABELS, per_tier=7):
    base = 1000
    gsize = {g: base // len(groups) for g in groups}
    inst, mv, di = [], [], []
    for ti, tier in enumerate(TIERS):
        for i in range(per_tier):
            name = f"{tier.split()[0]} Institution {i + 1}"
            acc, dol = 120 - 14 * i - 5 * ti, (90000 - 11000 * i) * (3 - ti * 0.3)
            by = {g: {"accounts": max(acc // len(groups) + (3 if g == groups[0] else 0), 1), "dollars": round(dol / len(groups)),
                      "pct": 1.0} for g in groups}
            inst.append({"inst": name, "tier": tier, "ambiguous": False, "type": "Credit Union" if i % 2 else "Bank", "accounts": acc,
                         "dollars": round(dol), "by_group": by, "pct": round(acc / base * 100, 2),
                         "nearest_mi": None if ti in (0, 1) else float(i + 1), "descriptors": [f"{name.upper()} PMT", f"{name.upper()} 12"],
                         "new_90": 10 - i, "stopped_90": 4 + i, "live_30": 20 - i, "heavy": 12 - i, "mid": 20, "median_share_pct": 3.2})
            mv.append({"inst": name, "tier": tier, "relationships": acc, "new_90": 10 - i, "stopped_90": 4 + i, "live_30": 20 - i})
            di.append({"inst": name, "tier": tier, "relationships": acc, "median_share_pct": 3.2, "heavy": 12 - i, "mid": 20})
    tiers = []
    for tier in TIERS:
        rows = [r for r in inst if r["tier"] == tier]
        tiers.append({"tier": tier, "accounts": sum(r["accounts"] for r in rows) // 2, "pct": round(sum(r["accounts"] for r in rows) / base * 50, 1),
                      "dollars": sum(r["dollars"] for r in rows), "institutions": len(rows),
                      "by_group": {g: {"accounts": 10, "dollars": 1000, "pct": 2.0 + k} for k, g in enumerate(groups)}})
    months = [f"2026-{m:02d}" for m in range(5, 11)]
    trend = [{"month": m, "group": g, "active": 800, "dollars": 100000, "per_active": 125.0 + k * 40, "pin_pct": 21.0 - k, "competitor_dollars": 1500,
              "competitor_pct": 1.5 + k * 0.1} for m in months for k, g in enumerate(["all"] + list(groups))]
    return {
        "cl_scope": {"depository_only": True, "rail": "card (PIN, SIG)", "district": "11", "client_type": "Credit Union", "thresholds": {"local_miles": 25.0, "national_states": 10}},
        "cl_base": {"accounts": base, "dollars": 5_000_000, "groups": gsize, "group_labels": labels},
        "cl_any": {"accounts": 150, "pct": 15.0, "dollars": sum(r["dollars"] for r in inst),
                   "by_group": {g: {"accounts": 20, "pct": 8.0 + 3 * k, "dollars": 5000} for k, g in enumerate(groups)}},
        "cl_tiers": tiers, "cl_institutions": inst,
        "cl_coverage": {"placed_dollars": 900000, "review_dollars": 25000, "pct": 97.3, "ambiguous_dollars": 4000, "review_names": 31},
        "cl_review_queue": [[f"UNPLACED NAME {i}", 5, 10, 9000 - i * 700] for i in range(12)],
        "cl_universe": [{"tier": t, "registry": 100 * (i + 1), "within_local": i * 3, "seen": 7} for i, t in enumerate(TIERS)],
        "cl_trend": trend, "cl_movement": mv, "cl_tier_movement": [],
        "cl_depth_tiers": [{"tier": t, "under 5%": 30, "5-20%": 20, "20%+": 10, "relationships": 60, "heavy_pct": 16.7} for t in TIERS], "cl_depth_institutions": di,
        "cl_multi": [{"group": g, "institutions": k, "accounts": 10, "pct": p} for g in ["all"] + list(groups) for k, p in (("0", 80.0), ("1", 14.0), ("2", 4.0), ("3+", 2.0))],
        "cl_recency": [{"tier": t, "live (30d)": 20, "cooling (31-90d)": 10, "quiet (91-180d)": 8, "dormant (180d+)": 12, "relationships": 50} for t in TIERS],
        "cl_distance": [{"band": "0-5 mi", "institutions": 6, "relationships": 300, "dollars": 400000}, {"band": "5-25 mi", "institutions": 9, "relationships": 90, "dollars": 90000},
                        {"band": "no branch near", "institutions": 70, "relationships": 900, "dollars": 1500000}],
        "cl_winback": [{"inst": f"Local Institution {i}", "tier": "Local", "heavy_live": 20 - 3 * i, "live": 40, "accounts": 90,
                        "by_group": {g: 2 + i for g in groups}} for i in range(6)],
        "cl_attrition": [{"exposed_to": "ANY depository competitor", "exposed": 900, "closed": 20, "closure_pct": 2.2, "unexposed": 4000, "unexposed_closure_pct": 1.7, "relative_risk": 1.3}] +
                        [{"exposed_to": t, "exposed": 300, "closed": 6, "closure_pct": 2.0, "unexposed": 4000, "unexposed_closure_pct": 1.7, "relative_risk": 1.0 + 0.2 * i} for i, t in enumerate(TIERS[:4])],
        "cl_branches": [{"branch": str(300 + i), "accounts": 500 + 90 * i, "any_pct": 12.0 + i, "local_pct": 2.0, "national_pct": 8.0, "digital_pct": 2.0, "closed_12m": 30 + i,
                         "closure_pct": 5.0 + 0.4 * i} for i in range(6)],
        "cl_changes": {"prior_period": "2026.10", "coverage": {"now": 97.3, "prior": 97.0},
                       "tiers": [{"tier": "National", "accounts_now": 100, "accounts_prior": 90, "pct_now": 9.0, "pct_prior": 8.0, "change_points": 1.0, "dollars_now": 5, "dollars_prior": 4},
                                 {"tier": "Local", "accounts_now": 20, "accounts_prior": 30, "pct_now": 2.0, "pct_prior": 3.0, "change_points": -1.0, "dollars_now": 5, "dollars_prior": 4}],
                       "institutions": [{"inst": "National Institution 1", "tier": "National", "accounts_now": 60, "accounts_prior": 20, "change": 40, "status": "continuing"},
                                        {"inst": "New Name", "tier": "Local", "accounts_now": 55, "accounts_prior": 0, "change": 55, "status": "new this month"},
                                        {"inst": "Gone Name", "tier": "Local", "accounts_now": 0, "accounts_prior": 12, "change": -12, "status": "not seen this month"}],
                       "triggers": [{"trigger": "New institution over the threshold", "subject": "New Name", "detail": "55 accounts (threshold 50)"},
                                    {"trigger": "Tier share moved", "subject": "National", "detail": "+1.00 points (threshold 0.3)"}]},
        "cl_map": {"client": [[35.0, -100.0], [35.05, -100.04]], "radius": 25.0,
                   "branches": [[35.0 + 0.01 * i, -100.0 + 0.012 * i, f"Local Institution {i % 5}", "Local" if i % 3 else None] for i in range(24)]},
    }


FULL = make_figures()


class _Rows:
    def __init__(self, n):
        self.cells = [type("C", (), {"text_frame": type("F", (), {"paragraphs": [type("P", (), {"alignment": None})()]})()})() for _ in range(n)]


class _Shape:
    def __init__(self, rows):
        self.table = type("T", (), {"rows": [_Rows(len(r)) for r in rows]})()


class _Harness(dict):
    def __init__(self, tmp, lens="ars"):
        super().__init__()
        self.tmp, self.slides, self.rails, self.tables, self.charts = tmp, [], [], [], []
        self["slide"] = self._slide
        self["chart"] = self._chart
        self["chart_left"] = lambda *a, **k: None
        self["picture"] = lambda *a, **k: 5.0
        self["rail"] = self._rail
        self["table"] = self._table
        self["lens"] = lens

    def _slide(self, headsub, topic):
        self.slides.append((headsub, topic))
        return object(), 1.5

    def _chart(self, name, fn, *a, **k):
        self.charts.append(name)
        return fn(*a, self.tmp / f"{name}.png", **k)

    def _rail(self, _s, rows, **_k):
        self.rails.append(rows)
        return 10.0

    def _table(self, _s, rows, *a, **k):
        self.tables.append(rows)
        return _Shape(rows)


BUILDERS = LAYERS.BUILDERS


@pytest.mark.parametrize("build", BUILDERS, ids=[b.__name__ for b in BUILDERS])
def test_each_slide_declines_with_a_reason_on_a_client_with_no_layers(build, tmp_path):
    why = build(_Harness(tmp_path), {}, "transacting personal accounts")
    assert isinstance(why, str) and "(" in why and why.endswith(")")


@pytest.mark.parametrize("build", BUILDERS, ids=[b.__name__ for b in BUILDERS])
def test_each_slide_draws_for_real_with_a_computed_headline(build, tmp_path):
    h = _Harness(tmp_path)
    why = build(h, dict(FULL), "transacting personal accounts")
    assert why is None, why
    assert h.slides, f"{build.__name__} drew no slide"
    for (head, sub), topic in h.slides:
        text = f"{head} {sub or ''}"
        assert head and "None" not in text and "nan" not in text.lower().split() and "{" not in text, text
        assert len(head) <= 150, f"{len(head)} characters: {head}"
        assert topic == LAYERS.TITLES[build.__name__] or topic == LAYERS.LIST_TOPIC
        assert not [w for w in BANNED if re.search(rf"\b{w}\b", text, re.I)], text
    for name in h.charts:
        assert (tmp_path / f"{name}.png").exists(), f"{build.__name__}: {name} not drawn"


def test_the_full_list_pages_cover_every_institution_once(tmp_path):
    h = _Harness(tmp_path)
    assert LAYERS.layers_full_list(h, dict(FULL), "transacting personal accounts") is None
    n = len(FULL["cl_institutions"])
    shown = sum(len(rows) - 1 for rows in h.tables)
    assert shown == n and len(h.slides) == -(-n // LAYERS.LIST_PAGE)
    assert all(h.slides[i][0][0].endswith(f"of {n})") for i in range(len(h.slides)))
    ranks = [r[0] for rows in h.tables for r in rows[1:]]
    assert ranks == list(range(1, n + 1))


def test_the_ics_lens_names_its_own_groups_and_the_near_responder_slide_stands_down(tmp_path):
    ics = make_figures(groups=["ics", "ics_dm", "not_ics"], labels=ICS_LABELS)
    h = _Harness(tmp_path, lens="ics")
    assert "ARS group" in LAYERS.layers_near_responders(h, ics, "x") or "mailed non-response" in LAYERS.layers_near_responders(h, ics, "x")
    assert LAYERS.layers_heat(h, ics, "x") is None and LAYERS.layers_lens(h, ics, "x") is None
    assert LAYERS.layers_winback(h, ics, "x") is None
    head = h.slides[0][0][0]
    assert "ICS account" in head or "Not ICS" in head


def test_a_missing_part_declines_only_its_own_slide(tmp_path):
    t = dict(FULL)
    del t["cl_attrition"], t["cl_map"], t["cl_branches"]
    h = _Harness(tmp_path)
    assert "closure dates" in LAYERS.layers_attrition(h, t, "x")
    assert LAYERS.layers_map(h, t, "x").startswith("Competitors near")
    assert LAYERS.layers_summary(h, t, "x") is None and LAYERS.layers_ladder(h, t, "x") is None


def test_the_clients_own_base_is_named_by_its_type_and_never_guessed():
    assert LAYERS._own({"cl_scope": {"client_type": "Credit Union"}}) == "members"
    assert LAYERS._own({"cl_scope": {"client_type": "Bank"}}) == "customers"
    assert LAYERS._own({"cl_scope": {}}) == "accounts"
    assert LAYERS._word("Credit Union") == "members" and LAYERS._word("Bank") == "customers"


def test_the_layers_slides_follow_the_chapters_own_and_replace_none():
    names = [b.__name__ for b in X.COMP_DRAWN]
    assert len(X.COMP_BUILDERS) == 22      # +2: the BNPL providers-in-depth and who-uses-it slides (test_ti_bnpl_expansion)
    assert names[-len(LAYERS.BUILDERS):] == [b.__name__ for b in LAYERS.BUILDERS]
    assert all(X.TITLES[b.__name__] for b in LAYERS.BUILDERS) and X.DRAWN_TITLES["layers_map"] == LAYERS.TITLES["layers_map"]


def test_the_whole_set_runs_through_the_real_deck_helpers_into_a_presentation(tmp_path):
    class _Ctx:
        prs = Presentation(os.path.join(HERE, "..", "templates", "ars_template.pptx"))
        pack = {"client_id": "9999", "client_name": "Test Credit Union", "sources": {"odd": "x"}, "metrics": {}}
        lens = type("L", (), {"label": "ARS lens", "key": "ars"})()
        pill, art_dir = "October 2026 Data", str(tmp_path)

    deck = Deck(_Ctx(), "the ODD extract and the monthly debit-card transaction files", tmp_path / "charts")
    slides = deck.run(LAYERS.BUILDERS, X.DRAWN_TITLES, dict(FULL), "transacting personal accounts")
    assert not deck.chart_failures, deck.chart_failures
    declined = [d for d in deck.declines]
    assert not declined, declined
    assert len(slides) == 57       # 7 orientation + 3 list pages + 5 tiers x 6 + 14 whole-book + 3 month-over-month, on this fixture
    notes = slides[0].notes_slide.notes_text_frame.text
    assert "Test Credit Union" in notes and "not ported from the ARS v5 engine" in notes


def test_a_review_of_a_real_deck_three_fixes_months_gap_percent_sign_and_absent_local_tier(tmp_path):
    """Seen on a real client: the month axis skipped a month with no card rows, the list's "% of base" had no % sign, and the
    ladder headline said "local institutions take 0%" for a client with no local tier at all."""
    assert LAYERS._span(["2025-11", "2026-02", "2026-04"]) == ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
    assert LAYERS._span([]) == []
    h = _Harness(tmp_path)
    LAYERS.layers_full_list(h, dict(FULL), "transacting personal accounts")
    assert all(str(r[4]).endswith("%") for rows in h.tables for r in rows[1:])
    t = dict(FULL)
    t["cl_tiers"] = [r for r in FULL["cl_tiers"] if r["tier"] not in ("Local", "Local (25-50 mi)")]
    h = _Harness(tmp_path)
    LAYERS.layers_ladder(h, t, "x")
    assert "take 0%" not in h.slides[0][0][0] and "no local institution" in h.slides[0][0][0]


def test_the_universe_headline_counts_every_paid_institution_not_only_the_registry_matches(tmp_path):
    """Seen on a real client: slide 33 said 202 institutions and the universe slide said 174, because 6 digital names and 22
    ambiguous names are paid but have no registry branch."""
    h = _Harness(tmp_path)
    t = dict(FULL)
    t["cl_institutions"] = list(FULL["cl_institutions"]) + [{"inst": "Digital Only", "tier": "Digital", "accounts": 1, "dollars": 1}]
    LAYERS.layers_universe(h, t, "x")
    head = h.slides[0][0][0]
    seen = sum(r["seen"] for r in FULL["cl_universe"])
    assert f"{len(t['cl_institutions']):,} institutions appear in card spending" in head and f"{seen} of them" in head
    assert "digital-only" in h.slides[0][0][1]


def test_the_lens_headline_is_short_and_the_group_figures_sit_in_the_subtitle(tmp_path):
    h = _Harness(tmp_path)
    LAYERS.layers_lens(h, dict(FULL), "x")
    head, sub = h.slides[0][0]
    assert head == "Share of each group paying a competitor, by tier" and "Any tier:" in sub
