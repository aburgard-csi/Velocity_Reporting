"""A slide with no data is left out of the deck (Aaron, 2026-11-22: "skip a slide if it doesn't have data").

It used to stay with a sentence saying the data was not carried (CLAUDE.md, "Never drop slides automatically"). The rule
now: the slide is not in the deck, the build log names it and why, nothing is zeroed, and the package stays sound (the
freed part name is never handed to a slide added later). The ARS age profile is checked on a real build in
test_golden_deck.py; the peer slides in test_peer_slide.py.
"""
import io
import os
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build"), str(REPO / "build" / "ars_pipeline"), str(REPO / "validation")]

from pptx import Presentation                                    # noqa: E402

import shapes as SH                                              # noqa: E402


def _deck():
    return Presentation(str(REPO / "templates" / "ars_template.pptx"))


def _parts(buf):
    with zipfile.ZipFile(buf) as z:
        names = z.namelist()
    return [n for n in names if n.startswith("ppt/slides/slide") and n.endswith(".xml")]


def test_a_dropped_slide_is_not_written_and_a_slide_added_after_cannot_reuse_its_name(tmp_path):
    import validate_deck as vd
    prs = _deck()
    n = len(prs.slides)
    gone = list(prs.slides)[3]
    title = SH.slide_title(gone)
    SH.drop_slide(prs, gone)
    assert len(prs.slides) == n - 1 and title not in [SH.slide_title(s) for s in prs.slides][3:4]
    SH.blank_slide(prs, prs.slides[0])                           # the Summit is added this way after the drops
    out = tmp_path / "d.pptx"
    prs.save(str(out))
    assert len(_parts(str(out))) == n
    assert vd.package_findings(str(out)) == []
    assert len(Presentation(str(out)).slides) == n


def test_a_registered_no_data_slide_is_dropped_and_named_in_the_log():
    prs = _deck()
    n = len(prs.slides)
    s = list(prs.slides)[5]
    title = SH.slide_title(s).split("\n")[0]
    SH.mark_no_data(s, "this extract carries no average balances")
    other = _deck()                                              # the same slide id in ANOTHER deck is not touched
    seen = []
    assert SH.drop_no_data_slides(other, log=seen.append) == [] and len(other.slides) == n
    got = SH.drop_no_data_slides(prs, log=seen.append)
    assert got == [(title, "this extract carries no average balances")] and len(prs.slides) == n - 1
    assert seen == [f"slide left out (no data): {title} - this extract carries no average balances"]


def test_an_opt_in_view_with_no_data_registers_itself():
    import combined_insight_slides as CIS
    prs = _deck()
    s = CIS._new_slide(prs, prs.slides[0])
    CIS._no_data_caption(s, "The book's own rates are not available for this period, so the sizing is not shown.")
    assert SH.drop_no_data_slides(prs, log=lambda m: None)[0][1].startswith("The book's own rates are not available")


def test_the_cashplease_volume_slide_is_left_out_when_the_workbook_has_no_loans(tmp_path, capsys):
    sys.path.insert(0, str(REPO / "build" / "cashplease_pipeline"))
    import build_cp_gen as G
    prs = Presentation(str(REPO / "templates" / "cashplease_template.pptx"))
    d = {"client_id": "9999", "client_name": "Union Financial", "monthly": [], "daily": [],
         "source_file": "CashPleaseSummary.xlsx", "sheet_name": "Union Financial", "report_generated": "10/11/2026 6:35:45 AM"}
    assert G.slide_volume(prs, d, "PTD · test", str(tmp_path)) is None
    assert "slide left out (no data): CashPlease Loan Volume by Month" in capsys.readouterr().out


def test_the_rule_is_recorded_where_the_old_one_was():
    text = " ".join((REPO / "CLAUDE.md").read_text(encoding="utf-8").split())
    assert "skip a slide if it doesn't have data" in text
    assert "Never drop slides automatically.** The deck keeps its full slide set" not in text
