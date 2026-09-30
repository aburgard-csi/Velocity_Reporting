"""The deposit slides: what the book's credits look like, and who is paid here.

Eleven slides, in the order they are read:

    deposit_overview        the descriptive portrait -- volume, reach, rhythm
                            of money arriving. The opening of the chapter.
    recurring_credits       who is paid HERE, and how regularly. Primacy.
    credits_stopped         who WAS paid here and no longer is. Risk.
    deposit_milestones      when money last arrived.
    deposit_spread          a few accounts carry the book.
    falling_and_slowing     balance draining AND inflow slowing, together.
    income_shape            salaried or gig: what KIND of income.
    tax_refunds             the windfall with a calendar.
    overdraft_and_income    do irregular earners overdraft more.
    deposit_primacy         pay lands here and the balance is fed.
    inflow_against_outflow  what arrives against what leaves on cards.

Two rules every renderer keeps, and a test holds each one:

    Read every metric BEFORE calling h["slide"](). The register assigns a
    renderer's reads to the slide registered next once the slide exists,
    so a rail built afterwards lands on the following slide's provenance.

    Place every picture with rail=True. Each of these slides carries a
    rail, and a picture centred across the whole field prints under it.

Section A's integrity numbers -- match rate, unmatched, orphans -- are
deliberately NOT on any of these. `extract_check` is this kit's existing
data-quality section and it reaches no slide either; the deck's chapters carry
findings, not plumbing. Those numbers live in the run output, in the warnings,
and in `tables/dep_coverage.csv` where they can be trended.

But the integrity numbers GATE these slides. Every renderer below refuses when
the join is too weak to present, because a deposit slide drawn on a broken
join is worse than no deposit slide -- it looks exactly like a finding.

Keys: dep_* . Module-level so each can be exercised against a stub harness the
way attrition_slides.py's are.
"""

from __future__ import annotations

from ..core.deposits import MIN_MATCH_PCT

from .txn_common import RAIL_EDGE

DEFAULT_MARGIN_L = 1.18
# MIN_MATCH_PCT is the loader's: the report's READ THIS FIRST line and the
# transaction join warning read the same name, so the three cannot disagree.
# A rate on fewer accounts than this is noise wearing a percentage.
MIN_COHORT = 30

RHYTHM_HEADERS = {"rhythm": "How often money arrives", "accounts": "Accounts",
                  "pct_of_matched": "% of matched"}
STOPPED_HEADERS = {"month_last_paid": "Last paid", "accounts": "Accounts"}


def _gate(t) -> str | None:
    """The one guard all three share: is the join sound enough to present."""
    pct = t.get("dep_match_pct")
    if pct is None:
        return "no deposits file"
    if pct < MIN_MATCH_PCT:
        return (f"deposits joined only {pct}% of the base -- under "
                f"{MIN_MATCH_PCT}% nothing here is presentable")
    if (t.get("dep_scored_n") or 0) < MIN_COHORT:
        return f"only {t.get('dep_scored_n')} accounts matched the deposits file"
    return None


def _month_label(ym) -> str:
    """'2025-08' -> 'Aug 25'. Twelve bare month numbers across a year
    boundary say nothing about the year turning."""
    text = str(ym)
    try:
        year, month = int(text[:4]), int(text[5:7])
    except ValueError:
        return text
    names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    if not 1 <= month <= 12:
        return text
    return f"{names[month - 1]} {year % 100:02d}"


def _money(v) -> str:
    if v is None:
        return "--"
    v = float(v)
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}bn"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.0f}m"
    return f"${v:,.0f}"


def deposit_overview(h, t) -> str | None:
    """The descriptive portrait: how much arrives, how often, for how many.

    Deliberately the first deposit slide. Every figure after it is a share or
    a rate, and a reader who has not been told the size of the thing cannot
    judge whether 3.6% is large.
    """
    gate = _gate(t)
    if gate:
        return f"What deposits look like ({gate})"
    series = t.get("dep_book_monthly") or []
    if not series:
        return "What deposits look like (missing dep_book_monthly)"

    total = sum(r[2] for r in series if len(r) > 2)
    months = len(series)
    peak = max(series, key=lambda r: r[1]) if series else None
    per_month = int(round(sum(r[1] for r in series) / months)) if months else 0
    items = [
        ("Accounts depositing", f"{peak[1]:,}" if peak else "--",
         "in the busiest month"),
        ("Typical month", f"{per_month:,}", "accounts receiving a credit"),
        ("Matched to the book", f"{t.get('dep_match_pct')}%",
         f"{t.get('dep_matched_n'):,} of {t.get('dep_n'):,}"),
    ]
    head = (f"{_money(total)} arrived across {months} months",
            "Every credit the core recorded, before any judgement "
            "about what kind")
    slide, top = h["slide"](head, "What deposits look like")

    # A LINE, not a table. Twelve months of dollars is a shape, and a shape
    # read as twelve rows of digits is a shape nobody reads.
    path = h["chart"]("dep_inflow", h["charts"].line_series,
                      [[_month_label(r[0]), r[2]] for r in series],
                      ylabel="dollars in", money=True)
    if path:
        h["picture"](slide, path, top=top + 0.05, max_h=4.6, rail=True)
    h["rail"](slide, items, top=top)
    return None


def recurring_credits(h, t) -> str | None:
    """Primacy: is this where the member's pay lands.

    The rhythm mix carries the evidence and sits ON the slide rather than in
    an appendix, because "probable direct deposit" is an inference and a
    reader is entitled to see what it was inferred from.
    """
    gate = _gate(t)
    if gate:
        return f"Who is paid here ({gate})"
    mix = t.get("dep_cadence_mix") or []
    if not mix:
        return "Who is paid here (missing dep_cadence_mix)"

    pct = t.get("dep_recurring_pct")
    rhythmic = sum(r[1] for r in mix
                   if r[0] not in ("irregular", "too few deposits"))
    scored = t.get("dep_scored_n") or 1
    items = [
        ("Probable direct deposit", f"{pct}%" if pct is not None else "--",
         "rhythmic AND steady in amount"),
        ("On some rhythm", f"{100 * rhythmic / scored:.0f}%",
         "before the amount test"),
        ("Median recurring credit", _money(t.get("dep_median_amount")),
         "per deposit"),
    ]
    head = (f"{pct}% of matched accounts are paid here on a rhythm"
            if pct is not None else "Most credits arrive without a rhythm",
            "Probable, not certain: the extract carries no flag")
    slide, top = h["slide"](head, "Who is paid here")

    # One horizontal 100% bar. charts.py::composition exists for exactly this
    # and its own docstring calls it "a different form from the bar charts
    # around it, and far less blue" -- which is the point: three deposit
    # slides in a row must not be three of the same chart.
    path = h["chart"]("dep_rhythm", h["charts"].composition,
                      [[r[0], r[1]] for r in mix], highlight="irregular")
    if path:
        h["picture"](slide, path, top=top + 0.05, max_h=4.2, rail=True)
    h["rail"](slide, items, top=top)
    return None


def credits_stopped(h, t) -> str | None:
    """Risk: members who HAD a recurring credit here and lost it.

    A separate slide from primacy on purpose. That one is a portfolio
    characteristic; this one is a list of members something happened to, and
    it carries an action. Sharing a slide would make the actionable half a
    footnote.
    """
    gate = _gate(t)
    if gate:
        return f"Who stopped being paid here ({gate})"
    n = t.get("dep_stopped_n")
    if n is None:
        return "Who stopped being paid here (missing dep_stopped_n)"

    by_month = t.get("dep_stopped_by_month") or []
    items = [
        ("Lost a recurring credit", f"{n:,}", "had one, then stopped"),
        ("Share of matched", f"{t.get('dep_stopped_pct')}%",
         "of accounts in the deposits file"),
        ("Never had one", "excluded", "nothing to lose"),
    ]
    head = (f"{n:,} members stopped being paid here",
            "Had an established credit, then three missed cycles")
    slide, top = h["slide"](head, "Who stopped being paid here")

    if by_month:
        # A third form again: columns by month. Whether this cohort went in one
        # month or bled out over twelve is the whole reading, and only a shape
        # shows it.
        path = h["chart"]("dep_stopped", h["charts"].tier_bars,
                          [[_month_label(m), k] for m, k in by_month[-12:]],
                          label="accounts", share=False)
        if path:
            h["picture"](slide, path, top=top + 0.05, max_h=4.4, rail=True)
    h["rail"](slide, items, top=top)
    return None


def deposit_milestones(h, t) -> str | None:
    """Section C: when money last arrived. A branch can act on this one."""
    gate = _gate(t)
    if gate:
        return f"When money last arrived ({gate})"
    bands = t.get("dep_quiet_bands") or []
    if not bands:
        return "When money last arrived (missing dep_quiet_bands)"

    stale = sum(b[1] for b in bands
                if b[0] in ("90 - 180 days", "over 180 days"))
    gap = t.get("dep_gap_median_days")
    onset = t.get("dep_onset_median_days")
    items = [("Quiet 90 days or more", f"{stale:,}", "no credit at all"),
             ("Longest gap, typical", f"{gap}d" if gap is not None else "--",
              "against the account's own rhythm"),
             ("Onset", f"{onset}d" if onset is not None else "--",
              "median days from opening to first credit")]
    head = (f"{stale:,} accounts have not been paid in 90 days",
            "Measured at the anchor, not at today")
    slide, top = h["slide"](head, "When money last arrived")

    # A donut: share-of-whole, and a fourth form so the deposit chapter does
    # not become four bar charts in a row.
    path = h["chart"]("dep_quiet", h["charts"].donut,
                      [[b[0], b[1]] for b in bands],
                      center_label="accounts",
                      center_value=f"{sum(b[1] for b in bands):,}")
    if path:
        h["picture"](slide, path, top=top + 0.05, max_h=4.3, rail=True)
    h["rail"](slide, items, top=top)
    return None


def deposit_spread(h, t) -> str | None:
    """Section E: a few accounts carry the book. Concentration, as a shape."""
    gate = _gate(t)
    if gate:
        return f"Where the deposits sit ({gate})"
    dist = t.get("dep_distribution") or []
    conc = t.get("dep_concentration") or []
    if not dist:
        return "Where the deposits sit (missing dep_distribution)"

    top10 = next((c for c in conc if str(c[0]).startswith("top 10")), None)
    pairs = [[str(c[0]), _slice_share(c[0]), int(c[1]), c[3], int(c[1])]
             for c in conc if _slice_share(c[0]) is not None]
    items = [("Median annual inflow",
              _money(t.get("dep_annual_inflow_median")), "per account"),
             ("90th percentile", _money(t.get("dep_annual_inflow_p90")), ""),
             ("Largest single credit",
              _money(t.get("dep_largest_deposit_median")), "median account")]
    head = (f"The top 10% of depositors carry {top10[3]}% of the inflow"
            if top10 else "Inflow is concentrated in a few accounts",
            "Share of depositing accounts against share of the year's inflow")
    slide, top = h["slide"](head, "Where the deposits sit")

    # paired_hbars: share of accounts against share of inflow, per slice.
    # The first cut drew a histogram of decile COUNTS, and deciles have
    # equal counts by construction -- ten identical bars, a chart of
    # nothing. Concentration is two shares side by side, or it is not shown.
    path = None
    if pairs:
        path = h["chart"]("dep_spread", h["charts"].paired_hbars, pairs,
                          "share of depositors", "share of inflow")
    if path:
        h["picture"](slide, path, top=top + 0.05, max_h=4.4, rail=True)
    h["rail"](slide, items, top=top)
    return None


def falling_and_slowing(h, t) -> str | None:
    """Section F: the combination. balance.py sees one half, this sees both."""
    gate = _gate(t)
    if gate:
        return f"Balance falling and inflow slowing ({gate})"
    both = t.get("dep_falling_and_slowing_n")
    if both is None:
        return "Balance falling and inflow slowing (missing dep_falling_and_slowing_n)"

    falling = t.get("dep_falling_only_n") or 0
    slowing = t.get("dep_slowing_only_n") or 0
    held = _money(t.get("dep_falling_and_slowing_dollars"))
    items = [("Doing both", f"{both:,}", "the finding"),
             ("Balance held there", held, ""),
             ("Balance proxy alone", f"{falling:,}",
              "what flight risk sees today")]
    head = (f"{both:,} accounts are draining AND being paid less",
            "Either alone is a month. Both together is a member leaving")
    slide, top = h["slide"](head, "Balance falling and inflow slowing")

    # category_blocks: one hero block for the overlap, two supporting
    # blocks for the halves. The first cut used grouped_bars and had to
    # invent a second all-zero series to satisfy its signature -- three
    # grey zero-height bars, each labelled 0, on the client's deck.
    # Supporting tiles are a quarter of the figure wide: short names, or
    # the second tile's title runs across the third.
    blocks = [["Both", f"{both:,}", "draining AND being paid less", held],
              ["Falling only", f"{falling:,}", "balance under its average", ""],
              ["Slowing only", f"{slowing:,}", "credits under the prior 3m", ""]]
    path = h["chart"]("dep_both", h["charts"].category_blocks, blocks)
    if path:
        h["picture"](slide, path, top=top + 0.05, max_h=4.2, rail=True)
    h["rail"](slide, items, top=top)
    return None


def income_shape(h, t) -> str | None:
    """Section L: what kind of income, which is a different question from
    whether it recurs. Salaried and hourly separate here."""
    gate = _gate(t)
    if gate:
        return f"What kind of income ({gate})"
    bands = t.get("dep_volatility_bands") or []
    if not bands:
        return "What kind of income (missing dep_volatility_bands)"

    uneven = sum(b[1] for b in bands if "uneven" in str(b[0]))
    items = [("Uneven income", f"{uneven:,}", "harder to lend to, easier to lose"),
             ("Median volatility", f"{t.get('dep_volatility_median') or '--'}",
              "0 is a salary, 1 is gig work"),
             ("Pay cuts seen", f"{t.get('dep_pay_cut_n') or 0:,}",
              "stream held its rhythm, lost its amount")]
    head = (f"{uneven:,} members are paid unevenly month to month",
            "Variation in total inflow, not in one credit")
    slide, top = h["slide"](head, "What kind of income")

    # health_bars: a distribution across bands, each with its share of the
    # whole -- which is what volatility bands are. (rate_bars went to the
    # overdraft slide, where the value IS a rate.)
    path = h["chart"]("dep_volatility", h["charts"].health_bars,
                      [[b[0], b[1]] for b in bands])
    if path:
        h["picture"](slide, path, top=top + 0.05, max_h=4.3, rail=True)
    h["rail"](slide, items, top=top)
    return None


def tax_refunds(h, t) -> str | None:
    """Section L: a windfall with a calendar. Timing is what identifies it."""
    gate = _gate(t)
    if gate:
        return f"Tax refunds ({gate})"
    n = t.get("dep_refund_n")
    if not n:
        return "Tax refunds (missing dep_refund_n)"

    days = t.get("dep_payday_weekday") or []
    items = [("Accounts receiving one", f"{n:,}",
              f"{t.get('dep_refund_pct')}% of matched"),
             ("Median refund", _money(t.get("dep_refund_median")), ""),
             ("Inferred, not labelled", "timing",
              "the core does not flag a refund")]
    head = (f"{_money(t.get('dep_refund_dollars'))} arrived as probable refunds",
            "Largest Feb-Apr credit at twice the account's own median")
    slide, top = h["slide"](head, "Tax refunds")

    # histogram: counts per band, and the band here is the weekday. The
    # payday profile is the better picture than the refund count -- it says
    # WHEN to reach people. (ticket_bars was the first choice; it wants a
    # blended figure and a third column, and the deck's first real render
    # crashed on it.)
    if days:
        path = h["chart"]("dep_payday", h["charts"].histogram,
                          [[d[0], d[1]] for d in days],
                          xlabel="weekday the recurring credit lands")
        if path:
            h["picture"](slide, path, top=top + 0.05, max_h=4.2, rail=True)
    h["rail"](slide, items, top=top)
    return None


def overdraft_and_income(h, t) -> str | None:
    """Section M: the question the overdraft programme rests on, asked of real
    income data for the first time. Do irregular earners overdraft more."""
    gate = _gate(t)
    if gate:
        return f"Who overdrafts, by how they are paid ({gate})"
    rows = t.get("dep_od_by_rhythm") or []
    if not rows:
        return "Who overdrafts, by how they are paid (missing dep_od_by_rhythm)"

    steady = next((r for r in rows if "on a rhythm" in str(r[0])
                   and "not" not in str(r[0])), None)
    erratic = next((r for r in rows if str(r[0]).startswith("not")), None)
    gap = (round(erratic[3] - steady[3], 1)
           if steady and erratic and steady[3] is not None
           and erratic[3] is not None else None)
    buffer_days = t.get("dep_buffer_median_days")
    items = [("Overdrafting accounts", f"{t.get('dep_od_accounts_n') or 0:,}",
              "at least one item in the window")]
    if gap is not None:
        items.append(("Gap", f"{gap:+.1f}pts", "irregular against regular"))
    if buffer_days is not None:
        items.append(("Buffer, typical", f"{buffer_days}d",
                      "days of spending in the balance"))
    head = (f"Members without a regular payday overdraft {gap} points more"
            if gap and gap > 0 else "Overdrafts against how members are paid",
            "Monthly NSF/OD items from the ODD, crossed with income rhythm")
    slide, top = h["slide"](head, "Who overdrafts, by how they are paid")

    # rate_bars: a rate per band with the base under it. The question is
    # whether irregular earners overdraft MORE, so the bar is the share of
    # each group that overdrafted. The first render handed health_bars the
    # overdrafting COUNTS, and it printed each group's share of all
    # overdrafters instead.
    # mark_weakest=False: the form paints the LOWEST rate red, which is
    # right for a take rate and backwards for an overdraft rate.
    path = h["chart"]("dep_od_rhythm", h["charts"].rate_bars,
                      [[r[0], r[1], None, r[3] or 0] for r in rows],
                      show_n=True, mark_weakest=False)
    if path:
        h["picture"](slide, path, top=top + 0.05, max_h=4.3, rail=True)
    h["rail"](slide, items, top=top)
    return None


def deposit_primacy(h, t) -> str | None:
    """Section N: primacy on where pay lands, not on how often a card is
    swiped. It replaces a proxy on a number already being published."""
    gate = _gate(t)
    if gate:
        return f"Who banks here first ({gate})"
    n = t.get("dep_primacy_n")
    if n is None:
        return "Who banks here first (missing dep_primacy_n)"

    base = t.get("dep_n") or 0
    matched = t.get("dep_matched_n") or 0
    paid = t.get("dep_recurring_n") or 0
    stages = [["Eligible accounts", base, None, None],
              ["Matched to the file", matched, None, _drop(base, matched)],
              ["Paid here on a rhythm", paid, None, _drop(matched, paid)],
              ["And the balance is fed", n, None, _drop(paid, n)]]
    items = [("Primary members", f"{n:,}", f"{t.get('dep_primacy_pct')}% of the base"),
             ("Balance they hold", _money(t.get("dep_primacy_dollars")), ""),
             ("Inflow floor", _money(t.get("dep_primacy_floor")), "a year")]
    head = (f"{n:,} members bank here first",
            "Pay lands here and the balance is fed -- not a swipe count")
    slide, top = h["slide"](head, "Who banks here first")

    # funnel: a tenth form, and the right one -- this IS a narrowing.
    path = h["chart"]("dep_primacy", h["charts"].funnel, stages)
    if path:
        h["picture"](slide, path, top=top + 0.05, max_h=4.5, rail=True)
    h["rail"](slide, items, top=top)
    return None


def _slice_share(label) -> float | None:
    """'top 10%' -> 10.0. The slice's own share of accounts, read from the
    label the chapter wrote, so the two bars are built from one source."""
    text = str(label).strip()
    if not text.startswith("top ") or not text.endswith("%"):
        return None
    try:
        return float(text[4:-1])
    except ValueError:
        return None


def _drop(before: float, after: float):
    """Percentage lost at a funnel stage, or None when unmeasurable."""
    if not before:
        return None
    return round(100 * (before - after) / before, 1)


def inflow_against_outflow(h, t) -> str | None:
    """Sections G and O: what arrives against what leaves.

    Refuses outright when the transaction load was short. That is the whole
    reason this renderer exists rather than the numbers going straight to a
    slide: on RALLY nine of twelve months were partial and the three healthy
    ones made the shortfall look like a season.
    """
    gate = _gate(t)
    if gate:
        return f"What arrives against what leaves ({gate})"
    if t.get("dep_competition_skipped"):
        return (f"What arrives against what leaves (transaction load short in "
                f"{t.get('dep_txn_short_months')} month(s))")
    pair = t.get("dep_vs_card_spend") or []
    if not pair:
        return "What arrives against what leaves (missing dep_vs_card_spend)"

    inflow = next((p[1] for p in pair if "inflow" in str(p[0])), 0)
    spend = next((p[1] for p in pair if "spend" in str(p[0])), 0)
    items = [("Named competitors", f"{t.get('dep_competitor_reach') or 0:,}",
              "seen in the transaction file"),
             ("Not a balance", "direction",
              "cash, transfers and cheques are in neither source")]
    head = (f"{_money(inflow)} in, {_money(spend)} out on cards",
            "Both sides from their own source")
    slide, top = h["slide"](head, "What arrives against what leaves")

    # value_waterfall: an eleventh form, and the only one that shows a
    # position built from two opposing quantities.
    path = h["chart"]("dep_flow", h["charts"].value_waterfall,
                      [["Inflow", inflow], ["Card spend", -spend],
                       ["Net", inflow - spend]])
    if path:
        h["picture"](slide, path, top=top + 0.05, max_h=4.3, rail=True)
    h["rail"](slide, items, top=top)
    return None
