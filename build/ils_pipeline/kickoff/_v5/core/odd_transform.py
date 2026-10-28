# Ported from v5 02-Scripts/core/odd_transform.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
"""ODD transform: raw ODD DataFrame -> analysis-ready DataFrame.

Replaces the legacy 7-step format_odd pipeline. Written from scratch.

Design rules:
  1. Month columns are ordered by PARSED DATE, never by position in df.columns.
  2. Business rules (response codes, swipe bins) live in TransformConfig, not code.
  3. "Response" has ONE definition, used by both grouping and segmentation.
  4. Every transform reports what it did; silence is not success.

Usage:
    from odd_transform import transform_odd, TransformConfig

    out, report = transform_odd(raw_df)
    if report.errors:
        raise ValueError(report.summary())
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Month tag parsing
# ---------------------------------------------------------------------------

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
_TAG_RE = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(\d{2})\s+(.+)$")


def parse_month_tag(column: str) -> tuple[pd.Timestamp, str] | None:
    """Split 'Apr25 PIN $' into (Timestamp(2025,4,1), 'PIN $').

    Returns None for columns without a month prefix.
    """
    match = _TAG_RE.match(str(column).strip())
    if not match:
        return None
    mon, yy, suffix = match.groups()
    return pd.Timestamp(2000 + int(yy), _MONTHS[mon], 1), suffix.strip()


def month_columns(df: pd.DataFrame, suffix: str) -> list[str]:
    """All columns with the given suffix, sorted CHRONOLOGICALLY.

    This is the core correctness guarantee. The legacy pipeline sliced
    `[-3:]` off a list built in df.columns order, which is only correct
    when the source happens to emit months in order.
    """
    found = []
    for col in df.columns:
        parsed = parse_month_tag(col)
        if parsed and parsed[1] == suffix:
            found.append((parsed[0], col))
    return [col for _, col in sorted(found)]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransformConfig:
    """Business rules. Change these here, not in the transform logic."""

    # A Resp value means the account responded when it is NU 5+ or any TH
    # tier. NU 1-4 is tracked but is NOT a response.
    #
    # Matched by pattern, not by an explicit list: a new tier (TH-30, NU 10+)
    # must not silently become a non-response because nobody updated a set.
    # Explicit codes still win when a client declares them.
    response_codes: frozenset[str] = frozenset()
    tracked_not_response: frozenset[str] = frozenset({"NU 1-4"})

    # Monthly-average swipe bins. (upper_bound_inclusive, label);
    # None upper bound = catch-all. Must be ascending.
    swipe_bins: tuple[tuple[float | None, str], ...] = (
        (1.0, "Non-user"),        # < 1
        (5.0, "1-5 Swipes"),
        (10.0, "6-10 Swipes"),
        (15.0, "11-15 Swipes"),
        (20.0, "16-20 Swipes"),
        (25.0, "21-25 Swipes"),
        (40.0, "26-40 Swipes"),
        (None, "41+ Swipes"),
    )

    # Columns dropped outright.
    drop_suffixes: tuple[str, ...] = ("YTD", "PYTD")
    drop_columns: tuple[str, ...] = ("Acct Mask",)

    rolling_windows: tuple[int, ...] = (3, 12)


@dataclass
class TransformReport:
    """What the transform did. Inspect before trusting the output."""

    rows_in: int = 0
    rows_out: int = 0
    cols_in: int = 0
    cols_out: int = 0
    anchor_date: pd.Timestamp | None = None
    data_month: pd.Timestamp | None = None
    dropped: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"rows {self.rows_in:,} -> {self.rows_out:,}",
            f"cols {self.cols_in} -> {self.cols_out} "
            f"({len(self.dropped)} dropped, {len(self.added)} added)",
            f"data month: {self.data_month:%Y-%m}" if self.data_month else "data month: UNKNOWN",
        ]
        for w in self.warnings:
            lines.append(f"  WARN  {w}")
        for e in self.errors:
            lines.append(f"  ERROR {e}")
        return "\n".join(lines)


_TH_RE = re.compile(r"^TH[\s\-_]?\d+", re.I)
_NU_RE = re.compile(r"^NU[\s\-_]?(\d+)\s*\+", re.I)


def _classify_tier(value: str, cfg: "TransformConfig") -> str:
    """response | tracked | unknown | blank"""
    v = str(value).strip()
    if not v or v.lower() == "nan":
        return "blank"
    if cfg.response_codes and v in cfg.response_codes:
        return "response"
    if v in cfg.tracked_not_response:
        return "tracked"
    if _TH_RE.match(v):
        return "response"
    if _NU_RE.match(v):
        return "response"          # NU 5+, NU 10+ -- any NU with a plus
    if v.upper().startswith("NU"):
        return "tracked"           # NU 1-4 and any other bounded NU range
    return "unknown"


def _is_response(series: pd.Series, cfg: "TransformConfig") -> pd.Series:
    vals = series.fillna("").astype(str).str.strip()
    return vals.map(lambda v: _classify_tier(v, cfg) == "response")


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def transform_odd(
    df: pd.DataFrame,
    config: TransformConfig | None = None,
) -> tuple[pd.DataFrame, TransformReport]:
    """Transform a raw ODD DataFrame into analysis-ready form."""
    cfg = config or TransformConfig()
    rpt = TransformReport(rows_in=len(df), cols_in=len(df.columns))

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    _resolve_dates(df, rpt)
    df = _drop_columns(df, cfg, rpt)
    df = _coerce_numeric(df, rpt)
    df = _add_monthly_combined(df, rpt)
    df = _add_totals_and_rolling(df, cfg, rpt)
    df = _add_ages(df, rpt)
    df = _add_response_metrics(df, cfg, rpt)

    rpt.rows_out = len(df)
    rpt.cols_out = len(df.columns)
    return df, rpt


def _resolve_dates(df: pd.DataFrame, rpt: TransformReport) -> None:
    """Determine the data month and the anchor date for age math.

    The data month is the newest month across TRANSACTION columns. Mail and
    Resp columns are excluded because the mailer track runs a month ahead of
    the transaction track -- using the max across all columns would push the
    anchor one month past the data.
    """
    txn_suffixes = ("PIN $", "Sig $", "PIN #", "Sig #", "MTD")
    dates: list[pd.Timestamp] = []
    for col in df.columns:
        parsed = parse_month_tag(col)
        if parsed and parsed[1] in txn_suffixes:
            dates.append(parsed[0])

    if not dates:
        rpt.errors.append("no month-tagged transaction columns found")
        rpt.anchor_date = pd.Timestamp.now().normalize()
        return

    rpt.data_month = max(dates)
    # Anchor at month end -- the data covers the full month.
    rpt.anchor_date = rpt.data_month + pd.offsets.MonthEnd(0)

    all_dates = [
        parse_month_tag(c)[0] for c in df.columns if parse_month_tag(c)
    ]
    if max(all_dates) > rpt.data_month:
        ahead = (max(all_dates).year - rpt.data_month.year) * 12 + (
            max(all_dates).month - rpt.data_month.month
        )
        if ahead > 1:
            rpt.warnings.append(
                f"non-transaction columns run {ahead} months past the data month"
            )


def _drop_columns(df, cfg, rpt) -> pd.DataFrame:
    drop = [
        c for c in df.columns
        if any(c.endswith(s) for s in cfg.drop_suffixes) or c in cfg.drop_columns
    ]
    rpt.dropped = drop
    return df.drop(columns=drop, errors="ignore")


def _coerce_numeric(df: pd.DataFrame, rpt: TransformReport) -> pd.DataFrame:
    """Force transaction columns numeric. Report how much was unparseable."""
    for suffix in ("PIN $", "Sig $", "PIN #", "Sig #", "MTD"):
        for col in month_columns(df, suffix):
            original = df[col]
            coerced = pd.to_numeric(original, errors="coerce")
            lost = int(coerced.isna().sum() - original.isna().sum())
            if lost > 0:
                rpt.warnings.append(f"{col}: {lost:,} values not numeric, set to 0")
            df[col] = coerced.fillna(0)
    return df


def _add_monthly_combined(df: pd.DataFrame, rpt: TransformReport) -> pd.DataFrame:
    """Per-month Spend = PIN $ + Sig $, Swipes = PIN # + Sig #."""
    new: dict[str, pd.Series] = {}

    for money, count, out_money, out_count in (
        ("PIN $", "Sig $", "Spend", None),
        ("PIN #", "Sig #", "Swipes", None),
    ):
        pin_cols = month_columns(df, money)
        for pin_col in pin_cols:
            date, _ = parse_month_tag(pin_col)
            prefix = pin_col.rsplit(" ", 2)[0]
            sig_col = f"{prefix} {count}"
            if sig_col not in df.columns:
                rpt.warnings.append(f"{pin_col} has no matching {count}")
                continue
            new[f"{prefix} {out_money}"] = df[pin_col] + df[sig_col]

    if new:
        rpt.added.extend(new)
        df = pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
    return df


def _add_totals_and_rolling(df, cfg, rpt) -> pd.DataFrame:
    """Lifetime totals, trailing-window totals, monthly averages, swipe bins."""
    spend_cols = month_columns(df, "Spend")
    swipe_cols = month_columns(df, "Swipes")
    item_cols = month_columns(df, "MTD")

    if not spend_cols:
        rpt.errors.append("no monthly Spend columns; cannot compute totals")
        return df

    new: dict[str, pd.Series] = {
        "Total Spend": df[spend_cols].sum(axis=1),
        "Total Swipes": df[swipe_cols].sum(axis=1),
        "Total Items": df[item_cols].sum(axis=1) if item_cols
        else pd.Series(0.0, index=df.index),
    }

    for n in cfg.rolling_windows:
        for cols, label in (
            (spend_cols, "spend"), (swipe_cols, "swipes"), (item_cols, "Items"),
        ):
            if len(cols) < n:
                rpt.warnings.append(
                    f"only {len(cols)} {label} months available for {n}-month window"
                )
            window = cols[-n:] if cols else []
            key = (f"last {n}-mon {label}" if label != "Items"
                   else f"Last {n}-mon Items")
            new[key] = (df[window].sum(axis=1) if window
                        else pd.Series(0.0, index=df.index))

        new[f"MonthlySpend{n}"] = new[f"last {n}-mon spend"] / n
        new[f"MonthlySwipes{n}"] = new[f"last {n}-mon swipes"] / n
        new[f"MonthlyItems{n}"] = new[f"Last {n}-mon Items"] / n
        new[f"SwipeCat{n}"] = _bin_swipes(new[f"MonthlySwipes{n}"], cfg)

    rpt.added.extend(new)
    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)


def _bin_swipes(values: pd.Series, cfg: TransformConfig) -> pd.Series:
    """Vectorized swipe binning (legacy used .apply per row)."""
    edges = [-np.inf] + [b for b, _ in cfg.swipe_bins if b is not None] + [np.inf]
    labels = [label for _, label in cfg.swipe_bins]
    return pd.cut(values, bins=edges, labels=labels, right=False,
                  include_lowest=True).astype(object)


def _add_ages(df: pd.DataFrame, rpt: TransformReport) -> pd.DataFrame:
    """Account Holder Age and Account Age, both in true years."""
    anchor = rpt.anchor_date
    new: dict[str, pd.Series] = {}

    if "DOB" in df.columns:
        dob = pd.to_datetime(df["DOB"], errors="coerce", format="mixed")
        # True age, not year subtraction: a Dec birthday is not a year older
        # on the following January.
        new["Account Holder Age"] = ((anchor - dob).dt.days / 365.2425).round(1)
        missing = int(dob.isna().sum())
        if missing:
            rpt.warnings.append(f"DOB: {missing:,} unparseable, age is null")
    else:
        rpt.warnings.append("no DOB column; Account Holder Age not computed")

    if "Date Opened" in df.columns:
        opened = pd.to_datetime(df["Date Opened"], errors="coerce", format="mixed")
        if "Date Closed" in df.columns:
            closed = pd.to_datetime(df["Date Closed"], errors="coerce", format="mixed")
            end = closed.fillna(anchor)
        else:
            end = pd.Series(anchor, index=df.index)
        new["Account Age"] = ((end - opened).dt.days / 365.2425).round(2)
        negative = int((new["Account Age"] < 0).sum())
        if negative:
            rpt.warnings.append(
                f"Account Age: {negative:,} negative (opened after anchor date)"
            )
    else:
        rpt.warnings.append("no Date Opened column; Account Age not computed")

    if new:
        rpt.added.extend(new)
        df = pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
    return df


def _add_response_metrics(df, cfg, rpt) -> pd.DataFrame:
    """Offers, responses, grouping, and per-month segmentation.

    ONE definition of 'responded': the Resp value is in cfg.response_codes.
    The legacy pipeline used 'not null and not NU 1-4' for counting but the
    explicit code set for segmentation, so a new response code was counted
    as a response by one and a non-response by the other.
    """
    resp_cols = month_columns(df, "Resp")
    mail_cols = month_columns(df, "Mail")

    if not resp_cols or not mail_cols:
        rpt.warnings.append("no Mail/Resp columns; response metrics skipped")
        return df

    # Report how each observed value was classified, so a new tier is visible
    # rather than quietly absorbed.
    seen: set[str] = set()
    for col in resp_cols:
        seen.update(v.strip() for v in df[col].dropna().astype(str) if v.strip())
    as_response = sorted(v for v in seen if _classify_tier(v, cfg) == "response")
    as_tracked = sorted(v for v in seen if _classify_tier(v, cfg) == "tracked")
    unclassified = sorted(v for v in seen if _classify_tier(v, cfg) == "unknown")
    if as_response:
        rpt.warnings.append(f"Resp values counted as responses: {as_response}")
    if unclassified:
        rpt.warnings.append(
            f"Resp values matching no rule, counted as NON-response: "
            f"{unclassified[:8]}"
        )

    def offered(col: str) -> pd.Series:
        s = df[col]
        return s.notna() & (s.astype(str).str.strip() != "")

    def responded(col: str) -> pd.Series:
        return _is_response(df[col], cfg)

    new: dict[str, pd.Series] = {
        "# of Offers": sum(offered(c).astype(int) for c in mail_cols),
        "# of Responses": sum(responded(c).astype(int) for c in resp_cols),
    }

    offers, responses = new["# of Offers"], new["# of Responses"]
    grouping = pd.Series("No Offer", index=df.index, dtype=object)
    grouping[(offers > 0) & (responses == 0)] = "Non-Responder"
    grouping[(offers == 1) & (responses == 1)] = "SO-SR"
    grouping[(offers >= 2) & (responses == 1)] = "MO-SR"
    grouping[responses >= 2] = "MR"
    new["Response Grouping"] = grouping

    # Per-wave group (Control / Responder / Non-Responder), using the same
    # 'responded' predicate. Named "Wave Group", not "Segmentation": the raw
    # ODD carries its own "<Mon> Segmentation" (the swipe category at each
    # mailing) and reusing that name produced two columns with one name.
    for resp_col in resp_cols:
        date, _ = parse_month_tag(resp_col)
        prefix = resp_col.rsplit(" ", 1)[0]
        mail_col = f"{prefix} Mail"
        if mail_col not in df.columns:
            rpt.warnings.append(f"{resp_col} has no matching Mail column")
            continue
        was_mailed = offered(mail_col)
        new[f"{prefix} Wave Group"] = np.select(
            [~was_mailed, was_mailed & responded(resp_col)],
            ["Control", "Responder"],
            default="Non-Responder",
        )

    rpt.added.extend(new)
    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
