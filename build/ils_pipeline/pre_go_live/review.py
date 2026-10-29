"""The Velocity PGL review's tables (RPE, 2026-10-28): the analysis the client deck is built on.

James Gilmore, 2026-10-28: "i want the analysis and insight from velocity", in Sheila's look. The tables
are the pivots of the Velocity PGL workbook (1616_PreGoLive_20251210-working.xlsx, sheets A-1 to A9 and
the two limit distributions), column for column, so a figure on a slide can be checked against the
same pivot a CSM would build by hand. Every table uses one row shape:

    label, # of accts, % of accts, # of NSF/OD items since import, % of items, # of paid items,
    pay ratio, average core limit, average ILS limit, average deposit count (33 days),
    average deposit $ (33 days), decline count, decline $

Bases, all with deleted-stamped rows out (the workbook's "Deleted = NULL" filter):
    live          every row                  A-1
    open          status in the confirmed open codes                 A-2
    open personal Personal_Business = PERSONAL                       A3
    eligible      open personal on a confirmed OD-eligible status   A4, limit tiers, A5, A6, A7
    open business / eligible business                                A8, A9, business limit tiers

Nothing is computed here that the codes did not decide: the CSM confirms them (the client confirms
nothing). Keys: pgl_review (the tables) and pgl_review_<table> with <table>_columns, so tables.py-style
writers can lay each one out as a CSV.
"""
from __future__ import annotations

import pandas as pd

ITEMS = "NSF OD Items since start date"
PAID = "Paid NSF OD Items since start date"
CORE = "Initial OD Limit (from Core)"
ILS = "OD Limit (from ILS)"
DEP_N = "Deposit Count Last 33 days"
DEP_D = "Deposit Amount Last 33 days"
DEC_N = "Debit Decline Count"
DEC_D = "Debit Decline Amount"
STATUS = "Account Status Code"
TYPE = "Personal_Business"
OD = "OD Status Code (from Core)"
REGE = "Reg-E Opt-In Value"
CHANGE = "UpOrDown from Initial OD Limit"
OPENED = "Open Date"

COLUMNS = ["group", "accounts", "pct_of_accounts", "items_since_import", "pct_of_items", "paid_items",
           "pay_ratio", "avg_core_limit", "avg_ils_limit", "avg_deposit_count_33d", "avg_deposit_dollars_33d",
           "decline_count", "decline_dollars", "median_deposit_dollars_33d"]
TIER_COLUMNS = ["ils_limit_tier", "accounts", "pct_of_accounts", "avg_deposit_dollars_33d", "median_deposit_dollars_33d"]
YEAR_COLUMNS = ["opened", "rege_y", "rege_n", "rege_blank", "accounts", "opt_in_rate"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _num(df, col):
    return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(dtype=float, index=df.index)


def _mean(s):
    s = s.dropna()
    return round(float(s.mean()), 2) if len(s) else None


def _median(s):
    s = s.dropna()
    return round(float(s.median()), 2) if len(s) else None


def _row(label, g, base_n, base_items):
    items, paid = float(_num(g, ITEMS).sum()), float(_num(g, PAID).sum())
    base_items = float(base_items)
    n = len(g)
    return [label, n, round(n / base_n, 4) if base_n else None,
            int(items), round(items / base_items, 4) if base_items else None, int(paid),
            round(paid / items, 4) if items else None,
            _mean(_num(g, CORE)), _mean(_num(g, ILS)), _mean(_num(g, DEP_N)), _mean(_num(g, DEP_D)),
            int(_num(g, DEC_N).sum()), round(float(_num(g, DEC_D).sum()), 2), _median(_num(g, DEP_D))]


def _cut(df, by, order=None, blocks=None):
    """Rows by `by` (blank as "Blank"), largest first or in `order`; `blocks` puts subtotal rows first."""
    base_n, base_items = len(df), _num(df, ITEMS).sum()
    key = df[by].astype("string").str.strip().fillna("Blank").replace({"": "Blank"}) if by in df.columns \
        else pd.Series("Blank", index=df.index)
    if blocks:
        rows = []
        for name, members in blocks:
            sub = df[key.isin(members)]
            if not len(sub):
                continue
            rows.append(_row(name, sub, base_n, base_items))
            k = key[sub.index]
            rows += [_row("  " + v, sub[k == v], base_n, base_items) for v in k.value_counts().index]
    else:
        labels = order or list(key.value_counts().index)
        rows = [_row(v, df[key == v], base_n, base_items) for v in labels if (key == v).any()]
    return {"rows": rows, "total": _row("Grand Total", df, base_n, base_items), "base_n": base_n}


def _tiers(df, step):
    lim = _num(df, ILS)
    tier = (lim // step * step).where(lim.notna())
    n = len(df)
    rows = []
    for t in sorted(tier.dropna().unique()):
        g = df[tier == t]
        rows.append([int(t), len(g), round(len(g) / n, 4) if n else None, _mean(_num(g, DEP_D)),
                     _median(_num(g, DEP_D))])
    # $250 bands for the slide, each with the median of its own accounts (medians cannot be combined from tiers)
    bands = []
    top = float(lim.max()) if lim.notna().any() else 0.0
    edges = [(0, 0)] + [(lo, lo + BAND) for lo in range(0, int(top), BAND)]
    for lo, hi in edges:
        m = (lim == 0) if hi == 0 else (lim > lo) & (lim <= hi)
        g = df[m.fillna(False)]
        if len(g):
            bands.append([int(hi), int(lo), len(g), round(len(g) / n, 4) if n else None, _mean(_num(g, DEP_D)),
                          _median(_num(g, DEP_D))])
    return {"rows": rows, "total": ["Grand Total", n, 1.0 if n else None, _mean(_num(df, DEP_D)), _median(_num(df, DEP_D))],
            "base_n": n, "bands": bands,
            "step": step, "no_limit": int(lim.isna().sum())}


BAND = 250


def _by_year(df):
    """Reg E opt-in by the year opened (pre-2010 together), then each month of the newest year."""
    opened = pd.to_datetime(df[OPENED], errors="coerce") if OPENED in df.columns else pd.Series(pd.NaT, index=df.index)
    rege = df[REGE].astype("string").str.strip().fillna("Blank").replace({"": "Blank"}) if REGE in df.columns \
        else pd.Series("Blank", index=df.index)

    def line(label, mask):
        r = rege[mask]
        y, nn, b = int((r == "Y").sum()), int((r == "N").sum()), int((~r.isin(["Y", "N"])).sum())
        tot = int(mask.sum())
        return [label, y, nn, b, tot, round(y / tot, 4) if tot else None]

    years = opened.dt.year
    rows = []
    if (years < 2010).any():
        rows.append(line("Pre-2010", years < 2010))
    last = int(years.max()) if years.notna().any() else None
    for yr in range(2010, (last or 2009) + 1):
        if (years == yr).any():
            rows.append(line(str(yr), years == yr))
    if last:
        for i, mo in enumerate(MONTHS, 1):
            m = (years == last) & (opened.dt.month == i)
            if m.any():
                rows.append(line(f"{mo} {last}", m))
    return {"rows": rows, "total": line("Grand Total", pd.Series(True, index=df.index)), "base_n": len(df),
            "undated": int(opened.isna().sum())}


def compute(df, codes, sysv: dict | None = None) -> dict:
    """The review tables on the confirmed codes. `codes` has open_status, od_eligible (lists)."""
    sysv = sysv or {}
    live = df[df["Deleted"].isna()] if "Deleted" in df.columns else df
    up = lambda s: s.astype("string").str.strip().str.upper()
    open_codes = {str(c).upper() for c in (codes.get("open_status") or [])}
    od_codes = {str(c).upper() for c in (codes.get("od_eligible") or [])}
    is_open = up(live[STATUS]).isin(open_codes) if STATUS in live.columns else pd.Series(False, index=live.index)
    kind = up(live[TYPE]) if TYPE in live.columns else pd.Series("", index=live.index)
    od = up(live[OD]).fillna("") if OD in live.columns else pd.Series("", index=live.index)
    step = sysv.get("sysv_matrix_rounding_step") or 50
    try:
        step = float(step) or 50
    except (TypeError, ValueError):
        step = 50

    open_ = live[is_open]
    pers, biz = open_[kind[is_open] == "PERSONAL"], open_[kind[is_open] == "BUSINESS"]

    def eligible(base):
        return base[od[base.index].isin(od_codes)]

    def od_blocks(base):
        seen = list(od[base.index].replace({"": "BLANK"}).value_counts().index)
        return [("Eligible", [v for v in seen if v in od_codes]), ("Ineligible", [v for v in seen if v not in od_codes])]

    def od_cut(base):
        b = base.assign(**{OD: od[base.index].replace({"": "BLANK"})})
        return _cut(b, OD, blocks=od_blocks(base))

    ep, eb = eligible(pers), eligible(biz)
    t = {
        "status": dict(_cut(live, STATUS), title="Account status", base="all accounts (deleted out)"),
        "type": dict(_cut(open_, TYPE), title="Open accounts by type", base="all open accounts"),
        "personal_od": dict(od_cut(pers), title="Personal accounts by OD status", base="open personal accounts"),
        "personal_change": dict(_cut(ep, CHANGE), title="Change in score, personal",
                                base="open, eligible personal accounts"),
        "personal_tiers": dict(_tiers(ep, step), title="Proposed ILS limits, personal",
                               base="open, eligible personal accounts"),
        "rege_y_change": dict(_cut(ep[up(ep[REGE]) == "Y"] if REGE in ep.columns else ep.iloc[:0], CHANGE),
                              title="Change in score, Reg E opted in", base="open, eligible personal, Reg E Y"),
        "rege": dict(_cut(ep.assign(**{REGE: up(ep[REGE])}) if REGE in ep.columns else ep, REGE),
                     title="Reg E opt-in", base="open, eligible personal accounts"),
        "rege_by_year": dict(_by_year(ep), title="Reg E opt-in by year opened", base="open, eligible personal"),
        "business_od": dict(od_cut(biz), title="Business accounts by OD status", base="open business accounts"),
        "business_rege": dict(_cut(eb.assign(**{REGE: up(eb[REGE])}) if REGE in eb.columns else eb, REGE),
                              title="Reg E opt-in, business", base="open, eligible business accounts"),
        "business_change": dict(_cut(eb, CHANGE), title="Change in score, business",
                                base="open, eligible business accounts"),
        "business_tiers": dict(_tiers(eb, step), title="Proposed ILS limits, business",
                               base="open, eligible business accounts"),
    }
    out = {"pgl_review": t}
    for k, v in t.items():
        cols = TIER_COLUMNS if k.endswith("tiers") else YEAR_COLUMNS if k == "rege_by_year" else COLUMNS
        out[f"pgl_review_{k}"] = v["rows"] + [v["total"]]
        out[f"pgl_review_{k}_columns"] = cols
    return out
