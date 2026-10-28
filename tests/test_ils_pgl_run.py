"""ILS pre-go-live run (build/ils_pipeline/pre_go_live/run.py).

v5's run round-trip tests (v5 tests/test_pgl_setup.py, the run block). The run reads
`Inputs/ILS PGL/<id>/` and writes under `Build Artifacts/ils/PGL/<id>/<yyyymmdd>/` by default.
"""
from ils_pipeline.pre_go_live.run import run
from test_ils_pgl_loader import root  # noqa: F401 (fixture)


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
