"""The ILS pre-go-live engine on deliveries shaped like the 2026-10 ones (1737 TNB, 1759 First Central).

Pinned: a delivery landed as a zip is read without touching Inputs, and unpacked again only when it
changes; a vendor dump is never taken as the extract, even undated and newer; a dump saved as .csv is
read like the .txt one; a SQL Server message line under a dump table is not a row; an extract with no
header row stops the run and says so; Sheila lists a client whose delivery is a zip.
"""
import os
import sys
import time
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build"), str(REPO / "scripts")]
from ils_pipeline import pgl_input  # noqa: E402
from ils_pipeline.pre_go_live import loader, run, system_view  # noqa: E402

DEPOSITS = """=== DEPOSIT HISTORY ===

DepositDate  DepositCount         DepositSum            Accounts w/o a Deposit in the last 20 days
------------ -------------------- --------------------- ------------------------------------------
10/25/2026   0                    NULL                  12218
10/26/2026   1836                 23811678.00           12249
Warning: Null value is eliminated by an aggregate or other SET operation.

(2 rows affected)
"""


def _extract_text(header=True):
    cols = loader.COLUMNS_1737
    row = ["1"] * len(cols)
    return (",".join(cols) + "\n" if header else "") + (",".join(row) + "\n") * 2


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    (tmp_path / "Inputs" / "ILS PGL").mkdir()
    return tmp_path


def _zip(root, name, files):
    z = root / "Inputs" / "ILS PGL" / name
    with zipfile.ZipFile(z, "w") as zf:
        for n, text in files.items():
            zf.writestr(n, text)
    return z


def test_a_landed_zip_is_read_and_inputs_is_not_touched(root):
    z = _zip(root, "1759_FirstCentral_PGL_20261026.zip",
             {"1759_FirstCentral_PGL_20261026.csv": _extract_text()})
    found = pgl_input.find_extract("1759")
    assert found.path.name == "1759_FirstCentral_PGL_20261026.csv"
    assert "Build Artifacts" in found.path.parts and "_landed" in found.path.parts
    assert sorted(p.name for p in (root / "Inputs" / "ILS PGL").iterdir()) == [z.name]


def test_the_zip_is_unpacked_again_only_when_it_changes(root):
    z = _zip(root, "1759_x.zip", {"1759_x_20261026.csv": _extract_text()})
    d = pgl_input.unpack(z, "1759")
    f = d / "1759_x_20261026.csv"
    f.write_text("edited", encoding="utf-8")
    pgl_input.unpack(z, "1759")
    assert f.read_text(encoding="utf-8") == "edited"          # same zip: left as it was
    time.sleep(1.1)
    z.unlink()
    z = _zip(root, "1759_x.zip", {"1759_x_20261026.csv": _extract_text()})
    pgl_input.unpack(z, "1759")
    assert f.read_text(encoding="utf-8") != "edited"          # a new zip: unpacked again


def test_another_clients_zip_is_not_this_clients(root):
    _zip(root, "17370_Other_PGL_20261026.zip", {"a_20261026.csv": _extract_text()})
    assert pgl_input.landed_zips(root / "Inputs" / "ILS PGL", "1737") == []


def test_a_vendor_dump_is_never_the_extract(root):
    d = root / "Inputs" / "ILS PGL" / "1759"
    d.mkdir()
    (d / "1759_FirstCentral_PGL_20261026.csv").write_text(_extract_text(), encoding="utf-8")
    for n in ("1759_MatrixValidation_PGL2.csv", "1759_IntegrityCheck_PGL2.csv"):
        (d / n).write_text("=== X ===\n", encoding="utf-8")
        later = time.time() + 86400 * 3                    # undated and newer: it used to win
        os.utime(d / n, (later, later))
    assert pgl_input.find_extract("1759").path.name == "1759_FirstCentral_PGL_20261026.csv"


def test_a_dump_saved_as_csv_is_read(tmp_path):
    (tmp_path / "1759_IntegrityCheck_PGL2.csv").write_text(DEPOSITS, encoding="utf-8")
    out = system_view.load(tmp_path, lambda w: None)
    assert out["sysv_files"] == ["1759_IntegrityCheck_PGL2.csv"]


def test_a_sql_server_message_under_a_table_is_not_a_row():
    rows = system_view._table(system_view._sections(DEPOSITS)["DEPOSIT HISTORY"])
    assert [r["DepositDate"] for r in rows] == ["10/25/2026", "10/26/2026"]
    dep = system_view.parse_integrity(DEPOSITS)["sysv_deposits"]
    assert dep["days"] == 2 and dep["no_deposit_20d_latest"] == 12249


def test_an_extract_with_no_header_row_stops_and_says_so(root):
    _zip(root, "1737_TNB_PGL_20261027.zip", {"1737_TNB_PGL_20261027.csv": _extract_text(header=False)})
    res = run("1737")
    assert not res.ok and "has no header row" in res.errors[0]


def test_sheila_lists_a_client_whose_delivery_is_a_zip(root):
    import ils_runs
    _zip(root, "1759_FirstCentral_PGL_20261026.zip", {"1759_FirstCentral_PGL_20261026.csv": _extract_text()})
    assert "1759" in ils_runs.landed_clients()
    pgl = ils_runs.client_doc("1759")["kinds"]["pgl"]
    assert pgl["exists"] and pgl["extract"] == "1759_FirstCentral_PGL_20261026.csv"
