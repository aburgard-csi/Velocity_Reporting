"""
Scoring Summary figures that are not predictor tables: the two heat maps, the limit distribution and
the limit-band profile table (seaborn / matplotlib pictures and an Excel range in the hand-built deck).

    odlimit_heatmap          Heat Map of ODLimit indexed by Age and 33 Day Deposits
    notice_crosstab_heatmap  Frequency of Notices Cross-Tabulated by Matrix Position
    limit_distribution       Score Distribution (ILS limit, stacked by user segment)
    strat_table              the ILS-limit band profile table beside it
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import r_common as R
from .r_common import ChartResult, compare, money, pct, plt
from .r_accounts import SCORE_BANDS, _num, _yes

AGE_EDGES = [30, 180, 365, 730, 1095, 1460, 1825, 2190, 2555, 2920, 3285, 3650, np.inf]
AGE_LABELS = ["0-30 Days", "31-180 Days", "181 Days-1 Yr", "1-2 Yrs", "2-3 Yrs", "3-4 Yrs", "4-5 Yrs", "5-6 Yrs",
              "6-7 Yrs", "7-8 Yrs", "8-9 Yrs", "9-10 Yrs", "10+ Yrs"]
DEP_EDGES = [100, 250, 500, 750, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000, 14000, 15000, np.inf]
DEP_LABELS = ["<= $100", "$101-250", "$251-500", "$501-750", "$751-1000", "$1001-1500", "$1501-2000", "$2001-3000",
              "$3001-4000", "$4001-5000", "$5001-6000", "$6001-8000", "$8001-10000", "$10001-12000", "$12001-14000",
              "$14001-15000", "$15001+"]
X_AGE = [30, 180, 365, 730, 1095, 3285, np.inf]
X_AGE_LABELS = ["1-30 Days", "31-180 Days", "181 Days - 1 Yr", "1-2 Yrs", "2-3 Yrs", "3-9 Yrs", "10+ Yrs"]
X_DEP = [500, 1500, 3000, 6000, 9000, np.inf]
X_DEP_LABELS = ["<= $500", "$501-$1500", "$1501-$3000", "$3001-$6000", "$6001-$9000", "$9001+"]


def _cut(v, edges):
    return np.clip(np.searchsorted(np.array(edges, dtype=float), np.asarray(v, dtype=float), side="left"), 0, len(edges) - 1)


def _ramp():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("rpe_ramp", ["#F2F5F8", R.STEEL_SOFT, R.STEEL, R.NAVY])


def odlimit_heatmap(fr, accttype, out_dir, size=(6.4, 4.9)):
    key = f"odlimit_heatmap_{accttype.lower()}"
    o = fr.open_accounts(accttype)
    if o.empty:
        return R.skipped(key, "ODLimit by age and 33-day deposits", "no open accounts")
    age = (fr.asof - pd.to_datetime(o["opendate"], errors="coerce")).dt.days
    ok = age.notna() & (age >= 0)
    lim = _num(o["ODLimit"])
    dep = _num(o["DepAmt33"]).fillna(0.0)
    d = pd.DataFrame({"a": _cut(age[ok], AGE_EDGES), "d": _cut(dep[ok], DEP_EDGES), "lim": lim[ok].to_numpy()})
    g = d.groupby(["a", "d"])["lim"].median().unstack().reindex(index=range(len(AGE_LABELS)), columns=range(len(DEP_LABELS)))
    if g.notna().sum().sum() < 6:
        return R.skipped(key, "ODLimit by age and 33-day deposits", "too few populated cells")
    fig, ax = R.new_fig(*size)
    m = ax.imshow(g.to_numpy(), origin="lower", aspect="auto", cmap=_ramp())
    ax.set_xticks(range(len(DEP_LABELS)))
    ax.set_xticklabels(DEP_LABELS, rotation=45, ha="right", fontsize=8, color=R.TICK)
    ax.set_yticks(range(len(AGE_LABELS)))
    ax.set_yticklabels(AGE_LABELS, fontsize=8.5, color=R.TICK)
    ax.set_xlabel("33-day deposits", fontsize=10, color=R.TICK)
    ax.set_ylabel("Account age", fontsize=10, color=R.TICK)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(m, ax=ax, fraction=0.04, pad=0.02)
    cb.ax.tick_params(labelsize=9, colors=R.TICK)
    cb.outline.set_visible(False)
    cb.set_label("Median ODLimit ($)", fontsize=9.5, color=R.TICK)
    fig.tight_layout()
    path = R.save(fig, out_dir, key)
    return ChartResult(key, "ODLimit by age and 33-day deposits", path,
                       numbers={"accounts": int(ok.sum()), "cells": int(g.notna().sum().sum()),
                                "median_limit_by_cell": {f"{AGE_LABELS[a]} | {DEP_LABELS[b]}": float(v)
                                                         for (a, b), v in g.stack().items()}},
                       notes=["Each cell is the median current ILS limit of the open accounts at that age and 33-day deposit "
                              "level: the matrix as it is operating, not as it is configured."])


def notice_crosstab_heatmap(fr, accttype, out_dir, size=(6.4, 4.9)):
    key = f"notice_crosstab_{accttype.lower()}"
    n = fr.notices
    if n is None:
        return R.skipped(key, "Notices by matrix position", "no ZTrend file")
    lo, hi = fr.scoring_window()
    w = n[(n["accttype"] == accttype) & (n["noticedate"] >= lo) & (n["noticedate"] <= hi) & (n["age_days"] >= 1)]
    if w.empty:
        return R.skipped(key, "Notices by matrix position", "no notices in the window")
    a = _cut(w["age_days"], X_AGE)
    d = _cut(w["deptotal33"].fillna(0.0), X_DEP)
    g = pd.crosstab(pd.Series(a, name="a"), pd.Series(d, name="d")).reindex(
        index=range(len(X_AGE_LABELS)), columns=range(len(X_DEP_LABELS)), fill_value=0)
    fig, ax = R.new_fig(*size)
    m = ax.imshow(g.to_numpy(), origin="lower", aspect="auto", cmap=_ramp())
    vmax = g.to_numpy().max() or 1
    for i in range(g.shape[0]):
        for j in range(g.shape[1]):
            v = int(g.iat[i, j])
            ax.text(j, i, f"{v:,}", ha="center", va="center", fontsize=9, color="white" if v > vmax * 0.45 else R.NAVY)
    ax.set_xticks(range(len(X_DEP_LABELS)))
    ax.set_xticklabels(X_DEP_LABELS, rotation=30, ha="right", fontsize=9, color=R.TICK)
    ax.set_yticks(range(len(X_AGE_LABELS)))
    ax.set_yticklabels(X_AGE_LABELS, fontsize=9, color=R.TICK)
    ax.set_xlabel("33-day deposits at the notice", fontsize=10, color=R.TICK)
    ax.set_ylabel("Account age at the notice", fontsize=10, color=R.TICK)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(m, ax=ax, fraction=0.04, pad=0.02)
    cb.ax.tick_params(labelsize=9, colors=R.TICK)
    cb.outline.set_visible(False)
    cb.set_label("Notices", fontsize=9.5, color=R.TICK)
    fig.tight_layout()
    path = R.save(fig, out_dir, key)
    return ChartResult(key, "Notices by matrix position", path,
                       numbers={"window": [str(lo)[:10], str(hi)[:10]], "notices": int(len(w)),
                                "grid": {f"{X_AGE_LABELS[i]} | {X_DEP_LABELS[j]}": int(g.iat[i, j])
                                         for i in range(g.shape[0]) for j in range(g.shape[1])}},
                       notes=["Every notice in the window is counted. The hand-built deck's R figure counts a random "
                              "sample of 100,000 notices."])


def limit_distribution(fr, accttype, out_dir, size=(6.0, 4.8)):
    key = f"limit_distribution_{accttype.lower()}"
    p = fr.active_open(accttype)
    if p.empty:
        return R.skipped(key, "ILS limit distribution", "no open active accounts")
    lim = _num(p["ODLimit"]).fillna(0.0)
    items = _num(p["items365"]).fillna(0.0)
    seg = np.where(items >= 24, 2, np.where(items > 0, 1, 0))
    hi = float(lim.max()) or 1.0
    step = 100 if hi > 1500 else 50
    bins = np.arange(0, hi + step * 2, step)
    fig, ax = R.new_fig(*size)
    bottom = np.zeros(len(bins) - 1)
    cols = (R.STEEL_SOFT, R.ORANGE, R.NAVY)
    labs = ("Non-user", "User (1-23 items)", "Heavy user (24+)")
    counts = {}
    for k in range(3):
        h, _ = np.histogram(lim[seg == k], bins=bins)
        ax.bar(bins[:-1], h, width=step * 0.9, bottom=bottom, align="edge", color=cols[k], label=labs[k])
        bottom += h
        counts[labs[k]] = int(h.sum())
    R.style_axes(ax)
    ax.set_xlabel("Current ILS limit ($)", fontsize=10, color=R.TICK)
    ax.set_ylabel("Accounts", fontsize=10, color=R.TICK)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.xaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.legend(frameon=False, fontsize=9.5, labelcolor=R.TICK, loc="upper right")
    fig.tight_layout()
    path = R.save(fig, out_dir, key)
    return ChartResult(key, "ILS limit distribution", path,
                       numbers={"accounts": int(len(p)), "bin_width": step, "by_segment": counts,
                                "median_limit": float(lim.median()), "max_limit": hi})


def strat_table(fr, accttype, ref=None):
    """Profile of open active accounts that can overdraft, by ILS-limit band."""
    p = fr.active_open(accttype)
    if p.empty:
        return None
    p = p.assign(can=_yes(p["CanOverdraft"]))
    p = p[p["can"]]
    if p.empty:
        return None
    zt = fr.zt
    fee_ret = fee_paid = None
    if zt is not None:
        lo, hi = fr.trailing(365)
        z = zt[(zt["noticedate"] > lo) & (zt["noticedate"] <= hi)]
        fee_ret = z[z["PD"] == 0].groupby("acctid")["CollectedFees"].sum()
        fee_paid = z[z["PD"] == 1].groupby("acctid")["CollectedFees"].sum()
    lim = _num(p["ODLimit"]).fillna(0.0)
    heads = ["ILS Limit", "Accounts", "Reg E Opt In", "Median Age (Yrs)", "Median Deposits (33d)", "Median $ (33d)",
             "Fees (365)", "NSF Fees", "OD Fees", "Pay Rate", "Median Deposits (365)"]
    rows = []
    for name, lo_, hi_ in SCORE_BANDS:
        m = (lim == 0) if lo_ is None else ((lim >= lo_) & ((lim <= hi_) if hi_ is not None else True))
        s = p[m.to_numpy()]
        if s.empty:
            continue
        age = (fr.asof - pd.to_datetime(s["opendate"], errors="coerce")).dt.days / 365.25
        items = _num(s["items365"]).fillna(0).sum()
        paid = _num(s["PD_365"]).fillna(0).sum()
        rows.append([name, f"{len(s):,}", f"{int((s['RegEOptinvalue'].astype(str).str.upper() == 'Y').sum()):,}",
                     f"{age.median():.1f}", f"{_num(s['DepCount33']).median():.0f}", money(_num(s["DepAmt33"]).median()),
                     money(_num(s["CollectedFees365"]).sum()),
                     money(float(fee_ret.reindex(s["acctid"]).sum())) if fee_ret is not None else "—",
                     money(float(fee_paid.reindex(s["acctid"]).sum())) if fee_paid is not None else "—",
                     pct(paid / items * 100) if items else "—", money(_num(s["depAmt365"]).median())])
    return {"headers": heads, "rows": rows, "population": int(len(p))}
