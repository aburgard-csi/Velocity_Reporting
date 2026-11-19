"""Two defects that reached main with the insurance PR (#142), each pinned by the check that would have caught it.

- A dictionary name is printed on a slide as it is written ("Life & annuity" on the Insurance by line slide), so a
  banned word in one fails validate_deck and keeps the Transaction Intelligence deck out of Outputs. Every category
  and subtype name in the financial-services dictionary, and every tier and institution name in the competitor
  dictionary, is checked against the validator's own list.
- The competition text report formatted the threat score's growth figure with a float format, and that figure is
  None when the data covers under six months (competition.MIN_GROWTH_DAYS), so ti_build raised before any deck was
  drawn.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "build" / "ars_pipeline"))
sys.path.insert(0, str(ROOT / "validation"))

from ti import dictionaries  # noqa: E402
from ti.transaction_intelligence import competition_report  # noqa: E402
import validate_deck  # noqa: E402


def _banned_in(name: str) -> list[str]:
    low = name.lower()
    if any(ok in low for ok in validate_deck.BANNED_ALLOW_CONTEXT):
        return []
    return [w for w in validate_deck.BANNED if re.search(r"\b" + re.escape(w) + r"\b", low)]


def test_no_dictionary_name_a_slide_prints_carries_a_banned_word():
    folder = pathlib.Path(dictionaries.folder())
    fs = json.loads((folder / "financial_services_patterns.json").read_text(encoding="utf-8"))
    names = []
    for cat, spec in fs["categories"].items():
        names.append(cat)
        names += list((spec.get("subtypes") or {}).keys())
    comp = json.loads((folder / "competitors.json").read_text(encoding="utf-8"))
    names += list(comp["tiers"]) + list(comp["institutions"])
    names += [v["tier"] for v in comp["institutions"].values() if v.get("tier")]
    bad = {n: _banned_in(n) for n in names if _banned_in(n)}
    assert not bad, f"names printed on slides carry banned words: {bad}"


def test_the_threat_report_reads_a_missing_growth_figure():
    m = {"comp_accounts_total": 1000, "comp_threat": [["First Example Bank", 81.2, 140, 52000, None],
                         ["Second Example CU", 64.0, 90, 31000, 12.5]],
         "comp_threat_basis": "40% penetration, 30% dollars"}
    out = "\n".join(competition_report.lines(m))
    assert "n/a" in out and "12.5%" in out
