# Ported from ARS v5 02-Scripts/tests/test_deposit_behaviour.py at a491b5c (James Gilmore); logic unchanged.
"""Deposit behaviour: the chapter, and the engine functions under it."""
import json
import pathlib
import re
import sys

import pandas as pd


from ti.core.periods import Month
from ti.core.subsets import build_subsets
from ti.monthly_analysis.deposit_behaviour import SATURATION_PCT, compute
from ti.core.deposits import behaviour as B
from ti.core.deposits import streams as S
from ti.core.deposits import trend as T

ANCHOR = Month.from_tag("Jul26")
ASOF = pd.Timestamp("2026-07-31")


def _odd(n=60):
    return pd.DataFrame({
        "Acct Number": [f"A{i}" for i in range(n)],
        "Debit?": ["Yes"] * n,
        "Date Opened": ["2019-01-15"] * n,
        "Curr Bal": [40000.0 if i % 3 == 0 else 500.0 for i in range(n)],
        "Avg Bal": [38000.0 if i % 3 == 0 else 500.0 for i in range(n)],
        **{f"{m}26 Spend": [100.0] * n
           for m in ("Feb", "Mar", "Apr", "May", "Jun", "Jul")},
    })


def _deposits(n=60, every=14, months=12, start="2025-08-01"):
    rows = []
    for i in range(n):
        day = pd.Timestamp(start)
        k = 0
        while k < months * 30 // every:
            rows.append([f"A{i}", day, 1, 1000.0])
            day += pd.to_timedelta(every, unit="D")
            k += 1
    return pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])


def _config(raw):
    return {"_deposit_raw": raw, "_deposit_monthly": T.monthly(raw)}


# ---- the engine -----------------------------------------------------------

def test_decline_month_dates_the_step_down():
    """The one thing balance.py says it cannot do: name the month."""
    rows = []
    day = pd.Timestamp("2025-08-01")
    for k in range(12):
        rows.append(["A", day, 1, 1000.0 if k < 8 else 200.0])
        day += pd.DateOffset(months=1)
    frame = pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])
    dated = T.decline_month(T.monthly(frame))
    assert dated["decline_month"].notna().all()
    assert dated["decline_month"].iloc[0] == pd.Timestamp("2026-04-01")


def test_a_steady_account_has_no_decline_month():
    """No step means NaT, never a month it never had."""
    dated = T.decline_month(T.monthly(_deposits(n=1, every=30)))
    assert dated["decline_month"].isna().all()


def test_only_an_established_rhythm_can_stop():
    """An account that never deposited regularly has nothing to lose.

    Flagging it anyway is how 'no recurring deposit' came to fire on 98.2%
    of a real book.
    """
    erratic = pd.DataFrame(
        [["A", pd.Timestamp("2025-08-01"), 1, 10.0],
         ["A", pd.Timestamp("2025-11-02"), 1, 900.0]],
        columns=["acct", "date", "dep_count", "dep_amount"])
    assert not B.stopped(erratic, ASOF)["recurring_stopped"].any()


def test_a_halted_payroll_is_flagged():
    frame = _deposits(n=1, every=14, months=6, start="2025-08-01")
    assert B.stopped(frame, ASOF)["recurring_stopped"].all()


def test_engine_functions_survive_an_empty_frame():
    empty = _deposits(n=0)
    assert not len(B.milestones(empty, ASOF))
    assert not len(B.stopped(empty, ASOF))
    assert T.concentration(empty) == []
    assert T.distribution(empty) == []
    assert T.book_monthly(T.monthly(empty)) == []


# ---- the section ----------------------------------------------------------

def test_section_declares_its_base_like_dctr_does():
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(_deposits()),
                  lambda m: None)
    assert out["dep_base"]
    assert out["dep_n"] > 0


def test_section_reports_nothing_rather_than_zeros_without_the_file():
    """A book-wide zero reads as a finding. Absent must read as absent."""
    out = compute(build_subsets(_odd(), {}, ANCHOR), {}, lambda m: None)
    assert out == {}


def test_section_always_reports_its_join_rate():
    """QC 3.1: the number to read before any other deposit number."""
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(_deposits()),
                  lambda m: None)
    assert out["dep_match_pct"] == 100.0
    assert out["dep_in_book_not_file"] == 0


def test_a_failed_join_warns_instead_of_reading_as_a_finding():
    raw = _deposits()
    raw["acct"] = "NOMATCH-" + raw["acct"]
    seen = []
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(raw), seen.append)
    assert out["dep_match_pct"] == 0.0
    assert any("joined only" in m for m in seen)


def test_accounts_outside_the_base_are_separated_from_accounts_nowhere_in_the_odd():
    """Two different facts that were one misleading number.

    The deposits file is institution-wide; the base is not. Accounts in the
    file but outside the base are EXPECTED (savings, business, closed) -- on
    RALLY that was 95,504 and it read as alarming. An account in the file that
    appears nowhere in the ODD at all is the real problem.
    """
    raw = _deposits(n=80)                      # A0..A79 deposit
    odd = _odd(60)                             # the ODD only knows A0..A59
    out = compute(build_subsets(odd, {}, ANCHOR), _config(raw), lambda m: None)
    # 20 accounts are in the file and not in the base...
    assert out["dep_in_file_not_base"] == 20
    # ...and because this ODD has no rows beyond the base, those same 20 are
    # genuinely unknown to the core, which is the number that matters.
    assert out["dep_in_file_not_odd"] == 20
    assert out["dep_file_found_in_odd_pct"] == 75.0


def test_an_unrecognised_file_account_warns_once_it_passes_the_threshold():
    """Warns below 90% recognised. A handful of strays is not an alarm; a
    tenth of the file being unknown to the core is."""
    raw = _deposits(n=60)
    stray = _deposits(n=10)
    stray["acct"] = "GHOST-" + stray["acct"]
    both = pd.concat([raw, stray], ignore_index=True)
    seen = []
    out = compute(build_subsets(_odd(60), {}, ANCHOR), _config(both), seen.append)
    assert out["dep_in_file_not_odd"] == 10
    assert out["dep_file_found_in_odd_pct"] == 85.7
    assert any("nowhere in the ODD" in m for m in seen)


def test_a_few_strays_do_not_trip_the_alarm():
    raw = _deposits(n=60)
    stray = _deposits(n=2)
    stray["acct"] = "GHOST-" + stray["acct"]
    both = pd.concat([raw, stray], ignore_index=True)
    seen = []
    out = compute(build_subsets(_odd(60), {}, ANCHOR), _config(both), seen.append)
    assert out["dep_in_file_not_odd"] == 2
    assert not any("nowhere in the ODD" in m for m in seen)


def test_windfalls_are_saturation_guarded_too():
    """RALLY flagged 52.5% of matched accounts as windfalls and it reached the
    report, because the guard was wired to two of four signals."""
    rows = []
    for i in range(60):
        day = pd.Timestamp("2025-08-01")
        for k in range(12):
            # tiny regular credits, then one enormous one: every account
            # clears 5x its own median, so the signal is meaningless.
            rows.append([f"A{i}", day, 1, 50_000.0 if k == 6 else 10.0])
            day += pd.DateOffset(months=1)
    raw = pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])
    seen = []
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(raw), seen.append)
    assert "dep_windfall_accounts" not in out
    assert any("windfall" in m for m in seen)


def test_dated_declines_are_saturation_guarded_too():
    rows = []
    for i in range(60):
        day = pd.Timestamp("2025-08-01")
        for k in range(12):
            rows.append([f"A{i}", day, 1, 1000.0 if k < 6 else 1.0])
            day += pd.DateOffset(months=1)
    raw = pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])
    seen = []
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(raw), seen.append)
    assert "dep_declines_dated_n" not in out
    assert any("decline" in m for m in seen)


def test_file_facts_reconcile():
    """A1: what the loader says about the file must agree with the frame."""
    raw = _deposits(n=60)
    out = compute(build_subsets(_odd(60), {}, ANCHOR), _config(raw),
                  lambda m: None)
    assert out["dep_file_rows"] == len(raw)
    assert out["dep_file_accounts"] == raw["acct"].nunique()
    assert out["dep_first_date"] == str(raw["date"].min().date())
    assert out["dep_last_date"] == str(raw["date"].max().date())


def test_a_condition_true_of_nearly_everyone_is_refused_not_counted():
    """Saturation is a failed join or a defaulted predicate, not a finding."""
    seen = []
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(_deposits()),
                  seen.append)
    assert "dep_recurring_n" not in out, "a 100% signal was reported as a finding"
    assert any(str(SATURATION_PCT) in m for m in seen)


def test_section_never_leaves_a_dataframe_in_the_metrics():
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(_deposits()),
                  lambda m: None)
    json.dumps(out, default=str)


def test_every_table_declares_its_columns():
    """An undeclared table is silently skipped by tables.write()."""
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(_deposits()),
                  lambda m: None)
    for key, value in out.items():
        if key.endswith("_columns") or not isinstance(value, list) or not value:
            continue
        if all(isinstance(r, (list, tuple)) for r in value):
            assert f"{key}_columns" in out, f"{key} declares no columns"


def test_section_is_registered_in_the_orchestrator():
    # RPE: the cut runs its ODD sections from ti/odd_sections.py, not v5's metrics.SECTIONS
    from ti.odd_sections import PARITY

    assert "deposit_behaviour" in PARITY


# ---- the slides -----------------------------------------------------------

class _StubCharts:
    """Every charts.py function, recording its name and drawing nothing."""

    def __getattr__(self, name):
        def fn(*a, **k):
            return None
        fn.__name__ = name
        return fn


def _harness():
    """Stub the helpers build.py hands a renderer, like the attrition slide
    tests do -- the contract, without pptx or matplotlib."""
    seen = {"slide": [], "table": [], "rail": [], "chart": [], "picture": [],
            "chart_args": []}

    def _slide(pair, fallback):
        seen["slide"].append((pair, fallback))
        return ("SL", 2.0)

    def _chart(name, fn, *a, **k):
        seen["chart"].append((name, fn.__name__))
        seen["chart_args"].append((name, a, k))
        # The stub records the call; the REAL form's signature judges it.
        # build.py calls fn(*a, target, **kw), and the first matplotlib
        # render found a renderer whose arguments no form accepted -- the
        # stub had swallowed them for a month. Bind, so the TypeError
        # surfaces here rather than on a client's deck.
        import inspect

        from ti.deck import charts as real
        inspect.signature(getattr(real, fn.__name__)).bind(
            *a, pathlib.Path(f"{name}.png"), **k)
        # build.py's chart() returns the png path; a renderer guards on it,
        # so the stub has to hand back something truthy or the picture step
        # is never reached and the test measures the stub, not the renderer.
        return pathlib.Path(f"{name}.png")

    return seen, {"slide": _slide,
                  "table": lambda *a, **k: seen["table"].append(a[1]),
                  "rail": lambda *a, **k: seen["rail"].append(a[1]),
                  "chart": _chart,
                  "picture": lambda *a, **k: seen["picture"].append((a, k)),
                  "charts": _StubCharts(),
                  "MARGIN_L": 1.18}


def _slide_metrics(**over):
    t = {"dep_match_pct": 75.5, "dep_scored_n": 814, "dep_n": 910,
         "dep_matched_n": 814,
         "dep_book_monthly": [["2026-06", 127912, 698884380],
                              ["2026-07", 129306, 766286298]],
         "dep_cadence_mix": [["weekly", 31, 3.8], ["irregular", 121, 14.9]],
         "dep_recurring_pct": 48.6, "dep_median_amount": 840,
         "dep_stopped_n": 43, "dep_stopped_pct": 5.3,
         "dep_stopped_by_month": [["2026-06", 12]],
         "dep_quiet_bands": [["within 30 days", 700, 86.0],
                             ["over 180 days", 114, 14.0]],
         "dep_onset_median_days": 41,
         "dep_distribution": [[1, 81, 100, 900], [2, 81, 900, 1800]],
         "dep_concentration": [["top 10%", 81, 4_701_175, 43.0]],
         "dep_annual_inflow_median": 9800, "dep_annual_inflow_p90": 41000,
         "dep_largest_deposit_median": 1200,
         "dep_falling_and_slowing_n": 366, "dep_falling_only_n": 900,
         "dep_slowing_only_n": 1200,
         "dep_falling_and_slowing_dollars": 1_500_895,
         "dep_volatility_bands": [["steady (< 0.20)", 400, 49.1],
                                  ["uneven (0.50 - 1.00)", 414, 50.9]],
         "dep_volatility_median": 0.31, "dep_pay_cut_n": 88,
         "dep_refund_n": 2_100, "dep_refund_pct": 25.8,
         "dep_refund_median": 2_400, "dep_refund_dollars": 5_040_000,
         "dep_payday_weekday": [["Thu", 300, 36.9], ["Fri", 514, 63.1]],
         "dep_od_by_rhythm": [["paid on a rhythm", 400, 90, 22.5, 300],
                              ["not on a rhythm", 414, 160, 38.6, 700]],
         "dep_od_accounts_n": 250, "dep_buffer_median_days": 18,
         "dep_primacy_n": 512, "dep_primacy_pct": 56.3,
         "dep_primacy_dollars": 41_000_000, "dep_primacy_floor": 12_000,
         "dep_recurring_n": 535,
         "dep_vs_card_spend": [["deposit inflow, year", 8_160_000_000],
                               ["card spend, year", 1_360_967_139]],
         "dep_competitor_reach": 41}
    t.update(over)
    return t


def _renderers():
    from ti.deck import deposit_slides as D

    return (D.deposit_overview, D.recurring_credits, D.credits_stopped,
            D.deposit_milestones, D.deposit_spread, D.falling_and_slowing,
            D.income_shape, D.tax_refunds, D.overdraft_and_income,
            D.deposit_primacy, D.inflow_against_outflow)


def test_all_three_slides_render_on_a_sound_join():
    seen, h = _harness()
    assert all(fn(h, _slide_metrics()) is None for fn in _renderers())
    assert [s[1] for s in seen["slide"]] == [
        "What deposits look like", "Who is paid here",
        "Who stopped being paid here", "When money last arrived",
        "Where the deposits sit", "Balance falling and inflow slowing",
        "What kind of income", "Tax refunds",
        "Who overdrafts, by how they are paid", "Who banks here first",
        "What arrives against what leaves"]


def test_slide_titles_are_registered_in_the_deck_main_path():
    """A slide built but not listed is auto-demoted to the appendix."""
    # RPE: the cut's deposits chapter lists its slides (ti/chapters/deposits.py), not v5's MAIN_PATH
    from ti.chapters.deposits import TITLES
    MAIN_PATH = set(TITLES.values())

    for title in ("What deposits look like", "Who is paid here",
                  "Who stopped being paid here", "When money last arrived",
                  "Where the deposits sit",
                  "Balance falling and inflow slowing",
                  "What kind of income", "Tax refunds",
                  "Who overdrafts, by how they are paid",
                  "Who banks here first",
                  "What arrives against what leaves"):
        assert title in MAIN_PATH, f"{title} missing from MAIN_PATH"


def test_a_weak_join_refuses_every_deposit_slide():
    """A deposit slide drawn on a broken join looks exactly like a finding."""
    seen, h = _harness()
    reasons = [fn(h, _slide_metrics(dep_match_pct=12.0)) for fn in _renderers()]
    assert all(reasons), "a slide rendered on a 12% join"
    assert all("12.0%" in r for r in reasons)
    assert not seen["slide"]


def test_no_deposits_file_refuses_every_deposit_slide():
    seen, h = _harness()
    assert all(fn(h, {}) for fn in _renderers())
    assert not seen["slide"]


def test_a_cohort_under_the_floor_refuses_every_deposit_slide():
    seen, h = _harness()
    assert all(fn(h, _slide_metrics(dep_scored_n=11)) for fn in _renderers())


def test_a_missing_key_refuses_only_the_slide_that_needs_it():
    seen, h = _harness()
    t = _slide_metrics()
    del t["dep_cadence_mix"]
    out = [fn(h, t) for fn in _renderers()]
    assert out[1] and "dep_cadence_mix" in out[1]
    assert out[0] is None and out[2] is None


def test_integrity_numbers_stay_off_the_slides():
    """extract_check's precedent: the deck carries findings, not plumbing."""
    seen, h = _harness()
    for fn in _renderers():
        fn(h, _slide_metrics())
    printed = str(seen["table"]) + str(seen["rail"]) + str(seen["slide"])
    for banned in ("in_file_not_odd", "in_file_not_base", "orphan"):
        assert banned not in printed


def test_each_slide_uses_a_DIFFERENT_chart_form():
    """Three slides in a row must not be three of the same chart.

    charts.py carries roughly forty forms. The first cut of these renderers
    drew a table and a rail on all three, which is one layout wearing three
    headlines.
    """
    seen, h = _harness()
    for fn in _renderers():
        fn(h, _slide_metrics())
    forms = [name for _, name in seen["chart"]]
    assert len(forms) == 11, f"expected a chart per slide, got {forms}"
    assert len(set(forms)) == 11, f"repeated chart form: {forms}"


def test_slides_draw_charts_rather_than_tables_of_digits():
    seen, h = _harness()
    for fn in _renderers():
        fn(h, _slide_metrics())
    assert not seen["table"], "a deposit slide fell back to a table"
    assert len(seen["picture"]) == 11


def test_every_picture_stops_before_the_rail():
    """Every deposit slide carries a rail. _picture centres across the whole
    content field unless told `rail=True`, and the first real render put
    four charts underneath the callouts."""
    seen, h = _harness()
    for fn in _renderers():
        fn(h, _slide_metrics())
    assert len(seen["picture"]) == 11
    for call in seen["picture"]:
        assert call[1].get("rail") is True, f"picture placed without rail: {call}"


def test_every_metric_is_read_before_the_slide_is_created():
    """The register assigns a renderer's reads to the slide registered
    NEXT once h["slide"]() has run. Rail values read after it were landing
    on the following slide's provenance, on all eleven."""
    seen, h = _harness()
    late = []

    class _Recording(dict):
        def get(self, key, default=None):
            if seen["slide"] and key not in ("dep_match_pct", "dep_scored_n"):
                late.append((seen["slide"][-1][1], key))
            return super().get(key, default)

        def __getitem__(self, key):
            self.get(key)
            return super().__getitem__(key)

    for fn in _renderers():
        seen["slide"].clear()
        fn(h, _Recording(_slide_metrics()))
    assert not late, f"read after the slide was created: {late}"


def test_no_chart_is_handed_an_all_zero_series():
    """grouped_bars wanted a second series and got [0, 0, 0] to satisfy the
    signature: three grey zero-height bars labelled 0 on the client's deck."""
    seen, h = _harness()
    for fn in _renderers():
        fn(h, _slide_metrics())
    for name, args, kwargs in seen["chart_args"]:
        for arg in args:
            if isinstance(arg, (list, tuple)) and arg and all(
                    isinstance(v, (int, float)) and v == 0 for v in arg):
                raise AssertionError(f"{name} was handed an all-zero series")


def test_month_axes_name_the_year():
    """'08' under a line is a month of some year. Twelve of them across a
    year boundary read 08 .. 12, 01 .. 07 with nothing saying the year
    turned."""
    seen, h = _harness()
    for fn in _renderers():
        fn(h, _slide_metrics())
    axes = {name: args[0] for name, args, _ in seen["chart_args"]
            if name in ("dep_inflow", "dep_stopped")}
    assert set(axes) == {"dep_inflow", "dep_stopped"}
    for name, rows in axes.items():
        for row in rows:
            assert re.fullmatch(r"[A-Z][a-z]{2} \d{2}", str(row[0])), \
                f"{name} label {row[0]!r} does not name month and year"


def test_no_rail_value_is_a_placeholder():
    seen, h = _harness()
    for fn in _renderers():
        fn(h, _slide_metrics())
    for items in seen["rail"]:
        for label, value, _note in items:
            assert "see table" not in str(value).lower(), (label, value)


def test_onset_is_measured_only_for_accounts_opened_inside_the_file_window():
    """An account opened in 2019 whose first credit in a 2025 file is in
    August did not take 2,400 days to start depositing -- its first deposit
    HERE is not its first deposit. The fixture's 3,768-day median onset was
    exactly that."""
    odd = _odd(4)
    odd["Date Opened"] = ["2019-01-15", "2019-01-15",
                          "2025-09-01", "2025-10-01"]
    raw = _deposits(4, every=14, start="2025-08-01")
    raw = raw[~((raw["acct"] == "A2") & (raw["date"] < "2025-09-10"))]
    raw = raw[~((raw["acct"] == "A3") & (raw["date"] < "2025-10-31"))]
    out = compute(build_subsets(odd, {}, ANCHOR), _config(raw), lambda m: None)
    assert out["dep_onset_measured_n"] == 2
    assert out["dep_onset_median_days"] < 60


def test_the_typical_longest_gap_is_a_number():
    """The milestone slide's rail printed 'see table' where the typical gap
    should be. The chapter has every account's longest gap; it never
    reduced them to one figure."""
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(_deposits()),
                  lambda m: None)
    assert out["dep_gap_median_days"] == 14


def test_section_m_reads_the_odd_s_monthly_item_columns():
    """The ODD carries monthly NSF/OD items as `{Mon}{YY} MTD` -- that is
    what profile.py and odd_transform read, and what REFERENCE.md documents.
    Section M looked for a suffix called `Items`, which no ODD has, so the
    ILS argument would never have run on a real book."""
    odd = _odd()
    for m in ("Feb", "Mar", "Apr", "May", "Jun", "Jul"):
        odd[f"{m}26 MTD"] = [1 if i % 4 == 0 else 0 for i in range(len(odd))]
    out = compute(build_subsets(odd, {}, ANCHOR), _config(_deposits()),
                  lambda m: None)
    assert out["dep_od_accounts_n"] == 15
    assert out["dep_od_by_rhythm"]


def test_the_match_floor_is_written_once():
    """QC section 2: MIN_MATCH_PCT was named once and written three times --
    the slide gate, the report's READ THIS FIRST line and the transaction
    join warning, the last two as a bare 50. Move the named one and the
    slides refuse while the report still prints: two answers about the same
    join."""
    from ti.core.deposits import MIN_MATCH_PCT

    from ti.deck import deposit_slides

    assert MIN_MATCH_PCT == deposit_slides.MIN_MATCH_PCT
    # RPE: the ported copies under build/ars_pipeline/ti/ (v5's text report is not ported)
    root = pathlib.Path(__file__).resolve().parents[1] / "build" / "ars_pipeline" / "ti"
    for rel in ("deck/deposit_slides.py",
                "transaction_intelligence/portfolio.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert "MIN_MATCH_PCT" in src, f"{rel} does not read the named floor"
        assert not re.search(r"[<>]=?\s*50\b", src), f"{rel} still writes 50"


def test_the_combination_blocks_fit_their_tiles():
    """category_blocks tiles its supporting blocks at a quarter of the
    figure. 'Balance falling only · 312' ran off its tile and across the
    next one on the second render."""
    seen, h = _harness()
    from ti.deck import deposit_slides as D

    D.falling_and_slowing(h, _slide_metrics())
    blocks = next(a[0] for name, a, _ in seen["chart_args"] if name == "dep_both")
    for name, value, sub, _trend in blocks[1:]:
        assert len(f"{name} · {value}") <= 20, (name, value)
        assert len(sub) <= 26, sub


def test_the_overdraft_chart_draws_the_rate_per_group():
    """The question is 'do irregular earners overdraft MORE', a rate per
    group. The first render handed health_bars the overdrafting COUNTS, and
    the chart printed each group's share of all overdrafters -- 58.6% over
    the rhythmic bar when 100% of both groups had overdrafted."""
    seen, h = _harness()
    from ti.deck import deposit_slides as D

    D.overdraft_and_income(h, _slide_metrics())
    name, form = seen["chart"][-1]
    rows = seen["chart_args"][-1][1][0]
    assert name == "dep_od_rhythm"
    assert form == "rate_bars"
    assert [r[3] for r in rows] == [22.5, 38.6]
    assert [r[1] for r in rows] == [400, 414]
    # rate_bars paints its red on the LOWEST rate, built for take rates.
    # Here the higher rate is the bad one, so the form must not choose.
    assert seen["chart_args"][-1][2].get("mark_weakest") is False


def test_a_duplicated_account_id_does_not_take_the_chapter_down():
    """RALLY's ODD carries one account id on two rows. The extract check
    already counts it; section C's join then raised 'cannot reindex on an
    axis with duplicate labels' and every deposit slide read 'no deposits
    file'. One bad row must cost one row, not the chapter."""
    odd = _odd()
    odd = pd.concat([odd, odd.iloc[[3]]], ignore_index=True)
    seen = []
    out = compute(build_subsets(odd, {}, ANCHOR), _config(_deposits()), seen.append)
    assert out["dep_match_pct"] == 100.0
    assert out["dep_quiet_bands"]
    assert out["dep_n"] == 60
    assert any("duplicate" in m for m in seen)


# ---- the five that fired on most of RALLY's book (2026-09-10, #179) --------

def _payroll_and_noise(acct="P", pay=800.0, extra=()):
    """One account: a fortnightly payroll, 26 small transfers, and whatever
    `extra` adds as (date, amount). The whole-account median sits far below
    the pay, which is what made refunds and windfalls fire on most of RALLY."""
    start = pd.Timestamp("2025-08-01")
    rows = []
    for k in range(26):
        rows.append([acct, start + pd.to_timedelta(14 * k, "D"), 1, pay])
    # More transfers than pay, on no rhythm -- gaps of 3 to 25 days in no
    # order -- so the whole-account median is $20, as on RALLY.
    day = 0
    for k in range(30):
        day += 3 + (k * 7 + k * k) % 23
        rows.append([acct, start + pd.to_timedelta(day % 360, "D"), 1, 20.0])
    for day, amount in extra:
        rows.append([acct, pd.Timestamp(day), 1, float(amount)])
    return pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])


def test_a_windfall_is_judged_against_the_dominant_stream():
    """RALLY: 57% of accounts had a 5x 'windfall' because the whole-account
    median is a $20 transfer. Against the $800 payroll, $2,500 is a good
    month and $5,000 is an event."""
    raw = _payroll_and_noise(extra=[("2025-11-03", 2500), ("2026-05-04", 5000)])
    out = B.windfalls(raw, reference=S.dominant_stream(raw)
                      .set_index("acct")["stream_median"]).set_index("acct")
    assert out.loc["P", "n_windfalls"] == 1
    assert out.loc["P", "windfall_dollars"] == 5000


def test_a_refund_is_judged_against_the_dominant_stream():
    """RALLY: 63% of matched accounts 'got a tax refund' -- any March credit
    over twice a $20 median. Twice the payroll is the bar."""
    raw = _payroll_and_noise(extra=[("2026-03-10", 1200)])
    assert pd.isna(S.income_shape(raw).set_index("acct").loc["P", "refund_amount"])
    raw = _payroll_and_noise(extra=[("2026-03-10", 2000)])
    assert S.income_shape(raw).set_index("acct").loc["P", "refund_amount"] == 2000


def test_a_recurring_stream_has_a_rhythm_not_just_a_size():
    """RALLY: 41.5% of accounts showed 4+ 'recurring streams'. n_streams
    counted amount bins with four members; six $300 credits on random days
    are not a stream."""
    raw = _payroll_and_noise(extra=[("2025-09-02", 300), ("2025-10-19", 300),
                                    ("2025-12-07", 300), ("2026-01-28", 300),
                                    ("2026-04-11", 300), ("2026-06-30", 300)])
    assert S.dominant_stream(raw).set_index("acct").loc["P", "n_streams"] == 1


def test_an_employer_cohort_needs_four_credits_from_each_member():
    """RALLY: 1,544 cohorts covering 99% of matched accounts. The four-credit
    floor was written `stream_n >= 4 & notna()`, which binds as
    `stream_n >= (4 & notna)` and floors at one."""
    raw = _deposits(60)                                   # same $1,000, same days
    thin = _deposits(5, months=1)                         # two credits each
    thin["acct"] = "T" + thin["acct"]
    odd = _odd(60)
    odd = pd.concat([odd, pd.DataFrame({
        "Acct Number": [f"TA{i}" for i in range(5)], "Debit?": ["Yes"] * 5,
        "Date Opened": ["2019-01-15"] * 5, "Curr Bal": [500.0] * 5,
        "Avg Bal": [500.0] * 5,
        **{f"{m}26 Spend": [100.0] * 5
           for m in ("Feb", "Mar", "Apr", "May", "Jun", "Jul")}})],
        ignore_index=True)
    out = compute(build_subsets(odd, {}, ANCHOR),
                  _config(pd.concat([raw, thin], ignore_index=True)), lambda m: None)
    assert out["dep_employer_covered_n"] == 60


def test_overdrafts_by_rhythm_keep_no_deposit_accounts_apart():
    """RALLY: 'not on a rhythm' overdrafted LESS than payroll accounts, which
    inverted the hypothesis -- because the row held the 44,801 accounts with
    no deposits at all. Three rows, and the rates on the accounts the file
    actually describes."""
    odd = _odd(60)
    for m in ("Feb", "Mar", "Apr", "May", "Jun", "Jul"):
        odd[f"{m}26 MTD"] = [1 if i % 4 == 0 else 0 for i in range(60)]
    raw = _deposits(45)                                   # A45..A59 never deposit
    # A30..A44 deposit on no rhythm: their dates are scattered
    jitter = raw["acct"].isin([f"A{i}" for i in range(30, 45)])
    raw.loc[jitter, "date"] = raw.loc[jitter, "date"] + pd.to_timedelta(
        (raw.index[jitter] * 7) % 11, unit="D")
    out = compute(build_subsets(odd, {}, ANCHOR), _config(raw), lambda m: None)
    rows = {r[0]: r for r in out["dep_od_by_rhythm"]}
    assert set(rows) == {"no deposits", "not on a rhythm", "paid on a rhythm"}
    assert rows["no deposits"][1] == 15
    assert rows["paid on a rhythm"][1] + rows["not on a rhythm"][1] == 45


def test_coverage_table_declares_its_columns():
    """A2/A3 have to survive the run, not vanish with the terminal."""
    out = compute(build_subsets(_odd(), {}, ANCHOR), _config(_deposits()),
                  lambda m: None)
    assert len(out["dep_coverage"]) == 1, "one row per run, so months stack"
    assert len(out["dep_coverage"][0]) == len(out["dep_coverage_columns"])


# ---- B5: stream separation, and the B3 fix that depends on it -------------

def _mixed_book(n=120, pay=800.0, paid_every=4):
    """An account shaped like RALLY's: a steady payroll buried under the other
    credits a real account carries. ~51 per account per year, as measured.

    Not every account gets a payroll -- one in `paid_every` receives only the
    mixed credits. A fixture where everyone passes trips the saturation guard,
    which is the guard working, and would leave this test measuring nothing.
    """
    rows = []
    for i in range(n):
        start = pd.Timestamp("2025-08-01")
        if i % paid_every:
            for k in range(26):                   # fortnightly payroll
                rows.append([f"A{i}", start + pd.to_timedelta(14 * k, "D"), 1,
                             round(pay * (1 + 0.03 * ((i + k) % 5 - 2) / 2), 2)])
        # Everything else, and it has to be genuinely irregular. A first
        # draft used four repeating amounts on a 29-day step, which is a
        # second REGULAR stream -- the separator found it, correctly, and the
        # test measured the fixture rather than the code.
        day = 0
        for k in range(25):
            day += 5 + (i * 7 + k * 11) % 31
            rows.append([f"A{i}", start + pd.to_timedelta(day % 360, "D"), 1,
                         float(12 + (i * 37 + k * 61) % 900)])
    return pd.DataFrame(rows, columns=["acct", "date", "dep_count",
                                       "dep_amount"])


def test_a_payroll_is_invisible_to_a_whole_account_cv():
    """The defect, pinned. RALLY: 48.9% rhythmic, 4.6% amount-consistent."""
    from ti.core.deposits import streams as S

    book = _mixed_book()
    whole = B.cadence(book)
    # The point is that the mixture pushes the CV past the threshold, not how
    # far past. On RALLY 81.8% of accounts landed above 0.50; here the median
    # is ~0.41 against a 0.25 threshold, and that is enough to hide the payroll.
    assert whole["amount_cv"].median() > B.RECURRING_CV
    assert whole["probable_direct_deposit"].mean() < 0.05, (
        "the whole-account CV found a payroll it should not be able to see")


def test_the_dominant_stream_recovers_the_payroll():
    from ti.core.deposits import streams as S

    book = _mixed_book(pay=800.0)
    found = S.recurring(book)
    # the 3-in-4 that have a payroll, and only those
    assert 0.6 < found["probable_direct_deposit"].mean() < 0.95
    assert abs(found["stream_median"].median() - 800.0) < 40
    assert found["stream_cv"].median() < B.RECURRING_CV


def test_stream_share_says_how_much_of_the_account_it_speaks_for():
    """A dominant stream covering little of an account is a weak claim, and
    the caller has to be able to see that rather than infer it."""
    from ti.core.deposits import streams as S

    found = S.recurring(_mixed_book())
    assert 0.3 < found["stream_share"].median() < 0.8
    assert (found["n_streams"] >= 2).any()


def test_stream_functions_survive_an_empty_frame():
    from ti.core.deposits import streams as S

    empty = _deposits(n=0)
    assert not len(S.dominant_stream(empty))
    assert not len(S.recurring(empty))


def test_the_chapter_reports_both_bases_so_the_change_is_provable():
    """Changing a published number has to be provable, not asserted."""
    out = compute(build_subsets(_odd(60), {}, ANCHOR),
                  _config(_mixed_book(60)), lambda m: None)
    assert out["dep_recurring_basis"] == "dominant stream"
    assert out["dep_recurring_whole_account_pct"] is not None
    assert out["dep_recurring_pct"] > out["dep_recurring_whole_account_pct"]


def test_thresholds_come_from_config_and_the_run_says_so():
    """A floor of 30 is right for a book doing 300 a month and wrong for one
    doing six."""
    seen = []
    cfg = dict(_config(_deposits()), DepositMinCohort=5,
               DepositIdleBalance=1000)
    out = compute(build_subsets(_odd(60), {}, ANCHOR), cfg, seen.append)
    assert out["dep_idle_balance_floor"] == 1000
    assert any("thresholds in use" in m for m in seen)


def test_a_junk_threshold_falls_back_and_warns():
    seen = []
    cfg = dict(_config(_deposits()), DepositIdleBalance="lots")
    out = compute(build_subsets(_odd(60), {}, ANCHOR), cfg, seen.append)
    assert out["dep_idle_balance_floor"] == 25_000
    assert any("not a number" in m for m in seen)


def test_a_short_transaction_load_refuses_the_competition_slide():
    """RALLY ran nine of twelve months at a third of the file, and the three
    healthy months made the shortfall look seasonal. A deposit-against-
    competitor figure on that is wrong, not merely small."""
    from ti.deck import deposit_slides as D

    seen, h = _harness()
    t = _slide_metrics(dep_competition_skipped="load incomplete",
                       dep_txn_short_months=9)
    reason = D.inflow_against_outflow(h, t)
    assert reason and "9 month" in reason
    assert not seen["slide"]


def test_the_chapter_never_reads_the_wall_clock():
    """Age and tenure came off `Timestamp.now()` until the date rolled over
    to 2026-09-09 and moved one synthetic member from 'under 25' to '25 - 34',
    breaking the golden. A band read from the clock means the same month
    re-run in December answers differently. Everything dates from the run's
    anchor.
    """
    import pathlib

    from ti.monthly_analysis import deposit_behaviour as D

    src = pathlib.Path(D.__file__).read_text(encoding="utf-8")
    for clock in ("Timestamp.now", "datetime.now", "date.today"):
        assert clock not in src, f"{clock} in deposit_behaviour: dates from the clock"
