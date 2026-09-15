"""The issue-page scripts (scripts/issue_pages/): no written-in paths, and the share-history scan (2026-09-15)."""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = os.path.join(REPO, "scripts", "issue_pages")
sys.path.insert(0, PAGES)


def test_no_script_writes_in_a_share_or_machine_path():
    # CLAUDE.md: paths resolve through rpe_env. These scripts began in a session scratchpad with the
    # share and the repo checkout written into them.
    bad = re.compile(r"PADMIS105|Velocity_company|C:\\\\Projects|C:\\Projects|AppData|Downloads", re.I)
    hits = []
    for name in os.listdir(PAGES):
        if name.endswith(".py"):
            text = open(os.path.join(PAGES, name), encoding="utf-8").read()
            hits += [f"{name}: {m.group(0)}" for m in bad.finditer(text)]
    assert not hits, hits


def test_the_runner_lists_every_step_script_that_exists():
    import build_issue_pages as B
    missing = [s for s in B.STEPS if not os.path.exists(os.path.join(PAGES, s))]
    assert not missing
    assert B.STEPS.index("gaps_matrix.py") == 0, "every later step reads gaps.json"
    assert B.STEPS.index("odd_wb_by_csm.py") > B.STEPS.index("mail_flags.py")


def test_the_share_history_scan_finds_every_file_and_only_ars_workbooks(tmp_path):
    import missing_wb_history as H
    for rel in ["2026.08/Jordan Berkowitz/1805-2026.08-Texar FCU-DCO v2_2.xlsx",
                "2026.09/Jordan Berkowitz/1805-2026.09-Texar FCU-Workbook_v2_1_0.xlsx",
                "2026.09/Jordan Berkowitz/1805-2026.09-Texar FCU-Invitation Checking Workbook v1.7.1.xlsx",
                "2026.09/Jordan Berkowitz/1799-2026.09-Central Bank-Workbook_v2_1_0.xlsx",
                "Archive/Jordan Berkowitz/1805-2025.01-Texar FCU-Workbook_v2_1_0.xlsx"]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
    out = H.scan(str(tmp_path), ["1805"])
    assert out["months"] == ["2026.08", "2026.09"], "a folder that is not a month is not scanned"
    assert len(out["all"]["1805"]) == 3 and "1799" not in out["all"]
    assert [h[2] for h in out["hits"]["1805"]] == ["1805-2026.09-Texar FCU-Workbook_v2_1_0.xlsx"]


def test_notes_copies_put_the_charset_first(tmp_path):
    import build_issue_pages as B
    src = tmp_path / "page.html"
    src.write_text("<title>x</title>“quote”", encoding="utf-8")
    dest_dir = tmp_path / "Notes"
    dest_dir.mkdir()
    out = B.copy_to_notes(src, dest_dir)
    assert out.read_text(encoding="utf-8").startswith('<meta charset="utf-8">')
