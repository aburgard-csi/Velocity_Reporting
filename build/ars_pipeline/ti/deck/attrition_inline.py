# Ported from ARS v5 02-Scripts/ars/deck/build.py at a491b5c (James Gilmore); logic unchanged.
"""
attrition_inline.py — three attrition slides that v5 draws inline in `ars/deck/build.py` rather than
in a slide module: Attrition by branch, Attrition by group, and Account retention — survival by
tenure.

Each is lifted out of the build function as a builder with the house signature `(h, m)`, returning
None when drawn or the reason when declined, so the cut's chapters call it like any ported builder.
The bodies are v5's line for line; only the closures they called (`slide`, `_rail`, `chart`,
`_chart_left`, `_text`, `n`) are reached through the helper bundle `h`.
"""
from __future__ import annotations

from . import charts, headlines

FOOT_Y = 6.44


def _n(m, key, default=0):
    return m.get(key, default) or default


def attrition_branch(h, m) -> str | None:
    """Where the closures cluster, branch by branch (v5 build.py, "Attrition by branch")."""
    ab = m.get("attrition_by_branch") or []
    if not ab:
        return "missing attrition_by_branch"
    s, top = h["slide"](headlines.attrition_branch(m), "Attrition by branch")
    items = []
    if m.get("attrition_rate") is not None:
        items.append(("Book closure", f"{_n(m, 'attrition_rate')}%", "12-month window"))
    aworst = m.get("attrition_branch_worst")
    abest = m.get("attrition_branch_best")
    if aworst:
        items.append(("Highest", f"{aworst[1]:.1f}%", f"{aworst[0]}, {aworst[2]:,} at risk"))
    if abest:
        items.append(("Lowest", f"{abest[1]:.1f}%", f"{abest[0]}, {abest[2]:,} at risk"))
    right = h["rail"](s, items, top=top)
    path = h["chart"]("attrition_branch", charts.branch_bars, ab, m.get("attrition_rate") or 0.0)
    if path:
        h["chart_left"](s, path, top, right)
    h["text"](s, h["MARGIN_L"] + 0.02, FOOT_Y, h["CONTENT_W"], 0.3,
              "Bar is the closure rate; the figure inside is closures. "
              "Small branches swing hard -- the headline rates 150+ "
              "at-risk only.", size=9.5, color=h["GREY"])
    return None


def attrition_by_group(h, m) -> str | None:
    """Who leaves, by lens group, per account-year at risk (v5 build.py, "Attrition by group")."""
    al = m.get("attrition_by_lens") or []
    if len(al) < 3:
        return "missing attrition_by_lens"
    book = next((r for r in al if r[0] == "all"), None)
    book_rate = book[6] if book and book[6] is not None else 0.0
    named = [r for r in al if r[0] != "all" and r[6] is not None]
    ics_row = next((r for r in al if r[0] == "ics"), None)
    gap = m.get("attrition_ics_vs_book_pp")

    if ics_row and gap is not None:
        better = "below" if gap < 0 else "above"
        head = (f"ICS accounts close {abs(gap):.1f} points {better} the "
                f"book, at {ics_row[6]:.1f}% a year")
    else:
        head = "Who leaves, by group"
    s, top = h["slide"](
        (head, "closures per account-year at risk, so a group that opened "
               "recently is not flattered by its short exposure; dashed "
               "line is the book"),
        "Attrition by group")
    items = [("Book", f"{book_rate:.1f}%", "per account-year")]
    if ics_row:
        items.append(("ICS", f"{ics_row[6]:.1f}%", f"{ics_row[2]:,} at risk"))
    worst = max(named, key=lambda r: r[6]) if named else None
    if worst:
        items.append(("Highest", f"{worst[6]:.1f}%", f"{worst[1]}, {worst[2]:,} at risk"))
    right = h["rail"](s, items, top=top)
    rows = [[r[1], r[2], r[3], r[6]] for r in named]
    path = h["chart"]("attrition_lens", charts.branch_bars, rows, book_rate)
    if path:
        h["chart_left"](s, path, top, right)
    h["text"](s, h["MARGIN_L"] + 0.02, FOOT_Y, h["CONTENT_W"], 0.3,
              "Groups overlap -- an account can be a responder and an ICS "
              "account at once, so these do not sum to the book.",
              size=9.5, color=h["GREY"])
    return None


def survival_by_tenure(h, m) -> str | None:
    """How long accounts stay open (v5 build.py, "Account retention — survival by tenure")."""
    if not m.get("survival"):
        return "missing survival"
    s, top = h["slide"](None, "Account retention — survival by tenure")
    items = [("1 year", f"{_n(m, 'ret_1yr')}%", "still open")]
    if m.get("ret_3yr"):
        items.append(("3 years", f"{_n(m, 'ret_3yr')}%", "still open"))
    if m.get("median_closed_life"):
        items.append(("Median life", f"{_n(m, 'median_closed_life')} yr", "of closed accounts"))
    right = h["rail"](s, items, top=top)
    path = h["chart"]("survival", charts.line_series, m["survival"], ylabel="still open", pct=True)
    if path:
        h["chart_left"](s, path, top, right)
    return None
