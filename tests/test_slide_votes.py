"""Slide Review: the keep / delete / appendix votes on every deck's slides (Aaron, 2026-10-27)."""
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
TI_DECK = "1075-2026.10-TI-ARS-Austin Bank Transaction Intelligence.pptx"
COMP_DECK = "1075-2026.10-COMP-Austin Bank ARS Companion.pptx"


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    SV._files.clear()
    SV._slides_cache.clear()
    W._votes_listing.update(at=0.0, period=None, doc=None)
    return tmp_path


def make_deck(path, titles, source="ODD extract, 10/05/26"):
    from pptx import Presentation
    prs = Presentation()
    for t in titles:
        s = prs.slides.add_slide(prs.slide_layouts[5])
        s.shapes.title.text = t
        s.notes_slide.notes_text_frame.text = f"Source: {source}. Selection: all accounts."
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))
    return path


def vote(deck=RPE_DECK, slide=1, title="Account Retention", v="keep", voter="aaron", client="1075", **kw):
    return SV.write_vote(client, deck, slide, title, v, voter=voter, **kw)


# ---------------------------------------------------------------- the deck name and the slide titles

def test_a_deck_name_gives_its_client_period_kind_and_family():
    assert SV.parse_deck(RPE_DECK) == ("1075", "2026.10", "ARS-ICS-MRPC", "RPE")
    assert SV.parse_deck("1204-2026.08-ARS-FSB Michigan ARS Results.pptx") == ("1204", "2026.08", "ARS", "RPE")
    assert SV.parse_deck(TI_DECK) == ("1075", "2026.10", "TI-ARS", "TI")
    assert SV.parse_deck("1075-2026.10-TI-ICS-Austin Bank Transaction Intelligence.pptx")[2:] == ("TI-ICS", "TI")
    assert SV.parse_deck(COMP_DECK) == ("1075", "2026.10", "COMP", "COMP")
    assert SV.parse_deck("1632-2026.10-ICS-CP-WesBanco Bank Results.pptx")[2] == "ICS-CP"
    assert SV.parse_deck("notes.pptx") is None and SV.parse_deck("1075-2026.10-XYZ-Bank.pptx") is None


def test_titles_are_read_in_order_with_the_source_line(tmp_path):
    deck = make_deck(tmp_path / RPE_DECK, ["Overview", "Account Retention", "Reg E Opt-In"])
    slides = SV.deck_slides(deck)
    assert [s["title"] for s in slides] == ["Overview", "Account Retention", "Reg E Opt-In"]
    assert [s["n"] for s in slides] == [1, 2, 3]
    assert slides[0]["source"].startswith("ODD extract, 10/05/26")


def test_a_slide_with_no_title_placeholder_uses_its_first_text_shape(tmp_path):
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text_frame.text = "Where the Balances Sit"
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(str(tmp_path / RPE_DECK))
    assert [x["title"] for x in SV.deck_slides(tmp_path / RPE_DECK)] == ["Where the Balances Sit", "(untitled)"]


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
    assert d1["at"] <= d2["at"] and d1["key"] == d2["key"] == "RPE|account retention"
    stored = json.loads((root / "Build Artifacts" / "slide_votes" / files[0]).read_text(encoding="utf-8"))
    assert {"voter", "client", "period", "kind", "family", "deck", "slide", "title", "key", "vote", "comment", "at"} <= set(stored)


def test_the_newest_vote_per_voter_slide_and_deck_kind_wins(root):
    vote(v="keep", voter="aaron")
    vote(v="delete", voter="aaron")                      # changed their mind
    vote(v="appendix", voter="sheila")
    vote(v="keep", voter="aaron", deck=TI_DECK, title="Where the money goes")   # another deck kind
    cur = SV.latest(SV.read_votes())
    assert len(cur) == 3
    assert {(v["voter"], v["kind"], v["vote"]) for v in cur} == {
        ("aaron", "ARS-ICS-MRPC", "delete"), ("sheila", "ARS-ICS-MRPC", "appendix"), ("aaron", "TI-ARS", "keep")}


def test_a_voters_current_votes_on_a_deck_come_back_by_title(root):
    vote(title="Overview", v="keep", comment="needed")
    vote(title="Account Retention", v="delete", voter="sheila")
    held = SV.mine(SV.read_votes(), "aaron", "1075", RPE_DECK)
    assert list(held) == ["Overview"] and held["Overview"]["comment"] == "needed"


def test_a_damaged_vote_file_is_skipped_not_fatal(root):
    vote()
    d = root / "Build Artifacts" / "slide_votes"
    (d / "20260101T000000000000-x-1-abcd.json").write_text("{not json", encoding="utf-8")
    (d / "20260101T000000000001-x-1-abcd.json").write_text(json.dumps({"vote": "maybe"}), encoding="utf-8")
    assert len(SV.read_votes()) == 1


def test_votes_count_across_clients_voters_and_deck_kinds_of_one_family(root):
    vote(client="1075", voter="aaron", v="delete")
    vote(client="1075", voter="sheila", v="delete")
    vote(client="1204", voter="aaron", v="keep", deck="1204-2026.10-ARS-FSB Michigan ARS Results.pptx", comment="client asks about it")
    vote(client="1075", voter="aaron", v="keep", deck=TI_DECK, title="Account Retention")     # TI is its own family
    rows = SV.aggregate(SV.read_votes())
    rpe = next(r for r in rows if r["family"] == "RPE")
    assert (rpe["keep"], rpe["delete"], rpe["appendix"], rpe["total"]) == (1, 2, 0, 3)
    assert rpe["clients"] == ["1075", "1204"] and rpe["voters"] == ["aaron", "sheila"]
    assert rpe["kinds"] == ["ARS", "ARS-ICS-MRPC"] and rpe["leading"] == "delete"
    assert rpe["comments"][0]["text"] == "client asks about it"
    assert len(rows) == 2 and [r["family"] for r in SV.aggregate(SV.read_votes(), "TI")] == ["TI"]


def test_the_slides_most_likely_to_go_come_first_and_a_tie_is_split(root):
    for t, vs in (("Keeper", ["keep", "keep"]), ("Doomed", ["delete", "delete"]), ("Contested", ["delete", "keep"])):
        for i, v in enumerate(vs):
            vote(title=t, v=v, voter=f"v{i}")
    rows = SV.aggregate(SV.read_votes())
    assert [r["title"] for r in rows] == ["Doomed", "Contested", "Keeper"]
    assert rows[1]["leading"] == "split"


def test_the_summary_exports_as_csv(root):
    vote(v="appendix", comment="for the appendix, said Sheila")
    text = SV.summary_csv(SV.aggregate(SV.read_votes()))
    assert text.splitlines()[0].startswith("Deck family,Slide,Keep,Delete,Appendix")
    assert "Account Retention,0,0,1,appendix,1,1,ARS-ICS-MRPC" in text and "for the appendix" in text


# ---------------------------------------------------------------- what is refused

@pytest.mark.parametrize("kw", [
    {"vote": "maybe"}, {"vote": ""}, {"client": "10x"}, {"title": ""}, {"title": "x" * 201}, {"slide": 0},
    {"slide": "one"}, {"comment": "c" * 501}, {"deck": "1204-2026.10-ARS-FSB Michigan ARS Results.pptx"},
    {"deck": "../Outputs/" + RPE_DECK}, {"deck": "notes.pptx"}])
def test_a_bad_vote_is_refused(root, kw):
    args = {"client": "1075", "deck": RPE_DECK, "slide": 1, "title": "Overview", "vote": "keep", "comment": ""}
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
    make_deck(root / "Outputs" / "Aaron Burgard" / RPE_DECK, ["Overview", "Account Retention", "Reg E Opt-In"])
    make_deck(root / "Outputs" / "Aaron Burgard" / TI_DECK, ["Where the money goes"])
    make_deck(root / "Outputs" / "Aaron Burgard" / "_Archive" / "1075 Austin Bank" / "1075-2026.10-ARS-Austin Bank Old.pptx", ["Old"])
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
    assert call(server, "GET", "/api/votes/clients", token=False)[0] == 403
    assert call(server, "POST", "/api/votes/vote", {"client": "1075"}, token=False)[0] == 403
    assert call(server, "GET", "/api/votes/summary", token=False)[0] == 403


def test_the_tab_lists_every_deck_in_outputs_but_never_an_archived_one(server):
    status, doc = jcall(server, "GET", "/api/votes/clients")
    assert status == 200 and doc["period"] == "2026.10" and doc["me"] == "aaron"
    assert [c["id"] for c in doc["clients"]] == ["1075"] and doc["clients"][0]["name"] == "Austin Bank"
    assert [d["kind"] for d in doc["clients"][0]["decks"]] == ["ARS-ICS-MRPC", "TI-ARS"]
    status, doc = jcall(server, "GET", "/api/votes/decks?client=1075")
    assert status == 200 and [d["family"] for d in doc["decks"]] == ["RPE", "TI"]
    assert jcall(server, "GET", "/api/votes/decks?client=10x")[0] == 400


def test_a_deck_comes_back_with_the_voters_own_votes(server):
    body = {"client": "1075", "deck": RPE_DECK, "slide": 2, "title": "Account Retention", "vote": "delete", "comment": "too dense"}
    assert jcall(server, "POST", "/api/votes/vote", body)[0] == 200
    status, doc = jcall(server, "GET", f"/api/votes/deck?client=1075&deck={RPE_DECK.replace(' ', '%20')}")
    assert status == 200 and [s["title"] for s in doc["slides"]] == ["Overview", "Account Retention", "Reg E Opt-In"]
    assert doc["slides"][1]["mine"] == {"vote": "delete", "comment": "too dense"} and doc["slides"][0]["mine"] is None
    assert doc["slides"][0]["source"].startswith("ODD extract")


def test_a_vote_from_a_stale_page_is_refused_and_nothing_is_written(server, root):
    base = {"client": "1075", "deck": RPE_DECK, "vote": "keep"}
    assert jcall(server, "POST", "/api/votes/vote", dict(base, slide=2, title="Reg E Opt-In"))[0] == 409   # the deck changed
    assert jcall(server, "POST", "/api/votes/vote", dict(base, slide=9, title="Overview"))[0] == 409
    assert jcall(server, "POST", "/api/votes/vote", dict(base, slide=1, title="Overview", vote="nope"))[0] == 400
    assert jcall(server, "POST", "/api/votes/vote", dict(base, deck="1075-2026.10-ARS-Austin Bank Old.pptx", slide=1, title="Old"))[0] == 404
    assert jcall(server, "POST", "/api/votes/vote", dict(base, deck="../../x.pptx", slide=1, title="Overview"))[0] == 400
    assert SV.read_votes() == []


def test_the_summary_and_the_export_read_every_voters_votes(server):
    for who, v in (("aaron", "delete"), ("sheila", "appendix")):
        SV.write_vote("1075", RPE_DECK, 2, "Account Retention", v, voter=who)
    status, doc = jcall(server, "GET", "/api/votes/summary")
    assert status == 200 and doc["votes"] == 2 and doc["voters"] == 2
    assert doc["rows"][0]["title"] == "Account Retention" and (doc["rows"][0]["delete"], doc["rows"][0]["appendix"]) == (1, 1)
    assert jcall(server, "GET", "/api/votes/summary?family=TI")[1]["rows"] == []
    status, data = call(server, "GET", "/api/votes/export")
    assert status == 200 and data.decode("utf-8").startswith("Deck family,Slide")


# ---------------------------------------------------------------- the page

def _between(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


def test_the_page_has_a_slide_review_tab_wired_into_the_modes():
    page = W.PAGE
    assert 'id="tab-votes" aria-selected="false">Slide Review</button>' in page
    assert 'm === "reported" || m === "votes");' in page and '"reported", "votes"])' in page
    assert 'else if (m === "votes") votesView(focus);' in page
    assert 'MODE === "votes" ? votesPick : select' in page
    assert page.count('id="tab-votes"') == 1 and "<style>" in page and page.index("votesView") < page.rindex("</script>")


def test_a_vote_button_sends_the_slides_title_and_number_with_the_vote():
    send = _between(W.PAGE, "async function votesSend", "async function votesSummary")
    for part in ('"/api/votes/vote"', "slide: +tr.dataset.n", "title: tr.dataset.title", "vote, comment"):
        assert part in send
    assert 'aria-pressed="${m.vote === v}"' in W.PAGE and "Keep" in W.PAGE and "Appendix" in W.PAGE


def test_the_vote_buttons_use_the_action_buttons_toned_down_edge():
    css = _between(W.PAGE, "button.vb,button.vt{", "button.vb:hover")
    assert "inset 0 1px 0 rgba(255,255,255,.16)" in css and "0 6px 16px" not in W.PAGE


def test_the_splice_fails_loudly_when_the_page_changes_under_it():
    import slide_review_ui as UI
    with pytest.raises(RuntimeError, match="anchor not found"):
        UI.install("<style></style><script></script>")
