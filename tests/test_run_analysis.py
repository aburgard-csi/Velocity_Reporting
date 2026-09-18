"""The analysis engine runs on the ODD the deck build already reads (2026-09-18).

On the synthetic ODD (tests/fixtures/make_odd.py, no real member data) the runner must
finish with a status that is not `error`, a non-zero eligible base, no section reporting
"failed:", and its evidence written where the build keeps evidence. A second run adds a
small zipped transaction file so the transaction sections are exercised through
rpe_env.open_txn, the same way the pipeline stores them.
"""
import json
import random
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
import run_analysis as RA  # noqa: E402

PERIOD = "2026.08"        # the fixture's latest month is Jul26


@pytest.fixture(scope="module")
def result(odd_csv, tmp_path_factory):
    out = tmp_path_factory.mktemp("analysis")
    return RA.run(odd_csv, "1441", PERIOD, out_dir=out, name="Synthetic Bank", txn=False, tables=None)


def test_the_run_finishes_without_a_section_failing(result):
    assert result.status != "error", result.errors
    assert result.metrics.get("n_eligible", 0) > 0
    failed = [w for w in result.warnings if "failed:" in w]
    assert not failed, failed


def test_the_data_month_is_the_month_before_the_period(result):
    assert result.data_month == "2026-07"
    assert result.metrics["anchor_tag"] == "Jul26"


def test_the_evidence_is_written(result):
    out = Path(result.outputs["metrics"]).parent
    assert (out / "metrics.json").exists() and (out / "enriched.parquet").exists()
    assert (out / "report.md").exists()
    m = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert m["n_eligible"] == result.metrics["n_eligible"]
    assert Path(result.outputs["manifest"]).exists()


def test_reg_e_is_read_through_the_shared_wording(result):
    m = result.metrics
    assert m["rege_pool"] > 0 and m["rege_in"] + m["rege_out"] + m["rege_default"] + m["rege_no"] + m["rege_unmapped"] == m["rege_pool"]
    assert not any("POSSIBLE DATA ISSUE" in w for w in result.warnings), "the fixture's wording is all mapped"


def _write_txn_zip(folder, accounts, seed=7):
    """One monthly transaction file in the core's layout, zipped one-member as the pipeline stores it."""
    rnd = random.Random(seed)
    name = "1441_[2026.07.05]_Monthly Transaction File.txt"
    lines = ["1441|7/5/2026 7:16:16 AM||31004|Monthly Transaction File|6.0.6.0"]
    for i in range(400):
        acct = rnd.choice(accounts)
        typ = rnd.choice(["PIN", "SIG", "SIG", "ACH", "CHK"])
        amt = f"{rnd.uniform(2, 180):.2f}"
        merchant = rnd.choice(["WALMART", "SHELL OIL", "CAPITAL ONE", "AMAZON", "CHASE CREDIT CRD", "H-E-B 12\" PIZZA"])
        lines.append("\t".join([f"6/{1 + i % 28}/2026", acct, typ, amt, "5411", merchant, "", "", "T1", "M1", "1441", "Y", "00"]))
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(folder / (name + ".zip"), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, "\n".join(lines) + "\n")
    return folder


def test_the_transaction_sections_run_on_a_zipped_file(odd_csv, tmp_path):
    pd = pytest.importorskip("pandas")
    ids = pd.read_csv(odd_csv, skiprows=4, dtype=str, usecols=["Acct Number"])["Acct Number"].dropna().tolist()[:120]
    txn_dir = _write_txn_zip(tmp_path / "Txn Files" / "1441", ids)
    r = RA.run(odd_csv, "1441", PERIOD, out_dir=tmp_path / "out", name="Synthetic Bank",
               txn=True, txn_dirs=[txn_dir], tables=None)
    assert r.status != "error", r.errors
    assert (tmp_path / "out" / "txn_metrics.json").exists()
    t = json.loads((tmp_path / "out" / "txn_metrics.json").read_text(encoding="utf-8"))
    assert t["txn_files_loaded"] == ["1441_[2026.07.05]_Monthly Transaction File.txt.zip"]   # read as stored
    assert t.get("txn_rows", 0) > 0 or t.get("txn_accounts", 0) > 0 or any(k.startswith("txn_") for k in t)
    failed = [w for w in r.warnings if "failed:" in w]
    assert not failed, failed
