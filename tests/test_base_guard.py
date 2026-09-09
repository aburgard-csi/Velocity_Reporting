"""base_guard — an ARS workbook saved without evaluating its formulas is refused.

openpyxl reads cached values, so an unevaluated workbook extracts as the
template's defaults (1 month, 0 mailings, $0) and looks like a client with no
revenue. 1539's 2026.08 workbook arrived that way on 2026-09-08. The guard has
one definition and every ARS entry point calls it; the second test pins that,
because a guard the dashboard had and the builder lacked is how it was caught
on a page and would have shipped in a deck.
"""
import os
import re

import pytest

import base_guard as G

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("base,expect", [
    ({"months": 1, "mailings": 0, "ltd_revenue": 0, "cur_revenue": 0}, True),
    ({"months": None, "ltd_revenue": None, "cur_revenue": None}, True),
    ({"months": "1", "ltd_revenue": "0", "cur_revenue": ""}, True),
    ({"months": 96, "mailings": 38, "ltd_revenue": 10677533.23, "cur_revenue": 154881.24}, False),
    ({"months": 1, "ltd_revenue": 0, "cur_revenue": 4200.0}, False),     # brand-new client, real revenue
    ({"months": 2, "ltd_revenue": 0, "cur_revenue": 0}, False),          # two months in: not the template
])
def test_uncalculated(base, expect):
    assert G.uncalculated(base) is expect


def test_check_stops_the_build_and_names_the_workbook():
    with pytest.raises(SystemExit) as e:
        G.check({"months": 1, "ltd_revenue": 0, "cur_revenue": 0}, "1539-2026.08-Marine FCU-Workbook_v2_1_0.xlsx")
    msg = str(e.value)
    assert msg.startswith("UNEVALUATED WORKBOOK")
    assert "1539-2026.08-Marine FCU-Workbook_v2_1_0.xlsx" in msg and "Excel" in msg
    good = {"months": 96, "ltd_revenue": 1.0, "cur_revenue": 1.0}
    assert G.check(good, "x.xlsx") is good


@pytest.mark.parametrize("path", [
    "build/ars_pipeline/extract_base_gen.py",
    "build/ars_pipeline/base_tab_extract.py",
    "build/ars_pipeline/build_ars_gen.py",
    "scripts/refresh_performance_dashboard.py",
])
def test_every_ars_entry_point_uses_the_one_guard(path):
    src = open(os.path.join(REPO, path), encoding="utf-8").read()
    assert re.search(r"\bbase_guard\b", src), path + " does not use base_guard"
