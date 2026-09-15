"""Outputs/_Archive: the archive's one name, and readers that never mistake it for a CSM (2026-09-15).

The folder was renamed from `Archive` so it sorts above the CSM folders in File Explorer (Aaron: "add
to the archive folder names so they stay at the top, above my name"). A reader that skipped only the
new name would count every superseded deck in a leftover `Archive/` as delivered.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build"), os.path.join(REPO, "scripts")]
import rpe_env as R  # noqa: E402


def test_the_archive_name_starts_with_an_underscore():
    assert R.ARCHIVE_DIRNAME == "_Archive"


def test_output_decks_skips_the_archive_under_either_name(tmp_path):
    name = "1441-2026.09-ARS-FNB Alaska ARS Results.pptx"
    for rel in (f"James Gilmore/{name}",
                f"_Archive/James Gilmore/1441 FNB Alaska/{name}",
                f"Archive/James Gilmore/1441 FNB Alaska/{name}"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    found = R.output_decks("1441-2026.09-*.pptx", root=tmp_path)
    assert [p.parent.name for p in found] == ["James Gilmore"]


def test_promote_month_archives_into_the_named_folder():
    src = open(os.path.join(REPO, "scripts", "promote_month.py"), encoding="utf-8").read()
    launcher = open(os.path.join(REPO, "scripts", "ars_launcher.py"), encoding="utf-8").read()
    assert 'out / "Archive"' not in src and "R.ARCHIVE_DIRNAME" in src
    assert 'out / "Archive"' not in launcher and "R.ARCHIVE_DIRNAME" in launcher
