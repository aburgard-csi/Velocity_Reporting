# Ported from v5 02-Scripts/ars/deck/labels.py at 7ba1e63. Logic unchanged; only money(), the one label helper deckkit exposes.
"""Human labels for keys that would otherwise leak jargon onto a slide.

One map, shared by the deck and any report that speaks to humans. Raw keys
stay in the JSON; a person reads words.
"""

def money(v) -> str:
    """The deck's one number grammar: $1.2M / $482K / $73, and -$7 for a
    negative -- never '$-7' (M4 sweep). Every module imports this; three
    competing formats in one deck read as carelessness."""
    if v is None:
        return "--"
    v = float(v)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1_000_000:
        return f"{sign}${a/1_000_000:.1f}M"
    if a >= 10_000:
        return f"{sign}${a/1_000:.0f}K"
    if a >= 1_000:
        return f"{sign}${a/1_000:.1f}K"
    return f"{sign}${a:,.0f}"

