"""The ARS Revenue Lift Matrix picture and its caption name the same move (2026-09-16)."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, os.pardir, "build", "ars_pipeline"), os.path.join(HERE, os.pardir, "build")]
import render_lift as RL  # noqa: E402

COLS = ["1-5", "6-10", "11-15", "16-20", "21-25", "26 Plus"]
LIFT = {
    "matrix_cols": COLS,
    "matrix_rows": [["NU", 4.03, 10.94, 16.29, 20.67, 23.71, 27.73],
                    ["1-5", None, 6.91, 12.26, 16.64, 19.68, 23.7],
                    ["6-10", None, None, 5.35, 9.73, 12.77, 16.8]],
    "revseg": [["NH", 0, 0.92], ["NU", 0.2251, 0.92], ["1-5", 0.1359, 4.95], ["6-10", 0.0776, 11.86],
               ["11-15", 0.0647, 17.21], ["16-20", 0.0527, 21.59], ["21-25", 0.0502, 24.63], ["26 Plus", 0.3936, 28.66]],
}


def test_the_example_is_1_5_to_11_15():
    assert RL.example_move(LIFT) == ("1-5", "11-15", 1, 2, 12.26)


def test_without_that_cell_the_example_is_the_largest_move():
    other = dict(LIFT, matrix_rows=[r for r in LIFT["matrix_rows"] if r[0] != "1-5"])
    assert RL.example_move(other) == ("NU", "26 Plus", 0, 5, 27.73)


def test_tiers_skip_a_segment_with_no_accounts():
    assert [t[0] for t in RL.tiers(LIFT)] == ["NU", "1-5", "6-10", "11-15", "16-20", "21-25", "26 Plus"]


def test_the_picture_is_drawn_at_the_slide_box_aspect(tmp_path):
    pytest.importorskip("matplotlib")
    from PIL import Image
    out = tmp_path / "lift.png"
    RL.render(LIFT, str(out))
    w, h = Image.open(out).size
    assert abs(w / h - 2554 / 784) < 0.01, (w, h)
