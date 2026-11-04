"""
The narrative spine of the ILS Program Analysis deck: where the ILS limit is CALCULATING, where it is
PERFORMING, and where it PULLS BACK (Aaron, 2026-11-04). One message per slide, a plain headline that states
the finding, one chart, up to three headline figures, a one-line "how to read it", and a one-line speaker note
(the sentence the presenter says first) ahead of the Source line.

NEW in the RPE port. Definitions, as Aaron gave them:

  * ELIGIBLE for overdraft / receives an ILS limit: decided by the Overdraft Status Code. The matrix validation
    extract's OD STATUS CODE MAPPING says what each code means and whether it can overdraft; a blank code is
    "Active" and can overdraft. CanOverdraft and ODLimit are NOT the gate.
  * CURED: a negative balance reaches $0 or above within 60 days of the notice (`Next_Positive_Date`). Not cured:
    it does not within 60 days. Used on every slide here. The Scoring Summary slides use a separate 40-day
    default and are not drawn in this narrative; the Data Notes slide states both.
  * PULLBACK: the account's current limit is below its own earlier maximum limit (`ODLimit < MaxODLimit`).
    The extracts carry NO daily limit history, so the slide cannot say WHEN a limit was lowered or why, and
    says so. No dollar savings are claimed: the slide shows rates only.
  * NSF = collected fees on returned items (PD 0), OD = collected fees on paid items (PD 1); fee revenue is the
    collected fees as recorded, not netted for refunds.
  * Charge-offs against growth: accounts by `Chargeoff_Date` month against accounts opened that month, complete
    months only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import shapes
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from . import client_slides as CS
from . import r_common as R
from . import theme as T
from .r_common import ChartResult, plt, money, pct
from .r_fees import _month_range, movement_phrase

CURE_DAYS = 60
TITLE_NOUN = {"limit": "ILS limit", "deposits": "33-day deposits", "age": "days on book"}
LIMIT_BANDS = [("$0", 0, 0), ("$1-$250", 1, 250), ("$251-$500", 251, 500), ("$501-$1,000", 501, 1000),
               ("$1,001-$1,500", 1001, 1500), ("$1,501-$2,000", 1501, 2000), ("Over $2,000", 2001, None)]
AGE_BANDS = [("Under 31 days", 0, 30), ("31-180 days", 31, 180), ("181 days-1 yr", 181, 365), ("1-2 yrs", 366, 730),
             ("2-5 yrs", 731, 1825), ("5-10 yrs", 1826, 3650), ("Over 10 yrs", 3651, None)]
DEP_BANDS = [("$100 or less", None, 100), ("$101-$500", 101, 500), ("$501-$1,000", 501, 1000), ("$1,001-$2,000", 1001, 2000),
             ("$2,001-$4,000", 2001, 4000), ("$4,001-$8,000", 4001, 8000), ("Over $8,000", 8001, None)]


def _band(series, bands):
    out = pd.Series(-1, index=series.index)
    for i, (_, lo, hi) in enumerate(bands):
        m = pd.Series(True, index=series.index)
        if lo is not None:
            m &= series >= lo
        if hi is not None:
            m &= series <= hi
        out[m & (out < 0)] = i
    return out


def _slide(dk, cfg, fr, title, sub, say, *, section, kinds=("za", "zt"), extra=""):
    s = dk.content(title, sub, section=section, source=CS._src(cfg, fr, *kinds, extra=extra))
    s.notes_slide.notes_text_frame.text = f"Say first: {say}\n" + s.notes_slide.notes_text_frame.text
    return s


def _tiles(slide, items, L=8.45, W=4.38, T0=1.80):
    h = 1.12
    for i, (v, lab) in enumerate(items[:3]):
        shapes.tile(slide, L, T0 + i * (h + 0.18), W, h, v, lab, small_label=True)


def _read(slide, text, L=8.45, W=4.38, T0=5.55):
    T.band_real(slide, L, T0, W, "HOW TO READ IT", h=0.34)
    T.bullets_real(slide, L, T0 + 0.42, W, 0.75, [text], size=14, min_size=11)


def _columns(vals, labels, ns, out_dir, key, *, size=(7.8, 4.6), ylab, fmt, hi=None, ymax=None):
    fig, ax = R.new_fig(*size)
    cols = [R.NAVY] * len(vals)
    if hi is not None:
        cols[hi] = R.ORANGE
    ax.bar(range(len(vals)), vals, color=cols, width=0.62)
    for i, v in enumerate(vals):
        ax.text(i, v + (ymax or max(vals)) * 0.015, fmt(v), ha="center", va="bottom", fontsize=10.5, color=R.NAVY, fontweight="bold")
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels([f"{l}\n(n={n:,})".replace("$", r"\$") for l, n in zip(labels, ns)], fontsize=9, color=R.TICK)
    R.style_axes(ax)
    ax.set_ylabel(ylab, fontsize=10.5, color=R.TICK)
    if ymax:
        ax.set_ylim(0, ymax)
    else:
        ax.set_ylim(0, max(vals) * 1.15)
    fig.tight_layout()
    return R.save(fig, out_dir, key)


# ═════════════════════════════ calculating ═════════════════════════════════
def _status_map(S):
    from . import matrix_data as MD
    m = {}
    for r in MD.section(S, "OD STATUS CODE MAPPING") if S else []:
        code = str(r.get("STATUS_CODE", "")).strip()
        m[code if code and code.upper() != "NULL" else ""] = (str(r.get("DESCRIPTION", "")).strip() or "Status " + code,
                                                              MD.is_true(r.get("CAN_OVERDRAFT")))
    return m


def add_calculating(dk, cfg, fr, S, *, section, progress=None):
    notes = []
    t = "Personal"
    o = fr.open_accounts(t)
    if o.empty:
        return ["Calculating slides skipped: no open personal accounts."]
    smap = _status_map(S)
    if not smap:
        notes.append("Which accounts receive an ILS limit: the matrix validation extract has no OD STATUS CODE MAPPING, so the status codes cannot be read; the eligibility slide was skipped.")
    else:
        code = pd.to_numeric(o["odstatuscode"], errors="coerce").map(lambda v: "" if pd.isna(v) else str(int(v)))
        desc = code.map(lambda c: smap.get(c, (f"Status {c}", False))[0])
        elig = code.map(lambda c: smap.get(c, ("", False))[1])
        n, ne = len(o), int(elig.sum())
        by = desc.groupby(desc).size().sort_values(ascending=False)
        rows = []
        for d_, k in by.items():
            can = any(v[0] == d_ and v[1] for v in smap.values())
            rows.append([d_, f"{k:,}", "Yes" if can else "No"])
        main = rows[:7]
        if len(rows) > 7:
            rest = sum(int(r[1].replace(",", "")) for r in rows[7:])
            main.append([f"All other ({len(rows) - 7} statuses)", f"{rest:,}", "No"])
        s = _slide(dk, cfg, fr, f"{ne / n * 100:.0f}% of open personal accounts are eligible for an ILS limit",
                   f"{n:,} open personal accounts by Overdraft Status Code, as of {fr.asof:%B} {fr.asof.day}, {fr.asof.year}.",
                   f"ILS gives a limit to accounts whose status allows overdraft; the rest are held out by their status.",
                   section=section, kinds=("za", "mx"),
                   extra="Eligible = the OD Status Code can overdraft, per the OD STATUS CODE MAPPING in the matrix validation extract.")
        CS.table(s, {"headers": ["Overdraft status", "Open accounts", "Can overdraft"], "rows": main}, 0.5, 1.80, 7.6, 4.7, max_fs=14)
        _tiles(s, [(f"{ne:,}", "Eligible open accounts"), (f"{n - ne:,}", "Held out by status"), (f"{ne / n * 100:.1f}%", "Share eligible")])
        _read(s, "Each row is one status. 'Can overdraft' is the matrix's own setting for that status.")
        dk.sidecars.append({"key": "calc_eligibility", "title": "Open accounts by overdraft status", "numbers": {"open": n, "eligible": ne, "rows": rows}})
        el = o[elig.to_numpy()]
        lim = pd.to_numeric(el["ODLimit"], errors="coerce").fillna(0)
        b = _band(lim, LIMIT_BANDS)
        ns = [int((b == i).sum()) for i in range(len(LIMIT_BANDS))]
        key = "calc_limit_distribution"
        png = _columns([x / max(1, sum(ns)) * 100 for x in ns], [l for l, _, _ in LIMIT_BANDS], ns, dk.chart_dir, key,
                       ylab="Share of eligible accounts", fmt=lambda v: f"{v:.0f}%", hi=int(np.argmax(ns)))
        top = int(np.argmax(ns))
        s2 = _slide(dk, cfg, fr, f"Most eligible accounts sit at {LIMIT_BANDS[top][0]}: {ns[top] / max(1, sum(ns)) * 100:.0f}% of them",
                    f"Current ILS limit of the {len(el):,} eligible open personal accounts; $0 is its own band.",
                    "This is how the limits are spread today across the accounts that can have one.", section=section)
        T.image_real(s2, png, 0.5, 1.75, 7.8, 4.75)
        _tiles(s2, [(f"{int(lim.median()):,}".join(["$", ""]), "Median limit, eligible accounts"), (f"{ns[0]:,}", "Eligible accounts at $0"),
                    (f"{int((lim > 0).sum()):,}", "Eligible accounts with a limit")])
        _read(s2, "Each bar is a limit band; the tallest is orange. n is the number of accounts in the band.")
        dk.sidecars.append({"key": key, "title": "Limit distribution", "png": key + ".png", "numbers": {"bands": [l for l, _, _ in LIMIT_BANDS], "accounts": ns}})
        u = pd.to_numeric(el["UniqueODLimit"], errors="coerce").fillna(1)
        ch = int((u > 1).sum())
        s3 = _slide(dk, cfg, fr, f"{ch / max(1, len(el)) * 100:.0f}% of eligible accounts have had more than one limit",
                    "Distinct limits each eligible open personal account has carried.",
                    "Limits are recalculated, so many accounts have already moved at least once.", section=section)
        grp = [("1", (u == 1).sum()), ("2", (u == 2).sum()), ("3 to 5", u.between(3, 5).sum()), ("6 or more", (u >= 6).sum())]
        png3 = _columns([g / max(1, len(el)) * 100 for _, g in grp], [a for a, _ in grp], [int(g) for _, g in grp], dk.chart_dir,
                        "calc_limit_changes", ylab="Share of eligible accounts", fmt=lambda v: f"{v:.0f}%")
        T.image_real(s3, png3, 0.5, 1.75, 7.8, 4.75)
        _tiles(s3, [(f"{ch:,}", "Accounts with 2+ limits"), (f"{float(u.median()):.0f}", "Median distinct limits"), (f"{int(u.max()):,}", "Most limits on one account")])
        _read(s3, "Bars show how many distinct limits an account has carried. The extract has the count, not the dates.")
    return notes


# ═════════════════════════════ performing ═════════════════════════════════
def _cure_frame(fr, accttype="Personal"):
    n = fr.notices
    if n is None:
        return None
    lo, hi = fr.scoring_window()
    w = n[(n["accttype"] == accttype) & (n["noticedate"] >= lo) & (n["noticedate"] <= hi)].copy()
    w["cured"] = w["days_to_positive"].between(0, CURE_DAYS)
    return w, lo, hi


def add_performing(dk, cfg, fr, S, *, section, progress=None):
    cf = _cure_frame(fr)
    if cf is None:
        return ["Performing slides skipped: no ZTrend file."]
    w, lo, hi = cf
    overall = w["cured"].mean() * 100
    notes = []
    specs = [("limit", "ILS limit in force at the notice", w["limit"].fillna(0.0), LIMIT_BANDS,
              "Limits go up and cure rates should follow: higher limits go to accounts the matrix expects to repay."),
             ("deposits", "33-day deposits at the notice", w["deptotal33"].fillna(0.0), DEP_BANDS,
              "Accounts with more deposits coming in cure more often."),
             ("age", "Days on book at the notice", w["age_days"], AGE_BANDS,
              "New accounts cure least; the rate climbs with age.")]
    for key, label, ser, bands, say in specs:
        ok = ser.notna()
        b = _band(ser[ok], bands)
        sub = w[ok]
        rates, ns = [], []
        for i in range(len(bands)):
            m = (b == i).to_numpy()
            ns.append(int(m.sum()))
            rates.append(float(sub["cured"].to_numpy()[m].mean() * 100) if m.sum() else 0.0)
        keep = [i for i, n_ in enumerate(ns) if n_ >= 50]
        if len(keep) < 3:
            notes.append(f"Cure rate by {label}: skipped, fewer than three bands with 50 or more notices.")
            continue
        r_ = [rates[i] for i in keep]
        lab = [bands[i][0] for i in keep]
        n_ = [ns[i] for i in keep]
        k = f"perform_cure_{key}"
        png = _columns(r_, lab, n_, dk.chart_dir, k, ylab="Share of notices cured within 60 days", fmt=lambda v: f"{v:.0f}%",
                       hi=int(np.argmin(r_)), ymax=105)
        s = _slide(dk, cfg, fr, f"Cure rate runs from {min(r_):.0f}% to {max(r_):.0f}% by {TITLE_NOUN[key]}",
                   f"Personal accounts: share of notices where the negative balance reached $0 or more within {CURE_DAYS} days, "
                   f"notices {str(lo)[:10]} to {str(hi)[:10]}.", say, section=section,
                   extra=f"Cured = Next_Positive_Date within {CURE_DAYS} days of the notice. A notice is one account on one date.")
        T.image_real(s, png, 0.5, 1.75, 7.8, 4.75)
        _tiles(s, [(f"{overall:.0f}%", "Cured, all notices"), (f"{max(r_):.0f}%", f"Highest band: {lab[int(np.argmax(r_))]}"),
                   (f"{min(r_):.0f}%", f"Lowest band (orange): {lab[int(np.argmin(r_))]}")])
        _read(s, f"Each bar is the share of notices cured within {CURE_DAYS} days. A cure means the balance reached $0 or more.")
        dk.sidecars.append({"key": k, "title": f"Cure rate by {label}", "png": k + ".png",
                            "numbers": {"bands": lab, "cure_rate_pct": r_, "notices": n_, "window": [str(lo)[:10], str(hi)[:10]], "cure_days": CURE_DAYS}})
    return notes


# ═════════════════════════════ fee mix and charge-offs ═════════════════════
def add_nsf_share(dk, cfg, fr, S, *, section, progress=None):
    z = fr.zt_type("Personal")
    if z is None or z.empty:
        return ["NSF share of fee revenue skipped: no ZTrend file."]
    mons = _month_range(fr, 24)
    ym = z["noticedate"].dt.to_period("M")
    nsf, od = [], []
    for m in mons:
        s_ = z[ym == m]
        nsf.append(float(s_.loc[s_["PD"] == 0, "CollectedFees"].sum()))
        od.append(float(s_.loc[s_["PD"] == 1, "CollectedFees"].sum()))
    share = [a / (a + b) * 100 if a + b else np.nan for a, b in zip(nsf, od)]
    labels = [R.periods.mon_yy(f"{m.year}-{m.month:02d}") for m in mons]
    fig, ax = R.new_fig(7.8, 4.6)
    ax.plot(range(len(share)), share, color=R.NAVY, linewidth=2.8, marker="o", markersize=4)
    ax.scatter([len(share) - 1], [share[-1]], color=R.ORANGE, s=50, zorder=5)
    ax.annotate(f"{labels[-1]}: {share[-1]:.1f}% of collected fees\nwere on returned items (NSF)", (len(share) - 1, share[-1]), (-12, 28),
                textcoords="offset points", ha="right", fontsize=10, color=R.NAVY, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=R.ORANGE, lw=1), arrowprops=dict(arrowstyle="-", color=R.ORANGE))
    ax.set_xticks(range(0, len(labels), 3))
    ax.set_xticklabels(labels[::3], rotation=45, ha="right", fontsize=10, color=R.TICK)
    R.style_axes(ax)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_ylabel("NSF share of collected fees", fontsize=10.5, color=R.TICK)
    ax.set_ylim(0, max(np.nanmax(share) * 1.6, 5))
    fig.tight_layout()
    png = R.save(fig, dk.chart_dir, "mix_nsf_share")
    cur, old = share[-1], share[-13]
    ph = movement_phrase(cur, old, lambda v: f"{v:.1f}%")
    s = _slide(dk, cfg, fr, f"Returned items bring in {cur:.0f}% of personal fee revenue",
               f"NSF fees (returned items) as a share of all collected fees, by month, {labels[0]} to {labels[-1]}.",
               "Most fee revenue is on items ILS lets through; the NSF share is the rest.", section=section, kinds=("zt", "za"),
               extra="NSF = collected fees on returned items (PD 0); OD = collected fees on paid items (PD 1); not netted for refunds. Complete months only.")
    T.image_real(s, png, 0.5, 1.75, 7.8, 4.75)
    _tiles(s, [(f"{cur:.1f}%", f"NSF share, {labels[-1]}"), (f"{old:.1f}%", f"NSF share, {labels[-13]}"), (money(nsf[-1]), f"NSF fees, {labels[-1]}")])
    _read(s, f"Each point is one month. {labels[-1]} is {ph} in {labels[-13]}.")
    dk.sidecars.append({"key": "mix_nsf_share", "title": "NSF share of fee revenue", "png": "mix_nsf_share.png",
                        "numbers": {"months": labels, "nsf_fees": nsf, "od_fees": od, "nsf_share_pct": share}})
    return []


def add_chargeoffs(dk, cfg, fr, S, *, section, progress=None):
    za = fr.za
    d = za[za["accttype"] == "Personal"]
    mons = _month_range(fr, 12)
    co = pd.to_datetime(d["Chargeoff_Date"], errors="coerce").dt.to_period("M")
    op = pd.to_datetime(d["opendate"], errors="coerce").dt.to_period("M")
    cos = [int((co == m).sum()) for m in mons]
    ops = [int((op == m).sum()) for m in mons]
    if sum(cos) == 0:
        return ["Charge-offs against account growth skipped: no charge-off dates in the last 12 months."]
    labels = [R.periods.mon_yy(f"{m.year}-{m.month:02d}") for m in mons]
    fig, ax = R.new_fig(7.8, 4.6)
    x = np.arange(len(mons))
    ax.bar(x - 0.2, ops, 0.4, color=R.NAVY, label="Accounts opened")
    ax.bar(x + 0.2, cos, 0.4, color=R.ORANGE, label="Accounts charged off")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10, color=R.TICK)
    R.style_axes(ax)
    ax.legend(frameon=False, fontsize=10, labelcolor=R.TICK, loc="upper left")
    ax.set_ylabel("Accounts per month", fontsize=10.5, color=R.TICK)
    fig.tight_layout()
    png = R.save(fig, dk.chart_dir, "mix_chargeoffs_growth")
    ratio = sum(cos) / max(1, sum(ops)) * 100
    s = _slide(dk, cfg, fr, f"In 12 months {sum(cos):,} accounts charged off and {sum(ops):,} were opened",
               f"Personal accounts by month, {labels[0]} to {labels[-1]} (12 complete months).",
               "Charge-offs are a small share of the accounts the program brings in each month.", section=section,
               extra="Charge-offs counted by Chargeoff_Date month; accounts opened by opendate month; complete months only.")
    T.image_real(s, png, 0.5, 1.75, 7.8, 4.75)
    _tiles(s, [(f"{sum(cos):,}", "Accounts charged off, 12 months"), (f"{sum(ops):,}", "Accounts opened, 12 months"), (f"{ratio:.0f}%", "Charge-offs per account opened")])
    _read(s, "Navy is accounts opened and orange is accounts charged off, month by month.")
    dk.sidecars.append({"key": "mix_chargeoffs_growth", "title": "Charge-offs against account growth", "png": "mix_chargeoffs_growth.png",
                        "numbers": {"months": labels, "opened": ops, "charged_off": cos}})
    return []


# ═════════════════════════════ pulling back ═════════════════════════════════
PULL_BANDS = [("No change", None), ("Lowered by $1-$250", 250), ("Lowered by $251-$500", 500),
              ("Lowered by $501-$1,000", 1000), ("Lowered by over $1,000", None)]


def add_pullback(dk, cfg, fr, S, *, section, progress=None):
    """How many eligible open accounts have been pulled back, and by how much.

    NOT shown: what happened to those accounts afterwards. In the extract an account's earlier maximum limit
    (MaxODLimit) is a recent-window figure: 90% of the personal accounts charged off in the last 12 months carry
    a $0 earlier maximum, so the limit they had before charge-off is not in the extract and a charge-off
    comparison of 'lowered' against 'stayed' would compare nothing. The slide says so."""
    o = fr.open_accounts("Personal")
    if "MaxODLimit" not in o.columns:
        return ["Pulling back skipped: the ZAccounts extract has no MaxODLimit column."]
    smap = _status_map(S)
    code = pd.to_numeric(o["odstatuscode"], errors="coerce").map(lambda v: "" if pd.isna(v) else str(int(v)))
    elig = code.map(lambda c: smap.get(c, ("", False))[1]) if smap else pd.Series(True, index=o.index)
    o = o[elig.to_numpy()]
    cur = pd.to_numeric(o["ODLimit"], errors="coerce")
    mx = pd.to_numeric(o["MaxODLimit"], errors="coerce")
    ok = cur.notna() & mx.notna() & (mx > 0)
    cur, mx = cur[ok], mx[ok]
    if len(cur) < 100:
        return ["Pulling back skipped: fewer than 100 eligible open accounts carry an earlier maximum limit."]
    drop = (mx - cur).clip(lower=0)
    n = len(cur)
    cats = [("No change", int((drop == 0).sum())), ("Lowered by $1-$250", int(drop.between(1, 250).sum())),
            ("Lowered by $251-$500", int(drop.between(251, 500).sum())), ("Lowered by $501-$1,000", int(drop.between(501, 1000).sum())),
            ("Lowered by over $1,000", int((drop > 1000).sum()))]
    low = n - cats[0][1]
    removed = int(((cur == 0) & (mx > 0)).sum())
    med = float(drop[drop > 0].median()) if low else 0.0
    png = _columns([c / n * 100 for _, c in cats], [l.replace("Lowered by ", "by ") if l != "No change" else l for l, _ in cats], [c for _, c in cats],
                   dk.chart_dir, "pullback_limits", ylab="Share of eligible open accounts", fmt=lambda v: f"{v:.0f}%", hi=None)
    s = _slide(dk, cfg, fr, f"{low / n * 100:.0f}% of eligible accounts have been pulled back from a higher limit",
               f"{n:,} eligible open personal accounts: current limit against the account's own earlier maximum limit.",
               "ILS lowers a limit when an account's behaviour calls for it; this is how many accounts and by how much.",
               section=section, kinds=("za", "mx"),
               extra="Lowered = ODLimit below MaxODLimit. The extracts carry no daily limit history, so when and why a limit was lowered is not shown, "
                     "and MaxODLimit is a recent-window figure: charged-off accounts show a $0 earlier maximum, so charge-offs cannot be compared "
                     "between lowered and unchanged accounts. No savings are claimed.")
    T.image_real(s, png, 0.5, 1.75, 7.8, 4.75)
    _tiles(s, [(f"{low:,}", "Accounts with a lowered limit"), (f"{removed:,}", "Of which now at $0"), (f"${med:,.0f}", "Median reduction")])
    _read(s, "Each bar is the size of the reduction. The extract has no daily history, so it cannot show when or why, or what followed.")
    dk.sidecars.append({"key": "pullback_limits", "title": "Pulling back", "png": "pullback_limits.png",
                        "numbers": {"eligible_with_earlier_max": n, "bands": dict(cats), "lowered": low, "now_zero": removed, "median_reduction": med,
                                    "identified_by": "ODLimit < MaxODLimit", "limit_history": "not in the extracts",
                                    "outcome_comparison": "blocked: charged-off accounts carry a $0 earlier maximum"}})
    return ["Pulling back: 'lowered' is the current limit below the account's own earlier maximum; the extracts have no daily limit history, so timing and cause "
            "(daily recalculation, override, trend) and what followed are not shown, and no dollar savings are claimed."]
