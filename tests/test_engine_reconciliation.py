"""With RPE_ANALYSIS=1 the engine must reproduce the deck's own figures (2026-09-18).

On the synthetic ODD the engine's eligible base, eligible personal base and personal take
rate must equal what metrics_gen and the pack compute from the same file. They share the
same predicates in odd_rows, so a difference is a second reading that crept in.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
import run_analysis as RA  # noqa: E402

PY = sys.executable


@pytest.fixture(scope="module")
def pack(odd_csv, tmp_path_factory):
    out = tmp_path_factory.mktemp("pack")
    subprocess.run([PY, str(REPO / "scripts" / "oddd_optimize.py"), "--input", str(odd_csv),
                    "--out", str(out), "--client", "1441", "--name", "Synthetic Bank"],
                   check=True, capture_output=True, text=True)
    return json.loads((out / "oddd_metrics.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def engine(odd_csv, tmp_path_factory):
    out = tmp_path_factory.mktemp("engine")
    r = RA.run(odd_csv, "1441", "2026.08", out_dir=out, name="Synthetic Bank", txn=False, tables=None)
    assert r.status != "error", r.errors
    return r.metrics


def test_the_engine_reproduces_the_decks_figures(engine, metrics, pack):
    fails, lines = RA.reconcile(engine, metrics, pack)
    assert not fails, "\n".join(lines)


def test_the_eligible_base_is_the_odd_flag_on_both_sides(engine, metrics, pack):
    assert engine["n_eligible"] == pack["funnel"]["eligible"]
    assert engine["n_eligible_personal"] == metrics["n_eligible"]
    assert engine["elig_flag_divergence_pct"] is not None


def test_a_drift_is_a_failure_and_a_missing_value_is_not():
    fails, lines = RA.reconcile({"n_eligible": 100, "n_eligible_personal": 90, "dctr_personal": 40.0},
                                {"n_eligible": 91, "take_hist_pct": 40.1}, {"funnel": {"eligible": 100}})
    assert fails == ["n_eligible_personal: engine 90 vs M n_eligible 91"]
    fails, _ = RA.reconcile({"n_eligible": 100}, {}, {})
    assert fails == []


def test_the_engine_is_opt_in():
    src = (REPO / "build" / "ars_pipeline" / "build_ars_gen.py").read_text(encoding="utf-8")
    assert 'os.environ.get("RPE_ANALYSIS") == "1"' in src
    assert "_ra.reconcile(" in src and "raise SystemExit" in src.split("RPE_ANALYSIS")[2][:2000]
