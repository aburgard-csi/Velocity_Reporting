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
        d = fr.segment(t)                  # a third type counts here by IsPersonal (Northwest's Private Banking)
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
        is_user = pd.to_numeric(d["items365"], errors="coerce").fillna(0) >= 1
        users = int(is_user.sum())
        # The notebook's p1 (cell 97): a charged-off user is a user on a charged-off account whose charge-off date
        # falls in the 365 days; % closed accounts charged off is that count over accounts closed in the 365 days
        # (its numerator counts users, as the notebook's does); % active users is users over active accounts.
        co_flag = R._yes(d["Chargeoff_Account"]) if "Chargeoff_Account" in d.columns else pd.Series(True, index=d.index)
        co_users = int((co_flag & (codt >= lo) & is_user).sum())
        active_all = int(fr.active(d).sum())
        act = fr.active_open(t)
        act_users = int((pd.to_numeric(act["items365"], errors="coerce").fillna(0) >= 1).sum())
        bad_co, bad_rf = fr.co_problem is not None, fr.refund_problem is not None
        cols[t] = {
            "Data as of": _fmt_asof(asof),
            "Collected Fees": money(fees), "Charge-Off Amount": "n/a" if bad_co else money(co, 2),
            "Loss Rate": "n/a" if bad_co else (pct(co / fees * 100) if fees else "n/a"),
            "Refund Amt": "n/a" if bad_rf else money(refund, 2),
            "Refund %": "n/a" if bad_rf else (pct(refund / fees * 100) if fees else "n/a"),
            "Active Checking Accts": f"{active_all:,}",
            "Open Accts": f"{len(o):,}", "Accts Opened (365 days)": f"{opened:,}",
            "Accts Closed (365 days)": f"{closed:,}",
            "Accounts Charged Off (365 days)": "n/a" if bad_co else f"{co_n:,}",
            "% Closed Accts Charged Off": "n/a" if bad_co else (pct(co_users / closed * 100) if closed else "n/a"),
            "Growth Rate": pct((opened - closed) / len(o) * 100) if len(o) else "n/a",
            "NSF/OD Users": f"{users:,}",
            "% Active Users": pct(users / active_all * 100) if active_all else "n/a",
            "Users Charged Off (365 days)": "n/a" if bad_co else f"{co_users:,}",
            "User Charge-Off Rate": "n/a" if bad_co else (pct(co_users / users * 100) if users else "n/a"),
            "Open Active Accts": f"{len(act):,}",
            "Open Active NSF/OD Users": f"{act_users:,}",
            "% Open Active Users": pct(act_users / len(act) * 100) if len(act) else "n/a",
        }
        raw = {"fees": fees, "charge_off": None if bad_co else co, "refund": None if bad_rf else refund,
               "open": len(o), "opened": opened,
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
    for p in (fr.co_problem, fr.refund_problem):
        if p:
            res.notes.append(p)
    res.notes.append("Active = more than $50 deposited or at least one NSF/OD item in the last 365 days (the analysis "
                     "notebook's definition). Open Active Accts are the open accounts among them; % Active Users is "
                     "NSF/OD users over active accounts; % Closed Accts Charged Off is users charged off in the 365 days "
                     "over accounts closed in the 365 days.")
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


def movement_phrase(cur, prev, fmt):
    """The +/-2% band (CLAUDE.md): within 2% 'almost flat'; up states the figures and the %; down gives the two
    figures and the % with no verb of movement."""
    if not prev:
        return None
    ch = (cur - prev) / prev * 100
    if abs(ch) <= 2:
        return f"almost flat: {fmt(cur)} against {fmt(prev)}"
    if ch > 0:
        return f"up {ch:.0f}%: {fmt(cur)} against {fmt(prev)}"
    return f"{fmt(cur)} against {fmt(prev)} ({ch:.0f}%)"


def _month_vs_year_ago(daily, fr):
    """Fees per day in the last COMPLETE month against the same month a year earlier (complete months only)."""
    m = _month_range(fr, 1)[0]
    prev = m - 12
    d = daily.copy()
    ym = d.index.to_period("M")
    if not ((ym == m).any() and (ym == prev).any()) or d.index.min() > prev.start_time:
        return None
    cur = float(d[ym == m].sum()) / m.days_in_month
    old = float(d[ym == prev].sum()) / prev.days_in_month
    return {"month": str(m), "per_day": cur, "year_earlier_month": str(prev), "year_earlier_per_day": old,
            "phrase": f"{R.periods.mon_yy(f'{m.year}-{m.month:02d}')} collected {movement_phrase(cur, old, lambda v: money(v) + ' per day')} "
                      f"in {R.periods.mon_yy(f'{prev.year}-{prev.month:02d}')}"}


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
    if len(daily) < 60:
        return R.skipped(key, f"Collected fees - {accttype}", "fewer than 60 days of notices, too short for a 30-day average")
    # The slide's table is the last 12 complete months. An account type whose notices all fall before them (a small
    # business book with no recent notices) has no table, and the slide
    # would claim a window it does not have, so it is skipped and says why.
    tbl = monthly_fee_table(fr, accttype, ref=ref)
    if not tbl or not tbl.get("rows"):
        return R.skipped(key, f"Collected fees - {accttype}",
                         f"no notices in the last 12 complete months (its notices run "
                         f"{daily.index.min():%Y-%m-%d} to {daily.index.max():%Y-%m-%d})")
    avg30 = daily.rolling(30).mean()
    last_day = daily.index.max()
    fig, ax = R.new_fig(*size)
    # the 30-day average is the mark; the raw days are faint context only (every weekday / weekend and
    # payday cycle is a spike, which hid the trend: Aaron, 2026-11-04)
    ax.plot(daily.index, daily.values, color=R.STEEL_SOFT, linewidth=0.6, alpha=0.30, label="Each day (context)")
    ax.plot(avg30.index, avg30.values, color=R.NAVY, linewidth=2.8, label="30-day average of daily collected fees")
    ax.scatter([last_day], [avg30.values[-1]], color=R.ORANGE, s=38, zorder=5)
    ax.annotate(f"30-day average to {last_day:%b} {last_day.day}, {last_day.year}:\n{money(avg30.values[-1])} per day",
                (last_day, avg30.values[-1]), (-10, 34), textcoords="offset points", ha="right", fontsize=10,
                color=R.NAVY, fontweight="bold", bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=R.ORANGE, lw=1),
                arrowprops=dict(arrowstyle="-", color=R.ORANGE, lw=1))
    R.style_axes(ax)
    R.month_ticks(ax, daily.index.min(), daily.index.max(), every=3)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.set_ylim(0, max(float(np.nanmax(avg30.values)) * 1.75, 1.0))
    ax.set_ylabel("Collected fees per day", fontsize=10.5, color=R.TICK)
    ax.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=R.TICK)
    fig.tight_layout()
    path = R.save(fig, out_dir, key)
    res = ChartResult(key, f"Collected fees - {accttype}", path,
                      numbers={"first_day": str(daily.index.min())[:10], "last_day": str(daily.index.max())[:10],
                               "days": int(len(daily)), "total_fees": float(daily.sum()),
                               "latest_30d_avg": float(avg30.values[-1]), "latest_30d_avg_date": str(last_day)[:10],
                               "first_30d_avg": float(avg30.dropna().values[0])})
    res.numbers["year_on_year"] = _month_vs_year_ago(daily, fr)
    res.notes.append("The line is the 30-day average of daily collected fees; each day is drawn faintly behind it.")
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
    if s.empty or not float(s["Items"].sum()):
        return None          # notices, but none in the window: no shares to show
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
# The analysis notebook's rule ('ILS Analysis - Python Script.ipynb' cells 30-34, 70, 86-87; William's Dannemora
# FCU review, 2026-10): a charged-off account's 'fatal' notice is its notice nearest the account's last positive
# date (the largest Last_Positive_Date over its notices; the earliest notice on a tie). The chart is the daily
# share of notices that are fatal over the scoring window (425 to 60 days before the newest notice) with a lowess
# trend; the table is the notebook's 198_NEWTS_BETA, the 12 calendar months to the last complete month.
# Reproduced exactly on 1781 (all twelve monthly % Fatal Notices equal William's slide 35 on a pull cut at his
# 10/25 data date). Losses are the account's Chargeoff_Amt_365, once, on its fatal notice.

def _lowess(x, y, frac=0.4, iters=2):
    """Local linear regression with tricube weights and two robustness passes (Cleveland's lowess, as
    statsmodels' lowess(frac=0.4) the notebook draws); numpy only."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    if n < 4:
        return y.copy()
    r = max(2, int(math.ceil(frac * n)))
    fit, rob = np.zeros(n), np.ones(n)
    for _ in range(iters + 1):
        for i in range(n):
            d = np.abs(x - x[i])
            h = np.partition(d, r - 1)[r - 1] or 1.0
            w = np.clip(1 - (d / h) ** 3, 0, None) ** 3 * rob
            sw = w.sum()
            if sw <= 0:
                fit[i] = y[i]
                continue
            xm, ym = (w * x).sum() / sw, (w * y).sum() / sw
            b = (w * (x - xm) ** 2).sum()
            slope = (w * (x - xm) * (y - ym)).sum() / b if b > 0 else 0.0
            fit[i] = ym + slope * (x[i] - xm)
        res = y - fit
        s = np.median(np.abs(res)) or 1e-12
        rob = np.clip(1 - (res / (6 * s)) ** 2, 0, None) ** 2
    return fit


def _fatal_frame(fr, accttype):
    """One account type's notices with the notebook's 'fatal' flag (r_common's nb_fatal) and its loss."""
    n = fr.notices
    if n is None or "nb_fatal" not in n.columns:
        return None
    s = n[n["accttype"] == accttype].copy()
    s["fatal"] = s["nb_fatal"].astype(bool)
    s["loss"] = s["nb_loss"]
    return s


def not_repaid(fr, accttype, out_dir, size=(6.2, 4.6), ref=None):
    key = f"not_repaid_{accttype.lower()}"
    s = _fatal_frame(fr, accttype)
    if s is None or s.empty:
        return R.skipped(key, f"Percent of NSF/OD items not repaid - {accttype}", "no ZTrend notices with a last positive date")
    top = fr.notices["noticedate"].max()
    lo, hi = top - pd.Timedelta(days=425), top - pd.Timedelta(days=60)
    w = s[(s["noticedate"] >= lo) & (s["noticedate"] <= hi)]
    daily = w.groupby("noticedate").agg(n=("acctid", "size"), f=("fatal", "sum"))
    if daily.empty:
        return R.skipped(key, f"Percent of NSF/OD items not repaid - {accttype}", "no notices in the window")
    rate = daily["f"] / daily["n"] * 100
    x = np.array([d.toordinal() for d in daily.index], float)
    # On a sparse series (most days with no fatal notice: 1781's business accounts) the robustness passes treat every
    # non-zero day as an outlier and pull the trend flat to zero, which read "-0.0%" beside a 6% series; such a series
    # takes the plain local fit.
    sparse = float((rate == 0).mean()) > 0.5
    trend = np.clip(_lowess(x, rate.to_numpy(), iters=0 if sparse else 2), 0, None)
    fig, ax = R.new_fig(*size)
    ax.plot(daily.index, rate.values, color=R.STEEL_SOFT, linewidth=0.8, alpha=0.75, label="Each notice day")
    ax.plot(daily.index, trend, color=R.NAVY, linewidth=2.8, label="Trend (lowess)")
    ax.scatter([daily.index[-1]], [trend[-1]], color=R.ORANGE, s=38, zorder=5)
    ax.annotate(f"Trend at {daily.index[-1]:%b} {daily.index[-1].day}, {daily.index[-1].year}: {trend[-1]:.1f}%",
                (daily.index[-1], trend[-1]), (-10, 34), textcoords="offset points", ha="right", fontsize=10,
                color=R.NAVY, fontweight="bold", bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=R.ORANGE, lw=1),
                arrowprops=dict(arrowstyle="-", color=R.ORANGE, lw=1))
    R.style_axes(ax)
    R.month_ticks(ax, lo, hi, every=2)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.1f}%")
    ax.set_ylim(0, max(float(np.nanpercentile(rate.values, 99)) * 1.15, float(np.nanmax(trend)) * 1.6, 0.5))
    ax.set_ylabel("Share of notices not repaid", fontsize=10.5, color=R.TICK)
    ax.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=R.TICK)
    fig.tight_layout()
    path = R.save(fig, out_dir, key)
    res = ChartResult(key, f"Percent of NSF/OD items not repaid - {accttype}", path,
                      numbers={"window": [str(lo)[:10], str(hi)[:10]], "notices": int(daily["n"].sum()),
                               "not_repaid_notices": int(daily["f"].sum()),
                               "rate_pct": float(daily["f"].sum() / max(1, daily["n"].sum()) * 100),
                               "trend_end_pct": float(trend[-1])})
    bad_co = getattr(fr, "co_problem", None) is not None
    rows, nums = [], []
    for m in _month_range(fr, 12):
        sm_ = s[s["noticedate"].dt.to_period("M") == m]
        if sm_.empty:
            continue
        fees = float(sm_["CollectedFees"].sum())
        days = int(sm_["noticedate"].nunique())
        items = float(sm_["Items"].sum()) if "Items" in sm_ else float("nan")
        pay = float(sm_["PD"].sum()) / items * 100 if items else float("nan")
        inelig = float(sm_["limit"].isna().mean() * 100)
        fatal_pct = float(sm_["fatal"].mean() * 100)
        loss_rate = None if bad_co else (float(sm_["loss"].sum()) / fees * 100 if fees else 0.0)
        rows.append([R.periods.mon_yy(f"{m.year}-{m.month:02d}"), f"{sm_['acctid'].nunique():,}", money(fees), f"{days}",
                     money(fees / days if days else 0), pct(pay, 2), pct(inelig, 2), pct(fatal_pct, 2),
                     "n/a" if loss_rate is None else pct(loss_rate, 2)])
        nums.append({"month": str(m), "accounts": int(sm_["acctid"].nunique()), "fees": fees, "business_days": days,
                     "pay_rate_pct": pay, "ineligible_pct": inelig, "fatal_pct": fatal_pct, "loss_rate_pct": loss_rate})
    res.tables["monthly"] = {"headers": ["Month", "OD Accts", "Collected Fees", "Biz Days", "Fees / Biz Day", "Pay Rate",
                                         "Ineligible", "% Fatal", "Loss Rate"], "rows": rows}
    res.numbers["monthly"] = nums
    first = nums[0] if nums else None
    if first:
        res.parity.append(compare(first["fatal_pct"], (ref or {}).get(f"not_repaid.{accttype}.{first['month']}.fatal_pct"),
                                  tol=0.005, measure=f"{accttype} {first['month']} % fatal notices"))
    res.notes.append("A notice is not repaid ('fatal') when its account was charged off and it is the account's notice nearest "
                     "its last positive date: the analysis notebook's rule, counted once per charged-off account. % Fatal is "
                     "fatal notices over all notices in the month; Ineligible is the share of notices with no ILS limit; pay "
                     "rate is paid items over items. A recent month's rate keeps moving as later data lands, because an "
                     "account's last positive date can still move: the table runs to the last complete month, as the "
                     "notebook's does, but the chart stops 60 days before the newest notice.")
    if nums and nums[-1]["fatal_pct"] > 2 * max(1e-9, float(np.median([m["fatal_pct"] for m in nums[:-1]] or [0]))):
        res.notes.append(f"{nums[-1]['month']} reads {nums[-1]['fatal_pct']:.2f}% fatal against a median of "
                         f"{np.median([m['fatal_pct'] for m in nums[:-1]]):.2f}% for the eleven months before: it has had the "
                         "least time to settle and should be read with that in mind.")
    if bad_co:
        res.notes.append(fr.co_problem)
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


def channel_medians(fr, accttype, channels=None):
    """Median item amount (ZTrend Item_Amts) per presentment channel over the 365 days to the as-of date, plus
    "Total" over every item in those channels. Folded into the DBIC "Exception items by channel" slide (Aaron,
    2026-11-17: it and the treemap slide carried the same items, so they are one slide). None with no notices."""
    z = fr.zt_type(accttype)
    if z is None or z.empty or "Item_Amts" not in z.columns:
        return None
    lo, hi = fr.trailing(365)
    s = z[(z["noticedate"] > lo) & (z["noticedate"] <= hi)]
    want = None if channels is None else {str(c).upper() for c in channels}
    out, anyf = {}, pd.Series(False, index=s.index)
    for c in CHANNELS:
        if c not in s.columns or (want is not None and c not in want):
            continue
        flag = pd.to_numeric(s[c], errors="coerce").fillna(0) > 0
        if flag.any():
            out[c] = float(s.loc[flag, "Item_Amts"].median())
            anyf |= flag
    if not out:
        return None
    out["Total"] = float(s.loc[anyf, "Item_Amts"].median())
    return {"window": [str(lo + pd.Timedelta(days=1))[:10], str(hi)[:10]], "medians": out}


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
    tiny = []
    for k, (r_, (x, y, w, h)) in enumerate(zip(stats, rects)):
        col = palette[k % len(palette)]
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=col, edgecolor="white", linewidth=2))
        dark = col in (R.NAVY, R.TEAL, R.SLATE, R.ORANGE, R.STEEL)
        ink = "white" if dark else R.NAVY
        big = w * h > 0.05
        cnt = (f"{r_['items'] / 1000:.0f}K items" if r_["items"] >= 1000 else f"{r_['items']:,} items")
        if w < 0.12 or h < 0.16:
            # Dannemora FCU: CHK and ATM labels ran over each other in slivers; a sliver is named below the chart
            tiny.append(f"{r_['channel']} {cnt}")
            continue
        ax.text(x + 0.012, y + 0.02, r_["channel"], ha="left", va="top", color=ink, fontsize=15 if big else 9.5,
                fontweight="bold")
        if big:
            ax.text(x + w / 2, y + h / 2, f"Median\n${r_['median_amount']:,.2f}", ha="center", va="center",
                    color=ink, fontsize=12)
        ax.text(x + 0.012, y + h - 0.02, cnt, ha="left", va="bottom", color=ink, fontsize=11 if big else 8.5)
    if tiny:
        fig.text(0.005, 0.0, "Smallest tiles: " + "; ".join(tiny), ha="left", va="bottom", fontsize=9, color=R.TICK)
        fig.subplots_adjust(0.005, 0.07, 0.995, 0.995)
    else:
        fig.subplots_adjust(0.005, 0.005, 0.995, 0.995)
    path = R.save(fig, out_dir, key)
    res = ChartResult(key, f"Exception items by channel - {accttype}", path,
                      numbers={"window": [str(lo + pd.Timedelta(days=1))[:10], str(hi)[:10]], "channels": stats,
                               "total_items": int(sum(r["items"] for r in stats))})
    res.tables["channels"] = {"headers": ["Channel", "Items", "Median item amount"],
                              "rows": [[r["channel"], f"{r['items']:,}", money(r["median_amount"], 2)] for r in stats]}
    res.notes.append("Tile area is the item count; the figure inside is the median item amount for that channel.")
    return res
