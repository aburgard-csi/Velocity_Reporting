"""Opportunities and risks in the PGL extract (RPE, 2026-10-28): what the Velocity review adds after the tables.

James Gilmore, 2026-10-28: "i feel like the analysis is missing something ... if we have the PGL dataset, what
else can we do?", then "All of them". Each is computed on the confirmed codes from the account extract (and, for
the last two, the notice items), deleted-stamped rows out, and returned with its base named:

  declines        debit declines on open personal accounts, by Reg E and by proposed limit, and what paying a
                  share of the eligible accounts' declines would earn at the client's OD fee (a scenario: the
                  share paid is an assumption, shown as 10 / 20 / 30%, July's First Central deck used 30%)
  concentration   how much of the NSF/OD activity the heaviest accounts carry (top 1 / 5 / 10 / 20%), and the
                  YTD item buckets (the Heavy Usage Letter population)
  overrides       the ILS overrides on eligible accounts, and the deposit and repayment trending adjustments
  new_accounts    accounts opened in the last 90 days and 91-365 days: proposed limit, $0 share, Reg E
  second_chance   the Second Chance (and any other non-personal, non-business) account type, in the review shape
  days_od         open accounts by days overdrawn
  products        open accounts by product code, in the review shape
  revenue_check   the extract's Rolling 12 Month NSF/OD fees against the notice items' annualized fees
  by_type         the notice items by transaction type: paid, returned, fees, average item

Keys: pgl_insights.
"""
from __future__ import annotations

import re

import pandas as pd

from . import review as R

DAYS_OD = "Days OD"
BUCKET = "YTDODItemsBucket"
OVERRIDE = "OVERRIDE (from ILS)"
PRODUCT = "Product Code"
R12_ITEMS = "Rolling 12 Month NSFOD Items"
R12_FEES = "Rolling 12 Month NSFOD Fees"
TRENDS = ("DEPOSIT_TRENDING", "REPAYMENT_TRENDING", "WINDFALL_TRENDING")
CAPTURE = (0.10, 0.20, 0.30)
DAYS_BANDS = ((0, 0, "Not overdrawn"), (1, 9, "1–9 days"), (10, 19, "10–19 days"), (20, 29, "20–29 days"),
              (30, 44, "30–44 days"), (45, 10 ** 6, "45+ days"))
LIMIT_BANDS = ((0, 0, "$0"), (1, 250, "$1–$250"), (251, 500, "$251–$500"), (501, 1000, "$501–$1,000"),
               (1001, 10 ** 9, "Over $1,000"))


def _n(df, col):
    return pd.to_numeric(df[col], errors="coerce").fillna(0) if col in df.columns else pd.Series(0.0, index=df.index)


def _up(df, col):
    return df[col].astype("string").str.strip().str.upper().fillna("") if col in df.columns \
        else pd.Series("", index=df.index)


def _r(v, d=2):
    return None if v is None else round(float(v), d)


QUINTILES = ("Bottom fifth", "2nd fifth", "Middle fifth", "4th fifth", "Top fifth")
CMP_BANDS = ((-1, 0, "$0"), (0, 250, "$1–$250"), (250, 500, "$251–$500"), (500, 1000, "$501–$1,000"),
             (1000, 10 ** 9, "Over $1,000"))


def core_vs_ils(e):
    """How well each system's limit follows the account's deposits, on one base of accounts.

    The core's limit (Initial OD Limit from Core) against the limit ILS proposes (OD Limit from ILS): by deposit
    quintile, how closely each follows 33-day deposits (Pearson correlation), the limit sitting on accounts with
    no deposits, depositors held at the core's typical limit, where the returned items and declines are, and the
    move from core band to ILS band."""
    if not len(e):
        return {}
    core, ils, dep = _n(e, R.CORE), _n(e, R.ILS), _n(e, R.DEP_D)
    items, paid, dec = _n(e, R.ITEMS), _n(e, R.PAID), _n(e, R.DEC_N)
    quint = []
    # fewer than 5 accounts cannot be split into fifths (a small business base); the comparison still stands
    q = pd.qcut(dep.rank(method="first"), 5, labels=QUINTILES) if len(e) >= 5 else None
    for lbl in QUINTILES if q is not None else ():
        m = q == lbl
        quint.append([lbl, int(m.sum()), _r(dep[m].median()), _r(core[m].mean()), _r(ils[m].mean())])
    nodep = dep <= 0
    typical = float(core.mode().iloc[0]) if len(core.mode()) else 0.0
    strong = dep >= dep.median()
    held = strong & (core <= typical)
    ret = (items - paid).clip(lower=0)
    raised = ils > core
    cut = pd.cut
    cb = cut(core, [b[0] for b in CMP_BANDS] + [CMP_BANDS[-1][1]], labels=[b[2] for b in CMP_BANDS])
    ib = cut(ils, [b[0] for b in CMP_BANDS] + [CMP_BANDS[-1][1]], labels=[b[2] for b in CMP_BANDS])
    xt = pd.crosstab(cb, ib).reindex(index=[b[2] for b in CMP_BANDS], columns=[b[2] for b in CMP_BANDS], fill_value=0)
    corr = lambda a: _r(a.corr(dep), 3) if a.std() > 0 and dep.std() > 0 else None     # NaN std on one account
    return {"accounts": len(e), "quintiles": quint,
            "corr_core": corr(core), "corr_ils": corr(ils),
            "typical_core": typical, "typical_core_share": _r((core == typical).mean(), 4),
            "nodep_accounts": int(nodep.sum()),
            "nodep_core_dollars": _r(core[nodep].sum()), "nodep_core_accounts": int((core[nodep] > 0).sum()),
            "nodep_ils_dollars": _r(ils[nodep].sum()), "nodep_ils_accounts": int((ils[nodep] > 0).sum()),
            "deposit_median": _r(dep.median()), "held_accounts": int(held.sum()), "held_ils_avg": _r(ils[held].mean()),
            "returned": int(ret.sum()), "returned_raised": int(ret[raised].sum()),
            "declines": int(dec.sum()), "declines_raised": int(dec[raised].sum()),
            "core_total": _r(core.sum()), "ils_total": _r(ils.sum()),
            "matrix_bands": [b[2] for b in CMP_BANDS], "matrix": [[int(v) for v in row] for row in xt.values]}


def compute(df, codes, notices=None, od_fee=None, extract_date=None) -> dict:
    live = df[df["Deleted"].isna()] if "Deleted" in df.columns else df
    open_codes = {str(c).upper() for c in (codes.get("open_status") or [])}
    od_codes = {str(c).upper() for c in (codes.get("od_eligible") or [])}
    opn = live[_up(live, R.STATUS).isin(open_codes)]
    kind = _up(opn, R.TYPE)
    pers = opn[kind == "PERSONAL"]
    elig = pers[_up(pers, R.OD).isin(od_codes)]
    regy = _up(pers, R.REGE) == "Y"
    out = {}

    # ---- 1. debit declines -------------------------------------------------------------------------------
    dn, dd = _n(pers, R.DEC_N), _n(pers, R.DEC_D)
    lim = _n(pers, R.ILS)
    by_rege = [[lbl, int((dn[m] > 0).sum()), int(dn[m].sum()), _r(dd[m].sum())] for lbl, m in
               (("Opted in to Reg E", regy), ("Not opted in (N or blank)", ~regy))]
    by_limit = []
    for lo, hi, lbl in LIMIT_BANDS:
        m = (lim >= lo) & (lim <= hi)
        by_limit.append([lbl, int(m.sum()), int((dn[m] > 0).sum()), int(dn[m].sum()), _r(dd[m].sum())])
    e_dn = _n(elig, R.DEC_N)
    e_regy = _up(elig, R.REGE) == "Y"
    fee = od_fee
    scen = [[f"{int(c * 100)}% of declines paid", int(round(e_dn.sum() * c)),
             _r(e_dn.sum() * c * fee) if fee else None] for c in CAPTURE]
    out["declines"] = {
        "base": "open personal accounts", "accounts": len(pers), "with_declines": int((dn > 0).sum()),
        "declines": int(dn.sum()), "decline_dollars": _r(dd.sum()), "by_rege": by_rege, "by_limit": by_limit,
        "eligible_declines": int(e_dn.sum()), "od_fee": fee, "scenarios": scen,
        "rege_targets": int(((~e_regy) & (e_dn > 0)).sum()),
        "rege_target_declines": int(e_dn[~e_regy].sum()),
        "note": "the decline counts are the extract's Debit Decline Count; a paid decline is assumed to earn the "
                "client's OD fee; the share paid is a scenario, not a forecast"}

    # ---- 2. concentration ----------------------------------------------------------------------------------
    items, r12 = _n(opn, R.ITEMS), _n(opn, R12_FEES)
    ordered = pd.DataFrame({"i": items, "f": r12}).sort_values(["i", "f"], ascending=False)
    tops = []
    for share in (0.01, 0.05, 0.10, 0.20):
        k = max(1, int(round(len(ordered) * share)))
        tops.append([f"Top {int(share * 100)}%", k, _r(ordered["i"].head(k).sum() / items.sum(), 4) if items.sum() else None,
                     _r(ordered.sort_values("f", ascending=False)["f"].head(k).sum() / r12.sum(), 4) if r12.sum() else None])
    buckets = []
    if BUCKET in opn.columns:
        b = opn[BUCKET].astype("string").str.strip().fillna("Blank")
        def first_number(v):
            m = re.match(r"\s*(\d+)", v)
            return (int(m.group(1)) if m else 10 ** 6, v)
        order = sorted(b.unique(), key=first_number)
        for v in order:
            m = b == v
            buckets.append([str(v), int(m.sum()), int(items[m].sum()), _r(r12[m].sum())])
    out["concentration"] = {"base": "open accounts", "accounts": len(opn), "with_items": int((items > 0).sum()),
                            "items": int(items.sum()), "r12_fees": _r(r12.sum()), "tops": tops, "buckets": buckets}

    # ---- 3. overrides and trending --------------------------------------------------------------------------
    ov = (elig[OVERRIDE].astype("string").str.strip() if OVERRIDE in elig.columns
          else pd.Series("", index=elig.index, dtype="string"))
    ov_rows = []
    for name, g in elig[ov.notna() & (ov != "")].groupby(ov[ov.notna() & (ov != "")]):
        ov_rows.append([str(name), len(g), _r(_n(g, R.CORE).mean()), _r(_n(g, R.ILS).mean()), int(_n(g, R.ITEMS).sum())])
    ov_rows.sort(key=lambda r: -r[1])
    trend = []
    for col in TRENDS:
        if col not in elig.columns:
            continue
        v = pd.to_numeric(elig[col], errors="coerce")
        trend.append([col.replace("_", " ").title(), int(v.notna().sum()), int((v < 0).sum()), int((v > 0).sum()),
                      _r(v[v < 0].sum()) if (v < 0).any() else 0.0])
    out["overrides"] = {"base": "open, eligible personal accounts", "accounts": len(elig),
                        "with_override": int(sum(r[1] for r in ov_rows)), "rows": ov_rows[:12], "trending": trend}

    # ---- 4. new accounts -------------------------------------------------------------------------------------
    asof = pd.Timestamp(extract_date) if extract_date is not None else pd.Timestamp.today().normalize()
    opened = pd.to_datetime(pers[R.OPENED], errors="coerce") if R.OPENED in pers.columns else pd.Series(pd.NaT, index=pers.index)
    age = (asof - opened).dt.days
    new = []
    for lo, hi, lbl in ((0, 90, "Opened in the last 90 days"), (91, 365, "Opened 91–365 days ago"),
                        (366, 10 ** 6, "Open more than a year")):
        m = (age >= lo) & (age <= hi)
        g = pers[m]
        gl = _n(g, R.ILS)
        new.append([lbl, len(g), int((gl == 0).sum()), _r((gl == 0).mean(), 4) if len(g) else None, _r(gl.mean()),
                    _r((_up(g, R.REGE) == "Y").mean(), 4) if len(g) else None, int(_n(g, R.ITEMS).sum())])
    out["new_accounts"] = {"base": "open personal accounts", "as_of": str(asof.date()), "rows": new}

    # ---- 5. second chance (and any other account type) ---------------------------------------------------------
    others = sorted(v for v in kind.unique() if v and v not in ("PERSONAL", "BUSINESS"))
    sc = {}
    for v in others:
        g = opn[kind == v]
        e = g[_up(g, R.OD).isin(od_codes)]
        sc[v] = {"open": len(g), "eligible": len(e), "od": R._cut(g.assign(**{R.OD: _up(g, R.OD).replace({"": "BLANK"})}), R.OD),
                 "change": R._cut(e, R.CHANGE), "limits": [[int(t), int(n)] for t, n in _n(e, R.ILS).value_counts().sort_index().items()]}
    out["second_chance"] = sc

    # ---- 6. days overdrawn ---------------------------------------------------------------------------------------
    days = _n(opn, DAYS_OD)
    out["days_od"] = {"base": "open accounts", "max": int(days.max()) if len(days) else 0, "rows": [
        [lbl, int(((days >= lo) & (days <= hi)).sum()), int(items[(days >= lo) & (days <= hi)].sum()),
         _r(_n(opn, R.ILS)[(days >= lo) & (days <= hi)].mean()) if ((days >= lo) & (days <= hi)).any() else None]
        for lo, hi, lbl in DAYS_BANDS]}

    # ---- 7. products ---------------------------------------------------------------------------------------------
    if PRODUCT in opn.columns:
        prod = R._cut(opn.assign(**{PRODUCT: _up(opn, PRODUCT).replace({"": "BLANK"})}), PRODUCT)
        prod["rows"] = prod["rows"][:12]
        out["products"] = prod

    # ---- core limits against ILS limits (James Gilmore, 2026-10-28: "compare the ILS limit with the core limit ...
    # show their current system is inefficient compared to ILS limits") ----------------------------------------------
    biz = opn[kind == "BUSINESS"]
    out["core_vs_ils"] = {"personal": core_vs_ils(elig),
                          "business": core_vs_ils(biz[_up(biz, R.OD).isin(od_codes)])}

    # ---- 8. revenue check ----------------------------------------------------------------------------------------
    nt = notices or {}
    out["revenue_check"] = {"r12_fees_open": _r(r12.sum()), "r12_fees_live": _r(_n(live, R12_FEES).sum()),
                            "r12_items_open": int(_n(opn, R12_ITEMS).sum()),
                            "notice_annualized": nt.get("revenue_annualized"), "notice_days": nt.get("days"),
                            "gap_pct": _r((r12.sum() - nt["revenue_annualized"]) / nt["revenue_annualized"], 4)
                            if nt.get("revenue_annualized") else None}
    return {"pgl_insights": out}

