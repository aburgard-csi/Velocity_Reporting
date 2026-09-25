#!/usr/bin/env python3
"""
lift_values.py — a client's ARS Lift Matrix, valued from their own ODD. One definition.

Aaron, 2026-09-25: "add functionality to Sheila to build client Lift Matrix for ARS. To do
this we need to value accounts by their swipe tiers. Value only based on consumer accounts.
We need to prevent outliers from overly affecting the calculation, and we'll need to use the
client's OD fee and blended interchange rate."

THE METHOD

  Population   every ARS-eligible account (`<latest> Elig` = Yes) that holds a debit card
               (Debit? = Yes), consumer AND business (Aaron, 2026-09-25: "change the calculate to
               include business accounts, but base the calculation only on ARS eligible
               accounts" — it was consumer only). Eligibility is the only account filter.
               The card is kept on purpose: the segments are swipe tiers of card holders, and
               counting eligible accounts with no card put them all in NU — on 2026.09 1705 and
               1539 NU rose from 16% / 23% to 27% / 30% against the workbooks' 15% / 23%, while
               adding the eligible business card holders (135 and 921 accounts) kept every
               segment within a point of the workbook's distribution. The counts record how many
               valued accounts are consumer, business, and neither (a blank Business?).
  Window       the last VAL_MONTHS months of the extract that are COMPLETE in every activity
               measure (month_complete.odd_completeness 'all' — swipes, spend, NSF/OD items).
               A half-loaded month would drag every segment's value down.
  Segment      the account's mean swipes per month (Sig # + PIN #) over the window, ROUNDED
               DOWN into its band (Aaron, 2026-09-22, the same rule as the deck's swipe tiers):
               NU (0), 1-5, 6-10, 11-15, 16-20, 21-25, 26 Plus.
  Outliers     each account's mean monthly spend and mean monthly NSF/OD items are capped at
               the WINSOR_PCT percentile OF ITS OWN SEGMENT before the segment mean is taken.
               Per segment because a book-wide cap would flatten the top segments into one
               value; capped rather than dropped because the heavy NSF/OD users are real
               revenue (dropping the top 5% of accounts removes ~75% of NSF/OD items). The
               99th, not the 95th: NSF/OD items sit on few accounts, and on 2026.09 1539 and
               1705 a 95th-percentile cap took 26-48% off each segment's items where the 99th
               takes 2-13% (spend: 1-4%) — the tail, not the revenue.
               The open-ended 26 Plus segment is valued on its first TOP_BAND swipes (26-30)
               so it steps like every other segment instead of carrying the whole right tail
               (Marine: 26 to 455 swipes/month). Distribution still counts every account.
  DDA Value    per account per month, for a segment:
                   interchange  = IC rate x mean monthly debit spend (Sig $ + PIN $)
                   NSF/OD       = NSF/OD fee x mean monthly NSF/OD items (MTD) x collection rate
               NH is valued on its OWN accounts (Aaron, 2026-09-25: "with the ODD we should be able
               to calculate an independent NH value"): the eligible accounts with NO debit card,
               their own spend and NSF/OD items, under the same outlier cap. It carries 0
               distribution in the file, as Bradford's does, because the distribution is of card
               holders. It used to carry NU's value; the workbooks already differ (1204: NH $0.84,
               NU $1.55). Only a client with no eligible card-less account falls back to NU's value,
               and says so. Values are rounded to the cent and the
               matrix is the difference of the rounded values, as in the file Bradford loads:
                   cell(baseline, current) = DDA[current] - DDA[baseline]

THE RATES — all three are editable in Sheila; these are the defaults it offers.

  IC rate      the client workbook's 'Interchange Rate' (Actuals MM, Key Assumptions, newest
               month), else DEFAULT_IC_RATE (60 BP).
  NSF/OD fee   from the ODD when it carries the fee (Aaron: "The NSF/OD fee column is typically
               Fees1"): each eligible account-month with fees and items gives fee / items, and
               the MOST COMMON per-item value wins — a client with tiered or several OD fees is
               valued at the one most items are charged. Without a fee column the value comes
               from the monthly OD item counters (MTD) times the workbook's 'NSF Fee'. With
               neither, there is no default: Sheila asks for it.
  Collection   DEFAULT_COLLECTION (100%) of NSF/OD fees charged are collected (Aaron, 2026-09-25:
               "default the collection rate to 100%"; it was 80%). Editable in Sheila.

`scan()` reads the ODD once and returns only segment-level figures (never member rows), so the
rates can change without re-reading the extract; `values()` applies them. IMPORT-SAFE: nothing
here runs at import.
"""
from __future__ import annotations

import csv
import math
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEGMENTS = ["NU", "1-5", "6-10", "11-15", "16-20", "21-25", "26 Plus"]
# NH (no debit card) is valued too but holds no share of the distribution, which is of card holders.
ALL_SEGMENTS = ["NH"] + SEGMENTS
BASELINES = SEGMENTS[:-2]          # NU .. 16-20, the rows of the file Bradford loads
CURRENTS = SEGMENTS[1:]            # 1-5 .. 26 Plus, its columns
VAL_MONTHS = 12
WINSOR_PCT = 0.99                  # the outlier cap: each segment's 99th percentile (the default)
# The caps Sheila offers (Aaron, 2026-09-25: "Add the 99% percentile option as a variable at the top").
# scan() values every segment at each of them, so choosing one never re-reads the ODD and no
# account-level figure is kept. 1.0 is no cap.
WINSOR_OPTIONS = (0.95, 0.975, 0.98, 0.99, 0.995, 1.0)
TOP_BAND = 5
DEFAULT_IC_RATE = 0.0060           # 60 BP
DEFAULT_COLLECTION = 1.00
FEE_BOUNDS = (1.0, 100.0)          # a per-item fee outside this is not an OD fee
WORKBOOK_VERSION = 1              # bump when read_workbook()'s output changes, so stored reads are redone
SCAN_VERSION = 4                   # bump when scan()'s output changes, so caches are re-read

_MONTH_RX = re.compile(r"^([A-Z][a-z]{2}\d{2}) Sig #$")
_FEE_RX = re.compile(r"^(?:([A-Z][a-z]{2}\d{2})\s+)?fees\s*1$", re.I)


def segment(mean_swipes):
    """Band for a mean monthly swipe count, rounded DOWN first (5.5 swipes is a 5-swipe account)."""
    s = math.floor(mean_swipes)
    if s < 1:
        return "NU"
    if s <= 5:
        return "1-5"
    if s <= 10:
        return "6-10"
    if s <= 15:
        return "11-15"
    if s <= 20:
        return "16-20"
    if s <= 25:
        return "21-25"
    return "26 Plus"


def fee_columns(hdr, months):
    """{month token: column index} for the NSF/OD fee columns, or {None: index} for one undated
    column (read against the newest month's items). {} when the extract carries no fee."""
    out = {}
    for i, h in enumerate(hdr):
        m = _FEE_RX.match(h.strip())
        if m:
            out[m.group(1)] = i
    if None in out and len(out) > 1:
        del out[None]              # dated columns win over an undated one
    return {k: v for k, v in out.items() if k is None or k in months}


def _pctile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    return sorted_vals[min(len(sorted_vals) - 1, max(0, int(math.ceil(q * len(sorted_vals))) - 1))]


def open_source(src):
    """(factory, member name): `factory()` yields a fresh text stream over the ODD csv, from a .zip or a .csv.

    Some ODDD zips also carry the raw monthly transaction file, itself sometimes a .csv, so the ODD
    extract is picked by name ('-ODD' / '_V2_') before falling back to the largest .csv. NUL bytes are
    dropped: a few cores pad fields with them and csv refuses the line."""
    import io
    import zipfile
    if src.lower().endswith(".zip"):
        zf = zipfile.ZipFile(src)
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise SystemExit(f"ERROR: no .csv inside {src}")
        odd = [n for n in members if "-odd" in n.lower() or "_v2_" in n.lower()]
        member = odd[0] if odd else max(members, key=lambda n: zf.getinfo(n).file_size)

        def factory():
            raw = io.TextIOWrapper(zf.open(member), encoding="utf-8", errors="replace", newline="")
            return (line.replace("\0", "") for line in raw)
        return factory, os.path.basename(member)

    def factory():
        raw = open(src, encoding="utf-8", errors="replace", newline="")
        return (line.replace("\0", "") for line in raw)
    return factory, os.path.basename(src)


def find_header(factory):
    """(row index, header) — the ODD carries preamble rows; the real header is the 'Acct ID' row."""
    for i, row in enumerate(csv.reader(factory())):
        if any(str(c).strip() == "Acct ID" for c in row):
            return i, [str(c).strip() for c in row]
        if i > 25:
            break
    raise SystemExit("ERROR: could not locate the 'Acct ID' header row")


def _rows(factory, hdr_idx, ncol):
    rd = csv.reader(factory())
    for _ in range(hdr_idx + 1):
        next(rd, None)
    for row in rd:
        if len(row) >= ncol:
            yield row


def scan(odd_path, val_months=VAL_MONTHS, winsor=WINSOR_PCT, top_band=TOP_BAND):
    """Segment-level figures from one ODD extract (.zip or .csv). JSON-safe; no member data."""
    import month_complete as MC
    from odd_rows import accessors

    factory, member = open_source(odd_path)
    hdr_idx, hdr = find_header(factory)
    H = {h: i for i, h in enumerate(hdr)}
    months = [m.group(1) for m in (_MONTH_RX.match(h) for h in hdr) if m]
    odd = accessors(H)
    ncol = len(hdr)

    comp = MC.odd_completeness(_rows(factory, hdr_idx, ncol), odd, months, MC.pull_date(member))
    usable = months[:comp["all"]["complete"]]
    if len(usable) < 3:
        raise SystemExit(f"POSSIBLE DATA ISSUE: {member} has {len(usable)} complete months; "
                         f"a Lift Matrix needs at least 3.")
    win = usable[-val_months:]
    n = len(win)
    latest = months[-1]
    elig_i = H.get(f"{latest} Elig")
    if elig_i is None:
        raise SystemExit(f"POSSIBLE DATA ISSUE: {member} carries no '{latest} Elig' column.")
    # Dated fee columns are read in the value window; one undated column belongs to the newest month.
    fees = fee_columns(hdr, months)
    fee_pairs = ([(latest, fees[None])] if None in fees
                 else [(m, i) for m, i in fees.items() if m in win])

    per = {s: [] for s in ALL_SEGMENTS}      # (mean swipes, spend, items) per account, per segment
    fee_seen = Counter()
    counts = Counter()
    for r in _rows(factory, hdr_idx, ncol):
        counts["rows"] += 1
        if r[elig_i].strip() != "Yes":
            counts["not eligible"] += 1
            continue
        # The fee is read on every eligible account, card or not: it is the account's OD fee.
        for m, i in fee_pairs:
            items = odd.nsf(r, m)
            if items > 0:
                v = odd.fnum(r, hdr[i])
                if v > 0:
                    unit = round(v / items, 2)
                    if FEE_BOUNDS[0] <= unit <= FEE_BOUNDS[1]:
                        fee_seen[unit] += items
        sw = sum(odd.swipes(r, m) for m in win) / n
        sp = sum(odd.spend(r, m) for m in win) / n
        it = sum(odd.nsf(r, m) for m in win) / n
        if not odd.hascard(r):
            counts["no card"] += 1
            per["NH"].append((sw, sp, it))
            continue
        counts["business" if odd.business(r) else "consumer" if odd.personal(r) else "business? blank"] += 1
        per[segment(sw)].append((sw, sp, it))

    pop = sum(len(per[s]) for s in SEGMENTS)
    if not pop:
        raise SystemExit(f"POSSIBLE DATA ISSUE: {member} has no card-holding, ARS-eligible account.")
    caps = sorted(set(WINSOR_OPTIONS) | {winsor})
    by_cap = {cap_key(p): {} for p in caps}
    for s in ALL_SEGMENTS:
        accts = per[s]
        valued = accts
        if s == SEGMENTS[-1] and top_band:
            banded = [a for a in accts if math.floor(a[0]) < 26 + top_band]
            valued = banded or accts
        sp = sorted(a[1] for a in valued)
        it = sorted(a[2] for a in valued)
        k = len(valued)
        base = {"n": len(accts), "n_valued": k, "dist": 0.0 if s == "NH" else len(accts) / pop,
                "spend_raw": sum(sp) / k if k else 0.0, "items_raw": sum(it) / k if k else 0.0}
        for p in caps:
            cap_sp, cap_it = _pctile(sp, p), _pctile(it, p)
            by_cap[cap_key(p)][s] = dict(
                base, cap_spend=cap_sp, cap_items=cap_it,
                spend=sum(min(v, cap_sp) for v in sp) / k if k else 0.0,
                items=sum(min(v, cap_it) for v in it) / k if k else 0.0)
    seg = by_cap[cap_key(winsor)]

    total_items = sum(fee_seen.values())
    fee = None
    if fee_pairs:
        top = fee_seen.most_common(5)
        fee = {"columns": [hdr[i] for _, i in fee_pairs],
               "value": top[0][0] if top else None,
               "items": total_items,
               "values": [{"fee": v, "share": c / total_items} for v, c in top] if total_items else []}
    return {
        "version": SCAN_VERSION,
        "source_file": member,
        "pull_date": (MC.pull_date(member).isoformat() if MC.pull_date(member) else None),
        "window": win, "window_label": f"{MC.label(win[0])} - {MC.label(win[-1])}",
        "excluded_months": MC.excluded_sentence(comp["all"]),
        "population": pop, "counts": dict(counts),
        "winsor_pct": winsor, "top_band": top_band,
        "segments": seg, "by_cap": by_cap, "fee": fee,
    }


def read_workbook(path):
    """{'assumptions': workbook_assumptions, 'matrix': workbook_matrix} from ONE open of the file —
    opening a workbook over the share takes 0.4-2 s."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return {"assumptions": _assumptions(wb), "matrix": _matrix(wb)}
    finally:
        wb.close()


def workbook_assumptions(path):
    """{'ic_rate', 'nsf_fee', 'sheet'} from a client workbook's Key Assumptions, newest month.
    A value the workbook does not carry is None."""
    return read_workbook(path)["assumptions"]


def workbook_matrix(path):
    """The Lift Matrix a workbook currently carries (its Revenue Segmentation DDA values, window and
    data month), or None when it has no 'Lift Matrix MM' tab or the tab holds no values (SM workbooks)."""
    return read_workbook(path)["matrix"]


def _assumptions(wb):
    out = {"ic_rate": None, "nsf_fee": None, "sheet": None}
    for name in ("Actuals MM", "Actuals SM", "Actuals"):
        if name not in wb.sheetnames:
            continue
        for row in wb[name].iter_rows(min_row=1, max_row=80, max_col=80, values_only=True):
            label = next((v for v in row[:4] if isinstance(v, str)), "")
            key = {"interchange rate": "ic_rate", "nsf fee": "nsf_fee"}.get(label.strip().lower())
            if not key or out[key] is not None:
                continue
            # One column per month, oldest first: the newest month's assumption is the last number.
            nums = [v for v in row if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
            if nums:
                out[key] = float(nums[-1])
        if out["ic_rate"] is not None or out["nsf_fee"] is not None:
            out["sheet"] = name
            break
    return out


class _Grid:
    """A sheet's top-left values, readable as ws.cell(r, c).value (what lift_window reads)."""
    class _C:
        def __init__(self, v):
            self.value = v

    def __init__(self, rows):
        self.rows = rows

    def cell(self, r, c):
        row = self.rows[r - 1] if 0 < r <= len(self.rows) else ()
        return self._C(row[c - 1] if 0 < c <= len(row) else None)


def _matrix(wb):
    from lift_window import SHEET, header_row, window
    if SHEET not in wb.sheetnames:
        return None
    rows = [list(r) for r in wb[SHEET].iter_rows(min_row=1, max_row=40, max_col=16, values_only=True)]
    g = _Grid(rows)
    hdr = header_row(g)
    out = window(g, hdr)
    # The lift grid the workbook carries now, as written (not re-derived from its DDA values):
    # 'Baseline Segment' in column B, the current segments across, a baseline per row below.
    grid = {}
    if hdr:
        cols = [str(g.cell(hdr, c).value or "").strip() for c in range(3, 9)]
        cols = ["26 Plus" if c.lower() in ("26+", "25+", "26 plus") else c for c in cols]
        for r in range(hdr + 1, hdr + 8):
            base = g.cell(r, 2).value
            if not base:
                break
            grid[str(base).strip()] = {c: round(v, 2) for c, v in
                                       ((c, g.cell(r, j).value) for j, c in zip(range(3, 9), cols))
                                       if c and isinstance(v, (int, float))}
    out["grid"] = grid
    segs = {}
    for r in range(1, len(rows) + 1):
        c = next((c for c in range(1, 17) if g.cell(r, c).value == "Segments"), None)
        if c is None:
            continue
        for rr in range(r + 1, r + 12):
            name = g.cell(rr, c).value
            if not name:
                break
            name = str(name).strip()
            name = "26 Plus" if name.lower() in ("26+", "25+", "26 plus") else name
            dist, dda = g.cell(rr, c + 1).value, g.cell(rr, c + 2).value
            segs[name] = {"dist": dist if isinstance(dist, (int, float)) else None,
                          "dda": round(dda, 2) if isinstance(dda, (int, float)) else None}
        break
    out["segments"] = segs
    # An SM workbook can carry the template's empty 'Lift Matrix MM' tab: no values, no matrix.
    return out if any(v["dda"] for v in segs.values()) else None


def default_rates(scan_doc, assumptions):
    """The rates Sheila offers before anyone edits them, each with where it came from."""
    a = assumptions or {}
    fee = (scan_doc or {}).get("fee") or {}
    if a.get("ic_rate"):
        ic = (a["ic_rate"], f"workbook ({a.get('sheet')}, Interchange Rate)")
    else:
        ic = (DEFAULT_IC_RATE, "default 60 BP (the workbook carries no Interchange Rate)")
    if fee.get("value"):
        top = fee["values"][0]["share"] if fee.get("values") else 0
        nsf = (fee["value"], f"ODD {fee['columns'][0]}: most common per-item fee ({top:.0%} of items)")
    elif a.get("nsf_fee"):
        nsf = (a["nsf_fee"], f"workbook ({a.get('sheet')}, NSF Fee)")
    else:
        nsf = (None, "not in the ODD or the workbook: enter the client's NSF/OD fee")
    return {"ic_rate": ic[0], "ic_source": ic[1], "nsf_fee": nsf[0], "nsf_source": nsf[1],
            "collection": DEFAULT_COLLECTION, "collection_source": "default 100%",
            "winsor": WINSOR_PCT, "winsor_source": f"default {cap_label(WINSOR_PCT)} of each segment"}


def cap_key(p):
    """0.99 -> '0.99', 1.0 -> '1': the by_cap key for an outlier cap."""
    return f"{float(p):g}"


def cap_label(p):
    """0.99 -> '99th percentile', 1.0 -> 'no cap'."""
    p = float(p)
    return "no cap" if p >= 1 else f"{p * 100:g}th percentile"


def values(scan_doc, ic_rate, nsf_fee, collection, winsor=None):
    """{'segments': [{segment, dist, n, interchange, nsf, dda}], 'matrix': {baseline: {current: lift}}}.

    `winsor` picks one of the scan's outlier caps (WINSOR_OPTIONS); None is the scan's own default."""
    segs = scan_doc["segments"] if winsor is None else scan_doc["by_cap"][cap_key(winsor)]
    rows = []
    for s in ALL_SEGMENTS:
        # NH from its own accounts; NU's figures only when the client has no eligible card-less account.
        d = segs["NU"] if s == "NH" and not segs.get("NH", {}).get("n") else segs[s]
        ic = ic_rate * d["spend"]
        od = nsf_fee * d["items"] * collection
        rows.append({"segment": s, "dist": 0.0 if s == "NH" else d["dist"],
                     "n": segs.get(s, {}).get("n", 0), "interchange": ic, "nsf": od,
                     "dda": round(ic + od, 2), "from_nu": s == "NH" and d is segs["NU"]})
    dda = {r["segment"]: r["dda"] for r in rows}
    matrix = {b: {c: round(dda[c] - dda[b], 2) for c in CURRENTS
                  if SEGMENTS.index(c) > SEGMENTS.index(b)} for b in BASELINES}
    return {"segments": rows, "matrix": matrix}


def out_name(cid, period, client_name):
    """<id>-<yyyy.mm>-ARS-<Client Name> ARS Lift Matrix.xlsx — the deck naming convention."""
    safe = re.sub(r'[<>:"/\\|?*]', "", client_name).strip()
    return f"{cid}-{period}-ARS-{safe} ARS Lift Matrix.xlsx"


def write_xlsx(vals, out):
    """The file emailed to Bradford, in the layout his system loads (CoastLife CU Lift Matrix
    Values.xlsx): Revenue Segmentation (NH + seven segments) and the Monthly Incremental Revenue
    Lift triangle. Nothing else goes in it — method notes live in Sheila and the CHANGELOG."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    bold = Font(bold=True)
    money = '"$"#,##0.00_);[Red]\\("$"#,##0.00\\)'
    acct = '_("$"* #,##0.00_);_("$"* \\(#,##0.00\\);_("$"* "-"??_);_(@_)'

    def label(cell, text):
        ws[cell] = text
        ws[cell].font = bold
        ws[cell].number_format = "@"

    ws["A1"], ws["A2"] = "Interchange and NSF", "Revenue Segmentation"
    ws["A1"].font = ws["A2"].font = bold
    ws.merge_cells("A1:C1")
    ws.merge_cells("A2:C3")
    for c, t in zip("ABC", ("Segments", "Distribution", "DDA Value")):
        label(f"{c}4", t)
    seg = {r["segment"]: r for r in vals["segments"]}
    rows = [(s, seg[s]["dist"], seg[s]["dda"]) for s in ALL_SEGMENTS]
    for i, (name, dist, dda) in enumerate(rows, start=5):
        label(f"A{i}", name)
        ws[f"B{i}"], ws[f"C{i}"] = dist, dda
        ws[f"B{i}"].number_format = "0%"
        ws[f"C{i}"].number_format = money

    ws["A16"] = "Monthly Incremental Revenue Lift"
    ws["A16"].font = bold
    ws.merge_cells("A16:C17")
    ws.merge_cells("D16:G17")
    label("A18", "Baseline Segment")
    cols = "BCDEFG"
    for c, cur in zip(cols, CURRENTS):
        label(f"{c}18", cur)
    for i, base in enumerate(BASELINES, start=19):
        label(f"A{i}", base)
        for c, cur in zip(cols, CURRENTS):
            v = vals["matrix"][base].get(cur)
            if v is not None:
                ws[f"{c}{i}"] = v
            ws[f"{c}{i}"].number_format = acct     # the empty triangle too, as in Bradford's file
    for c, w in (("A", 19.71), ("B", 12.86), ("C", 11.57), ("D", 8.71)):
        ws.column_dimensions[c].width = w
    wb.save(out)
    return out
