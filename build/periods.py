#!/usr/bin/env python3
"""
periods.py — every date phrase a deck renders, derived from one source.

On 2026-08-28 a Jul-2026 client shipped with "Monthly debit spend (June 2026)",
"opt-in status as of June 2026" and "Jul 2023 – Jun 2026 (36 months)" — about a
dozen captions naming a month the deck's own data did not cover. Each was a
literal typed into a different builder, and each had to be found by reading
slides.

A literal month is NOT banned. Writing "June 2026" is correct whenever June 2026
is genuinely the month being described — an ICS section reporting a quarterly
figure that carries forward is right to name an older month than the ARS section
beside it. What is banned is DERIVING a phrase by hand: computing a window, a
span, or a month count in an f-string, where the arithmetic silently goes stale
the next time the data moves.

So: take the snapshot month from the data pack, ask this module for the phrase,
and the phrase moves with the data.

    from periods import Period
    p = Period.from_pack(oddd_metrics)        # {"latest_month": "Jul26", ...}

    p.label()                 -> "July 2026"
    p.short()                 -> "Jul 2026"
    p.as_of()                 -> "as of July 2026"
    p.data_pill()             -> "July 2026 Data"
    p.ptd()                   -> "PTD · July 2026"
    p.window(12)              -> ("Aug25", "Jul26")
    p.span_label(36)          -> "Aug 2023 – Jul 2026 (36 months)"
    p.trailing(3)             -> "May–Jul 2026"

Chart TICKS are a separate vocabulary with ONE form, `axis_label` below.
Prose names a month in full; an axis carries 36 of them across one slide.
"""
from __future__ import annotations

import datetime
import re

MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
MONTH_ABBR = [m[:3] for m in MONTH_FULL]
_ABBR_IDX = {m.lower(): i for i, m in enumerate(MONTH_ABBR)}

# "Jul26" (ODD column form), "Jul 2026", "July 2026", "Jul 26", "Jul'26",
# "2026-07", "07-2026"
def _num_month(n):
    """Month abbreviation for 1-12, or None. Guarded: an out-of-range number
    used to index straight into MONTH_ABBR and raise IndexError rather than
    being rejected as unparseable."""
    return MONTH_ABBR[n - 1] if 1 <= n <= 12 else None


_TOKEN_FORMS = (
    (re.compile(r"^([A-Za-z]{3})(\d{2})$"), lambda m: (2000 + int(m.group(2)), m.group(1))),
    (re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{4})$"), lambda m: (int(m.group(2)), m.group(1))),
    # "Jul 26" — what metrics_gen's %b %y series and the ICS workbook extract
    # carry. It went unparsed until 2026-09-01, so those series could only be read
    # by slicing the string, which is what every chart renderer did.
    (re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{2})$"), lambda m: (2000 + int(m.group(2)), m.group(1))),
    # "Jul'26" — the axis form below, so a rendered tick round-trips.
    (re.compile(r"^([A-Za-z]{3})'(\d{2})$"), lambda m: (2000 + int(m.group(2)), m.group(1))),
    (re.compile(r"^(\d{4})-(\d{2})$"), lambda m: (int(m.group(1)), _num_month(int(m.group(2))))),
    (re.compile(r"^(\d{2})-(\d{4})$"), lambda m: (int(m.group(2)), _num_month(int(m.group(1))))),
)


def parse_month(token):
    """Any of the forms the pipeline uses -> date(y, m, 1). None if unparseable."""
    t = (token or "").strip()
    for rx, take in _TOKEN_FORMS:
        m = rx.match(t)
        if not m:
            continue
        year, mon = take(m)
        if mon is None:
            return None
        i = _ABBR_IDX.get(str(mon)[:3].lower())
        if i is None:
            return None
        return datetime.date(year, i + 1, 1)
    return None


def month_diff(a, b):
    """Inclusive month count from a to b. month_diff(Jul23, Jun26) == 36."""
    return (b.year - a.year) * 12 + (b.month - a.month) + 1


def shift(d, months):
    total = d.year * 12 + (d.month - 1) + months
    return datetime.date(total // 12, total % 12 + 1, 1)


# ---------------------------------------------------------------- axis labels
# The ONE form a chart tick may take (Aaron, 2026-09-01): no space, ASCII
# apostrophe, two-digit year. It is the narrowest of the forms that keep the
# year, and the 36-month axes are where width is scarce.
#
# Nine forms of "July 2026" were rendering across the three programs before this
# — Jul, Jul 26, Jul26, Jul'26, Jul '26, Jul 2026 — because each renderer cut a
# prose label back down with its own string slice. Ask this module instead.
AXIS_APOS = "'"
AXIS_MONTH_RE = re.compile(r"^[A-Z][a-z]{2}" + re.escape(AXIS_APOS) + r"\d{2}$")
# Year axes are a DIFFERENT vocabulary and keep four digits: "2024", "2026 YTD",
# "Pre-2018". Reg E by Vintage and MRPC Annual Revenue are genuinely annual
# series; named here so neither gets "standardized" into "'26".
AXIS_YEAR_RE = re.compile(r"^(?:Pre-)?(?:19|20)\d{2}(?:\s+(?:YTD|PTD|LTD))?$")


def axis_label(month):
    """A month, in any form the pipeline carries, as its chart tick: "Jul'26"."""
    d = parse_month(month) if isinstance(month, str) else month
    if d is None:
        raise ValueError(f"cannot read a month from {month!r}")
    return f"{MONTH_ABBR[d.month - 1]}{AXIS_APOS}{d.year % 100:02d}"


def axis_labels(months, field="months"):
    """`axis_label` across a series, naming the field when an entry is unreadable.

    An unreadable month RAISES. Passing the raw value through to the axis is how
    the ICS and MRPC charts came to render whatever the VIP dashboard happened to
    export that month, and a wrong tick label looks exactly like a right one.
    """
    out = []
    for i, m in enumerate(months):
        try:
            out.append(axis_label(m))
        except ValueError:
            raise ValueError(
                f"{field}[{i}]: cannot read a month from {m!r} — an axis is never "
                f"rendered from an unparsed value") from None
    return out


AXIS_SEP = "\u00b7"          # the middot STYLE.md already uses between pill halves


def axis_window(start, end, fallback=""):
    """A start/end window as pill tokens: "Aug'25 \u00b7 Jul'26".

    The deck's four window pills are shortened because the box overflows at
    "Aug 2025 - Jul 2026" (Aaron, 2026-07-15). They were shortened to "08-2025 \u00b7
    07-2026", a numeric form invented for that box and spelled nowhere else; the
    axis token is a character shorter and is the one form a month takes anywhere
    on a slide.

    `fallback` is returned when either end is unreadable, so a workbook that
    labels its window some other way still renders something rather than "None \u00b7
    None". The caller passes whatever the workbook itself said.
    """
    try:
        a, b = axis_label(start), axis_label(end)
    except ValueError:
        return fallback
    return f"{a} {AXIS_SEP} {b}"


_NAMES_A_MONTH_RE = re.compile(
    r"(?<![A-Za-z])(?:" + "|".join(MONTH_FULL + MONTH_ABBR) + r")(?![A-Za-z])", re.I)


def names_a_month(text):
    """True when a tick names a month AT ALL, in any form — a bare "Jul" included.

    This is the gate's filter, not a validator: it decides which rendered ticks
    are subject to the axis vocabulary. A branch number, a tier name or a swipe
    band names no month and is none of its business; "Jul", "Jul 26" and
    "Jul'26" all do, and only the last is allowed.
    """
    t = (text or "").strip()
    if not t:
        return False
    return parse_month(t) is not None or bool(_NAMES_A_MONTH_RE.search(t))


def is_axis_label(text):
    """True for a tick this module would have produced — month OR year form."""
    t = (text or "").strip()
    return bool(AXIS_MONTH_RE.match(t) or AXIS_YEAR_RE.match(t))


class Period:
    """The deck's reporting period, derived from the data pack."""

    def __init__(self, latest):
        if isinstance(latest, str):
            parsed = parse_month(latest)
            if parsed is None:
                raise ValueError(f"unparseable month token: {latest!r}")
            latest = parsed
        self.latest = latest

    # -- construction ------------------------------------------------------
    @classmethod
    def from_pack(cls, pack):
        """From oddd_metrics.json — `latest_month` first, then `period`.

        Never defaults to today. A deck built in September from a July extract
        reports July; taking the clock is how a caption goes stale without any
        code changing.
        """
        for key in ("latest_month", "period"):
            if pack.get(key):
                p = parse_month(str(pack[key]))
                if p:
                    return cls(p)
        raise ValueError("data pack carries no latest_month / period")

    # -- point in time -----------------------------------------------------
    def label(self):
        return f"{MONTH_FULL[self.latest.month - 1]} {self.latest.year}"

    def short(self):
        return f"{MONTH_ABBR[self.latest.month - 1]} {self.latest.year}"

    def token(self):
        """The ODD column form, e.g. 'Jul26'."""
        return f"{MONTH_ABBR[self.latest.month - 1]}{self.latest.year % 100:02d}"

    def as_of(self):
        return f"as of {self.label()}"

    def data_pill(self):
        return f"{self.label()} Data"

    def ptd(self):
        return f"PTD · {self.label()}"

    # -- windows -----------------------------------------------------------
    def window(self, n):
        """The n-month window ENDING at the snapshot month, as ODD tokens."""
        if n < 1:
            raise ValueError("window needs at least one month")
        start = shift(self.latest, -(n - 1))
        return (f"{MONTH_ABBR[start.month-1]}{start.year % 100:02d}", self.token())

    def span(self, n):
        """(start_date, end_date) for the n-month window ending at the snapshot."""
        return (shift(self.latest, -(n - 1)), self.latest)

    def span_label(self, n, dash="–"):
        """'Aug 2023 – Jul 2026 (36 months)' — the count is DERIVED, never typed."""
        a, b = self.span(n)
        months = month_diff(a, b)
        return (f"{MONTH_ABBR[a.month-1]} {a.year} {dash} "
                f"{MONTH_ABBR[b.month-1]} {b.year} "
                f"({months} month{'s' if months != 1 else ''})")

    def trailing(self, n, dash="–"):
        """'May–Jul 2026', collapsing the year when the window stays inside one."""
        a, b = self.span(n)
        if a.year == b.year:
            return f"{MONTH_ABBR[a.month-1]}{dash}{MONTH_ABBR[b.month-1]} {b.year}"
        return (f"{MONTH_ABBR[a.month-1]} {a.year}{dash}"
                f"{MONTH_ABBR[b.month-1]} {b.year}")

    def months_since(self, start):
        """Inclusive month count from `start` to the snapshot month."""
        s = parse_month(start) if isinstance(start, str) else start
        if s is None:
            raise ValueError(f"unparseable month: {start!r}")
        return month_diff(s, self.latest)

    def __repr__(self):
        return f"Period({self.token()})"
