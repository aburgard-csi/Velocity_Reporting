"""Extracts that are wrong in ways real clients' extracts were wrong (2026-09-14 all-client builds).

* 1147 Sutton: 3 of 28,930 rows carry one extra field. pandas read such a row with its
  first cell as an index and shifted every later cell, so 'Customer Opt In' reached a
  money column and oddd_optimize died casting it. The row is now skipped.
* 1226 Ellafi: Stat Desc is blank on every row (the status is in Stat Code), so no
  account reads as open and the Reg E rate divided by zero.
* 1121 Timberland: newer accounts carry numbers ('1', '39') in Prod Desc, so no new
  checking account was found and mean() of nothing crashed.

The last two are data problems, not code problems: metrics_gen now stops with a
POSSIBLE DATA ISSUE message that names what is missing, never a traceback. Synthetic
fixture only (tests/fixtures/make_odd.py), no member data.
"""
import csv
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tests", "fixtures"))
import make_odd  # noqa: E402


def _fixture(tmp_path, edit):
    p = tmp_path / "odd.csv"
    make_odd.build(str(p))
    with open(p, encoding="latin-1", newline="") as fh:
        rows = list(csv.reader(fh))
    hi = next(i for i, r in enumerate(rows) if "Acct ID" in r)
    edit(rows[hi], rows[hi + 1:])
    with open(p, "w", encoding="latin-1", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return p


def _run(*args):
    return subprocess.run([sys.executable, *map(str, args)], cwd=REPO, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))


def _column(header, suffix):
    i = next((k for k, c in enumerate(header) if c.strip().endswith(suffix)), None)
    if i is None:
        pytest.skip(f"fixture has no '{suffix}' column")
    return i


def _find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            got = _find(v, key)
            if got is not None:
                return got
    return None


def test_text_shifted_into_a_money_column_is_counted_and_flagged_not_fatal(tmp_path):
    """pandas keeps a row with one extra field and shifts its cells, so the text lands in a
    numeric column (`index_col=False` does not prevent it — tried and reverted). The
    arrow path cast strictly and died; the pandas path already coerced. Both now treat
    the cell as missing, and the pack's flags carry the count so it is never silent."""
    def edit(header, data):
        i = _column(header, " Sig $")
        for row in data[10:13]:
            row.insert(i, "Customer Opt In")
    p = _fixture(tmp_path, edit)
    r = _run("scripts/oddd_optimize.py", "--input", p, "--out", tmp_path / "pack",
             "--client", "9999", "--name", "Test")
    assert r.returncode == 0, r.stderr[-3000:]
    pack = json.loads((tmp_path / "pack" / "oddd_metrics.json").read_text(encoding="utf-8"))
    bad = _find(pack, "non_numeric_cells")
    assert bad and bad["total"] >= 3, "the malformed cells must be surfaced in the pack's flags"


def test_a_clean_extract_flags_no_non_numeric_cells(tmp_path):
    p = _fixture(tmp_path, lambda header, data: None)
    r = _run("scripts/oddd_optimize.py", "--input", p, "--out", tmp_path / "pack",
             "--client", "9999", "--name", "Test")
    assert r.returncode == 0, r.stderr[-3000:]
    pack = json.loads((tmp_path / "pack" / "oddd_metrics.json").read_text(encoding="utf-8"))
    assert not (_find(pack, "non_numeric_cells") or {}).get("total")


def test_no_open_accounts_is_a_possible_data_issue_not_a_zero_division(tmp_path):
    def edit(header, data):
        # Both status fields: a blank Stat Desc now falls back to Stat Code (O / A = Open).
        cols = [_column(header, "Stat Desc")] + [k for k, c in enumerate(header) if c.strip() == "Stat Code"]
        for row in data:
            for i in cols:
                if i < len(row):
                    row[i] = ""
    p = _fixture(tmp_path, edit)
    r = _run("build/ars_pipeline/metrics_gen.py", p, tmp_path / "metrics.json")
    assert r.returncode != 0 and "Traceback" not in r.stderr, r.stderr[-3000:]
    assert "POSSIBLE DATA ISSUE" in r.stderr and "Stat Desc" in r.stderr


def test_no_card_holder_swiping_in_the_latest_month_is_a_possible_data_issue_not_an_empty_mean(tmp_path):
    """1615 Cape & Coast (2026-09-15): no open card holder swiped in the latest month, and
    mean() of nothing crashed with a StatisticsError that named no cause.

    1615's book as a whole swiped normally that month; only its PERSONAL card holders did
    not. So the fixture keeps the month's total swipes up on the non-personal rows. Zeroing
    every row's swipes instead makes the whole month read as an unfinished extract, which
    month_complete (2026-09-17) rightly leaves out, and the case under test never arises.
    """
    def edit(header, data):
        months = sorted({c.strip()[:5] for c in header if c.strip().endswith(" Sig #")},
                        key=lambda t: (t[3:], "JanFebMarAprMayJunJulAugSepOctNovDec".index(t[:3])))
        latest = months[-1]
        cols = [k for k, c in enumerate(header) if c.strip() in (f"{latest} Sig #", f"{latest} PIN #")]
        biz = _column(header, "Business?")
        for row in data:
            personal = biz < len(row) and row[biz].strip() == "No"
            for i in cols:
                if i < len(row):
                    row[i] = "0" if personal else "400"
    p = _fixture(tmp_path, edit)
    r = _run("build/ars_pipeline/metrics_gen.py", p, tmp_path / "metrics.json")
    assert r.returncode != 0 and "Traceback" not in r.stderr, r.stderr[-3000:]
    assert "POSSIBLE DATA ISSUE" in r.stderr and "used the card" in r.stderr


def test_no_named_checking_products_is_a_possible_data_issue_not_an_empty_mean(tmp_path):
    def edit(header, data):
        i = _column(header, "Prod Desc")
        for n, row in enumerate(data):
            if i < len(row):
                row[i] = str(n % 40)
    p = _fixture(tmp_path, edit)
    r = _run("build/ars_pipeline/metrics_gen.py", p, tmp_path / "metrics.json")
    assert r.returncode != 0 and "Traceback" not in r.stderr, r.stderr[-3000:]
    assert "POSSIBLE DATA ISSUE" in r.stderr and "Prod Desc" in r.stderr
