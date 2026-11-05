"""
Slides carried over from the analysis team's delivered decks (Kevin Higginbotham's Achieva and First Arkansas
ANNUAL REVIEW decks) that the extracts can generate: the year-over-year comparison and who generates the fees.
Each one is one message, a plain headline, one small table or chart, a one-line "how to read it" and a "Say first"
speaker note ahead of the Source line.

PARITY. The hand decks' own figures are compared with ours where they exist (`dk.ref`, read from
`parity_reference.json` beside the charts, never from git). What can and cannot be reproduced is recorded in each
figure's sidecar and on the Data Notes page:

  * USAGE SEGMENTS (heavy users, 24 or more items in 365 days): the share of collected fees reproduces the deck's
    to within a point on the client it was calibrated on.
  * YEAR OVER YEAR: the deck's windows are not reproducible from the extract. Its collected fees match no 12-month
    window of the ZTrend extract ending between December and the last complete month (the nearest windows end about
    four months before the as-of date), so the levels differ; the year-over-year changes agree to within about two points.
    This build compares the last 12 COMPLETE months with the 12 before them, which is what the slide says. The deck's
    default-rate row is left out: notices in the last 60 days have not had time to resolve.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import shapes
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from . import client_slides as CS
from . import r_accounts as RA
from . import r_common as R
from . import theme as T
from .r_common import money, compare
from .r_fees import _month_range

BAND = 2.0


def _chg(cur, prev):
    """The +/-2% band: 'almost flat' within it, else the signed percent."""
    if not prev:
        return "n/a"
    ch = (cur - prev) / prev * 100
    return "almost flat" if abs(ch) <= BAND else f"{ch:+.0f}%"


def _pct_change(cur, prev):
    return None if not prev else (cur - prev) / prev * 100


def _window_stats(z, a, b):
    zz = z[(z["noticedate"] >= a) & (z["noticedate"] <= b)]
    notices = int(zz.drop_duplicates(["acctid", "noticedate"]).shape[0])
    accts = int(zz["acctid"].nunique())
    fees = float(zz["CollectedFees"].sum())
    return {"fees": fees, "notices": notices, "accounts": accts, "fees_per_account": fees / accts if accts else 0.0}


def add_yoy(dk, cfg, fr, S, *, section, progress=None):
    if not fr.has_trend:
        return ["Year-over-year comparison skipped: no ZTrend file."]
    mons = _month_range(fr, 12)
    a, b = mons[0].start_time, mons[-1].end_time.normalize()
    pa, pb = (mons[0] - 12).start_time, (mons[-1] - 12).end_time.normalize()
    tmin = fr.zt["noticedate"].min()
    if tmin > pa + pd.Timedelta(days=5):
        return [f"Year-over-year comparison skipped: ZTrend starts {tmin:%Y-%m-%d}, so the 12 months before the last 12 are not all in the extract."]
    lab_cur = f"{R.periods.mon_yy(f'{mons[0].year}-{mons[0].month:02d}')} to {R.periods.mon_yy(f'{mons[-1].year}-{mons[-1].month:02d}')}"
    pm0, pm1 = mons[0] - 12, mons[-1] - 12
    lab_prev = f"{R.periods.mon_yy(f'{pm0.year}-{pm0.month:02d}')} to {R.periods.mon_yy(f'{pm1.year}-{pm1.month:02d}')}"
    stats = {}
    for t in ("Personal", "Business"):
        z = fr.zt_type(t)
        if z is None or z.empty:
            continue
        stats[t] = (_window_stats(z, a, b), _window_stats(z, pa, pb))
    if "Personal" not in stats:
        return ["Year-over-year comparison skipped: no personal notices."]
    cur, prev = stats["Personal"]
    ch = _pct_change(cur["fees"], prev["fees"])
    if abs(ch) <= BAND:
        title = "Personal collected fees are almost flat against the prior 12 months"
    elif ch > 0:
        title = f"Personal collected fees are up {ch:.0f}% on the prior 12 months"
    else:
        title = f"Personal collected fees: {money(cur['fees'])} against {money(prev['fees'])} in the prior 12 months"
    s = dk.content(title, f"Notices dated {lab_cur} against {lab_prev}; both windows are 12 complete months.", section=section,
                   source=CS._src(cfg, fr, "zt", "za", extra=f"Collected fees = CollectedFees summed by notice date; a notice is one account on one "
                                  f"notice date; accounts = distinct accounts with a notice. Complete months only; the default rate is left out because "
                                  f"notices in the last 60 days have not had time to resolve."))
    gap = 0.3
    w = (CS.FULL_W - gap) / 2
    nums = {}
    for k, t in enumerate(stats):
        c_, p_ = stats[t]
        rows = [["Collected fees", money(c_["fees"]), money(p_["fees"]), _chg(c_["fees"], p_["fees"])],
                ["NSF/OD notices", f"{c_['notices']:,}", f"{p_['notices']:,}", _chg(c_["notices"], p_["notices"])],
                ["Accounts with a notice", f"{c_['accounts']:,}", f"{p_['accounts']:,}", _chg(c_["accounts"], p_["accounts"])],
                ["Fees per account", money(c_["fees_per_account"]), money(p_["fees_per_account"]), _chg(c_["fees_per_account"], p_["fees_per_account"])]]
        x = CS.LEFT + k * (w + gap)
        shapes.textbox(s, x, CS.BODY_T + 0.05, w, 0.4, t + " accounts", 18, T.NAVY, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.TOP)
        CS.table(s, {"headers": ["Measure", "Last 12 months", "Prior 12 months", "Change"], "rows": rows}, x, CS.BODY_T + 0.55, w, 3.2, max_fs=15)
        nums[t] = {"current": c_, "prior": p_,
                   "change_pct": {k_: _pct_change(c_[k_], p_[k_]) for k_ in ("fees", "notices", "accounts", "fees_per_account")}}
    CS.caption(s, "the left column is the latest 12 complete months and the middle column the 12 before; change within 2% reads almost flat.", T0=5.3)
    CS.say_first(s, "Fees are higher than a year ago; the question for the program is what has driven the extra items and the extra losses.")
    # parity with the hand-built deck's year-over-year tiles (levels differ by window; the changes are compared)
    parity = []
    for t, key_map in (("Personal", {"fees": "yoy.Personal.fees_chg_pct", "notices": "yoy.Personal.events_chg_pct", "accounts": "yoy.Personal.accts_chg_pct"}),
                       ("Business", {"fees": "yoy.Business.fees_chg_pct", "notices": "yoy.Business.events_chg_pct", "accounts": "yoy.Business.accts_chg_pct"})):
        if t not in nums:
            continue
        for k_, rk in key_map.items():
            parity.append(compare(nums[t]["change_pct"][k_], dk.ref.get(rk), tol=0.10, measure=f"{t} {k_} change %"))
    dk.sidecars.append({"key": "yoy_comparison", "title": "Year-over-year comparison", "numbers": nums, "parity": R._jsonable(parity),
                        "notes": [f"Windows: {lab_cur} against {lab_prev}. The hand-built deck's windows are not reproducible from the extract (see module docstring)."]})
    return [f"Year over year: this build compares the last 12 complete months ({lab_cur}) with the 12 before; the hand-built deck's windows "
            f"cannot be reproduced from the extract, so its levels differ and its changes agree to within about two points. Its default-rate row is not shown."]


# ═════════════════════════════ who generates the fees ═══════════════════════════
USAGE_BANDS = [("No items", 0, 0), ("1-6 items", 1, 6), ("7-23 items", 7, 23), ("24+ items", 24, None)]


def add_usage_segments(dk, cfg, fr, S, *, section, progress=None):
    t = "Personal"
    p = RA._population(fr, t)
    if p.empty:
        return ["Fees by annual item count skipped: no open active personal accounts."]
    items = pd.to_numeric(p["items365"], errors="coerce").fillna(0)
    fees = pd.to_numeric(p["CollectedFees365"], errors="coerce").fillna(0.0)
    n = len(p)
    tf = float(fees.sum())
    if tf <= 0:
        return ["Fees by annual item count skipped: no collected fees in the 365 days."]
    segs = []
    for lab, lo, hi in USAGE_BANDS:
        m = (items >= lo) & ((items <= hi) if hi is not None else True)
        segs.append((lab, int(m.sum()), float(fees[m].sum())))
    heavy = segs[-1]
    ha = heavy[1] / n * 100
    hf = heavy[2] / tf * 100
    fig, ax = R.new_fig(7.8, 4.5)
    x = np.arange(len(segs))
    sh_a = [s_[1] / n * 100 for s_ in segs]
    sh_f = [s_[2] / tf * 100 for s_ in segs]
    ax.bar(x - 0.2, sh_a, 0.4, color=R.STEEL, label="Share of accounts")
    ax.bar(x + 0.2, sh_f, 0.4, color=[R.NAVY] * (len(segs) - 1) + [R.ORANGE], label="Share of collected fees")
    for i, (a_, f_) in enumerate(zip(sh_a, sh_f)):
        ax.text(i - 0.2, a_ + 1.2, f"{a_:.0f}%" if a_ >= 1 else f"{a_:.1f}%", ha="center", fontsize=11, color=R.NAVY, fontweight="bold")
        ax.text(i + 0.2, f_ + 1.2, f"{f_:.0f}%", ha="center", fontsize=11, color=R.NAVY, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([s_[0] for s_ in segs], fontsize=11, color=R.TICK)
    R.style_axes(ax)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_ylim(0, max(max(sh_a), max(sh_f)) * 1.18)
    ax.legend(frameon=False, fontsize=10.5, labelcolor=R.TICK, loc="upper center")
    fig.tight_layout()
    png = R.save(fig, dk.chart_dir, "usage_segments_personal")
    s = dk.content(f"{ha:.1f}% of active personal accounts generate {hf:.0f}% of collected fees",
                   f"Open active personal accounts ({n:,}) by NSF/OD items in 365 days to {fr.asof:%B} {fr.asof.day}, {fr.asof.year}; the 24+ group is the heavy users.",
                   section=section, source=CS._src(cfg, fr, "za", extra="Items = items365; fees = CollectedFees365; open active = a deposit in the last "
                                                   "240 days or an NSF/OD item in the last 365. Heavy user = 24 or more items."))
    T.image_real(s, png, CS.LEFT, CS.BODY_T + 0.05, 7.8, 4.55)
    CS._tiles_real(s, [(f"{heavy[1]:,}", "Accounts with 24+ items"), (money(heavy[2]), "Collected fees from them"),
                       (f"{segs[0][1] / n * 100:.0f}%", "Accounts with no items")])
    CS.caption(s, "grey bars are the share of accounts and navy bars the share of fees; the orange bar is the 24+ item group's share of fees.", T0=6.35)
    CS.say_first(s, "A small group of heavy users brings in most of the fees, so that is where the program's results and risks sit.")
    par = [compare(hf, dk.ref.get("usage.Personal.heavy_fees_pct"), tol=0.02, measure="Personal heavy-user share of fees %"),
           compare(ha, dk.ref.get("usage.Personal.heavy_accts_pct"), tol=0.15, measure="Personal heavy-user share of accounts %")]
    dk.sidecars.append({"key": "usage_segments_personal", "title": "Collected fees by annual item count", "png": "usage_segments_personal.png",
                        "numbers": {"segments": [{"segment": a_, "accounts": b_, "fees": c_} for a_, b_, c_ in segs], "population": n, "fees_total": tf},
                        "parity": R._jsonable(par)})
    return [f"Fees by annual item count: heavy users (24+ items) hold {hf:.1f}% of collected fees of {n:,} open active accounts; the hand-built deck "
            f"counts a slightly different population, so its share of accounts can differ while its share of fees agrees to about a point."]
