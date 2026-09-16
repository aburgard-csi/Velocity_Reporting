"""The worked example in the ICS per-account-per-month subtitles reads the sheet's first cohort.

Slides "Interchange Revenue per Account per Month", "NSF/OD & Other Fees per Account per
Month" and "Spread Revenue per Account per Month" each explain the chart with one cohort:
"e.g. Dec 25: $3,693.10 / 103 / 9 = $3.98". The cohort label, account count and months
open were literals ("Nov 25 ... / 19 / 8") left from the reference client, so every full
ICS deck printed them — over the client's own dollar figure on two of the three slides,
and fully literal on the interchange one. 1776 CoastHills (2026.08) said
"Nov 25: $3,693.10 / 19 / 8 = $24.30" while its first cohort was Dec 25 with 103 accounts.
Nothing in the gate compared the example to the sheet, so it shipped on every full deck.

Every figure here is synthetic.
"""
import os
import re

import pytest

import build_ics_gen as G
import ics_charts_gen as CH
from test_ics_local_sheet import (NAME, PERIOD, CID, REPO, root, _sheet,  # noqa: F401 (fixture)
                                  write_referrals, write_charts, write_workbook,
                                  referral_file, charts_file, workbook_file)

EXAMPLE = re.compile(r"e\.g\. ([A-Z][a-z]{2} \d{2}): \$([\d,]+\.\d{2}) / ([\d,]+) / (\d+) = \$([\d,]+\.\d{2})\)")

SLIDES = {  # title -> the cohort dollars that slide's example must use
    "Interchange Revenue per Account per Month": lambda md: md["interchange"][0],
    "NSF/OD & Other Fees per Account per Month": lambda md: md["nsf_od"][0] + md["other_fees"][0],
    "Spread Revenue per Account per Month": lambda md: md["spread"][0],
}


def _num(s):
    return float(s.replace(",", ""))


def test_the_example_is_the_first_cohort():
    d = {"monthly_detail": {"months": ["Dec 25"] + [f"M{i}" for i in range(8)],
                            "accounts_opened": [103] + [50] * 8,
                            "interchange": [3693.10] + [1.0] * 8}}
    assert G.cohort_example(d, 3693.10) == "Dec 25: $3,693.10 / 103 / 9 = $3.98"


def test_months_open_is_the_charts_count():
    """The caption divides by what the chart beside it divides by."""
    d = {"monthly_detail": {"months": ["Mar 26", "Apr 26", "May 26"], "accounts_opened": [4, 5, 6]}}
    assert G.cohort_example(d, 120.0).endswith(f"/ 4 / {CH._months_open(d)[0]} = $10.00")


def test_no_literal_cohort_is_left_in_the_builder():
    src = open(os.path.join(REPO, "build", "ics_pipeline", "build_ics_gen.py"), encoding="utf-8").read()
    body = src.split("# 8-13 monthly detail", 1)[1]
    assert "Nov 25" not in body and "/ 19 / 8" not in body and "/19/8" not in body
    assert body.count("cohort_example(d, ") == 3


def test_built_deck_examples_match_the_sheet(root, tmp_path):
    """A full ICS build from a synthetic sheet whose first cohort is Dec 25 with 10
    accounts over 9 months — none of which is the old literal."""
    from pptx import Presentation
    write_referrals(referral_file(root))
    write_charts(charts_file(root))
    write_workbook(workbook_file(root, PERIOD))
    d = _sheet(root, tmp_path)
    md = d["monthly_detail"]
    assert (md["months"][0], md["accounts_opened"][0]) != ("Nov 25", 19)

    out = str(tmp_path / "deck" / f"{CID}-{PERIOD}-ICS-{NAME} ICS Results.pptx")
    os.makedirs(os.path.dirname(out))
    G.build(d, os.path.join(REPO, "templates", "ics_template.pptx"), out)

    found = {}
    for s in Presentation(out).slides:
        texts = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame]
        title = next((t for t in texts if t in SLIDES), None)
        if title:
            found[title] = [m for t in texts for m in EXAMPLE.findall(t)]
    assert set(found) == set(SLIDES), "every per-account slide must be in a full deck"

    for title, series in SLIDES.items():
        assert len(found[title]) == 1, f"{title}: expected one worked example, got {found[title]}"
        label, dollars, accounts, months, result = found[title][0]
        want = series(md)
        assert label == md["months"][0], title
        assert int(accounts.replace(",", "")) == md["accounts_opened"][0], title
        assert int(months) == len(md["months"]) == CH._months_open(d)[0], title
        assert _num(dollars) == pytest.approx(want, abs=0.005), title
        assert _num(result) == pytest.approx(want / md["accounts_opened"][0] / len(md["months"]), abs=0.005), title


def test_a_wide_first_cohort_still_fits_one_line(root, tmp_path):
    """The example now carries the client's own figures, so the subtitle's length follows
    the data. At $123,456.78 / 1,234 the old "(NSF/OD + other charges)" wording needed
    12.40in in a 12.10in box and the validator FAILed the deck. The whole deck must pass."""
    import subprocess
    import sys
    write_referrals(referral_file(root))
    write_charts(charts_file(root))
    write_workbook(workbook_file(root, PERIOD))
    d = _sheet(root, tmp_path)
    md = d["monthly_detail"]
    md["accounts_opened"][0] = 1234
    for k in ("interchange", "spread", "nsf_od"):
        md[k][0] = 123456.78
    out = str(tmp_path / "deck" / f"{CID}-{PERIOD}-ICS-{NAME} ICS Results.pptx")
    os.makedirs(os.path.dirname(out))
    G.build(d, os.path.join(REPO, "templates", "ics_template.pptx"), out)
    r = subprocess.run([sys.executable, os.path.join(REPO, "validation", "validate_deck.py"), out],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout[-3000:]
