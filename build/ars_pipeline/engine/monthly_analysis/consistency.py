"""Cross-surface consistency: the same concept must carry ONE number.

Every rule here exists because two surfaces disagreed on a real deck
(issue #17, the 1585 eyeball round): the hero quoted 12.4% while the
per-mailer table said 11.4% for the same offer; three slides carried
three responder counts; the P&L slide relabeled window revenue as
cumulative. The deck refuses to build while any rule is violated --
a contradictory deck is worse than no deck.

Rules fire only when BOTH sides of a comparison are present; absent
keys are never violations (sections decline independently by design).
"""

from __future__ import annotations


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(n, d, digits=1):
    return round(100 * n / d, digits) if d else 0.0


# scorecard label -> the metric key its value copies (synthesis._scorecard)
SCORECARD_SOURCES = {
    "Take rate, last 12 months": "dctr_l12m",
    "Reg E opt-in, last 12 months": "rege_l12m_pct",
    "Latest response rate": "latest_resprate",
    "Responder spend gain vs control": "ba_lift_net",
    "Cardholders moving up a swipe tier": "mig_up_pct",
    "Responder up-tier advantage": "mig_responder_up_advantage_pp",
    "Responders close less than control": "attrition_mailer_lift_pp",
    "Personal accounts leaking to external financial products":
        "fin_leaking_pct",
    "Personal accounts paying a named competitor": "comp_with_competitor_pct",
}

# branch call-outs [name, rate, n] -> the table they must appear in
# (table rows carry the rate at index 3)
BRANCH_CALLOUTS = (
    ("take_branch", "dctr_branch_best", "dctr_branch_worst",
     "dctr_branch_spread_pp"),
    ("rege_branch", "rege_branch_best", "rege_branch_worst",
     "rege_branch_spread_pp"),
    ("attrition_by_branch", "attrition_branch_best",
     "attrition_branch_worst", None),
)


def audit(m: dict, txn: dict | None = None) -> list[str]:
    """Return human-readable violations; empty list = all surfaces agree.

    txn is the txn_metrics dict when a transaction run preceded this one:
    its internal invariants are checked, and scorecard rows that quote
    txn figures are tied through it."""
    v: list[str] = []
    sources = {**(txn or {}), **m}   # scorecard/opportunity lookups

    def close(a, b, tol):
        return a is not None and b is not None and abs(a - b) <= tol

    # ---- 1. the hero rail IS the campaign table's last row --------------
    camp = [r for r in (m.get("campaign_rates") or []) if len(r) >= 4]
    if camp:
        tag, mailed, resp, rate = camp[-1][:4]
        if m.get("latest_mailing") is not None \
                and str(m["latest_mailing"]) != str(tag):
            v.append(f"latest_mailing {m['latest_mailing']} is not the last "
                     f"campaign_rates row ({tag})")
        for key, want in (("latest_mailed", mailed),
                          ("latest_responders", resp),
                          ("latest_resprate", rate)):
            got = _num(m.get(key))
            if got is not None and not close(got, _num(want), 0.051):
                v.append(f"{key} {m[key]} != campaign_rates[-1] {want} "
                         f"(hero rail vs per-mailer table)")

        # ---- 2. each row's rate recomputes from its own counts ----------
        for r in camp:
            want = _pct(r[2], r[1])
            if not close(_num(r[3]), want, 0.051):
                v.append(f"campaign_rates {r[0]}: rate {r[3]}% != "
                         f"{r[2]}/{r[1]} = {want}%")

        # ---- 3. the mean tile ties to the rows --------------------------
        mean = _num(m.get("resprate_mean"))
        if mean is not None:
            want = sum(_num(r[3]) or 0 for r in camp) / len(camp)
            if not close(mean, want, 0.06):
                v.append(f"resprate_mean {mean}% != mean of campaign_rates "
                         f"rows ({want:.2f}%)")

        # ---- 4. best/worst are actual rows ------------------------------
        rates = {str(r[0]): _num(r[3]) for r in camp}
        for key in ("resprate_best", "resprate_worst"):
            pair = m.get(key)
            if pair and len(pair) >= 2:
                have = rates.get(str(pair[0]))
                if have is None or not close(_num(pair[1]), have, 0.051):
                    v.append(f"{key} {pair} does not match any "
                             f"campaign_rates row")

    # ---- 4b. the program number: events sum, and unique <= events -------
    rt = _num(m.get("responses_total"))
    if rt is not None and camp:
        want = sum(_num(r[2]) or 0 for r in camp)
        if rt != want:
            v.append(f"responses_total {int(rt)} != sum of campaign_rates "
                     f"responders ({int(want)})")
    _reach = _num(m.get("reach_total"))
    if rt is not None and _reach is not None and _reach > rt:
        v.append(f"reach_total {int(_reach)} (unique accounts) exceeds "
                 f"responses_total {int(rt)} (events) -- impossible")

    # ---- 4c. the lift distribution ties to itself -----------------------
    dn = _num(m.get("dot_n"))
    hist = m.get("dot_hist") or []
    if dn is not None and hist:
        hsum = sum(_num(b[1]) or 0 for b in hist)
        if hsum != dn:
            v.append(f"dot_hist bins sum to {int(hsum)}, dot_n is {int(dn)}")
    segd = m.get("dot_by_segment") or []
    if dn is not None and segd:
        ssum = sum(_num(r[1]) or 0 for r in segd)
        if ssum != dn:
            v.append(f"dot_by_segment pairs sum to {int(ssum)}, dot_n is "
                     f"{int(dn)}")

    # ---- 5. depth sums to reach; cumulative reach ends at reach ---------
    reach = _num(m.get("reach_total"))
    depth = m.get("depth")
    if reach is not None and depth and len(depth) == 3:
        if sum(depth) != int(reach):
            v.append(f"depth {depth} sums to {sum(depth)}, reach_total is "
                     f"{int(reach)} (depth slide vs reach slide)")
    cum = m.get("reach_cumulative") or []
    if reach is not None and cum and len(cum[-1]) >= 2:
        if _num(cum[-1][1]) != reach:
            v.append(f"reach_cumulative ends at {cum[-1][1]}, reach_total "
                     f"is {int(reach)}")

    # ---- 6. the eligibility split sums ----------------------------------
    ne, np_, nb = (_num(m.get(k)) for k in
                   ("n_eligible", "n_eligible_personal",
                    "n_eligible_business"))
    if None not in (ne, np_, nb) and np_ + nb != ne:
        v.append(f"n_eligible {int(ne)} != personal + business "
                 f"({int(np_)} + {int(nb)})")
    nt = _num(m.get("n_total"))
    er = _num(m.get("eligibility_rate"))
    if None not in (nt, ne, er) and not close(er, _pct(ne, nt), 0.06):
        v.append(f"eligibility_rate {er}% != {int(ne)}/{int(nt)}")

    # ---- 7. the workbook ledger ties ------------------------------------
    rev, cost, prof = (_num(m.get(k)) for k in
                       ("wb_revenue_ltd", "wb_costs_ltd", "wb_profit_ltd"))
    if None not in (rev, cost, prof) and not close(prof, rev - abs(cost), 2):
        v.append(f"workbook ledger: profit {int(prof)} != revenue "
                 f"{int(rev)} - fees {int(abs(cost))} (hero vs P&L tiles)")

    # ---- 8. value groups cannot exceed their bases ----------------------
    # rows are dicts from value._cut: {"group": ..., "n": ...}
    vbr = [r for r in (m.get("value_by_response") or [])
           if isinstance(r, dict)]
    resp_n = next((_num(r.get("n")) for r in vbr
                   if str(r.get("group")) == "Responder"), None)
    if resp_n is not None and reach is not None and resp_n > reach:
        v.append(f"value_by_response Responder accounts {int(resp_n)} "
                 f"exceed reach_total {int(reach)}")
    if vbr and np_ is not None:
        total = sum(_num(r.get("n")) or 0 for r in vbr)
        if total > np_:
            v.append(f"value_by_response groups sum to {int(total)}, more "
                     f"than the eligible personal base {int(np_)}")

    # ---- 9. scorecard rows re-quote live metrics ------------------------
    for row in (m.get("syn_scorecard") or []):
        if len(row) < 2:
            continue
        key = SCORECARD_SOURCES.get(str(row[0]))
        want = _num(sources.get(key)) if key else None
        got = _num(row[1])
        if want is not None and got is not None and not close(got, want, 0.051):
            v.append(f"scorecard '{row[0]}' shows {row[1]} but {key} "
                     f"is {sources[key]}")

    # ---- 10. opportunity values tie to their named basis key ------------
    for o in (m.get("syn_opportunities") or []):
        if not isinstance(o, dict) or o.get("kind") != "revenue":
            continue
        basis = str(o.get("basis", ""))
        want = _num(sources.get(basis)) if basis in sources else None
        got = _num(o.get("value"))
        if want is not None and got is not None and not close(got, want, 1):
            v.append(f"opportunity '{o.get('label')}' quotes {o.get('value')} "
                     f"but its basis {basis} is {sources[basis]}")

    # ---- 11. branch call-outs must match their tables -------------------
    for table_key, best_key, worst_key, spread_key in BRANCH_CALLOUTS:
        table = m.get(table_key) or []
        rates = {str(r[0]): _num(r[3]) for r in table if len(r) >= 4}
        pair_vals = {}
        for ck in (best_key, worst_key):
            pair = m.get(ck)
            if not pair or len(pair) < 2 or not rates:
                continue
            have = rates.get(str(pair[0]))
            got = _num(pair[1])
            pair_vals[ck] = got
            if have is None or not close(got, have, 0.051):
                v.append(f"{ck} {pair[:2]} does not match any {table_key} "
                         f"row (table has {rates.get(str(pair[0]))})")
        spread = _num(m.get(spread_key)) if spread_key else None
        b, w = pair_vals.get(best_key), pair_vals.get(worst_key)
        if spread is not None and b is not None and w is not None \
                and not close(spread, b - w, 0.11):
            v.append(f"{spread_key} {spread} != best - worst "
                     f"({b} - {w})")

    # ---- 12. txn internals: rates and per-account figures recompute -----
    if txn:
        for prefix in ("fin", "finb"):
            tot = _num(txn.get(f"{prefix}_accounts_total"))
            leak = _num(txn.get(f"{prefix}_leaking_accounts"))
            pct = _num(txn.get(f"{prefix}_leaking_pct"))
            if None not in (tot, leak, pct) and tot \
                    and not close(pct, _pct(leak, tot), 0.06):
                v.append(f"{prefix}_leaking_pct {pct}% != "
                         f"{int(leak)}/{int(tot)}")
            for r in (txn.get(f"{prefix}_by_category") or []):
                if len(r) >= 6 and _num(r[1]) and _num(r[4]) is not None \
                        and _num(r[5]) is not None \
                        and not close(_num(r[5]), _num(r[4]) / _num(r[1]), 1):
                    v.append(f"{prefix}_by_category {r[0]}: $/acct {r[5]} "
                             f"!= {r[4]}/{r[1]}")
        ctot = _num(txn.get("comp_accounts_total"))
        cwith = _num(txn.get("comp_with_competitor"))
        cpct = _num(txn.get("comp_with_competitor_pct"))
        if None not in (ctot, cwith, cpct) and ctot \
                and not close(cpct, _pct(cwith, ctot), 0.06):
            v.append(f"comp_with_competitor_pct {cpct}% != "
                     f"{int(cwith)}/{int(ctot)}")

    return v
