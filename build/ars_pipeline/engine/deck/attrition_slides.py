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

from . import labels
from .txn_common import RAIL_EDGE

DEFAULT_MARGIN_L = 1.18
MAX_ROWS = 8

# Rail tiles are four across; each slide's headline tile takes one.
RAIL_CONDITIONS = 3

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
    for closers, ctrl in list(zip(decline, control))[:MAX_ROWS]:
        rows.append([
            closers[0],
            "n/a" if closers[2] is None else f"${closers[2]:,.0f}",
            "n/a" if ctrl[2] is None else f"${ctrl[2]:,.0f}",
            f"{closers[1]:,}",
            "n/a" if closers[4] is None else f"{closers[4]:.0f}%",
        ])
    left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
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

    for tenure, n, months in (t.get("life_divergence_by_tenure") or [])[:2]:
        items.append((tenure, f"{months} mo" if months is not None else "n/a",
                      f"{n:,} closed"))
    h["rail"](slide, items, top=top)
    return None


# --- concurrent_stressors ---


def _money(value) -> str:
    """Whole dollars, thousands-separated. Decks never show cents."""
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "n/a"


def concurrent_stressors(h, t) -> str | None:
    """Render the slide. Returns a skip reason when the section did not run."""
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
           f"{len(available)} condition(s) built from this client's files")
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

    items = [("Two or more", f"{n_multi:,}",
              f"{pct:.1f}% of base" if pct is not None else None)]
    for label in available[:RAIL_CONDITIONS]:
        items.append((labels.clip(label, 22), "", "built"))
    h["rail"](slide, items, top=top)
    return None
