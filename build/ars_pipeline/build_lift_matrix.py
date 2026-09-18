#!/usr/bin/env python3
"""
build_lift_matrix.py — standalone ARS Lift Matrix workbook (the file sent to
Bradford for input into the system).

Method
------
  * Segments are assigned on each account's AVERAGE SWIPES PER MONTH over the
    last 12 months of data (not the workbook's 3-month legend).
  * Segment values reflect the last 12 months of swipe/spend and NSF/OD activity.
  * Segment value ("DDA Value") = interchange + NSF/OD, per account per month:
        interchange = <Interchange Rate> x average monthly debit purchases
        NSF/OD      = <NSF Fee> x average monthly NSF/OD items x <collection>
    Rates come from the client workbook's `Actuals MM` tab (Key Assumptions);
    60 BP is the default interchange rate when a client carries none.
  * Outlier handling is selectable (--trim): none / winsorize / exclude, since
    excluding the top 5% removes ~30% of spend but ~75% of NSF items.
  * Population = card holders that are ARS eligible, reconciled to the DCO.
  * NH carries NU's DDA value at 0 distribution.
  * The lift matrix is purely differences of the DDA vector:
        cell(baseline, current) = DDA[current] - DDA[baseline]

Sanity check
------------
Weighted average spend and NSF/OD items are compared against the client
workbook's `Usage Summary MM` values ("Avg Spend per Account", "Average: NSFs
per Acct (w/card)"). Reported on the Source sheet and to stdout — a large
divergence means the population or window is wrong.

Formatting follows templates/STYLE.md: navy header rows, white grid lines,
alternating white / light-gray data rows, Calibri cells.
"""
import argparse
import pickle

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

SEGMENTS = ["NU", "1-5", "6-10", "11-15", "16-20", "21-25", "26 Plus"]
BASELINES = SEGMENTS[:-2]        # NU .. 16-20 (upper triangle)
CURRENTS = SEGMENTS[1:]          # 1-5 .. 26 Plus
DEFAULT_RATE = 0.0060            # 60 BP

# STYLE.md palette
NAVY = "FF00274C"
ORANGE = "FFF47A29"
ROWALT = "FFEEF2F7"
WHITE = "FFFFFFFF"
from brand import BODY

_navy_fill = PatternFill("solid", fgColor=NAVY)
_alt_fill = PatternFill("solid", fgColor=ROWALT)
_white_fill = PatternFill("solid", fgColor=WHITE)
_grid = Border(*[Side(style="thin", color=WHITE)] * 4)


def segment(avg_swipes_per_month):
    a = avg_swipes_per_month
    if a < 1:
        return "NU"
    if a < 6:
        return "1-5"
    if a < 11:
        return "6-10"
    if a < 16:
        return "11-15"
    if a < 21:
        return "16-20"
    if a < 26:
        return "21-25"
    return "26 Plus"


def _pct(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def compute(recs, rate, nsf_fee, collection=1.0, trim="none", pct=0.05,
            top_band=5):
    """trim: none | winsorize (cap at the 1-pct percentile) | exclude.

    top_band: value the open-ended top segment (26 Plus) on the swipe band
    [26, 26+top_band) so it carries the same 5-swipe width as every other
    segment. Left open-ended, 26 Plus spans the whole right tail (Marine:
    26 to 455 swipes/month, median 53.6) and its mean runs ~4.7x the prior
    step. Distribution still counts EVERY account in the segment; only the
    valuation basis is bounded. 0 disables.
    """
    from odd_rows import has_debit, is_eligible     # the one reading of the flag columns
    pop = [r for r in recs if has_debit(r["Debit?"]) and is_eligible(r["elig"])]
    n = len(pop)
    if not n:
        raise SystemExit("ERROR: empty eligible card-holding population")
    if "items12" not in pop[0]:
        # `fee12` was renamed to `items12` on 2026-09-01 (it was always the MTD
        # ITEM COUNT, never fee income). Fail loudly rather than KeyError deep
        # in the valuation.
        raise SystemExit("ERROR: this .pkl predates the fee12 -> items12 rename; "
                         "regenerate it with lift_extract.py")

    spend = {id(r): r["spend12"] for r in pop}
    items = {id(r): r["items12"] for r in pop}
    excluded = set()
    diag = {"population": n, "trim": trim, "trim_pct": pct,
            "collection": collection, "excluded": 0, "cap_spend": None,
            "cap_items": None}

    if trim == "exclude":
        k = int(round(n * pct))
        excluded = ({id(r) for r in sorted(pop, key=lambda r: -r["spend12"])[:k]}
                    | {id(r) for r in sorted(pop, key=lambda r: -r["items12"])[:k]})
        diag["excluded"] = len(excluded)
    elif trim == "winsorize":
        cs = _pct(sorted(spend.values()), 1 - pct)
        ci = _pct(sorted(items.values()), 1 - pct)
        diag["cap_spend"], diag["cap_items"] = cs, ci
        spend = {k_: min(v, cs) for k_, v in spend.items()}
        items = {k_: min(v, ci) for k_, v in items.items()}

    diag["top_band"] = top_band
    seg = {}
    for s in SEGMENTS:
        members = [r for r in pop if segment(r["swipes12"]) == s]
        valued = [r for r in members if id(r) not in excluded]
        if s == SEGMENTS[-1] and top_band:
            banded = [r for r in valued if r["swipes12"] < 26 + top_band]
            if banded:
                diag["top_band_n"] = len(banded)
                valued = banded
        if valued:
            sp = sum(spend[id(r)] for r in valued) / len(valued)
            it = sum(items[id(r)] for r in valued) / len(valued)
        else:
            sp = it = 0.0
        seg[s] = {"dist": len(members) / n, "n": len(members),
                  "n_valued": len(valued), "spend": sp, "items": it,
                  "interchange": rate * sp, "nsf": nsf_fee * it * collection,
                  "dda": rate * sp + nsf_fee * it * collection}

    # The workbook check reconciles the EXTRACTION against the book, so it is
    # computed on the full population — before the top-segment band and before
    # any trim. Otherwise the band (which covers ~40% of accounts) drags it down
    # and the check stops meaning anything.
    diag["wavg_spend"] = sum(r["spend12"] for r in pop) / n
    diag["wavg_items"] = sum(r["items12"] for r in pop) / n
    return seg, diag


def workbook_averages(path):
    """Read Avg Spend per Account / Avg NSFs per Acct (w/card) from the book."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if "Usage Summary MM" not in wb.sheetnames:
        wb.close()
        return {}
    ws = wb["Usage Summary MM"]
    out = {}
    for r in range(1, 60):
        for c in range(2, 12):
            v = ws.cell(r, c).value
            if not isinstance(v, str):
                continue
            nxt = ws.cell(r, c + 1).value
            if not isinstance(nxt, (int, float)):
                continue
            if v.strip().startswith("Avg Spend per Account"):
                out["spend"] = float(nxt)
            elif "NSFs per Acct" in v and "w/card" in v.replace(" ", ""):
                out["items"] = float(nxt)
            elif v.strip().startswith("Avg NSFs per Acct w/ Card"):
                out.setdefault("items", float(nxt))
    wb.close()
    return out


def _style_header(ws, row, ncols):
    for j in range(1, ncols + 1):
        c = ws.cell(row, j)
        c.fill = _navy_fill
        c.font = Font(name=BODY, bold=True, color=WHITE)
        c.border = _grid
        c.alignment = Alignment(horizontal="center" if j > 1 else "left",
                                vertical="center")


def _style_rows(ws, r0, r1, ncols):
    for i, r in enumerate(range(r0, r1 + 1)):
        fill = _alt_fill if i % 2 == 0 else _white_fill
        for j in range(1, ncols + 1):
            c = ws.cell(r, j)
            c.fill = fill
            c.font = Font(name=BODY, bold=(j == 1), color=NAVY)
            c.border = _grid
            c.alignment = Alignment(horizontal="left" if j == 1 else "right",
                                    vertical="center")
            if j > 1 and isinstance(c.value, (int, float)):
                c.number_format = ('0.0000' if ws.cell(4, j).value == "Distribution"
                                   else '0.00')


def build(seg, diag, meta, cid, name, rate, nsf_fee, period, out, book=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    title_font = Font(name=BODY, bold=True, color=NAVY, size=12)

    ws["A1"] = "Interchange and NSF"
    ws["A2"] = "Revenue Segmentation"
    ws["A1"].font = title_font
    ws["A2"].font = title_font

    ws["A4"], ws["B4"], ws["C4"] = "Segments", "Distribution", "DDA Value"
    rows = [("NH", 0, seg["NU"]["dda"])]
    rows += [(s, seg[s]["dist"], seg[s]["dda"]) for s in SEGMENTS]
    for i, (label, dist, dda) in enumerate(rows, start=5):
        ws.cell(i, 1, label)
        ws.cell(i, 2, dist)
        ws.cell(i, 3, dda)
    _style_header(ws, 4, 3)
    _style_rows(ws, 5, 12, 3)

    ws["A16"] = "Monthly Incremental Revenue Lift"
    ws["A16"].font = title_font
    ws.cell(18, 1, "Baseline Segment")
    for j, cur in enumerate(CURRENTS, start=2):
        ws.cell(18, j, cur)
    for i, base in enumerate(BASELINES, start=19):
        ws.cell(i, 1, base)
        bi = SEGMENTS.index(base)
        for j, cur in enumerate(CURRENTS, start=2):
            if SEGMENTS.index(cur) > bi:
                ws.cell(i, j, seg[cur]["dda"] - seg[base]["dda"])
    _style_header(ws, 18, 7)
    _style_rows(ws, 19, 23, 7)

    ws.column_dimensions["A"].width = 20
    for col in "BCDEFG":
        ws.column_dimensions[col].width = 13

    wb.save(out)
    return out


def _provenance_disabled(wb, seg, diag, meta, cid, name, rate, nsf_fee, period,
                         book):
    """Retained for reference only — NOT written.

    Aaron, 2026-08-17: the Excel file carries only the segments, values,
    distribution and the lift chart. Method notes and a copy of the values
    live in Obsidian (Work/ARS), not in the workbook Bradford ingests.
    """
    src = wb.create_sheet("Source")
    vw = meta["val_window"]
    chk = []
    if book:
        if book.get("spend"):
            chk.append(("Workbook avg spend/account", book["spend"]))
            chk.append(("  computed / workbook",
                        f"{diag['wavg_spend']/book['spend']:.1%}"))
        if book.get("items"):
            chk.append(("Workbook avg NSF items/account", book["items"]))
            chk.append(("  computed / workbook",
                        f"{diag['wavg_items']/book['items']:.1%}"))
    lines = [
        ("Client", f"{cid} - {name}"),
        ("Period", period),
        ("ODD extract", meta["source_file"]),
        ("Value window", f"{vw[0]} - {vw[-1]} ({len(vw)} months)"),
        ("Segment basis", "Average swipes per month over the value window"),
        ("", ""),
        ("Interchange rate", rate),
        ("NSF fee per item", nsf_fee),
        ("NSF/OD collection rate", diag["collection"]),
        ("Rate source", "Workbook 'Actuals MM' tab, Key Assumptions"),
        ("Outlier handling", f"{diag['trim']}"
                             + (f" @ {diag['trim_pct']:.0%}"
                                if diag["trim"] != "none" else "")),
        ("  accounts excluded", diag["excluded"]),
        ("  spend cap", diag["cap_spend"]),
        ("  NSF item cap", diag["cap_items"]),
        ("Top-segment valuation band",
         (f"26 - {26 + diag['top_band'] - 0.1:.1f} swipes/mo "
          f"({diag.get('top_band_n', 0):,} accounts valued)")
         if diag.get("top_band") else "open-ended (all 26+ accounts)"),
        ("  why", "26 Plus is the only open-ended segment; valuing it on the "
                  "same 5-swipe width as the others prevents runaway. "
                  "Distribution still counts every 26+ account."),
        ("", ""),
        ("DDA Value", "interchange + NSF/OD per account per month"),
        ("  interchange", "rate x avg monthly debit purchases (Sig $ + PIN $)"),
        ("  NSF/OD", "NSF fee x avg monthly NSF/OD items x collection rate"),
        ("Lift matrix", "DDA[current segment] - DDA[baseline segment]"),
        ("NH", "carries NU's DDA value at 0 distribution"),
        ("", ""),
        ("Population", "card holders that are ARS eligible "
                       "(Debit? = Yes and Elig = Yes)"),
        ("  accounts", diag["population"]),
        ("", ""),
        ("CHECK vs workbook", "weighted averages should track the book"),
        ("Computed avg spend/account", diag["wavg_spend"]),
        ("Computed avg NSF items/account", diag["wavg_items"]),
    ] + chk + [("", ""), ("Segment detail", "")]

    for i, (k, v) in enumerate(lines, start=1):
        src.cell(i, 1, k)
        src.cell(i, 2, v)
    r0 = len(lines) + 1
    hdr = ["Segment", "n accounts", "n valued", "avg spend/mo",
           "avg NSF-OD items/mo", "interchange $", "NSF $", "DDA Value"]
    for j, h in enumerate(hdr, start=1):
        src.cell(r0, j, h)
    _style_header(src, r0, len(hdr))
    for i, s in enumerate(SEGMENTS, start=r0 + 1):
        d = seg[s]
        for j, v in enumerate([s, d["n"], d["n_valued"], d["spend"], d["items"],
                               d["interchange"], d["nsf"], d["dda"]], start=1):
            src.cell(i, j, v)
    _style_rows(src, r0 + 1, r0 + len(SEGMENTS), len(hdr))
    src.column_dimensions["A"].width = 30
    src.column_dimensions["B"].width = 46
    for col in "CDEFGH":
        src.column_dimensions[col].width = 17

    wb.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pkl")
    ap.add_argument("client_id")
    ap.add_argument("client_name")
    ap.add_argument("rate", type=float)
    ap.add_argument("nsf_fee", type=float)
    ap.add_argument("period")
    ap.add_argument("out")
    ap.add_argument("--collection", type=float, default=1.0)
    ap.add_argument("--trim", choices=("none", "winsorize", "exclude"),
                    default="none")
    ap.add_argument("--trim-pct", type=float, default=0.05)
    ap.add_argument("--top-band", type=int, default=5,
                    help="swipe width used to value the open-ended top "
                         "segment (0 = open-ended)")
    ap.add_argument("--workbook", default=None,
                    help="client workbook, for the average-value check")
    a = ap.parse_args()

    rate = a.rate or DEFAULT_RATE
    meta, recs = pickle.load(open(a.pkl, "rb"))
    seg, diag = compute(recs, rate, a.nsf_fee, a.collection, a.trim,
                        a.trim_pct, a.top_band)
    book = workbook_averages(a.workbook) if a.workbook else {}
    build(seg, diag, meta, a.client_id, a.client_name, rate, a.nsf_fee,
          a.period, a.out, book)

    print(f"wrote {a.out}")
    print(f"  trim={diag['trim']} collection={diag['collection']:.0%} "
          f"population={diag['population']:,}")
    if book:
        sp = (f"{diag['wavg_spend']/book['spend']:.0%}"
              if book.get("spend") else "n/a")
        it = (f"{diag['wavg_items']/book['items']:.0%}"
              if book.get("items") else "n/a")
        print(f"  CHECK vs workbook — spend {diag['wavg_spend']:.2f} vs "
              f"{book.get('spend')} ({sp}) | NSF items "
              f"{diag['wavg_items']:.3f} vs {book.get('items')} ({it})")
    for s in SEGMENTS:
        d = seg[s]
        print(f"    {s:9} dist {d['dist']:.4f}  DDA {d['dda']:8.2f}"
              f"  (IC {d['interchange']:6.2f} + NSF {d['nsf']:5.2f})")


if __name__ == "__main__":
    main()
