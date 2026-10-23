# Ported from ARS v5 02-Scripts/core/periods.py at a491b5c (James Gilmore); logic unchanged.
"""Period parsing and month-window helpers.

One place for date logic. The legacy pipeline spread it across files and
disagreed with itself: ticket_calc.py carried a hardcoded month list ending
at Jun26 (so Jul26 data was silently dropped), and format_odd inferred its
anchor from the max of ALL month columns -- including Mail/Resp, which run a
month ahead of the transaction data, aging every account by an extra month.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NUM = {m: i + 1 for i, m in enumerate(MONTHS)}

# Column tags look like "Jul26 Sig $" / "Nov24 OD Limit" / "Apr25 Reg E Code".
TAG_RE = re.compile(r"^(" + "|".join(MONTHS) + r")(\d{2})\s+(.+)$")

# Suffixes that carry transaction data. The data month is derived from these
# ONLY -- Mail and Resp run ahead of the transaction track.
TXN_SUFFIXES = ("PIN $", "Sig $", "PIN #", "Sig #", "MTD")


@dataclass(frozen=True, order=True)
class Month:
    """A year-month. Ordered, so max()/sorted() work directly."""

    year: int
    month: int

    @classmethod
    def from_tag(cls, tag: str) -> "Month | None":
        """'Jul26' -> Month(2026, 7)."""
        m = re.fullmatch(r"([A-Z][a-z]{2})(\d{2})", tag.strip())
        if not m or m.group(1) not in MONTH_NUM:
            return None
        return cls(2000 + int(m.group(2)), MONTH_NUM[m.group(1)])

    @classmethod
    def parse(cls, text: str) -> "Month | None":
        """Accepts 2026-08, 2026.08, 08.2026, 202608, Aug 2026, Aug26.

        Separators may be - . / or _. A month outside 1-12 is refused rather
        than clamped, and anything genuinely ambiguous -- 03-04, which is
        either March 2004 or April 2003 -- is refused too. Guessing there
        would file a report against the wrong period without saying so.
        """
        s = str(text or "").strip()

        def made(year: int, month: int) -> "Month | None":
            return cls(year, month) if 1 <= month <= 12 else None

        m = re.fullmatch(r"(\d{4})[-._/](\d{1,2})", s)
        if m:
            return made(int(m.group(1)), int(m.group(2)))

        m = re.fullmatch(r"(\d{1,2})[-._/](\d{4})", s)      # 08.2026
        if m:
            return made(int(m.group(2)), int(m.group(1)))

        m = re.fullmatch(r"(\d{4})(\d{2})", s)              # 202608
        if m:
            return made(int(m.group(1)), int(m.group(2)))

        m = re.fullmatch(r"([A-Za-z]{3,})\.?\s*,?\s*(\d{4})", s)   # Aug 2026
        if m:
            key = m.group(1)[:3].title()
            if key in MONTH_NUM:
                return cls(int(m.group(2)), MONTH_NUM[key])

        return cls.from_tag(s)

    @property
    def tag(self) -> str:
        """Month(2026, 7) -> 'Jul26' (ODD column prefix)."""
        return f"{MONTHS[self.month - 1]}{self.year % 100:02d}"

    @property
    def iso(self) -> str:
        """Month(2026, 7) -> '2026-07'. Canonical form everywhere."""
        return f"{self.year:04d}-{self.month:02d}"

    def shift(self, n: int) -> "Month":
        total = self.year * 12 + (self.month - 1) + n
        return Month(total // 12, total % 12 + 1)

    def __str__(self) -> str:
        return self.iso


def split_tag(column: str) -> tuple[Month, str] | None:
    """'Jul26 Sig $' -> (Month(2026,7), 'Sig $'). None if not month-tagged."""
    m = TAG_RE.match(str(column).strip())
    if not m:
        return None
    return Month(2000 + int(m.group(2)), MONTH_NUM[m.group(1)]), m.group(3).strip()


def columns_for(columns, suffix: str) -> list[str]:
    """Columns with the given suffix, in CHRONOLOGICAL order.

    Never rely on position in the source file: a trailing [-3:] slice of an
    unsorted list silently returns the wrong quarter.
    """
    found = []
    for col in columns:
        parsed = split_tag(col)
        if parsed and parsed[1] == suffix:
            found.append((parsed[0], col))
    return [c for _, c in sorted(found)]


def data_month(columns) -> Month | None:
    """Newest month across TRANSACTION columns only."""
    months = []
    for col in columns:
        parsed = split_tag(col)
        if parsed and parsed[1] in TXN_SUFFIXES:
            months.append(parsed[0])
    return max(months) if months else None


def trailing(anchor: Month, n: int) -> list[Month]:
    """The n months ending at anchor, inclusive and in order.

    trailing(Jul26, 3) -> [May26, Jun26, Jul26]

    This replaces every hardcoded window in the legacy code. The literal
    w3 = ['Apr26','May26','Jun26'] was correct for one file and silently
    wrong for every file after it.
    """
    if n < 1:
        return []
    return [anchor.shift(-(n - 1) + i) for i in range(n)]


def window_columns(columns, suffix: str, anchor: Month, n: int):
    """Columns for the trailing n months with `suffix`, plus what's missing.

    Returns (present_columns, missing_months). A short window is reported,
    never silently summed over fewer months.
    """
    want = trailing(anchor, n)
    have = {}
    for col in columns:
        parsed = split_tag(col)
        if parsed and parsed[1] == suffix:
            have[parsed[0]] = col
    present = [have[m] for m in want if m in have]
    missing = [m for m in want if m not in have]
    return present, missing


def canonical(text) -> str | None:
    """Any accepted spelling of a period as ``YYYY-MM``, else None.

    The single normaliser for anything a person types. Entry points call
    this instead of matching a fixed pattern, so the tools stop being fussy
    about a distinction they can resolve -- a CSM types the month the way
    the file is named, and files arrive spelled every way there is.
    """
    month = Month.parse(text) if text is not None else None
    return month.iso if month else None
