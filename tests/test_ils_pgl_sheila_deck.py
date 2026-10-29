"""The ILS pre-go-live deck in Sheila's format, and the fee chapter from the notice items (2026-10-28).

Pinned: the deck is built on the ARS template shell with the Velocity review's chapters in order, passes
Sheila's deck validator, puts "ILS Program Analysis" on the cover, names an OD code by its description,
and draws a "to be completed" line where a CSM input is missing; the notice items give the fee baseline
and the cap / de minimis waivers from their own rows.
"""
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build"), str(REPO / "validation")]
import validate_deck as vd  # noqa: E402
from ils_pipeline.pre_go_live import notices, review, sheila_deck  # noqa: E402
from test_ils_pgl_review import CODES, _df  # noqa: E402


def _metrics():
    m = review.compute(_df(), CODES, {"sysv_matrix_rounding_step": 250})
    m["pgl_extract"] = "9999_Test_PGL_20261026.csv"
    return m


def _texts(prs):
    def shape_text(sh):
        if sh.has_text_frame:
            return sh.text_frame.text
        if sh.has_table:
            return "\n".join(c.text for r in sh.table.rows for c in r.cells)
        return ""
    return ["\n".join(shape_text(sh) for sh in s.shapes) for s in prs.slides]


def test_the_deck_is_built_in_sheilas_shell_and_passes_the_validator(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    matrix = {"types": ["Personal"], "codes": {"Personal": "P"}, "settings": {"Personal": {"Min": "0", "Max": "1500"}},
              "od_mapping": [{"STATUS_CODE": "NOT ODP", "DESCRIPTION": "Not on the program", "ILS_CALC": "1",
                              "CAN_OVERDRAFT": "0"}], "overrides": {}, "grids": {}, "trends": [], "triggers": [],
              "tiers": {}}
    out = sheila_deck.build(_metrics(), "9999", "Test Bank", tmp_path / "deck.pptx", codes=CODES,
                            extract_date="2026-10-26", matrix=matrix, matrix_file="9999_MatrixValidation.txt")
    texts = _texts(Presentation(str(out)))
    assert "ILS Program Analysis" in texts[0] and "Test Bank" in texts[0]
    joined = "\n".join(texts)
    for ch in sheila_deck.CHAPTERS:
        assert ch.title in joined, ch.title
    assert "Not Odp · Not on the program" in joined or "NOT ODP · Not on the program" in joined
    assert "To be completed by the CSM" in joined           # no key dates, no program details given
    assert "Aaron Burgard" not in texts[-1] and "to be confirmed" in texts[-1]   # never another CSM's card
    fails = [f for f in vd.run(str(out)) if f[0] == "FAIL"]
    assert fails == [], fails


def test_the_notice_items_give_the_baseline_and_the_waivers(tmp_path):
    rows = []
    for i in range(6):                                       # one account, six paid items in one day
        rows.append({"ILS Account ID": "1", "NSF-Overdraft Item Amount": "1.50" if i == 0 else "40",
                     "NSF-Overdraft Item Date": "9/21/2026 12:00:00 AM", "NSF-Overdraft Item Ending Balance": "-4" if i == 1 else "-50",
                     "NSF-Overdraft Item Fee Assessed": "27", "NSF-Overdraft Item Status": "PD",
                     "NSF-Overdraft Item Transaction Type": "CRD", "NSF-Overdraft Item Import ID": str(i)})
    rows.append({"ILS Account ID": "2", "NSF-Overdraft Item Amount": "100", "NSF-Overdraft Item Date": "9/22/2026 12:00:00 AM",
                 "NSF-Overdraft Item Ending Balance": "-100", "NSF-Overdraft Item Fee Assessed": "15",
                 "NSF-Overdraft Item Status": "RT", "NSF-Overdraft Item Transaction Type": "ACH",
                 "NSF-Overdraft Item Import ID": "9"})
    pd.DataFrame(rows).to_csv(tmp_path / "9999-FNF-Notices 120 Days.csv", index=False)
    n = notices.compute(tmp_path)["pgl_notices"]
    assert n["days"] == 2 and n["items"] == 7 and n["revenue"] == 6 * 27 + 15
    base = {r[0]: r for r in n["baseline"]}
    assert base["Paid (OD) items"][1] == 6 and base["Returned (NSF) items"][4] == 15
    sc = {r[0]: r for r in n["scenarios"]}
    assert sc["Daily fee cap of 4"][1:3] == [2, 54.0] and sc["Daily fee cap of 6"][1] == 0
    assert sc["Transaction de minimis $2"][1:3] == [1, 27.0]
    assert sc["Balance de minimis $5"][1:3] == [1, 27.0]


def test_a_notice_file_is_never_the_extract():
    from ils_pipeline.pre_go_live import loader
    assert loader.DUMP_RE.search("1759-FNF-Notices 120 Days.csv")
    assert not loader.DUMP_RE.search("1759_FirstCentral_PGL_20261026.csv")


def test_the_combined_grid_applies_de_minimis_before_the_cap(tmp_path):
    rows = [{"ILS Account ID": "1", "NSF-Overdraft Item Amount": "1.00" if i == 0 else "40",
             "NSF-Overdraft Item Date": "9/21/2026 12:00:00 AM", "NSF-Overdraft Item Ending Balance": "-50",
             "NSF-Overdraft Item Fee Assessed": "27", "NSF-Overdraft Item Status": "PD",
             "NSF-Overdraft Item Transaction Type": "CRD", "NSF-Overdraft Item Import ID": str(i)} for i in range(6)]
    pd.DataFrame(rows).to_csv(tmp_path / "9999-FNF-Notices.csv", index=False)
    n = notices.compute(tmp_path)["pgl_notices"]
    grid = {(r[1], r[2], r[3]): r for r in n["grid"]}
    assert grid[(4, 0, 0)][4] == 2                  # cap 4 alone waives the 5th and 6th fee
    assert grid[(4, 2, 0)][4] == 2                  # the $1 item is waived first, so the cap waives only the 6th
    assert grid[(4, 2, 5)][9] is True and grid[(0, 0, 0)][4] == 0
    assert [r[0] for r in n["per_day_dist"]] == ["6"] and n["cap_curve"][0][1] == 5
