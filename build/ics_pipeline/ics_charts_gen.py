#!/usr/bin/env python3
"""Data-driven ICS chart renderer. Reads a client ICS data sheet (JSON) and renders
every ICS chart. Used by build_ics_gen.py. Standalone: python3 ics_charts_gen.py <json> <dir>
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))  # build/
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from PIL import Image
from rpe_env import use_font

from brand import (bar_labels, NAVY, ORANGE, STEEL_SOFT as STEEL, LIGHT, TICK,
                   MUTED as GREY, usd_compact as _usd)
import periods as P
from ics_channel_split import AGE_EDGES
P.install_month_axis_guard()   # a month drawn outside MMM'YY fails the render

use_font("Carlito"); plt.rcParams.update({"font.size": 16})

def canvas(fig, CW, CH, path, pad=0.12):
    tmp=path+".tmp.png"; fig.savefig(tmp,dpi=150,facecolor="white",bbox_inches="tight",pad_inches=pad); plt.close(fig)
    im=Image.open(tmp).convert("RGB"); iw,ih=im.size; sc=min(CW/iw,CH/ih); nw,nh=round(iw*sc),round(ih*sc)
    cv=Image.new("RGB",(CW,CH),"white"); cv.paste(im.resize((nw,nh),Image.LANCZOS),((CW-nw)//2,(CH-nh)//2)); cv.save(path); os.remove(tmp)

def clean(ax):
    for sp in ("top","right","left"): ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GREY); ax.tick_params(colors=TICK,length=0); ax.set_axisbelow(True)

def slot_in(fig,ax):
    """Inches between neighbouring bar centres: the axes' width over its x range. Read after the
    bars and set_xlim, so a value label can be measured against the room it really has."""
    lo,hi=ax.get_xlim(); return ax.get_position().width*fig.get_figwidth()/(hi-lo)

def bars_last_orange(ax,x,v):
    return ax.bar(x,v,color=[ORANGE if i==len(v)-1 else NAVY for i in range(len(v))],width=0.66)

# ---- referral trend (navy bars, last complete month orange, partial month steel/hatch) ----
# Goal line is omitted: the monthly goal (7/branch across the whole network) is ~20x current
# volume and would flatten the bars. Goal context lives on the Power-of-Referrals tile + branch table.
def c_referral_trend(d,out):
    t=d["referrals"]["trend"]; mo=t["months"]; ref=t["referrals"]
    partial=bool(t.get("partial_last")); x=np.arange(len(mo))
    fig,ax=plt.subplots(figsize=(13,5.2))
    for i in range(len(mo)):
        if partial and i==len(mo)-1:
            ax.bar(i,ref[i],color=STEEL,width=0.7,hatch="//",edgecolor="white",alpha=0.6)
        else:
            c=ORANGE if (i==len(mo)-2 and partial) or (i==len(mo)-1 and not partial) else NAVY
            ax.bar(i,ref[i],color=c,width=0.7)
        ax.text(i,ref[i]+max(ref)*0.02,str(ref[i]),ha="center",va="bottom",
                color=(TICK if partial and i==len(mo)-1 else NAVY),fontweight="bold",fontsize=16)
    ax.set_xticks(x); ax.set_xticklabels(P.axis_months(mo),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA); ax.set_ylim(0,max(ref)*1.15)
    ax.get_yaxis().set_visible(False); clean(ax)
    h=[Patch(fc=NAVY,label="Referrals")]
    if partial: h.append(Patch(fc=STEEL,alpha=0.6,hatch="//",label=f"{P.mon_yy(mo[-1])} (partial)"))
    ax.legend(handles=h,loc="upper center",bbox_to_anchor=(0.5,1.1),ncol=len(h),frameon=False,fontsize=16)
    canvas(fig,2200,940,out)

# ---- direct-mail new accounts by month (house time-series treatment) ----
# The canvas matches the picture box on the "Direct Mail New Accounts" slide (8.05 x 4.95in),
# so the PNG is never stretched. Same marks as c_referral_trend: navy bars, the last COMPLETE
# month orange, a partial month hatched STEEL_SOFT, value labels above the bars, MMM'YY axis.
DM_BOX_IN = (8.05, 4.95)
DM_CANVAS = (1950, 1199)


def dm_partial_last(dm):
    """True when the newest month in the direct-mail block is still running: the report was
    drawn inside that month. A report dated after the month ends makes it complete."""
    import datetime as _dt
    rd, last = dm.get("report_date"), dm.get("last_month")
    try:
        r = _dt.date.fromisoformat(rd)
        y, m = (int(x) for x in last.split("-")[:2])
    except Exception:
        return False
    return (r.year, r.month) == (y, m)


def c_direct_mail_trend(d,out):
    dm=d["direct_mail"]; mo=dm["by_month"]["months"]; v=dm["by_month"]["accounts"]
    partial=dm_partial_last(dm); x=np.arange(len(mo)); top=max(v) or 1
    fig,ax=plt.subplots(figsize=(11,6.2))
    for i in range(len(mo)):
        if partial and i==len(mo)-1:
            ax.bar(i,v[i],color=STEEL,width=0.7,hatch="//",edgecolor="white",alpha=0.42)
        else:
            c=ORANGE if (i==len(mo)-2 and partial) or (i==len(mo)-1 and not partial) else NAVY
            ax.bar(i,v[i],color=c,width=0.7)
        ax.text(i,v[i]+top*0.02,f"{v[i]:,}",ha="center",va="bottom",
                color=(TICK if partial and i==len(mo)-1 else NAVY),fontweight="bold",fontsize=16)
    ax.set_xticks(x); ax.set_xticklabels(P.axis_months(mo),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)
    ax.set_ylim(0,top*1.15); ax.get_yaxis().set_visible(False); clean(ax)
    h=[Patch(fc=NAVY,label="Direct-mail accounts opened")]
    if partial: h.append(Patch(fc=STEEL,alpha=0.42,hatch="//",label=f"{P.mon_yy(mo[-1])} (partial)"))
    ax.legend(handles=h,loc="upper center",bbox_to_anchor=(0.5,1.1),ncol=len(h),frameon=False,fontsize=16)
    canvas(fig,DM_CANVAS[0],DM_CANVAS[1],out)


def has_direct_mail(d):
    """The Direct Mail New Accounts slide (and its chart) exists only for a block with accounts."""
    dm=d.get("direct_mail") or {}
    return bool((dm.get("accounts_opened_ptd") or 0) > 0 and (dm.get("by_month") or {}).get("months"))

# ---- ICS revenue pie (PTD components) ----
def c_revenue_pie(d,out):
    comp=d["revenue"]["components"]; labels=[c["name"] for c in comp]; vals=[c["amount"] for c in comp]
    cols=[NAVY,ORANGE,STEEL,LIGHT][:len(comp)]; tot=sum(vals)
    fig=plt.figure(figsize=(12,5.6))
    axp=fig.add_axes([0.02,0.03,0.44,0.94]); axl=fig.add_axes([0.5,0.05,0.48,0.9]); axl.axis("off")
    import matplotlib.patheffects as pe
    # donut (matches the Product Mix donut) with Total Program Revenue in the center
    wed=axp.pie(vals,colors=cols,startangle=90,counterclock=False,
            wedgeprops=dict(width=0.42,edgecolor="white",linewidth=2))[0]
    for w in wed:                                   # STYLE.md: pie/donut charts are FLAT — no shadow
        w.set_clip_on(False)
    # Revenue under $1M reads in K, not as a full dollar figure (Aaron, 2026-09-11).
    ctr=_usd(tot)
    # Larger type throughout (Cindy, 2026-11-03, on this slide: "We match on this- can you make font
    # larger?"): the legend names and dollar figures at 24 pt, the centre total at 30 pt.
    axp.text(0,0.13,ctr,ha="center",va="center",color=NAVY,fontsize=30,fontweight="bold")
    axp.text(0,-0.2,"Total Program\nRevenue",ha="center",va="center",color=TICK,fontsize=17)
    # legend: components with $ amount and share
    y=0.86
    for lab,v,c in zip(labels,vals,cols):
        axl.add_patch(plt.Rectangle((0.0,y-0.035),0.05,0.085,color=c,transform=axl.transAxes,clip_on=False))
        axl.text(0.08,y+0.035,lab,fontsize=24,color=NAVY,fontweight="bold",va="center",transform=axl.transAxes)
        axl.text(0.08,y-0.065,f"${v:,.0f}   ({v/tot*100:.0f}%)",fontsize=24,color=NAVY,va="center",transform=axl.transAxes)
        y-=0.235
    canvas(fig,2000,1010,out)

# ---- benchmark: velocity avg vs client, 4 metrics ----
def c_benchmark(d,out):
    ms=d["benchmark"]["metrics"]; client=d["meta"]["client_name"]
    fig,axes=plt.subplots(1,len(ms),figsize=(13,5.0),gridspec_kw={"wspace":0.35})
    for ax,m in zip(axes,ms):
        va,cl=m["velocity_avg"],m["client"]
        ax.bar([0,1],[va,cl],color=[STEEL,NAVY],width=0.62)
        def f(v):
            if m["fmt"]=="usd0": return f"${v:,.0f}"
            if m["fmt"]=="pct1": return f"{v:.1f}"
            return f"{v:g}"
        for xi,v in zip([0,1],[va,cl]): ax.text(xi,v+max(va,cl)*0.03,f(v),ha="center",color=NAVY,fontweight="bold",fontsize=16)
        ax.set_title(m["label"],color=NAVY,fontsize=16,fontweight="bold",pad=10)
        ax.set_xticks([0,1]); ax.set_xticklabels(["Velocity\nAvg",client],fontsize=16,color=TICK)
        ax.set_ylim(0,max(va,cl)*1.2); ax.get_yaxis().set_visible(False)
        for sp in ("top","right","left"): ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(GREY); ax.tick_params(colors=TICK,length=0)
    canvas(fig,2400,940,out)

# ---- monthly detail (cohort by opening month) ----
# EVERY cohort from the program's start (Aaron, 2026-11-03, Cindy's review of KEMBA CU 1195: "Why
# show newest accounts (least profitable) instead of onboarded accounts? Started ICS in December of
# 2022 - can we show all?"). The charts read the workbook's full Monthly Detail tab when the sheet
# carries it (`monthly_detail_full`), else the newest-twelve window an older sheet has. The first 12
# cohorts, the program's early referrals, are drawn apart from the rest: they have had the longest
# to earn, and they are the part a newest-twelve window hid.
EARLY_COHORTS = 12          # the program's first year of cohorts
YEAR_COHORTS = 12           # cohorts to a program year


def cohorts(d):
    """The cohort series the Monthly Detail charts draw: every cohort the sheet has.

    The full tab when present, else the newest-twelve window. Always carries `nsf_other`
    (NSF/OD plus other fees), the series the NSF/OD charts read."""
    full = d.get("monthly_detail_full") or {}
    src = full if (full.get("months") and full.get("accounts_opened")) else d["monthly_detail"]
    if "nsf_other" not in src and "nsf_od" in src and "other_fees" in src:
        src = dict(src)
        src["nsf_other"] = [src["nsf_od"][i] + src["other_fees"][i] for i in range(len(src["months"]))]
    return src


def is_all_cohorts(d):
    """True when the charts show every cohort (the full tab), not the newest-twelve window."""
    full = d.get("monthly_detail_full") or {}
    return bool(full.get("months") and full.get("accounts_opened"))


def has_early_split(d):
    """An early-program group exists only when there are cohorts beyond the first twelve."""
    return len(cohorts(d)["months"]) > EARLY_COHORTS


def program_years(n):
    """[(first index, last index), ...] — consecutive groups of 12 cohorts from the program's start.
    The last group is the program year still running."""
    return [(i, min(i + YEAR_COHORTS, n) - 1) for i in range(0, n, YEAR_COHORTS)]


def _months_open(d):
    n=len(cohorts(d)["months"]); return [n-i for i in range(n)]
def _per_acct_month(d,key):
    m=cohorts(d); op=m["accounts_opened"]; mo=_months_open(d)
    return [m[key][i]/op[i]/mo[i] if op[i] else 0.0 for i in range(len(m["months"]))]
def acct_months(d):
    m=cohorts(d); mo=_months_open(d); return sum(m["accounts_opened"][i]*mo[i] for i in range(len(m["months"])))


def year_group_values(d, key, per_account):
    """One figure per program year, for the group labels above the bars: the year's revenue, or its
    revenue over its account-months (a blended per-account-per-month, not a mean of cohort ratios)."""
    m=cohorts(d); mo=_months_open(d); out=[]
    for a,b in program_years(len(m["months"])):
        rev=sum(m[key][a:b+1])
        if per_account:
            am=sum(m["accounts_opened"][i]*mo[i] for i in range(a,b+1))
            out.append(rev/am if am else 0.0)
        else:
            out.append(rev)
    return out


def early_stats(d, keys):
    """The early program's share of a revenue measure (Cindy: "highlight revenue from early in the
    program"): the first 12 cohorts' revenue for the series `keys` (summed), its share of every
    cohort's, the accounts they opened and their blended revenue per account per month. None when
    the program has no cohorts beyond its first twelve (nothing to set the early ones against)."""
    m=cohorts(d); n=len(m["months"])
    if n<=EARLY_COHORTS: return None
    mo=_months_open(d); k=EARLY_COHORTS
    tot=lambda a,b: sum(sum(m[key][i] for key in keys) for i in range(a,b))
    e,allr=tot(0,k),tot(0,n)
    acct=sum(m["accounts_opened"][:k]); am=sum(m["accounts_opened"][i]*mo[i] for i in range(k))
    return {"revenue":e,"share":(e/allr if allr else 0.0),"accounts":acct,"per_acct_month":(e/am if am else 0.0),
            "first":m["months"][0],"last":m["months"][k-1],"total":allr}


def _year_labels(n):
    ys=program_years(n)
    return [f"Year {k+1}"+(f" ({b-a+1} mo)" if b-a+1<YEAR_COHORTS else "") for k,(a,b) in enumerate(ys)]


def _cohort_axis(ax, mo):
    """MMM'YY ticks: every one while it fits (up to 16 cohorts), else every third cohort — January,
    April, July, October — so forty-six months stay readable."""
    x=np.arange(len(mo))
    if len(mo)<=16:
        idx=list(x)
    else:
        idx=[i for i in x if i%3==0]
        if idx[-1]!=len(mo)-1 and len(mo)-1-idx[-1]>=2: idx.append(len(mo)-1)
    ax.set_xticks(idx); ax.set_xticklabels(P.axis_months([mo[i] for i in idx]),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)


def _year_marks(ax, n, labels, tops, top_y, fmt):
    """Faint separators between program years and a label above each: 'Year 1' over its figure."""
    ys=program_years(n)
    for k,(a,b) in enumerate(ys):
        if k: ax.axvline(a-0.5,color=MUTED_LINE,lw=1,ls=(0,(3,3)),zorder=0)
        cx=(a+b)/2
        ax.text(cx,top_y*0.985,labels[k],ha="center",va="top",fontsize=14,color=TICK)
        ax.text(cx,top_y*0.93,fmt(tops[k]),ha="center",va="top",fontsize=17,fontweight="bold",color=NAVY)


MUTED_LINE=GREY


def _monthly_bar(d,key,out,per_account):
    m=cohorts(d); mo=m["months"]; x=np.arange(len(mo))
    vals=_per_acct_month(d,key) if per_account else m[key]
    if len(mo)<=16:
        # a young program: every cohort fits a label of its own, as it always did
        fig,ax=plt.subplots(figsize=(11.5,5.6)); bars_last_orange(ax,x,vals)
        ax.set_xticks(x); ax.set_xticklabels(P.axis_months(mo),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA); ax.set_ylim(0,max(vals)*1.15); ax.get_yaxis().set_visible(False); clean(ax)
        # full figures unless twelve cohorts of them would run together, then $12.3K for all (2026-10-26)
        labels=bar_labels(vals,slot_in(fig,ax),pt=16,cents=per_account)
        for i,v in enumerate(vals): ax.text(i,v+max(vals)*0.02,labels[i],ha="center",va="bottom",color=NAVY,fontsize=16,fontweight="bold")
        canvas(fig,1815,1000,out)
        return
    # Every cohort from the program's start: early-program cohorts (the first 12) in orange, the
    # rest navy; each program year labelled with its own total, or its blended per-account figure.
    fig,ax=plt.subplots(figsize=(11.5,5.6))
    early=[i<EARLY_COHORTS for i in range(len(mo))]
    ax.bar(x,vals,color=[ORANGE if e else NAVY for e in early],width=0.78)
    top=max(vals)*1.42
    ax.set_ylim(0,top); ax.get_yaxis().set_visible(False); clean(ax); _cohort_axis(ax,mo)
    ax.set_xlim(-0.7,len(mo)-0.3)
    yv=year_group_values(d,key,per_account)
    _year_marks(ax,len(mo),_year_labels(len(mo)),yv,top,(lambda v:f"${v:,.2f}") if per_account else _usd)
    ax.legend(handles=[Patch(fc=ORANGE,label=f"First {EARLY_COHORTS} months of the program"),Patch(fc=NAVY,label="Later cohorts")],
              loc="upper center",bbox_to_anchor=(0.5,-0.2),ncol=2,frameon=False,fontsize=15)
    canvas(fig,1815,1000,out)

def c_composition(d,out):
    m=cohorts(d); mo=m["months"]; x=np.arange(len(mo))
    series=[(m["spread"],NAVY,"Spread on Deposits"),(m["interchange"],ORANGE,"Interchange"),
            (m["nsf_od"],STEEL,"NSF/OD Fees"),(m["other_fees"],LIGHT,"Other Fees")]
    fig,ax=plt.subplots(figsize=(11.5,5.6)); b=np.zeros(len(mo))
    if len(mo)<=16:
        for vals,c,lab in series: ax.bar(x,vals,bottom=b,color=c,width=0.66,label=lab); b=b+np.array(vals)
        ax.set_xticks(x); ax.set_xticklabels(P.axis_months(mo),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA); ax.set_ylim(0,max(b)*1.16); ax.get_yaxis().set_visible(False); clean(ax)
        labels=bar_labels(list(b),slot_in(fig,ax),pt=16)
        for i,t in enumerate(b): ax.text(i,t+max(b)*0.02,labels[i],ha="center",va="bottom",color=NAVY,fontsize=16,fontweight="bold")
        ax.legend(loc="upper center",bbox_to_anchor=(0.5,1.12),ncol=4,frameon=False,fontsize=16)
        canvas(fig,1815,1000,out)
        return
    # all cohorts: a tint behind the program's first 12 months, each program year's total above
    ax.axvspan(-0.7,EARLY_COHORTS-0.5,color=ORANGE,alpha=0.12,zorder=0,lw=0)
    for vals,c,lab in series: ax.bar(x,vals,bottom=b,color=c,width=0.78,label=lab); b=b+np.array(vals)
    top=max(b)*1.42
    ax.set_ylim(0,top); ax.set_xlim(-0.7,len(mo)-0.3); ax.get_yaxis().set_visible(False); clean(ax); _cohort_axis(ax,mo)
    ys=program_years(len(mo)); tot=[float(sum(b[a:z+1])) for a,z in ys]
    _year_marks(ax,len(mo),_year_labels(len(mo)),tot,top,_usd)
    h,l=ax.get_legend_handles_labels()
    h.append(Patch(fc=ORANGE,alpha=0.12,label=f"First {EARLY_COHORTS} months of the program"));
    ax.legend(handles=h,loc="upper center",bbox_to_anchor=(0.5,-0.2),ncol=3,frameon=False,fontsize=14)
    canvas(fig,1815,1000,out)

def c_perref(d,out):
    m=cohorts(d); mo=m["months"]
    for_ax=[(m["avg_balance"],"Avg Balance / Account","${:,.0f}"),
            (_per_acct_month(d,"interchange"),"Interchange / Acct / Mo","${:.2f}"),
            (_per_acct_month(d,"nsf_od"),"NSF-OD / Acct / Mo","${:.2f}")]
    fig,axes=plt.subplots(1,3,figsize=(13,4.4),gridspec_kw={"wspace":0.28})
    for ax,(vals,title,fmt) in zip(axes,for_ax):
        x=np.arange(len(mo)); bars_last_orange(ax,x,vals)
        ax.set_title(title,color=NAVY,fontsize=16,fontweight="bold",pad=8)
        ax.set_xticks(x); ax.set_xticklabels(P.axis_months(mo),fontsize=13,color=TICK,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)
        ax.set_ylim(0,max(vals)*1.18); ax.get_yaxis().set_visible(False); clean(ax)
        ax.text(len(mo)-1,vals[-1]+max(vals)*0.03,fmt.format(vals[-1]),ha="center",color=ORANGE,fontsize=16,fontweight="bold")
    canvas(fig,2100,800,out)

def c_bucket_compare(d,out):
    """Blended revenue per account per month, compared across the revenue buckets."""
    m=cohorts(d); am=acct_months(d)
    buckets=[("Spread on Deposits",sum(m["spread"]),NAVY),
             ("Interchange Income",sum(m["interchange"]),ORANGE),
             ("NSF / OD Fees",sum(m["nsf_od"]),STEEL),
             ("Other Fees",sum(m["other_fees"]),LIGHT)]
    labs=[b[0] for b in buckets]; vals=[b[1]/am for b in buckets]; cols=[b[2] for b in buckets]
    fig,ax=plt.subplots(figsize=(11.5,5.6)); x=np.arange(len(labs))
    ax.bar(x,vals,color=cols,width=0.62,edgecolor="white",linewidth=1.5)
    for i,v in enumerate(vals): ax.text(i,v+max(vals)*0.02,f"${v:,.2f}",ha="center",va="bottom",color=NAVY,fontsize=17,fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labs,fontsize=16,color=TICK); ax.set_ylim(0,max(vals)*1.16)
    ax.get_yaxis().set_visible(False); clean(ax)
    canvas(fig,1815,1000,out)

def c_referred_products(d,out):
    """Horizontal bars — referred accounts by participating product (referred>0)."""
    rp=[p for p in d["referred_by_product"]["products"] if p["referred"]>0]
    rp.sort(key=lambda p:p["referred"])
    labels=[p["name"] for p in rp]; vals=[p["referred"] for p in rp]; y=np.arange(len(labels))
    fig,ax=plt.subplots(figsize=(10.6,5.6))
    cols=[ORANGE if i==len(vals)-1 else NAVY for i in range(len(vals))]
    ax.barh(y,vals,color=cols,height=0.6)
    for i,v in enumerate(vals): ax.text(v+max(vals)*0.012,i,f"{v:,}",va="center",color=NAVY,fontsize=16,fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=16,color=NAVY)
    ax.set_xlim(0,max(vals)*1.14); ax.get_xaxis().set_visible(False)
    for sp in ("top","right","bottom"): ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(GREY); ax.tick_params(colors=TICK,length=0)
    canvas(fig,1720,1000,out)

# ---- direct mail vs branch referral (ics_channel_split) ----
def c_channel_accounts(d,split,out):
    """Accounts opened by cohort, stacked: branch referral (navy, the workbook's accounts less direct mail)
    and direct mail (orange, the CSM's list). Every cohort from the program's start; each program year
    carries its own account count and direct-mail share."""
    c=split["cohorts"]; mo=c["months"]; ref=np.array(c["referral"],float); dm=np.array(c["direct_mail"],float)
    n=len(mo); x=np.arange(n)
    fig,ax=plt.subplots(figsize=(11.5,5.6))
    ax.bar(x,ref,color=NAVY,width=0.78,label="Branch referral")
    ax.bar(x,dm,bottom=ref,color=ORANGE,width=0.78,label="Direct mail")
    top=float((ref+dm).max())*1.42
    ax.set_ylim(0,top); ax.set_xlim(-0.7,n-0.3); ax.get_yaxis().set_visible(False); clean(ax); _cohort_axis(ax,mo)
    for k,(a,b) in enumerate(program_years(n)):
        if k: ax.axvline(a-0.5,color=MUTED_LINE,lw=1,ls=(0,(3,3)),zorder=0)
        tot=float((ref+dm)[a:b+1].sum()); share=(float(dm[a:b+1].sum())/tot if tot else 0.0)
        lab=_year_labels(n)[k]
        ax.text((a+b)/2,top*0.985,lab,ha="center",va="top",fontsize=14,color=TICK)
        ax.text((a+b)/2,top*0.93,f"{tot:,.0f}",ha="center",va="top",fontsize=17,fontweight="bold",color=NAVY)
        ax.text((a+b)/2,top*0.85,(f"{share*100:.0f}% mail" if dm[a:b+1].sum() else "no mail"),ha="center",va="top",fontsize=13,color=TICK)
    ax.legend(loc="upper center",bbox_to_anchor=(0.5,-0.2),ncol=2,frameon=False,fontsize=15)
    canvas(fig,1815,1000,out)


def c_channel_interchange(d,split,out):
    """Interchange per open account per month by channel and calendar year — grouped bars, direct mail
    beside branch referral — over the same months for both. The ODD's debit spend x the blended rate the
    workbook implies, over the accounts open in each month."""
    s=channel_interchange_rows(d,split)
    labels=[r["label"] for r in s["years"]]; dm=[r["dm_pam"] for r in s["years"]]; rf=[r["ref_pam"] for r in s["years"]]
    x=np.arange(len(labels)); w=0.36
    fig,ax=plt.subplots(figsize=(11.5,5.6))
    b1=ax.bar(x-w/2,rf,width=w,color=NAVY,label="Branch referral"); b2=ax.bar(x+w/2,dm,width=w,color=ORANGE,label="Direct mail")
    top=max(rf+dm)*1.2
    for bars,vals in ((b1,rf),(b2,dm)):
        for b,v in zip(bars,vals): ax.text(b.get_x()+b.get_width()/2,v+top*0.015,f"${v:,.2f}",ha="center",va="bottom",fontsize=17,fontweight="bold",color=NAVY)
    ax.set_xticks(x); ax.set_xticklabels(labels,fontsize=16,color=TICK); ax.set_ylim(0,top); ax.get_yaxis().set_visible(False); clean(ax)
    ax.legend(loc="upper center",bbox_to_anchor=(0.5,1.12),ncol=2,frameon=False,fontsize=16)
    canvas(fig,1815,1000,out)


def channel_interchange_rows(d,split):
    """Interchange per open account per month, direct mail beside branch referral, by calendar year and
    in all — read from `split["odd"]["interchange"]` (the ODD's debit spend x the workbook's implied
    blended rate, over the accounts open in each month; see ics_channel_split.exposure_by_year).
    -> {"years": [{label, first, last, months, dm_pam, ref_pam, dm_ic, ref_ic, dm_active, ref_active}],
    "all": {...}} or None when the block has no stable-rate interchange split or direct-mail accounts."""
    ex=((split.get("odd") or {}).get("interchange"))
    if not ex or not ex["all"]["dm"]["account_months"] or not ex["all"]["ref"]["account_months"]: return None
    def row(r,label):
        dm,rf=r["dm"],r["ref"]
        return {"label":label,"first":r.get("first"),"last":r.get("last"),"months":r["months"],
                "dm_pam":dm["pam"],"ref_pam":rf["pam"],"dm_ic":dm["interchange"],"ref_ic":rf["interchange"],
                "dm_active":(dm["active"]/dm["account_months"] if dm["account_months"] else 0.0),
                "ref_active":(rf["active"]/rf["account_months"] if rf["account_months"] else 0.0),
                "dm_am":dm["account_months"],"ref_am":rf["account_months"]}
    years=[row(r,r["label"]+(f" ({r['months']} mo)" if r["months"]<12 else "")) for r in ex["years"]
           if r["dm"]["account_months"] and r["ref"]["account_months"]]
    return {"years":years,"all":row(ex["all"],"All")}


def c_age_demographics(profile,out):
    """Age of ICS account holders — a flat donut (STYLE.md: pies and donuts carry no shadow) with the
    bucket shares beside it."""
    from brand import PEACH
    labs=[k for k in profile["counts"]]; vals=[profile["counts"][k] for k in labs]; tot=sum(vals) or 1
    cols=[NAVY,ORANGE,STEEL,PEACH,LIGHT,GREY]
    fig=plt.figure(figsize=(10,5.6)); axp=fig.add_axes([0.0,0.02,0.52,0.96]); axl=fig.add_axes([0.56,0.05,0.44,0.9]); axl.axis("off")
    axp.pie(vals,colors=cols,startangle=90,counterclock=False,wedgeprops=dict(width=0.45,edgecolor="white",linewidth=2))
    axp.text(0,0.1,f"{sum(profile['counts'][l] for _,hi,l in AGE_EDGES if hi<=44)/tot*100:.0f}%",ha="center",va="center",color=NAVY,fontsize=34,fontweight="bold")
    axp.text(0,-0.2,"44 or younger",ha="center",va="center",color=TICK,fontsize=16)
    y=0.92
    for lab,v,c in zip(labs,vals,cols):
        axl.add_patch(plt.Rectangle((0.0,y-0.035),0.07,0.08,color=c,transform=axl.transAxes,clip_on=False))
        axl.text(0.12,y,f"{lab}",fontsize=20,color=NAVY,fontweight="bold",va="center",transform=axl.transAxes)
        axl.text(0.52,y,f"{v/tot*100:.0f}%",fontsize=20,color=NAVY,va="center",transform=axl.transAxes)
        y-=0.155
    canvas(fig,1800,1010,out)


def c_product_mix(products,out,top=7):
    """ICS accounts by product, largest first: horizontal bars, total accounts at the end of each. Products
    beyond the top few are one 'All other' bar."""
    rows=sorted(products,key=lambda p:-p["total"])
    if len(rows)>top:
        rest=rows[top-1:]; rows=rows[:top-1]+[{"product":f"All other ({len(rest)})","total":sum(p["total"] for p in rest)}]
    rows=rows[::-1]
    labels=[p["product"] for p in rows]; vals=[p["total"] for p in rows]; y=np.arange(len(labels))
    fig,ax=plt.subplots(figsize=(10.6,5.6))
    ax.barh(y,vals,color=[ORANGE if i==len(vals)-1 else NAVY for i in range(len(vals))],height=0.62)
    for i,v in enumerate(vals): ax.text(v+max(vals)*0.012,i,f"{v:,}",va="center",color=NAVY,fontsize=17,fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=16,color=NAVY); ax.set_xlim(0,max(vals)*1.16); ax.get_xaxis().set_visible(False)
    for sp in ("top","right","bottom"): ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(GREY); ax.tick_params(colors=TICK,length=0)
    canvas(fig,1720,1010,out)


def c_perf_intro(d,out):
    """Decorative on-brand motif for the 'Performance of Accounts' section intro —
    monthly referrals (navy bars) + cumulative referrals (orange line), axes stripped."""
    ref=d["referrals"]["trend"]["referrals"]; x=np.arange(len(ref))
    cum=np.cumsum(ref)
    # No trend line over a partial month (Aaron, 2026-09-17), decorative or not.
    if d["referrals"]["trend"].get("partial_last") and len(ref)>1:
        cum=cum[:-1]
    fig,ax=plt.subplots(figsize=(6.3,5.0))
    ax.bar(x,ref,color=NAVY,width=0.64,alpha=0.92,zorder=1)
    ax2=ax.twinx()
    ax2.plot(x[:len(cum)],cum,color=ORANGE,lw=3.2,marker="o",mfc="white",mec=ORANGE,ms=7,zorder=3)
    for a in (ax,ax2): a.axis("off")
    fig.savefig(out,dpi=200,transparent=True,bbox_inches="tight",pad_inches=0.1); plt.close(fig)

def render_split(d, split, A):
    """The charts that need the direct-mail / referral split (`ics_channel_split.compute`). Each is made
    only when the data behind it exists — the interchange chart needs the ODD, the age and product charts
    need the ODD join — so a client without them gets the slides it can support and no others."""
    os.makedirs(A,exist_ok=True); j=lambda n: os.path.join(A,n)
    if not split: return
    c_channel_accounts(d,split,j("ics_channel_accts.png"))
    if channel_interchange_rows(d,split): c_channel_interchange(d,split,j("ics_channel_ic.png"))
    odd=split.get("odd")
    if odd and odd["age"]["n"]: c_age_demographics(odd["age"],j("ics_age.png"))
    if odd and odd["products"]: c_product_mix(odd["products"],j("ics_products.png"))


def render_all(d, A, referrals_only=False):
    os.makedirs(A,exist_ok=True); j=lambda n: os.path.join(A,n)
    if referrals_only:
        # Client with no ICS workbook yet: only the VIP referral charts have data. Every
        # other chart reads monthly_detail / revenue / performance and would raise here.
        c_referral_trend(d,j("ics_trend.png"))
        if has_direct_mail(d): c_direct_mail_trend(d,j("ics_direct_mail.png"))
        if d.get("referred_by_product"): c_referred_products(d,j("ics_refprod.png"))
        print("ICS charts (referrals only) ->",A)
        return
    md=d["monthly_detail"]
    # NSF/OD slides include NSF/OD fees + other charges (service charges)
    md.setdefault("nsf_other",[md["nsf_od"][i]+md["other_fees"][i] for i in range(len(md["months"]))])
    c_referral_trend(d,j("ics_trend.png"))
    if has_direct_mail(d): c_direct_mail_trend(d,j("ics_direct_mail.png"))
    if d.get("referred_by_product"): c_referred_products(d,j("ics_refprod.png"))
    c_perf_intro(d,j("ics_perfintro.png"))
    c_revenue_pie(d,j("ics_revpie.png"))
    _monthly_bar(d,"interchange",j("ics_ic_tot.png"),False)
    _monthly_bar(d,"interchange",j("ics_ic_pam.png"),True)
    _monthly_bar(d,"nsf_other",j("ics_nsf_tot.png"),False)
    _monthly_bar(d,"nsf_other",j("ics_nsf_pam.png"),True)
    _monthly_bar(d,"spread",j("ics_spread_tot.png"),False)
    _monthly_bar(d,"spread",j("ics_spread_pam.png"),True)
    c_composition(d,j("ics_comp.png"))
    c_bucket_compare(d,j("ics_bucketcmp.png"))
    if not is_all_cohorts(d): c_perref(d,j("ics_perref.png"))   # on no slide; the full tab is too wide for it
    print("ICS charts ->",A)

if __name__=="__main__":
    render_all(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2])
