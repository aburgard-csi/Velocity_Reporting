import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np, json, sys
from PIL import Image
R=json.load(open(sys.argv[1])); OUTPNG=sys.argv[2]
NAVY="#00274C"; ORANGE="#F47A29"; STEEL="#7B9BB8"; TICK="#5A6670"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":13})
def clean(ax):
    for sp in ["top","right"]: ax.spines[sp].set_visible(False)
    ax.spines["left"].set_visible(False); ax.spines["bottom"].set_color("#B8C0CA")
    ax.tick_params(colors=TICK,length=0); ax.set_axisbelow(True)
CW,CH=2200,790                      # exact canvas px, aspect ~2.785 (frame 12.40 x 4.45)
fig=plt.figure(figsize=(CW/170,CH/170)); fig.patch.set_facecolor("white")
gs=fig.add_gridspec(1,2,width_ratios=[1.65,1.0],wspace=0.26,left=0.045,right=0.985,top=0.83,bottom=0.14)

tiers=[s[0] for s in R['segments']]; tk=[s[1] for s in R['segments']]; blend=R['blended']
ax=fig.add_subplot(gs[0,0])
bars=ax.bar(tiers,tk,color=NAVY,width=0.66); bars[-1].set_color(ORANGE)
mx=max(tk)
for i,v in enumerate(tk):
    ax.text(i,v+mx*0.02,f"${v:.0f}",ha="center",va="bottom",color=NAVY,fontweight="bold",fontsize=15)
ax.axhline(blend,ls="--",color=ORANGE,lw=2)
ax.text(0.02,blend+mx*0.02,f"Blended ${blend:.0f}",ha="left",va="bottom",color=ORANGE,fontsize=12,fontweight="bold")
ax.set_ylim(0,mx*1.16); ax.get_yaxis().set_visible(False)
ax.set_xlabel("Monthly swipe tier",color=TICK,fontsize=13)
ax.set_title("Average ticket falls as usage rises",color=NAVY,fontsize=16,fontweight="bold",pad=12,loc="left")
ax.tick_params(axis='x',labelsize=14); [t.set_color(NAVY) for t in ax.get_xticklabels()]
clean(ax)

ax2=fig.add_subplot(gs[0,1])
labels=['Mean','Median']; base=[R['base_mean'],R['base_med']]; resp=[R['resp_mean'],R['resp_med']]
x=np.arange(2); w=0.36
b1=ax2.bar(x-w/2,base,w,color=STEEL,label='Baseline (6 mo pre-mail)')
b2=ax2.bar(x+w/2,resp,w,color=ORANGE,label='Response (mail mo +3)')
m2=max(base+resp)
for rr in (b1,b2):
    for r in rr: ax2.text(r.get_x()+r.get_width()/2,r.get_height()+m2*0.015,f"${r.get_height():.0f}",ha="center",va="bottom",color=NAVY,fontsize=13,fontweight="bold")
ax2.set_xticks(x); ax2.set_xticklabels(labels,color=NAVY,fontsize=14)
ax2.set_ylim(0,m2*1.30); ax2.get_yaxis().set_visible(False)
ax2.set_title("Ticket holds through response",color=NAVY,fontsize=16,fontweight="bold",pad=12,loc="left")
ax2.text(0.5,0.905,f"Monthly swipes {R['base_swpm']} → {R['resp_swpm']}",transform=ax2.transAxes,ha="center",color=TICK,fontsize=11.5,style="italic")
ax2.legend(loc="upper center",bbox_to_anchor=(0.5,-0.09),ncol=2,frameon=False,fontsize=10.5,handlelength=1.1,columnspacing=1.4)
clean(ax2)

tmp=OUTPNG+".tmp.png"
fig.savefig(tmp,dpi=170,facecolor="white",bbox_inches="tight",pad_inches=0.10); plt.close(fig)
im=Image.open(tmp).convert("RGB"); iw,ih=im.size
sc=min(CW/iw,CH/ih); nw,nh=round(iw*sc),round(ih*sc)
im2=im.resize((nw,nh),Image.LANCZOS)
cv=Image.new("RGB",(CW,CH),"white"); cv.paste(im2,((CW-nw)//2,(CH-nh)//2)); cv.save(OUTPNG)
import os; os.remove(tmp); print("wrote",OUTPNG,cv.size)
