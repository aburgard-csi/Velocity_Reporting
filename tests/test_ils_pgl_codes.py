"""ILS pre-go-live codes (build/ils_pipeline/pre_go_live/codes.py).

v5's codes tests (v5 tests/test_pgl_setup.py, the codes block), on the RPE input folder.
"""
from ils_pipeline import pgl_input
from ils_pipeline.pre_go_live import codes as codes_mod
from ils_pipeline.pre_go_live import loader
from test_ils_pgl_loader import root  # noqa: F401 (fixture)


def test_codes_validate_against_file(root):
    found = pgl_input.find_extract("1737")
    df, _ = loader.load(found.path)
    good = codes_mod.Codes(open_status=["O"], od_eligible=["003", "005"], rege_opt_in=["Y"])
    assert codes_mod.validate(good, df) == []
    bad = codes_mod.Codes(open_status=["OPEN"], od_eligible=["003"], rege_opt_in=["Y"])
    problems = codes_mod.validate(bad, df)
    assert len(problems) == 1 and "OPEN" in problems[0] and "O" in problems[0]


def test_codes_accept_scalars():
    c = codes_mod.Codes(open_status="O", od_eligible="003", rege_opt_in="Y")
    assert c.open_status == ["O"] and c.od_eligible == ["003"]
