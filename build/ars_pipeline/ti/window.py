"""The transaction window: the last N COMPLETED months before the cycle.

The window is fixed by the cycle (the period, yyyy.mm), never by whatever the newest
file or the ODD happens to carry. Runs happen on the 4th or later, so the window always
runs through the last day of the previous month: cycle 2026.11 covers the N whole months
ending 31 Oct 2026.

N is 12 unless the run (TI_WINDOW_MONTHS) or the client config (TxnWindowMonths) says
otherwise. 1, 3, 6 and anything past 12 are all valid, as long as the files cover them;
a month in the window with no rows is warned, never invented.
"""

from __future__ import annotations

import datetime as _dt
import os

import pandas as pd

DEFAULT_MONTHS = 12
CONFIG_KEY = "TxnWindowMonths"
ENV_KEY = "TI_WINDOW_MONTHS"
FIRST_SAFE_DAY = 4          # the previous month's files have landed by the 4th


def _as_months(value, source: str) -> int:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{source}: the transaction window must be a whole number of months, "
                         f"not {value!r}") from None
    if n < 1:
        raise ValueError(f"{source}: the transaction window must be at least 1 month, not {n}")
    return n


def months_for(config: dict | None = None, override=None) -> int:
    """N: the caller's choice, else TI_WINDOW_MONTHS, else the client's TxnWindowMonths, else 12."""
    if override is not None:
        return _as_months(override, "the run")
    if os.environ.get(ENV_KEY):
        return _as_months(os.environ[ENV_KEY], ENV_KEY)
    if config and config.get(CONFIG_KEY) not in (None, ""):
        return _as_months(config[CONFIG_KEY], f"client config {CONFIG_KEY}")
    return DEFAULT_MONTHS


def _cycle(period: str) -> pd.Timestamp:
    y, m = (int(x) for x in str(period).split("."))
    return pd.Timestamp(y, m, 1)


def end_month(period: str) -> pd.Timestamp:
    """The last completed month before the cycle, as its first day: 2026.11 -> 2026-10-01."""
    return _cycle(period) - pd.DateOffset(months=1)


def bounds(period: str, months: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """[start, stop): the first day of the window's first month, and the first day of the
    cycle month (exclusive), so the whole of the previous month is in."""
    stop = _cycle(period)
    return stop - pd.DateOffset(months=months), stop


def month_starts(period: str, months: int) -> list[pd.Timestamp]:
    start, _ = bounds(period, months)
    return [start + pd.DateOffset(months=i) for i in range(months)]


def phrase(months: int, short: bool = False) -> str:
    """'in the last 12 months' / 'last 12 months'; 'in the last month' when N = 1."""
    span = "month" if int(months) == 1 else f"{int(months)} months"
    return f"last {span}" if short else f"in the last {span}"


def describe(period: str, months: int) -> dict:
    """The window as pack metrics."""
    start, stop = bounds(period, months)
    last = stop - pd.Timedelta(days=1)
    return {"txn_window_months": int(months),
            "txn_window_start": start.strftime("%Y-%m-%d"),
            "txn_window_end": last.strftime("%Y-%m-%d"),
            "txn_window_label": f"{phrase(months, short=True)} ({start:%b %Y} to {last:%b %Y})"}


def early_run_warning(period: str, today: _dt.date | None = None) -> str | None:
    """A run for the current cycle before the 4th may not have the previous month's files yet."""
    today = today or _dt.date.today()
    cyc = _cycle(period)
    if (today.year, today.month) == (cyc.year, cyc.month) and today.day < FIRST_SAFE_DAY:
        return (f"run on {today:%b} {today.day}, before the {FIRST_SAFE_DAY}th: the previous "
                f"month's transaction files may not all have landed yet")
    return None
