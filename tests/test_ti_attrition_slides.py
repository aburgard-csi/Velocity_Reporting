# Ported from ARS v5 02-Scripts/tests/test_attrition_slides.py at a491b5c (James Gilmore); logic unchanged; the geometry checks use the RPE grid
# (ti/deck/helpers.py: content from 0.6in, no navy spine) instead of v5's.
"""The attrition slides: months of warning, and concurrent stressors.

Exercised against a stub harness rather than a full deck build: the synthetic
fixture trips few conditions, so a real build cannot distinguish "correctly
skipped" from "silently broken". Same reasoning as test_hotspot_slides.py.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import attrition_slides as P  # noqa: E402


class _Harness(dict):
    """Records every slide, table and rail the builder asks for."""

    def __init__(self):
        super().__init__()
        self.slides, self.tables, self.rails = [], [], []
        self.geometry = []
        self.charts = []
        self["slide"] = self._slide
        self["table"] = self._table
        self["rail"] = self._rail
        self["chart"] = self._chart
        self["charts"] = __import__("ti.deck.charts", fromlist=["charts"])
        self["MARGIN_L"] = __import__("ti.deck.helpers", fromlist=["x"]).MARGIN_L  # RPE grid

    def _chart(self, name, fn, *args, **kwargs):
        self.charts.append((name, fn.__name__, args))
        return None

    def _slide(self, pair, fallback):
        self.slides.append((pair, fallback))
        return object(), 1.75

    def _table(self, slide, rows, left=None, top=None, width=None, *a, **k):
        self.tables.append(rows)
        self.geometry.append((left, width))

    def _rail(self, slide, items, **k):
        self.rails.append(items)

    def text(self):
        parts = []
        for pair, fallback in self.slides:
            parts.append(str(fallback))
            parts.extend(str(x) for x in pair if x)
        for items in self.rails:
            parts.extend(str(x) for item in items for x in item if x)
        for rows in self.tables:
            parts.extend(str(c) for row in rows for c in row)
        return "\n".join(parts)


def _metrics():
    return {
        "stress_base": "Open at anchor",
        "stress_n": 910,
        "stress_available": ["Spend health declining", "Deposits leaving",
                             "Gone quiet"],
        "stress_skipped": ["Banking elsewhere"],
        "stress_by_count": [[0, 464, 51.0, 4_323_622], [1, 375, 41.2, 6_854_548],
                            [2, 70, 7.7, 2_720_095], [3, 1, 0.1, 42_000]],
        "stress_by_count_columns": ["stressors", "accounts", "pct_of_base",
                                    "deposits"],
        "stress_2plus_n": 71,
        "stress_2plus_pct": 7.8,
        "stress_2plus_deposits": 2_762_095,
    }


def test_slide_is_skipped_when_the_section_did_not_run():
    """A client whose files built no condition gets no slide, not an empty one."""
    h = _Harness()
    reason = P.concurrent_stressors(h, {})
    assert not h.slides
    assert reason and "stress_by_count" in reason


def test_headline_leads_with_the_two_plus_cut():
    h = _Harness()
    assert P.concurrent_stressors(h, _metrics()) is None
    assert h.slides, "slide was not rendered"
    assert "71" in h.text()


def test_slide_names_its_base():
    """The three-bases problem is a labelling failure. Fix it on the slide."""
    h = _Harness()
    P.concurrent_stressors(h, _metrics())
    assert "Open at anchor" in h.text()


def test_skipped_conditions_are_disclosed_on_the_slide():
    """A count of 'n of 3' is not comparable to a client scored on 6. Say so
    where the reader is, not only in the JSON."""
    h = _Harness()
    P.concurrent_stressors(h, _metrics())
    assert "Banking elsewhere" in h.text()


def test_table_uses_the_declared_column_order():
    h = _Harness()
    P.concurrent_stressors(h, _metrics())
    assert h.tables, "no table was drawn"
    assert [str(c).lower() for c in h.tables[0][0]][:2] == ["stressors", "accounts"]


def test_table_headers_are_readable_not_metric_keys():
    """A CSM reads this slide. "pct_of_base" is a key, not a column heading."""
    h = _Harness()
    P.concurrent_stressors(h, _metrics())
    header = h.tables[0][0]
    assert "pct_of_base" not in header
    assert "% of base" in header


def test_a_book_with_no_multi_stressor_account_says_so_plainly():
    """Zero is a finding, not a blank slide."""
    m = dict(_metrics(), stress_2plus_n=0, stress_2plus_pct=0.0,
             stress_2plus_deposits=0)
    h = _Harness()
    P.concurrent_stressors(h, m)
    assert h.slides
    assert "No account" in h.text()


def test_table_clears_the_navy_spine():
    """SPINE_W is 0.85 and body content starts at MARGIN_L. A table at 0.6
    renders underneath the spine -- test_txn_deck_geometry catches it on the
    built deck, but only after a full build; catch it here instead."""
    from ti.deck.helpers import MARGIN_L  # RPE grid: no navy spine
    SPINE_W = 0.0

    h = _Harness()
    P.concurrent_stressors(h, _metrics())
    left, width = h.geometry[0]
    assert left >= SPINE_W, f"table starts at {left}, under the spine"
    assert left == MARGIN_L
    assert width > 0


# ---- months_of_warning ----------------------------------------------------

def _life_metrics(divergence=4):
    return {
        "life_window": 12,
        "life_depth_months": 35,
        "life_divergence_month": divergence,
        "life_divergence_ratio": 0.8,
        "life_decline": [[0, 210, 40.0, 8400, 55.0], [1, 208, 62.0, 12896, 71.0],
                         [2, 205, 78.0, 15990, 80.0], [3, 200, 96.0, 19200, 88.0],
                         [4, 198, 110.0, 21780, 91.0], [5, 195, 148.0, 28860, 94.0]],
        "life_control": [[0, 1280, 150.0, 192000, 95.0], [1, 1280, 151.0, 193280, 95.0],
                         [2, 1280, 149.0, 190720, 95.0], [3, 1280, 152.0, 194560, 95.0],
                         [4, 1280, 150.0, 192000, 95.0], [5, 1280, 150.0, 192000, 95.0]],
        "life_divergence_by_tenure": [["0-12 mo", 40, None], ["1-3 yr", 90, 2],
                                      ["3-5 yr", 60, 5], ["5-10 yr", 120, 4],
                                      ["10+ yr", 200, 6]],
        "life_divergence_by_tenure_columns": ["tenure", "closed_n",
                                              "months_of_warning"],
    }


def test_warning_slide_is_skipped_when_the_section_did_not_run():
    h = _Harness()
    reason = P.months_of_warning(h, {})
    assert not h.slides and reason


def test_headline_states_the_months_of_warning():
    h = _Harness()
    assert P.months_of_warning(h, _life_metrics()) is None
    assert "4" in h.text()


def test_a_book_with_no_divergence_says_so_rather_than_implying_zero():
    """No detectable warning is a finding. It must not read as 'zero months',
    which a reader would take as 'they leave without warning'."""
    h = _Harness()
    P.months_of_warning(h, _life_metrics(divergence=None))
    assert h.slides
    text = h.text().lower()
    assert "no " in text or "not" in text


def test_the_table_shows_the_base_at_every_offset():
    """A curve whose cohort thins must show it, or offset 12 reads as solid
    as offset 1."""
    h = _Harness()
    P.months_of_warning(h, _life_metrics())
    header = [str(c).lower() for c in h.tables[0][0]]
    assert any("account" in c for c in header)


def test_warning_table_clears_the_navy_spine():
    from ti.deck.helpers import MARGIN_L  # RPE grid: no navy spine
    SPINE_W = 0.0

    h = _Harness()
    P.months_of_warning(h, _life_metrics())
    left, width = h.geometry[0]
    assert left >= SPINE_W and left == MARGIN_L and width > 0


def test_the_slide_shows_deposit_warning_beside_spend_warning():
    """The gap between the two is the finding, so both appear or neither."""
    h = _Harness()
    m = dict(_life_metrics(), life_deposit_divergence_month=7,
             life_deposit_lead_months=3)
    P.months_of_warning(h, m)
    text = h.text()
    assert "Card spend" in text and "Deposits" in text
    assert "earlier" in text, "the lead over card spend must be stated"


def test_no_deposits_file_leaves_the_slide_reading_correctly():
    h = _Harness()
    P.months_of_warning(h, _life_metrics())
    assert "Deposits" not in h.text()


# ---- cohort_survival ------------------------------------------------------

def _cohort_metrics():
    return {"attrition_cohort_survival": [["Sep25", 420, 380, 40, 90.5],
                                          ["Oct25", 388, 360, 28, 92.8],
                                          ["Aug26", 512, 510, 2, 99.6]],
            "attrition_cohort_survival_columns": ["open_month", "opened", "still_open",
                                                  "closed", "survival_pct"],
            "attrition_cohort_first_year_rate": 12.5,
            "attrition_cohort_first_year_base": 4800,
            "attrition_closures_seasoned_pct": 61.0}


def test_cohort_slide_is_skipped_without_the_table():
    h = _Harness()
    reason = P.cohort_survival(h, {})
    assert not h.slides and "attrition_cohort_survival" in reason


def test_cohort_slide_headline_carries_the_first_year_rate_and_its_base():
    h = _Harness()
    assert P.cohort_survival(h, _cohort_metrics()) is None
    text = h.text()
    assert "12.5" in text and "4,800" in text


def test_cohort_chart_rows_carry_the_base_under_the_rate():
    """line_with_base wants [label, base_n, pct]: the cohort thins in the
    latest months and the chart must show it."""
    h = _Harness()
    P.cohort_survival(h, _cohort_metrics())
    name, fn, args = h.charts[-1]
    assert name == "attrition_cohort" and fn == "line_with_base"
    # the month goes through periods.axis_months: RPE's month-axis guard refused v5's "Sep25" and
    # the chart went missing on 1798 (Sheila's 1798 review, 2026-10-30)
    assert args[0][0] == ["Sep'25", 420, 90.5]


def test_cohort_slide_names_the_seasoned_share():
    h = _Harness()
    P.cohort_survival(h, _cohort_metrics())
    assert "61" in h.text()


# ---- product_and_hazard ---------------------------------------------------

def _cluster_metrics():
    return {"attrition_rate": 6.6,
            "attrition_by_product": [["Freedom Plus Checking", 25000, 1800, 7.2],
                                     ["Super Checking", 12000, 600, 5.0]],
            "attrition_hazard": [["< 1 yr", 5000, 400, 8.0], ["1-2 yr", 4800, 520, 10.8],
                                 ["2-3 yr", 4400, 460, 10.5], ["3-5 yr", 8000, 640, 8.0]],
            "attrition_hazard_columns": ["tenure", "reached_and_resolved",
                                         "closed_in_bucket", "hazard_pct"],
            "attrition_hazard_peak": ["1-2 yr", 10.8]}


def test_cluster_slide_needs_at_least_one_of_the_two_cuts():
    h = _Harness()
    assert P.product_and_hazard(h, {}) and not h.slides


def test_cluster_headline_names_the_worst_product_and_the_peak_tenure():
    h = _Harness()
    assert P.product_and_hazard(h, _cluster_metrics()) is None
    text = h.text()
    assert "Freedom Plus" in text and "1-2 yr" in text


def test_cluster_chart_rows_are_in_branch_bars_shape():
    h = _Harness()
    P.product_and_hazard(h, _cluster_metrics())
    name, fn, args = h.charts[-1]
    assert name == "attrition_product" and fn == "branch_bars"
    assert args[0][0][0] == "Freedom Plus Checking" and args[0][0][3] == 7.2
    assert args[1] == 6.6                       # the portfolio line


def test_risk_slide_leads_with_the_swipe_only_decliners():
    h = _Harness()
    t = {"retention_axes": [["Growing on both", 100, 10.0, 500000],
                            ["Fewer visits, same dollars", 59, 5.9, 300000]],
         "retention_axes_columns": ["quadrant", "accounts", "pct_of_prior_spenders",
                                    "prior_spend_annualized"],
         "retention_swipe_only_decline_n": 59,
         "retention_by_swipe_tier": [["41+ Swipes", 120, 12.0, 90000], ["1-5 Swipes", 40, 30.0, 8000]],
         "attrition_life_dist_months": [["< 1 mo", 4, 10.0], ["1-3 mo", 8, 20.0], ["12+ mo", 28, 70.0]],
         "attrition_mailed_vs_nevermailed_pp": -2.5}
    assert P.where_the_risk_sits(h, t) is None
    text = h.text()
    assert "59" in text and "Fewer visits" in text and "30%" in text and "-2.5" in text
    assert "pct_of_prior_spenders" not in text


def test_risk_slide_skips_without_any_part2_metric():
    h = _Harness()
    assert P.where_the_risk_sits(h, {}) and not h.slides


def test_hazard_table_headers_are_readable():
    h = _Harness()
    P.product_and_hazard(h, _cluster_metrics())
    header = [str(c) for c in h.tables[0][0]]
    assert "reached_and_resolved" not in header and "Tenure" in header
