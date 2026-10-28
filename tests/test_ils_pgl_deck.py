"""ILS pre-go-live board deck (build/ils_pipeline/pre_go_live/deck.py, ils_pipeline/deckkit/).

v5's end-to-end smoke (v5 tests/smoke_pgl.py) as a test: a synthetic PGL-shaped extract (42 named
columns, literal NULLs, mixed-case codes, deleted rows, a fee history) -> needs_codes -> coded run
with the fee -> deck. Plus the RPE side: the template is read, never written, it carries the one
layout the deck asks for, and everything lands under Build Artifacts.
"""
import hashlib

import numpy as np
import pandas as pd
import pytest

from ils_pipeline.core import layout
from ils_pipeline.pre_go_live import report, run
from ils_pipeline.pre_go_live.deck import build
from ils_pipeline.pre_go_live.loader import COLUMNS_1737

CLIENT = "1441"


def write_extract(folder, name, n=3000, seed=5):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({c: ["NULL"] * n for c in COLUMNS_1737})
    df["AcctNo"] = [f"{i:012d}" for i in range(n)]
    df["Personal_Business"] = rng.choice(["Personal", "Business"], n, p=[0.93, 0.07])
    df["Account Status Code"] = rng.choice(["O", "C", "D"], n, p=[0.7, 0.25, 0.05])
    df["OD Status Code (from Core)"] = rng.choice(["003", "005", "000", "1"], n, p=[0.5, 0.1, 0.3, 0.1])
    df["Reg-E Opt-In Value"] = rng.choice(["Y", "N", "NULL"], n, p=[0.35, 0.55, 0.1])
    df["UpOrDown from Initial OD Limit"] = rng.choice(
        ["Score100Plus", "Same", "ScoreLess100", "Unknown"], n, p=[0.3, 0.4, 0.2, 0.1])
    df["Initial OD Limit (from Core)"] = rng.choice([0, 300, 600], n).astype(str)
    df["OD Limit (from ILS)"] = rng.choice([0, 400, 700, 900], n).astype(str)
    df["NSF OD Items since start date"] = rng.integers(0, 12, n).astype(str)
    df["Paid NSF OD Items since start date"] = (rng.integers(0, 12, n) // 2).astype(str)
    df["Rolling 12 Month NSFOD Items"] = rng.integers(0, 15, n).astype(str)
    df["Rolling 12 Month NSFOD Fees"] = (rng.integers(0, 15, n) * 13.5).round(2).astype(str)
    df["Deposit Count Last 33 days"] = rng.integers(0, 30, n).astype(str)
    df["Deposit Amount Last 33 days"] = (rng.gamma(2, 800, n)).round(2).astype(str)
    opened = pd.Timestamp("2020-01-01") + pd.to_timedelta(rng.integers(0, 2300, n), unit="D")
    df["Open Date"] = opened.strftime("%m/%d/%Y")
    deleted = rng.random(n) < 0.04
    df.loc[deleted, "Deleted"] = "8/1/2026"
    folder.mkdir(parents=True, exist_ok=True)
    df.to_csv(folder / name, index=False, encoding="utf-8-sig")


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    folder = tmp_path / "Inputs" / "ILS PGL" / CLIENT
    write_extract(folder, f"{CLIENT}_Synth_PreGL_20260601.csv", n=500, seed=1)
    write_extract(folder, f"{CLIENT}_Synth_PreGL_20260801.csv")
    return tmp_path


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---- v5's smoke ---------------------------------------------------------------

def test_smoke_needs_codes_then_coded_run_then_deck(root):
    r1 = run(CLIENT)
    assert r1.status == "needs_codes", r1.status
    assert any("NOT used" in w for w in r1.warnings)
    assert report(r1)

    r2 = run(CLIENT, codes={"open_status": "O", "od_eligible": ["003", "005"],
                            "rege_opt_in": "Y", "rege_opt_out": "N"}, fee=27)
    assert report(r2)
    assert r2.ok and r2.metrics.get("pgl_fee_tiers"), "fee scenarios must run"
    assert r2.metrics["pgl_fee_audit"]["implied_pay_ratio_pct"] > 0
    assert r2.metrics.get("pgl_limit_dist_current_eligible")

    template = layout.TEMPLATE
    from pathlib import Path
    out = Path(r2.outputs["metrics"]).parent / "deck.pptx"
    deck = build(r2, template, out)
    assert deck.slides >= 7 and not deck.skipped
    crashed = [w for w in r2.warnings if "failed:" in w]
    assert not crashed, "a PGL section crashed"


# ---- RPE side -----------------------------------------------------------------

def test_the_template_has_the_layout_the_deck_asks_for():
    from pptx import Presentation
    from ils_pipeline import deckkit as dk
    prs = Presentation(str(layout.TEMPLATE))
    assert prs.slide_layouts[dk.LAYOUT_BLANK].name == "BLANK"
    assert layout.TEMPLATE.parent.name == "templates" and not layout.missing_assets()


def test_the_deck_is_read_from_the_template_and_lands_in_build_artifacts(root):
    before = _sha(layout.TEMPLATE)
    res = run(CLIENT, codes={"open_status": "O", "od_eligible": ["003", "005"], "rege_opt_in": "Y"})
    from ils_pipeline.pre_go_live.__main__ import main
    assert main([CLIENT, "--open-status", "O", "--od-eligible", "003,005", "--rege-opt-in", "Y",
                 "--deck", "--current-only"]) == 0
    out = root / "Build Artifacts" / "ils" / "PGL" / CLIENT / "20260801"
    assert (out / f"{CLIENT}_20260801_ILS_PreGoLive.pptx").exists()
    assert (out / "storyboard.md").exists() and any((out / "charts").glob("*.png"))
    assert not any((root / "Outputs").iterdir())
    assert _sha(layout.TEMPLATE) == before
    assert res.ok
