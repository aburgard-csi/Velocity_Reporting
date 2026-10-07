#!/usr/bin/env python3
"""mrpc_revenue_file.py - MRPC revenue by month from Accounting's "MRPC Revenue.xlsx".

The VIP "Revenue by Month" dashboard trails the rest of the program by months (Austin Bank's ended May 2026
in an October deck), and Accounting's workbook carries the missing months. It lives in
`Inputs/MRPC Analyses/MRPC Revenue.xlsx`: one row per client ("V<id>-NAME"), one column per month end, and a
"Grand Total" row and column that are ignored.

HOW IT IS USED (Aaron, 2026-10-06: "extend the series with it", months that look doubled "use as given,
note it"):

1. The client's VIP series is kept for every month BEFORE the workbook's first month; from that month on
   the workbook's figures are used, so a month both carry (April and May 2026) reads the workbook's.
2. The result is cut to the last 12 months, which is what the slide's "Avg Monthly Revenue (12 mo)" and
   "Trailing-12 Revenue" tiles say they are.
3. The "<year> YTD" bar on Revenue by Year is recomputed from the extended series (January through the last
   month), because the projection needs the YTD to run through the month the series ends on. Austin's
   VIP YTD of $165,270.05 through May is exactly the sum of its January to May months, so nothing is
   changed in kind by recomputing it. Life-of-program (the prior years plus the YTD) moves by the same
   amount, so the two never carry different sources for the same months (Aaron, 2026-10-06: the VIP and
   Accounting figures for a month do not stack; Accounting's is used).
4. A month at 1.8x the series median or more is named in the notes as stated, not smoothed.
5. `_file` on the block records what was done, for the notes; `_file["as_of"]` is the workbook's own date,
   which `build_mrpc_gen.complete_series` uses instead of the VIP pull date (the pull date predates the
   months the workbook supplies and would mark them all as not yet ended).

A client the workbook does not list, or a workbook that is absent, leaves the data exactly as it was.

IMPORT-SAFE: nothing is read at import time.
"""
from __future__ import annotations

import datetime
import re
import statistics

FILENAME = "MRPC Revenue.xlsx"
WINDOW = 12
DOUBLED_AT = 1.8          # x the series median at or above which a month is called out

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_cache = {}


def file_path():
    """Where the workbook belongs, resolved through rpe_env like every other input."""
    import rpe_env as R
    return R.input_dir("MRPCPM", create=False) / FILENAME


def _token(d):
    return f"{_MON[d.month - 1]} {d.year % 100:02d}"


def read(path):
    """{client id: {"months": ["Apr 26", ...], "values": [float | None, ...]}} (cached per file version)."""
    import openpyxl
    key = (str(path), path.stat().st_mtime_ns)
    if key in _cache:
        return _cache[key]
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        # Accounting's corrected file (2026-10-07) has title rows above the header and a second sheet of customer
        # refunds, so: the sheet named Sheet1 (else the active one), and the header is the row that starts "Client".
        ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.active
        rows = ws.iter_rows(values_only=True)
        head = next((r for r in rows if str(r[0] or "").strip().lower() == "client"), None)
        if head is None:
            return {}
        cols = [(i, c) for i, c in enumerate(head) if i and isinstance(c, (datetime.date, datetime.datetime))]
        out = {}
        for r in rows:
            m = re.match(r"^V(\d+)-", str(r[0] or ""))
            if not m:
                continue                         # the Grand Total row, a blank
            out[m.group(1)] = {
                "months": [_token(c) for _i, c in cols],
                "values": [None if r[i] is None else float(r[i]) for i, _c in cols],
            }
    finally:
        wb.close()
    _cache.clear()
    _cache[key] = out
    return out


def _trim(months, values):
    """Drop months with no figure at either end (a client that had not started yet, or has stopped);
    a gap inside the run is a month of $0."""
    lo, hi = 0, len(values)
    while lo < hi and values[lo] is None:
        lo += 1
    while hi > lo and values[hi - 1] is None:
        hi -= 1
    return months[lo:hi], [0.0 if v is None else v for v in values[lo:hi]]


def apply(data, path=None):
    """Extend `data["revenue"]["by_month"]` with the workbook's months, in place.

    -> the `_file` record, or None when nothing was changed (no workbook, no row for this client, or the
    sheet has no monthly series to extend)."""
    import month_complete as MC
    p = path or file_path()
    if not p.exists():
        return None
    rec = read(p).get(str((data.get("meta") or {}).get("client_id")))
    rv = data.get("revenue") or {}
    bm = rv.get("by_month")
    if not rec or not bm or not bm.get("months") or not bm.get("revenue"):
        return None
    fm, fv = _trim(rec["months"], rec["values"])
    if not fm:
        return None
    first = MC.month_start(fm[0])
    kept = [(m, v) for m, v in zip(bm["months"], bm["revenue"]) if MC.month_start(m) < first]
    replaced = [m for m in bm["months"] if MC.month_start(m) >= first and m in fm]
    vip_last = bm["months"][-1]
    pairs = (kept + list(zip(fm, fv)))[-WINDOW:]
    months, values = [m for m, _v in pairs], [v for _m, v in pairs]
    bm["months"], bm["revenue"] = months, values

    med = statistics.median(values)
    doubled = [{"month": m, "value": v, "median": med} for m, v in zip(months, values)
               if med > 0 and v >= DOUBLED_AT * med and m in fm]

    # The YTD bar follows the extended series, when the series covers January to its last month.
    ytd_year = None
    last = MC.month_start(months[-1])
    ytd = next((a for a in rv.get("annual") or [] if "YTD" in str(a.get("year", ""))), None)
    if ytd:
        year = int(str(ytd["year"]).split()[0])
        if last.year == year:
            in_year = {MC.month_start(m).month: v for m, v in zip(months, values) if MC.month_start(m).year == year}
            if all(mm in in_year for mm in range(1, last.month + 1)):
                old_ytd = float(ytd["amount"])
                ytd["amount"] = round(sum(in_year[mm] for mm in range(1, last.month + 1)), 2)
                ytd["ytd_through"] = _MON[last.month - 1]
                ytd_year = year
                # Life-of-program is the prior years plus the YTD (Austin: 2016 to 2025 $2,220,538 + YTD
                # $165,270 = $2,385,808), so it moves with the YTD. Left alone it would still carry VIP's YTD,
                # VIP's May with it, beside a YTD bar that now carries Accounting's: the two sources stacked.
                if rv.get("life_of_program") is not None:
                    life_old = float(rv["life_of_program"])
                    rv["life_of_program"] = round(life_old - old_ytd + ytd["amount"])      # whole dollars, as the sheet carries it
    as_of = datetime.date.fromtimestamp(p.stat().st_mtime)
    bm["_file"] = {"name": FILENAME, "as_of": as_of.isoformat(), "from": fm[0], "through": fm[-1],
                   "vip_last": vip_last, "replaced": replaced, "doubled": doubled, "ytd_year": ytd_year,
                   "life_of_program": rv.get("life_of_program") if ytd_year else None}
    return bm["_file"]


def source_sentence(info):
    """The sentence the Revenue by Month notes carry about where the months came from."""
    if not info:
        return "VIP MRPC Revenue by Month"
    return (f"VIP MRPC Revenue by Month through {info['vip_last']}, then {info['from']} to {info['through']} from "
            f"{info['name']} (Accounting, {info['as_of']})")


def doubled_sentence(info):
    """Months stated as the workbook gives them although they sit at about twice a normal month."""
    out = [f"{d['month']} (${d['value']:,.0f} against a median of ${d['median']:,.0f})"
           for d in (info or {}).get("doubled", [])]
    if not out:
        return ""
    return (" " + ", ".join(out) + (" is" if len(out) == 1 else " are")
            + " shown as the workbook states it; the month carries about twice a normal month's revenue.")
