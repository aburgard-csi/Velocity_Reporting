# Ported from ARS v5 02-Scripts/ars/deck/txn_compete.py at a491b5c (James Gilmore); logic unchanged.
"""Competition and deposit-flight slides for the transaction chapter."""
from __future__ import annotations

from . import charts, charts_story as CS, charts_txn as CT, labels
from .txn_common import RAIL_EDGE, money

LOCAL_TIER = "Local Bank / CU"
ECOSYSTEM_TIER = "Payment Ecosystem"


def _leads(inst, row):
    """The product categories in which `row` reaches the most accounts of any named competitor."""
    out = []
    for cat in (row[7] or []):
        if cat == "Transfer / other":
            continue
        best = max((r for r in inst if cat in (r[7] or [])), key=lambda r: r[2], default=None)
        if best is row:
            out.append(cat)
    return out


def who_competes(h, t, base):
    """RPE: the one competitor-penetration slide (Sheila's 1798 slide review, 2026-10-30, groups F
    and G). v5 said "20% pay a named competitor" three ways ("Who competes for our members", "Banks
    against the ecosystems", "How many competitors each account uses") and named the top competitor
    twice more ("Which competitors to work first", "Who leads each product"). Here: v5's penetration
    against dollars quadrant (which_to_work_first's chart) with the reach, the multi-banked count,
    the payment-app share and the top competitor on the rail."""
    inst = t.get("comp_institutions") or []
    if not inst:
        return None
    total = t.get("comp_accounts_total") or 0
    lead = inst[0]
    s, top = h["slide"]((
        f"{t.get('comp_with_competitor_pct', 0):.0f}% of {base} pay a named "
        f"competitor — {lead[0]} reaches {lead[2]:,} and takes {money(lead[5])} a year",
        f"{t.get('comp_institutions_n', 0)} institutions seen; penetration against dollars a "
        f"year, bubble is accounts; payment apps counted apart, never added"),
        "Who competes for our members")
    items = [("With a competitor", f"{t.get('comp_with_competitor', 0):,}",
              f"of {total:,} {base}"),
             ("Two or more", f"{t.get('comp_multi_banked', 0):,}",
              "named competitors"),
             ("Per year", money(t.get("comp_competitor_dollars")),
              "to named competitors")]
    eco_n = t.get("comp_ecosystem_accounts") or 0
    if eco_n and total:
        items.append(("In a payment app", f"{eco_n / total * 100:.0f}%",
                      f"{eco_n:,} accounts, counted apart"))
    led = _leads(inst, lead)
    items.append(("Top competitor", labels.clip(lead[0], 18),
                  f"{lead[3]:.0f}% of accounts" + (f", leads {led[0].lower()}" if led else "")))
    right = h["rail"](s, items[:5], top=top)
    if len(inst) >= 3:
        rows = [[labels.clip(r[0], 20), r[2], r[3], r[5]] for r in inst[:10]]
        path = h["chart"]("comp_quadrant", charts.branch_quadrant, rows,
                          quads=("monitor", "act now", "watch", "defend"),
                          bubble_label="bubble = accounts reached",
                          xlabel="penetration — % of accounts",
                          ylabel="Spend outside the client, a year", yfmt=money)
    else:
        # too few for a quadrant: v5's reach and momentum bars. comp_institutions is already cut
        # to TOP_INSTITUTIONS, so the note counts every institution that MATCHED
        net = {r[0]: r[3] for r in (t.get("comp_momentum") or [])}
        rows = [[labels.clip(r[0], 22), r[2], f"{money(r[6])}/acct", net.get(r[0]),
                 r[1] == LOCAL_TIER] for r in inst[:9]]
        matched = t.get("comp_institutions_n") or len(inst)
        note = labels.coverage_note(len(rows), matched, "institutions") or ""
        path = h["chart"]("comp_momentum_bars", charts.momentum_bars, rows,
                          footnote=note, momentum_unit="")
    if path:
        h["chart_left"](s, path, top, right)


def the_local_field(h, t, base):
    """Every configured local competitor, seen or not, and the review queue
    of bank-looking names nothing matched. The 19 August chapter carried a
    local tile on the rail; the 27 August rewrite dropped it (#245). Locals
    never make the top nine by accounts against the nationals, so without
    this slide the bank across the street is invisible."""
    loc = t.get("comp_local") or {}
    configured = loc.get("configured") or []
    if not configured:
        return ("The local field (no LocalCompetitors configured for this "
                "client -- the review queue is where to look for names)")
    seen = loc.get("institutions") or []
    seen_names = {r[0] for r in seen}
    missing = [n for n in configured if n not in seen_names]
    head = (f"{len(seen)} of {len(configured)} named local institutions seen "
            f"-- {loc.get('accounts', 0):,} {base} pay one, "
            f"{money(loc.get('dollars', 0))} a year")
    # RPE: the subtitle no longer lists every unseen name (88 words on 1798; Sheila's slide
    # review, 2026-10-30: too dense); it counts them and names the first
    if len(missing) == 1:
        sub = (f"{labels.clip(missing[0], 32)} is configured but not seen; not paid here, "
               f"or spelled another way in the file")
    elif missing:
        sub = (f"{len(missing)} configured names not seen, {labels.clip(missing[0], 32)} among "
               f"them; not paid here, or spelled another way in the file")
    else:
        sub = "every configured name was seen in the window"
    s, top = h["slide"]((head, sub), "The local field")
    items = [("Named locally", f"{len(configured)}", "in the client config"),
             ("Seen", f"{len(seen)}", f"{loc.get('pct', 0):.1f}% of {base}"),
             ("Review queue", money(t.get("comp_review_queue_dollars", 0)),
              "bank-looking, unmatched")]
    for core, txns, dollars in (t.get("comp_review_queue") or [])[:1]:
        items.append((labels.clip(core, 20), money(dollars), f"{txns:,} txns, top of the queue"))
    right = h["rail"](s, items, top=top)
    if seen:
        # the same horizontal form the 19 August slide used: accounts and
        # dollars per institution, local names in orange. Imported here
        # because txn_slides imports this module.
        from .txn_slides import institution_bars
        rows = [[r[0], LOCAL_TIER, r[1], None, None, r[2], None, r[3] or []]
                for r in seen]
        path = h["chart"]("comp_local_bars", institution_bars, rows)
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
        "penetration against Spend outside the client, bubble is accounts; the lit "
        "quadrant is broad reach and deep spend at once"),
        "Which competitors to work first")
    rows = [[labels.clip(r[0], 20), r[2], r[3], r[5]] for r in inst[:10]]
    path = h["chart"]("comp_quadrant", charts.branch_quadrant, rows,
                      quads=("monitor", "act now", "watch", "defend"),
                      bubble_label="bubble = accounts reached",
                      xlabel="penetration — % of accounts",
                      ylabel="Spend outside the client, a year", yfmt=money)
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def filed_growth_slide(h, t, base):
    """Slide 3 of the competitor chapter: what each named competitor filed with its
    regulator, latest quarter against a year earlier, beside the Spend at it."""
    rows = t.get("comp_filed") or []
    if not rows:
        return "Filed growth (no competitor resolved to a regulator record)"
    cols = t.get("comp_filed_columns") or []
    ix = {c: i for i, c in enumerate(cols)}
    top = rows[:10]
    lead = top[0]
    name = labels.clip(lead[ix["institution"]], 28)
    pct = lead[ix["growth_pct"]]
    verb = "grew" if pct >= 0 else "shrank"
    head = f"{name} {verb} {abs(pct):.1f}% in filed balances while taking {lead[ix['pct_of_accounts']]:.1f}% of your accounts"
    sub = (f"filed balances, latest quarter {lead[ix['latest_date']]} against a year earlier, "
           f"from FDIC and NCUA filings; Spend from your transaction file, top {len(top)} by dollars")
    s, top_y = h["slide"]((head, sub), "Filed growth")
    # momentum_bars rows: [name, count, depth_label, momentum_pct, marked].
    # The bar is the accounts it reaches here, the text column its filed
    # balance, the movement column its filed growth (red is growth). The
    # branch first handed the form two-field rows, which the chapter
    # harness accepted and the chart could not unpack (#255's lesson).
    chart_rows = [[labels.clip(r[ix["institution"]], 20), r[ix["accounts"]],
                   money(r[ix["deposits_latest"]]), r[ix["growth_pct"]], False]
                  for r in top]
    path = h["chart"]("comp_filed_growth", charts.momentum_bars, chart_rows,
                      footnote="bar: accounts here; movement: filed balances, "
                               "latest quarter against a year earlier",
                      headers=["institution · accounts here", "filed balances",
                               "filed growth"])
    if path:
        h["chart_left"](s, path, top_y, RAIL_EDGE)
    return None


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
    # comp_institutions carries each institution's whole-book reach and dollars only, never a
    # per-category figure, so the slide names the institution and prints no count (issue #87)
    s, top = h["slide"]((
        f"{inst0[0]} is the largest named competitor that also carries {cat0.lower()}",
        "the largest named competitor in each product category, ranked by its reach across "
        "the whole book; the data has no account count per category"),
        "Who leads each product")
    # The horizontal institution form: one bar per product, the leader's
    # accounts, dollars and name beside it, local names in orange. The
    # branch form this slide first used reads a rate the row never carried,
    # and its portfolio band means nothing here (#245, the 1776 rerun).
    from .txn_slides import leader_names
    rows = [[c, r[1], r[2], None, None, r[5], None, [r[0]]]
            for c, r in ranked]
    path = h["chart"]("comp_leaders", leader_names, rows)
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
        return None
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
                      ylabel="competitor dollars per account", yfmt=money)
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


# ---------------------------------------------------------------------------
# the competition family (legacy 14-35, 66-67; #258)
# ---------------------------------------------------------------------------

def who_owns_the_relationship(h, t, base):
    """Legacy 17_engagement_depth: of an account's transactions, how many go
    to each competitor. Heavy is half or more; that is the account the
    competitor owns."""
    rows = t.get("comp_engagement") or []
    if not rows:
        return "Who owns the relationship (no comp_engagement)"
    heavy_n = t.get("comp_engagement_heavy_n") or 0
    worst = max(rows, key=lambda r: r[4])
    s, top = h["slide"]((
        f"{heavy_n:,} {base} send half or more of their transactions to one competitor",
        f"{worst[0]} holds the most of them ({worst[4]:,}); the average competitor "
        f"relationship takes {t.get('comp_engagement_avg_share_pct', 0):.0f}% of an "
        f"account's transactions"),
        "Who owns the relationship")
    items = [
        ("Heavy relationships", f"{heavy_n:,}", "half or more of their transactions"),
        ("Average share", f"{t.get('comp_engagement_avg_share_pct', 0):.0f}%", "per competitor relationship"),
        ("Most heavy users", labels.clip(worst[0], 18), f"{worst[4]:,} accounts"),
    ]
    # RPE: the dollar view of the same question, from "How much of the wallet has left", as one
    # tile (Sheila's 1798 slide review, 2026-10-30, group H: two concentration slides to one)
    wallet = t.get("comp_wallet_by_institution") or []
    if wallet:
        w = max(wallet, key=lambda r: r[5])
        items.append(("Over half their spend", labels.clip(w[0], 18),
                      f"{w[5]:.0f}% of its {w[1]:,} accounts"))
    right = h["rail"](s, items, top=top)
    bands = [("Light (under 20%)", charts.TINT), ("Moderate (20-50%)", charts.ORANGE),
             ("Heavy (50% or more)", charts.RED)]
    chart_rows = [[labels.clip(r[0], 20), r[2], r[3], r[4]] for r in rows]
    path = h["chart"]("comp_engagement", CT.band_stack, chart_rows, bands,
                      note="share of the account's own transactions; accounts per band")
    if path:
        h["chart_left"](s, path, top, right)


def how_much_of_the_wallet_has_left(h, t, base):
    """Legacy 20-22: per competitor, the accounts whose dollars there pass a
    quarter and a half of their own spend."""
    rows = t.get("comp_wallet_by_institution") or []
    floor = t.get("comp_wallet_min_accounts") or 0
    if not rows:
        return f"How much of the wallet has left (no institution reaches {floor} accounts)"
    worst = max(rows, key=lambda r: r[5])
    exposed = t.get("comp_wallet_high_exposure_n") or 0
    s, top = h["slide"]((
        f"{worst[0]}: {worst[5]:.0f}% of its {worst[1]:,} accounts send it over half their spend",
        f"{exposed} competitor{'s' if exposed != 1 else ''} with more than a fifth of their "
        f"accounts in the heavy band; institutions under {floor} accounts not shown"),
        "How much of the wallet has left")
    right = h["rail"](s, [
        ("Highest exposure", labels.clip(worst[0], 18), f"{worst[5]:.0f}% heavy"),
        ("Over a fifth heavy", f"{exposed}", "competitors"),
        ("Shown", f"{len(rows)}", f"with {floor}+ accounts"),
    ], top=top)
    bands = [("CU-focused (under 25%)", charts.TINT), ("Balanced (25-50%)", charts.ORANGE),
             ("Heavy (over 50%)", charts.RED)]
    chart_rows = [[labels.clip(r[0], 20), r[2], r[3], r[4]] for r in rows]
    path = h["chart"]("comp_wallet_bands", CT.band_stack, chart_rows, bands,
                      note="competitor dollars over the account's own; accounts per band")
    if path:
        h["chart_left"](s, path, top, right)


def is_the_competitor_money_still_moving(h, t, base):
    """Legacy 27_recency_analysis: days since each account-competitor pair
    last transacted. A pair dormant for six months may already be back."""
    bands = t.get("comp_recency_bands") or []
    pairs = t.get("comp_recency_pairs") or 0
    if not pairs:
        return "Is the competitor money still moving (no account-competitor pairs)"
    active = t.get("comp_recency_active_pct") or 0
    dormant = t.get("comp_recency_dormant_pairs") or 0
    head = (f"{active:.0f}% of competitor relationships moved money in the last 30 days"
            if active >= 50 else
            f"Only {active:.0f}% of competitor relationships moved money in the last 30 days")
    s, top = h["slide"]((head,
        f"{pairs:,} account-competitor pairs; {dormant:,} quiet for six months or more, "
        f"which is where consolidation back to you may already have happened"),
        "Is the competitor money still moving")
    right = h["rail"](s, [
        ("Active, 30 days", f"{active:.0f}%", "of pairs"),
        ("Dormant, 180+ days", f"{dormant:,}", "pairs"),
        ("Pairs", f"{pairs:,}", "account x competitor"),
    ], top=top)
    path = h["chart"]("comp_recency", charts.tier_bars, [[r[0], r[1]] for r in bands],
                      label="pairs")
    if path:
        h["chart_left"](s, path, top, right)


def how_many_competitors_each_account_uses(h, t, base):
    """Legacy 35_competitor_count_distribution: breadth per account, and the
    share of the book that touches no competitor at all."""
    bands = t.get("comp_breadth_bands") or []
    if not bands or not any(r[1] for r in bands):
        return "How many competitors each account uses (no accounts with a competitor)"
    none_n, none_pct = t.get("comp_breadth_no_competitor") or 0, t.get("comp_breadth_no_competitor_pct") or 0
    shopping, deep = t.get("comp_breadth_shopping") or 0, t.get("comp_breadth_deep") or 0
    s, top = h["slide"]((
        f"{none_pct:.0f}% of {base} pay no named competitor; {shopping:,} pay two or more",
        f"banks and lenders only, payment apps apart; {deep:,} accounts use six or more"),
        "How many competitors each account uses")
    right = h["rail"](s, [
        ("No competitor", f"{none_n:,}", f"{none_pct:.0f}% of {base}"),
        ("Two or more", f"{shopping:,}", "actively shopping"),
        ("Six or more", f"{deep:,}", "deeply diversified"),
    ], top=top)
    path = h["chart"]("comp_breadth", charts.tier_bars, [[r[0], r[1]] for r in bands],
                      label="accounts")
    if path:
        h["chart_left"](s, path, top, right)


def winback_targets(h, t, base):
    """Legacy 16_opportunity: competitors whose volume fell, last three months
    against the three before, with enough accounts to be a campaign."""
    rows = t.get("comp_winback") or []
    floor = t.get("comp_winback_min_accounts") or 0
    if not rows:
        return (f"Winback targets (no competitor with {floor}+ accounts lost volume, "
                f"{t.get('comp_winback_window', 'window')})")
    accounts = t.get("comp_winback_accounts") or 0
    lead = rows[0]
    s, top = h["slide"]((
        f"{len(rows)} competitors are losing ground with {accounts:,} of {base} between them",
        f"{lead[0]} first: {lead[1]:,} accounts, transactions {lead[4]:+.0f}% "
        f"({t.get('comp_winback_window', '')}); minimum {floor} accounts"),
        "Winback targets")
    right = h["rail"](s, [
        ("Accounts to call", f"{accounts:,}", "across the targets"),
        ("Biggest fall", labels.clip(lead[0], 18), f"{lead[4]:+.0f}% transactions"),
        ("Window", t.get("comp_winback_window", ""), "recent against prior"),
    ], top=top)
    header = ["Competitor", "Accounts and volume", "Change"]
    chart_rows = [[labels.clip(r[0], 22), f"{r[1]:,} accounts · {r[2]:,} vs {r[3]:,} txns",
                   f"{r[4]:+.1f}%", i < 3] for i, r in enumerate(rows)]
    path = h["chart"]("comp_winback", CS.worklist, header, chart_rows)
    if path:
        h["chart_left"](s, path, top, right)


def depth_against_growth(h, t, base):
    """Legacy 14_engagement_scatter: transactions per account against growth,
    with the medians as the crosshairs. Deep and growing is the threat."""
    rows = t.get("comp_depth_growth") or []
    if len(rows) < 3:
        return "Depth against growth (fewer than three institutions)"
    med_d = sorted(r[2] for r in rows)[len(rows) // 2]
    med_g = sorted(r[3] for r in rows)[len(rows) // 2]
    hot = [r for r in rows if r[2] > med_d and r[3] > med_g]
    head = (f"{hot[0][0]} is deep and growing: {hot[0][2]:.1f} transactions an account, "
            f"{hot[0][3]:+.0f}% on the quarter" if hot else
            "No competitor is both deep in the account and growing this quarter")
    s, top = h["slide"]((head,
        "transactions per account against dollars this quarter over last; bubble is accounts"),
        "Depth against growth")
    chart_rows = [[labels.clip(r[0], 20), r[1], r[2], r[3]] for r in rows]
    path = h["chart"]("comp_depth_growth", charts.branch_quadrant, chart_rows,
                      bubble_label="bubble = accounts reached",
                      xlabel="transactions per account", ylabel="growth, last 3 months vs prior, %")
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def where_the_dollars_go(h, t, base):
    """Legacy 31_spend_ranking: follow the money. Institutions by dollars,
    where the chapter's opening slide ranked them by accounts."""
    inst = t.get("comp_institutions") or []
    if not inst:
        return "Where the dollars go (no comp_institutions)"
    ranked = sorted(inst, key=lambda r: -r[5])[:15]
    total = float(t.get("comp_competitor_dollars") or sum(r[5] for r in inst)) or 1.0
    top3 = sum(r[5] for r in ranked[:3])
    months = t.get("txn_months_covered") or 12
    s, top = h["slide"]((
        f"The top three take {money(top3)} a year, {top3 / total * 100:.0f}% of every dollar "
        f"paid to a named competitor",
        f"{ranked[0][0]} leads with {money(ranked[0][5])}; {len(ranked)} institutions shown "
        f"of {t.get('comp_institutions_n', len(inst))} seen"),
        "Where the dollars go")
    right = h["rail"](s, [
        ("Top three", money(top3), f"{top3 / total * 100:.0f}% of competitor dollars"),
        ("Run rate", money(top3 / months), "a month, top three"),
        ("All named", money(total), "a year"),
    ], top=top)
    path = h["chart"]("comp_dollars", charts.value_waterfall,
                      [[labels.clip(r[0], 22), r[5]] for r in ranked])
    if path:
        h["chart_left"](s, path, top, right)


def the_payment_ecosystems_ranked(h, t, base):
    """Legacy 33_non_bank_threats: the wallets, P2P and BNPL services by
    members, apart from the banks. Not competitors; replacing a banking
    function all the same."""
    eco = t.get("comp_ecosystems") or []
    if not eco:
        return "The payment ecosystems, ranked (no ecosystem rows)"
    n = t.get("comp_ecosystem_accounts") or 0
    total = t.get("comp_accounts_total") or 0
    # RPE: the one Cash App slide, its flow split from the financial products (Sheila's 1798 slide
    # review, 2026-10-30, group B). Cash App showed as $78.1M (fin_p2p), $78.3M (card merchants) and
    # $78.3M here, beside a $49.6M financial-product total it is not part of. The figure is this
    # one, comp_ecosystems; the buy-now-pay-later services ARE financial products, counted in that
    # total, and are coloured apart (their dollars here are matched by service name, so they are not the leakage category total).
    bnpl = {str(r[0]).upper() for r in ((t.get("comp_bnpl") or {}).get("providers") or [])}
    kind = lambda name: "bnpl" if str(name).upper() in bnpl else "p2p"
    p2p_d = sum(r[3] for r in eco if kind(r[0]) == "p2p")
    bnpl_d = sum(r[3] for r in eco if kind(r[0]) == "bnpl")
    lead = eco[0]
    lead_is_p2p = kind(lead[0]) == "p2p"
    s, top = h["slide"]((
        f"{n / total * 100 if total else 0:.0f}% of {base} run money through a payment app; "
        f"{lead[0]} reaches {lead[1]:,} and moves {money(lead[3])} a year",
        (f"{lead[0]} is P2P and card flow, not a financial product: it is not in the "
         f"{money(t.get('fin_leakage_dollars'))} paid to outside financial products"
         if lead_is_p2p and t.get("fin_leakage_dollars") else
         f"{len(eco)} services seen; counted apart from competitors and never added to them")),
        "The payment ecosystems, ranked")
    items = [("In a payment app", f"{n:,}", f"of {total:,} {base}"),
             ("P2P and wallets", money(p2p_d), "a year, not financial products")]
    if bnpl_d:
        items.append(("Buy now, pay later", money(bnpl_d),
                      "a year; a financial product"))
    items.append(("Leading service", labels.clip(lead[0], 18), f"{lead[1]:,} accounts"))
    right = h["rail"](s, items, top=top)
    rows = [[labels.clip(r[0], 20), r[3], r[1], kind(r[0])] for r in eco[:9]]
    kinds = {"p2p": ("P2P and wallets", charts.NAVY),
             "bnpl": ("Buy now, pay later", charts.ORANGE)}
    path = h["chart"]("comp_eco_ranked", CT.kind_bars, rows, kinds,
                      note=labels.coverage_note(len(rows), len(eco), "services") or "")
    if path:
        h["chart_left"](s, path, top, right)


def buy_now_pay_later(h, t, base):
    """Legacy 66-67: the BNPL providers, the reach, the dollars per account a
    month. Ten percent reach is the signal for a card or loan campaign."""
    b = t.get("comp_bnpl") or {}
    providers = b.get("providers") or []
    if not providers:
        return "Buy now, pay later (no BNPL provider seen)"
    pct = b.get("pct") or 0
    signal = pct >= 10
    s, top = h["slide"]((
        f"{pct:.0f}% of {base} carry buy-now-pay-later balances, "
        f"{money(b.get('per_acct_month'))} an account a month",
        (f"{providers[0][0]} leads; at {pct:.0f}% reach that is revolving credit displaced "
         f"from your own cards and loans" if signal else
         f"{providers[0][0]} leads; under 10% reach, worth watching rather than acting on")),
        "Buy now, pay later")
    right = h["rail"](s, [
        ("Reach", f"{pct:.0f}%", f"{b.get('accounts', 0):,} accounts"),
        ("Dollars", money(b.get("dollars")), f"over {b.get('months', 0)} months"),
        ("Per account", money(b.get("per_acct_month")), "a month"),
    ], top=top)
    blocks = [[labels.clip(r[0], 16), f"{r[1]:,}", f"{r[2]:.1f}% of {base} · {money(r[3])}", None]
              for r in providers[:5]]
    path = h["chart"]("comp_bnpl", charts.category_blocks, blocks,
                      note="accounts per provider; a member can use more than one")
    if path:
        h["chart_left"](s, path, top, right)
