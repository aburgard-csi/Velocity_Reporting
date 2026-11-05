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
    from ils_pipeline.pre_go_live import insights
    m.update(insights.compute(_df(), CODES, None, od_fee=27.0, extract_date="2026-10-26"))   # a one-account business base
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
    assert "Where the Core Limit Misses — Business" in joined and "Core Limits vs ILS — Business" not in joined
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


def test_the_fee_slides_name_the_notice_window_not_a_year():
    nt = {"first": "2026-07-01", "last": "2026-10-27", "days": 119}
    assert sheila_deck.window_text(nt) == "Jul 1 – Oct 27, 2026: 119 days (3.9 months)"
    assert sheila_deck.window_pill(nt) == "Notices 7/1–10/27/26"
    across = {"first": "2025-12-15", "last": "2026-02-14", "days": 62}
    assert sheila_deck.window_text(across) == "Dec 15, 2025 – Feb 14, 2026: 62 days (2.0 months)"


def test_every_od_code_can_be_counted_eligible_and_the_slide_says_why():
    from ils_pipeline.pre_go_live import codes as codes_mod
    df = _df()
    assert codes_mod.all_values(df, "od_eligible") == ["ODP", "CUST OPIN", "NOT ODP"]
    t = review.compute(df, dict(CODES, od_eligible=codes_mod.all_values(df, "od_eligible")))["pgl_review"]
    note = sheila_deck._od_note(t["personal_od"], "personal", True)
    assert note.startswith("Every OD status is counted as eligible") and "mass maintenance" in note
    assert "sit on ineligible" not in note


def test_the_agenda_badges_do_not_touch(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    out = sheila_deck.build(_metrics(), "9999", "Test Bank", tmp_path / "deck.pptx", codes=CODES,
                            extract_date="2026-10-26")
    agenda = Presentation(str(out)).slides[2]
    badges = sorted((sh for sh in agenda.shapes if sh.shape_type == 1 and not sh.text_frame.text.strip()),
                    key=lambda sh: sh.top)
    assert len(badges) == len(sheila_deck.CHAPTERS) + 1
    assert all(a.top + a.height < b.top for a, b in zip(badges, badges[1:]))
    assert badges[-1].top + badges[-1].height < 6.78 * 914400          # clear of the logo


def test_the_timeline_reads_the_csms_plan_and_falls_back_to_the_standard_milestones(tmp_path, monkeypatch):
    rows = sheila_deck.timeline_rows([["Project Kickoff meeting", "10/29/25 | done"], ["File development complete",
                                      "11/3/25 | at risk"], ["Weekly meetings begin", "In Process"], ["ILS Go Live", ""]])
    assert rows == [("Project Kickoff meeting", "10/29/25", "done"), ("File development complete", "11/3/25", "risk"),
                    ("Weekly meetings begin", "In Process", ""), ("ILS Go Live", "TBD", "")]
    assert [m for m, _, _ in sheila_deck.timeline_rows([])] == sheila_deck.MILESTONES
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    out = sheila_deck.build(_metrics(), "9999", "Test Bank", tmp_path / "deck.pptx", codes=CODES,
                            extract_date="2026-10-26", inputs={"key_dates": [["ILS Pre Go-Live Analysis", "12/19/25"],
                                                                             ["Project Kickoff meeting", "10/29/25 | done"]]})
    prs = Presentation(str(out))
    s = next(s for s in prs.slides if any(sh.has_text_frame and sh.text_frame.text.startswith(
        "ILS Configuration & Project Timeline") for sh in s.shapes))
    tb = next(sh for sh in s.shapes if sh.has_table).table
    assert [tb.cell(i, 0).text for i in range(3)] == ["Milestone", "ILS Pre Go-Live Analysis", "Project Kickoff meeting"]
    assert tb.cell(1, 0).fill.fore_color.rgb == sheila_deck.add_table.__globals__["ORANGE"]    # this meeting
    assert tb.cell(2, 2).text.endswith("Complete")
    # the timeline sits at the end, in the summary chapter, not on the first chapter's opening
    titles = [sheila_deck._title(x) for x in prs.slides]
    assert titles.index("Questions & Discussion") - titles.index("ILS Configuration & Project Timeline") <= 2
