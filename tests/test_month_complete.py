"""month_complete — comparisons use complete months only (Aaron, 2026-09-17).

"Don't calculate YoY or comparisons on partial months, only use complete months."
The trigger: Marine FCU 1539's 2026.09 NSF/OD slide said "-98% Items YoY (Aug 25 ->
Aug 26)" because the extract's August held 390 NSF/OD items against 19,451 in July,
while its swipes and spend for the same month were whole.

The unit half pins the rule on the real Marine figures and on the cases it must NOT
fire on. The fixture half runs the real metrics_gen and ticket_calc on the synthetic
ODD with a partial final month and checks every comparison moved back to the last
complete month, and that the default fixture is left alone.
"""
import datetime
import json
import os
import subprocess
import sys

import pytest

import month_complete as mc

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARS = os.path.join(REPO, "build", "ars_pipeline")
FIXTURES = os.path.join(REPO, "tests", "fixtures")
sys.path.insert(0, os.path.join(REPO, "build", "cashplease_pipeline"))

MARINE_TOKENS = ["Jan26", "Feb26", "Mar26", "Apr26", "May26", "Jun26", "Jul26", "Aug26"]
MARINE_ITEMS = [18960, 16126, 18456, 17293, 18635, 18754, 19451, 390]
MARINE_ACCTS = [4332, 3904, 4234, 4109, 4169, 4396, 4480, 290]
MARINE_SWIPES = [1001650, 917186, 1110972, 1090532, 1133538, 1081630, 1103258, 1104224]


# --------------------------------------------------------------------- the rule
def test_marine_partial_nsf_month_is_excluded():
    r = mc.assess(MARINE_TOKENS, MARINE_ITEMS, None, "NSF/OD items")
    assert r["last_complete"] == "Jul26" and r["complete"] == 7
    assert [(e["month"], e["value"], e["reason"]) for e in r["excluded"]] == [("Aug26", 390, "activity")]


def test_marine_whole_swipe_month_is_kept():
    """Completeness is per measure: August's swipes were whole in the same extract."""
    r = mc.assess(MARINE_TOKENS, MARINE_SWIPES, None, "debit swipes")
    assert r["last_complete"] == "Aug26" and r["excluded"] == []


def test_combine_takes_the_shortest_and_keeps_every_exclusion():
    r = mc.combine(mc.assess(MARINE_TOKENS, MARINE_SWIPES, None, "debit swipes"),
                   mc.assess(MARINE_TOKENS, MARINE_ITEMS, None, "NSF/OD items"),
                   mc.assess(MARINE_TOKENS, MARINE_ACCTS, None, "accounts with NSF/OD"))
    assert r["last_complete"] == "Jul26"
    assert sorted(e["measure"] for e in r["excluded"]) == ["NSF/OD items", "accounts with NSF/OD"]


def test_a_seasonal_dip_is_not_a_partial_month():
    """February runs ~85% of its neighbours; half is well clear of it."""
    r = mc.assess(MARINE_TOKENS[:2], [18960, 16126])      # too little baseline to judge
    assert r["excluded"] == []
    r = mc.assess(MARINE_TOKENS, MARINE_SWIPES[:7] + [0.6 * 1_090_000])
    assert r["excluded"] == [], "60% of baseline is a real month, not an unfinished one"


def test_a_dip_in_the_middle_of_a_series_is_data():
    vals = [100, 100, 100, 100, 100, 100, 10, 100]
    assert mc.assess(MARINE_TOKENS, vals)["excluded"] == []


def test_walks_back_over_two_trailing_partial_months_at_most():
    toks = ["Oct25", "Nov25", "Dec25"] + MARINE_TOKENS
    vals = [100] * 8 + [5, 5, 5]
    r = mc.assess(toks, vals)
    assert [e["month"] for e in r["excluded"]] == ["Jul26", "Aug26"]
    assert r["last_complete"] == "Jun26", (
        "a fall held three months is a real change, not an unfinished extract")


def test_a_zero_baseline_gives_no_verdict():
    assert mc.assess(MARINE_TOKENS, [0] * 7 + [5])["excluded"] == []


def test_a_blank_month_is_not_judged():
    assert mc.assess(MARINE_TOKENS, MARINE_ITEMS[:7] + [None])["excluded"] == []


def test_a_month_pulled_before_it_ended_is_excluded_whatever_its_volume():
    r = mc.assess(MARINE_TOKENS, MARINE_SWIPES, datetime.date(2026, 8, 20), "debit swipes")
    assert r["last_complete"] == "Jul26"
    assert r["excluded"][0]["reason"] == "pulled"
    # ...and a month that had ended is not
    assert mc.assess(MARINE_TOKENS, MARINE_SWIPES, datetime.date(2026, 9, 1))["excluded"] == []


def test_month_ended():
    assert mc.month_ended("Aug26", datetime.date(2026, 9, 1)) is True
    assert mc.month_ended("Aug 2026", datetime.date(2026, 8, 31)) is False
    assert mc.month_ended("Dec25", datetime.date(2026, 1, 1)) is True
    assert mc.month_ended("Aug26", None) is None


def test_pull_date_reads_the_member_stamp():
    name = "1539-2026-09-Marine FCU-ODD  (Sep23 forward) (090426_134750)_V2_1_1.csv"
    assert mc.pull_date(name) == datetime.date(2026, 9, 4)
    assert mc.pull_date("synthetic_odd.csv") is None


def test_excluded_sentence_names_the_month_and_the_figures():
    r = mc.combine(mc.assess(MARINE_TOKENS, MARINE_ITEMS, None, "NSF/OD items"),
                   mc.assess(MARINE_TOKENS, MARINE_ACCTS, None, "accounts with NSF/OD"))
    s = mc.excluded_sentence(r)
    assert s.startswith("Aug 2026 is left out as incomplete in this extract: 390 NSF/OD items")
    assert "290 accounts with NSF/OD" in s
    assert mc.excluded_sentence(mc.assess(MARINE_TOKENS, MARINE_SWIPES)) == ""


def test_complete_rows_on_the_workbook_series():
    rows = [["%s 2026" % m[:3], v / 20000, 35000] for m, v in zip(MARINE_TOKENS, MARINE_ITEMS)]
    kept, res = mc.complete_rows(rows, 1, "$M debit spend", min_volume=0)
    assert kept[-1][0] == "Jul 2026" and len(kept) == 7
    assert mc.excluded_months(res) == ["Aug 2026"]


def test_small_counts_are_not_judged():
    """An MRPC client enrolling a handful of cards has real months of 0 (1477: 2, 4, 2, 0)."""
    assert mc.assess(MARINE_TOKENS, [6, 10, 3, 2, 5, 3, 4, 0])["excluded"] == []


def test_iso_months_and_report_stamps():
    assert mc.month_start("2026-08") == datetime.date(2026, 8, 1)
    assert mc.month_start("2026-08-31") == datetime.date(2026, 8, 1)
    assert mc.report_date("9/13/2026 8:06:12 AM") == datetime.date(2026, 9, 13)
    assert mc.month_ended("2026-09", mc.report_date("9/13/2026 8:06:12 AM")) is False
    assert mc.month_ended("2026-08", mc.report_date("9/13/2026 8:06:12 AM")) is True


def test_the_module_is_import_safe():
    """metrics_gen runs at import; this module must not (CLAUDE.md, shared layer)."""
    import ast
    tree = ast.parse(open(mc.__file__, encoding="utf-8").read())
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "sys" not in names and "open" not in names
    top = [n for n in tree.body if not isinstance(
        n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign, ast.Expr))]
    assert top == [], "module-level statements beyond definitions run at import"


# --------------------------------------------------------------------- the fixture
def _odd(tmp_path, *flags):
    out = tmp_path / ("odd%s.csv" % "".join(f.replace("-", "_") for f in flags))
    r = subprocess.run([sys.executable, os.path.join(FIXTURES, "make_odd.py"), str(out), *flags],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-2000:]
    return str(out)


def _run(script, *args):
    r = subprocess.run([sys.executable, os.path.join(ARS, script), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ARS)
    assert r.returncode == 0, f"{script} failed:\n{r.stderr[-3000:]}"
    return r


@pytest.fixture(scope="module")
def partial_nsf(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("partial_nsf")
    odd = _odd(tmp, "--partial-nsf")
    met = tmp / "metrics.json"
    _run("metrics_gen.py", odd, met)
    tick = tmp / "ticket.json"
    _run("ticket_calc.py", odd, tick)
    return json.loads(met.read_text(encoding="utf-8")), json.loads(tick.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def partial_activity(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("partial_act")
    odd = _odd(tmp, "--partial-activity")
    met = tmp / "metrics.json"
    _run("metrics_gen.py", odd, met)
    return json.loads(met.read_text(encoding="utf-8"))


def test_the_default_fixture_has_no_partial_month(metrics):
    mcomp = metrics["month_completeness"]
    assert all(not mcomp[k]["excluded"] for k in ("activity", "nsf", "all"))
    assert metrics["nsf_series"][-1][0] == "Jul 26"
    assert metrics["nsf_excluded"] == [] and metrics["nsf_excluded_note"] == ""
    assert metrics["activity_month"] == "Jul 2026"


def test_nsf_yoy_compares_the_last_complete_month(partial_nsf):
    m, _ = partial_nsf
    assert m["nsf_series"][-1][0] == "Jun 26", "the partial month must not end the series"
    assert m["nsf_yoy_window"] == ["Jan–Jun 25", "Jan–Jun 26"]     # YTD, not month vs month (2026-10-12)
    assert m["nsf_last_month"] == "Jun 2026"
    assert [r[0] for r in m["nsf_excluded"]] == ["Jul 26"], "the left-out month is carried, not dropped"
    assert m["nsf_excluded_note"].startswith("Jul 2026 is left out as incomplete")
    # the YoY is recomputed from the rows it names — never a phantom from the partial month
    s = {r[0]: r[1] for r in m["nsf_series"]}
    cur = sum(s[f"{mo} 26"] for mo in ("Jan", "Feb", "Mar", "Apr", "May", "Jun"))
    prior = sum(s[f"{mo} 25"] for mo in ("Jan", "Feb", "Mar", "Apr", "May", "Jun"))
    assert m["nsf_yoy"] == round(100 * (cur - prior) / prior)
    assert m["nsf_last_items"] == s["Jun 26"]


def test_partial_nsf_leaves_the_activity_month_alone(partial_nsf):
    """Per measure: whole swipes in the same month still count for usage tiles."""
    m, _ = partial_nsf
    assert m["activity_month"] == "Jul 2026"
    assert m["month_completeness"]["activity"]["excluded"] == []


def test_windows_reading_nsf_end_on_complete_months(partial_nsf):
    m, t = partial_nsf
    assert m["w3_label"].endswith("Jun 2026"), m["w3_label"]
    assert t["win"][-1] == "Jun26", "ticket window and swipe-tier window must agree"


def test_partial_activity_moves_the_usage_month_back(partial_activity, metrics):
    m = partial_activity
    assert m["activity_month"] == "Jun 2026"
    assert m["month_completeness"]["activity"]["last_complete"] == "Jun26"
    assert m["w3_label"].endswith("Jun 2026")
    # Sustained never averages in the half-loaded month: every post-mailing window that
    # reached the final month is exactly one month shorter.
    full = {row[0]: row[3] for row in metrics["sustained"]}
    for label, _n, _pct, window in m["sustained"]:
        if full.get(label, 0) >= 1:
            assert window == full[label] - 1, (label, window, full[label])


def test_before_after_windows_stop_at_the_last_complete_month(partial_nsf, metrics):
    m, _ = partial_nsf
    # one fewer month available on the after side can only shrink the window or the
    # mailings it covers — never extend them into the partial month
    assert m["ba_n_mailings"] <= metrics["ba_n_mailings"]


# --------------------------------------------------------------------- CashPlease / MRPC
def _cp_sheet(generated, labels):
    """A CashPlease client tab on the fixed layout, with `labels` from row 22 down."""
    import openpyxl
    ws = openpyxl.Workbook().active
    ws["B6"] = f"Report Generated: {generated}"
    for i, lab in enumerate(labels):
        ws.cell(22 + i, 2).value = lab
        ws.cell(22 + i, 12).value = 10 + i
    ws.cell(22 + len(labels), 2).value = "* - Month roll-up"
    return ws


def test_cashplease_rollup_for_a_month_not_yet_ended_is_held_out():
    """The '*' convention says completed; the calendar has to agree (2026-09-17)."""
    import cp_extract
    ws = _cp_sheet("9/13/2026 8:06:12 AM",
                   ["2026-09-13", "2026-09-30*", "2026-08-31*", "2026-07-31*"])
    p = cp_extract.read_sheet(ws)
    assert [r["period_month"] for r in p["monthly"]] == ["2026-08", "2026-07"]
    assert [r["period_month"] for r in p["monthly_in_progress"]] == ["2026-09"]
    assert [r["period"] for r in p["daily"]] == ["2026-09-13"]


def test_cashplease_completed_rollups_are_untouched():
    import cp_extract
    p = cp_extract.read_sheet(_cp_sheet("9/13/2026 8:06:12 AM", ["2026-09-13", "2026-08-31*"]))
    assert [r["period_month"] for r in p["monthly"]] == ["2026-08"] and p["monthly_in_progress"] == []


def test_mrpc_series_ending_on_a_month_in_progress_are_trimmed_and_stated():
    import build_mrpc_gen as B
    data = {"meta": {"data_pull": "2026-09-04"},
            "performance_vs_goal": {"months": ["Jun 26", "Jul 26", "Aug 26", "Sep 26"],
                                    "new_accounts": [900, 950, 910, 120],
                                    "enrollments": [97, 114, 111, 9], "goal": [180, 190, 182, 24],
                                    "pct_of_goal": [54, 60, 61, 38], "goal_pct": 20},
            "revenue": {"by_month": {"months": ["Jun 26", "Jul 26", "Aug 26"],
                                     "revenue": [33000.0, 33300.0, 33200.0]}}}
    notes = B.complete_series(data)
    p = data["performance_vs_goal"]
    assert p["months"][-1] == "Aug 26" and len(p["pct_of_goal"]) == 3 and p["goal_pct"] == 20
    assert notes["performance_vs_goal"].startswith("Sep 2026 is left out: the data was pulled 2026-09-04")
    assert data["revenue"]["by_month"]["months"][-1] == "Aug 26" and "revenue.by_month" not in notes
