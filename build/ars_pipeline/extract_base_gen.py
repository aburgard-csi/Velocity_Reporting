import openpyxl,datetime,json
import sys
wb=openpyxl.load_workbook(sys.argv[1],read_only=True,data_only=True)
def ml(v): return v.strftime('%b %Y') if isinstance(v,datetime.datetime) else v
def mt(v): return v.strftime('%b%y') if isinstance(v,datetime.datetime) else v
def rowvals(ws,r): return [ws.cell(r,c).value for c in range(1,ws.max_column+1)]
def find_row(ws,label,c=3,r1=1,r2=80):
    for r in range(r1,r2):
        v=ws.cell(r,c).value
        if isinstance(v,str) and v.strip()==label: return r
    return None
out={}
ef=wb['Executive Financials MM']
out['client']=ef.cell(4,2).value
out['data_label']=ef.cell(6,2).value
out['months']=ef.cell(7,4).value
out['mailings']=ef.cell(8,4).value
def efv(label,col):
    for r in range(14,30):
        if isinstance(ef.cell(r,3).value,str) and ef.cell(r,3).value.strip()==label:
            return ef.cell(r,col).value
    return None
out['cur_revenue']=efv('Total Incremental Revenue',4)
out['ltd_revenue']=efv('Total Incremental Revenue',6)
out['cur_profit']=efv('Incremental Profit',4)
out['ltd_profit']=efv('Incremental Profit',6)
out['ltd_costs']=efv('Total Costs',6)
out['ltd_plan_profit']=efv('Incremental Profit',7)
# Always emit profitability; guard only the DENOMINATOR. Gating on revenue too
# omitted the key for a young program with no revenue booked yet (1549 Wellworth),
# and build_ars_gen then died with KeyError: 'profitability'. Zero revenue against
# real costs is a true 0.00 : 1, not missing data.
out['profitability']=round(out['ltd_revenue']/abs(out['ltd_costs']),2) if out['ltd_costs'] else 0.0
# monthly incremental revenue = Total Incremental Income (Summary block, row 9)
amr=wb['All Months Rollup MM']; hdr=rowvals(amr,8)
r9=rowvals(amr,find_row(amr,'Total Incremental Income',c=3,r1=8,r2=12))
months=[(ml(hdr[i]),(r9[i] or 0)) for i in range(len(hdr)) if isinstance(hdr[i],datetime.datetime)]
month_toks=[mt(h) for h in hdr if isinstance(h,datetime.datetime)]
out['monthly_rev_last12']=months[-12:]
out['monthly_rev_sum12']=round(sum(v for _,v in months[-12:]))
out['monthly_rev_avg12']=round(out['monthly_rev_sum12']/12)
# Key Trends MM
kt=wb['Key Trends MM']; khdr=rowvals(kt,8)
def kseries(label):
    r=find_row(kt,label,c=3,r1=8,r2=48)
    if not r: return {}
    vals=rowvals(kt,r); return {ml(khdr[i]):vals[i] for i in range(len(khdr)) if isinstance(khdr[i],datetime.datetime)}
spend=kseries('Total Spend (millions)'); tot=kseries('Total Accounts (000)'); non=kseries('Non Card Holding Accounts (000)')
mos=[ml(v) for v in khdr if isinstance(v,datetime.datetime)]
card={m:round(((tot.get(m) or 0)-(non.get(m) or 0))*1000) for m in mos}
tail=mos[-36:]
tail_toks=[mt(v) for v in khdr if isinstance(v,datetime.datetime)][-36:]
out['swipespend_36']=[(m,round(spend.get(m,0) or 0,2),card.get(m,0)) for m in tail]
# Mail Response Summary MM: col2 month, col3 NU5+, col4 threshold
mr=wb['Mail Response Summary MM']; rows=[]
for r in range(9,mr.max_row+1):
    d=mr.cell(r,2).value
    if isinstance(d,datetime.datetime):
        rows.append((ml(d), mr.cell(r,3).value, mr.cell(r,4).value, mt(d)))
out['mailings_recent']=[r[:3] for r in reversed(rows[-12:])]
# The axis token beside every month-labelled series. Chart renderers read these;
# they never slice a prose label. The workbook hands us real datetimes, so the
# token is emitted at source rather than parsed back out of "%b %Y".
out['axis_months']={'monthly_rev_last12':month_toks[-12:],
                    'swipespend_36':tail_toks,
                    'mailings_recent':[r[3] for r in reversed(rows[-12:])]}
print(json.dumps(out,indent=1,default=str))
# dco_eligible from DCO MM tab
try:
    dco=wb['DCO MM']
    for r in range(1,60):
        for c in (2,3,4):
            v=dco.cell(r,c).value
            if isinstance(v,str) and 'Eligible ARS Accounts' in v:
                for cc in range(c+1,c+4):
                    x=dco.cell(r,cc).value
                    if isinstance(x,(int,float)): out['dco_eligible']=int(x); break
                break
except Exception as e:
    pass
import json as _j
_j.dump(out, open(sys.argv[2],'w'), indent=1, default=str)
print('dco_eligible=',out.get('dco_eligible'))
