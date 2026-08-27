import csv, statistics, json, datetime, re
from collections import defaultdict, Counter
csv.field_size_limit(10**7)
import sys
F=sys.argv[1]
def _linesrc(path):
    """Decoded latin-1 lines from a .zip (in-stream) or plain CSV.

    Several ODDD zips carry the raw monthly transaction file as a SECOND .csv
    (1038, 1549, ...). Taking the first .csv picks that transaction dump instead
    of the ODD extract, and metrics_gen then dies with
    'itemgetter expected 1 argument, got 0' because no expected column matches.
    Select the ODD member by name; fall back to the largest .csv.
    """
    if path.lower().endswith('.zip'):
        import zipfile, io
        zf=zipfile.ZipFile(path)
        _csvs=[n for n in zf.namelist() if n.lower().endswith('.csv')]
        if not _csvs: raise SystemExit(f'ERROR: no .csv inside {path}')
        _odd=[n for n in _csvs if '-odd' in n.lower() or '_v2_' in n.lower()]
        name=_odd[0] if _odd else max(_csvs,key=lambda n: zf.getinfo(n).file_size)
        return io.TextIOWrapper(zf.open(name),encoding='latin-1',errors='replace',newline='')
    return open(path,encoding='latin-1',errors='replace')

def _latest_month(hdr):
    """Latest monthly column present, e.g. 'Jul26'. Derived per extract — the
    snapshot month moves with every ODD pull, so it must never be hardcoded."""
    _ms=[re.match(r'^([A-Z][a-z]{2}\d{2}) Sig #$',h) for h in hdr]
    _ms=[m.group(1) for m in _ms if m]
    if not _ms: raise SystemExit('ERROR: no "<Mon><yy> Sig #" columns in the extract')
    return sorted(_ms,key=lambda t: datetime.datetime.strptime(t,'%b%y'))[-1]
import os as _os, pickle as _pk
if F.endswith('.pkl'):
    hdr, _need, _redhdr, data = _pk.load(open(F, 'rb'))
    H = {h: j for j, h in enumerate(_redhdr)}
else:
    # header row (index 4)
    with _linesrc(F) as _fh:
        _head=[]
        for _i,_l in enumerate(_fh):
            _head.append(_l)
            if _i>=4: break
    hdr=[h.strip() for h in next(csv.reader([_head[4].replace('\x00','')]))]
    # project to the columns metrics_gen actually uses (cuts ~1/3 of the file from memory
    # so a big client fits; logic below is unchanged, H just maps to the kept columns)
    _LATEST=_latest_month(hdr)
    _STATIC={f'{_LATEST} Elig','Debit?','Stat Desc','Business?',
             f'{_LATEST} Reg E Desc','Branch',
             'Date Opened','Date Closed','DOB','Avg Bal','Curr Bal','Prod Desc'}
    _MFAM=re.compile(r'^[A-Z][a-z]{2}\d{2} (Sig #|PIN #|Sig \$|PIN \$|MTD|Mail|Resp)$')
    _need=[i for i,c in enumerate(hdr) if c in _STATIC or _MFAM.match(c)]
    _redhdr=[hdr[i] for i in _need]; H={h:j for j,h in enumerate(_redhdr)}
    import operator as _op
    _get=_op.itemgetter(*_need); _pad=max(_need)+1
    data=[]; _dapp=data.append
    with _linesrc(F) as _fh:
        _rdr=csv.reader((l.replace('\x00','') for l in _fh))
        for _k,_row in enumerate(_rdr):
            if _k<5: continue
            if len(_row)<_pad: _row=_row+['']*(_pad-len(_row))
            if ''.join(_row).strip():
                _dapp(list(_get(_row)))
    if _os.environ.get('MG_DUMP'):
        _pk.dump((hdr, _need, _redhdr, data), open(_os.environ['MG_DUMP'], 'wb')); sys.exit(0)
def g(r,n):
    i=H.get(n); return (r[i].strip() if i is not None and i<len(r) else '')
def fnum(r,n):
    v=g(r,n).replace(',','').replace('$','')
    if v in ('','-'): return 0.0
    try: return float(v)
    except: return 0.0
def mkey(t): return datetime.datetime.strptime(t,'%b%y')
smonths=sorted({re.match(r'^([A-Z][a-z]{2}\d{2}) Sig #',h).group(1) for h in hdr if re.match(r'^[A-Z][a-z]{2}\d{2} Sig #',h)},key=mkey)
mailmonths=sorted({re.match(r'^([A-Z][a-z]{2}\d{2}) Mail',h).group(1) for h in hdr if re.match(r'^[A-Z][a-z]{2}\d{2} Mail',h)},key=mkey)
nextm={smonths[i]:smonths[i+1] for i in range(len(smonths)-1)}
# Snapshot month of THIS extract — every "as of" reference below derives from it
# so a new ODD pull doesn't silently drop the Elig / Reg E columns or read the
# wrong month (these were hardcoded to Jun26; fixed 2026-08-17).
LATEST=_latest_month(hdr)
def lbl(t): return mkey(t).strftime("%b %Y")
RESP_MET={'NU 5+','TH-10','TH-15','TH-20','TH-25'}
OFFER_GOAL={'NU':5,'TH-10':10,'TH-15':15,'TH-20':20,'TH-25':25}
RESP_GOAL={'NU 5+':5,'TH-10':10,'TH-15':15,'TH-20':20,'TH-25':25}
TIER_ORDER=['NU 5+','TH-10','TH-15','TH-20','TH-25']
def swipes(r,m): return fnum(r,f'{m} Sig #')+fnum(r,f'{m} PIN #')
def spend(r,m): return fnum(r,f'{m} Sig $')+fnum(r,f'{m} PIN $')
def nsf(r,m): return fnum(r,f'{m} MTD')
def hascard(r): return g(r,'Debit?')=='Yes'
OPEN={'Open','Active','Open/Active','Dormant','Inactive','Restricted','No Close on Zero Balance','No Post: Force Pay Items Only',
      # core lifecycle wording (Aaron 2026-07-25)
      'New This Cycle','Pending Activation'}
CLOSED={'Closed','Charge-off','Charge-Off','Charged Off','Charged-Off',
        # core lifecycle wording (Aaron 2026-07-25)
        'Purge at Yearend','Purge at Year End','Pending Closeout','Pending Close Out'}
def isopen(r):
    sd=g(r,'Stat Desc'); return sd.startswith('Open') or sd.startswith('Active') or sd in OPEN
def personal(r): return g(r,'Business?')=='No'
def parsed(r,f):
    v=g(r,f)
    for fmt in ('%m/%d/%Y','%Y-%m-%d %H:%M:%S','%Y-%m-%d','%m/%d/%y'):
        try: return datetime.datetime.strptime(v,fmt)
        except: pass
    return None
_lm=mkey(LATEST)
NOW=(_lm.replace(day=28)+datetime.timedelta(days=4)).replace(day=1)-datetime.timedelta(days=1)
M=out={}
# cohorts
elig=[r for r in data if personal(r) and g(r,f'{LATEST} Elig')=='Yes']
def responded(r): return any(g(r,f'{m} Resp') in RESP_MET for m in mailmonths)
responders=[r for r in elig if responded(r)]
nonresp=[r for r in elig if not responded(r)]
M['n_eligible']=len(elig); M['n_responders']=len(responders); M['n_nonresp']=len(nonresp)
M['overall_take']=round(100*sum(1 for r in elig if hascard(r))/len(elig),1)

# ---- swipe tier (slide 8) ----
w3=smonths[-3:]   # trailing 3 months of THIS extract
def sw3(r): return sum(swipes(r,m) for m in w3)/3
def sp3(r): return sum(spend(r,m) for m in w3)/3
def ns3(r): return sum(nsf(r,m) for m in w3)/3
def tier(r):
    if not hascard(r): return 'No Debit Card'
    s=sw3(r)
    if s<1: return 'Non-User'
    for lo,hi,nm in [(1,5,'1-5'),(6,10,'6-10'),(11,15,'11-15'),(16,20,'16-20'),(21,25,'21-25')]:
        if lo<=s<=hi: return nm
    return '26+'
agg=defaultdict(lambda:[0,0.0,0.0,0.0])
for r in elig:
    t=tier(r); a=agg[t]; a[0]+=1; a[1]+=sw3(r); a[2]+=sp3(r); a[3]+=ns3(r)
order=['No Debit Card','Non-User','1-5','6-10','11-15','16-20','21-25','26+']
M['swipe_tier']=[[t,agg[t][0],round(agg[t][1]),round(agg[t][2]),round(agg[t][3])] for t in order]
M['swipe_tier_total']=[sum(agg[t][0] for t in order),round(sum(agg[t][1] for t in order)),
                       round(sum(agg[t][2] for t in order)),round(sum(agg[t][3] for t in order))]

# ---- ranking by tier per mailing (slide 11) recent 12 ----
recent12=mailmonths[:] 
# mailings with responders, mature (<= May26)
mature=[m for m in mailmonths if m in nextm]  # has a following month
recent=mature[-12:]
rank=[]
for m in recent:
    c=Counter(g(r,f'{m} Resp') for r in elig if g(r,f'{m} Resp') in RESP_MET)
    rank.append([lbl(m)]+[c.get(t,0) for t in TIER_ORDER])
M['ranking']=rank  # newest last

# ---- mailing response summary (slide 12), computed from the ODD ----
# Was read out of the workbook as percentages only, which disagreed with the latest-mailer
# slide: the workbook's denominator is not the mailed population, so 1549 read 16.3% on
# slide 12 and 10.7% on slide 14 for the same Jun 2026 drop (Aaron, 2026-08-20). Both now
# use the same definition — offers sent = personal accounts carrying a `<mon> Mail` value,
# responders = those whose `<mon> Resp` reached a goal tier. Newest mailing first.
msum=[]
for m in reversed(recent):
    sent=[r for r in data if personal(r) and g(r,f'{m} Mail')]
    if not sent: continue
    rs=[r for r in sent if g(r,f'{m} Resp') in RESP_MET]
    nu=sum(1 for r in rs if g(r,f'{m} Resp')=='NU 5+')
    msum.append([lbl(m), len(sent), len(rs),
                 round(100*nu/len(sent),1),
                 round(100*(len(rs)-nu)/len(sent),1),
                 round(100*len(rs)/len(sent),1)])
M['mail_summary']=msum
_tot_sent=sum(x[1] for x in msum); _tot_rs=sum(x[2] for x in msum)
# Weighted on offers sent, not a mean of rates — a mean would let a small drop swing the
# program average as hard as a large one.
M['mail_summary_total']=[_tot_sent, _tot_rs,
                         round(sum(x[3]*x[1] for x in msum)/_tot_sent,1) if _tot_sent else 0.0,
                         round(sum(x[4]*x[1] for x in msum)/_tot_sent,1) if _tot_sent else 0.0,
                         round(100*_tot_rs/_tot_sent,1) if _tot_sent else 0.0]

# ---- latest mailer (slide 12/13) ----
latest=mature[-1]
mailed=[r for r in data if g(r,f'{latest} Mail')]  # anyone mailed
mailed_p=[r for r in mailed if personal(r)]
resp_latest=[r for r in mailed_p if g(r,f'{latest} Resp') in RESP_MET]
M['latest_mailing']=lbl(latest)
M['latest_mailed']=len(mailed_p); M['latest_responders']=len(resp_latest)
M['latest_resprate']=round(100*len(resp_latest)/len(mailed_p),1)
M['latest_tier']=[ [t, sum(1 for r in resp_latest if g(r,f'{latest} Resp')==t)] for t in TIER_ORDER]
# movement vs prior mailing — the loop below scans every earlier mailing, so no
# second-to-last mailing is needed. (Was `prior=mature[-2]`, dead but fatal for a
# client with one mailing, e.g. 1549 Wellworth.)
def tier_rank(v): return TIER_ORDER.index(v) if v in TIER_ORDER else -1
mv=Counter()
for r in resp_latest:
    cur=g(r,f'{latest} Resp')
    pv=None
    for mm2 in [x for x in mailmonths if mkey(x)<mkey(latest)]:
        if g(r,f'{mm2} Resp') in RESP_MET: pv=g(r,f'{mm2} Resp')
    if pv is None: mv['First Response']+=1
    elif tier_rank(cur)>tier_rank(pv): mv['Improved']+=1
    elif tier_rank(cur)==tier_rank(pv): mv['Same']+=1
    else: mv['Declined']+=1
M['movement']=[[k,mv.get(k,0)] for k in ['First Response','Improved','Same','Declined']]

# ---- dot plot: transaction increase over ask (slide 14) ----
def first_offer_tier(r):
    for m in mailmonths:
        v=g(r,f'{m} Mail')
        if v: return v
    return None
incs=[]
for r in responders:
    # latest met-goal mailing that has a following month
    lm=None
    for m in mature:
        if g(r,f'{m} Resp') in RESP_MET: lm=m
    if not lm: continue
    offer=g(r,f'{lm} Mail')
    goal=OFFER_GOAL.get(offer, RESP_GOAL.get(g(r,f'{lm} Resp'),5))
    act=swipes(r,nextm[lm])
    incs.append(act-goal)
M['dot_n']=len(incs)
M['dot_mean']=round(statistics.mean(incs),1)
M['dot_std']=round(statistics.pstdev(incs),1)
M['dot_median']=round(statistics.median(incs),1)
hist=Counter()
for v in incs:
    b=int(v)
    if b<0: b=0
    if b>=40: b=40
    hist[b]+=1
M['dot_hist']=[[k,hist.get(k,0)] for k in range(0,41)]
M['dot_tail40']=hist.get(40,0)

# ---- sustained by mailing (slide 15) ----
def first_goal(r):
    t=first_offer_tier(r); return OFFER_GOAL.get(t,5)
sust=[]
for m in recent:  # recent 12 mailings
    rs=[r for r in elig if g(r,f'{m} Resp') in RESP_MET]
    if not rs: continue
    ok=sum(1 for r in rs if sw3(r)>=first_goal(r))
    sust.append([lbl(m),len(rs),round(100*ok/len(rs),1)])
M['sustained']=sust

# ---- before/after (slides 16/17) ----
def three_before(r,m):
    idx=smonths.index(m); pre=smonths[max(0,idx-3):idx]
    return pre
def all_after(r,m):
    idx=smonths.index(m); return smonths[idx+1:]
ba_mailings=[m for m in mature if smonths.index(m)>=3 and smonths.index(m)+1<len(smonths)]
ba=[]
for m in ba_mailings:
    rs=[r for r in elig if g(r,f'{m} Resp') in RESP_MET]
    if len(rs)<5: continue
    pre=smonths[max(0,smonths.index(m)-3):smonths.index(m)]
    post=smonths[smonths.index(m)+1:]
    sb=[statistics.mean([spend(r,x) for x in pre]) for r in rs]
    sa=[statistics.mean([spend(r,x) for x in post]) for r in rs]
    nb=[statistics.mean([nsf(r,x) for x in pre]) for r in rs]
    na=[statistics.mean([nsf(r,x) for x in post]) for r in rs]
    # winsorize spend at 3 SD
    def wins(vals):
        mu=statistics.mean(vals); sd=statistics.pstdev(vals); cap=mu+3*sd
        return [min(v,cap) for v in vals]
    sbw=wins(sb); saw=wins(sa)
    # overdraft participants for median NSF
    od=[i for i in range(len(rs)) if nb[i]>0 or na[i]>0]
    ba.append({'m':lbl(m),'n':len(rs),
       'sb_mean':round(statistics.mean(sbw)),'sa_mean':round(statistics.mean(saw)),
       'sb_sd':round(statistics.pstdev(sbw)),'sa_sd':round(statistics.pstdev(saw)),
       'nb_mean':round(statistics.mean(nb),2),'na_mean':round(statistics.mean(na),2),
       'nb_sd':round(statistics.pstdev(nb),2),'na_sd':round(statistics.pstdev(na),2),
       'sb_med':round(statistics.median(sb)),'sa_med':round(statistics.median(sa)),
       'nb_med':round(statistics.median([nb[i] for i in od]),2) if od else 0,
       'na_med':round(statistics.median([na[i] for i in od]),2) if od else 0})
M['before_after']=ba
# overall mean before/after (headline)
allsb=[];allsa=[];annb=[];anna=[]
for e in ba:
    allsb.append(e['sb_mean']);allsa.append(e['sa_mean'])
M['ba_spend_before']=round(statistics.mean(allsb)); M['ba_spend_after']=round(statistics.mean(allsa))
M['ba_spend_med_before']=round(statistics.mean([e['sb_med'] for e in ba]))
M['ba_spend_med_after']=round(statistics.mean([e['sa_med'] for e in ba]))

# ============ STAGE 2 ============
OPTIN='IN'; OPTOUT={'OUT'}; NOELECT={'NO'}
def regd(r):
    v=g(r,f'{LATEST} Reg E Desc'); low=v.lower()
    if not v or 'default' in low: return 'NO'
    if 'opt-in' in low or 'opt in' in low or 'optin' in low: return 'IN'
    if 'opt-out' in low or 'opt out' in low or 'optout' in low: return 'OUT'
    return 'NO'
# ---- Reg E all personal (slide 24): open personal debit-card holders ----
opdh=[r for r in data if personal(r) and isopen(r) and hascard(r)]
n_in=sum(1 for r in opdh if regd(r)==OPTIN)
n_out=sum(1 for r in opdh if regd(r) in OPTOUT)
n_no=sum(1 for r in opdh if regd(r) in NOELECT)
M['rege_pool']=len(opdh); M['rege_in']=n_in; M['rege_out']=n_out; M['rege_no']=n_no
M['rege_pct']=round(100*n_in/len(opdh),1)
# branch opt-in (branches with >=40 eligible open personal card holders)
brc=defaultdict(lambda:[0,0])
for r in opdh:
    b=g(r,'Branch'); brc[b][0]+=1; brc[b][1]+= (regd(r)==OPTIN)
brl=[(b,c[1],c[0],round(100*c[1]/c[0])) for b,c in brc.items() if c[0]>=40]
brl.sort(key=lambda x:-x[3])
M['rege_branch']=brl  # (branch, in, total, pct)
# ---- Reg E last 12 months (slide 25): personal card holders opened in the
# trailing 12 months of this extract and still open ----
def opened_in(r,a,b):
    d=parsed(r,'Date Opened'); return d is not None and a<=d<=b
J26=NOW; J25=mkey(smonths[-12]) if len(smonths)>=12 else mkey(smonths[0])
new_open=[r for r in data if personal(r) and hascard(r) and isopen(r) and opened_in(r,J25,J26)]
ni=sum(1 for r in new_open if regd(r)==OPTIN)
no_=sum(1 for r in new_open if regd(r) in OPTOUT)
nn=sum(1 for r in new_open if regd(r) in NOELECT)
M['rege_new_pool']=len(new_open); M['rege_new_in']=ni; M['rege_new_out']=no_; M['rege_new_no']=nn
M['rege_new_pct']=round(100*ni/len(new_open),1) if new_open else 0
nbrc=defaultdict(lambda:[0,0])
for r in new_open:
    b=g(r,'Branch'); nbrc[b][0]+=1; nbrc[b][1]+=(regd(r)==OPTIN)
nbrl=[(b,c[1],c[0],round(100*c[1]/c[0])) for b,c in nbrc.items() if c[0]>=15]
nbrl.sort(key=lambda x:-x[3])
M['rege_new_branch']=nbrl
# ---- Reg E by vintage (slide 26) ----
opdh_c=[r for r in data if personal(r) and isopen(r) and hascard(r)]
last12=smonths[-12:]
def part12(r): return sum(nsf(r,m) for m in last12)>0
def items12(r): return sum(nsf(r,m) for m in last12)
vint=defaultdict(lambda:[0,0,0,0.0,0])  # total, optin_all, participants, items, optin_participants
for r in opdh_c:
    d=parsed(r,'Date Opened')
    if not d: continue
    y=d.year
    key='Pre-2018' if y<2018 else str(y)
    v=vint[key]; v[0]+=1; v[1]+=(regd(r)==OPTIN)
    if part12(r):
        v[2]+=1; v[3]+=items12(r); v[4]+=(regd(r)==OPTIN)
years=['Pre-2018']+[str(y) for y in range(2018,2027)]
M['rege_vintage']=[[k,vint[k][0],round(100*vint[k][1]/vint[k][0]) if vint[k][0] else 0,
    round(vint[k][3]/vint[k][2]/12,2) if vint[k][2] else 0,
    round(100*vint[k][4]/vint[k][2]) if vint[k][2] else 0] for k in years if vint[k][0]>0]
M['rege_vintage_pool']=len(opdh_c)
# ---- Take rate personal (slide 19/20): NEW eligible personal accounts opened last 12 mo, by branch ----
new_elig=[r for r in elig if opened_in(r,J25,J26)]
if not new_elig:  # some clients' eligibility excludes recent openings -> fall back to all new personal
    new_elig=[r for r in data if personal(r) and opened_in(r,J25,J26)]
tb=defaultdict(lambda:[0,0])  # cards, total
for r in new_elig:
    b=g(r,'Branch'); tb[b][1]+=1; tb[b][0]+=hascard(r)
tbl=[(b,c[0],c[1],round(100*c[0]/c[1])) for b,c in tb.items() if c[1]>=15]
tbl.sort(key=lambda x:-x[2])
M['take_new_total']=len(new_elig); M['take_new_cards']=sum(1 for r in new_elig if hascard(r))
M['take_new_nocard']=M['take_new_total']-M['take_new_cards']
M['take_new_pct']=round(100*M['take_new_cards']/M['take_new_total'],1) if new_elig else 0
M['take_hist_pct']=M['overall_take']  # overall book take rate (card-holding / eligible)
M['take_branch']=tbl  # (branch, cards, elig, pct)
# monthly new-card counts by branch (Aug25-Jun26) for slide 20 table
tmonths=smonths[-11:]  # Aug25..Jun26
def opened_month(r,m):
    d=parsed(r,'Date Opened')
    if not d: return False
    return d.strftime('%b%y')==m
brmonthly=[]
for (b,cards,elign,pct) in tbl:
    row=[b]
    for m in tmonths:
        row.append(sum(1 for r in new_elig if g(r,'Branch')==b and opened_month(r,m) and hascard(r)))
    row+= [cards,elign,pct]
    brmonthly.append(row)
M['take_branch_monthly']=brmonthly; M['take_months']=[mkey(m).strftime('%b') for m in tmonths]
# full monthly column totals across ALL new eligible (for table reconciliation to 792)
M['take_col_totals']=[sum(1 for r in new_elig if opened_month(r,m) and hascard(r)) for m in tmonths]
# ---- NSF/OD over time (slide 22): monthly items + accounts w/ activity ----
nmonths=smonths[2:]  # Sep23..Jun26 (skip first 2 for parity w/ 1038 Sep start)
nsf_series=[]
for m in nmonths:
    items=sum(nsf(r,m) for r in data)
    accts=sum(1 for r in data if nsf(r,m)>0)
    nsf_series.append([mkey(m).strftime("%b %y"),round(items),accts])
M['nsf_series']=nsf_series
M['nsf_last_items']=nsf_series[-1][1]; M['nsf_last_accts']=nsf_series[-1][2]
# YoY
jun25=next((x for x in nsf_series if x[0]=='Jun 25'),None); jun26=nsf_series[-1]
M['nsf_yoy']=round(100*(jun26[1]-jun25[1])/jun25[1]) if jun25 else 0
# ---- Reach cumulative responders (slide 30) ----
reach=[]; seen=set();
for m in mailmonths:
    for i,r in enumerate(elig):
        if g(r,f'{m} Resp') in RESP_MET: seen.add(id(r))
    reach.append([lbl(m),len(seen)])
M['reach']=reach; M['reach_total']=len(responders)
M['reach_perml']=round(len(responders)/max(1,len([m for m in mailmonths if any(g(r,f'{m} Resp') in RESP_MET for r in elig)])))
# ---- Depth repeat responders (slide 31) ----
def nresp(r): return sum(1 for m in mailmonths if g(r,f'{m} Resp') in RESP_MET)
d1=sum(1 for r in responders if nresp(r)==1)
d2=sum(1 for r in responders if nresp(r)==2)
d3=sum(1 for r in responders if nresp(r)>=3)
M['depth']=[d1,d2,d3]; M['depth_repeat']=d2+d3
M['depth_repeat_pct']=round(100*(d2+d3)/len(responders),1)
# ---- Age profile (slide 32) ----
def age(r):
    d=parsed(r,'DOB')
    if not d: return None
    return int((NOW-d).days/365.25)
age_base=[r for r in elig if age(r) is not None]
M['age_base']=len(age_base)
bands=[('<25',0,24),('25-34',25,34),('35-44',35,44),('45-54',45,54),('55-64',55,64),('65+',65,200)]
agerows=[]
for nm,lo,hi in bands:
    eb=[r for r in age_base if lo<=age(r)<=hi]
    rb=[r for r in eb if any(g(r,f'{m} Resp') in RESP_MET for m in mailmonths)]
    agerows.append([nm,len(eb),len(rb)])
M['age']=agerows
# response rate by youngest/oldest
u25=next(x for x in agerows if x[0]=='<25'); o65=next(x for x in agerows if x[0]=='65+')
M['age_u25_rate']=round(100*u25[2]/u25[1]) if u25[1] else 0
M['age_o65_rate']=round(100*o65[2]/o65[1]) if o65[1] else 0
# No DOB in the extract (whole column blank for some cores) -> flag it; do NOT emit 0%.
if age_base:
    M['age_55plus_pct']=round(100*sum(x[1] for x in agerows if x[0] in('55-64','65+'))/len(age_base))
    M['age_missing']=False
else:
    M['age_55plus_pct']=None; M['age_missing']=True
    sys.stderr.write('WARNING: DOB column is empty for this client — age profile has no source. '
                     'Flag to Aaron (re-pull ODD with DOB, or source age from core/VIP).\n')
# ---- Balance profile (slide 33): responders vs non, recent-12-mailing scored base ----
def scored12(r): return any(g(r,f'{m} Mail') for m in mailmonths[-12:])
bbands=[('$0-500',0,500),('$500-2K',500,2000),('$2K-3K',2000,3000),('$3K-15K',3000,15000),('$15K+',15000,1e12)]
def curbal(r):
    ab=fnum(r,'Avg Bal'); return ab if ab!=0 else fnum(r,'Curr Bal')
resp_set=set(map(id,responders))
scored=[r for r in elig if scored12(r)]
balrows=[]
for nm,lo,hi in bbands:
    rr=[r for r in scored if id(r) in resp_set and lo<=curbal(r)<hi]
    nn=[r for r in scored if id(r) not in resp_set and lo<=curbal(r)<hi]
    balrows.append([nm,len(rr),len(nn)])
M['balance']=balrows
M['bal_resp_med']=round(statistics.median([curbal(r) for r in scored if id(r) in resp_set]))
M['bal_non_med']=round(statistics.median([curbal(r) for r in scored if id(r) not in resp_set]))
# ============ STAGE 3: NEW ACCOUNTS / RETENTION / BAYES ============
def ischecking(r): return 'checking' in g(r,'Prod Desc').lower()
newp=[r for r in data if personal(r) and opened_in(r,J25,J26)]
M['new_total']=len(newp)
M['new_stillopen_pct']=round(100*sum(1 for r in newp if isopen(r))/len(newp))
prodc=Counter(g(r,'Prod Desc') for r in newp)
M['new_products']=prodc.most_common(12)
M['new_checking_pct']=round(100*sum(1 for r in newp if ischecking(r))/len(newp))
chk=[p for p in prodc if 'Checking' in p]
topchk=max(chk,key=lambda p:prodc[p]) if chk else ''
M['new_topcheck']=topchk; M['new_topcheck_pct']=round(100*prodc.get(topchk,0)/len(newp))
# new checking balances (slide 36)
new_chk=[r for r in newp if ischecking(r)]
open_chk=[r for r in data if personal(r) and ischecking(r) and isopen(r)]
def bal(r):
    ab=fnum(r,'Avg Bal'); return ab if ab!=0 else fnum(r,'Curr Bal')
M['new_chk_avgbal']=round(statistics.mean([bal(r) for r in new_chk]))
M['open_chk_avgbal']=round(statistics.mean([bal(r) for r in open_chk]))
M['new_chk_funded_pct']=round(100*sum(1 for r in new_chk if bal(r)>0)/len(new_chk))
# debit penetration (slide 37)
M['new_chk_debit_pct']=round(100*sum(1 for r in new_chk if hascard(r))/len(new_chk),1)
M['open_chk_debit_pct']=round(100*sum(1 for r in open_chk if hascard(r))/len(open_chk),1)
M['debit_pen_gap']=round(M['new_chk_debit_pct']-M['open_chk_debit_pct'],1)
# debit usage new vs book (slide 38) — per active card in the latest month
def active_jun(r): return swipes(r,LATEST)>=1
new_card=[r for r in newp if hascard(r)]
open_pers_card=[r for r in data if personal(r) and isopen(r) and hascard(r)]
def act_rate(pool): return round(100*sum(1 for r in pool if active_jun(r))/len(pool),1)
M['new_active_pct']=act_rate(new_card); M['book_active_pct']=act_rate(open_pers_card)
new_act=[r for r in new_card if active_jun(r)]; book_act=[r for r in open_pers_card if active_jun(r)]
M['new_spend_active']=round(statistics.mean([spend(r,LATEST) for r in new_act]))
M['book_spend_active']=round(statistics.mean([spend(r,LATEST) for r in book_act]))
def ever_swiped(r): return any(swipes(r,m)>0 for m in smonths)
M['new_ever_swiped_pct']=round(100*sum(1 for r in new_card if ever_swiped(r))/len(new_card))
# new-account swipe segmentation (slide 39), latest month
def tier_jun(r):
    s=swipes(r,LATEST)
    if s<1: return 'Non-User'
    for lo,hi,nm in [(1,5,'1-5'),(6,10,'6-10'),(11,25,'11-25'),(26,1e9,'26+')]:
        if lo<=s<=hi: return nm
    return '26+'
M['new_card_n']=len(new_card)
segc=Counter(tier_jun(r) for r in new_card)
segorder=['Non-User','1-5','6-10','11-25','26+']
M['new_swipe_seg']=[[t,segc.get(t,0),round(100*segc.get(t,0)/len(new_card),1)] for t in segorder]
M['new_swipe_monthly_pct']=round(100*sum(1 for r in new_card if active_jun(r))/len(new_card),1)
M['new_swipe_heavy_pct']=round(100*segc.get('26+',0)/len(new_card),1)
# openings vs closures (slide 41) trailing 24 months
def _months_back(n):
    """First day of the month n months before the snapshot month."""
    y,m=_lm.year,_lm.month-n
    while m<=0: m+=12; y-=1
    return datetime.datetime(y,m,1)
J24=_months_back(23)   # 24-month window inclusive of the snapshot month
opens=defaultdict(int); closes=defaultdict(int)
for r in data:
    if not personal(r): continue
    do=parsed(r,'Date Opened'); dc=parsed(r,'Date Closed')
    if do and do>=J24 and do<=NOW: opens[do.strftime('%b %y')]+=1
    if dc and dc>=J24 and dc<=NOW: closes[dc.strftime('%b %y')]+=1
oc=[]; cum=0
mo=J24
while mo<=NOW:
    k=mo.strftime('%b %y'); o=opens[k]; c=closes[k]; cum+=o-c
    oc.append([k,o,c,cum])
    mo=datetime.datetime(mo.year+(mo.month//12), (mo.month%12)+1,1)
M['openings']=oc
M['open_24']=sum(x[1] for x in oc); M['close_24']=sum(x[2] for x in oc); M['net_24']=oc[-1][3]
# retention survival (slide 42) — Kaplan-Meier on well-observed cohort (opened >= Jul 2021,
# the window over which account closings are reliably captured in the extract).
allp=[r for r in data if personal(r)]
KMCUT=datetime.datetime(2021,7,1)
recs=[]
for r in allp:
    do=parsed(r,'Date Opened')
    if not do or do<KMCUT or do>NOW: continue
    if isopen(r): t=(NOW-do).days/30.44; ev=0
    else:
        dc=parsed(r,'Date Closed')
        if not dc: t=(NOW-do).days/30.44; ev=0
        else: t=(dc-do).days/30.44; ev=1
    if t>=0: recs.append((t,ev))
evtimes=sorted(set(t for t,e in recs if e==1))
Scur=1.0; surv_steps=[]
for et in evtimes:
    n=sum(1 for tt,_ in recs if tt>=et-1e-9)
    d=sum(1 for tt,e in recs if e==1 and abs(tt-et)<1e-9)
    if n>0: Scur*=(1-d/n)
    surv_steps.append((et,Scur))
def Sat(m):
    s=1.0
    for et,sv in surv_steps:
        if et<=m: s=sv
        else: break
    return s
def natrisk(m): return sum(1 for tt,_ in recs if tt>=m-1e-9)
miles=[('6mo',6),('1yr',12),('2yr',24),('3yr',36)]
surv=[['Open',100.0]]+[[nm,round(100*Sat(mm),1)] for nm,mm in miles]
M['survival']=surv
M['km_n']=len(recs); M['km_events']=sum(e for _,e in recs)
M['ret_1yr']=round(100*Sat(12),1); M['ret_3yr']=round(100*Sat(36),1)
# KM median survival (months where S crosses 0.5), else report last observable
medm=next((et for et,sv in surv_steps if sv<=0.5),None)
M['km_median_yr']=round(medm/12,1) if medm else None
closed_life=[ (parsed(r,'Date Closed')-parsed(r,'Date Opened')).days/365.25
              for r in allp if not isopen(r) and parsed(r,'Date Opened') and parsed(r,'Date Closed') ]
M['median_closed_life']=round(statistics.median(closed_life),1) if closed_life else 0
# Bayesian first-year closure by early debit use (slide 43)
# cohort opened 36 to 12 months before the snapshot, so every account has had a
# full first year of observation (was hardcoded Jul23-Jun25 against a Jun26 pull)
J23=_months_back(35); J25b=_months_back(11)-datetime.timedelta(days=1)
cohort=[r for r in data if personal(r) and opened_in(r,J23,J25b)]
def used_early(r):
    do=parsed(r,'Date Opened')
    if not do: return False
    # first 3 monthly tokens on/after open
    cnt=0
    for m in smonths:
        if mkey(m)>=datetime.datetime(do.year,do.month,1):
            if swipes(r,m)>0: return True
            cnt+=1
            if cnt>=3: break
    return False
def closed_yr1(r):
    do=parsed(r,'Date Opened'); dc=parsed(r,'Date Closed')
    if isopen(r) or not dc or not do: return False
    return (dc-do).days<=366
cn=len(cohort)
closed=[r for r in cohort if closed_yr1(r)]
surv_c=[r for r in cohort if not closed_yr1(r)]
prior=len(closed)/cn
p_used_close=sum(1 for r in closed if used_early(r))/len(closed) if closed else 0
p_used_surv=sum(1 for r in surv_c if used_early(r))/len(surv_c) if surv_c else 0
# posterior via Bayes over used / not used
p_used=sum(1 for r in cohort if used_early(r))/cn
post_close_used=(p_used_close*prior)/p_used if p_used else 0
post_close_notused=((1-p_used_close)*prior)/(1-p_used) if p_used<1 else 0
M['bayes_n']=cn
M['bayes_prior']=round(100*prior,1)
M['bayes_p_used']=round(100*p_used)
M['bayes_p_used_close']=round(100*p_used_close)
M['bayes_p_used_surv']=round(100*p_used_surv)
M['bayes_close_used']=round(100*post_close_used,1)
M['bayes_close_notused']=round(100*post_close_notused,1)
M['bayes_rr']=round(post_close_notused/post_close_used,1) if post_close_used else 0
json.dump(M,open(sys.argv[2],'w'),indent=1,default=str)
print('\nsustained bars:',[(s[0],s[2]) for s in M['sustained']])
print('ranking last 3:',M['ranking'][-3:])
print('ba spend before/after mean:',M['ba_spend_before'],M['ba_spend_after'],'median:',M['ba_spend_med_before'],M['ba_spend_med_after'])
print('ba n mailings:',len(ba))
