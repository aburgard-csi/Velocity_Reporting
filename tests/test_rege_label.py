"""Reg E wording has ONE reading, shared by the optimizer and the deck metrics (2026-09-16).

metrics_gen carried its own copy that matched only "opt in", so extracts worded "Opted In" /
"Opted Out" put every account in "no election": 1776 CoastHills and about a dozen other decks
showed Reg E opt-in at 0.0% while oddd_optimize, reading the same files, found both.
"""
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
from odd_rows import rege_label, REGE_IN, REGE_OUT, REGE_DEFAULT  # noqa: E402


@pytest.mark.parametrize("text,label", [
    # wordings seen in real extracts
    ("Opted In", REGE_IN), ("Opted Out", REGE_OUT),
    ("Opt-In Accepted", REGE_IN), ("Opt-In Declined", REGE_OUT), ("No Response Recevied", REGE_DEFAULT),
    ("Reg E Opt In", REGE_IN), ("Reg E Opt Out", REGE_OUT), ("Reg E Default", REGE_DEFAULT),
    ("OPTED IN", REGE_IN), ("  opted   out ", REGE_OUT),
    # confirmed by Aaron, 2026-09-16
    ("Yes", REGE_IN), ("Y", REGE_IN), ("No", REGE_OUT), ("N", REGE_OUT),
    ("Revoked", REGE_OUT), ("Failed to Respond", REGE_DEFAULT), ("No Decision", REGE_DEFAULT),
    ("Ineligible", ""), ("Exempt", ""), ("Tracking Type 56 Does Not Exist", ""),
    ("Did Not Reply", REGE_DEFAULT), ("D", REGE_DEFAULT), ("No Vaule - No Reg E", ""),
    # confirmed by Aaron, 2026-09-17
    ("Anything else", REGE_OUT), ("Accepted", REGE_IN), ("Declined", REGE_OUT),
    ("Bank Revoked", REGE_OUT),
    # blank is not applicable
    ("", ""), (None, ""), ("\x00", ""),
])
def test_known_wording(text, label):
    assert rege_label(text) == label


@pytest.mark.parametrize("text", ["Maybe", "Pending", "No opinion yet"])
def test_unknown_wording_is_unmapped_not_guessed(text):
    assert rege_label(text) is None


def test_metrics_gen_and_the_optimizer_share_the_one_reading():
    """A second copy of the wording rules is how the 0.0% shipped; neither file may carry one."""
    mg = (REPO / "build" / "ars_pipeline" / "metrics_gen.py").read_text(encoding="utf-8")
    oo = (REPO / "scripts" / "oddd_optimize.py").read_text(encoding="utf-8")
    for name, src in (("metrics_gen.py", mg), ("oddd_optimize.py", oo)):
        assert "rege_label" in src, f"{name} must read Reg E wording through odd_rows.rege_label"
        assert not re.search(r"""['"]opt[ -]?in['"]\s+in\b|opted in\|""", src), f"{name} carries its own Reg E wording rule"


def test_metrics_gen_stops_on_unmapped_wording():
    mg = (REPO / "build" / "ars_pipeline" / "metrics_gen.py").read_text(encoding="utf-8")
    assert "_rege_unmapped" in mg and "Reg E wording no mapping covers" in mg


def test_classify_rege_passes_unmapped_wording_through_for_the_flags():
    pd = pytest.importorskip("pandas")
    sys.path.insert(0, str(REPO / "scripts"))
    import oddd_optimize as O
    out = O.classify_rege(pd.Series(["Opted In", "Opted Out", "", "Exempt", "Pending", None]))
    assert list(out) == [REGE_IN, REGE_OUT, "", "", "Pending", ""]
