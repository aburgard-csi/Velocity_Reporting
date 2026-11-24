"""scripts/build_market_reference.py and scripts/ti_lists_backfill.py (Aaron, 2026-11-23).

No network and no share: the sources are replaced with small fakes, and Outputs is a temp folder.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
for p in (REPO / "scripts", REPO / "build", REPO / "build" / "ars_pipeline"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_market_reference as M      # noqa: E402
from ti.core.filed.join import REQUIRED_CACHE   # noqa: E402


class _Book:
    institutions = {"a": 1, "b": 2}
    branches = [1, 2, 3]
    unplaced = []


def _fake_sources(monkeypatch, short=None, fail=None):
    """Every fetcher writes its file(s) the way sources._cached does; `short` writes one file below its
    floor, `fail` raises in one step."""
    monkeypatch.setattr(M.sources, "MIN_ROWS", {n: 2 for n in REQUIRED_CACHE})

    def write(work, name):
        if fail == name:
            raise M.sources.SourceError(f"could not fetch {name}")
        rows = [{"x": 1}] if short == name else [{"x": 1}, {"x": 2}, {"x": 3}]
        (work / f"{name}.json").write_text(json.dumps(rows), encoding="utf-8")

    monkeypatch.setattr(M.sources, "fdic_institutions", lambda w, refresh: write(w, "fdic_institutions"))
    monkeypatch.setattr(M.sources, "fdic_locations", lambda w, refresh: write(w, "fdic_locations"))
    monkeypatch.setattr(M.sources, "fdic_financials", lambda w, refresh, since: write(w, "fdic_financials"))
    monkeypatch.setattr(M.sources, "ncua", lambda w, quarter, refresh: [
        write(w, n) for n in ("ncua_institutions", "ncua_branches", "ncua_trade_names", "ncua_financials")])
    monkeypatch.setattr(M.sources, "zip_centroids", lambda w, year, refresh: write(w, "zip_centroids"))
    monkeypatch.setattr(M.institutions, "load_book", lambda folder, quarter, gazetteer_year: _Book())


def test_a_full_fetch_lands_every_file_the_builds_require(monkeypatch, tmp_path):
    _fake_sources(monkeypatch)
    dest = tmp_path / "Market Reference"
    assert M.main(["--dest", str(dest)]) == 0
    for name in REQUIRED_CACHE:
        assert (dest / f"{name}.json").is_file()
    v = json.loads((dest / M.VINTAGES).read_text(encoding="utf-8"))
    assert v["ncua_quarter"] == M.sources.DEFAULT_NCUA_QUARTER and v["institutions"] == 2
    assert not list(dest.glob("*.part")), "no .part left behind"
    assert M.main(["--dest", str(dest), "--check"]) == 0


@pytest.mark.parametrize("kw", [{"fail": "ncua_branches"}, {"short": "fdic_locations"}])
def test_a_failed_or_short_source_never_touches_the_share(monkeypatch, tmp_path, kw):
    _fake_sources(monkeypatch, **kw)
    dest = tmp_path / "Market Reference"
    dest.mkdir()
    (dest / "fdic_institutions.json").write_text("OLD", encoding="utf-8")
    assert M.main(["--dest", str(dest)]) == 1
    assert (dest / "fdic_institutions.json").read_text(encoding="utf-8") == "OLD"
    assert sorted(p.name for p in dest.iterdir()) == ["fdic_institutions.json"]


def test_check_says_not_ready_when_the_store_is_missing(tmp_path):
    assert M.main(["--dest", str(tmp_path / "nothing"), "--check"]) == 1


def test_the_default_destination_is_the_folder_the_builds_read(monkeypatch, tmp_path):
    monkeypatch.setenv("TI_REFERENCE_DIR", str(tmp_path / "ref"))
    assert M.destination() == tmp_path / "ref"


# ------------------------------------------------------------------------------------------ lists backfill
def _staged(base, cid, period, name="Union Financial"):
    tdir = base / period / cid / "ti"
    (tdir / "lists").mkdir(parents=True)
    (tdir / "lists" / "finserv_master_list.csv").write_text("acct_id,list_type\n1,Auto\n", encoding="utf-8")
    (tdir / "ti_pack.json").write_text(json.dumps({"client_id": cid, "client_name": name}), encoding="utf-8")
    return tdir


def test_backfill_copies_only_lists_whose_deck_was_delivered(monkeypatch, tmp_path):
    import ti_lists_backfill as B
    base = tmp_path / "launcher"
    _staged(base, "9001", "2026.10")
    _staged(base, "9002", "2026.10")
    (tmp_path / "empty" / "ti" / "lists").mkdir(parents=True)      # a lists folder with no CSV is not a build
    out = tmp_path / "Outputs" / "Jane CSM"
    out.mkdir(parents=True)
    (out / "9001-2026.10-TI-ARS-Union Financial Transaction Intelligence.pptx").write_bytes(b"x")
    monkeypatch.setattr(B.R, "output_decks", lambda pat: sorted(out.glob(pat)))
    monkeypatch.setattr(B.R, "client_outputs", lambda cid, **k: out)

    rows = {(r[0], r[4]): r[5] for r in B.plan(base)}
    assert rows[("9001", "copy")] == str(out / "9001-2026.10-TI-Lists")
    assert "no TI deck" in rows[("9002", "skip")]

    (out / "9001-2026.10-TI-Lists").mkdir()
    rows = {(r[0], r[4]): r[5] for r in B.plan(base)}
    assert "already in Outputs" in rows[("9001", "skip")]


def test_backfill_is_a_dry_run_unless_told_to_apply(monkeypatch, tmp_path, capsys):
    import ti_lists_backfill as B
    called = []
    monkeypatch.setattr(B, "plan", lambda: [("9001", "2026.10", tmp_path, "U", "copy", "dest")])
    monkeypatch.setattr(B.L, "ti_lists_to_outputs", lambda *a: called.append(a) or (B.L.OK, "done"))
    assert B.main([]) == 0 and not called
    assert "Dry run" in capsys.readouterr().out
    assert B.main(["--apply"]) == 0 and len(called) == 1
