# Ported from ARS v5 02-Scripts/tests/test_rege_codes.py at a491b5c (James Gilmore); logic unchanged.
"""Reg E classification from config codes (1585: numeric election codes).

    python -m pytest tests/test_rege_codes.py -q
"""
import pathlib
import sys

import pytest

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.monthly_analysis import rege                              # noqa: E402


def test_numeric_codes_classify_via_config():
    cfg = {"RegEOptInCode": ["1", "1.0"],
           "RegEOptOutCode": ["2", "2.0", "3", "3.0", "4", "4.0"]}
    values = pd.Series(["1.0", "2.0", "3.0", "4.0", "1", "", None])
    warnings = []
    out = rege.classify(values, cfg, warnings.append)
    assert list(out[:5]) == [rege.OPT_IN, rege.OPT_OUT, rege.OPT_OUT,
                             rege.OPT_OUT, rege.OPT_IN]
    assert list(out[5:]) == [rege.BLANK, rege.BLANK]
    assert not warnings                     # nothing left to pattern-guess


@pytest.mark.skip(reason="reads v5's clients_config.json, which holds client data and stays out of "
                         "this repo; it checks v5's config, not the ported code")
def test_1585_config_carries_the_codes():
    """1585 must have Reg E codes configured -- by VALUE, not by spelling.

    This used to demand the literal pair {"1", "1.0"}. RegEOptInCode is a
    CODE_SHEET_FIELD, so `build_client_config.py --apply` regenerates it from
    the sheet as {"1"} and drops the hand-added float variant -- which is
    exactly what happened on the work PC (#174). The test then failed for a
    config rebuild rather than for anything being wrong.

    classify() now matches on the code's value, so either spelling works.
    What still matters is that the codes are there at all.
    """
    import json

    from ti.monthly_analysis.rege import _code_key

    cfg = json.loads((__import__("ti.dictionaries", fromlist=["folder"]).folder() /
                      "clients_config.json").read_text(encoding="utf-8-sig"))["1585"]
    assert {_code_key(c) for c in cfg["RegEOptInCode"]} == {"1"}
    assert {"2", "3", "4"} <= {_code_key(c)
                               for c in cfg.get("RegEOptOutCode", [])}


def test_a_float_spelled_code_matches_an_integer_config_and_the_reverse():
    """1585's config lost "1.0" to a config rebuild -- RegEOptInCode is a
    CODE_SHEET_FIELD, so the generator derives "1" from the sheet and drops
    the hand-added variant. Those rows then matched nothing and the opt-in
    rate undercounted (#174).

    Codes now match by VALUE, so the spelling in the file and the spelling in
    the config no longer have to agree.
    """
    import pandas as pd
    from ti.monthly_analysis import rege

    warnings = []
    out = rege.classify(pd.Series(["1.0", "1", "2.0", ""]),
                        {"RegEOptInCode": ["1"], "RegEOptOutCode": ["2"]},
                        warnings.append)
    assert list(out) == [rege.OPT_IN, rege.OPT_IN, rege.OPT_OUT, rege.BLANK]

    # the reverse spelling, config float against integer data
    out2 = rege.classify(pd.Series(["1", "1.0"]),
                         {"RegEOptInCode": ["1.0"]}, lambda *_a: None)
    assert list(out2) == [rege.OPT_IN, rege.OPT_IN]


def test_the_run_says_how_many_rows_the_looser_match_recovered():
    """The opt-in rate must never move without the run saying why."""
    import pandas as pd
    from ti.monthly_analysis import rege

    warnings = []
    rege.classify(pd.Series(["1.0"] * 7 + ["1"] * 3),
                  {"RegEOptInCode": ["1"]}, warnings.append)
    note = [w for w in warnings if "Reg E" in w]
    assert note and "7" in note[0], warnings


def test_nothing_is_reported_when_the_spellings_already_agree():
    """A warning on every run is a warning nobody reads."""
    import pandas as pd
    from ti.monthly_analysis import rege

    warnings = []
    rege.classify(pd.Series(["1", "1", "2"]),
                  {"RegEOptInCode": ["1"], "RegEOptOutCode": ["2"]},
                  warnings.append)
    assert not [w for w in warnings if "Reg E" in w], warnings


def test_non_numeric_codes_are_untouched():
    import pandas as pd
    from ti.monthly_analysis import rege

    out = rege.classify(pd.Series(["Y", "N", "OPT IN"]),
                        {"RegEOptInCode": ["Y", "OPT IN"],
                         "RegEOptOutCode": ["N"]}, lambda *_a: None)
    assert list(out) == [rege.OPT_IN, rege.OPT_OUT, rege.OPT_IN]
