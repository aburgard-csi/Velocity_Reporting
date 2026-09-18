"""Synthesis: what the CSM says in the room.

Reads metrics only -- every input below is a key another section already
computed -- and runs last, after leaks and the leak pricing. Nothing here
touches the frame, so nothing here can disagree with the sections.

Six things:
  1. the cascade      cards -> spend -> revenue -> retention, one chain
  2. what-if          +5 pts take rate, +5 pts Reg E, priced
  3. opportunity map  every priced gap on one list, ranked by dollars
  4. branch scorecard one row per branch across take, Reg E, value, closures
  5. RAG scorecard    headline metrics judged against their own comparator
                      (trend vs history, responders vs control) -- never an
                      absolute dollar threshold
  6. talking points   the three largest items, as sentences

Items on the opportunity map overlap (a leak is a subset of the cards-
without pool) and are deliberately NOT summed.
"""

from __future__ import annotations

from typing import Any

PLUS_PTS = 5.0
TALKING_POINTS = 3
RAG_TOLERANCE_PP = 1.0


def _num(m: dict, key: str, default=None):
    v = m.get(key, default)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else default


def _money(v) -> str:
    v = float(v or 0)
    return f"${v/1e6:.1f}M" if v >= 1e6 else (f"${v/1e3:.0f}k" if v >= 1e3 else f"${v:,.0f}")


# ---------------------------------------------------------------------------
# 1. cascade
# ---------------------------------------------------------------------------

def _cascade(m: dict) -> list[list]:
    steps = []
    elig, cards = _num(m, "n_eligible"), _num(m, "dctr_cards")
    if elig and cards is not None:
        steps.append(["Eligible accounts", elig, "accounts", None])
        steps.append(["Hold a debit card", cards, "accounts",
                      f"{_num(m, 'dctr_overall', 0)}% take rate"])
    per_card = _num(m, "value_per_card")
    if per_card is not None:
        steps.append(["A card is worth", per_card, "$/acct/yr",
                      "interchange + NSF/OD, with vs without"])
        rev = _num(m, "value_debit_current_revenue")
        if rev is None and cards:
            rev = cards * per_card
        if rev is not None:
            steps.append(["Card revenue on the book", round(rev), "$/yr", None])
    ic = _num(m, "counterfactual_ic_total")
    if ic is not None:
        steps.append(["Interchange earned on responder activation", round(ic), "$",
                      "cumulative, vs what spend would have been without the program"])
    lift = _num(m, "attrition_mailer_lift_pp")
    if lift is not None:
        steps.append(["Responders close less than mailed non-responders", lift, "pts", None])
    dlift = _num(m, "attrition_debit_lift_pp")
    if dlift is not None and m.get("attrition_debit_lift_valid"):
        steps.append(["Cardholders close less than non-holders", dlift, "pts", None])
    return steps


# ---------------------------------------------------------------------------
# 2. what-if
# ---------------------------------------------------------------------------

def _whatif(m: dict) -> dict:
    out: dict[str, Any] = {}
    elig, per_card = _num(m, "n_eligible"), _num(m, "value_per_card")
    if elig and per_card and per_card > 0:
        cards = round(elig * PLUS_PTS / 100)
        out["syn_whatif_dctr_plus5"] = {"pts": PLUS_PTS, "cards": cards,
                                        "value": round(cards * per_card)}
    pool, per_optin = _num(m, "rege_pool"), _num(m, "value_per_optin") or _num(m, "value_rege_delta")
    if pool and per_optin and per_optin > 0:
        optins = round(pool * PLUS_PTS / 100)
        out["syn_whatif_rege_plus5"] = {"pts": PLUS_PTS, "optins": optins,
                                        "value": round(optins * per_optin)}
    return out


# ---------------------------------------------------------------------------
# 3. opportunity map
# ---------------------------------------------------------------------------

def _opportunities(m: dict, warn) -> list[dict]:
    ic_rate = _num(m, "value_ic_rate")
    items: list[dict] = []

    def add(label, n, value, basis, kind="revenue"):
        if n is None or not n:
            return
        if kind == "count":
            items.append({"label": label, "n": int(n), "value": 0,
                          "basis": basis, "kind": kind})
            return
        if value is None or float(value) <= 0:
            return          # a non-positive figure is not an opportunity
        items.append({"label": label, "n": int(n), "value": round(float(value)),
                      "basis": basis, "kind": kind})

    add("Cards for eligible accounts without one, at the historical take rate",
        _num(m, "value_debit_n_without"), _num(m, "value_debit_pot_hist"),
        "value_debit_pot_hist")
    add("Top three debit leaks closed to the portfolio rate",
        _num(m, "dctr_leak_total"), _num(m, "dctr_leak_value"), "dctr_leak_value")
    gap = m.get("dctr_business_gap") or {}
    add("Business take rate brought to the portfolio rate",
        gap.get("accounts_lost"), _num(m, "dctr_business_value"), "dctr_business_value")
    add("Reg E opt-ins at the current election rate",
        _num(m, "value_rege_n_without"), _num(m, "value_rege_pot_current"),
        "value_rege_pot_current")
    add("Reg E elections never made", (m.get("rege_default_opportunity") or {}).get("n"),
        _num(m, "rege_default_value"), "rege_default_value")
    add("Top three Reg E leaks closed to the portfolio rate",
        _num(m, "rege_leak_total"), _num(m, "rege_leak_value"), "rege_leak_value")
    if ic_rate:
        add("Interchange on reactivating dormant cardholders' prior spend",
            _num(m, "reactivation_target_n"),
            (_num(m, "reactivation_target_prior_spend") or 0) * ic_rate,
            "reactivation_target_prior_spend x ICRate")
        add("Interchange at stake on high-risk cardholders' spend",
            _num(m, "retention_high_risk_n"),
            (_num(m, "retention_high_risk_spend") or 0) * ic_rate,
            "retention_high_risk_spend x ICRate", kind="at risk")
    add("Deposits declining at flight-risk accounts",
        _num(m, "flight_risk_n"), _num(m, "flight_risk_decline"),
        "flight_risk_decline", kind="deposits")
    fee_gap = (_num(m, "od_fee_per_acct_optin") or 0) - (_num(m, "od_fee_per_acct_not_optin") or 0)
    if _num(m, "od_optin_no_limit_n") and fee_gap > 0:
        add("Opted-in cardholders with no overdraft limit",
            _num(m, "od_optin_no_limit_n"), None, "count only", kind="count")

    # ---- transaction-intelligence items (present when a txn run preceded) --
    if ic_rate:
        cc = next((r for r in (m.get("fin_by_category") or []) if r[0] == "Credit Cards"), None)
        if cc:
            add("Interchange if competitor credit-card payments rode our debit card",
                cc[1], float(cc[4]) * ic_rate,
                "fin Credit Cards dollars x ICRate (recapture ceiling, not a forecast)")
    add("External financial payments from addressable categories",
        _num(m, "fin_addressable_accounts"), _num(m, "fin_addressable_dollars"),
        "fin_addressable_dollars", kind="at risk")
    add("Dollars flowing to named competitors",
        _num(m, "comp_with_competitor"), _num(m, "comp_competitor_dollars"),
        "comp_competitor_dollars", kind="at risk")
    car = m.get("comp_at_risk") or {}
    if car.get("with_competitor"):
        add("Recently inactive accounts with competitor activity",
            car["with_competitor"], None, "comp_at_risk", kind="count")

    # Items whose underlying accounts/transactions overlap carry the tag, so
    # nobody adds them: a leak is a subset of the cards-without pool; the
    # three TXN money items re-cut the same transfer rows.
    overlaps = {
        "dctr_leak_value": ["value_debit_pot_hist"],
        "dctr_business_value": ["value_debit_pot_hist"],
        "rege_leak_value": ["value_rege_pot_current"],
        "rege_default_value": ["value_rege_pot_current"],
        "fin_addressable_dollars": ["comp_competitor_dollars",
                                    "fin Credit Cards dollars x ICRate (recapture ceiling, not a forecast)"],
        "comp_competitor_dollars": ["fin_addressable_dollars"],
        "fin Credit Cards dollars x ICRate (recapture ceiling, not a forecast)":
            ["fin_addressable_dollars", "comp_competitor_dollars"],
        "reactivation_target_prior_spend x ICRate":
            ["retention_high_risk_spend x ICRate"],
    }
    by_basis = {i["basis"]: i["label"] for i in items}
    for i in items:
        shared = [by_basis[b] for b in overlaps.get(i["basis"], []) if b in by_basis]
        if shared:
            i["overlaps_with"] = shared

    # Revenue items first, by dollars; then at-risk, deposits, counts. Units
    # differ across kinds, so they never compete on the same scale.
    kind_order = {"revenue": 0, "at risk": 1, "deposits": 2, "count": 3}
    items.sort(key=lambda r: (kind_order.get(r["kind"], 9), -r["value"]))
    if not items:
        warn("synthesis: no priced opportunities available")
    return items


# ---------------------------------------------------------------------------
# 4. branch scorecard
# ---------------------------------------------------------------------------

def _branch_scorecard(m: dict) -> tuple[list[str], list[list]]:
    take = {r[0]: r for r in (m.get("take_branch") or [])}          # name, cards, elig, rate
    rege = {r[0]: r for r in (m.get("rege_branch") or [])}          # name, in, pool, pct
    value = {r["group"]: r for r in (m.get("value_by_branch") or [])}
    attr = {r[0]: r for r in (m.get("attrition_by_branch") or [])}  # name, n, closed, rate
    fy = {r[0]: r for r in (m.get("attrition_first_year_by_branch") or [])}
    if not take:
        return [], []
    rows = []
    for name, t in take.items():
        rows.append([
            name, int(t[2]), float(t[3]),
            float(rege[name][3]) if name in rege else None,
            float(value[name]["value_per_acct"]) if name in value else None,
            float(attr[name][3]) if name in attr else None,
            float(fy[name][3]) if name in fy else None,
        ])
    rows.sort(key=lambda r: -r[1])
    columns = ["branch", "eligible", "take_rate", "rege_pct", "value_per_acct",
               "closure_rate", "first_year_close_pct"]
    return columns, rows


# ---------------------------------------------------------------------------
# 5. RAG scorecard -- every judgement against the metric's own comparator
# ---------------------------------------------------------------------------

def _rag(delta, higher_is_better=True, tol=RAG_TOLERANCE_PP) -> str:
    if delta is None:
        return "grey"
    d = delta if higher_is_better else -delta
    return "green" if d > tol else ("red" if d < -tol else "amber")


def _scorecard(m: dict) -> list[list]:
    rows = []

    def row(metric, value, unit, comparator, delta, higher_is_better=True, tol=RAG_TOLERANCE_PP):
        if value is None:
            return
        rows.append([metric, value, unit, comparator,
                     None if delta is None else round(delta, 1),
                     _rag(delta, higher_is_better, tol)])

    row("Take rate, last 12 months", _num(m, "dctr_l12m"), "%",
        f"vs historical {_num(m, 'dctr_overall')}%", _num(m, "dctr_l12m_vs_hist_pp"))
    row("Reg E opt-in, last 12 months", _num(m, "rege_l12m_pct"), "%",
        f"vs historical {_num(m, 'rege_pct')}%", _num(m, "rege_l12m_vs_hist_pp"))
    lr, mr = _num(m, "latest_resprate"), _num(m, "resprate_mean")
    row("Latest response rate", lr, "%", f"vs mean of all waves {mr}%",
        None if lr is None or mr is None else lr - mr)
    row("Responder spend gain vs control", _num(m, "ba_lift_net"), "$/mo",
        "difference-in-differences", _num(m, "ba_lift_net"), tol=0)
    up, down = _num(m, "mig_up_pct"), _num(m, "mig_down_pct")
    row("Cardholders moving up a swipe tier", up, "%", f"vs {down}% moving down",
        None if up is None or down is None else up - down)
    row("Responder up-tier advantage", _num(m, "mig_responder_up_advantage_pp"), "pts",
        "vs mailed non-responders", _num(m, "mig_responder_up_advantage_pp"))
    row("Responders close less than control", _num(m, "attrition_mailer_lift_pp"), "pts",
        "closure rate gap", _num(m, "attrition_mailer_lift_pp"))
    slope = _num(m, "attrition_velocity_slope")
    row("Monthly closures, trend", slope, "closures/mo",
        "slope over the window", slope, higher_is_better=False, tol=0)
    row("Program share of existing-account activations", _num(m, "activation_program_pct"),
        "%", "of first swipes on accounts that existed a year ago", None)
    # TXN rows, present when a transaction run preceded this one.
    row("Transacting personal accounts leaking to external products",
        _num(m, "fin_leaking_pct"), "%",
        f"responders {_num(m, 'fin_responder_leak_gap_pp'):+.1f} pts vs control"
        if _num(m, "fin_responder_leak_gap_pp") is not None else "no responder comparator", None)
    row("Transacting personal accounts paying a named competitor",
        _num(m, "comp_with_competitor_pct"), "%",
        f"responders {_num(m, 'comp_responder_gap_pp'):+.1f} pts vs control"
        if _num(m, "comp_responder_gap_pp") is not None else "no responder comparator", None)
    mom = m.get("comp_momentum") or []
    if mom:
        net = sum(r[3] for r in mom)
        row("Competitor relationships, net new vs stopped", net, "relationships",
            "new minus stopped across named institutions", net,
            higher_is_better=False, tol=0)
    return rows


# ---------------------------------------------------------------------------
# 6. talking points
# ---------------------------------------------------------------------------

def _talking_points(m: dict, opps: list[dict]) -> list[str]:
    points = []
    for o in [o for o in opps if o["kind"] == "revenue"][:TALKING_POINTS]:
        points.append(f"{o['label']}: {o['n']:,} accounts, {_money(o['value'])} a year.")
    adv = _num(m, "mig_responder_up_advantage_pp")
    if adv is not None and adv > 0:
        groups = {r[0]: r for r in (m.get("mig_by_group") or [])}
        r, c = groups.get("Responder"), groups.get("Mailed non-responder")
        if r and c:
            points.append(f"Responders moved up a swipe tier at {r[2]:.0f}% against "
                          f"{c[2]:.0f}% for mailed non-responders.")
    share = _num(m, "responder_spend_share_pct")
    base = _num(m, "responder_share_of_eligible_pct")
    if share and base:
        points.append(f"Responders are {base:.0f}% of eligible accounts and "
                      f"{share:.0f}% of the spend.")
    pen = _num(m, "comp_with_competitor_pct")
    inst = m.get("comp_institutions") or []
    if pen and inst:
        blab = m.get("comp_base_label", "transacting personal accounts")
        points.append(f"{pen:.0f}% of {blab} pay a named competitor; "
                      f"{inst[0][0]} alone reaches {inst[0][2]:,} accounts.")
    return points[:TALKING_POINTS + 2]


# ---------------------------------------------------------------------------

def compute(metrics: dict, config: dict, warn) -> dict:
    out: dict[str, Any] = {}
    cascade = _cascade(metrics)
    if cascade:
        out["syn_cascade"] = cascade
    out.update(_whatif(metrics))
    opps = _opportunities(metrics, warn)
    if opps:
        out["syn_opportunities"] = opps
        out["syn_top_opportunity"] = opps[0]
        out["syn_opportunities_note"] = ("items overlap (a leak is a subset of the "
                                         "cards-without pool); not additive")
    cols, rows = _branch_scorecard(metrics)
    if rows:
        out["syn_branch_columns"] = cols
        out["syn_branch_scorecard"] = rows
    card = _scorecard(metrics)
    if card:
        out["syn_scorecard"] = card
        out["syn_scorecard_counts"] = {c: sum(1 for r in card if r[5] == c)
                                       for c in ("green", "amber", "red", "grey")}
    points = _talking_points(metrics, opps)
    if points:
        out["syn_talking_points"] = points
    return out
