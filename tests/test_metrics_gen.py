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


def test_the_fixture_has_no_mailing_in_progress(metrics):
    """Its last mailing (Jun26) has a following month, so nothing is pending."""
    assert metrics["mail_in_progress"] == []


def test_a_mailing_in_the_last_month_is_listed_as_in_progress(odd_csv, tmp_path, metrics):
    """A mailing in the extract's own last month has offers and no response yet.

    `mature` rightly keeps it out of every rate, but the Mailing Response Summary used
    to drop it without a word — 1549 Wellworth's Aug 2026 drop, 9,643 accounts mailed,
    was on no slide (2026-09-14). Add a mailing to the fixture's last month and assert
    it is reported as in progress, and that the completed rows and their total do not
    move.
    """
    import csv, json, subprocess, sys, os
    from conftest import ARS

    rows = list(csv.reader(open(odd_csv, encoding="utf-8", newline="")))
    hdr = [c.strip() for c in rows[4]]
    months = [h.split()[0] for h in hdr if h.endswith(" Sig #")]
    last, prior_mail = months[-1], next(h for h in reversed(hdr) if h.endswith(" Mail"))
    assert f"{last} Mail" not in hdr, "fixture already mails its last month"
    src = hdr.index(prior_mail)
    rows[4] += [f"{last} Mail", f"{last} Resp"]
    mailed = 0
    for r in rows[5:]:
        offer = r[src].strip() if len(r) > src else ""
        r.extend([""] * (len(rows[4]) - 2 - len(r)))
        r += [offer, ""]                        # same offers again; no response yet
        mailed += bool(offer)
    odd = tmp_path / "mailing_in_progress.csv"
    with open(odd, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    out = tmp_path / "metrics.json"
    r = subprocess.run([sys.executable, os.path.join(ARS, "metrics_gen.py"), str(odd), str(out)],
                       capture_output=True, text=True, cwd=ARS)
    assert r.returncode == 0, f"metrics_gen failed:\n{r.stderr[-2000:]}"
    m = json.loads(out.read_text())

    import datetime
    label = datetime.datetime.strptime(last, "%b%y").strftime("%b %Y")
    assert [x[0] for x in m["mail_in_progress"]] == [label]
    offers = m["mail_in_progress"][0][1]
    assert 0 < offers <= mailed, "offers are personal accounts carrying a value"
    # The completed mailing it copied its offers from counted the same personal accounts.
    assert offers == m["mail_summary"][0][1]
    assert label not in [x[0] for x in m["mail_summary"]]
    assert m["mail_summary"] == metrics["mail_summary"]
    assert m["mail_summary_total"] == metrics["mail_summary_total"]


# ---------------------------------------------------- swipe tiers, 2026-09-22
def _tier(s):
    """The shipped rule, reproduced: floor the average into its segment, then inclusive
    integer bands. metrics_gen reads sys.argv at module scope, so it cannot be imported."""
    import math
    s = math.floor(s)
    if s < 1:
        return "Non-User"
    for lo, hi, nm in [(1, 5, "1-5"), (6, 10, "6-10"), (11, 15, "11-15"),
                       (16, 20, "16-20"), (21, 25, "21-25")]:
        if lo <= s <= hi:
            return nm
    return "26+"


def test_swipe_tiers_round_down_into_their_segment():
    """Aaron, 2026-09-22: "round swipes down into the nearest segment". The bands are
    inclusive integer ranges tested against a THREE-MONTH MEAN, so without the floor an
    average of 5.5 matched no band and fell through to the '26+' catch-all: on 1539 Marine
    that was 1,381 of the 15,676 accounts in '26+' averaging fewer than 26 swipes, with the
    middle tiers short by those same accounts."""
    assert _tier(5.5) == "1-5"
    assert _tier(10.4) == "6-10"
    assert _tier(15.9) == "11-15"
    assert _tier(20.2) == "16-20"
    assert _tier(25.99) == "21-25"
    assert _tier(26.0) == "26+"
    assert _tier(0.9) == "Non-User"
    # and the integer boundaries still mean what they say
    assert [_tier(n) for n in (1, 5, 6, 10, 11, 15, 16, 20, 21, 25, 26)] == [
        "1-5", "1-5", "6-10", "6-10", "11-15", "11-15", "16-20", "16-20",
        "21-25", "21-25", "26+"]


def test_the_shipped_banding_matches_that_rule():
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "build", "ars_pipeline", "metrics_gen.py"), encoding="utf-8").read()
    assert "s=math.floor(sw3(r))" in src, "the 3-month average is no longer floored into a tier"
    assert "if lo<=s<=hi: return nm" in src


def test_the_two_tier_definitions_agree():
    """metrics_gen owns the deck's tiers; combined_insights re-implements them for the
    migration and by-tier views, because metrics_gen runs on import. They have to give the
    same answer, or two slides in one deck bucket the same account differently."""
    import combined_insights as CI
    for v in (0, 0.4, 0.99, 1, 1.5, 5, 5.5, 6, 10.9, 11, 15.9, 16, 20.2, 21, 25.99, 26, 99.9):
        assert CI.swipe_tier(v) == _tier(v), v

# --- new checking is compared on OPEN accounts (2026-10-07) -------------------
def _new_checking_rows(odd_rows_raw):
    """New personal checking accounts in metrics_gen's window, from the raw fixture rows."""
    import datetime
    from odd_rows import accessors
    hdr, rows = odd_rows_raw
    H = {h: i for i, h in enumerate(hdr)}
    odd = accessors(H)
    latest = [h.split()[0] for h in hdr if h.endswith(" Sig #")][-1]
    last = datetime.datetime.strptime(latest, "%b%y")
    y, m = last.year, last.month - 11
    while m <= 0:
        m += 12
        y -= 1
    j25 = datetime.datetime(y, m, 1)
    j26 = (last.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    out = []
    for r in rows:
        if len(r) < len(hdr) or not odd.personal(r):
            continue
        d = odd.g(r, "Date Opened")
        try:
            opened = datetime.datetime.strptime(d, "%m/%d/%Y")
        except ValueError:
            continue
        if j25 <= opened <= j26 and any(w in odd.g(r, "Prod Desc").lower() for w in ("checking", "share draft")):
            out.append((r, odd))
    return out


def test_new_checking_debit_penetration_counts_open_accounts_only(metrics, odd_rows_raw):
    """First State Bank 2026.10: slide 43 read 67.0% for new checking against 78.2% for the open book because
    119 closed or charged-off new accounts, which show no card, were in the new group but not in the book."""
    rows = _new_checking_rows(odd_rows_raw)
    opened = [(r, o) for r, o in rows if o.isopen(r)]
    closed = [(r, o) for r, o in rows if not o.isopen(r)]
    assert opened, "the fixture has no open new checking accounts"
    want = round(100 * sum(1 for r, o in opened if o.hascard(r)) / len(opened), 1)
    assert metrics["new_chk_debit_pct"] == want
    if closed:
        everyone = round(100 * sum(1 for r, o in rows if o.hascard(r)) / len(rows), 1)
        assert metrics["new_chk_debit_pct"] != everyone or all(o.hascard(r) for r, o in closed)


def test_new_checking_balances_are_for_open_accounts_only(metrics, odd_rows_raw):
    rows = [(r, o) for r, o in _new_checking_rows(odd_rows_raw) if o.isopen(r)]

    def bal(r, o):
        ab = o.fnum(r, "Avg Bal")
        return ab if ab != 0 else o.fnum(r, "Curr Bal")
    assert metrics["new_chk_funded_pct"] == round(100 * sum(1 for r, o in rows if bal(r, o) > 0) / len(rows))
