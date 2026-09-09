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
"""
from __future__ import annotations

import datetime
import re

MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
MONTH_ABBR = [m[:3] for m in MONTH_FULL]
_ABBR_IDX = {m.lower(): i for i, m in enumerate(MONTH_ABBR)}

# "Jul26" (ODD column form), "Jul 2026", "July 2026", "2026-07", "07-2026"
def _num_month(n):
    """Month abbreviation for 1-12, or None. Guarded: an out-of-range number
    used to index straight into MONTH_ABBR and raise IndexError rather than
    being rejected as unparseable."""
    return MONTH_ABBR[n - 1] if 1 <= n <= 12 else None


_TOKEN_FORMS = (
    (re.compile(r"^([A-Za-z]{3})(\d{2})$"), lambda m: (2000 + int(m.group(2)), m.group(1))),
    (re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{4})$"), lambda m: (int(m.group(2)), m.group(1))),
    # "Jun 25" and "Jun'25" — the two forms this pipeline actually carries, and
    # neither parsed until 2026-09-01. Every VIP series ("Jul 25", "Aug 25") and
    # every axis label the charts already drew fell straight through to None.
    # A two-digit year here is a YEAR: these tokens label monthly series, never
    # a day of the month.
    (re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{2})$"), lambda m: (2000 + int(m.group(2)), m.group(1))),
    # "Jun'25" and "Sep '23" — the space before the apostrophe is not decorative:
    # the ARS Sustained chart drew exactly that form, and it fell through to None
    # so the month-axis guard could not see it as a month at all (2026-09-08).
    (re.compile(r"^([A-Za-z]{3,9})\.?\s*'(\d{2})$"), lambda m: (2000 + int(m.group(2)), m.group(1))),
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


AXIS_ROTATION = 45          # angled, so a full MMM'YY never has to be shortened
AXIS_HA = "right"           # anchor the angled label under its own tick


def mon_yy(token):
    """A month as it appears on EVERY chart axis: MMM'YY (Aaron, 2026-09-01).

    One format, everywhere. Three were in service and none of them agreed:
    ARS drew "Jun'25" (built by stripping the space out of the data), MRPC drew
    "Aug 25" straight from the sheet, and the ICS quarter charts drew "Jul" —
    `mm.split()[0]` threw the YEAR AWAY, so a 14-month axis read Jan..Dec..Jan
    with no way to tell the two Januaries apart.

    Unparseable input is returned unchanged rather than mangled: an axis whose
    categories are branches or tiers, not months, must survive being passed here.
    """
    d = parse_month(token)
    if d is None:
        return token
    return "%s'%02d" % (MONTH_ABBR[d.month - 1], d.year % 100)


def axis_months(tokens):
    """Every label on one axis, in the house format."""
    return [mon_yy(t) for t in tokens]


class MonthAxisError(Exception):
    """A chart drew a calendar month outside the house format."""


def install_month_axis_guard():
    """Fail any render that puts a calendar month on an axis un-formatted.

    `mon_yy` settled the format; it did not make every chart adopt it, and the
    ones that never did were invisible because they build their labels by
    string-slicing instead of calling anything (Aaron, 2026-09-08). The ARS
    before/after panels sliced "Feb 2024" into "Feb24", Sustained drew
    "Sep '23", monthly revenue took `m.split()[0]` and threw the YEAR away, and
    Ranking left "Sep 2023" full-length down the y-axis. Five charts, four
    formats, none of them the standard.

    A lint over the source cannot see this — the label is a runtime value — so
    the check runs where the label is actually drawn. A category axis that is
    not months passes straight through: only a label `parse_month` recognises
    is held to the format, and it is held to being ALREADY correct, so the
    guard never silently rewrites a chart.

    Idempotent, so importing two chart modules in one process installs it once.
    """
    from matplotlib.axes import Axes

    def _wrap(name):
        orig = getattr(Axes, name)
        if getattr(orig, "_rpe_month_guard", False):
            return
        axis = name[4]                      # 'x' or 'y'

        def checked(self, labels, *a, **kw):
            for t in labels or ():
                s = str(t.get_text() if hasattr(t, "get_text") else t)
                if parse_month(s) and s != mon_yy(s):
                    raise MonthAxisError(
                        "%s-axis label %r is a calendar month drawn outside the "
                        "house format (%r). Pass it through "
                        "periods.axis_months() — see STYLE.md, chart standards."
                        % (axis, s, mon_yy(s)))
            return orig(self, labels, *a, **kw)

        checked._rpe_month_guard = True
        checked.__name__ = name
        setattr(Axes, name, checked)

    _wrap("set_xticklabels")
    _wrap("set_yticklabels")


def month_diff(a, b):
    """Inclusive month count from a to b. month_diff(Jul23, Jun26) == 36."""
    return (b.year - a.year) * 12 + (b.month - a.month) + 1


def shift(d, months):
    total = d.year * 12 + (d.month - 1) + months
    return datetime.date(total // 12, total % 12 + 1, 1)


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
