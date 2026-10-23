"""The Transaction Intelligence cut's shell (build/ars_pipeline/build_ti_gen.py, ti/).

What is pinned: the cut's file name can never be read as a program deck, so it cannot
supersede or archive the ARS deck; the shell is found by meaning and comes out as cover,
Summit, agenda, one section per chapter, Questions, Contact; the cover and the closing line
carry the reporting month; every content slide is numbered and owes a source note; and a
built deck passes the validator with 0 FAIL.

The chapter used here is a stub. Real chapters land one per pull request.
"""
import json
import os
import sys

import pytest
from pptx import Presentation

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("build", "build/ars_pipeline", "validation", "scripts"):
    sys.path.insert(0, os.path.join(REPO, p))

import assemble_combined as AC  # noqa: E402
import build_ti_gen as G  # noqa: E402
import promote_month as PM  # noqa: E402
import validate_deck as vd  # noqa: E402
from shapes import add_table  # noqa: E402
from ti import cut, frame  # noqa: E402

TEMPLATE = os.path.join(REPO, "templates", "ars_template.pptx")
CLIENT, NAME = "9999", "Test Bank"
PACK = {"client_id": CLIENT, "client_name": NAME, "period": "2026.10", "data_month": "Sep26",
        "sources": {"odd": "9999-ODD (100126_080000).csv"}, "chapters": {}}


def _stub_build(ctx):
    s = frame.content_slide(ctx, "Where Card Spend Goes", f"Eligible card accounts, {ctx.lens.label}")
    add_table(s, 0.6, 1.8, 6.0, 1.6,
              [["Group", "Accounts"]] + [[g, f"{100 * (i + 1):,}"] for i, g in enumerate(ctx.lens.groups)],
              [3.5, 2.5])
    frame.notes(s, f"Source: {ctx.pack['sources']['odd']}, client {ctx.pack['client_id']} "
                   f"{ctx.pack['client_name']}. Stub slide for the shell test.")
    return [s]


STUB = cut.Chapter("TI_STUB", "Transaction Intelligence", "Spend · Merchants · Channels",
                   "Where card spend goes, by lens group", lambda pack, ln: [("3", "groups")],
                   _stub_build)


@pytest.fixture
def contacts(tmp_path, monkeypatch):
    lst, con = tmp_path / "csm_list.csv", tmp_path / "csm_contacts.csv"
    lst.write_text(f"client_id,client_name,csm\n{CLIENT},{NAME},Test CSM\n", encoding="utf-8")
    con.write_text("csm,title,company,address,office,cell,email,source\n"
                   "Test CSM,Client Service Manager,CSI,,,(555) 010-0001,Test.CSM@example.com,synthetic\n",
                   encoding="utf-8")
    monkeypatch.setenv("RPE_CSM_LIST", str(lst))
    monkeypatch.setenv("RPE_CSM_CONTACTS", str(con))


def _built(tmp_path, lens_key):
    prs = Presentation(TEMPLATE)
    G.build(prs, dict(PACK), lens_key, [STUB])
    out = tmp_path / cut.deck_name(CLIENT, PACK["period"], NAME, lens_key)
    G.save(prs, out)
    return out, Presentation(str(out))


# --- the file name -------------------------------------------------------------------
@pytest.mark.parametrize("lens_key", sorted(cut.LENSES))
def test_file_name_is_never_read_as_a_program_deck(lens_key):
    name = cut.deck_name(CLIENT, "2026.10", NAME, lens_key)
    assert name == f"{CLIENT}-2026.10-TI-{cut.LENSES[lens_key].tag}-{NAME} Transaction Intelligence.pptx"
    assert PM.parse_deck_name(name) is None, "promote_month must leave a TI deck where it is"
    assert PM.program_tags(name) == (), "a TI deck must never count as an ARS (or any program) deck"


def test_file_name_refuses_a_bad_period_and_an_unknown_lens():
    with pytest.raises(ValueError):
        cut.deck_name(CLIENT, "2026-10", NAME, "ars")
    with pytest.raises(SystemExit):
        cut.deck_name(CLIENT, "2026.10", NAME, "mrpc")


# --- the frame -----------------------------------------------------------------------
def test_notes_without_a_source_are_refused():
    prs = Presentation(TEMPLATE)
    s = frame.new_slide(prs)
    with pytest.raises(ValueError, match="source"):
        frame.notes(s, "Accounts by lens group.")


# --- the deck ------------------------------------------------------------------------
def test_no_chapter_means_no_deck(contacts):
    with pytest.raises(SystemExit, match="no chapter"):
        G.build(Presentation(TEMPLATE), dict(PACK), "ars", [])


def test_pack_missing_fields_stops_the_build(tmp_path):
    p = tmp_path / "pack.json"
    p.write_text(json.dumps({"client_id": CLIENT, "client_name": NAME}), encoding="utf-8")
    with pytest.raises(SystemExit, match="period, data_month, sources.odd"):
        G.load_pack(p)


@pytest.mark.parametrize("lens_key", sorted(cut.LENSES))
def test_shell_shape_months_and_validation(tmp_path, contacts, lens_key):
    out, prs = _built(tmp_path, lens_key)
    titles = [G._title(s) for s in prs.slides]
    assert len(titles) == 7, titles
    assert AC._is_cover(prs.slides[0]) and AC._is_summit(prs.slides[1], 2)
    assert titles[2].startswith("Agenda")
    assert titles[3] == "Transaction Intelligence" and titles[4] == "Where Card Spend Goes"
    assert titles[5].startswith("Questions & Discussion") and titles[6].startswith("Contact Us")

    assert vd._cover_client_and_month(prs) == (NAME, "October 2026")
    assert vd.closing_month_findings(prs) == []
    cover_text = " ".join(sh.text_frame.text for sh in prs.slides[0].shapes if sh.has_text_frame)
    assert cut.LENSES[lens_key].label in cover_text
    assert ("Invitation Checking" in cover_text) == (lens_key == "ics")

    agenda = " ".join(sh.text_frame.text for sh in prs.slides[2].shapes if sh.has_text_frame)
    assert "Transaction Intelligence" in agenda and "Account Revenue Solution" not in agenda

    pill = " ".join(sh.text_frame.text for sh in prs.slides[4].shapes if sh.has_text_frame)
    assert "September 2026 Data" in pill, "the pill carries the DATA month, not the reporting month"

    fails = [f for f in vd.run(str(out)) if f[0] == "FAIL"]
    assert fails == [], fails


def test_ars_deck_and_template_are_untouched_by_the_cut():
    """The cut adds files; it does not reach into the ARS builder or its shell."""
    src = open(os.path.join(REPO, "build", "ars_pipeline", "build_ars_gen.py"), encoding="utf-8").read()
    assert "build_ti_gen" not in src and "from ti" not in src and "import ti" not in src
