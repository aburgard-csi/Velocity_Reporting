"""Slide Review: keep / delete / appendix votes and favourite stars on each program's slides, not on a client's
(Aaron, 2026-10-27, reworked 2026-10-28)."""
import http.client
import json
import os
import sys
import threading

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]
import slide_votes as SV  # noqa: E402
import ars_launcher_web as W  # noqa: E402

RPE_DECK = "1075-2026.10-ARS-ICS-MRPC-Austin Bank Results.pptx"
ARS_DECK = "1204-2026.10-ARS-FSB Michigan ARS Results.pptx"
TI_DECK = "1075-2026.10-TI-ARS-Austin Bank Transaction Intelligence.pptx"
COMP_DECK = "1075-2026.10-COMP-Austin Bank ARS Companion.pptx"


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    SV._files.clear()
    SV._slides_cache.clear()
    SV._disk_cache = None
    return tmp_path


def make_deck(path, titles, source="ODD extract, 10/05/26"):
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    for t in titles:
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1)).text_frame.text = t
        s.notes_slide.notes_text_frame.text = f"Source: {source}. Selection: all accounts."
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))
    return path


COMBINED = ["Austin Bank\nExecutive Review  •  October 2026", "Agenda",
            "Account Revenue Solution", "Account Retention", "Reg E Opt-In",
            "Invitation Checking System", "Power of Referrals",
            "MyRewards Premium Cards", "Enrollments by Channel",
            "Questions & Discussion", "Contact Us", "Appendix: Take Rate by Branch"]


def vote(program="ARS", slide=1, title="Account Retention", v="keep", voter="aaron", **kw):
    return SV.write_vote(program, slide, title, v, voter=voter, **kw)


# ---------------------------------------------------------------- the deck name and the slide titles

def test_a_deck_name_gives_its_client_period_kind_and_family():
    assert SV.parse_deck(RPE_DECK) == ("1075", "2026.10", "ARS-ICS-MRPC", "RPE")
    assert SV.parse_deck(TI_DECK) == ("1075", "2026.10", "TI-ARS", "TI")
    assert SV.parse_deck(COMP_DECK) == ("1075", "2026.10", "COMP", "COMP")
    assert SV.parse_deck("notes.pptx") is None and SV.parse_deck("1075-2026.10-XYZ-Bank.pptx") is None


def test_the_programs_a_deck_kind_carries():
    assert SV.deck_programs("ARS-ICS-MRPC") == ["ARS", "ICS", "MRPC"]
    assert SV.deck_programs("ICS-CP") == ["ICS", "CP"]
    assert SV.deck_programs("TI-ICS") == ["TI"] and SV.deck_programs("COMP") == ["COMP"]


def test_a_combined_deck_is_split_into_programs_by_its_dividers(tmp_path):
    slides = SV.deck_slides(make_deck(tmp_path / RPE_DECK, COMBINED))
    assert [(s["title"], s["program"]) for s in slides] == [
        ("Austin Bank", "Shared"), ("Agenda", "Shared"), ("Account Revenue Solution", "Shared"),
        ("Account Retention", "ARS"), ("Reg E Opt-In", "ARS"), ("Invitation Checking System", "Shared"),
        ("Power of Referrals", "ICS"), ("MyRewards Premium Cards", "Shared"), ("Enrollments by Channel", "MRPC"),
        ("Questions & Discussion", "Shared"), ("Contact Us", "Shared"), ("Appendix: Take Rate by Branch", "ARS")]


def test_a_single_program_deck_is_all_its_programs_apart_from_the_shared_slides(tmp_path):
    slides = SV.deck_slides(make_deck(tmp_path / ARS_DECK, ["FSB Michigan\nExecutive Review  •  October 2026",
                                                            "Account Retention", "Questions & Discussion"]))
    assert [s["program"] for s in slides] == ["Shared", "ARS", "Shared"]
    ti = SV.deck_slides(make_deck(tmp_path / TI_DECK, ["Where the money goes"]))
    assert ti[0]["program"] == "TI" and ti[0]["source"].startswith("ODD extract")


def test_a_title_is_matched_across_clients_by_its_words_not_its_figures():
    a = SV.norm_title("60% of transacting personal accounts send $164.8M a year to Austin Bank", "Austin Bank")
    b = SV.norm_title("47% of transacting personal accounts send $12.1M a year to Foothills CU", "Foothills CU")
    assert a == b == "#% of transacting personal accounts send $#m a year to <client>"
    assert SV.norm_title("Account Retention") == SV.norm_title("  account  retention ")


# ---------------------------------------------------------------- the record

def test_a_vote_is_its_own_file_and_is_never_rewritten(root):
    d1 = vote(v="keep")
    d2 = vote(v="delete")
    files = sorted(os.listdir(root / "Build Artifacts" / "slide_votes"))
    assert len(files) == 2 and not any(f.endswith(".part") for f in files)
    assert d1["at"] <= d2["at"] and d1["key"] == d2["key"] == "ARS|account retention"
    stored = json.loads((root / "Build Artifacts" / "slide_votes" / files[0]).read_text(encoding="utf-8"))
    assert {"voter", "program", "slide", "title", "key", "vote", "star", "comment", "at"} <= set(stored)
    assert "client" not in stored


def test_the_newest_vote_per_voter_and_slide_wins_whatever_the_deck(root):
    vote(v="keep", voter="aaron")
    vote(v="delete", voter="aaron")                      # changed their mind
    vote(v="appendix", voter="sheila")
    vote(program="TI", v="keep", voter="aaron", title="Where the money goes")      # another program
    cur = SV.latest(SV.read_votes())
    assert {(v["voter"], v["program"], v["vote"]) for v in cur} == {
        ("aaron", "ARS", "delete"), ("sheila", "ARS", "appendix"), ("aaron", "TI", "keep")}


def test_a_star_is_kept_beside_the_vote_and_can_stand_alone(root):
    vote(v="keep", star=True, comment="clients like it")
    vote(title="Reg E Opt-In", v="", star=True)                     # starred, not voted
    held = SV.mine(SV.read_votes(), "aaron", "ARS")
    assert held["ARS|account retention"]["star"] and held["ARS|account retention"]["vote"] == "keep"
    assert held["ARS|reg e opt-in"]["star"] and held["ARS|reg e opt-in"]["vote"] == ""
    vote(v="keep", star=False)                                      # un-starred
    assert not SV.mine(SV.read_votes(), "aaron", "ARS")["ARS|account retention"]["star"]


def test_a_damaged_vote_file_is_skipped_not_fatal(root):
    vote()
    d = root / "Build Artifacts" / "slide_votes"
    (d / "20260101T000000000000-x-1-abcd.json").write_text("{not json", encoding="utf-8")
    (d / "20260101T000000000001-x-1-abcd.json").write_text(json.dumps({"vote": "maybe"}), encoding="utf-8")
    assert len(SV.read_votes()) == 1


def test_a_first_round_vote_per_client_is_read_as_its_programs_vote(root):
    d = root / "Build Artifacts" / "slide_votes"
    d.mkdir(parents=True)
    old = {"v": 1, "voter": "aaron", "client": "1204", "period": "2026.10", "kind": "ARS", "family": "RPE",
           "deck": ARS_DECK, "slide": 4, "title": "Account Retention", "key": "RPE|account retention",
           "vote": "delete", "comment": "", "at": "2026-10-27T10:00:00.000000Z"}
    (d / "20261027T100000000000-aaron-1204-abcd.json").write_text(json.dumps(old), encoding="utf-8")
    combined = dict(old, kind="ARS-ICS-MRPC", client="1075", at="2026-10-27T10:01:00.000000Z")
    (d / "20261027T100100000000-aaron-1075-abcd.json").write_text(json.dumps(combined), encoding="utf-8")
    rows = SV.aggregate(SV.read_votes())
    assert [(r["program"], r["delete"]) for r in rows] == [("ARS", 1)]       # the combined deck's one cannot be placed


def test_votes_count_across_voters_and_stars_by_program(root):
    vote(voter="aaron", v="delete")
    vote(voter="sheila", v="delete", star=True)
    vote(voter="bob", v="keep", comment="clients ask about it")
    vote(program="TI", voter="aaron", v="keep", title="Account Retention")     # TI is its own program
    rows = SV.aggregate(SV.read_votes())
    ars = next(r for r in rows if r["program"] == "ARS")
    assert (ars["keep"], ars["delete"], ars["appendix"], ars["stars"], ars["total"]) == (1, 2, 0, 1, 3)
    assert ars["voters"] == ["aaron", "bob", "sheila"] and ars["leading"] == "delete" and "clients" not in ars
    assert ars["comments"][0]["text"] == "clients ask about it"
    assert len(rows) == 2 and [r["program"] for r in SV.aggregate(SV.read_votes(), "TI")] == ["TI"]


def test_the_slides_most_likely_to_go_come_first_and_a_tie_is_split(root):
    for t, vs in (("Keeper", ["keep", "keep"]), ("Doomed", ["delete", "delete"]), ("Contested", ["delete", "keep"])):
        for i, v in enumerate(vs):
            vote(title=t, v=v, voter=f"v{i}")
    rows = SV.aggregate(SV.read_votes())
    assert [r["title"] for r in rows] == ["Doomed", "Contested", "Keeper"]
    assert rows[1]["leading"] == "split"


def test_the_summary_exports_as_csv(root):
    vote(v="appendix", star=True, comment="for the appendix, said Sheila")
    text = SV.summary_csv(SV.aggregate(SV.read_votes()))
    assert text.splitlines()[0] == "Program,Slide,Keep,Delete,Appendix,Stars,Leading,Voters,Comments"
    assert "ARS,Account Retention,0,0,1,1,appendix,1" in text and "for the appendix" in text


# ---------------------------------------------------------------- what is refused

@pytest.mark.parametrize("kw", [
    {"vote": "maybe"}, {"vote": ""}, {"program": "XYZ"}, {"program": ""}, {"title": ""}, {"title": "x" * 201},
    {"slide": 0}, {"slide": "one"}, {"comment": "c" * 501}])
def test_a_bad_vote_is_refused(root, kw):
    args = {"program": "ARS", "slide": 1, "title": "Overview", "vote": "keep", "comment": ""}
    args.update(kw)
    with pytest.raises(SV.VoteError):
        SV.check_vote(**args)
    assert not (root / "Build Artifacts" / "slide_votes").exists() or not os.listdir(root / "Build Artifacts" / "slide_votes")


# ---------------------------------------------------------------- Sheila's API

@pytest.fixture
def server(root, monkeypatch):
    monkeypatch.setattr(W, "clients_doc", lambda: {"period": "2026.10", "clients": [{"id": "1075", "name": "Austin Bank"}]})
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    monkeypatch.setattr(SV, "whoami", lambda: "aaron")
    W._selected["period"] = None
    out = root / "Outputs" / "Aaron Burgard"
    make_deck(out / RPE_DECK, COMBINED)
    make_deck(out / TI_DECK, ["Where the money goes"])
    make_deck(out / "_Archive" / "1075 Austin Bank" / "1075-2026.10-ARS-Austin Bank Old.pptx", ["Old"])
    srv = W.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def call(port, method, path, body=None, token=True):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Token"] = W.TOKEN
    c.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


def jcall(*a, **k):
    status, data = call(*a, **k)
    return status, json.loads(data)


def test_the_votes_api_needs_the_token(server):
    assert call(server, "GET", "/api/votes/programs", token=False)[0] == 403
    assert call(server, "POST", "/api/votes/vote", {"program": "ARS"}, token=False)[0] == 403
    assert call(server, "GET", "/api/votes/summary", token=False)[0] == 403


def test_the_tab_lists_each_programs_slides_from_the_build_never_from_a_deck(server, monkeypatch):
    """Aaron, 2026-10-29: "the decks all carry the same slides, because they're all built using the same
    processes. We shouldn't need to scan the decks." The lists are build/slide_inventory.py; Outputs is
    never read, so the tab opens at once and an ICS list is the full workbook shape."""
    monkeypatch.setattr(W.R, "output_decks", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Outputs was read")))
    status, doc = jcall(server, "GET", "/api/votes/programs")
    assert status == 200 and doc["period"] == "2026.10" and doc["me"] == "aaron"
    counts = {p["id"]: p["slides"] for p in doc["programs"]}
    assert counts["ARS"] > 40 and counts["ICS"] > 20 and counts["MRPC"] == 8 and counts["CP"] == 6
    assert counts["TI"] > 100 and counts["COMP"] > 30
    assert "templates" in doc["from"]
    status, doc = jcall(server, "GET", "/api/votes/program?program=ICS")
    titles = [s["title"] for s in doc["slides"]]
    assert "ICS Financial Summary" in titles and "Appendix: Monthly Detail" in titles
    assert doc["slides"][0]["mine"] is None and doc["slides"][0]["key"].startswith("ICS|")
    assert jcall(server, "GET", "/api/votes/program?program=XYZ")[0] == 400


def test_a_vote_and_a_star_come_back_together_and_each_keeps_the_other(server):
    base = {"program": "ARS", "slide": 3, "title": "Program Overview"}
    assert jcall(server, "POST", "/api/votes/vote", dict(base, vote="delete", comment="too dense"))[0] == 200
    assert jcall(server, "POST", "/api/votes/vote", dict(base, vote="delete", star=True, comment="too dense"))[0] == 200
    doc = jcall(server, "GET", "/api/votes/program?program=ARS")[1]
    mine = {s["title"]: s["mine"] for s in doc["slides"]}
    assert mine["Program Overview"] == {"vote": "delete", "star": True, "comment": "too dense"} and mine["Excluded Accounts"] is None
    progs = jcall(server, "GET", "/api/votes/programs")[1]["programs"]
    assert (progs[0]["voted"], progs[0]["starred"]) == (1, 1)


def test_a_vote_for_a_slide_not_in_the_list_is_refused_and_nothing_is_written(server):
    base = {"program": "ARS", "slide": 1, "vote": "keep"}
    assert jcall(server, "POST", "/api/votes/vote", dict(base, title="The Power of Referrals"))[0] == 409   # an ICS slide
    assert jcall(server, "POST", "/api/votes/vote", dict(base, title="Program Overview", vote="nope"))[0] == 400
    assert jcall(server, "POST", "/api/votes/vote", dict(base, title="Program Overview", program="XYZ"))[0] == 400
    assert SV.read_votes() == []


def test_the_summary_and_the_export_are_per_program_across_every_voter(server):
    for who, v in (("aaron", "delete"), ("sheila", "appendix")):
        SV.write_vote("ARS", 1, "Account Retention", v, voter=who, star=(who == "sheila"))
    status, doc = jcall(server, "GET", "/api/votes/summary")
    assert status == 200 and doc["votes"] == 2 and doc["voters"] == 2 and doc["stars"] == 1
    assert doc["rows"][0]["title"] == "Account Retention" and (doc["rows"][0]["delete"], doc["rows"][0]["appendix"]) == (1, 1)
    assert jcall(server, "GET", "/api/votes/summary?program=TI")[1]["rows"] == []
    status, data = call(server, "GET", "/api/votes/export")
    assert status == 200 and data.decode("utf-8").startswith("Program,Slide")


# ---------------------------------------------------------------- the page

def _between(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


def test_the_page_has_a_slide_review_tab_wired_into_the_router():
    import sheila_hub as H
    page = H.PAGE
    assert page.count('data-tab="votes" href="#votes"') == 2, "the sidebar and the phone bar, to its own address"
    assert page.count('id="v-votes"') == 1 and 'registerTab("votes"' in page and "sheila_hub_votes" in H.TAB_MODULES
    assert "<style>" in page and page.index("registerTab(\"votes\"") < page.rindex("</script>")


def test_the_page_is_not_tied_to_a_client():
    import sheila_hub as H
    js = _between(H.PAGE, "// ------------------------------------------------------------ Slide Review", "registerTab(\"votes\"")
    assert "V.client" not in js and "/api/votes/clients" not in js and "/api/votes/decks" not in js
    assert "/api/votes/program?program=" in js


def test_a_vote_button_sends_the_slides_title_and_number_and_the_star_with_the_vote():
    import sheila_hub as H
    send = _between(H.PAGE, "async function send(i, patch)", "function paintRow(i)")
    for part in ('"/api/votes/vote"', "slide: s.n", "title: s.title", "star: next.star", "vote: next.vote"):
        assert part in send
    assert 'aria-pressed="${m.vote === v}"' in H.PAGE and 'class="star"' in H.PAGE and "Favorite slide" in H.PAGE
    assert "Keep" in H.PAGE and "Appendix" in H.PAGE


def test_the_vote_buttons_use_the_hubs_colours_not_an_accent():
    import sheila_hub as H
    css = _between(H.PAGE, "button.vb{", "input.vc{")
    assert "var(--good-soft)" in css and "var(--bad-soft)" in css and "var(--orange)" not in H.PAGE and "#F47A29" not in H.PAGE.upper()
