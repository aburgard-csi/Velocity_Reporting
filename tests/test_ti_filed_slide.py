# Ported from ARS v5 02-Scripts/tests/test_filed_slide.py at a491b5c (James Gilmore); logic unchanged.
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ti.deck import txn_compete  # noqa: E402

COLS = ["institution", "key", "regulator", "accounts", "pct_of_accounts", "dollars",
        "deposits_latest", "deposits_prior", "growth_pct", "latest_date", "quarters_apart"]


def _h(calls):
    def slide(pair, slide_id):
        calls.append(("slide", pair, slide_id))
        return "S", 1.0
    def chart(name, fn, rows, **kw):
        calls.append(("chart", name, rows, kw))
        return pathlib.Path("/tmp/x.png")
    return {"slide": slide, "chart": chart, "chart_left": lambda *a, **k: calls.append(("chart_left",)),
            "table": lambda *a, **k: None, "text": lambda *a, **k: None}


def test_skips_with_a_reason_when_no_filed_rows():
    calls = []
    why = txn_compete.filed_growth_slide(_h(calls), {"comp_filed": []}, {})
    assert "Filed growth" in why and calls == []


def test_headline_names_the_biggest_competitor_and_uses_filed_wording():
    calls = []
    t = {"comp_filed_columns": COLS, "comp_filed": [
        ["Chase", "fdic:9", "OCC", 120, 8.0, 250_000, 1_100_000_000, 1_000_000_000, 10.0, "2026-03-31", 4],
        ["Seamens Bank", "fdic:2", "FDIC", 40, 2.7, 90_000, 450_000_000, 500_000_000, -10.0, "2026-03-31", 4],
    ]}
    why = txn_compete.filed_growth_slide(_h(calls), t, {})
    assert why is None
    kind, pair, slide_id = calls[0]
    assert slide_id == "Filed growth"
    assert "Chase" in pair[0] and "10.0%" in pair[0]
    assert "deposit" not in pair[0].lower() and "filed" in pair[0].lower()
    assert "2026-03-31" in pair[1]
    chart = [c for c in calls if c[0] == "chart"][0]
    assert chart[1] == "comp_filed_growth"
    # momentum_bars rows: [name, count, depth_label, momentum_pct, marked]
    assert chart[2][0][0] == "Chase" and chart[2][0][1] == 120
    assert chart[2][0][3] == 10.0 and chart[2][1][3] == -10.0


def test_the_filed_growth_chart_draws_for_real(tmp_path):
    """The harness above records the chart call. This one lets momentum_bars
    run, so the row shape is proven: the branch first handed it two-field
    rows, which the stub accepted and the chart could not unpack."""
    from ti.deck import charts
    calls = []
    h = _h(calls)
    h["chart"] = lambda name, fn, rows, **kw: fn(rows, tmp_path / f"{name}.png", **kw)
    t = {"comp_filed_columns": COLS, "comp_filed": [
        ["Chase", "fdic:9", "OCC", 120, 8.0, 250_000, 1_100_000_000, 1_000_000_000, 10.0, "2026-03-31", 4],
        ["Seamens Bank", "fdic:2", "FDIC", 40, 2.7, 90_000, 450_000_000, 500_000_000, -10.0, "2026-03-31", 4],
    ]}
    assert txn_compete.filed_growth_slide(h, t, {}) is None
    assert (tmp_path / "comp_filed_growth.png").exists()
