import openpyxl, json, sys, datetime
wb=openpyxl.load_workbook(sys.argv[1],read_only=True,data_only=True); out={}
def ml(v): return v.strftime('%b %Y') if isinstance(v,datetime.datetime) else v
# --- Lift Matrix MM current window (first block, rows ~8-18) ---
lm=wb['Lift Matrix MM']
# find header row 'Baseline Segment' near top
hdr_r=None
for r in range(8,22):
    if lm.cell(r,2).value=='Baseline Segment': hdr_r=r; break
cols=[lm.cell(hdr_r,c).value for c in range(3,9)]  # 1-5,6-10,11-15,16-20,21-25,26 Plus
rows=[]
for r in range(hdr_r+1,hdr_r+7):
    seg=lm.cell(r,2).value
    if not seg: break
    vals=[lm.cell(r,c).value for c in range(3,9)]
    rows.append([seg]+[(round(v,2) if isinstance(v,(int,float)) else None) for v in vals])
out['matrix_cols']=cols; out['matrix_rows']=rows
# window dates (Start/End above header) and validity: data must fall within [Start, End], else
# revenue is stale. One definition in lift_window, shared with the launcher's pre-build check.
import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from lift_window import window as _lift_window
out.update(_lift_window(lm, hdr_r))
# --- DCO MM distribution + spend (card-holding buckets) ---
dco=wb['DCO MM']
def findrow(label,c=4):
    for r in range(20,60):
        v=dco.cell(r,c).value
        if isinstance(v,str) and label in v: return r
    return None
# card holding total
tot_r=None
for r in range(20,45):
    v=dco.cell(r,3).value
    if isinstance(v,str) and 'Card Holding Accounts' in v and dco.cell(r,4).value is None:
        tot_r=r; break
buckets=[('Non Users','NU'),('(1-5','1-5'),('(6-10','6-10'),('(11-15','11-15'),('(16-20','16-20'),('(21-25','21-25'),('(25+','26 Plus')]
seg=[]; total_acct=0
for r in range(20,55):
    lab=dco.cell(r,4).value
    if not isinstance(lab,str): continue
    for key,name in buckets:
        if lab.startswith(key) or key in lab:
            acct=dco.cell(r,5).value; spend=dco.cell(r,7).value
            if isinstance(acct,(int,float)) and acct>0 and r<37:  # first (spend) block only, not RegE block
                seg.append([name,int(acct),float(spend) if isinstance(spend,(int,float)) else 0]); total_acct+=int(acct)
            break
# dedupe (keep first occurrence per name)
seen=set(); seg2=[]
for name,a,s in seg:
    if name in seen: continue
    seen.add(name); seg2.append([name,a,s])
out['seg']=seg2; out['card_total']=sum(a for _,a,_ in seg2)

# --- Revenue Segmentation block (Segments | Distribution | DDA Value), to the right ---
seg_hdr=None; seg_col=None
for r in range(8,22):
    for c in range(9,16):
        if lm.cell(r,c).value=='Segments': seg_hdr=r; seg_col=c; break
    if seg_hdr: break
revseg=[]
if seg_hdr:
    for r in range(seg_hdr+1,seg_hdr+12):
        name=lm.cell(r,seg_col).value
        if not name: break
        dist=lm.cell(r,seg_col+1).value; dda=lm.cell(r,seg_col+2).value
        revseg.append([name, (round(dist,4) if isinstance(dist,(int,float)) else dist),
                             (round(dda,2) if isinstance(dda,(int,float)) else dda)])
out['revseg']=revseg

print(json.dumps(out,indent=1,default=str))
