"""Build scratch in the system temp folder is removed (2026-09-16).

Unzipped ODD extracts and rendered images were never deleted; the C: drive reached 0.11 GB free
with about 180 GB of leftovers and two builds died with "No space left on device".
"""
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build")]
import rpe_env as R  # noqa: E402


def test_sweep_removes_only_old_pipeline_scratch(tmp_path):
    old = time.time() - 10 * 3600
    stale = tmp_path / "oddd_stale"; stale.mkdir(); (stale / "x.csv").write_bytes(b"x" * 100)
    fresh = tmp_path / "oddcsv_running"; fresh.mkdir()
    other = tmp_path / "someone_elses"; other.mkdir()
    for d in (stale, other):
        os.utime(d, (old, old))
    removed, freed = R.sweep_temp(root=tmp_path)
    assert (removed, freed) == (1, 100)
    assert not stale.exists() and fresh.exists() and other.exists()


def test_temp_dir_is_removed_when_the_process_exits(tmp_path):
    code = ("import sys; sys.path.insert(0, %r); import rpe_env as R; d = R.temp_dir('ars_assets_'); "
            "open(d + '/f', 'w').write('x'); print(d)") % str(REPO / "build")
    d = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert d and not os.path.exists(d)


def test_temp_dir_refuses_a_prefix_the_sweep_would_miss():
    with pytest.raises(ValueError):
        R.temp_dir("mystery_")


def test_extract_takes_only_the_odd_member(tmp_path):
    z = tmp_path / "1234_ODDD.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("1234-odd-extract.csv", "Acct ID\n1\n")
        zf.writestr("1234_monthlytran.csv", "t" * 5000)          # the larger, wrong file
    path = R.extract_odd_csv(str(z))
    assert Path(path).name == "1234-odd-extract.csv"
    assert [p.name for p in Path(path).parent.iterdir()] == ["1234-odd-extract.csv"]


# Every way a pipeline module can put something in the system temp folder that nothing removes.
# `tempfile.TemporaryDirectory` is allowed only as a `with` block, which removes it however the
# block ends. `gettempdir()` is here because a file joined onto it is a leak with no mkdtemp in
# sight: `_<id>_ars_work.pptx` and CashPlease's `.__full.pptx` both lived there (2026-09-16).
_UNMANAGED = [
    (re.compile(r"\b(mkdtemp|mkstemp|gettempdir)\s*\("), "use rpe_env.temp_dir"),
    (re.compile(r"NamedTemporaryFile\([^)]*delete\s*=\s*False"), "use rpe_env.temp_dir"),
    (re.compile(r"\bextractall\s*\("), "extract only the member you read (rpe_env.extract_odd_csv)"),
]


def _pipeline_lines():
    for p in sorted(list((REPO / "build").rglob("*.py")) + list((REPO / "scripts").rglob("*.py"))):
        if p.name == "rpe_env.py":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not line.lstrip().startswith("#"):
                yield f"{p.relative_to(REPO)}:{i}", line


def test_no_pipeline_code_makes_an_unmanaged_temp_dir():
    """Every build scratch dir must come from rpe_env.temp_dir, or it leaks again."""
    hits = []
    for where, line in _pipeline_lines():
        for rx, fix in _UNMANAGED:
            if rx.search(line):
                hits.append(f"{where}: {line.strip()}  ({fix})")
        if "TemporaryDirectory(" in line and not re.search(r"\bwith\b", line):
            hits.append(f"{where}: {line.strip()}  (use it as a `with` block)")
    assert not hits, "build scratch with no cleanup path:\n  " + "\n  ".join(hits)


def test_extracted_odd_is_removed_when_the_process_exits(tmp_path):
    """The resolve_csv path: the unzipped ODD (165 MB for 1539) does not outlive the build."""
    z = tmp_path / "1234_ODDD.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("1234-odd-extract.csv", "Acct ID\n1\n")
        zf.writestr("1234_monthlytran.csv", "t" * 5000)
    code = ("import sys; sys.path.insert(0, %r); import rpe_env as R; "
            "print(R.extract_odd_csv(%r, prefix='oddcsv_'))") % (str(REPO / "build"), str(z))
    csv = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert Path(csv).name == "1234-odd-extract.csv"
    assert not os.path.exists(csv) and not os.path.exists(os.path.dirname(csv))


@pytest.mark.parametrize("module, func", [("build_ars_gen.py", "def resolve_csv"),
                                          ("product_mix_slide.py", "def _resolve_csv")])
def test_resolve_csv_goes_through_the_managed_extract(module, func):
    # build_ars_gen runs its whole build at import, so its resolve_csv is checked by source.
    src = (REPO / "build" / "ars_pipeline" / module).read_text(encoding="utf-8")
    body = src.split(func, 1)[1].split("\ndef ", 1)[0]
    assert "extract_odd_csv(" in body and "extract(" not in body.replace("extract_odd_csv(", "")


def test_build_client_sweeps_first():
    src = (REPO / "scripts" / "build_month.py").read_text(encoding="utf-8")
    body = src.split("def build_client", 1)[1].split("\ndef ", 1)[0]
    assert "sweep_temp()" in body
