# Ported from ARS v5 02-Scripts/tests/test_txn_attrition_slides.py at a491b5c (James Gilmore); logic unchanged.
"""Two transaction attrition slides that had metrics and no page (#245)."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import txn_attrition as A, txn_slides        # noqa: E402
from test_ti_hotspot_slides import _Harness as _Base          # noqa: E402
from test_ti_txn_attrition_report import CURVE, STRESS        # noqa: E402


class _Harness(_Base):
    def __init__(self):
        super().__init__()
        self.tables = []
        self["table"] = lambda s, rows, *a, **k: self.tables.append(rows)


def test_share_before_closure_headline_states_the_divergence_and_draws_pair_lines():
    h = _Harness()
    assert A.spend_before_closure(h, CURVE, "personal accounts") is None
    (head, sub), title = h.slides[-1]
    assert title == "Competitor spend before closure" and "3 month" in head
    assert h.charts[-1]["fn"] == "pair_lines"


def test_share_before_closure_without_divergence_says_so():
    h = _Harness()
    A.spend_before_closure(h, dict(CURVE, leak_divergence_month=None), "personal accounts")
    (head, _), _ = h.slides[-1]
    assert "no " in head.lower() or "not" in head.lower()


def test_stresses_across_files_names_banking_elsewhere_and_the_two_plus_cut():
    h = _Harness()
    assert A.stresses_across_files(h, STRESS, "personal accounts") is None
    rail = " ".join(str(x) for item in h.rails[-1] for x in item)
    assert "100" in rail
    # the conditions are named in the subtitle, not as value-less "built" tiles (Sheila's 1798
    # review, 2026-10-30)
    (_head, sub), _title = h.slides[-1]
    assert "Banking elsewhere" in sub and "built" not in rail
    assert h.tables and h.tables[-1][0][0] == "Stressors"


def test_both_skip_cleanly_without_metrics():
    h = _Harness()
    assert A.spend_before_closure(h, {}, "b") and A.stresses_across_files(h, {}, "b")
    assert not h.slides


def test_the_two_follow_lose_and_leak_together_in_the_chapter():
    names = [getattr(b, "__name__", "") for b in txn_slides.BUILDERS]
    i = names.index("lose_and_leak_together")
    assert names[i + 1:i + 3] == ["spend_before_closure", "stresses_across_files"]
