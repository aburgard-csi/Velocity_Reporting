import json, glob, shutil, os, re
B = "//PADMIS105/Velocity_company/CSM_Reporting/Inputs/VIP Data/"
exec(open('ics_raw.py').read())
TODAY = "2026-10-27"
log = []
def find(cid):
    return glob.glob(B + f"ICS/{cid}-*/{cid}_ics.json")[0]
def resolve(trunc, names):
    t = trunc.rstrip('.').strip()
    c = [n for n in names if n.lower().startswith(t.lower())]
    return c
for cid, v in R.items():
    f = find(cid)
    bak = f.replace("_ics.json", "_ics.2026-10-27.bak.json")
    if not os.path.exists(bak):
        shutil.copy2(f, bak)
    d = json.load(open(f, encoding='utf-8'))
    r = d['referrals']
    old = dict(prev=r['previous_month']['value'], ytd=r['year_to_date'], ptd=r['program_to_date'], mtd=r['month_to_date']['value'])
    goal = r['monthly_goal']; assert goal == v['goal_oct'] or cid == '1632' and goal == 1554, (cid, goal, v['goal_oct'])
    # trend
    t = r['trend']; assert t['months'][-1] == 'Oct 26', (cid, t['months'][-3:])
    sep_old = t['referrals'][-2]
    t['referrals'][-1] = v['mtd']; t['referrals'][-2] = v['prev']; t['partial_last'] = True
    r['previous_month']['value'] = v['prev']
    r['month_to_date'] = {"label": "October", "value": v['mtd'], "partial": True}
    r['year_to_date'] = v['ytd']; r['program_to_date'] = v['ptd']
    r['prev_month_vs_goal_pct'] = round(v['prev'] / goal * 100)
    r['latest_data_month'] = '2026-10'
    # YTD by branch
    oldnames = [b['name'] for b in r['by_branch']['branches']]
    oldmap = {b['name']: b for b in r['by_branch']['branches']}
    octref = {n: ref for n, g, ref in v.get('oct_branch', [])}
    if cid == '1632':
        newb = []
        for n, ref, g in v['ytd_top']:
            m = resolve(n, oldnames); name = m[0] if len(m) >= 1 else n
            newb.append({"name": name, "referrals": ref, "goal": g})
            if len(m) != 1: log.append(f"{cid} YTD name '{n}' matched {m}")
        r['by_branch']['branches'] = newb
        r['by_branch']['_note'] = "2026-10-27: top 15 rows of ~220 branches (partial_list). Names resolved from the 2026-10-01 list."
        top = [{"name": n, "referrals": c} for n, c in v['by_branch_top']]
        r['_current_month_by_branch'] = {"month": "2026-10", "partial": True, "branches": top, "total": v['mtd'],
                                         "listed_sum": sum(x['referrals'] for x in top), "partial_list": True}
    else:
        newb = []
        used = set()
        for n, ref, g in v['ytd_branches']:
            if n in oldmap: name = n
            else:
                m = [x for x in resolve(n, oldnames) if x not in used]
                if len(m) > 1 and n.startswith('Lebanon'):
                    # disambiguate by old + october referrals
                    m = [x for x in m if oldmap[x]['referrals'] + octref.get(x, 0) == ref] or m
                name = m[0] if m else n
                if len(m) != 1: log.append(f"{cid} YTD name '{n}' -> {m}")
            used.add(name)
            newb.append({"name": name, "referrals": ref, "goal": g})
        r['by_branch']['branches'] = newb
        cur = sorted([(n, ref) for n, g, ref in v['oct_branch'] if ref > 0], key=lambda x: -x[1])
        r['_current_month_by_branch'] = {"month": "2026-10", "partial": True, "branches": [{"name": n, "referrals": c} for n, c in cur], "total": v['mtd']}
        # branch success Oct
        nums = {x['name']: x.get('branch_number') for x in (r.get('_branch_success_2026_09') or {}).get('rows', [])}
        rows = []
        for n, g, ref in v['oct_branch']:
            row = {"branch_number": nums.get(n), "name": n, "goal": g, "referrals": ref}
            row["pct_of_goal"] = round(ref / g * 100, 1) if g else None
            rows.append(row)
        r['_branch_success_2026_10'] = {"month": "2026-10", "partial": True, "rows": rows}
    r['_truncated_note'] = ("2026-10-27: branch tables read in full (scrolled) and reconcile to the YTD and MTD tiles; none truncated."
                            if cid != '1632' else "2026-10-27: 1632 has ~220 branches; YTD and by-branch lists are top rows only (partial_list).")
    r['_origination_pct']['_note'] = "VIP's Origination widget still shows September (the Previous Month split) on 2026-10-27; not re-read as October."
    note = (f"Pull 2026-10-27 (VIP updated): October MTD={v['mtd']} (partial); September {old['prev']}->{v['prev']}; "
            f"YTD {old['ytd']}->{v['ytd']}; PTD {old['ptd']}->{v['ptd']}; latest_data_month 2026-10. "
            + (f"VIP restated September {old['prev']} -> {v['prev']}; closed months otherwise unchanged. " if v['prev'] != old['prev'] else "No closed month restated. ")
            + "Branch Success and by-branch tables are October MTD; September Branch Success kept in _branch_success_2026_09.")
    d['meta']['data_pull'] = TODAY
    d['meta']['note_period'] = note
    json.dump(d, open(f, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    log.append(f"{cid}: prev {old['prev']}->{v['prev']} mtd {old['mtd']}->{v['mtd']} ytd {old['ytd']}->{v['ytd']} ptd {old['ptd']}->{v['ptd']} | trend Sep was {sep_old}")
print("\n".join(log))
