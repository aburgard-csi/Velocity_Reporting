"""ILS pre-go-live field summary (build/ils_pipeline/pre_go_live/field_summary.py).

v5's field-summary tests (v5 tests/test_pgl_setup.py, the field summary block and the two
deleted / data-review tests), on the RPE input folder.
"""
from ils_pipeline import pgl_input
from ils_pipeline.pre_go_live import field_summary, loader
from test_ils_pgl_loader import root  # noqa: F401 (fixture)


def _frame():
    df, _ = loader.load(pgl_input.find_extract("1737").path)
    return df


def test_field_summary_profiles_code_fields(root):
    df = _frame()
    m = field_summary.compute(df, warn=lambda _m: None)
    vals = dict(m["pgl_code_values"])["Account Status Code"]
    assert ["O", 5] in vals and ["C", 1] in vals
    od = dict(m["pgl_code_values"])["OD Status Code (from Core)"]
    assert ["003", 3] in od
    assert m["pgl_rows"] == 6
    groups = dict(m["pgl_column_groups"])
    assert any("Initial OD Limit (from Core)" in cols for cols in groups.values())
    cov = dict(m["pgl_coverage"])
    assert cov["Eligible_For_Scoring"] == 0.0                              # all NULL
    assert m["pgl_deleted_rows"] == 1


def test_field_summary_suggests_unambiguous_codes(root):
    df = _frame()
    m = field_summary.compute(df, warn=lambda _m: None)
    s = m["pgl_suggested_codes"]
    assert s["open_status"] == ["O"]
    assert s["rege_opt_in"] == ["Y"] and s["rege_opt_out"] == ["N"]
    assert "od_eligible" not in s                                          # never guessed


def test_deleted_rows_get_a_breakdown_not_just_a_count(root):
    df = _frame()
    m = field_summary.compute(df, warn=lambda _m: None)
    b = m["pgl_deleted_breakdown"]
    assert b["rows"] == 1
    assert dict(b["by_status"]) == {"C": 1}


def test_data_review_slices_whole_file_by_status(root):
    """Step 1 is a broad review: every row (deleted included), sliced by the
    code fields with the measures that discriminate open/active/on-program."""
    df = _frame()
    m = field_summary.compute(df, warn=lambda _m: None)
    rows = {r[0]: dict(zip(m["pgl_review_by_status_columns"], r))
            for r in m["pgl_review_by_status"]}
    assert rows["O"]["accounts"] == 5 and rows["C"]["accounts"] == 1
    assert rows["C"]["deleted"] == 1                      # the deleted row is VISIBLE here
    assert rows["O"]["ils_limit_gt0"] == 3                # 700, 400, 800
    assert rows["O"]["deposits_gt0"] == 4
    x = {(r[0], r[1]): r[2] for r in m["pgl_review_status_x_od"]}
    assert x[("O", "003")] == 2 and x[("C", "003")] == 1
