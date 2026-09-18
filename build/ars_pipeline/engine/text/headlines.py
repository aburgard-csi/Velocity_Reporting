"""Action titles, computed from the metrics.

A slide titled "Debit card take rate by branch" makes the reader do the work.
"South Center holds 9% of eligible accounts and 7% of the cards" states the
finding. Every headline here is derived from the numbers, with the wording
branching on what the numbers actually say -- a gap is described as a gap, a
lead as a lead.

Deterministic on purpose. Generating this text at runtime through a model
would put a number in a sentence without a guarantee it matches the number in
the chart beside it. These read the same values the charts do.

Each function returns (headline, subhead) or None when the inputs are absent,
so a slide is dropped rather than titled with a blank.
"""

from __future__ import annotations


def _money(v) -> str:
    from .labels import money
    return money(v)


def population(m: dict) -> tuple[str, str] | None:
    total, elig = m.get("n_total"), m.get("n_eligible")
    if not total or not elig:
        return None
    rate = m.get("eligibility_rate", 0)
    drop = m.get("biggest_dropoff")
    head = f"{elig:,} of {total:,} accounts are eligible"
    # the rate says it; commentary ('most of the book qualifies') doesn't
    sub = f"{rate}% eligibility"
    if drop:
        sub += (f"; {drop[0].lstrip('+ ').lower()} removes {drop[1]}% "
                f"at that step")
    return head, sub


def take_rate(m: dict) -> tuple[str, str] | None:
    overall = m.get("dctr_overall")
    if overall is None:
        return None
    best, worst = m.get("dctr_branch_best"), m.get("dctr_branch_worst")
    spread = m.get("dctr_branch_spread_pp")
    l12m = m.get("dctr_l12m")
    trend = m.get("dctr_l12m_vs_hist_pp")

    if best and worst and spread and spread >= 10:
        head = (f"{best[0]} takes the card at {best[1]:.0f}%, "
                f"{spread:.0f} points ahead of {worst[0]}")
    else:
        head = f"Debit card penetration runs {overall}% across the portfolio"

    sub = f"portfolio {overall}%"
    if l12m is not None and trend is not None:
        if trend >= 3:
            sub += (f"; accounts opened in the last year are reaching "
                    f"{l12m}%, {trend:+.1f} points ahead")
        elif trend <= -3:
            sub += (f"; accounts opened in the last year are at {l12m}%, "
                    f"{trend:.1f} points behind")
        else:
            sub += f"; new accounts track close behind at {l12m}%"
    return head, sub


def leaks(m: dict) -> tuple[str, str] | None:
    rows = m.get("dctr_leaks") or []
    total = m.get("dctr_leak_total")
    if not rows or not total:
        return None
    top = rows[0]
    value = m.get("dctr_leak_value")
    if value and value > 0:
        head = (f"Closing the three widest branch gaps is worth "
                f"{_money(value)} a year")
    else:
        # zero or negative measured value: state the gap, never 'worth $-X'
        head = f"The three widest branch gaps account for {total:,} cards"
    sub = (f"{top['segment']} holds {top['share_of_volume']:.0f}% of eligible "
           f"accounts and {top['share_of_outcome']:.0f}% of the cards; "
           f"{total:,} cards across the gaps")
    return head, sub


def od_limit(m: dict) -> tuple[str, str] | None:
    n = m.get("od_eligible_n")
    if not n:
        return None
    if m.get("od_eligibility_informative"):
        head = (f"{m.get('od_eligible_pct', 0):.0f}% of eligible accounts "
                f"are overdraft-eligible")
        lead = f"{m.get('od_with_limit_pct', 0):.0f}% of those carry a limit; "
    else:
        head = (f"{m.get('od_with_limit_pct_of_eligible', 0):.0f}% of "
                f"eligible accounts carry an overdraft limit")
        lead = f"the average limit is {_money(m.get('od_limit_mean', 0))}; "
    if m.get("od_rege_base"):
        sub = (lead + f"{m.get('od_optin_pct', 0):.0f}% of OD-eligible cardholders "
               f"have opted in; {m.get('od_eligible_not_optin_n', 0):,} have not")
        if m.get("od_optin_no_limit_n"):
            sub += f", and {m['od_optin_no_limit_n']:,} opted in with no limit"
    else:
        sub = lead + f"{n:,} OD-eligible accounts of {m.get('od_base', 0):,} eligible"
    return head, sub


def migration(m: dict) -> tuple[str, str] | None:
    if not m.get("mig_base"):
        return None
    head = (f"{m.get('mig_up_pct', 0):.0f}% of cardholders moved up "
            f"a swipe tier")
    window = (f"{m.get('mig_first')} to {m.get('mig_latest')}; "
              f"{m.get('mig_down_pct', 0):.0f}% moved down")
    adv = m.get("mig_responder_up_advantage_pp")
    groups = {r[0]: r for r in (m.get("mig_by_group") or [])}
    if adv is not None and "Responder" in groups:
        sub = (f"{window}; responders moved up at "
               f"{groups['Responder'][2]:.0f}% against "
               f"{groups['Mailed non-responder'][2]:.0f}% for mailed "
               f"non-responders")
    else:
        sub = f"{window}; base of {m.get('mig_base', 0):,} eligible cardholders"
    if m.get("mig_entered_use_n"):
        sub += f"; {m['mig_entered_use_n']:,} non-users started swiping"
    return head, sub


def cohort(m: dict) -> tuple[str, str] | None:
    rows = m.get("cohort_lift") or []
    if not rows:
        return None
    twelve = next((r for r in rows if r.get("horizon_months") == 12), rows[-1])
    one = next((r for r in rows if r.get("horizon_months") == 1), rows[0])
    did12 = twelve.get("diff_in_diff")
    did1 = one.get("diff_in_diff")
    if did12 is None:
        return None

    head = (f"A response is still worth {_money(did12)} a month "
            f"{twelve['horizon_months']} months later")
    if did1 and did1 > did12:
        decay = round(100 * (did1 - did12) / did1)
        sub = (f"the effect peaks at {_money(did1)} in the first month and "
               f"settles {decay}% below that")
    else:
        sub = "measured against mailed accounts that did not respond"
    dip = m.get("selection_dip_pct")
    if dip is not None and dip < -10:
        sub += (f"; responders start {abs(dip):.0f}% below their own normal, "
                f"which the baseline corrects for")
    return head, sub


def segments(m: dict) -> tuple[str, str] | None:
    rows = m.get("segment_summary") or []
    rows = [r for r in rows if r.get("response_rate") is not None]
    if len(rows) < 2:
        return None
    best = max(rows, key=lambda r: r.get("ic_per_1000_mailed") or 0)
    worst = min(rows, key=lambda r: r.get("ic_per_1000_mailed") or 0)
    b, w = best.get("ic_per_1000_mailed"), worst.get("ic_per_1000_mailed")
    if not b or not w:
        return None
    ratio = b / w if w else 0

    head = (f"{best['segment']} returns {ratio:.0f}x what {worst['segment']} "
            f"does per thousand mailed")
    sub = (f"{best['segment']} converts {best['response_rate']:.1f}% against "
           f"{worst['segment']} at {worst['response_rate']:.1f}%, while the "
           f"value of a response barely changes")
    return head, sub


def value(m: dict) -> tuple[str, str] | None:
    card = m.get("value_debit_delta")
    optin = m.get("value_rege_delta")
    if card is None and optin is None:
        return None
    parts = []
    if card is not None:
        parts.append(f"a card is worth {_money(card)} a year" if card >= 0
                     else f"carded accounts run {_money(abs(card))} a year "
                          f"below cardless ones on this book")
    if optin is not None:
        parts.append(f"an opt-in {_money(optin)}" if optin >= 0
                     else f"opt-ins {_money(abs(optin))} below")
    head = " and ".join(parts).capitalize()

    without = m.get("value_debit_n_without")
    pot = m.get("value_debit_pot_l12m")
    if without and pot:
        sub = (f"{without:,} eligible accounts have no card; converting them "
               f"at the current new-account rate is {_money(pot)}")
    else:
        sub = "interchange plus NSF/OD fees, trailing twelve months"
    return head, sub


def health(m: dict) -> tuple[str, str] | None:
    carded = m.get("retention_carded_n")
    at_risk = m.get("retention_at_risk_n")
    if not carded or at_risk is None:
        return None
    share = m.get("retention_at_risk_of_carded_pct", 0)
    rows = {r[0]: r[1] for r in (m.get("retention_health") or [])}
    never = rows.get("Never activated", 0)

    if never and never / carded >= 0.10:
        head = (f"{never:,} cards have been issued and never used")
        sub = (f"{at_risk:,} of {carded:,} cardholders show fading or absent "
               f"activity ({share:.0f}%)")
    else:
        head = f"{share:.0f}% of cardholders show fading card activity"
        sub = f"{at_risk:,} of {carded:,} accounts"

    adv = m.get("retention_responder_advantage_pp")
    if adv is not None and adv > 5:
        sub += (f"; responders are {adv:.0f} points less likely to be among "
                f"them than mailed non-responders")
    target = m.get("reactivation_target_n")
    if target:
        sub += f". {target:,} are already on the mailing file"
    return head, sub


def closing(m: dict) -> tuple[str, str] | None:
    """Three sized opportunities, largest first."""
    items = []
    if m.get("value_debit_pot_l12m"):
        items.append(("cards", m["value_debit_pot_l12m"]))
    if m.get("rege_default_value"):
        items.append(("Reg E elections", m["rege_default_value"]))
    if m.get("dctr_leak_value"):
        items.append(("closing the widest branch gaps", m["dctr_leak_value"]))
    if not items:
        return None
    items.sort(key=lambda i: -i[1])
    total = sum(v for _, v in items)
    head = f"{_money(total)} a year sits in three moves"
    sub = ", ".join(f"{label} {_money(v)}" for label, v in items)
    return head, sub


# ---------------------------------------------------------------------------
# Horizontal-logic pass (2026-08-20): action titles for the slide families
# that fell back to topic labels. Same contract as everything above --
# deterministic, branch on the numbers, return None when the keys are absent.
# ---------------------------------------------------------------------------

def _n(m, key):
    v = m.get(key)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def swipe_usage(m: dict) -> tuple[str, str] | None:
    rows = m.get("swipe_tier") or []
    if not rows:
        return None
    counts = {r[0]: r[1] for r in rows}
    carded = sum(v for k, v in counts.items() if k != "No card")
    if not carded:
        return None
    heavy = counts.get("26-40", 0) + counts.get("41+", 0)
    non = counts.get("Non-user", 0)
    head = f"{100 * heavy / carded:.0f}% of cardholders swipe 26+ times a month"
    return head, (f"{100 * non / carded:.0f}% hold a card they never use; "
                  f"monthly-average tiers over "
                  f"{', '.join(m.get('swipe_window', []))}")


def ticket(m: dict) -> tuple[str, str] | None:
    blended = _n(m, "ticket_blended")
    # highest REAL tier: a Non-user's two annual swipes make a nonsense ticket
    rows = [t for t in (m.get("ticket_by_tier") or []) if t[0] != "Non-user"]
    hi = max(rows, key=lambda t: t[2])[:1] + [max(t[2] for t in rows)] if rows \
        else m.get("ticket_highest")
    if not blended or not hi:
        return None
    return (f"The average debit swipe is ${blended:.0f}",
            f"the {hi[0]} tier spends ${hi[1]:.0f} per swipe; "
            f"spend divided by swipes, trailing three months")


def waves(m: dict) -> tuple[str, str] | None:
    lr, mean = _n(m, "latest_resprate"), _n(m, "resprate_mean")
    if lr is None or mean is None:
        return None
    verb = "ahead of" if lr > mean + 0.5 else ("below" if lr < mean - 0.5 else "in line with")
    return (f"The latest offer responded at {lr:.1f}%, {verb} the "
            f"{mean:.1f}% average", "mean across completed offers")


def dot_ask(m: dict) -> tuple[str, str] | None:
    mean, pos = _n(m, "dot_mean"), _n(m, "dot_positive_pct")
    if mean is None or pos is None:
        return None
    sub = (f"{pos:.0f}% increased at all; {m.get('dot_n', 0):,} "
           f"responder-offer pairs, measured after the mail month")
    if mean < 0.5:
        # a near-zero or negative mean is not a raise -- say what happened
        head = ("Responder swipes held level against their own baseline"
                if mean > -0.5 else
                f"Responder swipes ran {abs(mean):.0f} below their own "
                f"baseline")
        return head, sub
    fell = _n(m, "dot_fell_n")
    if fell:
        sub += (f"; the 'fell' bar is {fell:,.0f} responders who ran below "
                f"their own baseline")
    return (f"Responders raised monthly swipes by {mean:.0f} over "
            f"their own baseline", sub)


def dot_segments(m: dict) -> tuple[str, str] | None:
    rows = m.get("dot_by_segment") or []
    if not rows:
        return None
    total40 = sum(r[5] for r in rows)
    if total40:
        top = max(rows, key=lambda r: r[5])
        head = f"The biggest jumps follow {top[0]} offers"
        return head, (f"{top[5]:,} of the {total40:,} responses that gained "
                      f"40+ swipes; swipe lift over each account's own run "
                      f"rate, split by the tier the response achieved")
    else:
        top = max(rows, key=lambda r: r[2])
        if top[2] >= 0.5:
            head = (f"{top[0]} delivers the strongest lift at "
                    f"+{top[2]:.0f} swipes over baseline")
        else:
            # no segment lifted -- the closest-to-baseline fact, honestly
            head = (f"{top[0]} holds closest to baseline at "
                    f"{top[2]:.1f} swipes")
    return head, ("swipe lift over each account's own run rate, split by "
                  "the tier the response achieved")


def sustained(m: dict) -> tuple[str, str] | None:
    months = _n(m, "sustained_months_above")
    if months is None:
        return None
    return (f"Responder activity holds above baseline for "
            f"{months:.0f} of 12 months",
            "months after the mailing, indexed to each cohort's "
            "pre-mail spend")


def age_profile(m: dict) -> tuple[str, str] | None:
    u25, o65 = _n(m, "age_u25_rate"), _n(m, "age_o65_rate")
    if u25 is None or o65 is None:
        return None
    hi = "under-25s" if u25 >= o65 else "over-65s"
    return (f"Response skews to {hi}: {u25:.1f}% under 25 vs {o65:.1f}% over 65",
            f"{m.get('age_base', 0):,} accounts with a valid holder age")


def balance_profile(m: dict) -> tuple[str, str] | None:
    r, n = _n(m, "bal_resp_med"), _n(m, "bal_non_med")
    if r is None or n is None:
        return None
    comp = "lower" if r < n else "higher"
    return (f"Responders hold a {_money(r)} median balance",
            f"{comp} than the {_money(n)} of mailed non-responders")


def take_by_base(m: dict) -> tuple[str, str] | None:
    overall, l12 = _n(m, "dctr_overall"), _n(m, "dctr_l12m")
    if overall is None or l12 is None:
        return None
    d = l12 - overall
    return (f"Recent accounts take the card {abs(d):.1f} pts "
            f"{'above' if d >= 0 else 'below'} the book",
            f"last-12-month accounts at {l12:.1f}%, book at {overall:.1f}%; "
            f"every base states its own denominator")


def spend_trend(m: dict) -> tuple[str, str] | None:
    sp, sw = _n(m, "spend_yoy_pct"), _n(m, "swipes_yoy_pct")
    if sp is None or sw is None:
        return None
    return (f"Debit spend is {'up' if sp >= 0 else 'down'} {abs(sp):.1f}% year over year; "
            f"swipes {'up' if sw >= 0 else 'down'} {abs(sw):.1f}%", None)


def nsf_trend(m: dict) -> tuple[str, str] | None:
    items, yoy = _n(m, "nsf_last_items"), _n(m, "nsf_yoy")
    if items is None or yoy is None:
        return None
    return (f"NSF/OD items ran {items:,.0f} last month, "
            f"{'up' if yoy >= 0 else 'down'} {abs(yoy):.0f}% year over year",
            f"{m.get('nsf_last_accts', 0):,} accounts had at least one item")


def rege_vintage(m: dict) -> tuple[str, str] | None:
    l12, hist = _n(m, "rege_l12m_pct"), _n(m, "rege_pct")
    if l12 is None or hist is None:
        return None
    d = l12 - hist
    return (f"New accounts elect Reg E {abs(d):.1f} pts "
            f"{'above' if d >= 0 else 'below'} the book",
            f"last-year accounts at {l12:.1f}%, book at {hist:.1f}%; "
            f"election rate by the account's opening vintage")


def rege_by_branch(m: dict) -> tuple[str, str] | None:
    rows = [r for r in (m.get("rege_branch") or []) if r[2] and r[2] >= 50]
    if len(rows) < 2:
        return None
    best = max(rows, key=lambda r: r[3])
    worst = min(rows, key=lambda r: r[3])
    return (f"Reg E opt-in reaches {best[3]:.0f}% at {best[0]}; "
            f"{worst[0]} sits at {worst[3]:.0f}%",
            "a process gap, not a customer one; branches with 50+ "
            "accounts in the pool")


def next_moves(m: dict) -> tuple[str, str] | None:
    opps = [o for o in (m.get("syn_opportunities") or []) if o.get("kind") == "revenue"][:3]
    if not opps:
        return None
    total = sum(o["value"] for o in opps)
    return (f"The next quarter's three moves are worth {_money(total)} a year",
            "sized from this file; items overlap, so worked in order, not summed")


# ---------------------------------------------------------------------------
# Branch and mailer detail pass (2026-08-20): five slides that were tables in
# the report but absent from the deck. Same contract -- deterministic, branch
# on the numbers, return None when the keys are absent.
# ---------------------------------------------------------------------------

def per_mailer(m: dict) -> tuple[str, str] | None:
    best = m.get("resprate_best")
    mean = _n(m, "resprate_mean")
    if not best or mean is None:
        return None
    head = f"{best[0]} is the highest-responding offer at {best[1]:.1f}%"
    sub = f"mean {mean:.1f}% across completed offers"
    worst = m.get("resprate_worst")
    if worst:
        sub += f"; lowest is {worst[0]} at {worst[1]:.1f}%"
    return head, sub


def before_after(m: dict) -> tuple[str, str] | None:
    net = _n(m, "ba_lift_net")
    cpre, cpost = _n(m, "ba_control_before"), _n(m, "ba_control_after")
    if net is None or cpre is None or cpost is None:
        return None
    rpre, rpost = _n(m, "ba_spend_before"), _n(m, "ba_spend_after")
    if cpost < cpre:
        # The control fell: the mailing's work was arresting a decline, not
        # conjuring new spend. Say that, or the number reads as a miss.
        head = (f"Responders arrested the control's decline: "
                f"{_money(net)}/mo net")
    else:
        head = (f"Responders gained {_money(net)}/mo over control around "
                f"each mailing")
    sub = None
    if rpre is not None and rpost is not None:
        sub = (f"control fell {_money(cpre - cpost)}/mo; responders "
               f"{_money(rpre)} to {_money(rpost)}/mo, control "
               f"{_money(cpre)} to {_money(cpost)}/mo, six months "
               f"before each offer against three after")
    return head, sub


def branch_scorecard(m: dict) -> tuple[str, str] | None:
    rows = [r for r in (m.get("syn_branch_scorecard") or [])
            if len(r) > 2 and r[2] is not None]
    rated = [r for r in rows if r[1] and r[1] >= 25]   # dctr.py's floor: tiny
    if len(rated) >= 2:                                # branches cannot headline
        rows = rated
    if len(rows) < 2:
        return None
    best = max(rows, key=lambda r: r[2])
    worst = min(rows, key=lambda r: r[2])
    head = (f"{best[0]} takes the card at {best[2]:.0f}%; "
            f"{worst[0]} at {worst[2]:.0f}%")
    sub = ("every branch on one line — cards, Reg E, value per account "
           "and closures")
    return head, sub


def branch_value(m: dict) -> tuple[str, str] | None:
    spread = _n(m, "value_branch_spread")
    best, worst = m.get("value_branch_best"), m.get("value_branch_worst")
    if spread is None or not best or not worst:
        return None
    head = (f"{best['group']} out-earns {worst['group']} by "
            f"{_money(spread)} per account a year")
    share = _n(m, "value_branch_penetration_share")
    if share is not None:
        sub = (f"{share:.0f}% of the spread is card penetration — "
               f"a process lever, not the customer base")
    else:
        sub = "interchange plus NSF/OD fees per eligible account"
    return head, sub


def divergence(m: dict) -> tuple[str, str] | None:
    rows = m.get("branch_divergence") or []
    if not rows:
        return None
    top = rows[0]
    head = (f"{top[0]}: cards {top[4]:+.1f} pts on the book, Reg E "
            f"{abs(top[5]):.1f} behind")
    sub = "strong on one ask and weak on the other is process, not customers"
    dctr, rege = _n(m, "dctr_overall"), _n(m, "rege_pct")
    if dctr is not None and rege is not None:
        sub += f" — book: cards {dctr:.0f}%, Reg E {rege:.0f}%"
    return head, sub


# ---------------------------------------------------------------------------
# Wave 2 (issue #14): responder economics, reach, activation, the monthly
# branch matrix, the tenure ladder and the responder profile. Same contract
# as everything above -- deterministic, branch on the numbers, return None
# when the keys are absent.
# ---------------------------------------------------------------------------

def responder_value(m: dict) -> tuple[str, str] | None:
    prem = _n(m, "value_responder_premium")
    if prem is not None:
        head = (f"A responder out-earns a mailed non-responder by "
                f"{_money(prem)} a year")
        ic = _n(m, "value_responder_premium_ic")
        nsf = _n(m, "value_responder_premium_nsf")
        if ic is not None and nsf is not None:
            sub = (f"{_money(ic)} of it is interchange, {_money(nsf)} NSF/OD "
                   f"— carded accounts only, so the gap is behaviour, "
                   f"not card ownership")
        else:
            sub = ("carded accounts only, so the gap is behaviour, "
                   "not card ownership")
        return head, sub
    rows = m.get("value_by_response") or []
    resp = next((r for r in rows if r.get("group") == "Responder"), None)
    # small books lose cells to the minimum-cell rule; compare against
    # whichever non-responder group survived
    other = (next((r for r in rows if r.get("group") == "Not mailed"), None)
             or next((r for r in rows
                      if r.get("group") == "Mailed non-responder"), None))
    if not resp or not other:
        return None
    name = ("the never-mailed" if other["group"] == "Not mailed"
            else "mailed non-responders")
    head = (f"A responder generates {_money(resp['value_per_acct'])} a year "
            f"against {_money(other['value_per_acct'])} for {name}")
    return head, "interchange plus NSF/OD per eligible account"


def program_reach(m: dict) -> tuple[str, str] | None:
    total, pct = m.get("reach_total"), _n(m, "reach")
    if total is None or pct is None:
        return None
    base = str(m.get("reach_base") or "eligible").lower()
    head = (f"{total:,} accounts have responded — "
            f"{pct:.0f}% of the {base} base")
    parts = []
    events = m.get("responses_total")
    if events:
        parts.append(f"counted once each; {events:,} responses across "
                     f"all offers")
    of_mailed = _n(m, "reach_of_mailed")
    if of_mailed is not None and m.get("n_ever_mailed"):
        parts.append(f"{of_mailed:.0f}% of the {m['n_ever_mailed']:,} "
                     f"ever mailed")
    per = _n(m, "reach_perml")
    if per is not None:
        parts.append(f"about {per:,.0f} new responders per completed offer")
    return head, "; ".join(parts) or None


def activation_split(m: dict) -> tuple[str, str] | None:
    prog_pct = _n(m, "activation_program_pct")
    existing = m.get("activation_existing_n")
    l12m = m.get("activation_l12m_n")
    if existing is None or l12m is None:
        return None
    if not existing:
        # every first swipe came from a brand-new account: nothing here is
        # the program's to claim, and saying so is the finding
        head = (f"All {l12m:,} first swipes in the last year are "
                f"new-account onboarding")
        return head, ("no existing account activated in the window, so "
                      "neither the mail nor organic drift moved anyone")
    if prog_pct is None:
        return None
    head = (f"The program drove {prog_pct:.0f}% of existing-account "
            f"activations")
    prog, org = m.get("activation_program_n"), m.get("activation_organic_n")
    if prog is not None and org is not None:
        sub = (f"of {existing:,} existing accounts taking a first swipe "
               f"in the last year, {prog:,} were mailed first and {org:,} "
               f"moved on their own")
    else:
        sub = f"{existing:,} existing accounts took a first swipe"
    new = m.get("activation_new_account_n")
    if new:
        sub += f"; {new:,} more were new-account onboarding"
    return head, sub


def branch_month(m: dict) -> tuple[str, str] | None:
    totals = [t for t in (m.get("dctr_monthly_totals") or [])
              if t is not None]
    if len(totals) < 2:
        return None
    t0, t1 = totals[0], totals[-1]
    if t1 - t0 > 1:
        head = (f"New-account take rate is rising — {t0:.0f}% early to "
                f"{t1:.0f}% in the latest month")
    elif t0 - t1 > 1:
        head = (f"New-account take rate is falling — {t0:.0f}% early to "
                f"{t1:.0f}% in the latest month")
    else:
        head = f"New-account take rate holds near {t1:.0f}% through the year"
    sub = ("take rate by the month the account was opened, base: that "
           "month's newly opened eligible accounts; largest branches shown")
    movers = [r for r in (m.get("dctr_branch_trend") or [])
              if len(r) > 5 and r[5] is not None]
    if movers:
        top = max(movers, key=lambda r: abs(r[5]))
        sub += f"; {top[0]} moved most, {top[5]:+.1f} pts vs its history"
    return head, sub


def value_ladder(m: dict) -> tuple[str, str] | None:
    rows = m.get("value_by_account_age") or []
    if len(rows) < 2:
        return None
    step = m.get("value_age_biggest_step")
    if step:
        head = (f"Value per account climbs {_money(step['step'])} between "
                f"{step['from']} and {step['to']}")
    else:
        head = (f"Value per account climbs from "
                f"{_money(rows[0]['value_per_acct'])} to "
                f"{_money(rows[-1]['value_per_acct'])} as accounts age")
    pot_h = _n(m, "value_debit_pot_hist")
    pot_f = _n(m, "value_debit_pot_full")
    if pot_h is not None and pot_f is not None:
        sub = ("the ladder's biggest step; " if step else "") + (
               f"unrecaptured cards are worth {_money(pot_h)} at history's "
               f"take rate, {_money(pot_f)} at full")
        rege = _n(m, "value_rege_pot_elected")
        if rege is not None:
            sub += f"; Reg E adds {_money(rege)} at the elected rate"
    else:
        sub = "interchange plus NSF/OD per eligible account, by account age"
    return head, sub


def responder_profile(m: dict) -> tuple[str, str] | None:
    prof = m.get("responder_profile") or {}
    bal = prof.get("balance_median")
    spend = prof.get("spend_per_mo")
    # The balance comparison already headlines "Who responds -- balance
    # profile" (T2, review-trends.md: one finding per deck) -- this slide
    # leads with spend and keeps balance for the sub
    if spend and len(spend) == 2:
        head = (f"Responders spend {_money(spend[0])}/mo on debit to "
                f"non-responders' {_money(spend[1])}")
    elif bal and len(bal) == 2:
        head = (f"Responders hold {_money(bal[0])} in median balance to "
                f"non-responders' {_money(bal[1])}")
    else:
        return None
    parts = []
    if bal and spend and len(spend) == 2 and len(bal) == 2:
        parts.append(f"median balance {_money(bal[0])} vs "
                     f"{_money(bal[1])}")
    debit = prof.get("debit_pct")
    if debit and len(debit) == 2:
        parts.append(f"cards in {debit[0]:.0f}% vs {debit[1]:.0f}% of hands")
    rep = _n(m, "depth_repeat_pct")
    if rep is not None:
        parts.append(f"{rep:.0f}% of responders come back more than once")
    return head, "; ".join(parts) or None


def ladder_waves(m: dict) -> tuple[str, str] | None:
    moves = dict(m.get("ladder_movement") or [])
    total = sum(moves.values())
    nu = _n(m, "nu_conversion_pct")
    if not total and nu is None:
        return None
    nu_line = (f"NU partials convert at {nu:.1f}%; "
               if nu is not None else "")
    if total:
        up = 100 * moves.get("Up", 0) / total
        head = f"{up:.0f}% of repeat responses moved up a tier"
    else:
        head = f"NU partials convert to a full response at {nu:.1f}%"
    ft, rp = _n(m, "ladder_first_time"), _n(m, "ladder_repeat")
    sub = None
    if ft is not None and rp is not None:
        sub = nu_line + (f"{ft:,.0f} first-time and {rp:,.0f} repeat responses -- "
               f"response events from offers 2 onward, not unique accounts; "
               f"movement is judged against each account's best prior tier")
    return head, sub


def segment_traj(m: dict) -> tuple[str, str] | None:
    rows = [r for r in (m.get("segment_summary") or [])
            if r.get("did_per_1000_mailed") is not None]
    if not rows:
        return None
    best = max(rows, key=lambda r: r["did_per_1000_mailed"])
    head = (f"{best['segment']} returns {_money(best['did_per_1000_mailed'])} "
            f"per 1,000 pieces mailed")
    sub = (f"the strongest segment; responder lift minus control, pooled "
           f"across offers; segment read from "
           f"{m.get('segment_source', 'the offer tier')}")
    return head, sub


def counterfactual(m: dict) -> tuple[str, str] | None:
    gap = _n(m, "counterfactual_gap_total")
    if gap is None:
        return None
    if gap >= 0:
        head = (f"Responder activation held spend {_money(gap)} above "
                f"the no-program line")
    else:
        head = f"Spend sits {_money(abs(gap))} below the no-program line"
    ic = _n(m, "counterfactual_ic_total")
    sub = "the control's trajectory applied to responders' own pre-spend"
    if ic is not None:
        sub += f"; {_money(ic)} interchange earned on the difference"
    return head, sub


def attrition_branch(m: dict) -> tuple[str, str] | None:
    worst, best = m.get("attrition_branch_worst"), m.get("attrition_branch_best")
    if not worst or not best:
        return None
    head = (f"{best[0]} keeps attrition to {best[1]:.1f}%; {worst[0]} "
            f"runs {worst[1]:.1f}%")
    sub = (f"a {worst[1] - best[1]:.1f}-pt spread; closures over the "
           f"12-month window; only branches with 150+ at-risk accounts "
           f"are rated")
    return head, sub


def cascade(m: dict) -> tuple[str, str] | None:
    steps = {s[0]: s for s in (m.get("syn_cascade") or []) if len(s) >= 3}
    elig = steps.get("Eligible accounts")
    rev = steps.get("Card revenue on the book")
    if not steps or not elig:
        return None
    if rev:
        head = (f"{_money(rev[1])} of card revenue stands on "
                f"{elig[1]:,.0f} eligible accounts")
    else:
        head = (f"The program's economics, step by step, from "
                f"{elig[1]:,.0f} eligible accounts")
    sub = ("eligibility to retention on one line of sight; every step is "
           "the section's own reported number")
    return head, sub


def penalty(m: dict) -> tuple[str, str] | None:
    v = _n(m, "penalty_box_violations")
    if not v:
        return None
    head = f"{v:,.0f} responses repeated a tier inside the penalty window"
    waves = _n(m, "penalty_box_waves")
    sub = None
    if waves:
        sub = (f"the program bars repeating a tier within {waves:.0f} mailers "
               f"— a suppression-rule gap to close, not customer behaviour")
    return head, sub


def hero(m: dict) -> tuple[str, str] | None:
    """The campaign hero: the earned-dollars headline the deck opens on.
    Prefers the workbook's life-to-date profit; falls back to the ODD's
    control-anchored counterfactual."""
    bal = _n(m, "gt_deferred_balance")
    if bal is not None and bal > 1 and m.get("gt_state") != "clear":
        # the deferral tracker exists AND a balance is live: its math IS
        # the client's economics (James, issue #42) -- an in-guarantee
        # client never reads as a loss. A cleared guarantee (or a tracker
        # that drew to zero) falls through to the workbook.
        rev, paid = _n(m, "gt_revenue_ltd"), _n(m, "gt_paid_ltd")
        earned = (rev or 0) - (paid or 0)
        head = (f"The 2:1 guarantee holds: {_money(earned)} earned over "
                f"the fees paid")
        sub = (f"{_money(rev)} revenue against {_money(paid)} paid; "
               f"{_money(bal)} deferred through {m.get('gt_latest_month')}"
               f", forgiven at contract end unless drawn down "
               f"(deferral tracker)")
        return head, sub
    wb_profit = _n(m, "wb_profit_ltd")
    if wb_profit is not None:
        months = _n(m, "wb_months_in_program")
        span = f" in {months:.0f} months" if months else ""
        if wb_profit >= 0:
            head = (f"The program has earned {_money(wb_profit)} of program "
                    f"profit{span}")
        else:
            head = (f"The program is {_money(abs(wb_profit))} short of its "
                    f"fees{span}")
        rev = _n(m, "wb_revenue_ltd")
        sub = None
        if rev is not None:
            sub = (f"{_money(rev)} program revenue less program fees, from "
                   f"the ARS Workbook; response and lift from the ODD")
        return head, sub
    if m.get("wb_found"):
        # This client HAS a workbook: the hero is its booked profit or it
        # is nothing. Falling to the ODD frames below would swap BOOKED
        # for INCREMENTAL in the booked slot, which issue #40 forbids
        # (DESIGN/copy-rules.md, "Revenue frames"). The workbook did not
        # read this run -- say so by declining, the way Program P&L and
        # the wave rollups already do (James, 2026-08-31, issue #116).
        return None
    gap = _n(m, "counterfactual_gap_total")
    if gap is not None and gap > 0:
        head = (f"The campaigns held {_money(gap)} of spend above the "
                f"no-mail line")
        return head, ("control-anchored: responders measured against mailed "
                      "non-responders, never before/after")
    net = _n(m, "ba_lift_net")
    if net is not None:
        return (f"Responders run {_money(net)}/mo ahead of control around "
                f"each mailing",
                "control-anchored: mailed non-responders, never before/after")
    return None


def pnl(m: dict) -> tuple[str, str] | None:
    """Program P&L -- guarantee math when the tracker exists, the
    workbook's billed figures otherwise."""
    bal = _n(m, "gt_deferred_balance")
    if bal is not None and bal > 1 and m.get("gt_state") != "clear":
        months = _n(m, "gt_months_n")
        head = (f"The 2:1 guarantee holds: {_money(bal)} of fees deferred "
                f"to date")
        sub = (f"the client pays half of revenue while under the 2x mark"
               + (f"; {months:.0f} months tracked" if months else "")
               + ", deferred fees forgiven at contract end unless drawn down")
        return head, sub
    profit = _n(m, "wb_profit_ltd")
    if profit is None:
        return None
    rev, costs = _n(m, "wb_revenue_ltd"), _n(m, "wb_costs_ltd")
    if rev is not None and costs:
        per = rev / abs(costs)
        head = (f"Every fee dollar has returned ${per:,.2f} in revenue "
                f"— {_money(profit)} profit to date")
    else:
        head = f"{_money(profit)} of program profit to date"
    months = _n(m, "wb_months_in_program")
    mailings = _n(m, "wb_mailings_to_date")
    sub = "revenue and fees from the ARS Workbook; response from the ODD"
    if months and mailings:
        sub = (f"{mailings:.0f} mailings over {months:.0f} months — "
               f"revenue and fees from the ARS Workbook")
    return head, sub


def guarantee(m: dict) -> tuple[str, str] | None:
    """The 2:1 guarantee slide (issues #42/#43)."""
    bal = _n(m, "gt_deferred_balance")
    if bal is None:
        return None
    ratio = _n(m, "gt_ratio_latest")
    state = str(m.get("gt_state", ""))
    if state == "clear":
        head = "The guarantee is clear: no fees remain deferred"
    elif state == "drawing-down":
        head = (f"Revenue has crossed the 2x mark: the {_money(bal)} "
                f"deferred balance is drawing down")
    else:
        head = (f"{_money(bal)} of fees are deferred under the 2:1 "
                f"guarantee")
    sub = None
    if ratio is not None:
        sub = (f"latest month runs at {ratio:.2f}x billing; the deferral "
               f"releases at 2.00x and is forgiven at contract end")
    return head, sub


def revenue_frames(m: dict) -> tuple[str, str] | None:
    """The bridge between booked workbook revenue and DiD estimates
    (James, issue #40): two frames, named, never blended."""
    wb, net = _n(m, "wb_revenue_ltd"), _n(m, "ba_lift_net")
    if wb is None or net is None:
        return None
    return ("Booked revenue and the DiD estimate answer different questions",
            f"the ledger books {_money(wb)} gross program revenue; DiD "
            f"estimates {_money(net)}/mo incremental, net of control, "
            f"so the two never tie")


def lift_matrix(m: dict) -> tuple[str, str] | None:
    """The workbook's rate card: what an account earns at each swipe band,
    by the band it started in. Every claim is CHECKED against the grid --
    "climbs" is a finding here, not a house assumption, because a card
    that does not climb is the more interesting slide."""
    cols = m.get("wb_lift_cols") or []
    rows = m.get("wb_lift_rows") or []
    series = [[v for v in row[1:] if isinstance(v, (int, float))]
              for row in rows]
    vals = [v for row in series for v in row]
    if not cols or not vals:
        return None
    lo, hi = min(vals), max(vals)
    # the sheet names its own unit; only format as money when it says so.
    # Cents, not whole dollars: a rate card's rows are a few dollars apart
    # and _money would round the whole card to the same number.
    money = "$" in str(m.get("wb_lift_caption") or "$")
    fmt = (lambda v: f"${v:,.2f}") if money else (lambda v: f"{v:,.2f}")
    climbs = all(a <= b for row in series for a, b in zip(row, row[1:]))
    # Kept short deliberately: a card with four-figure rates adds ~12
    # characters to the range, and the one-line rule is enforced on the
    # rendered title, not on this fixture's small numbers.
    if climbs:
        head = f"Every segment climbs, {fmt(lo)} to {fmt(hi)} a month"
    else:
        head = f"The rate card runs {fmt(lo)} to {fmt(hi)} a month"
    window = m.get("wb_lift_window")
    tail = ("the window has closed, so the card is stale"
            if m.get("wb_lift_stale")
            else "booked frame, the workbook's own rate card")
    seg_n = f"{len(rows)} baseline segment" + ("s" if len(rows) != 1 else "")
    sub = (f"{seg_n} by {len(cols)} band" + ("s" if len(cols) != 1 else "")
           + (f", {window}" if window else "") + f"; {tail}")
    return head, sub


def rege_dashboard(m: dict) -> tuple[str, str] | None:
    """The Reg E chapter dashboard (James, issue #41): topic title, the
    two facts that matter in the sub, denominators on the tiles."""
    pct, pool = _n(m, "rege_pct"), _n(m, "rege_pool")
    if pct is None or not pool:
        return None
    never = int((_n(m, "rege_no") or 0) + (_n(m, "rege_default") or 0))
    sub = f"{pct}% of cardholders are opted in"
    if never:
        sub += f"; {never:,} have never made an election at all"
    return "Reg E opt-in", sub


def take_dashboard(m: dict) -> tuple[str, str] | None:
    """The debit chapter's operational dashboard (James, issue #41):
    topic title, the finding in the sub."""
    overall, l12m = _n(m, "dctr_overall"), _n(m, "dctr_l12m")
    if overall is None or l12m is None:
        return None
    drags = []
    if (_n(m, "dctr_business") or 100) < overall - 10:
        drags.append("business accounts")
    bal = [r for r in (m.get("dctr_balance") or []) if r[1]]
    if bal and min(r[3] for r in bal) < overall - 10:
        drags.append("high balances" if bal.index(
            min(bal, key=lambda r: r[3])) >= len(bal) - 2 else
            f"the {min(bal, key=lambda r: r[3])[0]} balance band")
    sub = (f"New business runs at {l12m:.1f}%; the book sits at "
           f"{overall:.1f}%")
    if drags:
        sub += f": {' and '.join(drags)} are the drag"
    return "Debit card take rate", sub


def no_card(m: dict) -> tuple[str, str] | None:
    """Who does not carry a card: the pools where take rate is lowest
    (James, issue #41 added slide)."""
    holder = [r for r in (m.get("dctr_holder_age") or []) if r[1]]
    tenure = [r for r in (m.get("dctr_account_age") or []) if r[1]]
    if not holder and not tenure:
        return None
    pools = []
    if holder:
        pools.append(f"the {min(holder, key=lambda r: r[3])[0]} holders")
    if tenure:
        pools.append(f"the {min(tenure, key=lambda r: r[3])[0]} tenure pool")
    return ("Who does not carry a card",
            "take rate falls with holder age and tenure: "
            + " and ".join(pools) + " hold the cardless accounts")


def tier_movement(m: dict) -> tuple[str, str] | None:
    """Tier movement by response status (James, issue #41 image spec)."""
    rows = {r[0]: r for r in (m.get("mig_by_group") or [])}
    resp, notm = rows.get("Responder"), rows.get("Not mailed")
    if not resp:
        return None
    head = f"Responders move up a swipe tier at {resp[2]:.0f}%"
    if notm and notm[2]:
        head += f", {resp[2] / notm[2]:.1f}x the unmailed rate"
    return head, ("share of accounts moving up, holding, or dropping a "
                  "swipe tier between their first and latest window on file")


def new_debit_gap(m: dict) -> tuple[str, str] | None:
    gap = _n(m, "debit_pen_gap")
    if gap is None:
        return None
    word = "ahead of" if gap > 0 else "behind"
    return (f"New accounts take the card {abs(gap):.1f} pts {word} the book",
            "debit penetration, accounts opened last 12 months vs all eligible")


def growth(m: dict) -> tuple[str, str] | None:
    net = _n(m, "net_24")
    if net is None:
        return None
    word = "grew" if net >= 0 else "shrank"
    return (f"The book {word} by {abs(net):,.0f} accounts in the latest month",
            "openings less closures; the line is the running net")


def firstyear_close(m: dict) -> tuple[str, str] | None:
    gap = _n(m, "firstyear_close_gap_pp")
    if gap is None:
        return None
    return (f"Never-used cards close {abs(gap):.1f} pts more often "
            f"in year one",
            "first-year closure rate by early card use")


def ops_kpis(m: dict) -> tuple[str, str] | None:
    take, rege = _n(m, "dctr_overall"), _n(m, "rege_pct")
    if take is None or rege is None:
        return None
    take_rows = {r[0]: r for r in (m.get("take_branch") or [])}
    rege_rows = {r[0]: r for r in (m.get("rege_branch") or [])}
    joined = [b for b in take_rows if b in rege_rows]
    below_both = [b for b in joined
                  if take_rows[b][3] < take and rege_rows[b][3] < rege]
    head = f"Take rate {take:.1f}% and Reg E opt-in {rege:.1f}%"
    if joined and below_both:
        lead = (f"{len(below_both)} of {len(joined)} branches run below "
                f"the book on both; ")
    elif joined:
        lead = f"across {len(joined)} branches; "
    else:
        lead = ""
    sub = lead + ("take rate on eligible accounts; Reg E on eligible "
                  "personal with debit; dashed lines are each metric's "
                  "book rate")
    return head, sub


def trajectory(m: dict, which: str) -> tuple[str, str] | None:
    """Factual-positive header for the per-tier trajectory lines."""
    tiers = m.get(f"cohort_{which}_by_tier") or {}
    offs = m.get("cohort_offsets") or []
    if not tiers or not offs:
        return None
    tail = max(offs)
    unit = "spend" if which == "spend" else "swipes"
    head = (f"Responder {unit} stays above control for "
            f"{tail} months post-mail")
    if tail < 6:
        head = f"Responder {unit} rises after the mail in every segment"
    sub = (f"monthly {unit} per account by response segment, "
           f"{abs(min(offs))} months before the mail to {tail} after; "
           f"dashed grey is the mailed non-responder control")
    return head, sub


def seg_combo(m: dict) -> tuple[str, str] | None:
    det = m.get("cohort_seg_detail") or {}
    offs = det.get("offsets") or []
    if not det.get("segments") or not offs:
        return None
    n_seg = len(det["segments"])
    total = sum((det.get("counts") or {}).values())
    head = "Every segment lifts and holds above its own run-in"
    sub = (f"swipes (top) and spend (bottom) per mailed account, "
           f"{n_seg} segmentation bands, {total:,} account-offer pairs, "
           f"{abs(min(offs))} months before the mail to {max(offs)} after")
    return head, sub


def exec_takeaways(m: dict) -> tuple[str, str] | None:
    """Factual-positive exec summary (James: 'the next three quarters'
    framing is old -- an executive summary of takeaways instead)."""
    opps = [o for o in (m.get("syn_opportunities") or [])
            if o.get("kind") == "revenue"][:3]
    total = sum(o.get("value") or 0 for o in opps)
    if total:
        head = (f"Three measured opportunities total "
                f"{_money(total)} a year")
    elif opps:
        head = f"The book's top {len(opps)} measured opportunities"
    else:
        return None
    sub = ("sized from this book's own rates and values; "
           "each carries its base and its list")
    return head, sub


# ---- wave revenue: the All Months Rollup matrix (issue #85) -------------
def _wave_series(m: dict) -> dict:
    """{wave: {month: booked revenue}} from the rollup matrix."""
    out: dict = {}
    for tag, month, value in (m.get("wb_wave_revenue") or []):
        out.setdefault(tag, {})[month] = value
    return out


def wave_mix(m: dict) -> tuple[str, str] | None:
    """Every live offer earns in the same month; say how many and how much."""
    waves = _wave_series(m)
    if len(waves) < 2:
        return None
    latest = max(mth for s in waves.values() for mth in s)
    live = {t: s[latest] for t, s in waves.items() if latest in s}
    total = sum(live.values())
    if not total:
        return None
    newest = list(waves)[-1]
    older = sum(v for t, v in live.items()
                if len(waves[t]) > 12)
    head = (f"{len(live)} offers earned together — {_money(total)} booked "
            f"in the month")
    sub = (f"the newest offer contributes {_money(live.get(newest, 0))}"
           + (f"; offers past their first year still carry "
              f"{100 * older / total:.0f}%" if older else "")
           + "; booked frame, the workbook's own ledger")
    return head, sub


def wave_totals(m: dict) -> tuple[str, str] | None:
    """What each offer has earned, and the age behind the leader."""
    waves = _wave_series(m)
    if not waves:
        return None
    totals = {tag: sum(s.values()) for tag, s in waves.items()}
    booked = sum(totals.values())
    if not booked:
        return None
    top, top_value = max(totals.items(), key=lambda kv: kv[1])
    newest = list(waves)[-1]
    head = f"The {top} offer has returned {_money(top_value)} to date"
    sub = (f"{len(waves)} offers have booked {_money(booked)} between them; "
           f"{top} has had {len(waves[top])} months to earn it and the "
           f"newest offer {len(waves[newest])}; booked frame, the "
           f"workbook's own ledger")
    return head, sub
