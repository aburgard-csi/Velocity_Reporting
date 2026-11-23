#!/usr/bin/env python3
"""blocks.py — the vocabulary a program module speaks and the browser draws.

A view model is plain JSON. A screen is a title, a headline sentence, a list of blocks, the source
entries behind it, and any notes the page must state (a month left out, data not carried). The
browser knows these block types and nothing about any program:

    kpis      tiles: label, value, fmt, sub
    bars      vertical or horizontal bars, one or more series, optional drill into a table
    line      lines over months
    donut     a whole split into parts (loans by status, cardholders by engagement)
    waterfall a running total built up or down in steps (revenue less each cost line = profit)
    scatter   points on two measures, sized by a third, with the medians drawn (take rate against Reg E opt-in by branch)
    matrix    a heat grid (rows x columns)
    table     sortable, searchable; `kind` rows for a P&L
    variants  a segmented control that swaps the blocks beneath it (a cohort, a metric)
    drill     a chart tied to the table behind it: click a bar, the table opens on that row

`fmt` names how the browser prints a raw number: int, usd, usdk, usd2, pct1 and pct2 (the value is already a
percent), pct0, frac1 (0-1), dec1, dec2, ratio. Numbers in the model are raw; the browser formats.

Import-safe.
"""


# ----------------------------------------------------------------- sentence formatters
def f_int(v):
    return f"{v:,.0f}"


def f_usd(v):
    return f"${v:,.0f}"


def f_usdk(v):
    """$1.24M at a million and up, $830K below, whole dollars under a thousand (brand.usd_compact's rule)."""
    a = abs(v)
    s = "-" if v < 0 else ""
    if a >= 1e6:
        return f"{s}${a / 1e6:.2f}M"
    if a >= 1e3:
        return f"{s}${a / 1e3:.0f}K"
    return f"{s}${a:,.0f}"


def f_pct1(v):
    return f"{v:.1f}%"


def f_pct0(v):
    return f"{v:.0f}%"


def f_ratio(v):
    return "—" if v is None else f"{v:.1f} : 1"


# ----------------------------------------------------------------- blocks
def kpi(label, value, fmt, sub=None, tone=None, hot=False, go=None):
    return {"label": label, "value": value, "fmt": fmt, "sub": sub, "tone": tone, "hot": hot, "go": go}


def kpis(items):
    return {"t": "kpis", "items": items}


def bars(id, title, cats, series, fmt, sub=None, horizontal=False, stacked=False, drill=None,
         highlight=None, empty=None, metrics=None):
    """series: [{"name", "values", "color"?}] — colors are names the browser maps to the palette
    (navy, orange, steel, teal, tick, gold). `drill` is {"table": id} and makes a bar clickable.
    `metrics`: [{"key", "label", "series", "fmt"}] adds a small control that swaps what the bars show."""
    return {"t": "bars", "id": id, "title": title, "sub": sub, "cats": cats, "series": series, "fmt": fmt,
            "horizontal": horizontal, "stacked": stacked, "drill": drill, "highlight": highlight,
            "empty": empty, "metrics": metrics}


def line(id, title, cats, series, fmt, sub=None, empty=None):
    return {"t": "line", "id": id, "title": title, "sub": sub, "cats": cats, "series": series, "fmt": fmt,
            "empty": empty}


def matrix(id, title, rows, cols, values, fmt, sub=None, mark=None):
    return {"t": "matrix", "id": id, "title": title, "sub": sub, "rowsl": rows, "cols": cols,
            "values": values, "fmt": fmt, "mark": mark}


def col(key, label, fmt=None, align=None):
    return {"key": key, "label": label, "fmt": fmt, "align": align or ("right" if fmt else "left")}


def table(id, title, cols, rows, total=None, search=True, sort=None, sub=None, key="name", kind=None):
    """rows: list of dicts keyed by col.key. `total`: a dict of the same keys (an All row), drawn last."""
    return {"t": "table", "id": id, "title": title, "sub": sub, "columns": cols, "rows": rows,
            "total": total, "search": search, "sort": sort, "key": key, "kind": kind}


def donut(id, title, cats, values, fmt, sub=None, center="Total", empty=None):
    """A whole split into parts: `cats` and `values` in step; only positive values are drawn."""
    return {"t": "donut", "id": id, "title": title, "sub": sub, "cats": cats, "values": values, "fmt": fmt, "center": center, "empty": empty}


def waterfall(id, title, metrics, fmt, sub=None, empty=None):
    """metrics: [{"key", "label", "steps": [{"label", "value", "kind"}]}], one waterfall per metric (the first is shown first).
    A "total" step stands on the baseline (revenue, profit); a "delta" step moves the running total (a cost is negative)."""
    return {"t": "waterfall", "id": id, "title": title, "sub": sub, "metrics": metrics, "fmt": fmt, "empty": empty}


def scatter(id, title, points, xlabel, ylabel, xfmt, yfmt, sub=None, slabel="accounts", sfmt="int", quad=True, empty=None):
    """points: [{"name", "x", "y", "size"}]. The medians are drawn; with `quad` the corner below both is shaded (the branches to coach)."""
    return {"t": "scatter", "id": id, "title": title, "sub": sub, "points": points, "xlabel": xlabel, "ylabel": ylabel,
            "xfmt": xfmt, "yfmt": yfmt, "slabel": slabel, "sfmt": sfmt, "quad": quad, "empty": empty}


def variants(id, label, options):
    """options: [{"key", "label", "blocks": [...]}] — the first is shown first."""
    return {"t": "variants", "id": id, "label": label, "options": options}


def drill(chart, tbl):
    """A chart whose bars open the table behind it (same block ids wire them together)."""
    chart = dict(chart)
    chart["drill"] = {"table": tbl["id"]}
    return {"t": "drill", "chart": chart, "table": tbl}


def screen(id, title, kicker, headline, blocks, sources, notes=None):
    return {"id": id, "title": title, "kicker": kicker, "headline": headline, "blocks": blocks,
            "sources": sources, "notes": notes or []}
