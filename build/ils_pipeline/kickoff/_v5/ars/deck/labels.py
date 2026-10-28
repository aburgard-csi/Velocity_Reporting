# Ported from v5 02-Scripts/ars/deck/labels.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
"""Human labels for keys that would otherwise leak jargon onto a slide.

One map, shared by the deck and any report that speaks to humans. Raw keys
stay in the JSON; a person reads words.
"""

LABELS = {
    "all": "All accounts", "responders": "Responders",
    "mailed_nonresp": "Mailed non-responders", "not_mailed": "Not mailed",
    "business": "Business", "personal": "Personal",
    "new_accounts": "Opened last 12 mo", "recently_inactive": "Recently inactive",
    "ics": "ICS accounts", "mrpc": "MRPC accounts",
}


def label(key: str) -> str:
    return LABELS.get(str(key), str(key).replace("_", " "))


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


def signed(v, fmt: str = "g") -> str:
    """Signed number grammar: +2 / -0.1, and plain 0 for a zero -- never
    '+-0.1' (a literal '+' prefix on a negative) and never '+0.0'."""
    if v is None:
        return "--"
    rendered = format(float(v), "+" + fmt)
    if rendered.lstrip("+-").strip("0.") == "":
        return "0"
    return rendered


def clip(text, n: int) -> str:
    """Ellipsized clip: a cut is VISIBLE, and short text never cuts --
    'Northern Lights'[:14] printing 'Northern Light' is how a truncation
    masquerades as a different name (M4 sweep)."""
    text = str(text)
    return text if len(text) <= n else text[:n - 1] + "\u2026"


def coverage_note(shown: int, total: int, noun: str) -> str | None:
    """"showing 10 of 12 lists", or None when nothing was dropped.

    A headline that counts the whole set over a slide that renders part of
    it reads as completeness (#71). Every capped surface states its coverage
    through this, so the sentence is worded the same way everywhere.
    """
    if shown >= total:
        return None
    return f"showing {shown:,} of {total:,} {noun}"
