"""
Fee, repayment and exception-item figures: the R / Excel / Power BI pictures on the "Client
Analysis" slides of the hand-built ILS analysis deck, redrawn in Python from the raw extracts.

Replaced, one function each:
    kpi_rollup           365-Day KPI Rollup (an Excel range pasted in)             -> table
    fees_daily           Collected Fee Trending, Personal / Business (R line plot)  -> chart
    monthly_fee_table    the Excel range beside it (accounts, fees, fees per day, pay rate) -> table
    paid_vs_returned     Collected Fees - Paid vs. Returned Items (R stacked bars + Excel table)
    not_repaid           Percent of NSF/OD Items Not Repaid (R line plot with a smoother)
    exception_treemap    Trends in Exception Items (a Power BI treemap)

Every function returns a `r_common.ChartResult` whose `numbers` and `tables` are written beside the
PNG as a sidecar, and records in `parity` how each figure compares with the hand-built deck when a
reference figure is supplied (`ref`). Nothing is invented: a measure the extract cannot support is
left out and the reason is in `notes`.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import r_common as R
from .r_common import ChartResult, compare, money, pct, plt

CHANNELS = ("ACH", "ATM", "CHK", "INT", "CSR", "BPY", "OTH", "POS")


def _month_range(fr, n=12):
    """The last n COMPLETE calendar months before the as-of date (month_complete: a month still
    running on the data's as-of date is partial and is left out)."""
    asof = fr.asof
    last_full = (asof.replace(day=1) - pd.Timedelta(days=1)) if asof.day != asof.days_in_month else asof
    end = last_full.to_period("M")
    return [end - i for i in range(n - 1, -1, -1)]


def _fmt_asof(ts):
    return f"{ts.month}/{ts.day}/{ts.year}"


# ═════════════════════════════ 365-day KPI rollup ═══════════════════════════
def kpi_rollup(fr, ref=None):
    ref = ref or {}
    za, asof = fr.za, fr.asof
    lo = asof - pd.Timedelta(days=365)
    cols = {}
    for t in ("Business", "Personal"):
        d = za[za["accttype"] == t]
        if d.empty:
            continue
        o = d[d["acctstatus"].astype(str).str.upper() == "O"]
        fees = float(d["CollectedFees365"].sum())
        co = float(d["Chargeoff_Amt_365"].sum())
        refund = float(d["Refund_Amt_365"].sum())
        opened = int((pd.to_datetime(d["opendate"], errors="coerce") >= lo).sum())
        closed = int((pd.to_datetime(d["closeddate"], errors="coerce") >= lo).sum())
        codt = pd.to_datetime(d["Chargeoff_Date"], errors="coerce")
        co_n = int((codt >= lo).sum())
        users = int((d["items365"] > 0).sum())
        co_users = int(((codt >= lo) & (d["items365"] > 0)).sum())
        act = fr.active_open(t)
        act_users = int((act["items365"] > 0).sum())
        cols[t] = {
            "Data as of": _fmt_asof(asof),
            "Collected Fees": money(fees), "Charge-Off Amount": money(co, 2),
            "Loss Rate": pct(co / fees * 100) if fees else "n/a",
            "Refund Amt": money(refund, 2), "Refund %": pct(refund / fees * 100) if fees else "n/a",
            "Open Accts": f"{len(o):,}", "Accts Opened (365 days)": f"{opened:,}",
            "Accts Closed (365 days)": f"{closed:,}",
            "Accounts Charged Off (365 days)": f"{co_n:,}",
            "Growth Rate": pct((opened - closed) / len(o) * 100) if len(o) else "n/a",
            "NSF/OD Users": f"{users:,}", "Users Charged Off (365 days)": f"{co_users:,}",
            "User Charge-Off Rate": pct(co_users / users * 100) if users else "n/a",
            "Open Active Accts": f"{len(act):,}",
            "Open Active NSF/OD Users": f"{act_users:,}",
            "% Open Active Users": pct(act_users / len(act) * 100) if len(act) else "n/a",
        }
        raw = {"fees": fees, "charge_off": co, "refund": refund, "open": len(o), "opened": opened,
               "closed": closed, "users": users}
        cols[t]["_raw"] = raw
    if not cols:
        return R.skipped("kpi_rollup", "365-day KPI rollup", "no Business or Personal accounts in the extract")
    types = list(cols)
    labels = [k for k in next(iter(cols.values())) if k != "_raw"]
    rows = [[lab] + [cols[t][lab] for t in types] for lab in labels]
    res = ChartResult("kpi_rollup", "365-day KPI rollup",
                      tables={"kpi": {"headers": ["Measure"] + types, "rows": rows}},
                      numbers={t: cols[t]["_raw"] for t in types})
    for t in types:
        for name, key in (("Collected Fees", "fees"), ("Charge-Off Amount", "charge_off"),
                          ("Refund Amt", "refund"), ("Open Accts", "open"), ("Accts Opened", "opened"),
                          ("Accts Closed", "closed"), ("NSF/OD Users", "users")):
            res.parity.append(compare(cols[t]["_raw"][key], ref.get(f"kpi.{t}.{key}"), measure=f"{t} {name}"))
    res.notes.append("Open Active Accts = open accounts with a deposit in the last 240 days or an NSF/OD item in the "
                     "last 365 (the analysis team's own definition is in their SQL, not in the extract; 240 days "
                     "reproduces Achieva's personal figure to 2 accounts).")
    return res


# ═════════════════════════════ monthly fee table ═══════════════════════════
def monthly_fee_table(fr, accttype, n=12, ref=None):
    z = fr.zt_type(accttype)
    if z is None or z.empty:
        return None
    ref = ref or {}
    mons = _month_range(fr, n)
    ym = z["noticedate"].dt.to_period("M")
    rows, nums = [], []
    for m in mons:
        s = z[ym == m]
        if s.empty:
            continue
        items, paid = float(s["Items"].sum()), float(s["PD"].sum())
        fees = float(s["CollectedFees"].sum())
        days = m.days_in_month
        rows.append([R.periods.mon_yy(f"{m.year}-{m.month:02d}"), f"{s['acctid'].nunique():,}", money(fees),
                     money(fees / days), pct(paid / items * 100, 2) if items else "n/a"])
        nums.append({"month": str(m), "accounts": int(s["acctid"].nunique()), "fees": fees, "days": days,
                     "fees_per_day": fees / days, "pay_rate_pct": paid / items * 100 if items else None})
    return {"headers": ["Month", "OD Accts", "Collected Fees", "Fees / Day", "Pay Rate"],
            "rows": rows, "numbers": nums}


# ═════════════════════════════ daily collected fees ════════════════════════
def fees_daily(fr, accttype, out_dir, size=(7.7, 4.45), ref=None):
    key = f"fees_daily_{accttype.lower()}"
    z = fr.zt_type(accttype)
    if z is None or z.empty:
        return R.skipped(key, f"Collected fees - {accttype}", "no ZTrend notices for this account type")
    ref = ref or {}
    daily = z.groupby("noticedate")["CollectedFees"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(idx, fill_value=0.0)
    ewma = daily.ewm(span=30, adjust=False).mean()
    fig, ax = R.new_fig(*size)
    ax.plot(daily.index, daily.values, color=R.STEEL, linewidth=0.8, alpha=0.9, label="Daily collected fees")
    ax.plot(ewma.index[30:], ewma.values[30:], color=R.NAVY, linewidth=2.6, label="30-day moving average")
    ax.scatter([ewma.index[-1]], [ewma.values[-1]], color=R.ORANGE, s=34, zorder=5)
    ax.annotate(money(ewma.values[-1]), (ewma.index[-1], ewma.values[-1]), (-8, 26), textcoords="offset points",
                ha="right", fontsize=10.5, color=R.ORANGE, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    R.style_axes(ax)
    R.month_ticks(ax, daily.index.min(), daily.index.max(), every=3)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Collected fees per day", fontsize=10.5, color=R.TICK)
    ax.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=R.TICK)
    fig.tight_layout()
    path = R.save(fig, out_dir, key)
    res = ChartResult(key, f"Collected fees - {accttype}", path,
                      numbers={"first_day": str(daily.index.min())[:10], "last_day": str(daily.index.max())[:10],
                               "days": int(len(daily)), "total_fees": float(daily.sum()),
                               "latest_30d_avg": float(ewma.values[-1]), "first_30d_avg": float(ewma.values[30])})
    tbl = monthly_fee_table(fr, accttype, ref=ref)
    if tbl:
        res.tables["monthly"] = {"headers": tbl["headers"], "rows": tbl["rows"]}
        res.numbers["monthly"] = tbl["numbers"]
        for r in tbl["numbers"][:1] + tbl["numbers"][-1:]:
            for fld, nm in (("accounts", "OD accounts"), ("fees", "collected fees"), ("pay_rate_pct", "pay rate %")):
                res.parity.append(compare(r[fld], ref.get(f"fees.{accttype}.{r['month']}.{fld}"),
                                          measure=f"{accttype} {r['month']} {nm}"))
    return res


# ═════════════════════════════ paid vs returned ═════════════════════════════
def paid_vs_returned_stats(fr, accttype, n=12):
    z = fr.zt_type(accttype)
    if z is None or z.empty:
        return None
    mons = _month_range(fr, n)
    s = z[z["noticedate"].dt.to_period("M").isin(mons)]
    paid, ret = s[s["PD"] == 1], s[s["PD"] == 0]
    tot_items, tot_fees = float(s["Items"].sum()), float(s["CollectedFees"].sum())
    paid_items, ret_items = float(paid["Items"].sum()), float(ret["Items"].sum())
    paid_fees, ret_fees = float(paid["CollectedFees"].sum()), float(ret["CollectedFees"].sum())
    paid_amt, ret_amt = float(paid["Item_Amts"].sum()), float(ret["Item_Amts"].sum())
    return {"first_month": str(mons[0]), "last_month": str(mons[-1]), "total_items": tot_items,
            "collected_fees": tot_fees, "paid_items": paid_items, "pct_paid_items": paid_items / tot_items * 100,
            "paid_fees": paid_fees, "pct_fees_paid": paid_fees / tot_fees * 100 if tot_fees else 0,
            "paid_item_amount": paid_amt, "purchase_power": paid_amt / paid_fees if paid_fees else 0,
            "returned_items": ret_items, "pct_returned_items": ret_items / tot_items * 100,
            "returned_fees": ret_fees, "pct_returned_fees": ret_fees / tot_fees * 100 if tot_fees else 0,
            "returned_item_amount": ret_amt}


def paid_vs_returned(fr, out_dir, size=(7.2, 3.9), ref=None):
    key = "paid_vs_returned"
    stats = {t: paid_vs_returned_stats(fr, t) for t in ("Personal", "Business")}
    stats = {t: s for t, s in stats.items() if s}
    if not stats:
        return R.skipped(key, "Collected fees - paid vs. returned items", "no ZTrend notices")
    ref = ref or {}
    fig, axes = plt.subplots(1, len(stats), figsize=size, sharey=True)
    axes = np.atleast_1d(axes)
    for ax, (t, s) in zip(axes, stats.items()):
        xs = ["Collected fees", "Items"]
        paid = [s["pct_fees_paid"], s["pct_paid_items"]]
        ret = [100 - p for p in paid]
        ax.bar(xs, paid, color=R.NAVY, width=0.62, label="Paid")
        ax.bar(xs, ret, bottom=paid, color=R.ORANGE, width=0.62, label="Returned")
        for i, (p, r_) in enumerate(zip(paid, ret)):
            ax.text(i, p / 2, f"{p:.1f}%", ha="center", va="center", color="white", fontsize=12, fontweight="bold")
            ax.text(i, p + r_ / 2, f"{r_:.1f}%", ha="center", va="center", color="white", fontsize=12, fontweight="bold")
        ax.set_title(f"{t} accounts", fontsize=12, color=R.NAVY, loc="left", fontweight="bold")
        R.style_axes(ax, grid="y")
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    axes[0].set_ylabel("Share of total", fontsize=10.5, color=R.TICK)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False, fontsize=10.5, labelcolor=R.TICK)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    path = R.save(fig, out_dir, key)
    res = ChartResult(key, "Collected fees - paid vs. returned items", path, numbers=stats)
    heads = ["Account Type", "Total Items", "Collected Fees", "Paid Items", "% Paid Items", "Paid Fees",
             "% Fees Paid", "Paid Item Amount", "Purchase Power x", "Returned Items", "% Returned Items",
             "Returned Fees", "% Returned Fees", "Returned Item Amount"]
    rows = []
    for t, s in stats.items():
        rows.append([t, f"{s['total_items']:,.0f}", money(s["collected_fees"]), f"{s['paid_items']:,.0f}",
                     pct(s["pct_paid_items"], 2), money(s["paid_fees"]), pct(s["pct_fees_paid"], 2),
                     money(s["paid_item_amount"]), f"{s['purchase_power']:.1f}", f"{s['returned_items']:,.0f}",
                     pct(s["pct_returned_items"], 2), money(s["returned_fees"]), pct(s["pct_returned_fees"], 2),
                     money(s["returned_item_amount"])])
        for fld, nm in (("total_items", "total items"), ("collected_fees", "collected fees"),
                        ("paid_items", "paid items"), ("returned_fees", "returned fees")):
            res.parity.append(compare(s[fld], ref.get(f"paid_vs_returned.{t}.{fld}"), measure=f"{t} {nm}"))
    res.tables["summary"] = {"headers": heads, "rows": rows}
    return res


# ═════════════════════════════ percent of items not repaid ══════════════════
def _fatal_frame(fr, accttype):
    """Notices for one account type with the 'fatal' flag: the LAST notice of an account that was
    charged off. The hand-built deck's definition is not in the extract (its R script reads a
    charge-off table the pull does not carry), so this is the nearest the extract supports."""
    n = fr.notices
    if n is None:
        return None
    s = n[n["accttype"] == accttype].sort_values(["acctid", "noticedate"]).copy()
    s["is_last"] = ~s.duplicated("acctid", keep="last")
    s["fatal"] = s["co"] & s["is_last"]
    s["loss"] = np.where(s["fatal"], s["co_amt"], 0.0)
    return s


def not_repaid(fr, accttype, out_dir, size=(7.7, 4.45), ref=None):
    key = f"not_repaid_{accttype.lower()}"
    s = _fatal_frame(fr, accttype)
    if s is None or s.empty:
        return R.skipped(key, f"Percent of NSF/OD items not repaid - {accttype}", "no ZTrend notices")
    lo, hi = fr.scoring_window()
    w = s[(s["noticedate"] >= lo) & (s["noticedate"] <= hi)]
    daily = w.groupby("noticedate").agg(n=("acctid", "size"), f=("fatal", "sum"))
    daily = daily.reindex(pd.date_range(lo, hi, freq="D"), fill_value=0)
    rate = (daily["f"] / daily["n"].where(daily["n"] > 0) * 100).fillna(0.0)
    sm = R.smooth(rate.values, frac=0.45)
    fig, ax = R.new_fig(*size)
    ax.plot(rate.index, rate.values, color=R.STEEL, linewidth=0.9, label="Daily share of notices not repaid")
    ax.plot(rate.index, sm, color=R.NAVY, linewidth=2.6, label="Smoothed trend")
    R.style_axes(ax)
    R.month_ticks(ax, lo, hi, every=2)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.1f}%")
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Notices not repaid", fontsize=10.5, color=R.TICK)
    ax.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=R.TICK)
    fig.tight_layout()
    path = R.save(fig, out_dir, key)
    res = ChartResult(key, f"Percent of NSF/OD items not repaid - {accttype}", path,
                      numbers={"window": [str(lo)[:10], str(hi)[:10]], "notices": int(daily["n"].sum()),
                               "not_repaid_notices": int(daily["f"].sum()),
                               "rate_pct": float(daily["f"].sum() / max(1, daily["n"].sum()) * 100),
                               "loss_dollars": float(w["loss"].sum())})
    # monthly table: only months whose notices all fall inside the matured window (month_complete)
    mons = _month_range(fr, 12)
    allw = s
    rows, nums = [], []
    for m in mons:
        sm_ = allw[allw["noticedate"].dt.to_period("M") == m]
        if sm_.empty:
            continue
        label = R.periods.mon_yy(f"{m.year}-{m.month:02d}")
        mature = m.end_time.normalize() <= hi
        fees = float(sm_["CollectedFees"].sum())
        if mature:
            fatal_pct = sm_["fatal"].mean() * 100
            loss_rate = sm_["loss"].sum() / fees * 100 if fees else 0
            rows.append([label, f"{sm_['acctid'].nunique():,}", money(fees), pct(fatal_pct, 2), pct(loss_rate, 2)])
            nums.append({"month": str(m), "fatal_pct": fatal_pct, "loss_rate_pct": loss_rate, "fees": fees})
        else:
            rows.append([label, f"{sm_['acctid'].nunique():,}", money(fees), "—", "—"])
            nums.append({"month": str(m), "fatal_pct": None, "loss_rate_pct": None, "fees": fees})
    res.tables["monthly"] = {"headers": ["Month", "OD Accounts", "Collected Fees", "% Fatal Notices", "Loss Rate"],
                             "rows": rows}
    res.numbers["monthly"] = nums
    first = next((x for x in nums if x["fatal_pct"] is not None), None)
    if first:
        res.parity.append(compare(first["fatal_pct"], (ref or {}).get(f"not_repaid.{accttype}.{first['month']}.fatal_pct"),
                                  tol=0.35, measure=f"{accttype} {first['month']} % fatal notices"))
        res.parity.append(compare(first["loss_rate_pct"], (ref or {}).get(f"not_repaid.{accttype}.{first['month']}.loss_rate_pct"),
                                  tol=0.35, measure=f"{accttype} {first['month']} loss rate"))
    res.notes.append("A notice is counted as not repaid when it is the last notice before its account was charged "
                     "off. The hand-built deck's definition comes from a charge-off table that is not in the "
                     "extract, so these rates are close to, not equal to, the deck's. Months whose notices run "
                     "past the 60-day follow-up are shown as a dash: they have not matured.")
    return res


# ═════════════════════════════ exception items treemap ══════════════════════
def _squarify(values, x, y, w, h):
    """Squarified treemap (Bruls, Huizing, van Wijk): rectangles for `values` (descending) in the box."""
    rects = []
    vals = list(values)
    total = float(sum(vals)) or 1.0
    area = [v / total * w * h for v in vals]

    def worst(row, side):
        s = sum(row)
        return max(max(side * side * r / (s * s), s * s / (side * side * r)) for r in row if r > 0)

    i = 0
    while i < len(area):
        side = min(w, h)
        row = [area[i]]
        j = i + 1
        while j < len(area) and worst(row + [area[j]], side) <= worst(row, side):
            row.append(area[j])
            j += 1
        s = sum(row)
        if w >= h:                       # lay the row as a column on the left
            cw = s / h
            yy = y
            for a in row:
                rects.append((x, yy, cw, a / cw))
                yy += a / cw
            x, w = x + cw, w - cw
        else:                            # lay the row along the top
            rh = s / w
            xx = x
            for a in row:
                rects.append((xx, y, a / rh, rh))
                xx += a / rh
            y, h = y + rh, h - rh
        i = j
    return rects


def exception_treemap(fr, accttype, out_dir, size=(5.9, 3.3), ref=None):
    key = f"exception_items_{accttype.lower()}"
    z = fr.zt_type(accttype)
    if z is None or z.empty:
        return R.skipped(key, f"Exception items by channel - {accttype}", "no ZTrend notices")
    lo, hi = fr.trailing(365)
    s = z[(z["noticedate"] > lo) & (z["noticedate"] <= hi)]
    have = [c for c in CHANNELS if c in s.columns]
    if not have:
        return R.skipped(key, f"Exception items by channel - {accttype}", "ZTrend carries no channel columns")
    stats = []
    for c in have:
        flag = pd.to_numeric(s[c], errors="coerce").fillna(0) > 0
        n = int(flag.sum())
        if n:
            stats.append({"channel": c, "items": n, "median_amount": float(s.loc[flag, "Item_Amts"].median())})
    if not stats:
        return R.skipped(key, f"Exception items by channel - {accttype}", "no channel-coded items in the window")
    stats.sort(key=lambda r: -r["items"])
    palette = [R.NAVY, R.STEEL, R.TEAL, R.SLATE, R.GOLD, R.ORANGE, R.STEEL_SOFT, R.LABEL]
    fig, ax = R.new_fig(*size)
    ax.set_xlim(0, 1)
    ax.set_ylim(1, 0)
    ax.axis("off")
    rects = _squarify([r["items"] for r in stats], 0, 0, 1, 1)
    for k, (r_, (x, y, w, h)) in enumerate(zip(stats, rects)):
        col = palette[k % len(palette)]
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=col, edgecolor="white", linewidth=2))
        dark = col in (R.NAVY, R.TEAL, R.SLATE, R.ORANGE, R.STEEL)
        ink = "white" if dark else R.NAVY
        big = w * h > 0.05
        cnt = f"{r_['items'] / 1000:.0f}K" if r_["items"] >= 1000 else f"{r_['items']:,}"
        ax.text(x + 0.012, y + 0.02, r_["channel"], ha="left", va="top", color=ink, fontsize=15 if big else 9.5,
                fontweight="bold")
        if big:
            ax.text(x + w / 2, y + h / 2, f"Median\n${r_['median_amount']:,.2f}", ha="center", va="center",
                    color=ink, fontsize=12)
        ax.text(x + 0.012, y + h - 0.02, cnt, ha="left", va="bottom", color=ink, fontsize=11 if big else 8.5)
    fig.subplots_adjust(0.005, 0.005, 0.995, 0.995)
    path = R.save(fig, out_dir, key)
    res = ChartResult(key, f"Exception items by channel - {accttype}", path,
                      numbers={"window": [str(lo + pd.Timedelta(days=1))[:10], str(hi)[:10]], "channels": stats,
                               "total_items": int(sum(r["items"] for r in stats))})
    res.tables["channels"] = {"headers": ["Channel", "Items", "Median item amount"],
                              "rows": [[r["channel"], f"{r['items']:,}", money(r["median_amount"], 2)] for r in stats]}
    res.notes.append("Tile area is the item count; the figure inside is the median item amount for that channel.")
    return res
