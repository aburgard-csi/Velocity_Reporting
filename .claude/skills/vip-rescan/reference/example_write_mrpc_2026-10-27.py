import json, glob, shutil, os
B = "//PADMIS105/Velocity_company/CSM_Reporting/Inputs/VIP Data/"
exec(open('mrpc_raw.py').read())
TODAY = "2026-10-27"
log = []
for cid, v in M.items():
    f = glob.glob(B + f"MRPC/{cid}-*/{cid}_mrpc.json")[0]
    bak = f.replace("_mrpc.json", "_mrpc.2026-10-27.bak.json")
    if not os.path.exists(bak): shutil.copy2(f, bak)
    d = json.load(open(f, encoding='utf-8'))
    ch = []
    # enrollments
    if 'enroll' in v and 'months' in v['enroll']:
        e = d['enrollments_by_month']; em = v['enroll']
        for i, m in enumerate(em['months']):
            if m in e['months']:
                j = e['months'].index(m)
            else:
                e['months'].append(m); [e[k].append(0) for k in ('totals','gold','platinum','business')]; j = len(e['months']) - 1
            for k, s in (('gold','gold'),('platinum','platinum'),('business','business')):
                if e[k][j] != em[s][i]: ch.append(f"enroll {m} {k} {e[k][j]}->{em[s][i]}")
                e[k][j] = em[s][i]
            e['totals'][j] = e['gold'][j] + e['platinum'][j] + e['business'][j]
        e['partial_last'] = True
        j = e['months'].index('Sep 26')
        e['last_complete'] = {"label": "Sep 2026", "gold": e['gold'][j], "platinum": e['platinum'][j], "business": e['business'][j]}
        e['_split_note'] = f"Exact per-month Gold/Platinum/Business read from the VIP stacked bars {TODAY}. Sep-26 complete; Oct-26 partial (month to date)." + (" " + em['note'] if em.get('note') else "")
    elif 'enroll' in v:   # 1075: only Oct partial + Sep check
        e = d['enrollments_by_month']; j = e['months'].index('Oct 26')
        g, p, b = v['enroll']['oct']; e['gold'][j], e['platinum'][j], e['business'][j] = g, p, b; e['totals'][j] = g + p + b; e['partial_last'] = True
        k = e['months'].index('Sep 26'); assert (e['gold'][k], e['platinum'][k], e['business'][k]) == v['enroll']['sep'], cid
        e['_split_note'] = f"Per-month split read from the VIP stacked bars {TODAY}; Sep-26 and earlier unchanged vs 2026-10-01; Oct-26 partial (month to date)."
        ch.append(f"Oct 26 partial {g}/{p}/{b}")
    # channel pct
    if v.get('channel'):
        old = d['channel']['pct']
        d['channel']['pct'] = {k: v['channel'].get(k, old.get(k)) for k in d['channel']['order']}
        ch.append("channel pct " + json.dumps(d['channel']['pct']))
    # aging
    if v.get('aging'):
        d['_enrollment_aging'] = {"as_of": TODAY, "scope": "active status only", "buckets": v['aging']}
    # performance
    if v.get('perf'):
        pv = d['performance_vs_goal']; p = v['perf']
        old_last = (pv['months'][-1], pv['pct_of_goal'][-1])
        pv.update(months=p['months'], enrollments=p['enrollments'], new_accounts=p['new_accounts'], goal=p['goal'], pct_of_goal=p['pct'])
        pv['_note'] = (f"Exact from VIP New Accounts Performance by Period, read {TODAY}; latest complete period 2026-09 "
                       "(table updates on the 15th; 2026-10 due about 2026-11-15). Small restatements of earlier periods vs 2026-10-01 are taken as VIP shows them.")
        ch.append(f"perf now through Sep 26 ({p['enrollments'][-1]} on {p['new_accounts'][-1]}, {p['pct'][-1]}%); was {old_last}")
    # retention
    if v.get('retention'):
        rt = d['retention']; r = v['retention']
        rt['cohort_months'] = r['cohorts']; rt['enrolled'] = r['enrolled']; rt['still_active'] = r['active']
        rt['cancellations_by_reason'] = [{"reason": a, "pct": b} for a, b in r['cancel']]
        rt['_note'] = f"Cohorts {r['cohorts'][0]} to {r['cohorts'][-1]} read {TODAY} from VIP Retention by Month Enrolled (exact labels). still_active declines between pulls as accounts cancel."
        if v['retention'].get('may_active_label_obscured'): rt['_note'] += " 1539 May 26 Total Active label was overprinted; 65 read from the marker."
        if cid == '1437': rt['_note'] += " Cohort totals differ from the 2026-10-01 file by up to +6 (e.g. Jun 25 41 -> 47); taken as VIP shows them."
    # branch tables
    eb = d.setdefault('_enrollments_by_branch', {})
    if 'branch_prev' in v:
        eb['previous_month'] = [{"name": n, "enrollments": c} for n, c in v['branch_prev']]
        eb['year_to_date'] = [{"name": n, "enrollments": c} for n, c in v['branch_ytd']]
        if v.get('branch_ptd'): eb['program_to_date'] = [{"name": n, "enrollments": c} for n, c in v['branch_ptd']]
        eb['_truncated'] = f"Read {TODAY} from the MRPC Performance Top Performers tables (up to 20 rows each; previous month = 2026-09, the latest performance period)." + (" Program-to-date table was still loading and is carried from 2026-10-01." if cid == '1075' else "")
    d['meta']['data_pull'] = TODAY
    d['meta']['note_period'] = (f"Pull {TODAY} (VIP updated): New Accounts Performance now through 2026-09; enrollments Oct-26 partial; retention, cancellations, aging and branch tables re-read. "
                                "Revenue-to-FI and card billing NOT refreshed (revenue data stale for all clients, being fixed with Accounting).")
    json.dump(d, open(f, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    log.append(f"{cid}: " + "; ".join(ch))
print("\n".join(log))
