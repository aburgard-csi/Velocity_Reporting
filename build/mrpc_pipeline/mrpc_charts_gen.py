#!/usr/bin/env python3
"""Data-driven MRPC chart renderer.

Reads a per-client MRPC data sheet (JSON, from Inputs/VIP Data/) and renders
every MRPC chart for ANY client into an output directory. Charts are padded to
the exact aspect ratio of their slide slot so the build script can swap them in
without distortion.

Usage:
    python3 mrpc_charts_gen.py <client_mrpc.json> <out_dir>

Tier colors (fixed, per STYLE.md): Gold = orange, Platinum = gray, Business = navy.
Business series/panels render only when meta.has_business is true.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))  # build/
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from PIL import Image
from rpe_env import use_font

def _shadow_wedges(wedges):
    return wedges   # STYLE.md: pie/donut charts are FLAT — no shadow


# ---- palette ---------------------------------------------------------------
from brand import NAVY, STEEL_SOFT as STEEL, ORANGE, LIGHT, TEAL
import periods as P
P.install_month_axis_guard()   # a month drawn outside MMM'YY fails the render
from brand import TICK, MUTED as GREY, HAIRLINE, SLATE
# MRPC enrollment tier palette (Aaron 2026-07-16): Gold=orange, Platinum=navy, Business=steel.
# Aaron 2026-07-24: Gold orange, Platinum GRAY, Business NAVY
GOLDC, PLATC, BIZC = ORANGE, STEEL, NAVY
# cancellation donut palette (navy -> steel ramp + orange/gold/rose accents)
from brand import CANCEL_RAMP as CANCEL_COLORS

use_font("Carlito"); plt.rcParams.update({"font.size": 14})

def canvas(fig, CW, CH, path, pad=0.12):
    """Save fig, then letterbox onto an exact CW x CH white canvas (keeps the
    slide-slot aspect ratio so the swapped picture is never stretched)."""
    tmp=path+".tmp.png"
    fig.savefig(tmp, dpi=150, facecolor="white", bbox_inches="tight", pad_inches=pad)
    plt.close(fig)
    im=Image.open(tmp).convert("RGB"); iw,ih=im.size
    sc=min(CW/iw, CH/ih); nw,nh=round(iw*sc), round(ih*sc)
    cv=Image.new("RGB",(CW,CH),"white")
    cv.paste(im.resize((nw,nh), Image.LANCZOS), ((CW-nw)//2,(CH-nh)//2))
    cv.save(path); os.remove(tmp); print("wrote", os.path.basename(path))

def _overlay_line(ax, x, y, label, zorder=3, ms=6, color=TEAL, ls='-', lw=2.2):
    """A series line drawn OVER the bars, in a colour that reads on both
    backgrounds it crosses: the navy bar, and the white gap between bars.

    Three goes at this. It was drawn plain WHITE (STYLE.md, pre 2026-09-01) on
    the assumption it never left a navy bar — it does, and the MRPC Retention
    line was invisible for its whole length on the 2026.08 decks. Then navy with
    a white stroke under it, which was legible but rejected on looks (Aaron,
    2026-09-01). Now TEAL, which needs no stroke: 4.02:1 against #00274C and
    3.74:1 against white, both clear of WCAG's 3:1 for non-text.

    Orange callers (the Goal line) pass their own colour and are unaffected —
    orange already reads at 5.5:1 on navy. A mark is never drawn in the canvas
    colour: see tests/test_chart_colors.py.
    """
    return ax.plot(x, y, color=color, lw=lw, ls=ls, marker='o', mfc='white', mec=color,
                   ms=ms, label=label, zorder=zorder)


def _clean(ax):
    for sp in ("top","right","left"): ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GREY); ax.tick_params(colors=TICK, length=0)
    ax.set_axisbelow(True)

# ---- individual charts -----------------------------------------------------
def _split_tiers(totals, last, has_business):
    """Apportion each month's total into gold/platinum/business using the last
    complete month's ratio (seed). Exact monthly tiers should be supplied via
    VIP where available; this keeps the stack visually consistent."""
    g0,p0,b0 = last["gold"], last["platinum"], (last["business"] if has_business else 0)
    denom=g0+p0+b0 or 1
    gr,pr,br = g0/denom, p0/denom, b0/denom
    gold=[]; plat=[]; biz=[]
    for t in totals:
        gg=round(t*gr); bb=round(t*br) if has_business else 0
        pp=t-gg-bb
        gold.append(gg); plat.append(pp); biz.append(bb)
    return gold, plat, biz

def chart_enroll(d, out, dims):
    e=d["enrollments_by_month"]; hb=d["meta"]["has_business"]
    m=e["months"]; tot=e["totals"]; partial=[False]*(len(m)-1)+[bool(e.get("partial_last"))]
    # Prefer exact per-month tier arrays when supplied (VIP); else apportion from
    # the last-complete month's ratio.
    if e.get("gold") and e.get("platinum") and len(e["gold"])==len(m) and len(e["platinum"])==len(m):
        gold=list(e["gold"]); plat=list(e["platinum"])
        biz=list(e["business"]) if (hb and e.get("business") and len(e["business"])==len(m)) else [0]*len(m)
        tot=[gold[i]+plat[i]+biz[i] for i in range(len(m))]
    else:
        gold,plat,biz=_split_tiers(tot, e["last_complete"], hb)
    fig,ax=plt.subplots(figsize=SLOT_IN["enroll"]);
    for i in range(len(m)):
        a=0.42 if partial[i] else 1.0; h='//' if partial[i] else None
        ax.bar(i,gold[i],color=GOLDC,width=0.72,alpha=a,hatch=h,edgecolor='white',linewidth=0.5)
        ax.bar(i,plat[i],bottom=gold[i],color=PLATC,width=0.72,alpha=a,hatch=h,edgecolor='white',linewidth=0.5)
        if hb:
            ax.bar(i,biz[i],bottom=gold[i]+plat[i],color=BIZC,width=0.72,alpha=a,hatch=h,edgecolor='white',linewidth=0.5)
        ax.text(i,tot[i]+max(tot)*0.015,str(tot[i]),ha="center",va="bottom",
                color=(TICK if partial[i] else NAVY),fontweight="bold",fontsize=13)
    ax.set_xticks(range(len(m))); ax.set_xticklabels(P.axis_months(m),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)
    ax.set_ylim(0,max(tot)*1.18); ax.get_yaxis().set_visible(False); _clean(ax)
    handles=[Patch(fc=GOLDC,label='Gold'),Patch(fc=PLATC,label='Platinum')]
    if hb: handles.append(Patch(fc=BIZC,label='Business'))
    if partial[-1]:   # the legend names a partial month only when there is one (2026-09-17)
        handles.append(Patch(fc=PLATC,alpha=0.42,hatch='//',label=f'{P.mon_yy(m[-1])} (partial)'))
    ax.legend(handles=handles,loc='upper center',bbox_to_anchor=(0.5,1.10),
              ncol=len(handles),frameon=False,fontsize=13)
    canvas(fig,*dims,out)

def chart_channel(d, out, dims):
    c=d["channel"]; order=c["order"]; pct=[c["pct"][k] for k in order]
    cols=[NAVY,STEEL,LIGHT,ORANGE][:len(order)]
    fig,(axd,axb)=plt.subplots(1,2,figsize=SLOT_IN["channel"],
        gridspec_kw={'width_ratios':[1,1.05],'wspace':0.25})
    _shadow_wedges(axd.pie(pct,colors=cols,startangle=90,counterclock=False,
            wedgeprops=dict(width=0.42,edgecolor='white',linewidth=2))[0])
    axd.text(0,-1.35," · ".join(f"{k} {v:.0f}%" for k,v in zip(order,pct)),
             ha='center',color=TICK,fontsize=13)
    axd.set_title("% Enrollments by Channel",color=NAVY,fontsize=13,fontweight='bold',pad=8)
    # A channel count may be absent for two different reasons, and they are not
    # the same fact:
    #   count is 0, or None with a 0% share  -> the channel genuinely has none
    #   count is None with a NON-ZERO share  -> enrolments exist, VIP would not
    #                                           surface the number (Marine 1539's
    #                                           Paper bar is too small to trigger
    #                                           a tooltip; 0.04% implies ~3)
    # Both draw a zero-length bar; only the LABEL differs, so the chart never
    # asserts a count it does not have and never reads a real zero as missing.
    # Plotting None directly crashed on `vals + max(vals)`.
    pctd=c.get("pct") or dict(zip(order,pct))
    counts=c.get("counts")
    y=np.arange(len(order))[::-1]
    if counts:
        raw=[counts.get(k) for k in order]
        vals=[0 if v is None else v for v in raw]
        labels=[f"{v:,}" if v is not None else ("0" if (pctd.get(k) or 0) == 0 else "n/a")
                for k,v in zip(order,raw)]
        _unread=[k for k,v in zip(order,raw) if v is None and (pctd.get(k) or 0) > 0]
        if _unread:
            print(f"chart_channel: VIP surfaced no count for {', '.join(_unread)} "
                  f"(share is non-zero) — bar drawn at 0 and labelled n/a")
        span=max(vals) or 1
        axb.barh(y,vals,color=NAVY,height=0.6)
        for yy,vv,lb in zip(y,vals,labels): axb.text(vv+span*0.02,yy,lb,va='center',color=NAVY,fontweight='bold',fontsize=13)
        axb.set_xlim(0,span*1.18); axb.set_title("Total Enrollments by Channel",color=NAVY,fontsize=13,fontweight='bold',pad=8)
    else:
        axb.barh(y,pct,color=NAVY,height=0.6)
        for yy,vv in zip(y,pct): axb.text(vv+max(pct)*0.02,yy,f"{vv:.1f}%",va='center',color=NAVY,fontweight='bold',fontsize=13)
        axb.set_xlim(0,max(pct)*1.18); axb.set_title("Share by Channel",color=NAVY,fontsize=13,fontweight='bold',pad=8)
    axb.set_yticks(y); axb.set_yticklabels(order,fontsize=13,color=NAVY); axb.get_xaxis().set_visible(False)
    for sp in ("top","right","bottom"): axb.spines[sp].set_visible(False)
    axb.spines["left"].set_color(GREY); axb.tick_params(colors=TICK,length=0)
    canvas(fig,*dims,out)

def chart_perf(d, out, dims):
    """New-checking bars vs the enrollment goal, with the Enrollments line over them.

    Bars and goal come STRAIGHT FROM THE DATA. They used to be invented: the code
    read `new_checking_approx`, a key no client sheet has ever carried, and fell
    back to `enrollments / 0.11` — a guessed 11% penetration. The real counts sit
    in `new_accounts` and the real goal in `goal`, present in every sheet. On
    Austin 1075 the fabrication drew 1,036 new accounts for a month that actually
    had 873, and because the goal line was derived from those same invented bars,
    every month's goal was wrong too. There is no fallback now: absent keys raise,
    because a chart that cannot be drawn from the client's data must not be drawn
    from a constant.

    Enrollment counts are labelled ABOVE THE BAR (Aaron, 2026-09-01), matching
    MRPC Retention. On the line they sat at the Enrollments y-value, low and
    crowded against the goal line; above the bar they read as one clean row.
    """
    p=d["performance_vs_goal"]; m=p["months"]; enr=p["enrollments"]
    for k in ("new_accounts","goal","enrollments"):
        # Presence AND length: a short series indexes out of range at `nc[i]`, or
        # reaches matplotlib as a mismatched plot. chart_enroll above guards the
        # same way.
        if not p.get(k):
            raise SystemExit(f"performance_vs_goal.{k} is missing — refusing to "
                             f"draw MRPC Enrollment Performance from a placeholder")
        if len(p[k]) != len(m):
            raise SystemExit(f"performance_vs_goal.{k} has {len(p[k])} values for "
                             f"{len(m)} months — refusing to draw a misaligned chart")
    nc=p["new_accounts"]; goal=p["goal"]
    fig,ax=plt.subplots(figsize=SLOT_IN["perf"]); x=np.arange(len(m))
    cols=[ORANGE if i==len(m)-1 else NAVY for i in range(len(m))]
    ax.bar(x,nc,color=cols,width=0.66,label='New Checking Accounts',zorder=1)
    _overlay_line(ax,x,goal,f'Goal ({p["goal_pct"]}%)',zorder=3,ms=5,color=ORANGE,ls='--',lw=2)
    _overlay_line(ax,x,enr,'Enrollments',zorder=4)
    for i in range(len(m)):
        ax.text(i,nc[i]+max(nc)*0.02,str(enr[i]),ha='center',color=NAVY,fontsize=13,fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(P.axis_months(m),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)
    ax.set_ylim(0,max(nc)*1.15); ax.get_yaxis().set_visible(False); _clean(ax)
    ax.legend(loc='upper center',bbox_to_anchor=(0.5,1.10),ncol=3,frameon=False,fontsize=13)
    canvas(fig,*dims,out)

def chart_retention(d, out, dims):
    # Enrolled bars: navy, last cohort month orange (standard format). The Still-Active
    # line is cased (see _overlay_line) -- it crosses the white gaps between bars.
    # The line is the sheet's own still_active counts (2026-10-02). It used to read
    # `still_active_approx` -- a True/False flag -- and, that being False on every sheet, fall
    # back to 60% of enrolled: every MRPC deck drew an invented line. A sheet without the
    # counts stops the build; a line is never made up.
    r=d["retention"]; m=r["cohort_months"]; en=r["enrolled"]
    ac=r.get("still_active")
    if not isinstance(ac,list) or len(ac)!=len(en) or any(not isinstance(v,(int,float)) for v in ac):
        raise SystemExit("MRPC retention: the sheet carries no still_active count for every "
                         f"cohort month ({len(en)} enrolled, still_active={ac!r}); refresh the VIP sheet")
    fig,ax=plt.subplots(figsize=SLOT_IN["retention"]); x=np.arange(len(m))
    cols=[ORANGE if i==len(m)-1 else NAVY for i in range(len(m))]
    ax.bar(x,en,color=cols,width=0.68,label='Enrolled',zorder=1)
    _overlay_line(ax,x,ac,'Still Active',zorder=3)
    for i in range(len(m)): ax.text(i,en[i]+max(en)*0.02,str(en[i]),ha='center',color=NAVY,fontsize=13,fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(P.axis_months(m),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)
    ax.set_ylim(0,max(en)*1.15); ax.get_yaxis().set_visible(False); _clean(ax)
    ax.legend(loc='upper center',bbox_to_anchor=(0.5,1.10),ncol=2,frameon=False,fontsize=13)
    canvas(fig,*dims,out)

def chart_cancel(d, out, dims):
    """Cancellations by reason as RANKED HORIZONTAL BARS (Aaron 2026-07-24) — a donut+legend
    scales poorly with 4-8 reasons of very different size; ranked bars need no legend,
    labels never collide, and any reason count fits."""
    cc=sorted(d["retention"]["cancellations_by_reason"], key=lambda c:-c["pct"])
    labels=[c["reason"] for c in cc]; vals=[c["pct"] for c in cc]
    fig,ax=plt.subplots(figsize=SLOT_IN["cancel"])
    y=list(range(len(vals)))[::-1]
    cols=[NAVY if i==0 else STEEL for i in range(len(vals))]   # top reason in navy
    ax.barh(y,vals,color=cols,height=0.62)
    for yi,v in zip(y,vals):
        ax.text(v+max(vals)*0.015,yi,f"{v:.1f}%",va='center',color=NAVY,fontweight='bold',fontsize=13)
    ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=13,color=NAVY)
    ax.set_xlim(0,max(vals)*1.18); ax.get_xaxis().set_visible(False)
    for sp in ("top","right","bottom"): ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(HAIRLINE); ax.tick_params(length=0)
    canvas(fig,*dims,out)

def chart_revenue(d, out, dims):
    """Revenue by year. When the builder has projected the current year
    (d["revenue"]["projection"], Aaron 2026-10-02) the projected remainder is stacked on the
    YTD bar as a hatched, outlined segment -- visibly not actual -- with the projected full
    year printed above it and the YTD actual inside."""
    rv=d["revenue"]["annual"]; pj=(d["revenue"].get("projection") or {})
    yrs=[a["year"] for a in rv]; amt=[a["amount"] for a in rv]
    cols=[ORANGE if ("2025" in y and "2026" not in y) else (STEEL if "YTD" in y else NAVY) for y in yrs]
    proj_i=next((i for i,y in enumerate(yrs) if "YTD" in y), None) if pj.get("ok") else None
    top=[a+(pj["remainder"] if i==proj_i else 0) for i,a in enumerate(amt)]
    fig,ax=plt.subplots(figsize=SLOT_IN["revenue"]); x=np.arange(len(yrs))
    ax.bar(x,amt,color=cols,width=0.64)
    if proj_i is not None:
        ax.bar(proj_i,pj["remainder"],bottom=amt[proj_i],width=0.64,color='white',
               edgecolor=STEEL,hatch='///',linewidth=1.4)
    for i,a in enumerate(amt):
        if i==proj_i:
            ax.text(i,a/2,f"${a/1000:,.0f}K",ha='center',va='center',color=NAVY,fontweight='bold',fontsize=12)
            ax.text(i,top[i]+max(top)*0.02,f"${top[i]/1000:,.0f}K\nprojected",ha='center',va='bottom',
                    color=NAVY,fontweight='bold',fontsize=12,linespacing=1.0)
        else:
            ax.text(i,a+max(top)*0.02,f"${a/1000:,.0f}K",ha='center',va='bottom',color=NAVY,fontweight='bold',fontsize=13)
    labels=[(y.replace(" YTD","")+"\n(YTD + proj.)") if i==proj_i else y for i,y in enumerate(yrs)]
    ax.set_xticks(x); ax.set_xticklabels(labels,fontsize=13,color=TICK)
    ax.set_ylim(0,max(top)*1.22); ax.get_yaxis().set_visible(False); _clean(ax)
    canvas(fig,*dims,out)

def chart_billing(d, out, dims):
    b=d["card_billing"]; rows=b["by_fee"]; tot_acct=b["total_accounts"]
    labels=[(f"${r['fee']:.2f}" if isinstance(r['fee'],(int,float)) else str(r['fee'])) for r in rows]
    accts=[r["accounts"] for r in rows]
    y=np.arange(len(rows))[::-1]
    fig,ax=plt.subplots(figsize=(9,3.6))
    cols=[ORANGE if i==0 else NAVY for i in range(len(rows))]
    ax.barh(y,accts,color=cols,height=0.66)
    for yy,vv in zip(y,accts):
        ax.text(vv+max(accts)*0.01,yy,f"{vv:,}  ({vv/tot_acct*100:.1f}%)",va='center',color=NAVY,fontsize=13,fontweight='bold')
    ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=13,color=NAVY)
    ax.set_xlim(0,max(accts)*1.22); ax.get_xaxis().set_visible(False)
    for sp in ("top","right","bottom"): ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(GREY); ax.tick_params(colors=TICK,length=0)
    ax.set_title("Card Billing — Accounts by Monthly Fee",color=NAVY,fontsize=13,fontweight='bold',loc='left',pad=6)
    canvas(fig,*dims,out)

def chart_revenue_month(d, out, dims):
    # Monthly revenue bars: navy, last month orange (standard format), value labels on top.
    rm=d["revenue"]["by_month"]; m=rm["months"]; v=rm["revenue"]
    fig,ax=plt.subplots(figsize=SLOT_IN["revmonth"]); x=np.arange(len(m))
    cols=[ORANGE if i==len(m)-1 else NAVY for i in range(len(m))]
    ax.bar(x,v,color=cols,width=0.7)
    for i,a in enumerate(v):
        ax.text(i,a+max(v)*0.015,f"${a/1000:.1f}K",ha="center",va="bottom",color=NAVY,fontsize=12,fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(P.axis_months(m),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)
    ax.set_ylim(0,max(v)*1.14); ax.get_yaxis().set_visible(False); _clean(ax)
    canvas(fig,*dims,out)

def card_types(cb):
    """Normalise card_billing into the [{name, accounts, price}] shape.

    The 2026-08-10 VIP rescan replaced the old `card_types` list with a richer
    `by_fee` breakdown (fee / accounts / amount / label) plus `prices` and
    `multi_card_accounts`. Accept either: pass `card_types` through when present,
    otherwise fold `by_fee` into single-card tiers plus one "Multiple Cards"
    segment (STYLE.md: Platinum / Gold / Business Platinum / Multiple Cards).
    """
    if cb.get("card_types"):
        return cb["card_types"]
    prices = cb.get("prices") or {}
    singles, multi = [], 0
    for row in cb.get("by_fee") or []:
        label = str(row.get("label", "")).strip()
        acct = int(row.get("accounts") or 0)
        if label in prices:
            singles.append({"name": label, "accounts": acct,
                            "price": prices[label]})
        else:                      # "2x Platinum", "2x Gold", ... = multi-card
            multi += acct
    singles.sort(key=lambda c: -c["accounts"])
    if not multi:
        multi = int(cb.get("multi_card_accounts") or 0)
    if multi:
        singles.append({"name": "Multiple Cards", "accounts": multi,
                        "price": None})
    return singles


def chart_card_pie(d, out, dims):
    # Donut of the card portfolio (single-card types + a Multiple Cards segment) with a
    # legend showing count, share, and monthly price.
    cb=d["card_billing"]; types=card_types(cb); total=cb["total_accounts"]
    names=[t["name"] for t in types]; vals=[t["accounts"] for t in types]
    prices=[t.get("price") for t in types]
    cols=[NAVY,ORANGE,STEEL,SLATE][:len(types)]
    fig=plt.figure(figsize=SLOT_IN["cardpie"])
    axd=fig.add_axes([0.00,0.02,0.46,0.96]); axl=fig.add_axes([0.50,0.02,0.48,0.96]); axl.axis('off')
    _shadow_wedges(axd.pie(vals,colors=cols,startangle=90,counterclock=False,
            wedgeprops=dict(width=0.42,edgecolor='white',linewidth=2))[0])
    axd.text(0,0.10,f"{total:,}",ha='center',va='center',color=NAVY,fontsize=22,fontweight='bold')
    axd.text(0,-0.16,"cards billed",ha='center',va='center',color=TICK,fontsize=12)
    y=0.88
    for name,val,pr,c in zip(names,vals,prices,cols):
        pct=val/total*100
        axl.add_patch(plt.Rectangle((0.0,y-0.035),0.045,0.06,color=c,transform=axl.transAxes,clip_on=False))
        price=f"   ·   ${pr:.2f}/mo" if pr else "   ·   multiple cards"
        axl.text(0.075,y+0.005,name,fontsize=14,color=NAVY,fontweight='bold',va='center',transform=axl.transAxes)
        axl.text(0.075,y-0.105,f"{val:,}  ({pct:.1f}%){price}",fontsize=12.5,color=TICK,va='center',transform=axl.transAxes)
        y-=0.29
    canvas(fig,*dims,out)

# The inches each chart occupies on its slide (2026-10-02). Every figure used to be drawn
# 1.2-1.9x larger than its slot and then shrunk into it, so 13pt text landed at 7-11pt on the
# slide (Card Portfolio's legend at ~8pt). Drawn at the slot's own size, a font size in this
# file IS its size on the slide. Keep in step with the builder's picture boxes; DIMS below is
# the same shape in pixels.
SLOT_IN={
    "enroll":   (9.0, 5.15),
    "channel":  (9.9, 4.87),
    "perf":     (11.3, 4.7),
    "retention":(6.1, 4.5),
    "cancel":   (6.2, 4.6),
    "revenue":  (7.55, 5.15),
    "revmonth": (7.55, 5.15),
    "cardpie":  (6.5, 2.82),
}

# slot pixel targets (match the Marine MRPC template slot aspect ratios)
DIMS={
    "enroll":   (1980,1133),
    "channel":  (2070,1018),
    "perf":     (2260,1052),
    "retention":(1360,1003),
    "cancel":   (1360,1009),
    "revenue":  (1740,1187),
    "revmonth": (1740,1187),
    "cardpie":  (1980,860),
    "billing":  (1875,750),
}

def render_all(data, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    j=lambda n: os.path.join(out_dir,n)
    chart_enroll(data,   j("mrpc_enroll.png"),    DIMS["enroll"])
    chart_channel(data,  j("mrpc_channel.png"),   DIMS["channel"])
    chart_perf(data,     j("mrpc_perf.png"),      DIMS["perf"])
    chart_retention(data,j("mrpc_retention.png"), DIMS["retention"])
    chart_cancel(data,   j("mrpc_cancel.png"),    DIMS["cancel"])
    chart_revenue(data,  j("mrpc_revenue.png"),   DIMS["revenue"])
    chart_revenue_month(data, j("mrpc_revmonth.png"), DIMS["revmonth"])
    chart_card_pie(data, j("mrpc_cardpie.png"),   DIMS["cardpie"])
    chart_billing(data,  j("mrpc_billing.png"),   DIMS["billing"])
    print("all mrpc charts done ->", out_dir)

if __name__=="__main__":
    data=json.load(open(sys.argv[1], encoding="utf-8"))
    render_all(data, sys.argv[2])
