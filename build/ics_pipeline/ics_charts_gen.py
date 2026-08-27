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

NAVY="#00274C"; ORANGE="#F47A29"; STEEL="#9DB8CC"; LIGHT="#C9D6E3"; TICK="#5A6670"; GREY="#B8C0CA"

use_font("Carlito"); plt.rcParams.update({"font.size": 16})

def canvas(fig, CW, CH, path, pad=0.12):
    tmp=path+".tmp.png"; fig.savefig(tmp,dpi=150,facecolor="white",bbox_inches="tight",pad_inches=pad); plt.close(fig)
    im=Image.open(tmp).convert("RGB"); iw,ih=im.size; sc=min(CW/iw,CH/ih); nw,nh=round(iw*sc),round(ih*sc)
    cv=Image.new("RGB",(CW,CH),"white"); cv.paste(im.resize((nw,nh),Image.LANCZOS),((CW-nw)//2,(CH-nh)//2)); cv.save(path); os.remove(tmp)

def clean(ax):
    for sp in ("top","right","left"): ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GREY); ax.tick_params(colors=TICK,length=0); ax.set_axisbelow(True)

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
    ax.set_xticks(x); ax.set_xticklabels(mo,fontsize=16,color=TICK); ax.set_ylim(0,max(ref)*1.15)
    ax.get_yaxis().set_visible(False); clean(ax)
    h=[Patch(fc=NAVY,label="Referrals")]
    if partial: h.append(Patch(fc=STEEL,alpha=0.6,hatch="//",label=f"{mo[-1]} (partial)"))
    ax.legend(handles=h,loc="upper center",bbox_to_anchor=(0.5,1.1),ncol=len(h),frameon=False,fontsize=16)
    canvas(fig,2200,940,out)

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
    ctr=(f"${tot/1e6:,.2f}M" if tot>=1e6 else f"${tot:,.0f}")
    axp.text(0,0.13,ctr,ha="center",va="center",color=NAVY,fontsize=24,fontweight="bold")
    axp.text(0,-0.17,"Total Program\nRevenue",ha="center",va="center",color=TICK,fontsize=13)
    # legend: components with $ amount and share
    y=0.86
    for lab,v,c in zip(labels,vals,cols):
        axl.add_patch(plt.Rectangle((0.0,y-0.02),0.05,0.06,color=c,transform=axl.transAxes,clip_on=False))
        axl.text(0.08,y+0.02,lab,fontsize=16,color=NAVY,fontweight="bold",va="center",transform=axl.transAxes)
        axl.text(0.08,y-0.055,f"${v:,.0f}   ({v/tot*100:.0f}%)",fontsize=16,color=NAVY,va="center",transform=axl.transAxes)
        y-=0.205
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
def _months_open(d):
    n=len(d["monthly_detail"]["months"]); return [n-i for i in range(n)]
def _per_acct_month(d,key):
    m=d["monthly_detail"]; op=m["accounts_opened"]; mo=_months_open(d)
    return [m[key][i]/op[i]/mo[i] for i in range(len(m["months"]))]
def acct_months(d):
    m=d["monthly_detail"]; mo=_months_open(d); return sum(m["accounts_opened"][i]*mo[i] for i in range(len(m["months"])))

def _monthly_bar(d,key,out,per_account):
    m=d["monthly_detail"]; mo=m["months"]; x=np.arange(len(mo))
    vals=_per_acct_month(d,key) if per_account else m[key]
    fig,ax=plt.subplots(figsize=(11.5,5.6)); bars_last_orange(ax,x,vals)
    fmt=(lambda v:f"${v:,.2f}") if per_account else (lambda v:f"${v:,.0f}")
    for i,v in enumerate(vals): ax.text(i,v+max(vals)*0.02,fmt(v),ha="center",va="bottom",color=NAVY,fontsize=16,fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(mo,fontsize=16,color=TICK); ax.set_ylim(0,max(vals)*1.15); ax.get_yaxis().set_visible(False); clean(ax)
    canvas(fig,1815,1000,out)

def c_composition(d,out):
    m=d["monthly_detail"]; mo=m["months"]; x=np.arange(len(mo))
    series=[(m["spread"],NAVY,"Spread on Deposits"),(m["interchange"],ORANGE,"Interchange"),
            (m["nsf_od"],STEEL,"NSF/OD Fees"),(m["other_fees"],LIGHT,"Other Fees")]
    fig,ax=plt.subplots(figsize=(11.5,5.6)); b=np.zeros(len(mo))
    for vals,c,lab in series: ax.bar(x,vals,bottom=b,color=c,width=0.66,label=lab); b=b+np.array(vals)
    for i,t in enumerate(b): ax.text(i,t+max(b)*0.02,f"${t:,.0f}",ha="center",va="bottom",color=NAVY,fontsize=16,fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(mo,fontsize=16,color=TICK); ax.set_ylim(0,max(b)*1.16); ax.get_yaxis().set_visible(False); clean(ax)
    ax.legend(loc="upper center",bbox_to_anchor=(0.5,1.12),ncol=4,frameon=False,fontsize=16)
    canvas(fig,1815,1000,out)

def c_perref(d,out):
    m=d["monthly_detail"]; mo=m["months"]
    for_ax=[(m["avg_balance"],"Avg Balance / Account","${:,.0f}"),
            (_per_acct_month(d,"interchange"),"Interchange / Acct / Mo","${:.2f}"),
            (_per_acct_month(d,"nsf_od"),"NSF-OD / Acct / Mo","${:.2f}")]
    fig,axes=plt.subplots(1,3,figsize=(13,4.4),gridspec_kw={"wspace":0.28})
    for ax,(vals,title,fmt) in zip(axes,for_ax):
        x=np.arange(len(mo)); bars_last_orange(ax,x,vals)
        ax.set_title(title,color=NAVY,fontsize=16,fontweight="bold",pad=8)
        ax.set_xticks(x); ax.set_xticklabels([mm.split()[0] for mm in mo],fontsize=16,color=TICK,rotation=40,ha="right")
        ax.set_ylim(0,max(vals)*1.18); ax.get_yaxis().set_visible(False); clean(ax)
        ax.text(len(mo)-1,vals[-1]+max(vals)*0.03,fmt.format(vals[-1]),ha="center",color=ORANGE,fontsize=16,fontweight="bold")
    canvas(fig,2100,800,out)

def c_bucket_compare(d,out):
    """Blended revenue per account per month, compared across the revenue buckets."""
    m=d["monthly_detail"]; am=acct_months(d)
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

def c_perf_intro(d,out):
    """Decorative on-brand motif for the 'Performance of Accounts' section intro —
    monthly referrals (navy bars) + cumulative referrals (orange line), axes stripped."""
    ref=d["referrals"]["trend"]["referrals"]; x=np.arange(len(ref))
    cum=np.cumsum(ref)
    fig,ax=plt.subplots(figsize=(6.3,5.0))
    ax.bar(x,ref,color=NAVY,width=0.64,alpha=0.92,zorder=1)
    ax2=ax.twinx()
    ax2.plot(x,cum,color=ORANGE,lw=3.2,marker="o",mfc="white",mec=ORANGE,ms=7,zorder=3)
    for a in (ax,ax2): a.axis("off")
    fig.savefig(out,dpi=200,transparent=True,bbox_inches="tight",pad_inches=0.1); plt.close(fig)

def render_all(d, A):
    os.makedirs(A,exist_ok=True); j=lambda n: os.path.join(A,n)
    md=d["monthly_detail"]
    # NSF/OD slides include NSF/OD fees + other charges (service charges)
    md.setdefault("nsf_other",[md["nsf_od"][i]+md["other_fees"][i] for i in range(len(md["months"]))])
    c_referral_trend(d,j("ics_trend.png"))
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
    c_perref(d,j("ics_perref.png"))
    print("ICS charts ->",A)

if __name__=="__main__":
    render_all(json.load(open(sys.argv[1])), sys.argv[2])
