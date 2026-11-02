# Ported from ARS v5 02-Scripts/ars/deck/attrition_slides.py at a491b5c (James Gilmore); logic unchanged.
"""The attrition slides: how much warning, and how many warnings at once.

Two slides that answer adjacent halves of the same question, kept together
because they are read together and neither is large enough to own a file.

    months_of_warning       how far ahead a closure was visible
    concurrent_stressors    how many warnings land on one account

Both carry their base and their coverage on the slide itself, because a rate
whose denominator is unstated and a count whose signal set is unstated are the
two ways this chapter has previously been misread.

--- months_of_warning ---

Every other attrition surface reports what already happened. This one reports
how far ahead it was visible, which is the only version of the question a
credit union can act on.

The slide always carries the CONTROL alongside the closers. Without it,
"accounts that closed were spending less" is circular -- closing accounts
spend less by definition. And it always carries the base at each offset,
because the cohort thins with depth and a curve that hides that reads as
solid at month 12 as at month 1.

Keys: life_* and stress_* . Module-level so both can be exercised against a
stub harness the way txn_compete.py's slides are.
"""

from __future__ import annotations

import re

import periods as _rpe_periods

from . import labels
from .txn_common import RAIL_EDGE, absent_note

DEFAULT_MARGIN_L = 1.18
MAX_ROWS = 8
# A note under a table or chart: the size every footnote in the cut keeps to (Sheila's 1798 review,
# 2026-10-30: nothing under 10.5pt but the slide number).
NOTE_PT = 10.5
NOTE_Y = 6.30


def _note(h, slide, text, left=None, width=None):
    """A short stated note at the foot of the content (what a slide left out, and why). Drawn only
    through the bundle's own text helper; a stub harness without one simply records nothing."""
    if not text or not h.get("text"):
        return
    left = h.get("MARGIN_L", DEFAULT_MARGIN_L) if left is None else left
    width = (RAIL_EDGE - left) if width is None else width
    h["text"](slide, left + 0.02, NOTE_Y, width, 0.4, text, size=NOTE_PT, color=h.get("GREY"))


def band_phrase(label) -> str:
    """A tenure band as words: "5-10 yr" -> "5-10 years", "0-6 mo" -> "0-6 months",
    "< 1 yr" -> "under 1 year". v5 wrote "in year 5-10 yr" (Sheila's 1798 review, 2026-10-30)."""
    text = str(label).strip()
    under = text.startswith("<")
    text = text.lstrip("< ").strip()
    m = re.fullmatch(r"(.*?)\s*(yr|yrs|mo|mos)\.?", text)
    if m:
        num, unit = m.group(1).strip(), m.group(2)
        word = "year" if unit.startswith("yr") else "month"
        text = f"{num} {word}{'' if num == '1' else 's'}"
    return f"under {text}" if under else text

# Metric keys are the machine contract and do not change. What a CSM reads on
# the slide is not "pct_of_base". Kept as two dicts rather than one merged
# mapping so each slide's columns are readable next to the slide that uses them.
WARNING_HEADERS = {"offset": "Months before close", "closers": "Closing accounts",
                   "control": "Still open", "n": "Accounts measured",
                   "active": "% still active"}
STRESSOR_HEADERS = {"stressors": "Stressors", "accounts": "Accounts",
                    "pct_of_base": "% of base", "deposits": "Deposits held"}


def months_of_warning(h, t) -> str | None:
    """Render the slide, or return a skip reason when the section did not run."""
    decline = t.get("life_decline") or []
    control = t.get("life_control") or []
    if not decline or not control:
        return "Months of warning (missing life_decline / life_control)"

    warning = t.get("life_divergence_month")
    ratio = t.get("life_divergence_ratio") or 0.8
    if warning is not None:
        head = (f"Closing accounts were already fading {warning} month"
                f"{'s' if warning != 1 else ''} before they closed")
        sub = (f"spend below {int(100 * ratio)}% of still-open accounts from "
               f"that month onward, measured over the same calendar months")
    else:
        # Not the same as zero. Zero would read as "they leave without
        # warning", which is a much stronger claim than "we did not detect it".
        head = "No sustained fade was detectable before closure on this book"
        sub = ("closing accounts did not stay below "
               f"{int(100 * ratio)}% of still-open accounts for any run of "
               "months; the signal may be shorter than a month or absent")

    slide, top = h["slide"]((head, sub), "How much warning do we get")

    rows = [[WARNING_HEADERS["offset"], WARNING_HEADERS["closers"],
             WARNING_HEADERS["control"], WARNING_HEADERS["n"],
             WARNING_HEADERS["active"]]]
    # A month with no measured value is left out of the table and stated under it, never printed
    # as "n/a" in a cell (Sheila's 1798 review, 2026-10-30).
    unmeasured = []
    for closers, ctrl in list(zip(decline, control))[:MAX_ROWS]:
        if closers[2] is None or ctrl[2] is None or closers[4] is None:
            unmeasured.append(str(closers[0]))
            continue
        rows.append([
            closers[0],
            f"${closers[2]:,.0f}",
            f"${ctrl[2]:,.0f}",
            f"{closers[1]:,}",
            f"{closers[4]:.0f}%",
        ])
    left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
    if len(rows) > 1:
        h["table"](slide, rows, left, top, RAIL_EDGE - left)

    items = [("Card spend", f"{warning} mo" if warning is not None else "none",
              "before closure")]

    # Deposits, when the client sent the file. Shown beside card spend rather
    # than instead of it: the gap between the two is the finding. People stop
    # routing pay somewhere before they stop swiping there, so a deposit
    # warning that arrives EARLIER is the case for watching deposits first.
    deposit = t.get("life_deposit_divergence_month")
    if deposit is not None:
        lead = t.get("life_deposit_lead_months")
        note = ("same month as spend" if lead == 0 else
                f"{abs(lead)} mo {'earlier' if lead and lead > 0 else 'later'}"
                if lead is not None else "before closure")
        items.append(("Deposits", f"{deposit} mo", note))

    # A tenure band with no detectable fade gets no tile (v5 drew "n/a"); the bands left out are
    # named in a note, so the absence is stated, never zeroed (Sheila's 1798 review, 2026-10-30).
    tenure_rows = t.get("life_divergence_by_tenure") or []
    for tenure, n, months in [r for r in tenure_rows if r[2] is not None][:2]:
        items.append((tenure, f"{months} mo", f"{n:,} closed"))
    h["rail"](slide, items, top=top)
    notes = []
    if unmeasured:
        notes.append("Months before close with no measured spend, left out: "
                     f"{absent_note(unmeasured, 'months')}.")
    quiet = [str(r[0]) for r in tenure_rows if r[2] is None]
    if quiet:
        notes.append(f"No sustained fade was detectable for {absent_note(quiet, 'tenure bands')}.")
    _note(h, slide, " ".join(notes))
    return None


# --- concurrent_stressors ---


def _money(value) -> str:
    """The deck's one money grammar (labels.money): $1.2M / $482K / $73. This printed whole
    dollars with every digit ($1,234,567) beside slides that said $1.2M (2026-10-28)."""
    from .labels import money
    try:
        return money(float(value))
    except (TypeError, ValueError):
        return "n/a"


def concurrent_stressors(h, t) -> str | None:
    """Accounts under several stresses, on every base this client's files allow (combine group J,
    Sheila's 1798 review, 2026-10-30). The ODD-only count (stress_2plus_n) and the count once the
    transaction file adds "Banking elsewhere" (stress_txn_2plus_n) were two slides, 908 against
    20,991 on 1798, with nothing saying why. With both on hand they are one slide, side by side,
    each base and its conditions stated; with one, that one is drawn on its own."""
    odd = t.get("stress_by_count") or []
    txn = t.get("stress_txn_by_count") or []
    if odd and txn:
        return _stressors_both_bases(h, t)
    if not odd and txn:
        from .txn_attrition import stresses_across_files
        return stresses_across_files(h, t, t.get("fin_base_label", "accounts"))
    return _stressors_odd_only(h, t)


def _conditions(names) -> str:
    return ", ".join(str(n) for n in names) if names else "none"


def _stressors_both_bases(h, t) -> str | None:
    odd = t.get("stress_by_count") or []
    txn = t.get("stress_txn_by_count") or []
    n_odd = t.get("stress_2plus_n") or 0
    n_txn = t.get("stress_txn_2plus_n") or 0
    odd_avail = list(t.get("stress_available") or [])
    txn_avail = list(t.get("stress_txn_available") or [])
    added = [c for c in txn_avail if c not in odd_avail]
    skipped = [c for c in (t.get("stress_txn_skipped") or []) if c]

    head = (f"{n_odd:,} accounts carry 2+ stressors on the ODD alone; "
            f"{n_txn:,} once banking elsewhere is counted")
    sub = (f"two bases side by side: the ODD's conditions on "
           f"{t.get('stress_base') or 'the ODD base'}, and the same plus the transaction "
           f"file on {t.get('stress_txn_base') or 'the transacting base'}")
    slide, top = h["slide"]((head, sub), "Accounts under several stresses")

    by_odd = {r[0]: r for r in odd}
    by_txn = {r[0]: r for r in txn}
    table = [["Stressors", "ODD only", "% of base", "With transactions", "% of base"]]
    for k in sorted(set(by_odd) | set(by_txn), key=lambda v: (str(type(v)), v)):
        a, b = by_odd.get(k), by_txn.get(k)
        table.append([k,
                      f"{a[1]:,}" if a else "none", f"{a[2]:.1f}%" if a else "",
                      f"{b[1]:,}" if b else "none", f"{b[2]:.1f}%" if b else ""])
    left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
    h["table"](slide, table, left, top, RAIL_EDGE - left)

    def tile_note(pct_key, dep_key):
        parts = []
        if t.get(pct_key) is not None:
            parts.append(f"{t[pct_key]:.1f}% of base")
        if t.get(dep_key) is not None:
            parts.append(f"{_money(t[dep_key])} held")
        return ", ".join(parts) or None

    items = [("2+ on the ODD alone", f"{n_odd:,}",
              tile_note("stress_2plus_pct", "stress_2plus_deposits")),
             ("2+ with transactions", f"{n_txn:,}",
              tile_note("stress_txn_2plus_pct", "stress_txn_2plus_deposits"))]
    if t.get("stress_txn_2plus_competitor_dollars") is not None:
        items.append(("To competitors", _money(t.get("stress_txn_2plus_competitor_dollars")),
                      "from the with-transactions 2+"))
    h["rail"](slide, items, top=top)

    note = (f"ODD only counts: {_conditions(odd_avail)}. "
            f"With transactions adds: {_conditions(added)}.")
    if skipped:
        note += f" Not available for this client: {_conditions(skipped)}."
    _note(h, slide, note)
    return None


def _stressors_odd_only(h, t) -> str | None:
    """The ODD-only slide. Returns a skip reason when the section did not run."""
    rows = t.get("stress_by_count") or []
    if not rows:
        return "Concurrent stressors (missing stress_by_count)"

    n_multi = t.get("stress_2plus_n") or 0
    pct = t.get("stress_2plus_pct")
    available = t.get("stress_available") or []
    skipped = t.get("stress_skipped") or []

    if n_multi:
        head = (f"{n_multi:,} accounts carry two or more stressors at once, "
                f"holding {_money(t.get('stress_2plus_deposits'))}")
    else:
        # Zero is a finding. A blank slide reads as a broken section.
        head = "No account carries two stressors at once"

    sub = (f"base: {t.get('stress_base') or 'unstated'}; "
           f"conditions: {_conditions(available)}")
    if skipped:
        sub += f" -- not available: {', '.join(skipped)}"

    slide, top = h["slide"]((head, sub), "Accounts under several stresses")

    columns = t.get("stress_by_count_columns") or [
        "stressors", "accounts", "pct_of_base", "deposits"]
    table = [[STRESSOR_HEADERS.get(c, str(c).replace("_", " ").capitalize())
              for c in columns]] + [
        [r[0], f"{r[1]:,}", f"{r[2]:.1f}%", _money(r[3])] for r in rows]
    left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
    h["table"](slide, table, left, top, RAIL_EDGE - left)

    # The conditions are named in the subtitle; v5 also gave each one a tile with no value and
    # "built" under it, which read as empty cards (Sheila's 1798 review, 2026-10-30).
    items = [("Two or more", f"{n_multi:,}",
              f"{pct:.1f}% of base" if pct is not None else None)]
    if t.get("stress_2plus_deposits") is not None:
        items.append(("Deposits held", _money(t.get("stress_2plus_deposits")), "by those accounts"))
    h["rail"](slide, items, top=top)
    return None


# --- cohort_survival ---


def cohort_survival(h, t) -> str | None:
    """Every month of openings and how many are still here (legacy A9.0b,
    #245). The latest cohorts are young by construction; the base under
    each point is on the chart so 99% at month one is not read as strength."""
    rows = t.get("attrition_cohort_survival") or []
    if not rows:
        return "New accounts, cohort by cohort (missing attrition_cohort_survival)"
    fy = t.get("attrition_cohort_first_year_rate")
    base = t.get("attrition_cohort_first_year_base") or 0
    if fy is not None and base:
        head = (f"{fy:.1f}% of the accounts opened a year ago have already "
                f"closed -- {base:,} in that cohort")
    else:
        head = "No opening cohort has had a full year yet"
    seasoned = t.get("attrition_closures_seasoned_pct")
    sub = ("opened, still open and closed for each month of openings; "
           "survival is still open over opened")
    if seasoned is not None:
        sub += (f"; {seasoned:.0f}% of the window's closures were seasoned "
                f"accounts, {100 - seasoned:.0f}% the window's own cohort")
    slide, top = h["slide"]((head, sub), "New accounts, cohort by cohort")
    # The cohort months arrive as v5's "Jan24"; RPE's month-axis guard refuses anything but
    # MMM'YY and Deck.chart swallowed the refusal, so this chart went missing on 1798 (Sheila's
    # 1798 review, 2026-10-30). The labels go through periods.axis_months here.
    months = _rpe_periods.axis_months([r[0] for r in rows])
    chart_rows = [[mo, r[1], r[4]] for mo, r in zip(months, rows)]
    path = h["chart"]("attrition_cohort", h["charts"].line_with_base, chart_rows,
                      ylabel="% still open")
    if path and h.get("picture"):
        h["picture"](slide, path, top=top + 0.1, max_h=4.4, rail=True)
    items = []
    if fy is not None:
        items.append(("Cohort at one year", f"{fy:.1f}%", f"{base:,} accounts" if base else "closed"))
    newest, oldest = rows[-1], rows[0]
    items.append((f"Opened {months[-1]}", f"{newest[1]:,}", f"{newest[2]:,} still open"))
    items.append((f"Opened {months[0]}", f"{oldest[4]:.0f}% kept",
                  f"{oldest[3]:,} of {oldest[1]:,} closed"))
    h["rail"](slide, items, top=top)
    return None


# --- product_and_hazard ---

HAZARD_HEADERS = {"tenure": "Tenure", "reached_and_resolved": "Accounts judged",
                  "closed_in_bucket": "Closed in band", "hazard_pct": "Closure hazard"}
MAX_PRODUCTS = 8


def product_and_hazard(h, t) -> str | None:
    """Two cuts computed on every run and shown nowhere (#245): closure
    rate by product (legacy A9.5) and the closure hazard by tenure (A9.7)."""
    products = t.get("attrition_by_product") or []
    hazard = t.get("attrition_hazard") or []
    if not products and not hazard:
        return "Where closures cluster (missing attrition_by_product and attrition_hazard)"
    parts = []
    if products:
        worst = max(products, key=lambda r: r[3] or 0)
        parts.append(f"{worst[0]} closes at {worst[3]:.1f}%")
    peak = t.get("attrition_hazard_peak")
    if peak:
        parts.append(f"the hazard peaks at {peak[1]:.1f}% at {band_phrase(peak[0])}")
    head = " and ".join(parts) if parts else "Where closures cluster"
    sub = (f"book closure {t.get('attrition_rate') or 0:.1f}%; product bars show "
           f"the window rate, the table shows the hazard: of accounts that lived "
           f"to the start of a band, the share that closed inside it")
    slide, top = h["slide"]((head, sub), "Where closures cluster")
    if products:
        rows = [[r[0], None, r[2], r[3]] for r in products[:MAX_PRODUCTS]]
        path = h["chart"]("attrition_product", h["charts"].branch_bars, rows,
                          t.get("attrition_rate") or 0.0)
        if path and h.get("picture"):
            h["picture"](slide, path, top=top + 0.1, max_h=3.3, rail=True)
    if hazard:
        columns = t.get("attrition_hazard_columns") or list(HAZARD_HEADERS)
        judged = [r for r in hazard[:MAX_ROWS] if r[3] is not None]
        table = [[HAZARD_HEADERS.get(c, str(c)) for c in columns]] + [
            [r[0], f"{r[1]:,}", f"{r[2]:,}", f"{r[3]:.1f}%"] for r in judged]
        left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
        if judged:
            h["table"](slide, table, left, top + 3.6, RAIL_EDGE - left)
        unjudged = [str(r[0]) for r in hazard[:MAX_ROWS] if r[3] is None]
        if unjudged:
            _note(h, slide, f"No hazard could be measured for {absent_note(unjudged)}; "
                            f"left out of the table.")
    items = []
    if products:
        items.append(("Products cut", f"{len(products)}", "100+ at risk each"))
    if peak:
        items.append(("Peak hazard", f"{peak[1]:.1f}%", f"at {band_phrase(peak[0])}"))
    h["rail"](slide, items, top=top)
    return None


# --- where_the_risk_sits ---

AXES_HEADERS = {"quadrant": "Spend against swipes", "accounts": "Accounts",
                "pct_of_prior_spenders": "% of spenders",
                "prior_spend_annualized": "Prior spend / yr"}


def where_the_risk_sits(h, t) -> str | None:
    """The Part 2 metrics on one page (#245): the spend-against-swipes
    quadrants, the at-risk rate by swipe tier, closure duration in months
    and the never-mailed control. Builds on whichever of them the run
    produced; skips only when none did."""
    axes = t.get("retention_axes") or []
    tiers = t.get("retention_by_swipe_tier") or []
    months = t.get("attrition_life_dist_months") or []
    gap = t.get("attrition_mailed_vs_nevermailed_pp")
    if not (axes or tiers or months or gap is not None):
        return "Where the risk sits (missing retention_axes and the Part 2 cuts)"
    swipe_only = t.get("retention_swipe_only_decline_n") or 0
    if axes and swipe_only:
        head = (f"{swipe_only:,} accounts are visiting less on the same dollars "
                f"-- a spend-only read could not see them")
    elif tiers:
        worst = max(tiers, key=lambda r: r[2] or 0)
        head = f"{worst[0]} cardholders carry the highest at-risk rate, {worst[2]:.0f}%"
    else:
        head = "Where the risk sits"
    sub = ("recent three months against the prior three, on spend and on swipes; "
           "at-risk by the ODD's own swipe tier; how soon closures come")
    slide, top = h["slide"]((head, sub), "Where the risk sits")
    if axes:
        columns = t.get("retention_axes_columns") or list(AXES_HEADERS)
        table = [[AXES_HEADERS.get(c, str(c)) for c in columns]] + [
            [r[0], f"{r[1]:,}", f"{r[2]:.1f}%", _money(r[3])] for r in axes]
        left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
        h["table"](slide, table, left, top, RAIL_EDGE - left)
    items = []
    for label, n, pct, _spend in [r for r in tiers if r[2] is not None][:2]:
        items.append((labels.clip(str(label), 18), f"{pct:.0f}%", f"{n:,} at risk of tier"))
    if months:
        first = [r for r in months if r[0] in ("< 1 mo", "1-3 mo")]
        early = sum(r[2] for r in first if r[2] is not None)
        items.append(("Closed within 3 mo", f"{early:.0f}%", "of the window's closures"))
    if gap is not None:
        items.append(("Mailed vs never mailed", f"{gap:+.1f} pts", "closure rate"))
    h["rail"](slide, items[:5], top=top)
    return None
