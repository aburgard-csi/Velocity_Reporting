# Ported from ARS v5 02-Scripts/ars/deck/labels.py at a491b5c (James Gilmore); logic unchanged.
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


def window_months(t) -> int:
    """N in the transaction window (ti/window.py): the pack's txn_window_months, else the months
    the files covered, else 12."""
    for key in ("txn_window_months", "txn_months_covered"):
        v = (t or {}).get(key)
        if v:
            return int(v)
    return 12


def window(t, prefix: str = "in") -> str:
    """The window in words for slide copy: 'in the last 12 months', 'over the last 3 months',
    'last month' (prefix='') -- never 'a year', which is only true when N is 12."""
    n = window_months(t)
    span = "the last month" if n == 1 else f"the last {n} months"
    if not prefix:
        span = span[len("the "):]
    return f"{prefix} {span}".strip()


def window_title(t) -> str:
    """'Last 12 months', for a rail label."""
    w = window(t, prefix="")
    return w[0].upper() + w[1:]


def money(v) -> str:
    """The deck's one number grammar: $1.2M / $482K / $73, and -$7 for a
    negative -- never '$-7' (M4 sweep). Every module imports this; three
    competing formats in one deck read as carelessness."""
    if v is None:
        return "--"
    v = float(v)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1_000_000_000:
        return f"{sign}${a/1_000_000_000:.1f}B"
    if a >= 1_000_000:
        return f"{sign}${a/1_000_000:.1f}M"
    if a >= 10_000:
        return f"{sign}${a/1_000:.0f}K"
    if a >= 1_000:
        return f"{sign}${a/1_000:.1f}K"
    return f"{sign}${a:,.0f}"


def count(v) -> str:
    """A count: thousands-separated, no decimals, never a float's tail (2026-10-28)."""
    if v is None:
        return "--"
    return f"{float(v):,.0f}"


def signed_count(v) -> str:
    """A signed count: +14,150 / -327 / 0 -- a change in accounts is a count, never a percent
    (the competitor momentum column printed the net new accounts as "+14150%", 2026-10-28)."""
    if v is None:
        return "--"
    v = float(v)
    if round(v) == 0:
        return "0"
    return f"{'+' if v > 0 else '-'}{abs(v):,.0f}"


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


# --- names on a slide ------------------------------------------------------------------------------
# Merchant and institution names reach the deck as the transaction file carries them ("CIRCLEK",
# "WAL MART", "LOWES") and v5 cased them with str.title(), which prints "Lowe'S", "Circlek" and
# "Mountain America Cu" (Sheila's 1798 slide review, 2026-10-30). display_name() is the one casing
# rule every merchant / institution label goes through. RPE addition, not in v5.
import re as _re

# A collapsed or split key the casing cannot recover by itself, by its normalised key (upper case,
# no apostrophes / periods, hyphens as spaces); a key is also looked up with its spaces removed.
NAME_ALIASES = {
    "CIRCLEK": "Circle K", "CIRCLE K": "Circle K",
    "WALMART": "Walmart", "WAL MART": "Walmart",
    "LOWES": "Lowe's",
    "MOUNTAIN AMERICA CU": "Mountain America CU",
    "PAYPAL": "PayPal",
}
# Kept upper case wherever they fall (by the token's letters, periods dropped: "N.A." is "NA").
ACRONYMS = {"CU", "FCU", "USAA", "ATM", "BNPL", "LLC", "NA", "AT&T", "CVS", "HSBC", "TD", "PNC",
            "BMO", "USA", "ACH", "P2P", "MCC", "IRS", "DMV", "ICS", "ARS", "HEB", "QT", "BP", "TJ"}
# Brands whose casing is neither title nor upper.
SPECIAL_CASE = {"PAYPAL": "PayPal", "EBAY": "eBay", "ITUNES": "iTunes", "IPHONE": "iPhone",
                "MCDONALDS": "McDonald's", "MCDONALD'S": "McDonald's"}
_SMALL_WORDS = {"of", "and", "the", "at", "for", "in", "on", "by", "to"}
# All-caps tokens without a vowel that are words, not acronyms.
_NOT_ACRONYM = {"MR", "MRS", "MS", "DR", "ST", "JR", "SR", "MT", "FT", "N", "S", "E", "W"}
_VOWELS = set("AEIOUY")


def _name_key(s: str) -> str:
    s = s.upper().replace("\u2019", "'").replace("-", " ")
    s = _re.sub(r"['.]", "", s)
    return " ".join(s.split())


def _case_word(w: str) -> str:
    """One all-caps / all-lower word in display case: 'LOWE'S' -> "Lowe's", "O'REILLY" -> "O'Reilly",
    'COCA-COLA' -> 'Coca-Cola', '7-ELEVEN' -> '7-Eleven'."""
    if "-" in w:
        return "-".join(_case_word(p) for p in w.split("-"))
    if "'" in w:
        head, _, tail = w.partition("'")
        if len(head) == 1 and head.upper() in "OD" and len(tail) > 1:      # O'Reilly, D'Angelo
            return head.upper() + "'" + tail[:1].upper() + tail[1:].lower()
        return _case_word(head) + "'" + tail.lower()
    if not w:
        return w
    i = next((k for k, ch in enumerate(w) if ch.isalpha()), None)
    if i is None:
        return w
    return w[:i] + w[i].upper() + w[i + 1:].lower()


def display_name(raw) -> str:
    """A merchant or institution name as a slide prints it.

    Proper case with apostrophes kept lower ("Lowe's", never "Lowe'S"); acronyms upper (CU, FCU, USAA,
    ATM, BNPL, LLC, N.A.); PayPal as PayPal; collapsed keys through NAME_ALIASES ("CIRCLEK" -> "Circle K").
    A name already in mixed case keeps its own casing except for str.title()'s tells ("Cu", "'S"),
    so the function is idempotent on clean names. None / blank -> "".
    """
    if raw is None:
        return ""
    s = " ".join(str(raw).replace("\u2019", "'").split())
    if not s:
        return ""
    key = _name_key(s)
    hit = NAME_ALIASES.get(key) or NAME_ALIASES.get(key.replace(" ", ""))
    if hit:
        return hit
    letters = [ch for ch in s if ch.isalpha()]
    mixed = any(ch.isupper() for ch in letters) and any(ch.islower() for ch in letters)
    out = []
    for n, tok in enumerate(s.split(" ")):
        bare = tok.upper().strip(",;:()")
        core = bare.replace(".", "")
        lead = tok[:len(tok) - len(tok.lstrip(",;:("))]
        trail = tok[len(tok.rstrip(",;:)")):]
        if bare == "N.A." or core in ACRONYMS:
            word = "N.A." if bare == "N.A." else core
        elif core in SPECIAL_CASE or bare in SPECIAL_CASE:
            word = SPECIAL_CASE.get(bare) or SPECIAL_CASE[core]
        elif "&" in core and len(core) <= 5:
            word = core
        elif mixed and n > 0 and tok in {w.capitalize() for w in _SMALL_WORDS}:
            word = tok.lower()                     # str.title()'s "Bank Of America"
        elif mixed and not (tok.isupper() or tok.islower()):
            # already cased by a person or by str.title(): keep it, but undo title()'s "'S"
            out.append(_re.sub(r"(?<=[a-z])'S\b", "'s", tok))
            continue
        elif mixed and tok.isupper():
            out.append(tok)                       # an all-caps word inside a cased name is deliberate
            continue
        elif (core.isalpha() and core.isupper() and 2 <= len(core) <= 4 and not (set(core) & _VOWELS)
              and core not in _NOT_ACRONYM):
            word = core                            # CVS, TJX: no vowel, so not a word
        elif n > 0 and tok.lower().strip(",;:()") in _SMALL_WORDS:
            word = tok.lower().strip(",;:()")
        elif core.startswith("MC") and len(core) > 3 and core.isalpha():
            word = "Mc" + core[2].upper() + core[3:].lower()
        else:
            word = _case_word(tok.strip(",;:()"))
        out.append(lead + word + trail)
    return " ".join(out)
