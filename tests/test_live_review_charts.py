"""Live Review's added chart types: donut, waterfall and quadrant scatter (Aaron, 2026-11-03: "I'd like to see more chart types in LR too").

The renderers live in the browser (static/live.js); these tests pin the blocks the programs hand it, where each type is used, and that
the page knows how to draw them.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline"), os.path.join(REPO, "tests")]

from review_page import blocks as B   # noqa: E402
from test_live_review import build, pack_root, CID   # noqa: E402,F401


def js():
    return open(os.path.join(REPO, "build", "review_page", "static", "live.js"), encoding="utf-8").read()


def walk(bs):
    for b in bs:
        if b["t"] == "variants":
            for o in b["options"]:
                yield from walk(o["blocks"])
        elif b["t"] == "drill":
            yield b["chart"]
            yield b["table"]
        else:
            yield b


def test_the_block_constructors_carry_what_the_page_draws():
    d = B.donut("d", "Loans by status", ["Funded", "Paid Off"], [3, 7], "int", center="Loans")
    assert d["t"] == "donut" and d["cats"] == ["Funded", "Paid Off"] and d["values"] == [3, 7] and d["center"] == "Loans"
    w = B.waterfall("w", "From revenue to profit", [{"key": "c0", "label": "Sep 2026", "steps": [{"label": "Revenue", "value": 10, "kind": "total"}]}], "usdk")
    assert w["t"] == "waterfall" and w["metrics"][0]["steps"][0]["kind"] == "total"
    s = B.scatter("s", "Take against Reg E", [{"name": "A", "x": 1, "y": 2, "size": 3}], "Take", "Reg E", "pct1", "pct1")
    assert s["t"] == "scatter" and s["quad"] is True and s["points"][0]["size"] == 3


def test_the_page_draws_each_new_type_and_keeps_its_axes_inside_the_data():
    src = js()
    for fn in ("function donutSVG", "function waterfallSVG", "function scatterSVG", "function niceTicks"):
        assert fn in src
    assert "{line: lineSVG, donut: donutSVG, waterfall: waterfallSVG, scatter: scatterSVG}" in src      # the dispatch
    assert 'b.t === "donut" || b.t === "waterfall" || b.t === "scatter"' in src                           # a card for each
    assert "if (v >= hi - step * 0.001) break" in src                                                     # ticks reach the last point
    assert "lo >= 0 ? Math.max(0, lo - d)" in src and "Math.min(100, hi + d)" in src                      # no negative axis, no percentage past 100


def test_the_ars_profit_bridge_is_a_waterfall_beside_the_monthly_chart(pack_root):
    model, _t, problems = build(pack_root)
    assert problems == []                                                                                 # every step traces to the P&L
    fin = next(s for s in model["programs"][0]["screens"] if s["id"] == "financial")
    view = next(b for b in fin["blocks"] if b["t"] == "variants")
    assert [o["key"] for o in view["options"]] == ["month", "bridge"]                                     # it still starts on the monthly chart
    wf = next(b for o in view["options"] for b in o["blocks"] if b["t"] == "waterfall")
    for m in wf["metrics"]:
        kinds = [s["kind"] for s in m["steps"]]
        assert kinds[0] == "total" and kinds[-1] == "total" and set(kinds[1:-1]) == {"delta"}
        assert abs(m["steps"][0]["value"] + sum(s["value"] for s in m["steps"][1:-1]) - m["steps"][-1]["value"]) < 0.51     # revenue less costs is the profit


def test_cashplease_loans_by_status_is_a_donut(tmp_path):
    packs = tmp_path / "cashplease" / "packs"
    packs.mkdir(parents=True)
    months = [{"period_month": f"2026-{m:02d}", "loans": 100, "principal": 40000.0, "interest": 1000.0,
               "funded": 90, "paid_off": 10, "overdue": 0, "charged_off": 0} for m in range(1, 10)]
    pack = {"client_id": CID, "client_name": "Test Bank", "source_file": "w.xlsx", "dda_sent": None, "report_generated": "10/12/2026 8:57:13 AM",
            "charge_off_pct": 0.04, "total": {"principal": 10.0, "interest": 3.0, "loans": 550}, "monthly": months,
            "status": {"Funded": {"principal": 1.0, "interest": 1.0, "loans": 50}, "Paid Off": {"principal": 9.0, "interest": 2.0, "loans": 500}},
            "metrics": {"total_loans": 550, "total_principal": 10.0, "active_loans": 50, "active_principal": 1.0, "avg_loan_size": 40.0,
                        "loans_per_1k_dda": None, "dda_missing_reason": "no DDA count"}}
    (packs / f"{CID}_cashplease.json").write_text(json.dumps(pack), encoding="utf-8")
    model, _t, problems = build(tmp_path, ("cashplease",))
    assert problems == []
    summary = model["programs"][0]["screens"][0]
    donut = next(b for b in walk(summary["blocks"]) if b["t"] == "donut")
    assert donut["cats"] == ["Funded", "Paid Off"] and donut["values"] == [50, 500]
    assert [b["t"] for b in summary["blocks"]][:2] == ["kpis", "donut"]                                   # tiles, then the chart, then the table


def test_branch_screens_offer_take_against_the_other_measure():
    import inspect
    from review_page.programs import companion, ti
    assert "B.scatter(" in inspect.getsource(companion._scorecard) and "B.scatter(" in inspect.getsource(ti._branch_gap)
    assert "len(rows) >= 4" in inspect.getsource(companion._scorecard)                                     # four branches or more: fewer make no quadrant
