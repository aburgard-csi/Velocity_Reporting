#!/usr/bin/env python3
"""Secondary ARS extraction pipeline: reads the BASE (non-MM) workbook tabs for
workbooks whose month-end 'MM' tabs did not populate. Normalizes to the same
figures the standard MM pipeline produces. Usage:
    python3 base_tab_extract.py <workbook.xlsx> [<dco.xlsx>]  -> prints JSON
"""
import sys,json,datetime,openpyxl
def load(p): return openpyxl.load_workbook(p,read_only=True,data_only=True)
def ml(v): return v.strftime("%b %Y") if isinstance(v,datetime.datetime) else v
def mt(v): return v.strftime("%b%y") if isinstance(v,datetime.datetime) else v
def rowvals(ws,r): return [ws.cell(r,c).value for c in range(1,ws.max_column+1)]
def find_row(ws,label,c=3,r1=8,r2=60):
    for r in range(r1,r2):
        v=ws.cell(r,c).value
        if isinstance(v,str) and v.strip()==label: return r
    return None

def extract(wb):
    out={}
    ef=wb["Executive Financials"]
    out["client"]=ef.cell(4,2).value
    out["data_label"]=ef.cell(6,2).value
    out["months"]=ef.cell(7,4).value
    out["mailings"]=ef.cell(8,4).value
    # find rows by label in col C
    def efv(label,col):
        for r in range(14,34):
            if isinstance(ef.cell(r,3).value,str) and ef.cell(r,3).value.strip()==label:
                return ef.cell(r,col).value
        return None
    out["cur_revenue"]=efv("Total Incremental Revenue",4)
    out["ltd_revenue"]=efv("Total Incremental Revenue",6)
    out["cur_profit"]=efv("Incremental Profit",4)
    out["ltd_profit"]=efv("Incremental Profit",6)
    out["ltd_costs"]=efv("Total Costs",6)
    out["ltd_plan_profit"]=efv("Incremental Profit",7)
    if out["ltd_revenue"] and out["ltd_costs"]:
        out["profitability"]=round(out["ltd_revenue"]/abs(out["ltd_costs"]),2)
    # Monthly incremental revenue = Interchange Revenue + NSF Revenue (All Months Rollup)
    amr=wb["All Months Rollup"]; hdr=rowvals(amr,8)
    ri=find_row(amr,"Total Interchange Revenue"); rn=find_row(amr,"Total NSF Revenue")
    iv=rowvals(amr,ri); nv=rowvals(amr,rn)
    months=[(ml(hdr[i]),(iv[i] or 0)+(nv[i] or 0)) for i in range(len(hdr)) if isinstance(hdr[i],datetime.datetime)]
    month_toks=[mt(h) for h in hdr if isinstance(h,datetime.datetime)]
    out["monthly_rev_last12"]=months[-12:]
    out["monthly_rev_sum12"]=round(sum(v for _,v in months[-12:]))
    out["monthly_rev_avg12"]=round(out["monthly_rev_sum12"]/12)
    # Key Trends: spend + card-holding
    kt=wb["Key Trends"]; khdr=rowvals(kt,8)
    def kseries(label):
        r=find_row(kt,label); 
        if not r: return {}
        vals=rowvals(kt,r); return {ml(khdr[i]):vals[i] for i in range(len(khdr)) if isinstance(khdr[i],datetime.datetime)}
    spend=kseries("Total Spend (millions)"); tot=kseries("Total Accounts (000)"); non=kseries("Non Card Holding Accounts (000)")
    mos=[ml(v) for v in khdr if isinstance(v,datetime.datetime)]
    card={m:round(((tot.get(m) or 0)-(non.get(m) or 0))*1000) for m in mos}
    tail=mos[-36:]
    tail_toks=[mt(v) for v in khdr if isinstance(v,datetime.datetime)][-36:]
    out["swipespend_36"]=[(m,round(spend.get(m,0),2),card.get(m,0)) for m in tail]
    # Mail Response Summary (recent mailings): month, NU5+, threshold-met
    mr=wb["Mail Response Summary"]; rows=[]
    for r in range(9,mr.max_row+1):
        d=mr.cell(r,2).value
        if isinstance(d,datetime.datetime):
            rows.append((ml(d), mr.cell(r,4).value, mr.cell(r,6).value, mt(d)))  # NU5+, ThresholdMet
    out["mailings_recent"]=[r[:3] for r in reversed(rows[-12:])]   # rows are oldest-first; take newest 12
    # The axis token beside every month-labelled series. Chart renderers read
    # these; they never slice a prose label. The workbook hands us real
    # datetimes, so the token is emitted at source rather than parsed back out
    # of "%b %Y".
    out["axis_months"]={"monthly_rev_last12":month_toks[-12:],
                        "swipespend_36":tail_toks,
                        "mailings_recent":[r[3] for r in reversed(rows[-12:])]}
    return out

wb=load(sys.argv[1]); res=extract(wb)
if len(sys.argv)>2:
    dco=load(sys.argv[2]); ws=dco[dco.sheetnames[0]]
    def dcell(label):
        for r in range(6,60):
            if isinstance(ws.cell(r,4).value,str) and label in ws.cell(r,4).value: return ws.cell(r,5).value
            if isinstance(ws.cell(r,3).value,str) and label in ws.cell(r,3).value: return ws.cell(r,5).value
        return None
    res["dco_eligible"]=dcell("Eligible ARS Accounts")
print(json.dumps(res,indent=1,default=str))
