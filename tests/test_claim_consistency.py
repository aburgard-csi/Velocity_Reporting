"""validate_deck.claim_consistency_findings — slide text must match slide data.

The defect: Marine FCU's responder commentary read "NSF/OD activity stayed
roughly flat" when NSF/OD had risen 27% (0.40 -> 0.50 per responder per month)
in the very extract the slide was built from. Every gate passed it — the swap
landed, the sidecar saw one value per measure, no banned word, nothing
overflowed. Nothing asked whether the sentence was TRUE.

Half these tests are the rule working. The other half are the three ways the
first drafts got it wrong, each of which failed correct, already-shipped slides:

  * comparison read as movement — "lower balances than non-responders
    ($924 vs $2,477)" is right; as a change it looks like a 168% rise (6 decks)
  * one claim tested against another claim's numbers — "ticket holds
    (mean $56->$53) while swipes rise 8.9->17.4" (6 decks)
  * two unrelated percentages attached to one pair — "net +26.2% against
    -17.2%, with swipes 11.5 -> 16.0" (1 deck)

A gate that fails correct work gets switched off, so the false-positive tests
matter as much as the true-positive ones.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation"))
import validate_deck as V                                         # noqa: E402


class _Frame:
    def __init__(self, t):
        self.text = t


class _Shape:
    has_table = False
    shape_type = 1

    def __init__(self, t):
        self.has_text_frame = True
        self.text_frame = _Frame(t)


class _Slide:
    def __init__(self, t):
        self.shapes = [_Shape(t)]


class _Prs:
    def __init__(self, *texts):
        self.slides = [_Slide(t) for t in texts]


def find(text):
    return V.claim_consistency_findings(_Prs(text))


def fails(text):
    return [f for f in find(text) if f[0] == "FAIL"]


# --------------------------------------------------------------- true positives
def test_flat_claim_outside_the_band_fails():
    """Aaron's threshold: +/-2% is almost flat, outside it is not."""
    f = fails("NSF/OD activity stayed roughly flat, from 0.40 to 0.50 per responder.")
    assert len(f) == 1 and "outside the +/-2% band" in f[0][2]


def test_a_claim_of_stability_covers_holds():
    """'holds' asserts stability as much as 'flat' does — it shipped on six
    2026.08 decks over a 5-9% decline."""
    assert fails("For responders, ticket holds through response (mean $56 to $53).")


@pytest.mark.parametrize("txt", [
    "Average ticket declined from $18.10 to $22.40.",
    "Spend fell from $556 to $1,077.",
])
def test_a_decline_that_rose_fails(txt):
    assert fails(txt)


def test_a_rise_that_fell_fails():
    assert fails("Spend rose from $1,077 to $556.")


def test_a_percentage_that_does_not_divide_out_fails():
    f = fails("Debit spend rose from $556 to $1,077 (+40%).")
    assert len(f) == 1 and "does not match" in f[0][2]


def test_a_comparison_in_the_wrong_order_fails():
    assert fails("Responders carry lower balances than non-responders "
                 "(median $2,477 vs $924).")


# -------------------------------------------------------------- false positives
def test_a_correct_comparison_passes():
    """Two GROUPS at one moment. $924 IS lower than $2,477 — read as movement
    this looks like a +168% rise. Failed six shipped decks."""
    assert not fails("Responders carry lower balances than non-responders "
                     "(median $924 vs $2,477)")


def test_a_correct_higher_comparison_passes():
    assert not fails("Responders carry modestly higher balances than "
                     "non-responders (median $547 vs $393)")


def test_each_claim_is_tested_against_its_own_numbers():
    """'rise' belongs to the swipes beside it, not to the ticket figures earlier
    in the sentence. Failed six shipped decks."""
    assert not fails(
        "For responders, ticket moved little (mean $56 to $55) while monthly "
        "swipes rise 8.9 to 17.4: the gain is more transactions, not larger ones.")


def test_two_percentages_are_not_pinned_to_one_pair():
    """Two tier-movement rates and one unrelated pair. Failed a shipped deck."""
    assert not fails("On equal footing responders net +26.2% against -17.2%, "
                     "with swipes 11.5 to 16.0 per month.")


def test_a_negated_verb_is_not_read_as_its_opposite():
    """"did not increase" alongside a fall is correct writing. Reading the verb
    without its negation reports the finding backwards."""
    assert not fails("Swipe volume did not increase over this window (19.7 to 19.1).")
    assert not fails("There was no rise in ticket (from $56 to $53).")


def test_a_correctly_rounded_percentage_passes():
    """93.7% stated as +94% is rounding, not a defect."""
    assert not fails("Debit spend rose from $556 to $1,077 (+94%).")


def test_a_genuinely_flat_pair_passes():
    assert not fails("NSF/OD activity was essentially flat, from 0.40 to 0.404.")


def test_prose_without_figures_is_not_flagged():
    """An earlier draft reported these and produced 156 findings across 20
    files, almost all legitimate bullets whose evidence is the chart."""
    assert not find("Card-holding accounts have grown over the last 36 months")


def test_a_mailing_drop_is_not_a_decline():
    """In this pipeline a drop is something you send."""
    assert not find("Selection: the 3,199 accounts mailed in the Jun 2026 drop.")


def test_definitions_and_metadata_are_skipped():
    assert not find("Increase = transactions in the month after the offer minus the goal")
    assert not find("Source: 1539 ODD extract, pulled 2026-08-13.")


# ------------------------------------------------------------------ wiring
def test_the_check_runs_as_part_of_the_gate():
    """A rule nothing calls is a rule that does not exist."""
    import inspect
    src = inspect.getsource(V.main)
    assert "claim_consistency_findings" in src


def test_the_flat_band_is_aarons_two_percent():
    assert V.FLAT_BAND_PCT == 2.0
