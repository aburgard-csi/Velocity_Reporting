"""The parity check against v5 (build/ars_pipeline/ti/parity.py, scripts/ti_parity.py).

The compare must catch a real difference anywhere in a nested figure, tolerate float noise,
and say which key and where. The registry runs on a v5-shaped run folder built here from the
synthetic ODD, so the suite needs no v5 checkout and no share.
"""
import json
import math

import pytest

from ti import odd, parity
from ti.core.subsets import build_subsets


def test_identical_values_match_through_json():
    rows = parity.compare({"a": (1, 2.0), "b": {"c": [1, {"d": "x"}]}},
                          {"a": [1, 2], "b": {"c": [1, {"d": "x"}]}})
    assert [st for _k, st, _d in rows] == ["match", "match"]


def test_a_nested_difference_names_its_path():
    rows = dict((k, (st, d)) for k, st, d in parity.compare(
        {"b": {"c": [1, {"d": 3}]}}, {"b": {"c": [1, {"d": 4}]}}))
    assert rows["b"][0] == "differs" and "b.c[1].d" in rows["b"][1]


def test_float_noise_matches_and_a_real_change_does_not():
    assert parity.diff(0.1 + 0.2, 0.3) is None
    assert parity.diff(float("nan"), float("nan")) is None
    assert parity.diff(12.3, 12.4) is not None
    assert parity.diff(True, 1) is not None, "a flag is not a count"


def test_missing_keys_and_lengths_are_reported():
    assert parity.compare({"x": 1}, {}) == [("x", "missing in v5", "")]
    assert "2 items != 3" in parity.diff([1, 2], [1, 2, 3])
    assert "keys differ" in parity.diff({"a": 1}, {"b": 1})


@pytest.fixture
def v5_run(tmp_path, odd_csv):
    """A v5-shaped run folder: the frame v5 would have saved and the bases it would have written."""
    frame, _ = odd.load(odd_csv)
    frame.to_parquet(tmp_path / "enriched.parquet")
    anchor = odd.frame_data_month(frame)
    ctx = parity.Ctx(frame, {}, anchor, build_subsets(frame, {}, anchor), tmp_path)
    (tmp_path / "metrics.json").write_text(json.dumps(parity._norm(parity._bases(ctx))), encoding="utf-8")
    return tmp_path


def test_the_bases_check_passes_on_its_own_run(v5_run):
    rows = parity.run(v5_run, {})["bases"]
    assert rows and all(st == "match" for _k, st, _d in rows)


def test_a_changed_v5_figure_is_caught(v5_run):
    m = json.loads((v5_run / "metrics.json").read_text(encoding="utf-8"))
    m["n_eligible"] += 1
    (v5_run / "metrics.json").write_text(json.dumps(m), encoding="utf-8")
    bad = [k for k, st, _d in parity.run(v5_run, {})["bases"] if st != "match"]
    assert "n_eligible" in bad
