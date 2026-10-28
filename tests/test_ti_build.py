"""The Transaction Intelligence cut's build step (build/ars_pipeline/ti_build.py) and its
opt-in wiring into scripts/build_month.py.

Pinned: no chapter means nothing built; figures are computed once and kept in the pack; a lens
with no accounts is stated, not built; the decks pass the validator; and a cut deck staged in
ti/ can never be the deliverable in place of the client's ARS deck.
"""
import json
import os
import shutil
import sys
import zipfile

import pytest
from pptx import Presentation

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("build", "build/ars_pipeline", "validation", "scripts"):
    sys.path.insert(0, os.path.join(REPO, p))

import promote_month as PM  # noqa: E402
import ti_build  # noqa: E402
import validate_deck as vd  # noqa: E402
from test_ti_shell import STUB  # noqa: E402
from ti import cut  # noqa: E402

CLIENT, NAME = "9999", "Test Bank"


@pytest.fixture
def root(tmp_path, monkeypatch, odd_csv):
    for d in ("Inputs/ODDD", "Inputs/ARS Settings", "Inputs/ICS Direct Mail", "Inputs/ICS Referrals",
              "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    with zipfile.ZipFile(tmp_path / "Inputs/ODDD" / f"{CLIENT}_ODDD.zip", "w") as z:
        z.write(odd_csv, f"{CLIENT}-2026-10-{NAME}-ODD.csv")
    (tmp_path / "csm_list.csv").write_text(f"client_id,client_name,csm\n{CLIENT},{NAME},Test CSM\n", encoding="utf-8")
    (tmp_path / "csm_contacts.csv").write_text(
        "csm,title,company,address,office,cell,email,source\n"
        "Test CSM,Client Service Manager,CSI,,,(555) 010-0001,Test.CSM@example.com,synthetic\n", encoding="utf-8")
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("RPE_CSM_LIST", str(tmp_path / "csm_list.csv"))
    monkeypatch.setenv("RPE_CSM_CONTACTS", str(tmp_path / "csm_contacts.csv"))
    monkeypatch.delenv("TI_CLIENT_CONFIG", raising=False)
    return tmp_path


def test_no_chapter_means_nothing_built(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cut, "CHAPTERS", ())
    assert ti_build.main([CLIENT, "2026.10", NAME, str(tmp_path / "ti")]) == 0
    assert "nothing built" in capsys.readouterr().out
    assert not (tmp_path / "ti").exists()


def test_pack_and_decks(root, monkeypatch):
    monkeypatch.setattr(cut, "CHAPTERS", (STUB,))
    stage = root / "stage" / CLIENT
    out = stage / "ti"
    assert ti_build.main([CLIENT, "2026.10", NAME, str(out), "--ics"]) == 0

    pack = json.loads((out / "ti_pack.json").read_text(encoding="utf-8"))
    assert pack["metrics"]["stub_groups"] == 3 and pack["metrics"]["n_total"] > 0
    assert pack["lenses"] == ["ars"]
    assert "No ICS accounts" in pack["lenses_unavailable"]["ics"], "an empty lens is stated, not built"
    assert any("no direct-mail" in w for w in pack["warnings"])

    decks = sorted(out.glob("*.pptx"))
    assert [d.name for d in decks] == [cut.deck_name(CLIENT, "2026.10", NAME, "ars")]
    fails = [f for f in vd.run(str(decks[0])) if f[0] == "FAIL"]
    assert fails == [], fails

    # the client's ARS deck in the staging folder stays the deliverable
    ars = stage / f"{CLIENT}-2026.10-ARS-{NAME} ARS Results.pptx"
    shutil.copy(decks[0], ars)
    assert PM.deliverable(str(stage)) == str(ars)


def test_the_analyst_tables_land_beside_the_pack(root, monkeypatch):
    """v5's tables layer (ti/monthly_analysis/tables.py): a tabular figure that names its columns
    is a CSV under ti/tables, listed in the pack; one that names none is stated, not dropped."""
    def figures(_ctx):
        return {"thing_by_branch": [["Main", 10, 1.5], ["Harbor", 20, 2.5]],
                "thing_by_branch_columns": ["branch", "n", "rate"],
                "mystery": [[1, 2]]}
    monkeypatch.setattr(cut, "CHAPTERS", (STUB._replace(compute=figures),))
    out = root / "stage" / CLIENT / "ti"
    assert ti_build.main([CLIENT, "2026.10", NAME, str(out)]) == 0

    pack = json.loads((out / "ti_pack.json").read_text(encoding="utf-8"))
    csv_path = out / "tables" / "thing_by_branch.csv"
    assert pack["tables"] == {"thing_by_branch": str(csv_path)}
    assert csv_path.read_text(encoding="utf-8-sig").splitlines()[:2] == ["branch,n,rate", "Main,10,1.5"]
    assert any("declare no columns" in w and "mystery" in w for w in pack["warnings"])


def test_a_failing_chapter_is_stated_and_the_build_goes_on(root, monkeypatch):
    def boom(_ctx):
        raise ValueError("no fin_by_category")
    monkeypatch.setattr(cut, "CHAPTERS", (STUB._replace(compute=boom),))
    pack = ti_build.compute_pack(CLIENT, "2026.10", NAME)
    assert any("figures not computed (ValueError: no fin_by_category)" in w for w in pack["warnings"])


def test_build_month_runs_the_cut_only_when_asked():
    src = open(os.path.join(REPO, "scripts", "build_month.py"), encoding="utf-8").read()
    block = src[src.index('if os.environ.get("RPE_TI") == "1":'):]
    block = block[:block.index("\n\n")]
    assert "ti_build.py" in block and 'os.path.join(d, "ti")' in block
    assert "made[" not in block, "the cut is never combined or delivered"
