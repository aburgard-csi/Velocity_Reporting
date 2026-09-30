"""Competition and deposit-flight slides for the transaction chapter."""
from __future__ import annotations

from . import charts, charts_txn as CT, labels
from .txn_common import RAIL_EDGE, money

LOCAL_TIER = "Local Bank / CU"
ECOSYSTEM_TIER = "Payment Ecosystem"


def who_competes(h, t, base):
    """momentum_bars -- reach, depth and momentum on one row each. Built and
    tested since the v4 forms landed; never called by a slide until now."""
    inst = t.get("comp_institutions") or []
    if not inst:
        return "Who competes for our members (no comp_institutions)"
    net = {r[0]: r[3] for r in (t.get("comp_momentum") or [])}
    s, top = h["slide"]((
        f"{t.get('comp_with_competitor_pct', 0):.0f}% of {base} pay a named "
        f"competitor — {inst[0][0]} reaches {inst[0][2]:,}",
        f"{t.get('comp_institutions_n', 0)} institutions seen; "
        f"{t.get('comp_multi_banked_pct', 0):.0f}% of the accounts with a "
        f"competitor deal with two or more; payment apps reported apart"),
        "Who competes for our members")
    items = [("With a competitor", f"{t.get('comp_with_competitor', 0):,}",
              f"of {t.get('comp_accounts_total', 0):,} {base}"),
             ("Multi-banked", f"{t.get('comp_multi_banked', 0):,}",
              "two or more named competitors"),
             ("Per year", money(t.get("comp_competitor_dollars")),
              "to named competitors")]
    ar = t.get("comp_at_risk") or {}
    if ar.get("accounts"):
        items.append(("Inactive, with competitor",
                      f"{ar['with_competitor']:,}",
                      f"{ar['pct']:.0f}% of recently inactive"))
    right = h["rail"](s, items[:5], top=top)
    rows = [[labels.clip(r[0], 22), r[2], f"${r[6]}/acct", net.get(r[0]),
             r[1] == LOCAL_TIER] for r in inst[:9]]
    # comp_institutions is itself already cut to TOP_INSTITUTIONS, so the
    # coverage note has to count against every institution that MATCHED, not
    # against the truncated list -- otherwise a book with 82 configured
    # competitors reads as "9 of 25" and the second cut is invisible.
    matched = t.get("comp_institutions_n") or len(inst)
    note = labels.coverage_note(len(rows), matched, "institutions") or ""
    path = h["chart"]("comp_momentum_bars", charts.momentum_bars, rows,
                      footnote=note)
    if path:
        h["chart_left"](s, path, top, right)


def which_to_work_first(h, t, base):
    """The legacy threat quadrant, restored: 13_threat_quadrant and
    32_material_threats. Every axis is a column comp_institutions carries."""
    inst = t.get("comp_institutions") or []
    if len(inst) < 3:
        return "Which competitors to work first (too few institutions)"
    med_pen = sorted(r[3] for r in inst)[len(inst) // 2]
    med_dol = sorted(r[5] for r in inst)[len(inst) // 2]
    hot = [r for r in inst if r[3] > med_pen and r[5] > med_dol]
    head = (f"{hot[0][0]} sits top right — {hot[0][3]:.0f}% penetration and "
            f"{money(hot[0][5])} a year" if hot else
            "Reach against dollars, with the medians as the crosshairs")
    s, top = h["slide"]((head,
        "penetration against external dollars, bubble is accounts; the lit "
        "quadrant is broad reach and deep spend at once"),
        "Which competitors to work first")
    rows = [[labels.clip(r[0], 20), r[2], r[3], r[5]] for r in inst[:10]]
    path = h["chart"]("comp_quadrant", charts.branch_quadrant, rows,
                      quads=("monitor", "act now", "watch", "defend"),
                      bubble_label="bubble = accounts reached",
                      xlabel="penetration — % of accounts",
                      ylabel="external dollars a year")
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def where_the_field_sits(h, t, base):
    tier = t.get("comp_by_tier") or []
    if not tier:
        return "Where the field sits (no comp_by_tier)"
    s, top = h["slide"]((
        f"{t.get('comp_institutions_n', 0)} institutions seen, across "
        f"{len(tier)} kinds of competitor",
        "nationals against card issuers, digitals, captives, mortgage and "
        "brokerage — the shape of the threat, not its names"),
        "Where the field sits")
    rows = [[labels.clip(r[0], 26), r[2]] for r in tier]
    path = h["chart"]("comp_tiers", charts.donut, rows,
                      center_label="institutions",
                      center_value=str(t.get("comp_institutions_n", 0)))
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def gaining_and_losing(h, t, base):
    mom = t.get("comp_momentum") or []
    if not mom:
        return "Gaining and losing (no comp_momentum)"
    rows = sorted(mom, key=lambda r: -r[3])[:8]
    s, top = h["slide"]((
        f"{rows[0][0]} added {rows[0][1]:,} relationships in 90 days and lost "
        f"{rows[0][2]:,}",
        "new against stopped per institution — who is taking ground and who "
        "is giving it up"), "Gaining and losing")
    path = h["chart"]("comp_tornado", CT.tornado,
                      [[labels.clip(r[0], 22), r[2], r[1]] for r in rows])
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def who_leads_each_product(h, t, base):
    """Restores legacy 30_category_leaders. comp_institutions[7] is the
    product list; inverted it names who leads each product."""
    inst = t.get("comp_institutions") or []
    leaders: dict = {}
    for r in inst:
        for cat in (r[7] or []):
            best = leaders.get(cat)
            if best is None or r[2] > best[2]:
                leaders[cat] = r
    ranked = sorted(leaders.items(), key=lambda kv: -kv[1][2])[:8]
    if not ranked:
        return "Who leads each product (no product mix on comp_institutions)"
    cat0, inst0 = ranked[0]
    s, top = h["slide"]((
        f"{inst0[0]} leads {cat0.lower()} with {inst0[2]:,} accounts",
        "the named competitor reaching the most accounts in each product "
        "category — where the relationship is actually lost"),
        "Who leads each product")
    # tier_bars, not branch_bars: v5 called branch_bars with rows it cannot read (and a
    # keyword the chart helper collides with), so this slide never drew its chart
    # (found on the fixture, 2026-09-30). The leader and its dollars ride the tick label.
    rows = [[f"{labels.clip(c, 18)}\n{labels.clip(r[0], 18)} · {money(r[5])}", r[2]]
            for c, r in ranked]
    path = h["chart"]("comp_leaders", charts.tier_bars, rows, value_idx=1,
                      share=False, fmt="{:,.0f}", label="accounts")
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def banks_against_ecosystems(h, t, base):
    """Restores legacy 70_banking_vs_ecosystems and the 60-65 banks-only cut."""
    eco_n = t.get("comp_ecosystem_accounts") or 0
    bank_n = t.get("comp_with_competitor") or 0
    total = t.get("comp_accounts_total") or 0
    if not (total and (eco_n or bank_n)):
        return "Banks against the ecosystems (no competitor totals)"
    eco_d = t.get("comp_ecosystem_dollars") or 0
    bank_d = t.get("comp_competitor_dollars") or 0
    s, top = h["slide"]((
        f"{bank_n / total * 100:.0f}% of {base} pay a named bank; "
        f"{eco_n / total * 100:.0f}% are inside a payment ecosystem",
        "the two are counted separately and never added — a wallet is not a "
        "competitor, but it is replacing a banking function"),
        "Banks against the ecosystems")
    panels = [
        ("Named banks and lenders", "of accounts", bank_n / total * 100,
         [(f"{bank_n:,}", "accounts"), (money(bank_d), "a year")]),
        ("Payment ecosystems", "of accounts", eco_n / total * 100,
         [(f"{eco_n:,}", "accounts"), (money(eco_d), "a year")]),
    ]
    if eco_d + bank_d:
        panels.append(
            ("Per account", "ecosystem share of the two",
             eco_d / (eco_d + bank_d) * 100,
             [(money(bank_d // bank_n if bank_n else 0), "per bank acct"),
              (money(eco_d // eco_n if eco_n else 0), "per eco acct")]))
    path = h["chart"]("comp_eco", charts.split_panels, panels)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def where_the_outflow_goes(h, t, base):
    """flow_ribbons on the deposit-flight overlay -- the main-path slide that
    was a table."""
    dests = t.get("ovl_destinations") or []
    if not dests:
        return "Where the outflow goes (no ovl_destinations)"
    s, top = h["slide"]((
        f"{money(t.get('ovl_named_destination_deposits'))} of outflow has a "
        f"named destination — {t.get('ovl_named_destination_n', 0):,} "
        f"flight-risk accounts already pay it",
        f"flight risk = balance >= {money(t.get('ovl_flight_threshold'))} and "
        f"below its own average"), "Where the outflow goes")
    right = h["rail"](s, [
        ("Flight risk", f"{t.get('ovl_flight_n', 0):,}",
         f"{money(t.get('ovl_flight_deposits'))} deposits held"),
        ("Named destination", f"{t.get('ovl_named_destination_pct', 0):.0f}%",
         f"{t.get('ovl_named_destination_n', 0):,} accounts"),
        ("Already declining", money(t.get("ovl_named_destination_decline")),
         "below their own average balance")], top=top)
    source = {"count": f"{t.get('ovl_flight_n', 0):,}",
              "count_label": "flight-risk accounts",
              "held": f"{money(t.get('ovl_flight_deposits'))} held",
              "drain": f"{money(t.get('ovl_flight_decline'))} declining"}
    rows = [[labels.clip(r[0], 26),
             f"{r[1]:,} accounts · {money(r[2])} external", r[1]]
            for r in dests[:5]]
    note = labels.coverage_note(len(rows), len(dests), "destinations") or ""
    path = h["chart"]("ovl_flow", charts.flow_ribbons, source, rows,
                      footnote=note)
    if path:
        h["chart_left"](s, path, top, right)


def where_we_leak_by_branch(h, t, base):
    """Competition on the axis attrition already reports on.

    Both halves were computed for months and never shared an axis, so the
    branch table and the competitor table could not be read together.
    """
    rows = t.get("comp_by_branch") or []
    if len(rows) < 2:
        return "Where we leak by branch (fewer than two branch rows)"
    worst = rows[0]
    s, top = h["slide"]((
        f"{worst[0]} leaks hardest — {worst[3]:.0f}% of its accounts pay "
        f"a competitor",
        f"{money(worst[5])} an account a year across every account at the "
        f"branch, not just the ones already leaking; {worst[6]} takes the "
        f"most there"),
        "Where we leak, by branch")
    quad = [[labels.clip(r[0], 18), r[1], r[3], r[5]] for r in rows[:12]]
    path = h["chart"]("comp_branch_quadrant", charts.branch_quadrant, quad,
                      quads=("watch", "act now", "steady", "deep few"),
                      bubble_label="bubble = transacting accounts",
                      xlabel="accounts paying a competitor — %",
                      ylabel="competitor dollars per account")
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)
        h["rail"](s, [(r[0], f"{r[3]:.0f}%", money(r[5])) for r in rows[:5]],
                  top=top)


def lose_and_leak_together(h, t, base):
    """The question neither chapter could answer alone: is the branch we
    lose accounts at the branch we leak money at?"""
    rows = t.get("hot_by_branch") or []
    if len(rows) < 2:
        return "Lose and leak together (the two tables did not join)"
    rho = t.get("hot_rank_correlation")
    both = t.get("hot_both_above_median") or []

    if rho is not None and abs(rho) >= 0.4:
        direction = "the same branches" if rho > 0 else "different branches"
        head = (f"We lose accounts and leak money at {direction} "
                f"(rank correlation {rho:+.2f})")
    elif both:
        head = (f"{len(both)} branch(es) sit above the book on both closures "
                f"and leakage")
    else:
        head = "Closures against competitor leakage, branch by branch"

    sub = ("closures per account-year at risk against the share of accounts "
           "paying a competitor; both figures are the ARS and transaction "
           "chapters' own")
    if both:
        sub += f" — top right: {', '.join(both[:4])}"
    s, top = h["slide"]((head, sub), "Where we lose and where we leak")

    quad = [[labels.clip(r[0], 18), r[4], r[5], r[3]] for r in rows[:12]
            if r[3] is not None]
    path = h["chart"]("hot_quadrant", charts.branch_quadrant, quad,
                      quads=("leaking only", "losing and leaking",
                             "healthy", "losing only"),
                      bubble_label="bubble = transacting accounts",
                      xlabel="accounts paying a competitor — %",
                      ylabel="closures per account-year")
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)
        rail = [(r[0], f"{r[3]:.1f}/yr", f"{r[5]:.0f}% leak")
                for r in rows[:5] if r[3] is not None]
        if rail:
            h["rail"](s, rail, top=top)
