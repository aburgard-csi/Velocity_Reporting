#!/usr/bin/env python3
"""MM ARS extraction: reads the '... MM' tabs of a Lift Matrix workbook into base.json.

    python3 extract_base_gen.py <workbook.xlsx> <base.json>

**A blank Key Trends month is a possible data issue, never a zero (2026-09-14).** This
read each month as `round(spend.get(m, 0) or 0, 2)` and the card count as
`(tot or 0) - (non or 0)`, so a blank month became $0 spend and zero cardholders and
charted as a collapse. It never crashed, which is why it went unseen; the SM extractor's
version of the same read crashed on 1657 and was fixed first. Both extractors now share
`base_guard.key_trends`: a blank stays None, the unevaluated-workbook guard runs first,
and any blank month left over stops the run with a POSSIBLE DATA ISSUE message naming the
workbook and the months, with nothing written to base.json.

Import-safe: the work happens in `main()`, so `extract()` can be tested directly.
"""
import datetime
import json
import os
import sys

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actuals_tab
import xl_cache
import base_guard as _bg                        # noqa: E402  (one definition, shared)
from base_guard import data_issue, key_trends   # noqa: E402


def ml(v): return v.strftime('%b %Y') if isinstance(v, datetime.datetime) else v
def rowvals(ws, r): return [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]


def find_row(ws, label, c=3, r1=1, r2=80):
    for r in range(r1, r2):
        v = ws.cell(r, c).value
        if isinstance(v, str) and v.strip() == label:
            return r
    return None


def extract(wb):
    out = {}
    ef = wb['Executive Financials MM']
    out['client'] = ef.cell(4, 2).value
    out['data_label'] = ef.cell(6, 2).value
    out['months'] = ef.cell(7, 4).value
    out['mailings'] = ef.cell(8, 4).value

    def efv(label, col):
        for r in range(14, 30):
            if isinstance(ef.cell(r, 3).value, str) and ef.cell(r, 3).value.strip() == label:
                return ef.cell(r, col).value
        return None
    out['cur_revenue'] = efv('Total Incremental Revenue', 4)
    out['ltd_revenue'] = efv('Total Incremental Revenue', 6)
    out['cur_profit'] = efv('Incremental Profit', 4)
    out['ltd_profit'] = efv('Incremental Profit', 6)
    out['ltd_costs'] = efv('Total Costs', 6)
    out['cur_costs']=efv('Total Costs',4)   # current-month ARS expense = revenue to CSI (perf page)
    out['ltd_plan_profit'] = efv('Incremental Profit', 7)
    # Always emit profitability; guard only the DENOMINATOR. Gating on revenue too
    # omitted the key for a young program with no revenue booked yet (1549 Wellworth),
    # and build_ars_gen then died with KeyError: 'profitability'. Zero revenue against
    # real costs is a true 0.00 : 1, not missing data.
    out['profitability'] = round(out['ltd_revenue'] / abs(out['ltd_costs']), 2) if out['ltd_costs'] else 0.0
    # monthly incremental revenue = Total Incremental Income (Summary block, row 9)
    amr = wb['All Months Rollup MM']; hdr = rowvals(amr, 8)
    r9 = rowvals(amr, find_row(amr, 'Total Incremental Income', c=3, r1=8, r2=12))
    months = [(ml(hdr[i]), (r9[i] or 0)) for i in range(len(hdr)) if isinstance(hdr[i], datetime.datetime)]
    out['monthly_rev_last12'] = months[-12:]
    out['monthly_rev_sum12'] = round(sum(v for _, v in months[-12:]))
    out['monthly_rev_avg12'] = round(out['monthly_rev_sum12'] / 12)
    # Key Trends MM
    kt = wb['Key Trends MM']; khdr = rowvals(kt, 8)

    def kseries(label):
        r = find_row(kt, label, c=3, r1=8, r2=48)
        if not r:
            return {}
        vals = rowvals(kt, r)
        return {ml(khdr[i]): vals[i] for i in range(len(khdr)) if isinstance(khdr[i], datetime.datetime)}
    spend = kseries('Total Spend (millions)'); tot = kseries('Total Accounts (000)')
    non = kseries('Non Card Holding Accounts (000)')
    mos = [ml(v) for v in khdr if isinstance(v, datetime.datetime)]
    # A blank cell stays None and its month is listed (base_guard.key_trends, shared with SM).
    out['swipespend_36'], out['key_trends_blank'] = key_trends(spend, tot, non, mos[-36:])
    # Mail Response Summary MM: col2 month, col3 NU5+, col4 threshold
    mr = wb['Mail Response Summary MM']; rows = []
    for r in range(9, mr.max_row + 1):
        d = mr.cell(r, 2).value
        if isinstance(d, datetime.datetime):
            rows.append((ml(d), mr.cell(r, 3).value, mr.cell(r, 4).value))
    out['mailings_recent'] = list(reversed(rows[-12:]))
    # The Actuals tab's month-by-month revenue and cost (2026-09-22). Executive Financials
    # carries the same arithmetic already summed; the Revenue Guarantee slide needs the
    # months, because a guarantee is a statement about revenue against cost over the life of
    # the program and only the months show whether a client is closing on it or drifting.
    out['actuals'] = actuals_tab.read(wb, mm=True)
    return out


def dco_eligible(wb):
    """`Eligible ARS Accounts` from the DCO MM tab, or None when the tab or value is absent.

    The LAST labelled row in the first 60 wins, as the module-scope loop this replaced
    did: it kept scanning after a hit. The tab can carry the label twice (1542 reads
    13,044 then 11,275), and returning the first changed 1542's figure in the rewrite.
    """
    found = None
    try:
        dco = wb['DCO MM']
        for r in range(1, 60):
            for c in (2, 3, 4):
                v = dco.cell(r, c).value
                if isinstance(v, str) and 'Eligible ARS Accounts' in v:
                    for cc in range(c + 1, c + 4):
                        x = dco.cell(r, cc).value
                        if isinstance(x, (int, float)):
                            found = int(x)
                            break
                    break
    except Exception:
        pass
    return found


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    wb = xl_cache.load(argv[0])   # each sheet read once, not re-streamed per cell
    out = extract(wb)
    name = os.path.basename(argv[0])
    # A workbook saved without evaluating its formulas reads as the template's zeros.
    # Checked FIRST: it names the likelier cause of blank months too.
    _bg.check(out, name)
    issue = data_issue(out, name)
    if issue:
        raise SystemExit(issue)
    print(json.dumps(out, indent=1, default=str))
    d = dco_eligible(wb)
    if d is not None:
        out['dco_eligible'] = d
    with open(argv[1], 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1, default=str)
    print('dco_eligible=', out.get('dco_eligible'))


if __name__ == '__main__':
    main()
