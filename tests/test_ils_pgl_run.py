"""ILS pre-go-live run (build/ils_pipeline/pre_go_live/run.py).

v5's run round-trip tests (v5 tests/test_pgl_setup.py, the run block). The run reads
`Inputs/ILS PGL/<id>/` and writes under `Build Artifacts/ils/PGL/<id>/<yyyymmdd>/` by default.
"""
from ils_pipeline.pre_go_live import report, run
from test_ils_pgl_loader import root  # noqa: F401 (fixture)

CODES = {"open_status": "O", "od_eligible": ["003", "005"], "rege_opt_in": "Y"}


def test_run_without_codes_returns_field_summary(root):
    res = run("1737")
    assert res.status == "needs_codes"
    assert res.metrics["pgl_rows"] == 6
    assert "pgl_suggested_codes" in res.metrics
    assert "pgl_bases" not in res.metrics                    # no analysis without codes


def test_run_with_bad_codes_fails_loudly(root):
    res = run("1737", codes={"open_status": "OPEN", "od_eligible": "003", "rege_opt_in": "Y"})
    assert not res.ok
    assert any("OPEN" in e for e in res.errors)


def test_the_run_reads_the_rpe_input_folder_and_writes_nothing_without_codes(root):
    res = run("1737")
    assert res.outputs["source"].endswith("1737_TxNat_PreGL_20260807.csv")
    assert any("NOT used" in w and "20260705" in w for w in res.warnings)
    assert not any((root / "Outputs").iterdir())


def test_run_with_codes_builds_bases_and_persists(root):
    res = run("1737", codes=CODES)
    assert res.ok and res.status != "needs_codes"
    bases = dict((r[0], r[1]) for r in res.metrics["pgl_bases"])
    assert bases["all"] == 5                                  # deleted row excluded
    assert bases["personal"] == 4 and bases["business"] == 1
    assert bases["open"] == 5                                 # deleted C row already gone
    assert bases["eligible"] == 3                              # personal+open+od in {003,005}: 001,002,003
    assert bases["opted_in"] == 2                             # Y among open: 001, 006
    assert res.metrics["pgl_codes_used"]["od_eligible"] == ["003", "005"]
    out = root / "Build Artifacts" / "ils" / "PGL" / "1737" / "20260807"
    assert (out / "pgl_metrics.json").exists()


def test_include_deleted_flag_keeps_every_row(root):
    res = run("1737", codes=CODES, include_deleted=True)
    bases = {r[0]: r[1] for r in res.metrics["pgl_bases"]}
    assert bases["all"] == 6                       # nothing excluded
    assert any("INCLUDED" in w or "included" in w for w in res.warnings)


def test_cli_accepts_lists_however_a_human_types_them():
    """James typed --open-status ["C", "X", "O","D"] in PowerShell; the shell
    splits it into tokens. The CLI accepts comma lists, space lists, and
    bracket/quote garnish alike."""
    from ils_pipeline.pre_go_live.__main__ import _gather
    assert _gather(['["C",', '"X",', '"O","D"]']) == ["C", "X", "O", "D"]
    assert _gather(["C,X,O,D"]) == ["C", "X", "O", "D"]
    assert _gather(["C", "X"]) == ["C", "X"]
    assert _gather(["[001,1]"]) == ["001", "1"]
    assert _gather(None) is None


# ---- RPE side -----------------------------------------------------------------

def test_a_coded_run_writes_only_under_build_artifacts(root):
    res = run("1737", codes=CODES)
    out = root / "Build Artifacts" / "ils" / "PGL" / "1737" / "20260807"
    assert res.outputs["manifest"].startswith(str(out))
    assert not any((root / "Outputs").iterdir())
    assert "pgl_funnel" in res.metrics and not [w for w in res.warnings if "failed:" in w]
    assert "1737" in report(res)


def test_the_cli_runs_the_two_steps(root, capsys):
    from ils_pipeline.pre_go_live.__main__ import main
    assert main(["1737"]) == 0
    assert "CODES NEEDED" in capsys.readouterr().out
    assert main(["1737", "--open-status", "O", "--od-eligible", "003,005", "--rege-opt-in", "Y"]) == 0
    assert (root / "Build Artifacts" / "ils" / "PGL" / "1737" / "20260807" / "pgl_metrics.json").exists()


def test_run_with_no_rege_value_still_runs(root):
    """James, 2026-11-11: 1842 has no Reg E yet. A blank opt-in, or an opt-in the file does not carry, runs."""
    blank = run("1737", codes={"open_status": "O", "od_eligible": ["003", "005"]})
    assert blank.ok and blank.status != "needs_codes"
    assert "opted_in" not in dict((r[0], r[1]) for r in blank.metrics["pgl_bases"])
    absent = run("1737", codes={**CODES, "rege_opt_in": "ZZ"})
    assert absent.ok and any("rege_opt_in" in w for w in absent.warnings)
