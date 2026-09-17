"""Outputs is filed by CSM — `Outputs/<CSM>/` (Aaron, 2026-09-14: "sort the Outputs folder by CSM").

Writers resolve the folder with `rpe_env.client_outputs`; readers find decks with
`rpe_env.output_decks`, which searches every CSM folder and the flat root but never
Archive/. A reader left globbing the flat root would report every deck as not built.
"""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build"), os.path.join(REPO, "scripts")]
import rpe_env as R  # noqa: E402


@pytest.fixture
def csm_list(tmp_path, monkeypatch):
    p = tmp_path / R.CSM_LIST_NAME
    p.write_text("client_id,client_name,csm\n1038,Sugar River,Aaron Burgard\n"
                 "1200,Guardians,Jordan Berkowitz\n1300,Nobody,\n", encoding="utf-8")
    monkeypatch.setattr(R, "csm_list_file", lambda: p)
    R._csm_cache.clear()
    yield p
    R._csm_cache.clear()


def test_a_client_is_filed_under_its_csm(csm_list, tmp_path):
    out = tmp_path / "Outputs"
    assert R.client_outputs("1038", root=out) == out / "Aaron Burgard"
    assert R.client_outputs(1200, root=out, create=True) == out / "Jordan Berkowitz"
    assert (out / "Jordan Berkowitz").is_dir()


def test_no_named_csm_is_unassigned_never_a_default(csm_list, tmp_path, monkeypatch):
    import build_month
    monkeypatch.setattr(build_month, "read_cashplease_roster", lambda: [])
    R._csm_cache.clear()
    out = tmp_path / "Outputs"
    assert R.client_outputs("1300", root=out) == out / R.UNASSIGNED_CSM
    assert R.client_outputs("9999", root=out) == out / R.UNASSIGNED_CSM


def test_a_cashplease_only_client_takes_the_roster_csm(csm_list, tmp_path, monkeypatch):
    import build_month
    monkeypatch.setattr(build_month, "read_cashplease_roster",
                        lambda: [{"client_id": "1131", "csm": "Aaron Burgard"},
                                 {"client_id": "1038", "csm": "Someone Else"}])
    R._csm_cache.clear()
    out = tmp_path / "Outputs"
    assert R.client_outputs("1131", root=out) == out / "Aaron Burgard"
    assert R.client_outputs("1038", root=out) == out / "Aaron Burgard", "the list wins over the roster"


def test_readers_search_every_csm_folder_and_the_root_but_not_archive(tmp_path):
    out = tmp_path / "Outputs"
    for rel in ("Aaron Burgard/1038-2026.09-ARS-Sugar River ARS Results.pptx",
                "1038-2026.08-ARS-Sugar River ARS Results.pptx",
                "Archive/1038 Sugar River/1038-2026.09-ARS-Sugar River ARS Results (superseded 2026-09-14).pptx",
                "Aaron Burgard/~$1038-2026.09-ARS-Sugar River ARS Results.pptx",
                "Jordan Berkowitz/1200-2026.09-ARS-Guardians ARS Results.pptx"):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(b"x")
    got = [p.relative_to(out).as_posix() for p in R.output_decks("1038-*.pptx", root=out)]
    assert got == ["1038-2026.08-ARS-Sugar River ARS Results.pptx",
                   "Aaron Burgard/1038-2026.09-ARS-Sugar River ARS Results.pptx"]


def test_the_delivery_dashboard_sees_a_deck_in_a_csm_folder(tmp_path):
    import deck_status as DS
    out = tmp_path / "Outputs"
    (out / "Aaron Burgard").mkdir(parents=True)
    (out / "Aaron Burgard" / "1038-2026.09-ARS-Sugar River ARS Results.pptx").write_bytes(b"x")
    got = DS.built_deck("1038", "2026.09", str(out))
    assert got and got["file"] == "1038-2026.09-ARS-Sugar River ARS Results.pptx"
    assert DS.built_deck("1038", "2026.08", str(out)) is None


def test_readers_list_each_folder_once_and_match_as_glob_did(tmp_path, monkeypatch):
    """output_decks reads each folder with one listing (2026-09-17): on the share a stat per entry is a round
    trip. Case folds on Windows as glob's did; a folder named like a deck is not a deck."""
    out = tmp_path / "Outputs"
    for rel in ("Aaron Burgard/1038-2026.09-ARS-Sugar River ARS Results.pptx",
                "Aaron Burgard/1038-2026.09-ars-lower case ARS Results.PPTX",
                ".hidden/1038-2026.09-ARS-Hidden ARS Results.pptx",
                "_Archive/1038-2026.09-ARS-Sugar River ARS Results.pptx"):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(b"x")
    (out / "Aaron Burgard" / "1038-2026.09-ARS-a folder.pptx").mkdir()
    calls = []
    real = os.stat
    monkeypatch.setattr(os, "stat", lambda *a, **kw: calls.append(a[0]) or real(*a, **kw))
    got = [p.relative_to(out).as_posix() for p in R.output_decks("1038-2026.09-ARS*.pptx", root=out)]
    want = ["Aaron Burgard/1038-2026.09-ARS-Sugar River ARS Results.pptx"]
    if os.name == "nt":
        want.insert(0, "Aaron Burgard/1038-2026.09-ars-lower case ARS Results.PPTX")
    assert sorted(got) == sorted(want)
    if os.name == "nt":
        assert calls == [], "the listing carries each entry's type; no stat per entry"
    assert R.output_decks("1038-*.pptx", root=tmp_path / "missing") == []
