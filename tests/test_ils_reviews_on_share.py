"""The ILS review PDFs on the share (Aaron, 2026-11-06: "put ILS review PDFs on the share").

`scripts/land_ils_reviews.py` copies each client's newest `<id>-<yyyy.mm>-ILS-<Client> ILS Review.pdf` from the Clients
library into `Inputs/ILS Reviews/<id>/` and reads it into the pack Live Review's ILS section shows. These tests pin: the
folder is a kind that nothing scans, which review is the newest, that landing is copy-only (nothing deleted or
overwritten, a half-written copy never takes the name), and that a review that cannot be read is reported with no pack.

The PDFs here are empty stand-ins and the reader is stubbed: no real review, no client data.
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]

import land_ils_reviews as LR                       # noqa: E402
import rpe_env                                      # noqa: E402
from review_page import ils_review_pack as R        # noqa: E402


def name(cid, ym, client="Test Bank"):
    return f"{cid}-{ym}-ILS-{client} ILS Review.pdf"


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    return tmp_path


def library(tmp_path):
    """A Clients library: one folder per client, an `ILS Delivery` folder in each, several reviews and a deck."""
    lib = tmp_path / "Clients"
    for cid, files in {"9001": [name("9001", "2023.10"), name("9001", "2025.12"), "9001-2025.12-ILS-Test Bank ILS Review.pptm"],
                       "9002": [name("9002", "2026.07", "Other CU")], "9003": ["notes.pdf"]}.items():
        d = lib / f"Client {cid}" / "ILS Delivery"
        d.mkdir(parents=True)
        for f in files:
            (d / f).write_bytes(b"%PDF-1.4 " + f.encode())
    return lib


# ----------------------------------------------------------------- the folder
def test_it_is_a_kind_nothing_scans(root):
    assert rpe_env.INPUT_KIND_DIRS["ILS reviews"] == "ILS Reviews"
    assert "ILS reviews" in rpe_env.NOT_SCANNED_KINDS
    assert rpe_env.input_dir("ILS reviews", create=False) == root / "Inputs" / "ILS Reviews"
    assert root / "Inputs" / "ILS Reviews" not in rpe_env.report_dirs()


def test_a_review_is_known_by_its_name_and_the_newest_by_its_period():
    assert R.review_period(name("1539", "2026.07", "Marine FCU")) == ("2026", "07")
    assert R.review_period("1539-2026.07-ILS-Marine FCU ILS Review.pptm") is None      # the deck is not the review
    assert R.review_period("notes.pdf") is None
    assert R.newest([name("9001", "2023.10"), name("9001", "2025.12"), name("9001", "2024.08")]) == name("9001", "2025.12")
    assert R.newest(["a.pdf"]) is None


def test_newest_review_reads_the_clients_folder_on_the_share(root):
    assert R.newest_review("9001") is None
    d = R.reviews_dir("9001", create=True)
    (d / name("9001", "2023.10")).write_bytes(b"x")
    (d / name("9001", "2025.12")).write_bytes(b"x")
    assert R.newest_review("9001").name == name("9001", "2025.12")


def test_a_client_number_that_is_not_one_is_not_a_path_but_the_name_rule_never_matches_it():
    assert R.client_from_filename("../x-2026.07-ILS-A ILS Review.pdf") is None


# ----------------------------------------------------------------- landing
def test_the_plan_is_the_newest_review_per_client_and_leaves_decks_and_other_pdfs(tmp_path):
    lib = library(tmp_path)
    got = LR.plan(lib)
    assert sorted(got) == ["9001", "9002"]                                   # 9003's notes.pdf is not a review
    assert got["9001"].name == name("9001", "2025.12") and got["9001"].suffix == ".pdf"
    assert sorted(LR.plan(lib, {"9002"})) == ["9002"]


def test_landing_copies_once_and_never_overwrites_or_deletes(root, tmp_path):
    lib = library(tmp_path)
    src = LR.plan(lib)["9001"]
    dest = R.reviews_dir("9001")
    assert LR.land(src, dest, dry_run=True) == "landed" and not dest.exists()      # a dry run writes nothing
    assert LR.land(src, dest) == "landed" and (dest / src.name).read_bytes() == src.read_bytes()
    assert not list(dest.glob("*.part"))
    assert LR.land(src, dest) == "on hand"
    (dest / src.name).write_bytes(b"a different file")                              # same name, another size
    assert LR.land(src, dest) == "differs" and (dest / src.name).read_bytes() == b"a different file"
    older = dest / name("9001", "2023.10")
    older.write_bytes(b"older review")
    LR.land(src, dest)
    assert older.exists()                                                           # an older review stays beside it


def test_a_failed_copy_leaves_no_partial_file_under_the_name(root, tmp_path, monkeypatch):
    lib = library(tmp_path)
    src = LR.plan(lib)["9002"]
    dest = R.reviews_dir("9002")

    def boom(a, b):
        raise OSError("the share went away")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        LR.land(src, dest)
    assert not (dest / src.name).exists() and not list(dest.glob("*.part"))


# ----------------------------------------------------------------- the pack
def test_pack_client_reads_the_newest_review_once_and_reports_one_it_cannot_read(root, tmp_path, monkeypatch):
    assert LR.pack_client("9001")[0] == "no review"
    d = R.reviews_dir("9001", create=True)
    (d / name("9001", "2025.12")).write_bytes(b"x")
    monkeypatch.setattr(R, "read_pdf", lambda p: ["page"])
    monkeypatch.setattr(R, "parse", lambda pages, src, cid: {"version": R.PACK_VERSION, "client_id": cid, "client_name": "Test Bank",
                                                              "review_date": "2025-12-01", "source_file": src})
    assert LR.pack_client("9001", dry_run=True)[0] == "packed" and not R.pack_path("9001").exists()
    st, detail = LR.pack_client("9001")
    assert st == "packed" and "Test Bank" in detail
    assert json.loads(R.pack_path("9001").read_text())["source_file"] == name("9001", "2025.12")
    assert LR.pack_client("9001")[0] == "current"                                   # the pack already comes from this review

    def bad(pages, src, cid):
        raise R.ReviewReadError("the twelve months do not add up to the annual row")
    (d / name("9001", "2026.06")).write_bytes(b"y")                                 # a newer review that cannot be read
    monkeypatch.setattr(R, "parse", bad)
    st, detail = LR.pack_client("9001")
    assert st == "not read" and "do not add up" in detail
    assert json.loads(R.pack_path("9001").read_text())["source_file"] == name("9001", "2025.12")   # the old pack is kept, not blanked


def test_main_lands_and_reports(root, tmp_path, monkeypatch, capsys):
    lib = library(tmp_path)
    monkeypatch.setattr(R, "read_pdf", lambda p: ["page"])
    monkeypatch.setattr(R, "parse", lambda pages, src, cid: {"version": R.PACK_VERSION, "client_id": cid, "client_name": "T",
                                                              "review_date": "2026-01-01", "source_file": src})
    assert LR.main(["--from", str(lib), "--dry-run"]) == 0
    assert not (root / "Inputs" / "ILS Reviews").exists()
    assert LR.main(["--from", str(lib)]) == 0
    out = capsys.readouterr().out
    assert "9001" in out and "9002" in out and "landed 2" in out and "pack packed 2" in out
    assert R.newest_review("9001").name == name("9001", "2025.12") and R.pack_path("9002").is_file()
    assert LR.main(["--from", str(lib)]) == 0
    assert "on hand 2" in capsys.readouterr().out
    assert LR.main(["--from", str(tmp_path / "nowhere")]) == 2


def test_it_never_deletes_and_is_not_in_the_watch_or_sheila():
    src = open(os.path.join(REPO, "scripts", "land_ils_reviews.py"), encoding="utf-8").read()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    body = code.split('"""', 2)[2]
    for needle in ("rmtree", "os.remove(", "shutil.move", "os.rename("):
        assert needle not in body, needle
    for other in ("watch_sources.py", "ars_launcher_web.py"):
        assert "land_ils_reviews" not in open(os.path.join(REPO, "scripts", other), encoding="utf-8").read()
