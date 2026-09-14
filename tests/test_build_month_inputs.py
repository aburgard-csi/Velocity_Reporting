"""build_month — finding a client's inputs across the per-kind Inputs folders.

Inputs were sorted into a folder per kind on 2026-09-09, which made `rpe_env.report_dirs()`
a LIST. `build_client` kept joining the DCO pattern onto `str(REPORTS)` — the string of a
list — so no SM client's DCO was ever found again, and `base_tab_extract` ran without it
(1038 Sugar River's staged builds all carry `dco_eligible: null`). Nothing failed: a
missing DCO is optional to the extractor, which is exactly why it went unseen.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "build"))
import build_month as BM  # noqa: E402


def _folders(tmp_path):
    dirs = [tmp_path / "ARS Workbooks", tmp_path / "DCOs", tmp_path / "ARS & MRPC Reports"]
    for d in dirs:
        d.mkdir()
    return dirs


def test_the_dco_is_found_across_every_report_folder(tmp_path):
    dirs = _folders(tmp_path)
    (tmp_path / "DCOs" / "1038-2026.09-Sugar River-DCO v2_2.xlsx").write_bytes(b"x")
    (tmp_path / "DCOs" / "1038-2026.08-Sugar River-DCO v2_2.xlsx").write_bytes(b"x")
    (tmp_path / "ARS & MRPC Reports" / "1204-2026.09-First State Bank-DCO v2_2.xlsx").write_bytes(b"x")
    assert [os.path.basename(p) for p in BM.dco_file(dirs, "1038", "2026.09")] == [
        "1038-2026.09-Sugar River-DCO v2_2.xlsx"], "the period's DCO, not last month's"
    assert [os.path.basename(p) for p in BM.dco_file([str(d) for d in dirs], "1204", "2026.09")] == [
        "1204-2026.09-First State Bank-DCO v2_2.xlsx"], "a file left in the legacy folder still counts"
    assert BM.dco_file(dirs, "9999", "2026.09") == []
    assert BM.dco_file(str(tmp_path / "DCOs"), "1038", "2026.09"), "a single folder still works"


def test_build_client_does_not_join_a_pattern_onto_a_list_of_folders():
    src = open(os.path.join(REPO, "scripts", "build_month.py"), encoding="utf-8").read()
    assert "os.path.join(str(REPORTS)" not in src
    assert "dco_file(REPORTS, cid, period)" in src
