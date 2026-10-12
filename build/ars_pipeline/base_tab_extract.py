#!/usr/bin/env python3
"""Secondary ARS extraction pipeline: reads the BASE (non-MM) workbook tabs for
workbooks whose month-end 'MM' tabs did not populate. Normalizes to the same
figures the standard MM pipeline produces. Usage:
    python3 base_tab_extract.py <workbook.xlsx> [<dco.xlsx>]  -> prints JSON

**A blank Key Trends month is a possible data issue, never a zero (2026-09-14).**
`round(spend.get(m, 0), 2)` only defaulted a month that was ABSENT; a month whose
cell was blank came back as None and raised TypeError. 1657 Marine Credit Union's
2026.09 workbook crashed here — and because the crash came before the
unevaluated-workbook guard, what reached the dashboard was a traceback instead of
the real problem: the workbook was never calculated (one month, Sep 2007, the
template's date). Blank months now extract as None, the guard runs first, and any
blank month left over stops the run with a POSSIBLE DATA ISSUE message naming the
workbook and the months — so a gap is called out, not charted as $0.

Import-safe: the work happens in `main()`, so `extract()` can be tested directly.
"""
import sys,json,datetime,os,openpyxl
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base_guard import data_issue, key_trends   # one definition, shared with extract_base_gen
import base_guard as _bg
import actuals_tab
import xl_cache
def load(p): return xl_cache.load(p)   # each sheet read once, not re-streamed per cell
def ml(v): return v.strftime("%b %Y") if isinstance(v,datetime.datetime) else v
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
    out["cur_costs"]=efv("Total Costs",4)   # current-month ARS expense = revenue to CSI (perf page)
    out["ltd_plan_profit"]=efv("Incremental Profit",7)
    if out["ltd_revenue"] and out["ltd_costs"]:
        # Full precision; rounding happens where it is printed (see extract_base_gen, 2026-10-12).
        out["profitability"]=out["ltd_revenue"]/abs(out["ltd_costs"])
    # Monthly incremental revenue = Interchange Revenue + NSF Revenue (All Months Rollup)
    amr=wb["All Months Rollup"]; hdr=rowvals(amr,8)
    ri=find_row(amr,"Total Interchange Revenue"); rn=find_row(amr,"Total NSF Revenue")
    iv=rowvals(amr,ri); nv=rowvals(amr,rn)
    months=[(ml(hdr[i]),(iv[i] or 0)+(nv[i] or 0)) for i in range(len(hdr)) if isinstance(hdr[i],datetime.datetime)]
    out["monthly_rev_last12"]=months[-12:]
    out["monthly_rev_sum12"]=round(sum(v for _,v in months[-12:]))
    out["monthly_rev_avg12"]=round(out["monthly_rev_sum12"]/12)
    # Key Trends: spend + card-holding
    kt=wb["Key Trends"]; khdr=rowvals(kt,8)
    def kseries(label):
        r=find_row(kt,label)
        if not r: return {}
        vals=rowvals(kt,r); return {ml(khdr[i]):vals[i] for i in range(len(khdr)) if isinstance(khdr[i],datetime.datetime)}
    spend=kseries("Total Spend (millions)"); tot=kseries("Total Accounts (000)"); non=kseries("Non Card Holding Accounts (000)")
    mos=[ml(v) for v in khdr if isinstance(v,datetime.datetime)]
    tail=mos[-36:]
    # A blank cell stays None and its month is listed: a month with no figures is not a
    # month of $0 spend and zero cardholders (base_guard.key_trends, shared with MM).
    out["swipespend_36"], out["key_trends_blank"] = key_trends(spend, tot, non, tail)
    # Mail Response Summary (recent mailings): month, NU5+, threshold-met
    mr=wb["Mail Response Summary"]; rows=[]
    for r in range(9,mr.max_row+1):
        d=mr.cell(r,2).value
        if isinstance(d,datetime.datetime):
            rows.append((ml(d), mr.cell(r,4).value, mr.cell(r,6).value))  # NU5+, ThresholdMet
    out["mailings_recent"]=list(reversed(rows[-12:]))   # rows are oldest-first; take newest 12
    # The Actuals tab's month-by-month revenue and cost (2026-09-22) — the SM shape, whose
    # cost rows are spot mailings, points and a program fee rather than a respondent fee.
    # Only the two totals rows are read, and those exist in both shapes.
    out["actuals"]=actuals_tab.read(wb, mm=False)
    return out


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    wb=load(argv[0]); res=extract(wb)
    name=os.path.basename(argv[0])
    # A workbook saved without evaluating its formulas reads as the template's zeros.
    # Checked FIRST: it names the likelier cause of blank months too.
    _bg.check(res, name)
    issue=data_issue(res, name)
    if issue:
        raise SystemExit(issue)
    if len(argv)>1:
        dco=load(argv[1]); ws=dco[dco.sheetnames[0]]
        def dcell(label):
            for r in range(6,60):
                if isinstance(ws.cell(r,4).value,str) and label in ws.cell(r,4).value: return ws.cell(r,5).value
                if isinstance(ws.cell(r,3).value,str) and label in ws.cell(r,3).value: return ws.cell(r,5).value
            return None
        res["dco_eligible"]=dcell("Eligible ARS Accounts")
    print(json.dumps(res,indent=1,default=str))


if __name__ == "__main__":
    main()
