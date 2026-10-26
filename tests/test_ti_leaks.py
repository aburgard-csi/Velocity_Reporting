"""v5's leak post-passes in the cut (build/ars_pipeline/ti/odd_sections.leaks).

The debit half of `leaks.compute` reads `n_eligible`, which in v5 sits in the metrics from the
account bases before any section runs. The cut's first wrapper handed leaks only the dctr / rege /
value figures, and the debit half was skipped without a word: parity matched 7 of 7 keys while v5
had written 14. The bases are part of what leaks reads now.
"""
from ti import odd_sections


class _Subsets:
    def sizes(self):
        return {"n_eligible": 1000}


class _Ctx:
    subsets, config = _Subsets(), {}

    def warn(self, _m):
        pass


DCTR = {"dctr_overall": 60.0, "dctr_cards": 600,
        "take_branch": [["Main", 700, 1000, 70.0], ["North", 100, 400, 25.0]],
        "n_dctr_business": 200, "dctr_business": 40.0}


def test_the_debit_half_runs_on_the_bases_and_is_priced():
    out = odd_sections.leaks(_Ctx(), {**DCTR, "value_per_card": 120.0})
    assert out["dctr_leaks"], "the debit leaks need n_eligible from the bases"
    assert out["dctr_business_gap"]["gap_pp"] == 20.0
    assert "dctr_leak_value" in out and "dctr_business_value" in out, "apply_to_leaks prices them"
