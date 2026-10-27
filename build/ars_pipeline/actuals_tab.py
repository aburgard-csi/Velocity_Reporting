#!/usr/bin/env python3
"""
actuals_tab.py — the ONE reading of the ARS workbook's Actuals tab.

The Actuals tab is the program's month-by-month P&L: marginal revenue, cost, incremental
profit and the cumulative contribution, one column per month since the program started. Until
now nothing in the pipeline read it — the financial slides took program-to-date totals off
Executive Financials, which is the same arithmetic already done, with the months thrown away.

The 2 : 1 revenue guarantee needs the months (Aaron, 2026-09-22: "you should be able to
calculate the 2:1 guarantee slides from the Actuals tab"): a guarantee is a statement about
revenue against cost over the life of the program, and the only way to show whether a client
is closing on it or drifting away from it is to draw both lines.

The tab comes in three shapes in the same workbook — `Actuals MM`, `Actuals SM` and plain
`Actuals` — matching the three Executive Financials tabs, and their COST ROWS DIFFER (an MM
client is billed a respondent fee; an SM client carries spot mailings, points and a program
fee). Two rows are read here, and both exist in every shape:

    Total Marginal Revenues     the month's revenue
    Total Cost                  the month's cost, negative in the sheet

and so are the cost lines between the "Costs" heading and Total Cost, whatever this shape
calls them, so the Revenue Guarantee slide can lay the program out as a P&L (Aaron,
2026-10-02). Their labels are taken from the sheet, never from a list kept here, because the
MM and SM shapes carry different ones.

Read once, here, because two extractors need it and a second copy of this parsing is how
`metrics_gen` and `responder_activity` drifted apart for a year.

Public entry point
------------------
    read(workbook_path_or_open_workbook, mm=True) -> dict | {"available": False, ...}
"""
import datetime
import os
import re

# Both wordings are in use: the SM tab says "Total Marginal Revenues", a new client's MM tab
# "Total Marginal Revenue" (Texar 1805, 2026-10-26).
REV_LABELS = ("total marginal revenues", "total marginal revenue")
# A new client has three months of actuals, so three is the shortest header row read as the
# months; fewer is a stray date, not a month row.
MIN_MONTH_COLUMNS = 3
COST_LABEL = "total cost"
# In tab order of preference. An MM client's workbook carries all three; taking the plain one
# for an MM client would report the SM revenue model's figures, which is the bug this ordering
# exists to prevent.
MM_SHEETS = ("Actuals MM",)
SM_SHEETS = ("Actuals", "Actuals SM")
_GENERATED = re.compile(r"report generated:\s*(\S+)", re.I)


def _label_of(row, depth=4):
    """The row's label — the last text cell before the month columns start."""
    out = ""
    for c in row[:depth]:
        if isinstance(c, str) and c.strip():
            out = c.strip()
    return out


def _sheet_names(wb, mm):
    want = MM_SHEETS if mm else SM_SHEETS
    return [n for n in want if n in wb.sheetnames]


def _label(dt):
    return f"{dt:%b %Y}"


def read(source, mm=True):
    """Read the Actuals tab. `source` is a path or an already-open openpyxl workbook.

    Returns {"available": True, "sheet", "months": [[label, revenue, cost], ...],
             "lines": [[label, [cost per month, aligned with months]], ...],
             "revenue", "cost", "generated", "total_column"} with cost POSITIVE (a discount
    is therefore negative), or
    {"available": False, "reason": ...} — never a partial dict, so a caller cannot read a
    total that was never found.
    """
    import openpyxl
    opened = False
    if hasattr(source, "sheetnames"):
        wb = source
    else:
        if not source or not os.path.exists(str(source)):
            return {"available": False, "reason": "no ARS workbook was found for this period"}
        wb = openpyxl.load_workbook(str(source), read_only=True, data_only=True)
        opened = True
    try:
        names = _sheet_names(wb, mm)
        if not names:
            return {"available": False,
                    "reason": "the workbook has no %s tab" % (" or ".join(
                        MM_SHEETS if mm else SM_SHEETS))}
        sheet = names[0]
        rows = [list(r) for r in wb[sheet].iter_rows(values_only=True)]
    finally:
        if opened:
            wb.close()

    hdr = next((r for r in rows
                if sum(1 for c in r if isinstance(c, datetime.datetime)) >= MIN_MONTH_COLUMNS), None)
    if hdr is None:
        return {"available": False, "reason": f"'{sheet}' carries no month columns"}
    cols = [(j, c) for j, c in enumerate(hdr) if isinstance(c, datetime.datetime)]

    rev_row = cost_row = None
    cost_at = None
    generated = None
    for i, r in enumerate(rows):
        lab = _label_of(r).lower()
        if lab in REV_LABELS and rev_row is None:
            rev_row = r
        elif lab == COST_LABEL and cost_row is None:
            cost_row, cost_at = r, i
        for c in r:
            if isinstance(c, str) and generated is None:
                m = _GENERATED.search(c)
                if m:
                    generated = m.group(1)
    if rev_row is None or cost_row is None:
        missing = " and ".join(x for x, y in (("Total Marginal Revenues", rev_row),
                                              ("Total Cost", cost_row)) if y is None)
        return {"available": False, "reason": f"'{sheet}' has no {missing} row"}

    def num(row, j):
        v = row[j] if j < len(row) else None
        return float(v) if isinstance(v, (int, float)) else None

    months, kept = [], []
    for j, dt in cols:
        rev, cost = num(rev_row, j), num(cost_row, j)
        if rev is None and cost is None:
            continue                        # a month the sheet carries no figures for
        months.append([_label(dt), round(rev or 0.0, 2), round(abs(cost or 0.0), 2)])
        kept.append(j)

    # The cost lines: every labelled row above Total Cost, back to the "Costs" heading.
    lines = []
    for r in reversed(rows[:cost_at]):
        lab = _label_of(r)
        if lab.lower() == "costs":
            break
        if lab and any(num(r, j) is not None for j in kept):
            lines.insert(0, [lab, [round(-(num(r, j) or 0.0), 2) + 0.0 for j in kept]])
    if not months:
        return {"available": False, "reason": f"'{sheet}' carries no month with figures"}

    # The sheet ends with a program-to-date total column beyond the last month. It is read as
    # a CROSS-CHECK, never as the answer: summing the months is the figure the chart draws, and
    # a total that disagrees with its own months is worth seeing rather than trusting.
    last = cols[-1][0]
    tail = [num(rev_row, j) for j in range(last + 1, len(rev_row))]
    total_col = next((v for v in tail if v is not None), None)

    return {
        "available": True,
        "sheet": sheet,
        "months": months,
        "lines": lines,
        "revenue": round(sum(m[1] for m in months), 2),
        "cost": round(sum(m[2] for m in months), 2),
        "total_column": round(total_col, 2) if total_col is not None else None,
        "generated": generated,
        "window": [months[0][0], months[-1][0]],
    }
