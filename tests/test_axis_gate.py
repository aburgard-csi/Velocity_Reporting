"""The gate: no chart in any program renders a month outside the vocabulary.

Per the standing rule (CLAUDE.md, Aaron 2026-08-17) — when a defect gets through,
add the check that would have caught it. `validate_deck.py` cannot: a tick label
is pixels inside a PNG, and the validator reads paragraphs. `qa_all.py`'s layout
fingerprints compare geometry, not glyphs. The builder's swap gate fires when a
swap matches NOTHING, and all nine spellings rendered successfully — they were
just spelled differently.

So the check has to run at the producer. Every chart with a month axis is
rendered here from synthetic fixtures, `Figure.savefig` is intercepted, and every
tick that names a month at all must be in the one form. A chart that drops the
year fails on "Jul"; a chart that slices its own label fails on "Jul 26".
"""
import os
import re
import runpy
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import pytest

from conftest import ARS, FIXTURES, ICS, MRPC
from periods import is_axis_label, names_a_month

import ics_charts_gen as ICSCH
import mrpc_charts_gen as MRPCCH
from test_ics_charts import detail, months_in
from test_mrpc_charts import _months_in as mrpc_months_in

CHART_MODULES = [
    os.path.join(ARS, "charts_gen.py"),
    os.path.join(ARS, "chart_lib.py"),
    os.path.join(ARS, "ticket_chart.py"),
    os.path.join(ICS, "ics_charts_gen.py"),
    os.path.join(MRPC, "mrpc_charts_gen.py"),
]


class Recorder:
    """Reads every x axis of every figure the renderers save."""

    def __init__(self):
        self.ticks = []          # (label, chart name)

    def __enter__(self):
        self._real = Figure.savefig
        rec = self

        def savefig(fig, fname, *a, **kw):
            name = os.path.basename(str(fname)) if isinstance(fname, (str, os.PathLike)) else "?"
            for ax in fig.axes:
                for t in ax.get_xticklabels():
                    text = t.get_text()
                    if text:
                        rec.ticks.append((text, name))
            return rec._real(fig, fname, *a, **kw)

        Figure.savefig = savefig
        return self

    def __exit__(self, *exc):
        Figure.savefig = self._real
        plt.close("all")
        return False

    @property
    def month_ticks(self):
        return [(t, n) for t, n in self.ticks if names_a_month(t)]


def assert_one_form(rec, what):
    assert rec.month_ticks, f"{what}: no month ticks were rendered at all"
    bad = sorted({(t, n) for t, n in rec.month_ticks if not is_axis_label(t)})
    assert not bad, (
        f"{what}: {len(bad)} tick(s) outside the axis vocabulary — "
        + ", ".join(f"{t!r} in {n}" for t, n in bad[:8]))


# --- ARS: the whole chart set, from the real renderer ---------------------
def test_every_ars_chart_renders_one_month_form(odd_csv, tmp_path):
    """charts_gen renders all 28 ARS charts; this drives the real script."""
    base, metrics = tmp_path / "base.json", tmp_path / "metrics.json"
    charts = tmp_path / "charts"
    charts.mkdir()
    import subprocess
    for cmd in ([sys.executable, os.path.join(FIXTURES, "make_base.py"), odd_csv, str(base)],
                [sys.executable, os.path.join(ARS, "metrics_gen.py"), odd_csv, str(metrics)]):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ARS)
        assert r.returncode == 0, r.stderr[-2000:]

    argv = sys.argv
    sys.argv = ["charts_gen.py", str(metrics), str(base), str(charts)]
    try:
        with Recorder() as rec:
            runpy.run_path(os.path.join(ARS, "charts_gen.py"), run_name="__main__")
    finally:
        sys.argv = argv
    assert_one_form(rec, "ARS")


# --- ICS ------------------------------------------------------------------
def test_every_ics_month_chart_renders_one_form(tmp_path):
    d = detail(months_in("Jul 25", 9))
    d["referrals"] = {"trend": {"months": months_in("Jul 25", 12),
                                "referrals": [4 + i for i in range(12)],
                                "partial_last": True}}
    with Recorder() as rec:
        ICSCH.c_referral_trend(d, str(tmp_path / "trend.png"))
        ICSCH._monthly_bar(d, "interchange", str(tmp_path / "ic_tot.png"), False)
        ICSCH._monthly_bar(d, "interchange", str(tmp_path / "ic_pam.png"), True)
        ICSCH.c_composition(d, str(tmp_path / "comp.png"))
        ICSCH.c_perref(d, str(tmp_path / "perref.png"))
    assert_one_form(rec, "ICS")


# --- MRPC -----------------------------------------------------------------
def test_every_mrpc_month_chart_renders_one_form(tmp_path):
    m6, m8, m10, m12 = (mrpc_months_in("Jul 25", n) for n in (6, 8, 10, 12))
    d = {"meta": {"has_business": False},
         "enrollments_by_month": {"months": m6, "totals": [10, 12, 9, 14, 11, 7],
                                  "gold": [6, 7, 5, 8, 6, 4],
                                  "platinum": [4, 5, 4, 6, 5, 3],
                                  "partial_last": True},
         "performance_vs_goal": {"months": m10, "enrollments": [9] * 10, "goal_pct": 11},
         "retention": {"cohort_months": m8, "enrolled": [40, 38, 35, 30, 28, 22, 19, 11]},
         "revenue": {"by_month": {"months": m12,
                                  "revenue": [1000 * (i + 1) for i in range(12)]},
                     "annual": [{"year": "2024", "amount": 41000},
                                {"year": "2025", "amount": 52000},
                                {"year": "2026 YTD", "amount": 33000}]}}
    with Recorder() as rec:
        MRPCCH.chart_enroll(d, str(tmp_path / "e.png"), MRPCCH.DIMS["enroll"])
        MRPCCH.chart_perf(d, str(tmp_path / "p.png"), MRPCCH.DIMS["perf"])
        MRPCCH.chart_retention(d, str(tmp_path / "t.png"), MRPCCH.DIMS["retention"])
        MRPCCH.chart_revenue_month(d, str(tmp_path / "rm.png"), MRPCCH.DIMS["revmonth"])
        MRPCCH.chart_revenue(d, str(tmp_path / "ra.png"), MRPCCH.DIMS["revenue"])
    assert_one_form(rec, "MRPC")


def test_the_year_axis_keeps_four_digits(tmp_path):
    """Reg E by Vintage and MRPC Annual Revenue are a DIFFERENT vocabulary.

    They must not be swept into the month form by a later tidy-up, and they must
    not be left as free text either.
    """
    d = {"revenue": {"annual": [{"year": "2024", "amount": 41000},
                                {"year": "2025", "amount": 52000},
                                {"year": "2026 YTD", "amount": 33000}]}}
    with Recorder() as rec:
        MRPCCH.chart_revenue(d, str(tmp_path / "ra.png"), MRPCCH.DIMS["revenue"])
    years = [t for t, _ in rec.ticks if re.match(r"^(?:Pre-)?(?:19|20)\d{2}", t)]
    assert years, "no year ticks rendered"
    assert all(is_axis_label(t) for t in years), years
    assert not any(names_a_month(t) for t in years), years


# --- the surgery does not come back ---------------------------------------
# Each of these is a real line that used to be in a renderer. They are what
# turned one month into nine spellings, so they are named rather than described.
RETIRED = [
    (r"\.split\(\)\[0\]", 'm.split()[0] — the year discarded'),
    (r"\.replace\(\s*['\"] 20['\"]", '''.replace(' 20',"'") — Program Reach'''),
    (r"\[:3\]\s*\+\s*\w+\[-2:\]", 'c[:3]+c[-2:] — the NSF axis'),
    (r"strftime\(\s*['\"]%m-%Y", '%m-%Y — the numeric pill form'),
]


def executable_source(path):
    """The module's code with comments and DOCSTRINGS removed, nothing else.

    Both removals matter and so does the "nothing else". Every retired idiom is
    named in the very docstring explaining why it was retired, so a scrubber that
    only drops `#` lines reports the explanation as the offence. But dropping all
    string literals is just as wrong: `%m-%Y` only ever appears inside one, so
    that check would pass for the wrong reason. And a token scrubber that
    space-joins turns `m.split()[0]` into `m . split ( ) [ 0 ]`, which no
    punctuation pattern matches — the check silently stops working.

    `ast.unparse` of the tree with docstrings stripped gives normalized source:
    comments are absent (they never reach the AST), docstrings are removed here,
    and every other literal survives.
    """
    import ast
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


@pytest.mark.parametrize("path", CHART_MODULES, ids=lambda p: os.path.basename(p))
def test_no_renderer_slices_a_month_label(path):
    """A new chart must ask `axis.month_ticks`, not cut up a prose label."""
    code = executable_source(path)
    for pattern, what in RETIRED:
        assert not re.search(pattern, code), (
            f"{os.path.basename(path)} is back to slicing a month label ({what}) — "
            f"use axis.month_ticks and the pack's axis_months tokens")


def test_the_builder_no_longer_formats_a_pill_by_hand():
    code = executable_source(os.path.join(ARS, "build_ars_gen.py"))
    assert "%m-%Y" not in code, (
        "a window pill is back to the numeric form — use periods.axis_window")
