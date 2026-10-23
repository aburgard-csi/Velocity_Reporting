"""The Transaction Intelligence cut's ODD frame (build/ars_pipeline/ti/odd.py).

The synthetic 800-row ODD carries a preamble above its header, so the header is found by
detection, not position; the transform is v5's, so the frame carries v5's derived columns.
"""
import pytest

from ti import odd
from ti.core.subsets import build_subsets


def test_header_is_detected_past_the_preamble(odd_csv):
    assert odd.header_row(odd_csv) > 0


def test_frame_carries_v5_derived_columns(odd_csv):
    frame, report = odd.load(odd_csv)
    assert not report.errors, report.errors
    assert len(frame) == report.rows_out > 0
    assert odd.frame_data_month(frame) is not None


def test_bases_build_on_the_frame(odd_csv):
    frame, _ = odd.load(odd_csv)
    subsets = build_subsets(frame, {}, odd.frame_data_month(frame))
    assert 0 < len(subsets.eligible) <= len(subsets.open_accounts) <= len(frame)


def test_missing_extract_is_a_plain_sentence(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    with pytest.raises(SystemExit, match="no ODD extract"):
        odd.odd_zip("9999")
