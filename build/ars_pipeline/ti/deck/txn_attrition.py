# Ported from ARS v5 02-Scripts/ars/deck/txn_attrition.py at a491b5c (James Gilmore); logic unchanged.
"""Attrition slides that need the transaction file: competitor spend before
closure (leakage.py) and the stressor count across both files
(stressors_txn.py). Both were computed on every run and drawn nowhere (#245).
"""
from __future__ import annotations

from . import charts
from .txn_common import RAIL_EDGE, money

DEFAULT_MARGIN_L = 1.18
NOTE_PT = 10.5
NOTE_Y = 6.30


def _note(h, s, text):
    """A short stated note at the foot of the content; nothing on a stub harness without `text`."""
    if text and h.get("text"):
        left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
        h["text"](s, left + 0.02, NOTE_Y, RAIL_EDGE - left, 0.4, text, size=NOTE_PT,
                  color=h.get("GREY"))


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
    # A month with no closers measured (n 0, mean None) is left off the chart and the tiles and
    # stated in a note; v5 read the last row regardless and printed "n/a" (1798: offset 12 has no
    # closers, and no still-open control was measured at all; Sheila's 1798 review, 2026-10-30).
    unmeasured = [r[i_off] for r in curve if r[i_mean] is None]
    curve = [r for r in curve if r[i_mean] is not None]
    if not curve:
        return "Competitor spend before closure (no closing account had competitor spend measured)"
    xs = [r[i_off] for r in curve]
    closers = [r[i_mean] for r in curve]
    ctrl_by = {r[i_off]: r[i_mean] for r in control if r[i_mean] is not None}
    ctrl = [ctrl_by.get(x) for x in xs]
    has_ctrl = any(v is not None for v in ctrl)
    div = t.get("leak_divergence_month")
    if div is not None:
        head = (f"Closing accounts were paying competitors more from {div} month"
                f"{'s' if div != 1 else ''} before they closed")
    else:
        head = "No sustained rise in competitor spend was detectable before closure"
    sub = ("mean competitor dollars per account, month by month before the "
           "account's own close date; "
           + (f"control: {t.get('leak_control_basis') or 'still-open accounts'}" if has_ctrl else
              "no still-open control could be measured on this file"))
    s, top = h["slide"]((head, sub), "Competitor spend before closure")
    path = h["chart"]("leak_curve", charts.pair_lines, xs, closers, ctrl,
                      "closing accounts", "still open", ylabel="$ per account",
                      xlabel="months before close")
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)
    # The month before close: offset 1 (or -1) where the curve has it, else the nearest measured
    # month to the close. v5 took the curve's last row, which is the month FURTHEST from the close
    # when offsets count up from 0 (1798), and labelled it "the last month before close".
    nonzero = [r for r in curve if r[i_off] not in (0, None)] or curve
    last = min(nonzero, key=lambda r: abs(r[i_off]))
    last_ctrl = ctrl_by.get(last[i_off])
    away = abs(last[i_off])
    when = "the month before close" if away == 1 else f"{away} months before close"
    h["rail"](s, [("Month before close" if away == 1 else f"{away} months out", money(last[i_mean]),
                   f"vs {money(last_ctrl)} still open" if last_ctrl is not None
                   else "per closing account"),
                  ("Closers measured", f"{last[i_n]:,}", f"in {when}"),
                  ("Warning", f"{div} mo" if div is not None else "none", "before closure")],
              top=top)
    if unmeasured:
        _note(h, s, "No closing account was measured "
                    + (f"{abs(unmeasured[0])} months before close" if len(unmeasured) == 1 else
                       f"in {len(unmeasured)} of the months") + "; left off the chart.")
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
    sub = (f"base: {t.get('stress_txn_base') or 'unstated'}; conditions: "
           f"{', '.join(str(a) for a in avail) or 'none'}")
    if skipped:
        sub += " -- not available: " + ", ".join(skipped)
    s, top = h["slide"]((head, sub), "Stresses across both files")
    table = [["Stressors", "Accounts", "% of base", "Deposits held"]] + [
        [r[0], f"{r[1]:,}", f"{r[2]:.1f}%", money(r[3])] for r in rows]
    left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
    h["table"](s, table, left, top, RAIL_EDGE - left)
    # No tile without a value: v5 gave each condition a tile reading "" / "built", and a missing
    # figure read "n/a" or 0.0%. The conditions are named in the subtitle (Sheila's 1798 review,
    # 2026-10-30).
    pct = t.get("stress_txn_2plus_pct")
    items = [("Two or more", f"{n2:,}", f"{pct:.1f}% of base" if pct is not None else None)]
    if t.get("stress_txn_2plus_competitor_dollars") is not None:
        items.append(("To competitors", money(t.get("stress_txn_2plus_competitor_dollars")),
                      "from those accounts"))
    h["rail"](s, items, top=top)
    return None
