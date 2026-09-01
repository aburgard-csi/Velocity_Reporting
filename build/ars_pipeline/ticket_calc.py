import csv, statistics, json, sys, re, datetime
F=sys.argv[1]; OUT=sys.argv[2]
with open(F,encoding='latin-1') as fh:
    rows=list(csv.reader(x.replace('\x00','') for x in fh))
hdr=rows[4]; data=rows[5:]; idx={c.strip():i for i,c in enumerate(hdr)}
# Months come from the extract, in order. This used to be a literal list ending
# Jun26 filtered to what existed, which silently dropped every month after Jun26
# (so a newer pull kept reporting a stale trailing quarter).
MONTHS=sorted({m.group(1) for m in
               (re.match(r'^([A-Z][a-z]{2}\d{2}) Sig #$',c.strip()) for c in hdr) if m},
              key=lambda t: datetime.datetime.strptime(t,'%b%y'))
if not MONTHS: raise SystemExit('ERROR: no "<Mon><yy> Sig #" columns in the ODD')
mpos={m:i for i,m in enumerate(MONTHS)}
# Shared ODD vocabulary. personal() previously read `!= 'yes'` here, which made
# a BLANK Business? cell personal — while metrics_gen read `== 'No'`, which made
# it business. Two slides of one deck, two denominators. odd_rows follows the
# three-way split product_mix_slide already used: a blank is neither.
from odd_rows import accessors
_odd=accessors(idx)
sw=_odd.swipes; sp=_odd.spend; personal=_odd.personal
RESPM=[m for m in MONTHS if (m+' Resp') in idx]
WIN=MONTHS[-3:]  # trailing quarter

# cross-sectional avg ticket by monthly-swipe tier
segdef=[('1-5',1,5),('6-10',6,10),('11-15',11,15),('16-20',16,20),('21-25',21,25),('26+',26,10**9)]
seg_sw={s[0]:0.0 for s in segdef}; seg_sp={s[0]:0.0 for s in segdef}; tot_sw=tot_sp=0.0
for row in data:
    if not personal(row): continue
    tsw=sum(sw(row,m) for m in WIN); tsp=sum(sp(row,m) for m in WIN)
    if tsw<=0: continue
    permo=tsw/len(WIN)
    for name,lo,hi in segdef:
        if lo<=permo<=hi: seg_sw[name]+=tsw; seg_sp[name]+=tsp; break
    tot_sw+=tsw; tot_sp+=tsp
segments=[[n, round(seg_sp[n]/seg_sw[n],2)] for n,_,_ in segdef if seg_sw[n]>0]
blended=round(tot_sp/tot_sw,2)

# responder baseline vs response ticket
base_tk=[]; resp_tk=[]; bsw_t=bsp_t=rsw_t=rsp_t=0.0
for row in data:
    if not personal(row): continue
    for rm in RESPM:
        if not row[idx[rm+' Resp']].strip(): continue
        p=mpos[rm]; bms=MONTHS[max(0,p-6):p]; rms=MONTHS[p:p+3]
        bsw=sum(sw(row,m) for m in bms); bsp=sum(sp(row,m) for m in bms)
        rsw=sum(sw(row,m) for m in rms); rsp=sum(sp(row,m) for m in rms)
        if bsw>0 and rsw>0:
            base_tk.append(bsp/bsw); resp_tk.append(rsp/rsw)
            bsw_t+=bsw; bsp_t+=bsp; rsw_t+=rsw; rsp_t+=rsp
R={'segments':segments,'blended':blended,'win':WIN,
   'base_mean':round(bsp_t/bsw_t,2),'resp_mean':round(rsp_t/rsw_t,2),
   'base_med':round(statistics.median(base_tk),2),'resp_med':round(statistics.median(resp_tk),2),
   'base_swpm':round(bsw_t/len(base_tk)/6,1),'resp_swpm':round(rsw_t/len(resp_tk)/3,1),
   'n_resp':len(base_tk),'win_label':f"{WIN[0]}–{WIN[-1]}"}
json.dump(R,open(OUT,'w', encoding="utf-8"),indent=1); print(json.dumps(R,indent=1))
