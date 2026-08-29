import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))  # build/
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json, sys
from rpe_env import use_font
L=json.load(open(sys.argv[1])); OUT=sys.argv[2]
from brand import NAVY, ROWALT as GREY, TICK
use_font("Carlito")
cols=L['matrix_cols']; mrows=L['matrix_rows']; rev=L['revseg']
fig=plt.figure(figsize=(13.0,4.5))
TOP=0.06; HGT=0.72   # both tables share top & height -> aligned top/bottom, balanced
# ---- left matrix ----
axL=fig.add_axes([0.015,TOP,0.60,HGT]); axL.axis('off')
hdr=['Base / Now →']+[c.replace(' Plus','+') for c in cols]
tbl=[hdr]+[[r[0].replace('NU','Non-User')]+[('' if v is None else f"${v:,.2f}") for v in r[1:]] for r in mrows]
t1=axL.table(cellText=tbl,cellLoc='center',loc='center',bbox=[0,0,1,1],colWidths=[0.205]+[0.1325]*6); t1.auto_set_font_size(False); t1.set_fontsize(12)
for (r,c),cell in t1.get_celld().items():
    cell.set_edgecolor('white'); cell.set_linewidth(1.5)
    if r==0: cell.set_facecolor(NAVY); cell.get_text().set_color('white'); cell.get_text().set_fontweight('bold')
    else:
        cell.set_facecolor(GREY if r%2==0 else 'white'); cell.get_text().set_color(NAVY)
        if c==0: cell.get_text().set_ha('left'); cell.get_text().set_fontweight('bold')
axL.set_title("Monthly incremental revenue lift per account ($)",color=NAVY,fontsize=13,fontweight='bold',loc="left",pad=28)
axL.text(0,1.02,"Rows = baseline segment · Columns = current swipe tier",transform=axL.transAxes,color=TICK,fontsize=9.5)
# ---- right segmentation (same top & height => aligned) ----
axR=fig.add_axes([0.655,TOP,0.33,HGT]); axR.axis('off')
stbl=[['Segment','Distribution','DDA Value']]
for name,dist,dda in rev:
    stbl.append([name, f"{round(100*dist)}%" if isinstance(dist,(int,float)) else str(dist),
                 f"${dda:,.2f}" if isinstance(dda,(int,float)) else str(dda)])
t2=axR.table(cellText=stbl,cellLoc='center',loc='center',bbox=[0,0,1,1],colWidths=[0.40,0.31,0.29]); t2.auto_set_font_size(False); t2.set_fontsize(11)
for (r,c),cell in t2.get_celld().items():
    cell.set_edgecolor('white'); cell.set_linewidth(1.5)
    if r==0: cell.set_facecolor(NAVY); cell.get_text().set_color('white'); cell.get_text().set_fontweight('bold')
    else:
        cell.set_facecolor(GREY if r%2==0 else 'white'); cell.get_text().set_color(NAVY)
        if c==0: cell.get_text().set_ha('left')
axR.set_title("Revenue Segmentation",color=NAVY,fontsize=13,fontweight='bold',loc="left",pad=28)
axR.text(0,1.02,"Distribution of card accounts · monthly DDA value per account",transform=axR.transAxes,color=TICK,fontsize=9.5)
fig.savefig(OUT,dpi=200,bbox_inches='tight',facecolor='white',pad_inches=0.08)
print('wrote',OUT)
