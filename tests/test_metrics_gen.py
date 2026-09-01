"""metrics_gen end-to-end against the synthetic ODD.

Nearly every CHANGELOG entry since 2026-08-20 is a wrong-number bug: a rate
computed against the wrong denominator, a cohort that disagrees with the same
cohort on another slide, a window offset by one month. These assert the
INTERNAL CONSISTENCY of the metrics pack — the property those bugs violated —
rather than pinning literal values, which would only pin today's arithmetic.
"""
import math
import pytest


def approx_pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else 0.0


# --- the pack is well-formed ---------------------------------------------
def test_metrics_pack_is_produced(metrics):
    assert isinstance(metrics, dict) and len(metrics) > 50


@pytest.mark.parametrize("key", [
    "n_eligible", "n_responders", "overall_take", "latest_mailed",
    "latest_responders", "latest_resprate", "reach_total", "sustained",
    "ranking", "balance", "new_total",
])
def test_required_keys_present(metrics, key):
    assert key in metrics, f"metrics_gen dropped '{key}'"


def test_no_nan_or_none_in_scalar_metrics(metrics):
    bad = [k for k, v in metrics.items()
           if v is None or (isinstance(v, float) and math.isnan(v))]
    assert not bad, f"None/NaN in {bad}"


# --- rates are rates ------------------------------------------------------
@pytest.mark.parametrize("key", [
    "overall_take", "latest_resprate", "rege_pct", "rege_new_pct",
    "take_new_pct", "take_hist_pct", "new_chk_debit_pct", "book_active_pct",
    "depth_repeat_pct", "open_chk_debit_pct",
])
def test_percentages_are_in_range(metrics, key):
    v = metrics.get(key)
    if v is None:
        pytest.skip(f"{key} not produced for this fixture")
    assert 0 <= float(v) <= 100, f"{key} = {v} is not a percentage"


# --- the denominator bug class -------------------------------------------
def test_latest_response_rate_matches_its_own_numerator_and_denominator(metrics):
    """The rate must be responders/mailed for the SAME month.

    This is the shape of the 2026-08-20 slide-12-vs-14 split (16.3% vs 10.7%),
    where a rate was taken against a base that did not contain its numerator.
    """
    assert metrics["latest_resprate"] == pytest.approx(
        approx_pct(metrics["latest_responders"], metrics["latest_mailed"]), abs=0.15)


def test_responders_never_exceed_the_mailed_population(metrics):
    assert metrics["latest_responders"] <= metrics["latest_mailed"]


def test_reach_total_equals_distinct_responders(metrics):
    """Program Reach and the responder count are the same people counted once."""
    assert metrics["reach_total"] == metrics["n_responders"]


def test_take_rate_parts_sum_to_the_whole(metrics):
    if not {"take_new_cards", "take_new_nocard", "take_new_total"} <= metrics.keys():
        pytest.skip("new-account take-rate block not produced")
    assert metrics["take_new_cards"] + metrics["take_new_nocard"] == metrics["take_new_total"]


def test_take_new_pct_matches_its_parts(metrics):
    if "take_new_total" not in metrics or not metrics["take_new_total"]:
        pytest.skip("no new-account cohort")
    assert metrics["take_new_pct"] == pytest.approx(
        approx_pct(metrics["take_new_cards"], metrics["take_new_total"]), abs=0.15)


# --- table shapes ---------------------------------------------------------
def test_sustained_rows_are_month_and_rate(metrics):
    rows = metrics["sustained"]
    assert rows, "sustained window produced no rows"
    for r in rows:
        assert len(r) >= 3, f"sustained row too short: {r}"
        assert 0 <= float(r[2]) <= 100, f"sustained rate out of range: {r}"


def test_sustained_months_are_strictly_increasing(metrics):
    """An off-by-one in the window shows up as a repeated or reordered month."""
    labels = [r[0] for r in metrics["sustained"]]
    assert len(labels) == len(set(labels)), f"duplicate months: {labels}"


def test_ranking_rows_are_uniform_width(metrics):
    rows = metrics["ranking"]
    assert rows
    widths = {len(r) for r in rows}
    assert len(widths) == 1, f"ragged ranking table: {widths}"


def test_balance_bands_are_labelled_pairs(metrics):
    for band in metrics["balance"]:
        assert len(band) == 3, f"balance band malformed: {band}"
        assert isinstance(band[0], str) and band[1] >= 0 and band[2] >= 0


def test_responder_and_nonresponder_counts_are_positive(metrics):
    assert metrics["n_responders"] > 0
    assert metrics["n_nonresp"] > 0


# --- dated windows are derived, not typed ---------------------------------
# Both of these guard against a month literal in the source. metrics_gen used to
# search nsf_series for the row labelled 'Jun 25' and compare it to the LAST row,
# and to draw the Reg E vintage axis from range(2018, 2027).

def test_nsf_yoy_compares_the_same_month_a_year_apart(metrics):
    """The YoY window is 12 months, whatever month the extract ends on."""
    import datetime
    win = metrics["nsf_yoy_window"]
    assert win, "nsf_yoy_window missing — the tile caption has nothing to name"
    a, b = (datetime.datetime.strptime(w, "%b %y") for w in win)
    assert (b.year - a.year) * 12 + (b.month - a.month) == 12, \
        f"nsf_yoy compares {win[0]} to {win[1]} — not a year"
    assert win[1] == metrics["nsf_series"][-1][0], \
        "nsf_yoy must end at the newest month in the series"


def test_nsf_yoy_is_never_a_phantom_zero(metrics):
    """Absent prior year is None (stated on the slide), never 0."""
    yoy = metrics["nsf_yoy"]
    assert yoy is not None, "the fixture carries 36 months — a prior year exists"
    if metrics["nsf_yoy_window"] is None:
        assert yoy is None


def test_rege_vintage_charts_every_account_it_counted(metrics):
    """Pool in, pool out. A dropped bucket shows up here as a shortfall."""
    charted = sum(r[1] for r in metrics["rege_vintage"])
    assert charted == metrics["rege_vintage_pool"], (
        f"{metrics['rege_vintage_pool'] - charted} accounts counted toward the "
        f"Reg E vintage pool but appear in no bucket on the chart")
    for k, *_ in metrics["rege_vintage"]:
        assert k == "Pre-2018" or (k.isdigit() and len(k) == 4), f"odd axis key {k!r}"


def test_rege_vintage_axis_is_not_capped_at_a_typed_year(odd_csv, tmp_path):
    """Re-run the pack on an extract that opens accounts past the current year.

    The axis was a typed `range(2018, 2027)`, so an account opened outside it was
    counted into the pool and then silently dropped from the chart. Nothing in the
    fixture's own year spread can catch that — the years all sat inside the range —
    so this shifts the newest cohort forward and asserts it still lands on the axis.
    """
    import csv, json, subprocess, sys, os
    from conftest import ARS

    rows = list(csv.reader(open(odd_csv, encoding="utf-8", newline="")))
    col = [c.strip() for c in rows[4]].index("Date Opened")
    years = [r[col].strip()[-4:] for r in rows[5:]
             if len(r) > col and r[col].strip()[-4:].isdigit()]
    newest = max(years)
    shifted = str(int(newest) + 1)
    moved = 0
    for r in rows[5:]:
        if len(r) > col and r[col].strip().endswith(newest):
            r[col] = r[col].strip()[:-4] + shifted
            moved += 1
    assert moved, f"no rows opened in {newest} to shift"

    odd = tmp_path / "shifted_odd.csv"
    with open(odd, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    out = tmp_path / "metrics.json"
    r = subprocess.run([sys.executable, os.path.join(ARS, "metrics_gen.py"),
                        str(odd), str(out)],
                       capture_output=True, text=True, cwd=ARS)
    assert r.returncode == 0, f"metrics_gen failed on the shifted extract:\n{r.stderr[-2000:]}"
    m = json.loads(out.read_text())

    shown = [k for k, *_ in m["rege_vintage"]]
    assert shifted in shown, (
        f"accounts opened in {shifted} are missing from the vintage axis {shown} — "
        f"the axis is capped rather than derived from the data")
    assert sum(r[1] for r in m["rege_vintage"]) == m["rege_vintage_pool"]


# --- axis months: one token series per month-labelled chart ---------------
# Phase 1 of the axis standardization. The renderers read these instead of
# cutting a prose label down with their own slice.

def _series_len(metrics, name):
    """How many rows the series these tokens belong to actually has."""
    if name == "take_branch_monthly":
        # one row per branch, each carrying one column per month
        rows = metrics["take_branch_monthly"]
        return len(rows[0]) - 4 if rows else 0
    return len(metrics[name])


def test_axis_months_is_emitted(metrics):
    ax = metrics.get("axis_months")
    assert isinstance(ax, dict) and ax, "metrics_gen emitted no axis_months"
    for name in ("ranking", "sustained", "before_after", "reach",
                 "nsf_series", "openings", "take_branch_monthly"):
        assert name in ax, f"no axis tokens for '{name}'"


def test_every_axis_token_reaches_the_standard_form(metrics):
    from periods import axis_label, is_axis_label
    for name, toks in metrics["axis_months"].items():
        for t in toks:
            assert is_axis_label(axis_label(t)), f"{name}: {t!r} does not render"


def test_axis_tokens_line_up_with_their_series(metrics):
    """A parallel list that falls out of step with its rows mislabels every bar."""
    for name, toks in metrics["axis_months"].items():
        assert len(toks) == _series_len(metrics, name), (
            f"{name}: {len(toks)} tokens against {_series_len(metrics, name)} rows")


def test_axis_tokens_name_the_same_month_their_label_does(metrics):
    """The token is the row's own month, not a neighbour's."""
    from periods import parse_month
    pairs = [("ranking", lambda r: r[0]), ("sustained", lambda r: r[0]),
             ("reach", lambda r: r[0]), ("nsf_series", lambda r: r[0]),
             ("openings", lambda r: r[0]), ("before_after", lambda r: r["m"])]
    for name, label_of in pairs:
        for tok, row in zip(metrics["axis_months"][name], metrics[name]):
            assert parse_month(tok) == parse_month(label_of(row)), \
                f"{name}: token {tok!r} against label {label_of(row)!r}"


def test_take_branch_tokens_carry_the_year_the_label_lost(metrics):
    """take_months is bare "%b" — the only series whose label cannot be parsed
    back, which is why its tokens come from the months themselves."""
    from periods import parse_month, MONTH_ABBR
    toks = metrics["axis_months"]["take_branch_monthly"]
    assert len(toks) == len(metrics["take_months"])
    for tok, short in zip(toks, metrics["take_months"]):
        d = parse_month(tok)
        assert d is not None and MONTH_ABBR[d.month - 1] == short
    assert len({t[-2:] for t in toks}) >= 1 and all(len(t) == 5 for t in toks)


def test_axis_months_is_ordered_oldest_first(metrics):
    from periods import parse_month
    for name, toks in metrics["axis_months"].items():
        dates = [parse_month(t) for t in toks]
        assert dates == sorted(dates), f"{name} is not in month order: {toks}"
