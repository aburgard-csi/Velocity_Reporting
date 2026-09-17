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
    _STATIC={f'{_LATEST} Elig','Debit?','Stat Desc','Stat Code','Business?',
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
# The ODD row vocabulary is defined once in odd_rows and bound here. It used to
# be re-declared in every script, and personal() had drifted between them.
from odd_rows import accessors as _accessors, OPEN_STATUSES as OPEN, CLOSED_STATUSES as CLOSED
_odd=_accessors(H)
g=_odd.g; fnum=_odd.fnum
_MKEY={}
def mkey(t):
    # 185,000 calls for about three dozen distinct tokens ('Jul26'), and
    # strptime is not cheap: it was 2.1s of a 25s run (2026-09-11).
    d=_MKEY.get(t)
    if d is None:
        d=_MKEY[t]=datetime.datetime.strptime(t,'%b%y')
    return d
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
swipes=_odd.swipes; spend=_odd.spend; nsf=_odd.nsf
hascard=_odd.hascard; isopen=_odd.isopen; personal=_odd.personal
# strptime dominated this script: 3.8M calls, ~24s of a 100s run, almost all of it
# re-parsing the same handful of date strings. Cache on the STRING (not on the row) — a
# few thousand distinct dates, and no dependence on row object identity.
_DATE_CACHE={}
_UNSET=object()        # None is a real cached result (unparseable date), so it cannot be the miss marker
def parsed(r,f):
    v=g(r,f)
    d=_DATE_CACHE.get(v,_UNSET)
    if d is not _UNSET:
        return d
    out_=None
    for fmt in ('%m/%d/%Y','%Y-%m-%d %H:%M:%S','%Y-%m-%d','%m/%d/%y'):
        try:
            out_=datetime.datetime.strptime(v,fmt); break
        except Exception:
            pass
    _DATE_CACHE[v]=out_
    return out_
_lm=mkey(LATEST)
NOW=(_lm.replace(day=28)+datetime.timedelta(days=4)).replace(day=1)-datetime.timedelta(days=1)
M=out={}
def _data_issue(what, detail=""):
    """Stop with a named data problem instead of a ZeroDivisionError or an empty mean().

    A slide cannot be built on a base of nothing, and a traceback says nothing about
    why the base is empty. The cause is in the extract, so the message says what is
    missing and what the extract carries instead (2026-09-14: 1226 Ellafi writes its
    status only to Stat Code; 1121 Timberland writes numbers into Prod Desc).
    """
    raise SystemExit("POSSIBLE DATA ISSUE: %s %s.%s Nothing was computed from it. Check the "
                     "extract with the data team, then rebuild."
                     % (_os.path.basename(F), what, (" " + detail) if detail else ""))
# cohorts
elig=[r for r in data if personal(r) and g(r,f'{LATEST} Elig')=='Yes']
# HISTORICAL response cohort — every personal account, NOT filtered by current
# eligibility. Counting a past mailing's responders through the `{LATEST} Elig`
# snapshot is a survivorship filter: it silently drops anyone who responded and has
# since closed or gone ineligible, and the same mailing then reports a different
# responder count on different slides. Wellworth 1549 Jun 2026 read 1,077 on the
# mailing slides (personal + mailed) but 1,026 on Program Reach, Depth of
# Engagement, Ranking and Sustained — 51 responders short (Aaron, 2026-08-28).
# Slides 18/19 already used this cohort for exactly this reason; the rest now match.
resp_pop=[r for r in data if personal(r)]
def responded(r): return any(g(r,f'{m} Resp') in RESP_MET for m in mailmonths)
responders=[r for r in resp_pop if responded(r)]
nonresp=[r for r in elig if not responded(r)]
M['n_eligible']=len(elig); M['n_responders']=len(responders); M['n_nonresp']=len(nonresp)
M['overall_take']=round(100*sum(1 for r in elig if hascard(r))/len(elig),1)

# ---- swipe tier (slide 8) ----
w3=smonths[-3:]   # trailing 3 months of THIS extract
# Label for the slides that quote this window. It was hardcoded in the template as
# "(Apr–Jun 2026)" and never swapped, so every client shipped the reference client's window.
M['w3_label']=f"{mkey(w3[0]).strftime('%b')}\u2013{mkey(w3[-1]).strftime('%b %Y')}" 
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
    c=Counter(g(r,f'{m} Resp') for r in resp_pop if g(r,f'{m} Resp') in RESP_MET)
    rank.append([lbl(m)]+[c.get(t,0) for t in TIER_ORDER])
M['ranking']=rank  # newest last

# ---- mailing response summary (slide 12), computed from the ODD ----
# Was read out of the workbook as percentages only, which disagreed with the latest-mailer
# slide: the workbook's denominator is not the mailed population, so 1549 read 16.3% on
# slide 12 and 10.7% on slide 14 for the same Jun 2026 drop (Aaron, 2026-08-20). Both now
# use the same definition — offers sent = personal accounts carrying a `<mon> Mail` value,
# responders = those whose `<mon> Resp` reached a goal tier. Newest mailing first.
# Each rate uses ITS OWN offer group as the denominator (Aaron, 2026-08-27):
#   NU 5+ rate     = NU respondents / NU recipients
#   Threshold rate = TH respondents / TH recipients
# Both used to divide by the whole mailed population, which mixes the two offers into one
# denominator and understates both — Austin Feb 2026 read NU 2.5% where the NU offer
# actually drew 337 of 4,420 (7.6%). The offer a recipient was sent is the '<mon> Mail'
# value ('NU' or 'TH-10'..'TH-25'); '<mon> Resp' carries what they achieved ('NU 5+' or
# 'TH-nn' when met, 'NU 1-4' when not). Only the overall Response % spans both groups.
msum=[]; _nu_s=_nu_r=_th_s=_th_r=0; _unknown_offers=Counter()
for m in reversed(recent):
    sent=[r for r in data if personal(r) and g(r,f'{m} Mail')]
    if not sent: continue
    rs=[r for r in sent if g(r,f'{m} Resp') in RESP_MET]
    nu_sent=[r for r in sent if g(r,f'{m} Mail')=='NU']
    th_sent=[r for r in sent if g(r,f'{m} Mail').startswith('TH')]
    for r in sent:
        _o=g(r,f'{m} Mail')
        if _o!='NU' and not _o.startswith('TH'): _unknown_offers[_o]+=1
    nu_r=sum(1 for r in nu_sent if g(r,f'{m} Resp') in RESP_MET)
    th_r=sum(1 for r in th_sent if g(r,f'{m} Resp') in RESP_MET)
    _nu_s+=len(nu_sent); _nu_r+=nu_r; _th_s+=len(th_sent); _th_r+=th_r
    msum.append([lbl(m), len(sent), len(rs),
                 round(100*nu_r/len(nu_sent),1) if nu_sent else 0.0,
                 round(100*th_r/len(th_sent),1) if th_sent else 0.0,
                 round(100*len(rs)/len(sent),1)])
if _unknown_offers:
    print(f"WARNING mail_summary: offer codes that are neither NU nor TH-* were excluded "
          f"from both rate denominators: {dict(_unknown_offers.most_common(8))}", file=sys.stderr)
M['mail_summary']=msum
_tot_sent=sum(x[1] for x in msum); _tot_rs=sum(x[2] for x in msum)
# Trailing total pools each group's own recipients and respondents. It is NOT a mean of the
# per-mailing rates: that would let a small drop swing the program figure as hard as a large
# one, and with per-group denominators the pooled ratio is the only correct roll-up.
M['mail_summary_total']=[_tot_sent, _tot_rs,
                         round(100*_nu_r/_nu_s,1) if _nu_s else 0.0,
                         round(100*_th_r/_th_s,1) if _th_s else 0.0,
                         round(100*_tot_rs/_tot_sent,1) if _tot_sent else 0.0]

# ---- mailings in progress (slide 12) ----
# A mailing in the extract's own last month has offers but no measured response: its
# '<mon> Resp' is filled only once the following month's activity lands. `mature` drops
# it, which is right for every rate on the deck, but it also left the drop off the
# Mailing Response Summary entirely — 1549 Wellworth's Aug 2026 mailing was on 9,643
# accounts and appeared nowhere (Aaron, 2026-09-14: "if the client has a mailing in
# process but incomplete, list it here"). Offers are counted exactly as the completed
# rows count them — personal accounts carrying a value. No response figure is produced,
# because none exists yet, and these never enter mail_summary_total.
M['mail_in_progress']=[[lbl(m), sum(1 for r in data if personal(r) and g(r,f'{m} Mail'))]
                       for m in reversed([x for x in mailmonths if x not in nextm])]
M['mail_in_progress']=[x for x in M['mail_in_progress'] if x[1]]

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
# Sustained = average monthly swipes over the CURRENT 3-month window at or above the ask
# this respondent answered (Aaron, 2026-08-27). sw3() is already the 3-month mean, so the
# comparison is like-for-like against a monthly ask.
#
# The ask is the one attached to THIS mailing — the offer they were sent ('<mon> Mail'),
# falling back to the goal implied by what they achieved ('<mon> Resp') when the offer cell
# is blank. It used to be first_offer_tier(): the first offer ever SENT to the account,
# whether or not they responded to it. For a repeat responder whose ask moved between
# mailings that benchmarks the cohort against the wrong number.
def _ask(r, m):
    o = g(r,f'{m} Mail')
    if o in OFFER_GOAL: return OFFER_GOAL[o]
    return RESP_GOAL.get(g(r,f'{m} Resp'), 5)
# Sustained is measured on the months AFTER the mailing, not on a fixed current
# window. sw3() is the trailing 3 months of the EXTRACT, so for a recent mailing it
# averaged in months from BEFORE the customer ever responded and reported attrition
# that had not happened yet. A responder met the ask in their response month by
# definition, so that month is 100% and attrition can only appear afterwards
# (Aaron, 2026-08-28). Each row carries its own post-window length so the caption
# can state what was actually measured rather than claiming a 3-month window.
sust=[]
for m in recent:  # recent 12 mailings
    rs=[r for r in resp_pop if g(r,f'{m} Resp') in RESP_MET]
    if not rs: continue
    # A response is measured in the month AFTER the offer — the same convention the
    # dot plot uses ("swipes in the month after the latest met-goal offer"). Wellworth
    # confirms it: 44% of the Jun 2026 responders cleared their ask in June, 100% in
    # July. So the RESPONSE month is mailing+1 and attrition can only show from
    # mailing+2 onward (Aaron, 2026-08-28).
    post = smonths[smonths.index(m)+2:] if m in smonths else []
    if not post:
        # the response month itself: every responder met the ask there by definition,
        # so this reads 100% and no attrition window exists yet
        sust.append([lbl(m), len(rs), 100.0, 0])
        continue
    ok=sum(1 for r in rs
           if sum(swipes(r,x) for x in post)/len(post) >= _ask(r,m))
    sust.append([lbl(m),len(rs),round(100*ok/len(rs),1),len(post)])
M['sustained']=sust
# widest post-window any bar uses, for the slide caption
M['sustained_window']=max((x[3] for x in sust), default=0)

# ---- before/after (slides 18/19) ----
# The measure itself lives in before_after.py, imported by BOTH this module and
# responder_activity.py (the Summit one-pager), because the two used to compute it
# four different ways and a Summit attendee could be shown a number their own
# monthly deck contradicted (Aaron, 2026-09-08). Cohort, window, winsorizing and
# pooling are all defined there, with the evidence for each choice.
import before_after as _BA
_ba_out = _BA.compute(data, _odd, smonths, mature,
                      on_warning=lambda msg: print("WARNING " + msg, file=sys.stderr))
M.update(_ba_out)

# ============ STAGE 2 ============
OPTIN='IN'; OPTOUT={'OUT'}; NOELECT={'NO'}
# Reg E wording is read by odd_rows.rege_label, the same rule oddd_optimize uses. This
# function had its own copy that knew only "opt in", and "Opted In" / "Opted Out"
# extracts shipped Reg E at 0.0% (2026-09-16). Wording no rule covers stops the build.
from odd_rows import rege_label as _rege_label, REGE_IN as _RG_IN, REGE_OUT as _RG_OUT
from collections import Counter as _Counter
_rege_unmapped = _Counter()
def regd(r):
    v=g(r,f'{LATEST} Reg E Desc'); lab=_rege_label(v)
    if lab is None:
        _rege_unmapped[v] += 1
        return 'NO'
    return 'IN' if lab == _RG_IN else 'OUT' if lab == _RG_OUT else 'NO'
# ---- Reg E all personal (slide 24): open personal debit-card holders ----
opdh=[r for r in data if personal(r) and isopen(r) and hascard(r)]
if not opdh:
    _pers=[r for r in data if personal(r)]
    _data_issue("has no open personal debit-card holders, so there is no Reg E base",
                "Of %s personal accounts, %s read as open from Stat Desc, or Stat Code where the description is blank (%s have a blank Stat Desc) "
                "and %s carry a debit card." % (f"{len(_pers):,}", f"{sum(1 for r in _pers if isopen(r)):,}",
                f"{sum(1 for r in _pers if not g(r,'Stat Desc')):,}", f"{sum(1 for r in _pers if hascard(r)):,}"))
n_in=sum(1 for r in opdh if regd(r)==OPTIN)
if _rege_unmapped:
    _data_issue("carries Reg E wording no mapping covers",
                "%s Reg E Desc values: %s. Ask how to map them (odd_rows.rege_label)." % (
                    LATEST, ", ".join("'%s' (%s)" % (k, f"{n:,}") for k, n in _rege_unmapped.most_common(8))))
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
# Full per-branch election breakdown for the Reg E by Branch TABLE (Aaron, 2026-08-28).
# Built on new_open — accounts opened in the trailing 12 months — not the whole book
# (Aaron, 2026-08-28): the all-vintages view is dominated by decades of legacy
# elections and says nothing about how branches are asking TODAY. Same cohort and same
# >=15 threshold as the new-account chart beside it, so the two agree.
# Kept as its OWN key: rege_branch is a fixed 4-tuple the chart and the takeaways slide
# both unpack positionally.
brc3=defaultdict(lambda:[0,0,0,0])   # total, in, out, no-election
for r in new_open:
    b=g(r,'Branch'); e=regd(r)
    brc3[b][0]+=1
    if e==OPTIN: brc3[b][1]+=1
    elif e in OPTOUT: brc3[b][2]+=1
    elif e in NOELECT: brc3[b][3]+=1
_bt=[[b,c[1],c[2],c[3],c[0],round(100*c[1]/c[0])] for b,c in brc3.items() if c[0]>=15]
_bt.sort(key=lambda x:-x[5])
M['rege_branch_table']=_bt   # (branch, in, out, no_election, total, pct)
M['rege_branch_table_total']=[sum(x[1] for x in _bt), sum(x[2] for x in _bt),
                              sum(x[3] for x in _bt), sum(x[4] for x in _bt)]
# The window ACTUALLY used. J25 falls back to the first activity month when the extract
# carries fewer than 12, so a short extract's cohort is NOT a full year — Wellworth's is
# Mar-Jul 2026. The heading states this rather than claiming twelve months.
M['rege_new_window']=[J25.strftime('%b %Y'), J26.strftime('%b %Y'), len(smonths[-12:])]
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
# The vintage axis is derived from the data. It used to be a typed
# range(2018,2027): an account opened in 2027 landed under key '2027', which
# was not in the list, so it counted toward the pool and then vanished from
# the chart. Keys are 4-digit years, so a plain sort orders them.
years=(['Pre-2018'] if 'Pre-2018' in vint else [])+sorted(k for k in vint if k!='Pre-2018')
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
# One pass over the rows accumulating every month, instead of two full scans per month
# (34 months x 273k rows x 2 = ~18M nsf() calls, each of which is two field reads).
_items={m:0.0 for m in nmonths}; _accts={m:0 for m in nmonths}
for r in data:
    for m in nmonths:
        v=nsf(r,m)
        if v:
            _items[m]+=v
            if v>0: _accts[m]+=1
nsf_series=[[mkey(m).strftime("%b %y"),round(_items[m]),_accts[m]] for m in nmonths]
M['nsf_series']=nsf_series
M['nsf_last_items']=nsf_series[-1][1]; M['nsf_last_accts']=nsf_series[-1][2]
# YoY = this month against the SAME month a year earlier, found by month arithmetic.
# It used to search for the literal 'Jun 25' row and compare it to the LAST row, so
# the figure was year-over-year only for a June deck — a Jul-2026 deck compared
# Jun 25 to Jul 26 and still called it YoY — and any client whose series starts
# after Jun 2025 fell to the `else 0` branch and shipped a phantom 0%. Absent prior
# month -> None, which the builder states on the tile; it is never zeroed.
_nsf_by_tok=dict(zip(nmonths,nsf_series))
_nsf_cur=nsf_series[-1]; _nsf_end=mkey(nmonths[-1])
_nsf_prior=_nsf_by_tok.get(_nsf_end.replace(year=_nsf_end.year-1).strftime('%b%y'))
M['nsf_yoy']=round(100*(_nsf_cur[1]-_nsf_prior[1])/_nsf_prior[1]) if (_nsf_prior and _nsf_prior[1]) else None
# The two months actually compared, so the tile's own caption names them instead
# of carrying the template's literal '(Jun 25 - Jun 26)'.
M['nsf_yoy_window']=[_nsf_prior[0],_nsf_cur[0]] if _nsf_prior else None
# ---- Reach cumulative responders (slide 30) ----
reach=[]; seen=set();
for m in mailmonths:
    for i,r in enumerate(resp_pop):
        if g(r,f'{m} Resp') in RESP_MET: seen.add(id(r))
    reach.append([lbl(m),len(seen)])
M['reach']=reach; M['reach_total']=len(responders)
M['reach_perml']=round(len(responders)/max(1,len([m for m in mailmonths if any(g(r,f'{m} Resp') in RESP_MET for r in resp_pop)])))
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
# A credit union's checking account is a SHARE DRAFT (1200 Guardians: 'Share Draft',
# 'Share Draft Aspire'). Matching 'checking' alone found no new checking accounts
# there and mean() of nothing crashed the build (2026-09-14).
CHECKING_WORDS = ('checking', 'share draft')
def is_checking_name(p): return any(w in (p or '').lower() for w in CHECKING_WORDS)
def ischecking(r): return is_checking_name(g(r,'Prod Desc'))
newp=[r for r in data if personal(r) and opened_in(r,J25,J26)]
if not newp:
    _data_issue("has no personal accounts opened in its last 12 months (%s to %s)" % (J25.strftime('%b %Y'), J26.strftime('%b %Y')),
                "Check Date Opened.")
M['new_total']=len(newp)
M['new_stillopen_pct']=round(100*sum(1 for r in newp if isopen(r))/len(newp))
prodc=Counter(g(r,'Prod Desc') for r in newp)
M['new_products']=prodc.most_common(12)
M['new_checking_pct']=round(100*sum(1 for r in newp if ischecking(r))/len(newp))
chk=[p for p in prodc if is_checking_name(p)]
topchk=max(chk,key=lambda p:prodc[p]) if chk else ''
M['new_topcheck']=topchk; M['new_topcheck_pct']=round(100*prodc.get(topchk,0)/len(newp))
# new checking balances (slide 36)
new_chk=[r for r in newp if ischecking(r)]
open_chk=[r for r in data if personal(r) and ischecking(r) and isopen(r)]
if not new_chk or not open_chk:
    _noname=Counter(g(r,'Prod Desc') or '(blank)' for r in newp if not re.search('[A-Za-z]', g(r,'Prod Desc')))
    _data_issue("has no %s checking accounts to compare" % ("new" if not new_chk else "open"),
                "Checking means 'checking' or 'share draft' in Prod Desc. %s personal accounts opened since %s "
                "include %s such accounts; %s of them carry a Prod Desc with no product name in it (most common: %s)."
                % (f"{len(newp):,}", J25.strftime('%b %Y'), f"{len(new_chk):,}", f"{sum(_noname.values()):,}",
                   ", ".join(repr(k) for k, _ in _noname.most_common(4)) or "none"))
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
new_act=[r for r in new_card if active_jun(r)]; book_act=[r for r in open_pers_card if active_jun(r)]
if not new_act or not book_act:
    # 1615 Cape & Coast (2026-09-15): 18,912 personal accounts carry Stat Code '0' and a blank
    # Stat Desc, so only 720 read as open, and none of their 287 card holders swiped in Aug26.
    # mean() of nothing crashed the build with a StatisticsError that named no cause.
    _notopen=Counter(g(r,'Stat Desc') or "blank description, Stat Code %r" % g(r,'Stat Code')
                     for r in data if personal(r) and not isopen(r))
    _data_issue("has no %s debit-card holders who used the card in %s" % ("new" if not new_act else "open", lbl(LATEST)),
                "%s new and %s open personal accounts carry a card. Personal accounts that do not read as open "
                "most often show: %s."
                % (f"{len(new_card):,}", f"{len(open_pers_card):,}",
                   "; ".join(f"{k} ({v:,})" for k, v in _notopen.most_common(3)) or "none"))
M['new_active_pct']=act_rate(new_card); M['book_active_pct']=act_rate(open_pers_card)
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
M['km_cut']=KMCUT.strftime('%b %Y')   # the caption states this window; derive, never retype
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
# Kaplan-Meier. Was O(event times x records) — two full scans of `recs` per event time,
# 38.7M generator steps and ~11s on Austin 1075. The at-risk count is just "how many
# records have tt >= et", which one sort plus a binary search answers, and the deaths per
# time are one Counter. Same numbers, same order.
import bisect as _bisect
_times=sorted(tt for tt,_ in recs)
_deaths=Counter(tt for tt,e in recs if e==1)
evtimes=sorted(_deaths)
Scur=1.0; surv_steps=[]
_N=len(_times)
for et in evtimes:
    n=_N-_bisect.bisect_left(_times, et-1e-9)
    d=_deaths[et]
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
closed_life=[]
for r in allp:                      # was parsing both dates twice per row in the filter
    if isopen(r): continue
    _o=parsed(r,'Date Opened'); _c=parsed(r,'Date Closed')
    if _o and _c: closed_life.append((_c-_o).days/365.25)
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
# ---- branch names (Aaron, 2026-08-27) ----------------------------------------------
# The ODD carries branch NUMBERS only. The client's "<Client> Charts 2026" workbook maps
# them to names on its Branch Results tab, so charts and tables can say "Lufkin" rather
# than "Branch 41". Point ARS_CHARTS_FILE at that workbook; without it the deck keeps the
# numbers, and an unmapped branch keeps its number too rather than going blank.
_charts=_os.environ.get('ARS_CHARTS_FILE','').strip()
if _charts:
    _bdir=_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), _os.pardir)
    if _bdir not in sys.path: sys.path.insert(0, _bdir)
    import branch_names as _bn
    _map=_bn.load_map(_charts)
    if not _map:
        print(f"WARNING branch names: no usable Branch Results tab in "
              f"{_os.path.basename(_charts)} — no branch reference slide will be built",
              file=sys.stderr)
    else:
        # Charts and tables keep the NUMBER: on an eight-bar take-rate chart the names
        # collide badly (Aaron, 2026-08-27). The mapping rides along as data instead, and
        # the builder turns it into one reference slide in the Appendix.
        _pairs=[]; _seen=set(); _unmapped=[]
        for _k in _bn.BRANCH_KEYS:
            for _row in (M.get(_k) or []):
                _lbl=str(_row[0])
                if _lbl in _seen: continue
                _seen.add(_lbl)
                _nm=_map.get(_lbl) or (_map.get(str(int(_lbl))) if _lbl.isdigit() else None)
                (_pairs.append([_lbl,_nm]) if _nm else _unmapped.append(_lbl))
        # Sorted the way a reader scans them, and keyed by the SAME label the charts print.
        _pairs.sort(key=lambda x: (0, int(x[0])) if x[0].isdigit() else (1, 0))
        _tot=len(_pairs)+len(_unmapped)
        _cov=(len(_pairs)/_tot) if _tot else 0
        # A low match rate means the two files are numbering different things, not that the
        # Charts file is missing rows. Texas Bay 1509's ODD branch column holds ids like
        # 114413 / 707221 while its Charts file lists 01-10: exactly 2 "matched", and both
        # were coincidences that would have put the wrong branch name against the wrong
        # number. Publish the mapping only when most of the deck's branches resolve.
        if _cov < 0.5:
            M['branch_names']=[]
            print(f"WARNING branch names: only {len(_pairs)} of {_tot} branch ids resolve "
                  f"({_cov:.0%}) — the ODD and the Charts file appear to number different "
                  f"things (ODD ids e.g. {sorted(_unmapped)[:4]}); no reference slide built",
                  file=sys.stderr)
        else:
            M['branch_names']=_pairs
            print(f"branch names: {len(_pairs)} of {_tot} branches named ({_cov:.0%})"
                  + (f"; no name in file for {sorted(_unmapped)[:8]}" if _unmapped else ""))

# ---- TEST BRANCH: branch names on the branch charts (Aaron, 2026-09-17) ------------------
# test/james-aaron-combined only, and only with RPE_JAMES_SLIDES=1: "use branch names on the
# other branch charts too" (names only; the Branch Scorecard keeps number + name). Names come
# from Inputs/Branch Names/branch_names.csv (branch_names.client_map), applied only when most
# of the deck's branch ids resolve, the same coverage rule as the Charts-file path above. An
# unnamed branch keeps its number. M['branch_name_of'] keeps number -> name so tables that
# order branches by number still can.
if _os.environ.get('RPE_JAMES_SLIDES')=='1':
    _bdir=_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), _os.pardir)
    if _bdir not in sys.path: sys.path.insert(0, _bdir)
    import branch_names as _bn2
    _cid=_os.environ.get('RPE_CLIENT_ID','').strip() or (re.match(r'(\d+)', _os.path.basename(F)) or [None, ''])[1]
    _nm=_bn2.client_map(_cid) if _cid else {}
    _ids=sorted({str(_r[0]) for _k in _bn2.BRANCH_KEYS for _r in (M.get(_k) or [])})
    _hit={_i:_nm[_i] for _i in _ids if _i in _nm}
    if _ids and len(_hit)/len(_ids)>=0.5:
        _bn2.apply_to_metrics(M, _hit)
        M['branch_name_of']=_hit
        M['branch_names']=[]      # the charts carry names now; no number lookup slide
        print(f"branch names on charts: {len(_hit)} of {len(_ids)} branch ids named from branch_names.csv")
    else:
        print(f"branch names on charts: only {len(_hit)} of {len(_ids)} branch ids named; charts keep numbers",
              file=sys.stderr)

json.dump(M,open(sys.argv[2],'w', encoding="utf-8"),indent=1,default=str)
print('\nsustained bars:',[(s[0],s[2]) for s in M['sustained']])
print('ranking last 3:',M['ranking'][-3:])
print('ba spend before/after mean:',M['ba_spend_before'],M['ba_spend_after'],'median:',M['ba_spend_med_before'],M['ba_spend_med_after'])
print('ba window: %d before / %d after | %d mailings'
      % (M['ba_before_months'],M['ba_after_months'],M['ba_n_mailings']))
print('ba nsf before/after:',M['ba_nsf_before'],M['ba_nsf_after'])
