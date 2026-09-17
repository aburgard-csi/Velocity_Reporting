import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))  # build/
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, json, os
from PIL import Image
import sys
from rpe_env import use_font
M=json.load(open(sys.argv[1], encoding="utf-8"))
B=json.load(open(sys.argv[2], encoding="utf-8"))
OUT=sys.argv[3]; os.makedirs(OUT,exist_ok=True)
from brand import (NAVY, ORANGE, LABEL as GREY, STEEL, TICK,
                   STEEL_SOFT as LIGHT, GOLD, MUTED, HAIRLINE)
import periods as P
P.install_month_axis_guard()   # a month drawn outside MMM'YY fails the render
use_font("Carlito"); plt.rcParams.update({"font.size":13})
def _fixacr(txt):
    """Collapse space-separated single capital letters: 'Individual H S A' -> 'Individual HSA'."""
    toks=txt.split(); out=[]; buf=[]
    for t in toks:
        if len(t)==1 and t.isalpha() and t.isupper(): buf.append(t)
        else:
            if buf: out.append("".join(buf)); buf=[]
            out.append(t)
    if buf: out.append("".join(buf))
    return " ".join(out)
DIM={'image5':(1365,705),'image6':(1432,672),'image7':(1035,549),'image8':(1099,683),
 'image9':(1732,675),'image10':(2639,1003),'image11':(1383,540),'image12':(1740,1064),
 'image13':(491,491),'image14':(1520,900),'image15':(491,491),'image16':(1520,900),
 'image17':(1368,453),'image18':(1006,612),'image19':(1446,681),'image20':(1446,825),
 'image21':(1660,780),'image22':(978,598),'image23':(946,598),'image24':(1834,740),
 'image25':(1700,754),'image26':(1725,900),'image27':(1533,800),'image28':(1740,1007),
 'image29':(1740,1064),'image30':(2047,816),'image31':(2639,1003),'image32':(2050,790)}
# TEST BRANCH (RPE_JAMES_SLIDES=1): the take rate and Reg E branch charts render at the larger
# boxes insight_layout places them in (Aaron, 2026-09-17).
import os as _os_j
if _os_j.environ.get('RPE_JAMES_SLIDES')=='1':
    sys.path.insert(0, _os_j.path.dirname(_os_j.path.abspath(__file__)))
    import insight_layout as _il
    DIM.update({'image11': _il.CHART_DIMS['take'], 'image14': _il.CHART_DIMS['rege'], 'image16': _il.CHART_DIMS['rege']})

def _clean(ax):
    for sp in ["top","right"]: ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(HAIRLINE); ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=TICK,length=0); ax.set_axisbelow(True)
def save(fig,name):
    tmp=f"{OUT}/_{name}.png"
    fig.savefig(tmp,dpi=200,bbox_inches="tight",transparent=False,facecolor="white",pad_inches=0.06)
    plt.close(fig)
    im=Image.open(tmp).convert("RGB")
    tw,th=DIM[name]; iw,ih=im.size
    # fit preserving aspect (no stretch), pad with white to exact frame dims
    sc=min(tw/iw, th/ih); nw,nh=max(1,round(iw*sc)),max(1,round(ih*sc))
    im2=im.resize((nw,nh),Image.LANCZOS)
    canvas=Image.new("RGB",(tw,th),"white"); canvas.paste(im2,((tw-nw)//2,(th-nh)//2))
    canvas.save(f"{OUT}/{name}.png"); os.remove(tmp); print("wrote",name)
def figfor(name,scale=5.2):
    w,h=DIM[name]; a=w/h; H=scale; return plt.subplots(figsize=(H*a,H))

def _month_axis(ax,ticks,tokens,fontsize=9):
    """EVERY calendar-month x-axis in this file goes through here.

    MMM'YY, angled, anchored right — the one format (STYLE.md, periods.AXIS_*).
    It is a function rather than a convention because four charts drew their own
    labels by string-slicing and so never picked the standard up: the two
    before/after panels sliced "Feb 2024" into "Feb24", Sustained drew "Sep '23",
    and the monthly-revenue bars took `m.split()[0]` and threw the YEAR AWAY
    (Aaron, 2026-09-08). `periods.install_month_axis_guard`, armed at the top of
    this module, fails the render if a month reaches an axis any other way; the
    y-axis equivalent is a bare `P.axis_months` call (see c_ranking)."""
    ax.set_xticks(ticks)
    ax.set_xticklabels(P.axis_months(tokens),fontsize=fontsize,
                       rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)

def _xmonths(ax,x,cats,labels):
    """One x-axis style for the 36-mo combo charts: ~12 ticks, 9pt, 45deg (STYLE.md)."""
    step=max(1,round(len(cats)/12))
    _month_axis(ax,x[::step],[labels[i] for i in range(0,len(labels),step)])

# image5: monthly incremental revenue, navy bars + orange dashed avg
def c_monthly():
    data=B['monthly_rev_last12']; months=[m for m,_ in data]; rev=[v for _,v in data]
    avg=sum(rev)/len(rev)
    fig,ax=figfor('image5',3.4)
    ax.bar(np.arange(len(rev)),rev,color=NAVY,width=0.68)
    mx=max(rev)
    # Same halo as the SM Monthly Summary chart: a bar near the average has its
    # label crossing the dashed avg line, and the dash would strike through the
    # number rather than pass behind it.
    _halo=dict(boxstyle="square,pad=0.12", facecolor="white", edgecolor="none")
    for i,v in enumerate(rev):
        off=mx*(0.02 if i%2==0 else 0.10)   # stagger alternate labels so wide $ values don't collide
        ax.text(i,v+off,f"${v/1000:.0f}K",ha="center",va="bottom",color=NAVY,
                fontweight="bold",fontsize=8.5,bbox=_halo,zorder=5)
    ax.axhline(avg,ls="--",color=ORANGE,lw=2,zorder=2)
    _month_axis(ax,np.arange(len(rev)),months)
    ax.set_ylim(0,mx*1.26); ax.get_yaxis().set_visible(False)
    _clean(ax); ax.spines["left"].set_visible(False)
    save(fig,'image5')

TIERS=['NU 5+','TH-10','TH-15','TH-20','TH-25']; TCOL=[NAVY,STEEL,LIGHT,ORANGE,GOLD]
# image6: ranking horizontal stacked by tier, newest at top
def c_ranking():
    rows=list(reversed(M['ranking']))  # newest first (top)
    labels=[r[0] for r in rows]; y=np.arange(len(rows))[::-1]
    fig,ax=figfor('image6',5.0)
    left=np.zeros(len(rows))
    for ti,t in enumerate(TIERS):
        vals=[r[1+ti] for r in rows]
        ax.barh(y,vals,left=left,color=TCOL[ti],label=t,height=0.7)
        left+=vals
    for yi,tot in zip(y,left):
        ax.text(tot+left.max()*0.01,yi,f"{int(tot)}",va="center",ha="left",color=NAVY,fontweight="bold",fontsize=10)
    # Months, so the house format applies here too — this axis read "Sep 2023"
    # full-length while every other month axis in the deck read MMM'YY. No
    # rotation: these run down the side, one per row, with room to spare.
    ax.set_yticks(y); ax.set_yticklabels(P.axis_months(labels),fontsize=10)
    ax.set_xlim(0,left.max()*1.1); ax.get_xaxis().set_visible(False)
    _clean(ax); ax.spines["bottom"].set_visible(False)
    ax.legend(ncol=5,frameon=False,fontsize=9,loc="lower center",bbox_to_anchor=(0.5,-0.13))
    save(fig,'image6')
# image7: latest mailer tiers horizontal bars
def c_mailer():
    t=M['latest_tier']; labels=[x[0] for x in t]; vals=[x[1] for x in t]
    fig,ax=figfor('image7',4.4)
    y=np.arange(len(vals))[::-1]
    ax.barh(y,vals,color=TCOL,height=0.66)
    for yi,v in zip(y,vals):
        ax.text(v+max(vals)*0.02,yi,str(v),va="center",color=NAVY,fontweight="bold",fontsize=12)
    ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=12)
    ax.set_xlim(0,max(vals)*1.14); ax.get_xaxis().set_visible(False)
    _clean(ax); ax.spines["bottom"].set_visible(False)
    save(fig,'image7')
# image8: movement bars
def c_movement():
    mv=M['movement']; labels=[x[0].replace(' Response','\nResponse') for x in mv]; vals=[x[1] for x in mv]
    cols=[STEEL,ORANGE,GREY,NAVY]
    fig,ax=figfor('image8',4.6)
    ax.bar(range(len(vals)),vals,color=cols,width=0.66)
    for i,v in enumerate(vals):
        ax.text(i,v+max(vals)*0.01,str(v),ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=13)
    ax.set_xticks(range(len(vals))); ax.set_xticklabels(labels,fontsize=11)
    ax.set_ylim(0,max(vals)*1.16); ax.get_yaxis().set_visible(False)
    _clean(ax); ax.spines["left"].set_visible(False)
    save(fig,'image8')
# image9: sustained by mailing
def c_sustained():
    s=M['sustained']; cats=[x[0] for x in s]        # "Sep 2023"; _month_axis formats
    pct=[x[2] for x in s]
    fig,ax=figfor('image9',3.4)
    # grey marks a definitional 100%: a mailing with no month after it yet (post
    # window 0), not "immature data". Older rows may lack the 4th element.
    cols=[GREY if (len(x) > 3 and x[3] == 0) else ORANGE for x in s]
    ax.bar(range(len(pct)),pct,color=cols,width=0.62)
    for i,v in enumerate(pct):
        ax.text(i,v+1,f"{v:.0f}%",ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=11)
    _month_axis(ax,range(len(pct)),cats,fontsize=8.5)
    ax.set_ylim(0,max(pct)*1.22); ax.get_yaxis().set_visible(False)
    _clean(ax); ax.spines["left"].set_visible(False)
    save(fig,'image9')
# image31: before/after by OFFER GROUP (mean). Replaces the median twin — the deck
# reports one statistic, the mean, and splits it by what was asked instead
# (Aaron, 2026-08-28). NU asks a non-user to start; TH asks a user to reach a
# threshold, so pooling them hid which offer actually moved.
def c_before_after_split():
    sp=M.get('before_after_split') or []
    if not sp:
        print("skip image31 — no offer-group split available"); return
    cats=[e['m'] for e in sp]                       # "Feb 2024"; _month_axis formats
    name='image31'
    fig,axes=plt.subplots(1,2,figsize=(DIM[name][0]/DIM[name][1]*4.2,4.2))
    x=np.arange(len(cats)); w=0.4
    # ONE scale across both panels. With independent axes the NU panel topped at
    # $1,200 and the TH panel at $1,500, so a lower NU bar drew the same height as a
    # taller TH bar — the comparison the slide exists to make read backwards.
    _allv=[e[k][b] for e in sp for k in ('nu','th') for b in ('before','after')]
    _top=max(_allv+[1])*1.18
    for ax,key,title in zip(axes,('nu','th'),
                            ("Non-User Respondents","Threshold Respondents")):
        bb=[e[key]['before'] for e in sp]; aa=[e[key]['after'] for e in sp]
        ns=[e[key]['n'] for e in sp]
        ax.bar(x-w/2,bb,w,color=STEEL,label="Before")
        ax.bar(x+w/2,aa,w,color=ORANGE,label="After")
        # Label every Nth mailing only. Sugar River 1038 has FIFTEEN mailings and every
        # month plus an "(n=...)" second line was drawn, so the whole axis rendered as
        # overlapping mush (Aaron, 2026-08-28). Wellworth has one mailing, which is why
        # this never showed. The n counts move to the speaker notes rather than the axis.
        _step = max(1, -(-len(cats) // 8))          # at most 8 ticks
        _keep = list(range(0, len(cats), _step))
        if _keep[-1] != len(cats) - 1:
            # Always label the newest mailing — but appending it blindly put two
            # ticks side by side whenever the stride did not land on the last
            # index. Austin 1075 has 10 mailings, stride 2, so ticks ran
            # ... 8, 9 and "Nov25"/"Feb26" printed on top of each other
            # (Aaron, 2026-08-29). Drop the neighbour rather than crowd it.
            if len(cats) - 1 - _keep[-1] < _step:
                _keep.pop()
            _keep.append(len(cats) - 1)
        _month_axis(ax,[x[i] for i in _keep],[cats[i] for i in _keep],fontsize=11)
        ax.set_title(f"{title} — Avg Monthly Debit Spend",color=NAVY,
                     fontweight="bold",fontsize=12,pad=6)
        _clean(ax)
        ax.yaxis.set_major_formatter(lambda v,p:f"${v:,.0f}")
        ax.tick_params(axis='y',labelsize=12)
        ax.set_ylim(0,_top)
        # Per-bar dollar labels only when they can be read. At 15 mailings that is 30
        # labels across ~5in and they collided into each other ($1,116/$1,111/$1,120 on
        # Sugar River). Above 8 mailings the y-axis carries the scale and the headline
        # figures are in the slide caption.
        if len(cats) <= 8:
            for xi,(b_,a_) in enumerate(zip(bb,aa)):
                if b_: ax.text(xi-w/2,b_+_top*0.015,f"${b_:,.0f}",ha="center",va="bottom",
                               color=NAVY,fontsize=10)
                if a_: ax.text(xi+w/2,a_+_top*0.015,f"${a_:,.0f}",ha="center",va="bottom",
                               color=NAVY,fontweight="bold",fontsize=10)
    h,l=axes[0].get_legend_handles_labels()
    fig.legend(h,l,loc="upper center",frameon=False,fontsize=10,ncol=2,bbox_to_anchor=(0.5,1.07))
    fig.subplots_adjust(top=0.80,wspace=0.16,bottom=0.16)
    save(fig,name)

# The legend states the windows the bars actually cover. It read "3-mo window" as a
# constant, so moving the after side to 6 months (Aaron, 2026-09-08) would have left a
# chart labelled with the old window — the same shape of defect as a hardcoded caption,
# except a validator cannot read a rendered legend.
_BA_B=M.get('ba_before_months',3); _BA_A=M.get('ba_after_months',6)
_BA_L1=f"Before ({_BA_B}-mo baseline)"; _BA_L2=f"After ({_BA_A}-mo window)"

# before/after two-panel (mean) image10
def c_before_after(mean=True):
    ba=M['before_after']; cats=[e['m'] for e in ba]   # "Feb 2024"; _month_axis formats
    if mean:
        sb=[e['sb_mean'] for e in ba]; sa=[e['sa_mean'] for e in ba]
        sbsd=[e['sb_sd'] for e in ba]; sasd=[e['sa_sd'] for e in ba]
        nb=[e['nb_mean'] for e in ba]; na=[e['na_mean'] for e in ba]
        nbsd=[e['nb_sd'] for e in ba]; nasd=[e['na_sd'] for e in ba]
        name='image10'; t1="Avg Monthly Debit Spend / Responder"; t2="Avg Monthly NSF/OD Items / Responder"
        l1=_BA_L1; l2=_BA_L2
    else:
        sb=[e['sb_med'] for e in ba]; sa=[e['sa_med'] for e in ba]; sbsd=sasd=None
        nb=[e['nb_med'] for e in ba]; na=[e['na_med'] for e in ba]; nbsd=nasd=None
        name='image31'; t1="Median Monthly Debit Spend / Responder"; t2="Median NSF/OD Items / Overdraft Participant"
        l1=_BA_L1; l2=_BA_L2
    fig,axes=plt.subplots(1,2,figsize=(DIM[name][0]/DIM[name][1]*4.2,4.2))
    x=np.arange(len(cats)); w=0.4
    for ax,(bb,aa,bs,as_,title,isnsf) in zip(axes,[(sb,sa,sbsd,sasd,t1,False),(nb,na,nbsd,nasd,t2,True)]):
        ax.bar(x-w/2,bb,w,color=STEEL,label=l1,yerr=bs,error_kw=dict(ecolor='#333',lw=0.8,capsize=1.5) if bs else {})
        ax.bar(x+w/2,aa,w,color=ORANGE,label=l2,yerr=as_,error_kw=dict(ecolor='#333',lw=0.8,capsize=1.5) if as_ else {})
        _month_axis(ax,x,cats,fontsize=11)
        ax.set_title(title,color=NAVY,fontweight="bold",fontsize=12,pad=6)
        _clean(ax)
        if not isnsf: ax.yaxis.set_major_formatter(lambda v,p:f"${v:,.0f}")
        ax.tick_params(axis='y',labelsize=12)
        top=max([v+(s if s else 0) for v,s in zip(bb+aa,(bs or [0]*len(bb))+(as_ or [0]*len(aa)))])
        ax.set_ylim(0,top*1.12)
    h,l=axes[0].get_legend_handles_labels()
    fig.legend(h,l,loc="upper center",frameon=False,fontsize=10,ncol=2,bbox_to_anchor=(0.5,1.07))
    fig.subplots_adjust(top=0.80,wspace=0.16,bottom=0.14)
    save(fig,name)
# image11: take rate by branch (new eligible)
def c_take_branch():
    import chart_lib   # shared renderer -> personal + business take-rate charts stay identical
    # top-N by size first, then ordered by branch number for display
    tb=chart_lib.top_branches(M['take_branch'], chart_lib.BRANCH_CAP)
    chart_lib.branch_chart(f"{OUT}/image11.png", tb, ORANGE, NAVY,
                           *DIM['image11'], rate_label="Take rate")
    print("wrote image11")
# image12: swipes & spend combo (workbook 36mo)
def c_swipespend():
    d=B['swipespend_36']; cats=[m.split()[0]+m.split()[1][2:] for m,_,_ in d]
    spend=[s for _,s,_ in d]; cards=[c for _,_,c in d]
    fig,ax=figfor('image12',4.0); x=np.arange(len(cats))
    ax.bar(x,spend,color=STEEL,width=0.66,label="Debit Spend ($M)")
    ax.set_ylabel("Monthly Debit Spend ($M)",color=NAVY,fontsize=10); ax.set_ylim(0,max(spend)*1.15)
    _xmonths(ax,x,cats,cats)
    _clean(ax)
    ax2=ax.twinx(); ax2.plot(x,cards,color=ORANGE,lw=3,label="Accounts w/ Card")
    ax2.set_ylim(0,max(cards)*1.35); ax2.set_ylabel("Accounts w/ Card",color=ORANGE,fontsize=10)
    ax2.tick_params(colors=TICK,length=0); ax2.spines["top"].set_visible(False); ax2.spines["right"].set_color(HAIRLINE)
    h1,l1=ax.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels()
    ax.legend(h1+h2,l1+l2,loc="upper center",frameon=False,ncol=2,bbox_to_anchor=(0.5,1.13),fontsize=10)
    save(fig,'image12')
# donut image13/15
def c_donut(name,vin,vout,vno,pct):
    fig,ax=plt.subplots(figsize=(5,5))
    ax.pie([vin,vout,vno],colors=[ORANGE,NAVY,STEEL],startangle=90,counterclock=False,
           wedgeprops=dict(width=0.42,edgecolor="white",linewidth=2))
    ax.text(0,0.08,f"{pct:.0f}%",ha="center",va="center",fontsize=40,color=NAVY,fontweight="bold")
    ax.text(0,-0.22,"Opted In",ha="center",va="center",fontsize=17,color=NAVY)
    ax.set(aspect="equal"); save(fig,name)
# rege branch image14/16
def c_rege_branch(name,rows,acct_label):
    import chart_lib
    # Largest branches by accounts, ranked best-to-worst on opt-in rate. This
    # took rows[:6] off a list already sorted by RATE, so it showed the six best
    # performers rather than the six biggest branches.
    #
    # It also drew its own bars, a near-copy of the take-rate renderer that had
    # already drifted (its own halo dict, its own headroom, its own tick sizes).
    # Both now go through chart_lib.branch_chart: accounts in the bars, opt-in
    # rate on the line, the program average still the dashed reference the slide
    # caption names.
    rows=chart_lib.top_branches(rows, chart_lib.BRANCH_CAP)
    chart_lib.branch_chart(f"{OUT}/{name}.png", rows, ORANGE, NAVY, *DIM[name],
                           acct_label=acct_label, rate_label="Opt-in rate")
    print("wrote",name)
# reach area image17
def c_reach():
    rc=M['reach']; cats=[x[0] for x in rc]; vals=[x[1] for x in rc]
    fig,ax=figfor('image17',3.0)
    x=np.arange(len(cats))
    ax.fill_between(x,vals,color=ORANGE,alpha=0.9); ax.plot(x,vals,color=ORANGE,lw=2)
    step=max(1,len(cats)//8)
    for i in range(0,len(cats),step): ax.text(i,vals[i]+max(vals)*0.02,f"{vals[i]:,}",ha="center",color=NAVY,fontweight="bold",fontsize=8)
    ax.set_xticks(x[::step]); ax.set_xticklabels(P.axis_months([cats[i] for i in range(0,len(cats),step)]),fontsize=8,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)
    ax.set_ylim(0,max(vals)*1.14); ax.get_yaxis().set_visible(False)
    _clean(ax); ax.spines["left"].set_visible(False)
    save(fig,'image17')
# depth image18
def c_depth():
    d=M['depth']; labels=["Responded once","Twice","3+ times"]; cols=[STEEL,NAVY,NAVY]
    fig,ax=figfor('image18',4.4)
    ax.bar(range(3),d,color=cols,width=0.62)
    for i,v in enumerate(d): ax.text(i,v+max(d)*0.01,f"{v:,}",ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=12)
    ax.set_xticks(range(3)); ax.set_xticklabels(labels,fontsize=10)
    ax.set_ylim(0,max(d)*1.14); ax.get_yaxis().set_visible(False)
    _clean(ax); ax.spines["left"].set_visible(False)
    save(fig,'image18')
# age two-series image19
def c_age():
    a=M['age']; cats=[x[0] for x in a]; elig=[x[1] for x in a]; resp=[x[2] for x in a]
    fig,ax=figfor('image19',4.0); x=np.arange(len(cats)); w=0.4
    ax.bar(x-w/2,elig,w,color=STEEL,label="All eligible (mailed)")
    ax.bar(x+w/2,resp,w,color=ORANGE,label="Responders")
    for i in range(len(cats)):
        ax.text(i-w/2,elig[i]+max(elig)*0.01,f"{elig[i]:,}",ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=9)
        ax.text(i+w/2,resp[i]+max(elig)*0.01,f"{resp[i]:,}",ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(cats,fontsize=10); ax.set_ylim(0,max(elig)*1.16); ax.get_yaxis().set_visible(False)
    _clean(ax); ax.spines["left"].set_visible(False)
    ax.legend(ncol=2,frameon=False,fontsize=10,loc="upper center",bbox_to_anchor=(0.5,1.12))
    save(fig,'image19')
# balance two-series image20
def c_balance():
    b=M['balance']; cats=[x[0] for x in b]; resp=[x[1] for x in b]; non=[x[2] for x in b]
    fig,ax=figfor('image20',4.0); x=np.arange(len(cats)); w=0.4
    ax.bar(x-w/2,resp,w,color=ORANGE,label="Responders")
    ax.bar(x+w/2,non,w,color=STEEL,label="Non-responders")
    for i in range(len(cats)):
        ax.text(i-w/2,resp[i]+max(non+resp)*0.01,f"{resp[i]:,}",ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=9)
        ax.text(i+w/2,non[i]+max(non+resp)*0.01,f"{non[i]:,}",ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(cats,fontsize=10); ax.set_ylim(0,max(non+resp)*1.16); ax.get_yaxis().set_visible(False)
    _clean(ax); ax.spines["left"].set_visible(False)
    ax.legend(ncol=2,frameon=False,fontsize=10,loc="upper center",bbox_to_anchor=(0.5,1.12))
    save(fig,'image20')
# new by product image21 horizontal
def c_new_product():
    p=M['new_products'][:8]; labels=[_fixacr(x[0]) for x in p]; vals=[x[1] for x in p]
    cols=[ORANGE if 'Checking' in l else NAVY for l in labels]
    fig,ax=figfor('image21',2.6)
    y=np.arange(len(vals))[::-1]
    ax.barh(y,vals,color=cols,height=0.7)
    for yi,v in zip(y,vals): ax.text(v+max(vals)*0.01,yi,f"{v:,}",va="center",color=NAVY,fontweight="bold",fontsize=10)
    ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=10); ax.set_xlim(0,max(vals)*1.1); ax.get_xaxis().set_visible(False)
    _clean(ax); ax.spines["bottom"].set_visible(False)
    save(fig,'image21')
# two-bar image22/23
def c_twobar(name,v1,v2,l1,l2,title,fmt):
    fig,ax=figfor(name,4.2)
    ax.bar([0,1],[v1,v2],color=[ORANGE,NAVY],width=0.6)
    for i,v in enumerate([v1,v2]): ax.text(i,v*1.01,fmt(v),ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=14)
    ax.set_xticks([0,1]); ax.set_xticklabels([l1,l2],fontsize=12)
    ax.set_ylim(0,max(v1,v2)*1.18); ax.set_title(title,color=NAVY,fontweight="bold",fontsize=12,pad=8)
    ax.tick_params(axis='y',labelsize=9); _clean(ax)
    save(fig,name)
# debit usage two-panel image24
def c_usage():
    fig,axes=plt.subplots(1,2,figsize=(DIM['image24'][0]/DIM['image24'][1]*4.0,4.0))
    for ax,(v1,v2,title,fmt) in zip(axes,[(M['new_active_pct'],M['book_active_pct'],"% of cards active in month",lambda v:f"{v:.1f}%"),
                                           (M['new_spend_active'],M['book_spend_active'],"Monthly spend / active card",lambda v:f"${v:,}")]):
        ax.bar([0,1],[v1,v2],color=[ORANGE,NAVY],width=0.6)
        for i,v in enumerate([v1,v2]): ax.text(i,v*1.01,fmt(v),ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=13)
        ax.set_xticks([0,1]); ax.set_xticklabels(["New","Open book"],fontsize=11); ax.set_ylim(0,max(v1,v2)*1.2)
        ax.set_title(title,color=NAVY,fontweight="bold",fontsize=11,pad=6); ax.tick_params(axis='y',labelsize=8); _clean(ax)
    fig.subplots_adjust(wspace=0.18); save(fig,'image24')
# new swipe seg image25
def c_new_seg():
    s=M['new_swipe_seg']; cats=[x[0] for x in s]; pct=[x[2] for x in s]
    cols=[ORANGE,NAVY,NAVY,NAVY,ORANGE]
    fig,ax=figfor('image25',3.4)
    ax.bar(range(len(pct)),pct,color=cols,width=0.62)
    for i,v in enumerate(pct): ax.text(i,v+0.4,f"{v:.1f}%",ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=11)
    ax.set_xticks(range(len(pct))); ax.set_xticklabels(cats,fontsize=10); ax.set_ylabel("% of new card holders",color=NAVY,fontsize=10)
    ax.set_ylim(0,max(pct)*1.2); ax.tick_params(axis='y',labelsize=9); _clean(ax)
    ax.set_xlabel("Swipes per month (June 2026)",color=TICK,fontsize=10)
    save(fig,'image25')
# openings/closures area image26
def c_openings():
    oc=M['openings']; cats=[x[0] for x in oc]; cum=[x[3] for x in oc]
    fig,ax=figfor('image26',3.4); x=np.arange(len(cats))
    ax.fill_between(x,cum,0,color=ORANGE,alpha=0.9); ax.plot(x,cum,color=ORANGE,lw=2)
    lo=min(0,min(cum)); hi=max(0,max(cum)); span=(hi-lo) or 1
    off=span*0.03
    ax.axhline(0,color=MUTED,lw=1)                          # zero baseline
    step=max(1,len(cats)//9)
    idxs=list(range(0,len(cats),step))
    if (len(cats)-1) not in idxs: idxs.append(len(cats)-1)   # always label the endpoint (headline net)
    for i in idxs:
        v=cum[i]; above=v>=0
        ax.text(i, v+(off if above else -off), f"{v:+,d}", ha="center",
                va="bottom" if above else "top", color=NAVY, fontweight="bold", fontsize=9)
    ax.set_xticks(x[::step]); ax.set_xticklabels(P.axis_months([cats[i] for i in range(0,len(cats),step)]),fontsize=8,rotation=P.AXIS_ROTATION,ha=P.AXIS_HA)
    ax.set_ylim(lo-span*0.16, hi+span*0.16); ax.get_yaxis().set_visible(False)
    _clean(ax); ax.spines["left"].set_visible(False)
    save(fig,'image26')
# retention survival image27
def c_survival():
    s=M['survival']; cats=[x[0] for x in s]; vals=[x[1] for x in s]
    fig,ax=figfor('image27',3.4); x=np.arange(len(cats))
    ax.fill_between(x,vals,color=ORANGE,alpha=0.9); ax.plot(x,vals,color=ORANGE,lw=2,marker='o',mfc='white',mec=ORANGE,ms=8,mew=2)
    for i,v in enumerate(vals):
        lbl="100" if i==0 else f"{v:.0f}%"
        ax.text(i,v+1.2,lbl,ha="center",color=NAVY,fontweight="bold",fontsize=11)
    ax.set_xticks(x); ax.set_xticklabels(cats,fontsize=10); ax.set_ylabel("% still open",color=NAVY,fontsize=10)
    ax.set_ylim(min(vals)*0.9,104); ax.tick_params(axis='y',labelsize=9); _clean(ax)
    save(fig,'image27')
# dot plot image28
def c_dotplot():
    h=M['dot_hist']; xs=[k for k,_ in h]; ys=[v for _,v in h]
    fig,ax=figfor('image28',4.4)
    ax.vlines(xs,0,ys,color=NAVY,lw=1.4)
    ax.plot(xs,ys,'o',color=ORANGE,ms=4)
    ax.axvline(M['dot_median'],ls=':',color=ORANGE,lw=2)
    ax.axvline(M['dot_mean'],ls='--',color=NAVY,lw=2)
    ax.text(M['dot_median']+0.4,max(ys)*0.82,f"Median +{M['dot_median']:.0f}",color=ORANGE,fontweight="bold",fontsize=11)
    ax.text(M['dot_mean']+0.4,max(ys)*0.92,f"Mean +{M['dot_mean']}",color=NAVY,fontweight="bold",fontsize=11)
    ax.set_xlabel("Transaction increase over the ask  (actual − goal, month after offer)",color=TICK,fontsize=10)
    ax.set_ylabel("Number of responders",color=NAVY,fontsize=10)
    ax.set_xticks([0,5,10,15,20,25,30,35,40]); ax.set_xticklabels(['0','5','10','15','20','25','30','35','40+'],fontsize=9)
    ax.tick_params(axis='y',labelsize=9); _clean(ax); ax.set_ylim(0,max(ys)*1.05)
    save(fig,'image28')
# nsf over time combo image29
def c_nsf():
    ns=M['nsf_series']; cats=[x[0] for x in ns]; items=[x[1] for x in ns]; accts=[x[2] for x in ns]
    fig,ax=figfor('image29',4.0); x=np.arange(len(cats))
    ax.bar(x,items,color=STEEL,width=0.66,label="NSF/OD items")
    ax.set_ylabel("NSF/OD items / month",color=NAVY,fontsize=10); ax.set_ylim(0,max(items)*1.2)
    _xmonths(ax,x,cats,[c[:3]+c[-2:] for c in cats])
    _clean(ax)
    ax2=ax.twinx(); ax2.plot(x,accts,color=ORANGE,lw=3,label="Accounts with NSF/OD")
    ax2.set_ylim(0,max(accts)*1.5); ax2.set_ylabel("Accounts with activity",color=ORANGE,fontsize=10)
    ax2.tick_params(colors=TICK,length=0); ax2.spines["top"].set_visible(False); ax2.spines["right"].set_color(HAIRLINE)
    h1,l1=ax.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels()
    ax.legend(h1+h2,l1+l2,loc="upper center",frameon=False,ncol=2,bbox_to_anchor=(0.5,1.12),fontsize=10)
    save(fig,'image29')
# rege vintage combo image30
def c_vintage():
    v=M['rege_vintage']; cats=[x[0] for x in v]; allh=[x[2] for x in v]; ipp=[x[3] for x in v]; parto=[x[4] for x in v]
    fig,ax=figfor('image30',4.0); x=np.arange(len(cats)); w=0.4
    ax.bar(x-w/2,allh,w,color=STEEL,label="All debit holders")
    ax.bar(x+w/2,parto,w,color=ORANGE,label="Overdraft participants")
    for i in range(len(cats)):
        # these are opt-in RATES — a bare "27" beside a "27%" axis reads as a count
        # (Aaron, 2026-08-28)
        # the NSF/OD line on ax2 runs straight through these labels (it struck out
        # "29%" at 2022 and "30%" at 2025 on Wellworth), so each sits on a white pad —
        # the same treatment the bayes chart uses where a line crosses a label
        _lb=dict(boxstyle="round,pad=0.12",fc="white",ec="none")
        ax.text(i-w/2,allh[i]+0.5,f"{allh[i]}%",ha="center",va="bottom",color=NAVY,
                fontweight="bold",fontsize=8,bbox=_lb,zorder=6)
        ax.text(i+w/2,parto[i]+0.5,f"{parto[i]}%",ha="center",va="bottom",color=NAVY,
                fontweight="bold",fontsize=8,bbox=_lb,zorder=6)
    ax.set_ylabel("Reg E opt-in rate",color=NAVY,fontsize=10); ax.set_ylim(0,max(allh+parto)*1.45)
    ax.yaxis.set_major_formatter(lambda v,_p:f"{v:.0f}%")
    ax.set_xticks(x); ax.set_xticklabels(cats,fontsize=9,rotation=0); _clean(ax); ax.tick_params(axis='y',labelsize=9)
    ax2=ax.twinx(); ax2.plot(x,ipp,color=NAVY,lw=2,marker='o',mfc='white',mec=NAVY,ms=6,label="NSF/OD items per participant / mo")
    ax2.set_ylim(0,max(ipp)*1.5); ax2.set_ylabel("NSF/OD items per participant / month",color=NAVY,fontsize=9)
    ax2.tick_params(colors=TICK,length=0); ax2.spines["top"].set_visible(False)
    h1,l1=ax.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels()
    ax.legend(h1+h2,l1+l2,loc="upper center",frameon=False,ncol=2,bbox_to_anchor=(0.5,1.18),fontsize=9)
    fig.subplots_adjust(top=0.84)
    save(fig,'image30')
# bayes tree image32
def c_bayes():
    fig,ax=plt.subplots(figsize=(DIM['image32'][0]/DIM['image32'][1]*4.4,4.4)); ax.axis('off')
    ax.set_xlim(0,10); ax.set_ylim(0,10)
    def box(x,y,w,h,text,fc,tc="white",fs=11):
        ax.add_patch(plt.Rectangle((x,y),w,h,fc=fc,ec="none",zorder=2))
        ax.text(x+w/2,y+h/2,text,ha="center",va="center",color=tc,fontsize=fs,fontweight="bold",zorder=3)
    # root (wider box + smaller font so text fits inside)
    box(0.05,4.3,2.75,1.5,f"New consumer\naccount\n(prior {M['bayes_prior']}% close)",NAVY,fs=8.5)
    box(3.6,6.2,2.2,1.4,"Used debit\ncard early",STEEL,fs=11)
    box(3.6,2.4,2.2,1.4,"No early\nuse",STEEL,fs=11)
    _pl=dict(ha="center",va="center",zorder=5)   # % labels centered on the line midpoint, white bbox masks the line
    _bb=dict(boxstyle="round,pad=0.22",fc="white",ec="none")
    ax.plot([2.8,3.6],[5.4,6.9],color=NAVY,lw=1.5,zorder=1); ax.text(3.2,6.15,f"{M['bayes_p_used']}%",color=NAVY,fontsize=10,fontweight="bold",bbox=_bb,**_pl)
    ax.plot([2.8,3.6],[4.7,3.1],color=NAVY,lw=1.5,zorder=1); ax.text(3.2,3.9,f"{100-M['bayes_p_used']}%",color=NAVY,fontsize=10,fontweight="bold",bbox=_bb,**_pl)
    box(7.0,7.0,2.4,1.0,"Closes yr 1",ORANGE,fs=11); box(7.0,5.7,2.4,1.0,"Stays open",GREY,tc=NAVY,fs=11)
    box(7.0,3.2,2.4,1.0,"Closes yr 1",ORANGE,fs=11); box(7.0,1.9,2.4,1.0,"Stays open",GREY,tc=NAVY,fs=11)
    ax.plot([5.8,7.0],[6.9,7.5],color=ORANGE,lw=1.8,zorder=1); ax.text(6.4,7.2,f"{M['bayes_close_used']}%",color=ORANGE,fontsize=10,fontweight="bold",bbox=_bb,**_pl)
    ax.plot([5.8,7.0],[6.9,6.2],color=STEEL,lw=1.5,zorder=1); ax.text(6.4,6.55,f"{100-M['bayes_close_used']:.1f}%",color=NAVY,fontsize=9,fontweight="bold",bbox=_bb,**_pl)
    ax.plot([5.8,7.0],[3.1,3.7],color=ORANGE,lw=1.8,zorder=1); ax.text(6.4,3.4,f"{M['bayes_close_notused']}%",color=ORANGE,fontsize=10,fontweight="bold",bbox=_bb,**_pl)
    ax.plot([5.8,7.0],[3.1,2.4],color=STEEL,lw=1.5,zorder=1); ax.text(6.4,2.75,f"{100-M['bayes_close_notused']:.1f}%",color=NAVY,fontsize=9,fontweight="bold",bbox=_bb,**_pl)
    save(fig,'image32')

c_monthly(); c_ranking(); c_mailer(); c_movement(); c_sustained()
c_before_after(True); c_before_after_split(); c_take_branch(); c_swipespend()
c_donut('image13',M['rege_in'],M['rege_out'],M['rege_no'],M['rege_pct'])
c_donut('image15',M['rege_new_in'],M['rege_new_out'],M['rege_new_no'],M['rege_new_pct'])
# image14 is the whole eligible book, image16 only accounts opened in the last 12
# months — so the bars mean different things and the axis has to say which.
c_rege_branch('image14',M['rege_branch'],'Card-holding accounts')
c_rege_branch('image16',M['rege_new_branch'],'Accounts opened')
c_reach(); c_depth(); c_age(); c_balance(); c_new_product()
c_twobar('image22',M['new_chk_avgbal'],M['open_chk_avgbal'],"New","Open book","Average checking balance",lambda v:f"${v:,}")
c_twobar('image23',M['new_chk_debit_pct'],M['open_chk_debit_pct'],"New","Open book","% of checking accounts with a debit card",lambda v:f"{v:.1f}%")
c_usage(); c_new_seg(); c_openings(); c_survival(); c_dotplot(); c_nsf(); c_vintage(); c_bayes()
print("ALL CHARTS DONE")
