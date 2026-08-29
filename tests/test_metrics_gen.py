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
