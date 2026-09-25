"""The ODD's `<mon> MTD` column is an NSF/OD ITEM COUNT, never fee income.

The two descriptions had drifted apart and nothing caught it: `odd_rows.nsf()`
called the column "NSF/OD fee income", while `charts_gen` titled the same
quantity "NSF/OD Items", `metrics_gen` named it items12/nsf_last_items,
`build_lift_matrix` multiplied it BY a per-item fee, and `oddd_optimize`
published it as `od_fee_income_MTD` formatted with a dollar sign.

The evidence, gathered 2026-09-01 from the 2026.08 extracts of six clients
(1539, 1705, 1204, 1075, 1549, 1218 — ~580k account-months):

  * Every populated `<mon> MTD` cell is a non-negative INTEGER. Not one value
    carries cents.
  * The values decay smoothly from 0: 1, 2, 3, 4, 5, ... with monotonically
    falling frequency. Fee income would cluster on multiples of the fee.
  * `<mon> YTD` is the calendar-year cumulative of the same integers — 19,552
    of 19,573 sampled 1539 accounts reconcile exactly against Jan..Jul MTD.
  * The ODD carries no OD-fee dollar column at all. NSF revenue reaches the
    deck from the client workbook ("Total NSF Revenue"), via base_tab_extract.

Per the CLAUDE.md standing rule, these pin the meaning in both directions: the
DATA must keep the shape of an item count, and no module that reads the column
may describe it in money terms again.
"""
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every module that reads or republishes the MTD column.
MTD_READERS = [
    "build/ars_pipeline/odd_rows.py",
    "build/ars_pipeline/lift_values.py",
    "build/ars_pipeline/charts_gen.py",
    "scripts/oddd_optimize.py",
]

# Money words applied to NSF/OD. Matched only when they sit next to the NSF/OD
# subject, so "Total NSF Revenue" (the WORKBOOK column, which really is dollars)
# and the explanatory prose in this repo's own comments stay legible — those are
# allowed by NOT_A_CLAIM below.
MONEY_CLAIM = re.compile(
    r"(nsf|od|overdraft)[\w/ ]{0,12}\b(fee income|income|revenue)\b"
    r"|(fee income|revenue)[\w/ ]{0,12}\b(nsf|od|overdraft)\b",
    re.I,
)

# Lines that mention the money reading in order to DENY it, or that name the
# workbook's genuine dollar column, are not claims about the MTD column.
NOT_A_CLAIM = re.compile(
    r"not dollars|never dollars|item count|items, not|is not in the odd"
    r"|total nsf revenue|would price the fee twice|used to say|no od-fee dollar",
    re.I,
)


def _norm(text):
    """Underscores read as spaces, so `od_fee_income_MTD` is caught as prose is.

    `_` is a word character, so a word-boundary-anchored pattern misses every
    snake_case identifier — which is exactly the form the defect took in
    oddd_optimize.
    """
    return text.replace("_", " ")


def _months(hdr):
    return sorted({m.group(1) for m in
                   (re.match(r"^([A-Z][a-z]{2}\d{2}) MTD$", h) for h in hdr) if m})


# --- the data keeps the shape of a count ---------------------------------
def test_every_mtd_cell_is_a_whole_number(odd_rows_raw):
    """Fee income carries cents and clusters on multiples of the fee. Counts do neither."""
    hdr, rows = odd_rows_raw
    cols = [(m, hdr.index(f"{m} MTD")) for m in _months(hdr)]
    assert cols, "fixture carries no `<mon> MTD` columns"
    bad = []
    for r in rows:
        for m, i in cols:
            v = r[i].strip()
            if not v:
                continue
            if not re.fullmatch(r"\d+", v):
                bad.append(f"{m}={v!r}")
    assert not bad, f"non-integer MTD values (dollars?): {bad[:10]}"


def test_mtd_magnitudes_are_count_scale_not_fee_scale(odd_rows_raw):
    """A per-account month of NSF fee income would run tens to hundreds of dollars.

    Real extracts put the mean under 1 item per account-month; the guard is set
    an order of magnitude above that, low enough that any dollar-scale column
    substituted here trips it.
    """
    hdr, rows = odd_rows_raw
    cols = [hdr.index(f"{m} MTD") for m in _months(hdr)]
    vals = [float(r[i]) for r in rows for i in cols if r[i].strip()]
    assert vals
    mean = sum(vals) / len(vals)
    assert mean < 10, f"mean MTD = {mean:.2f} — that is fee-income scale, not items"


def test_ytd_is_the_cumulative_of_the_same_unit(odd_rows_raw):
    """YTD is the calendar-year running total of MTD, so it is never smaller."""
    hdr, rows = odd_rows_raw
    pairs = [(m, hdr.index(f"{m} MTD"), hdr.index(f"{m} YTD"))
             for m in _months(hdr) if f"{m} YTD" in hdr]
    assert pairs, "fixture carries no `<mon> YTD` columns"
    for r in rows[:200]:
        for m, i, j in pairs:
            if not (r[i].strip() and r[j].strip()):
                continue
            assert re.fullmatch(r"\d+", r[j].strip()), f"{m} YTD is not a whole number"
            assert float(r[j]) >= float(r[i]), f"{m} YTD < MTD — not a cumulative count"


# --- odd_rows.nsf() returns that count, unchanged -------------------------
def test_nsf_returns_the_mtd_count_verbatim():
    from odd_rows import accessors
    odd = accessors({"Jul26 MTD": 0})
    assert odd.nsf(["3"], "Jul26") == 3.0
    assert odd.nsf([""], "Jul26") == 0.0


def test_nsf_docstring_says_items_and_not_fee_income():
    """The docstring is the thing that drifted. Pin its claim, not its prose."""
    from odd_rows import accessors
    doc = accessors({}).nsf.__doc__ or ""
    assert "ITEM COUNT" in doc, "odd_rows.nsf() must state that MTD is an item count"
    assert "fee income for month" not in doc.lower()


# --- no module may call it money again ------------------------------------
@pytest.mark.parametrize("rel", MTD_READERS)
def test_no_mtd_reader_describes_the_column_as_money(rel):
    """The drift guard: the defect was two files describing one column two ways."""
    path = os.path.join(REPO, rel)
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    offenders = [f"{rel}:{n}: {ln.strip()}" for n, ln in enumerate(lines, 1)
                 if MONEY_CLAIM.search(_norm(ln)) and not NOT_A_CLAIM.search(_norm(ln))]
    assert not offenders, (
        "the `<mon> MTD` column is an NSF/OD ITEM COUNT — these lines call it money:\n  "
        + "\n  ".join(offenders))


def test_the_guard_would_catch_the_original_defect():
    """A guard nobody has seen fail is a guard nobody can trust."""
    assert MONEY_CLAIM.search(_norm(
        '"""NSF/OD fee income for month m (the MTD column)."""'))
    assert MONEY_CLAIM.search(_norm('"od_fee_income_MTD": series(money["MTD"]),'))
    assert MONEY_CLAIM.search(_norm(
        '  * fee12 - 12-month average MONTHLY NSF/OD fee income (the `MTD` column).'))
    assert MONEY_CLAIM.search(_norm('A("## Top Branches by OD Income (latest MTD)")'))
    # ...and does not fire on the workbook's genuine dollar column, or on prose
    # that exists to deny the money reading.
    assert NOT_A_CLAIM.search(_norm('find_row(amr, "Total NSF Revenue")'))
    assert NOT_A_CLAIM.search(_norm("MTD is an NSF/OD item count, not dollars"))


# --- the Lift Matrix contract: items in, fee applied once -----------------
# build_lift_matrix and lift_extract carried their own valuation until 2026-09-25; build_lift_matrix
# now wraps lift_values (the one definition) and lift_extract is gone, so the contract is pinned there.
def test_lift_values_reads_mtd_as_items():
    import lift_values
    src = open(lift_values.__file__, encoding="utf-8").read()
    assert "odd.nsf(r, m)" in src, "lift_values must read NSF/OD through odd_rows.nsf (items)"


def test_lift_matrix_multiplies_items_by_the_fee_exactly_once():
    """If MTD were already dollars, this would price the fee twice."""
    import lift_values
    seg = {s: {"n": 1, "dist": 1 / 7, "spend": 0.0, "items": 2.0} for s in lift_values.SEGMENTS}
    v = lift_values.values({"segments": seg}, ic_rate=0.006, nsf_fee=30.0, collection=1.0)
    nu = next(r for r in v["segments"] if r["segment"] == "NU")
    assert nu["nsf"] == pytest.approx(60.0)      # 2 items x $30, once
    assert nu["dda"] == pytest.approx(60.0)

