"""
Account-level figures: the R / Excel pictures on the eligibility, branch, Reg E and debit-decline
slides of the hand-built ILS analysis deck, redrawn in Python from the raw extracts.

Replaced, one function each:
    eligibility_chart    Eligibility Drilldown: accounts by OD status code, user segment, deposit band
    eligibility_tables   the two Excel ranges beside it (status-code table, items-segment table)
    branch_bubbles       Branch Summary: items per user against eligibility / Reg E opt-in (R bubbles)
    branch_tables        the top-ten Excel tables
    branch_opened_regE   accounts opened vs Reg E opt-in rate by branch (R bar + line)
    reg_e_tables         Reg E Drilldown tables (by election, by account-opening year)
    reg_e_flow           the Reg E alluvial (R)
    debit_decline_tables Debit Declines tables (Excel)

Every function returns a `r_common.ChartResult` (numbers + tables for the sidecar); a population the
extract cannot support is skipped with the reason in `skipped`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import r_common as R
from .r_common import ChartResult, compare, money, pct, plt

DEP_BANDS = [("NO DEPS", None, None), ("LESS 1000", 0, 1000), ("1001-2000", 1000, 2000),
             ("2001-5000", 2000, 5000), ("5000+", 5000, None)]
USER_SEGMENTS = (("NON-USER", lambda i: i <= 0), ("USER", lambda i: (i > 0) & (i < 24)),
                 ("HEAVY USER (24+)", lambda i: i >= 24))
ITEM_BANDS = [("NO ITEMS", 0, 0), ("1-6 ITEMS", 1, 6), ("7-12 ITEMS", 7, 12), ("13-24 ITEMS", 13, 24),
              ("25-48 ITEMS", 25, 48), ("49+ ITEMS", 49, None)]


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _dep_band(v):
    v = _num(v)
    out = pd.Series("NO DEPS", index=v.index, dtype=object)
    out[(v > 0) & (v < 1000)] = "LESS 1000"
    out[(v >= 1000) & (v < 2000)] = "1001-2000"
    out[(v >= 2000) & (v < 5000)] = "2001-5000"
    out[v >= 5000] = "5000+"
    return out


def _code_label(s):
    c = _num(s)
    return c.map(lambda v: "Blank" if pd.isna(v) else str(int(v)))


def _yes(s):
    return s.astype(str).str.lower().isin(("true", "1", "t", "y", "yes"))


def _population(fr, accttype):
    return fr.active_open(accttype)


# ═════════════════════════════ eligibility drilldown ═══════════════════════
def eligibility_chart(fr, accttype, out_dir, size=(6.4, 4.75)):
    key = f"eligibility_{accttype.lower()}"
    p = _population(fr, accttype)
    if p.empty:
        return R.skipped(key, f"Eligibility drilldown - {accttype}", "no open accounts with a deposit in 365 days")
    p = p.assign(code=_code_label(p["odstatuscode"]), band=_dep_band(p["DepAmt33"]), items=_num(p["items365"]).fillna(0))
    coded = p[p["code"] != "Blank"]
    if coded.empty:
        return R.skipped(key, f"Eligibility drilldown - {accttype}", "no account carries an OD status code")
    codes = sorted(coded["code"].unique(), key=lambda c: (len(c), c))
    colors = {"NO DEPS": R.STEEL, "LESS 1000": R.ORANGE, "1001-2000": R.TEAL, "2001-5000": R.SLATE, "5000+": R.GOLD}
    fig, axes = plt.subplots(1, 3, figsize=size, sharey=True)
    nums = {}
    for ax, (seg, fn) in zip(axes, USER_SEGMENTS):
        s = coded[fn(coded["items"])]
        bottom = np.zeros(len(codes))
        for b, _, _ in DEP_BANDS:
            vals = np.array([int(((s["code"] == c) & (s["band"] == b)).sum()) for c in codes], dtype=float)
            ax.bar(range(len(codes)), vals, bottom=bottom, color=colors[b], width=0.8, label=b)
            bottom += vals
        nums[seg] = {c: int(v) for c, v in zip(codes, bottom)}
        ax.set_xticks(range(len(codes)))
        ax.set_xticklabels(codes, fontsize=9, color=R.TICK)
        ax.set_title(seg, fontsize=10.5, color=R.NAVY, fontweight="bold")
        R.style_axes(ax)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    axes[0].set_ylabel("Accounts", fontsize=10.5, color=R.TICK)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, frameon=False, fontsize=9.5, labelcolor=R.TICK,
               title="33-day deposits", title_fontsize=9.5)
    fig.supxlabel("OD status code", fontsize=10, color=R.TICK, y=0.17)
    fig.tight_layout(rect=(0, 0.17, 1, 1))
    path = R.save(fig, out_dir, key)
    res = ChartResult(key, f"Eligibility drilldown - {accttype}", path,
                      numbers={"accounts_in_population": int(len(p)), "accounts_with_status_code": int(len(coded)),
                               "by_segment_and_code": nums})
    res.notes.append("Accounts with no OD status code (the large majority) are not drawn; they are in the table.")
    return res


def eligibility_tables(fr, accttype, ref=None):
    ref = ref or {}
    p = _population(fr, accttype)
    if p.empty:
        return None
    p = p.assign(code=_code_label(p["odstatuscode"]), items=_num(p["items365"]).fillna(0),
                 can=_yes(p["CanOverdraft"]), regE=p["RegEOptinvalue"].astype(str).str.upper().str.strip())
    heads = ["OD Status Code", "Accounts", "Can Overdraft", "Users", "Reg E Opt In", "Median 33-Day Deposits"]
    rows, nums = [], {}
    order = sorted(p["code"].unique(), key=lambda c: (-int((p["code"] == c).sum()), c))
    for c in order:
        s = p[p["code"] == c]
        rows.append([c, f"{len(s):,}", f"{int(s['can'].sum()):,}", f"{int((s['items'] > 0).sum()):,}",
                     f"{int((s['regE'] == 'Y').sum()):,}", money(_num(s["DepAmt33"]).median())])
        nums[c] = len(s)
    rows.append(["Total", f"{len(p):,}", f"{int(p['can'].sum()):,}", f"{int((p['items'] > 0).sum()):,}",
                 f"{int((p['regE'] == 'Y').sum()):,}", money(_num(p["DepAmt33"]).median())])
    t1 = {"headers": heads, "rows": rows}
    heads2 = ["Segment", "Accounts", "% of Accounts", "Can Overdraft", "% Can OD", "Reg E Opt In", "Reg E Opt Out",
              "Collected Fees", "% of Fees"]
    rows2 = []
    tot_fees = float(_num(p["CollectedFees365"]).sum()) or 1.0
    for name, lo, hi in ITEM_BANDS:
        m = (p["items"] >= lo) & ((p["items"] <= hi) if hi is not None else True)
        s = p[m]
        if s.empty:
            continue
        fees = float(_num(s["CollectedFees365"]).sum())
        rows2.append([name, f"{len(s):,}", pct(len(s) / len(p) * 100), f"{int(s['can'].sum()):,}",
                      pct(s["can"].mean() * 100), f"{int(((s['regE'] == 'Y') & s['can']).sum()):,}",
                      f"{int(((s['regE'] == 'N') & s['can']).sum()):,}", money(fees), pct(fees / tot_fees * 100)])
    rows2.append(["Total", f"{len(p):,}", "100.0%", f"{int(p['can'].sum()):,}", pct(p["can"].mean() * 100),
                  f"{int(((p['regE'] == 'Y') & p['can']).sum()):,}", f"{int(((p['regE'] == 'N') & p['can']).sum()):,}",
                  money(tot_fees), "100.0%"])
    t2 = {"headers": heads2, "rows": rows2}
    return {"codes": t1, "segments": t2, "population": int(len(p)),
            "parity": [compare(len(p), ref.get(f"eligibility.{accttype}.population"),
                               tol=0.03, measure=f"{accttype} open active accounts")]}


# ═════════════════════════════ branch summary ═════════════════════════════
def _branch_frame(fr, accttype, min_accounts=None):
    p = _population(fr, accttype)
    if p.empty:
        return None, 0
    p = p.assign(items=_num(p["items365"]).fillna(0), can=_yes(p["CanOverdraft"]),
                 regE=p["RegEOptinvalue"].astype(str).str.upper().str.strip(),
                 name=p["branchname"].astype(str))
    thr = min_accounts or max(25, int(round(len(p) * 0.0014)))
    g = p.groupby("name", observed=True).agg(accounts=("acctid", "size"), eligible=("can", "mean"),
                                             optin=("regE", lambda s: (s == "Y").mean()),
                                             n_items=("items", "sum"), users=("items", lambda s: int((s > 0).sum())))
    g["items_per_user"] = g["n_items"] / g["users"].where(g["users"] > 0)
    g = g[g["accounts"] >= thr].dropna(subset=["items_per_user"])
    return g, thr


def branch_bubbles(fr, accttype, out_dir, size=(6.1, 4.55)):
    outs = {}
    g, thr = _branch_frame(fr, accttype)
    for key_, ycol, ylab, ttl in (("branch_eligibility", "eligible", "Percent of open accounts eligible",
                                   "Items per user by eligibility"),
                                  ("branch_regE", "optin", "Percent opted in to Reg E", "Items per user by Reg E opt-in")):
        key = f"{key_}_{accttype.lower()}"
        if g is None or len(g) < 3:
            outs[key_] = R.skipped(key, ttl, f"fewer than 3 {accttype.lower()} branches with {thr}+ open accounts")
            continue
        fig, ax = R.new_fig(*size)
        x, y = g["items_per_user"].to_numpy(), g[ycol].to_numpy() * 100
        s = 40 + (g["n_items"] / g["n_items"].max()) * 520
        ax.scatter(x, y, s=s, c=g["n_items"], cmap=_ramp(), alpha=0.9, edgecolors="white", linewidths=0.8, zorder=3)
        ax.axvline(float(g["n_items"].sum() / g["users"].sum()), color=R.ORANGE, linestyle="--", linewidth=1.4, zorder=2)
        ax.axhline(float(np.average(y, weights=g["accounts"])), color=R.ORANGE, linestyle="--", linewidth=1.4, zorder=2)
        for nm, xi, yi in zip(g.index, x, y):
            ax.annotate(_short(nm), (xi, yi), (0, 8), textcoords="offset points", ha="center", fontsize=7.5, color=R.TICK)
        R.style_axes(ax, grid="both")
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
        ax.set_xlabel("NSF/OD items per user, last 365 days", fontsize=10, color=R.TICK)
        ax.set_ylabel(ylab, fontsize=10, color=R.TICK)
        ax.margins(0.1)
        fig.tight_layout()
        path = R.save(fig, out_dir, key)
        outs[key_] = ChartResult(key, ttl, path,
                                 numbers={"branches_plotted": int(len(g)), "min_open_accounts": thr,
                                          "min_accounts_note": "0.14% of the type's open active accounts (Achieva's deck uses 132 for 93,668)",
                                          "by_branch": {n: {"accounts": int(r.accounts), "items_per_user": float(r.items_per_user),
                                                            "eligible_pct": float(r.eligible * 100), "optin_pct": float(r.optin * 100),
                                                            "items": int(r.n_items)} for n, r in g.iterrows()}})
    return outs


def _ramp():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("rpe_blue", [R.STEEL_SOFT, R.STEEL, R.NAVY])


def _short(name, n=16):
    s = str(name).strip()
    return s if len(s) <= n else s[:n - 1] + "."


def branch_tables(fr, accttype):
    g, thr = _branch_frame(fr, accttype)
    if g is None or len(g) < 3:
        return None
    top_e = g.sort_values("eligible", ascending=False).head(10)
    top_i = g.sort_values("items_per_user", ascending=False).head(10)
    t1 = {"headers": ["Rank", "Branch", "Accounts", "Percent Eligible"],
          "rows": [[i, n, f"{int(r.accounts):,}", pct(r.eligible * 100)] for i, (n, r) in enumerate(top_e.iterrows(), 1)]}
    t2 = {"headers": ["Rank", "Branch", "Accounts", "Items per User"],
          "rows": [[i, n, f"{int(r.accounts):,}", f"{r.items_per_user:.1f}"] for i, (n, r) in enumerate(top_i.iterrows(), 1)]}
    return {"eligible": t1, "items_per_user": t2, "branches": int(len(g)), "min_accounts": thr}


def branch_opened_regE(fr, accttype, out_dir, size=(12.1, 4.2)):
    key = f"branch_opened_regE_{accttype.lower()}"
    o = fr.open_accounts(accttype)
    if o.empty:
        return R.skipped(key, "Accounts opened and Reg E opt-in by branch", "no open accounts")
    od = pd.to_datetime(o["opendate"], errors="coerce")
    regE = o["RegEOptinvalue"].astype(str).str.upper().str.strip()
    name = o["branchname"].astype(str)
    lo365 = fr.asof - pd.Timedelta(days=365)
    lo90 = fr.asof - pd.Timedelta(days=90)
    a = pd.DataFrame({"name": name, "opened365": od >= lo365, "o90": od >= lo90, "y90": (od >= lo90) & (regE == "Y")})
    g = a.groupby("name", observed=True).agg(opened=("opened365", "sum"), o90=("o90", "sum"), y90=("y90", "sum"))
    g = g[g["opened"] >= 25].copy()
    g["rate"] = np.where(g["o90"] >= 5, g["y90"] / g["o90"].where(g["o90"] > 0) * 100, np.nan)
    if len(g) < 3:
        return R.skipped(key, "Accounts opened and Reg E opt-in by branch", "fewer than 3 branches opened 25+ accounts in 365 days")
    g = g.sort_values("rate", ascending=False, na_position="last")
    fig, ax = R.new_fig(*size)
    ax.bar(range(len(g)), g["opened"], color=R.NAVY, width=0.7, label="Accounts opened, last 365 days")
    ax.set_xticks(range(len(g)))
    ax.set_xticklabels([_short(n, 14) for n in g.index], rotation=55, ha="right", fontsize=8, color=R.TICK)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.set_ylabel("Accounts opened", fontsize=10, color=R.TICK)
    R.style_axes(ax)
    ax2 = ax.twinx()
    ax2.plot(range(len(g)), g["rate"], color=R.TEAL, linewidth=2.2, marker="o", markersize=4,
             label="Reg E opt-in, accounts opened in last 90 days")
    ax2.set_ylim(0, 100)
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax2.tick_params(axis="y", labelsize=10, colors=R.TICK)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(R.MUTED)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", ncol=2, frameon=False, fontsize=9.5, labelcolor=R.TICK,
              bbox_to_anchor=(0.5, 1.12))
    fig.tight_layout()
    path = R.save(fig, out_dir, key)
    return ChartResult(key, "Accounts opened and Reg E opt-in by branch", path,
                       numbers={"branches": int(len(g)),
                                "by_branch": {n: {"opened_365": int(r.opened), "opened_90": int(r.o90),
                                                  "optin_90_pct": None if pd.isna(r.rate) else float(r.rate)}
                                              for n, r in g.iterrows()}},
                       notes=["A branch's opt-in rate is drawn only when it opened 5+ accounts in the last 90 days."])


# ═════════════════════════════ Reg E drilldown ═════════════════════════════
def reg_e_tables(fr, accttype="Personal", ref=None):
    p = _population(fr, accttype)
    if p.empty:
        return None
    p = p.assign(items=_num(p["items365"]).fillna(0), can=_yes(p["CanOverdraft"]),
                 regE=p["RegEOptinvalue"].astype(str).str.upper().str.strip(), fees=_num(p["CollectedFees365"]).fillna(0),
                 lim=_num(p["ODLimit"]))
    rows = []
    for v in ("D", "N", "Y"):
        s = p[p["regE"] == v]
        if s.empty:
            continue
        users = int((s["items"] > 0).sum())
        hu = s[s["items"] >= 24]
        rows.append([v, f"{len(s):,}", pct(s["can"].mean() * 100), money(s["lim"].median()),
                     money(float(s["fees"].sum())), f"{users:,}", money(float(s["fees"].sum()) / users if users else 0, 2),
                     f"{len(hu):,}", money(float(hu["fees"].sum()))])
    users = int((p["items"] > 0).sum())
    hu = p[p["items"] >= 24]
    rows.append(["Total", f"{len(p):,}", pct(p["can"].mean() * 100), money(p["lim"].median()),
                 money(float(p["fees"].sum())), f"{users:,}", money(float(p["fees"].sum()) / users if users else 0, 2),
                 f"{len(hu):,}", money(float(hu["fees"].sum()))])
    by_election = {"headers": ["Reg E", "Accounts", "% Can OD", "Median ILS Limit", "Collected Fees (365)", "Users",
                               "Fees / User", "Heavy Users (24+)", "Heavy-User Fees"], "rows": rows}
    allo = fr.open_accounts(accttype)
    allo = allo.assign(regE=allo["RegEOptinvalue"].astype(str).str.upper().str.strip())
    p_year = allo
    yr = pd.to_datetime(allo["opendate"], errors="coerce").dt.year
    lab = pd.Series("Unknown", index=allo.index, dtype=object)
    lab[yr <= 1990] = "<= 1990"
    lab[(yr > 1990) & (yr <= 2000)] = "1991-2000"
    lab[(yr > 2000) & (yr <= 2010)] = "2001-2010"
    for y in range(2011, int(fr.asof.year) + 1):
        lab[yr == y] = str(y)
    yrows = []
    for L in ["<= 1990", "1991-2000", "2001-2010"] + [str(y) for y in range(2011, int(fr.asof.year) + 1)]:
        s = p_year[lab == L]
        if s.empty:
            continue
        yrows.append([L, f"{len(s):,}", f"{int((s['regE'] == 'Y').sum()):,}", pct((s["regE"] == "Y").mean() * 100)])
    by_year = {"headers": ["Year Opened", "Accounts", "Reg E = Y", "% Opted In"], "rows": yrows}
    return {"by_election": by_election, "by_year": by_year, "population": int(len(p))}


def reg_e_flow(fr, accttype, out_dir, size=(5.6, 3.5)):
    key = f"reg_e_flow_{accttype.lower()}"
    p = fr.open_accounts(accttype)
    if p.empty:
        return R.skipped(key, "Reg E flow", "no open accounts")
    p = p.assign(regE=p["RegEOptinvalue"].astype(str).str.upper().str.strip(), items=_num(p["items365"]).fillna(0),
                 dec=_num(p["declines_365"]).fillna(0))
    cols = [v for v in ("Y", "N", "D") if (p["regE"] == v).any()]
    items = [float(p.loc[p["regE"] == v, "items"].sum()) for v in cols]
    decl = [float(p.loc[p["regE"] == v, "dec"].sum()) for v in cols]
    if sum(items) + sum(decl) == 0:
        return R.skipped(key, "Reg E flow", "no items or declines")
    fig, ax = R.new_fig(*size)
    tot = [a + b for a, b in zip(items, decl)]
    scale = 1.0 / max(tot)
    bw = 0.32

    def band(i, which):            # (y0, y1) of the stratum, items on the bottom, declines above
        base = 0.0 if which == "items" else items[i] * scale
        val = (items[i] if which == "items" else decl[i]) * scale
        return base, base + val
    for which, col in (("items", R.TEAL), ("decl", R.NAVY)):
        wh = "items" if which == "items" else "decl"
        for i in range(len(cols) - 1):
            a0, a1 = band(i, wh)
            b0, b1 = band(i + 1, wh)
            xs = np.linspace(i + bw, i + 1 - bw, 40)
            t = (1 - np.cos((xs - (i + bw)) / (1 - 2 * bw) * np.pi)) / 2
            ax.fill_between(xs, a0 + (b0 - a0) * t, a1 + (b1 - a1) * t, color=col, alpha=0.35, linewidth=0)
        for i in range(len(cols)):
            y0, y1 = band(i, wh)
            ax.add_patch(plt.Rectangle((i - bw, y0), 2 * bw, y1 - y0, color=col))
            v = (items if which == "items" else decl)[i]
            if y1 - y0 > 0.07:
                ax.text(i, (y0 + y1) / 2, f"{v / 1000:,.0f}K" if v >= 1000 else f"{v:,.0f}", ha="center", va="center",
                        color="white", fontsize=11, fontweight="bold")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([f"Reg E: {c}" for c in cols], fontsize=10.5, color=R.TICK)
    ax.set_yticks([])
    ax.set_xlim(-0.6, len(cols) - 0.4)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(R.MUTED)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=R.NAVY, label="Debit declines, 365 days"), Patch(color=R.TEAL, label="NSF/OD items, 365 days")],
              loc="upper center", ncol=2, frameon=False, fontsize=9.5, labelcolor=R.TICK, bbox_to_anchor=(0.5, 1.1))
    fig.tight_layout()
    path = R.save(fig, out_dir, key)
    return ChartResult(key, "Items and declines by Reg E election", path,
                       numbers={"elections": cols, "items_365": dict(zip(cols, items)), "declines_365": dict(zip(cols, decl))},
                       notes=["The hand-built deck's alluvial is an R figure whose strata are not in the extract; this "
                              "shows the two measures the extract does carry, items and declines, by Reg E election."])


# ═════════════════════════════ debit declines ═════════════════════════════
DECLINE_SEGMENTS = [("1 to 6", 1, 6), ("7 to 12", 7, 12), ("13 to 18", 13, 18), ("19 to 24", 19, 24),
                    ("25 to 30", 25, 30), ("31 to 36", 31, 36), ("37 to 42", 37, 42), ("43 to 48", 43, 48),
                    ("> 48", 49, None)]
SCORE_BANDS = [("Zero Score", None, 0), ("1-100", 1, 100), ("101-250", 101, 250), ("251-500", 251, 500),
               ("501-750", 501, 750), ("751-1000", 751, 1000), ("1001-1250", 1001, 1250),
               ("1251-1500", 1251, 1500), ("1501-1750", 1501, 1750), ("1751-2000", 1751, 2000),
               ("2001-2500", 2001, 2500), ("2501+", 2501, None)]


def debit_decline_tables(fr, accttype, ref=None):
    """(segmentation table, score-band table) for one account type, or None."""
    p = fr.open_accounts(accttype)
    if p.empty:
        return None
    p = p.assign(can=_yes(p["CanOverdraft"]), regE=p["RegEOptinvalue"].astype(str).str.upper().str.strip(),
                 dec=_num(p["declines_365"]).fillna(0), lim=_num(p["ODLimit"]).fillna(0))
    # segmentation: open, can overdraft, not opted in to Reg E, with at least one decline
    seg = p[p["can"] & (p["regE"] != "Y") & (p["dec"] > 0)]
    rows = []
    for name, lo, hi in DECLINE_SEGMENTS:
        s = seg[(seg["dec"] >= lo) & ((seg["dec"] <= hi) if hi is not None else True)]
        if s.empty:
            continue
        rows.append([name, f"{len(s):,}", f"{_num(s['items365']).sum():,.0f}", f"{_num(s['PD_365']).sum():,.0f}",
                     money(_num(s["CollectedFees365"]).sum()), money(_num(s["Refund_Amt_365"]).sum()),
                     f"{_num(s['DepCount33']).mean():.1f}", money(_num(s["DepAmt33"]).mean())])
    if rows:
        s = seg
        rows.append(["Total", f"{len(s):,}", f"{_num(s['items365']).sum():,.0f}", f"{_num(s['PD_365']).sum():,.0f}",
                     money(_num(s["CollectedFees365"]).sum()), money(_num(s["Refund_Amt_365"]).sum()),
                     f"{_num(s['DepCount33']).mean():.1f}", money(_num(s["DepAmt33"]).mean())])
    t1 = {"headers": ["Annual Decline Segment", "Accounts", "Items Presented (365)", "Paid Items (365)",
                      "Collected Fees (365)", "Refunded Fees (365)", "Avg Deposit Count (33 days)",
                      "Avg Deposit Amount (33 days)"], "rows": rows}
    # score-band table from the decline file, joined to the accounts
    t2 = None
    if fr.dd is not None and len(fr.dd):
        dd = fr.dd
        lo90 = fr.asof - pd.Timedelta(days=90)
        a1 = p.set_index("acctid")
        j = dd[dd["acctid"].isin(a1.index)].copy()
        if len(j):
            j["lim"] = j["acctid"].map(a1["lim"])
            j["amt"] = _num(j["transaction_amount"])
            j["last90"] = j["decline_date"] >= lo90
            rows2 = []
            for name, lo, hi in SCORE_BANDS:
                lim = j["lim"]
                m = (lim == 0) if lo is None else ((lim >= lo) & ((lim <= hi) if hi is not None else True))
                s = j[m]
                if s.empty:
                    continue
                accts = a1.loc[s["acctid"].unique()]
                rows2.append([name, f"{s['acctid'].nunique():,}", f"{int((accts['items365'] > 0).sum()):,}",
                              f"{int(s['last90'].sum()):,}", money(s["amt"].median(), 2),
                              f"{_num(accts['items365']).sum():,.0f}", money(_num(accts["DepAmt33"]).median(), 2)])
            t2 = {"headers": ["ILS Limit Band", "Accounts Declined", "Of Which NSF/OD Users", "Declines, Last 90 Days",
                              "Median Declined Amount", "NSF/OD Items (365)", "Median 33-Day Deposits"], "rows": rows2}
    return {"segmentation": t1, "score_bands": t2, "population": int(len(seg))}
