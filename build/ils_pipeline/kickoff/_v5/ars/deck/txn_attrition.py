# Ported from v5 02-Scripts/ars/deck/txn_attrition.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
"""Attrition slides that need the transaction file: competitor spend before
closure (leakage.py) and the stressor count across both files
(stressors_txn.py). Both were computed on every run and drawn nowhere (#245).
"""
from __future__ import annotations

from . import charts, labels
from .txn_common import RAIL_EDGE, money

DEFAULT_MARGIN_L = 1.18


def _col(t: dict, key: str, name: str, default: int) -> int:
    cols = t.get(key) or []
    return cols.index(name) if name in cols else default


def spend_before_closure(h, t, base):
    curve = t.get("leak_curve") or []
    control = t.get("leak_control") or []
    if not curve:
        return "Competitor spend before closure (missing leak_curve)"
    i_off = _col(t, "leak_curve_columns", "offset_months", 0)
    i_n = _col(t, "leak_curve_columns", "n", 1)
    i_mean = _col(t, "leak_curve_columns", "mean_competitor_dollars", 2)
    xs = [r[i_off] for r in curve]
    closers = [r[i_mean] for r in curve]
    ctrl_by = {r[i_off]: r[i_mean] for r in control}
    ctrl = [ctrl_by.get(x) for x in xs]
    div = t.get("leak_divergence_month")
    if div is not None:
        head = (f"Closing accounts were paying competitors more from {div} month"
                f"{'s' if div != 1 else ''} before they closed")
    else:
        head = "No sustained rise in competitor spend was detectable before closure"
    sub = ("mean competitor dollars per account, month by month before the "
           "account's own close date; control: "
           f"{t.get('leak_control_basis') or 'still-open accounts'}")
    s, top = h["slide"]((head, sub), "Competitor spend before closure")
    path = h["chart"]("leak_curve", charts.pair_lines, xs, closers, ctrl,
                      "closing accounts", "still open", ylabel="$ per account",
                      xlabel="months before close")
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)
    last = curve[-1]
    last_ctrl = ctrl[-1]
    h["rail"](s, [("Last month", money(last[i_mean]),
                   f"vs {money(last_ctrl)} still open" if last_ctrl is not None else "closers"),
                  ("Closers measured", f"{last[i_n]:,}", "in the last month before close"),
                  ("Warning", f"{div} mo" if div is not None else "none", "before closure")],
              top=top)
    return None


def stresses_across_files(h, t, base):
    rows = t.get("stress_txn_by_count") or []
    if not rows:
        return "Stresses across both files (missing stress_txn_by_count)"
    n2 = t.get("stress_txn_2plus_n") or 0
    if n2:
        head = (f"{n2:,} accounts carry two or more stressors once banking elsewhere "
                f"is counted, holding {money(t.get('stress_txn_2plus_deposits'))}")
    else:
        head = "No account carries two stressors once banking elsewhere is counted"
    avail = t.get("stress_txn_available") or []
    skipped = t.get("stress_txn_skipped") or []
    sub = f"base: {t.get('stress_txn_base') or 'unstated'}; {len(avail)} condition(s) built"
    if skipped:
        sub += " -- not available: " + ", ".join(skipped)
    s, top = h["slide"]((head, sub), "Stresses across both files")
    table = [["Stressors", "Accounts", "% of base", "Deposits held"]] + [
        [r[0], f"{r[1]:,}", f"{r[2]:.1f}%", money(r[3])] for r in rows]
    left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
    h["table"](s, table, left, top, RAIL_EDGE - left)
    items = [("Two or more", f"{n2:,}", f"{t.get('stress_txn_2plus_pct') or 0:.1f}% of base"),
             ("To competitors", money(t.get("stress_txn_2plus_competitor_dollars")),
              "from those accounts")]
    for label in avail[:2]:
        items.append((labels.clip(label, 22), "", "built"))
    h["rail"](s, items, top=top)
    return None
