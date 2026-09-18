"""The subset layer: every denominator, built once, named.

Rates that divide by the wrong base are not a rounding difference. The same
client reads ~30% take rate on Eligible and ~80% on Open. So the bases are
built once, in one place, and every calculator asks for one by name rather
than filtering inline.

    subsets = build_subsets(df, config, anchor)
    rate = has_debit(subsets.eligible).mean()      # base: Eligible
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .periods import Month

# Debit and business are read through odd_rows, the one place those rules live in the
# pipeline (the deck's builders read the same functions). v5 accepted Y / D / DC / TRUE / 1
# as well; every ODD seen writes Yes / No exactly, and one reading beats a wider one.
from odd_rows import flag_yes_series as _flag_yes_series, business_class_series as _business_class_series


def norm(series) -> pd.Series | None:
    """Strip NULs and whitespace, NaN -> ''. Returns None if the column is absent."""
    if series is None:
        return None
    return (series.fillna("").astype(str)
            .str.replace("\x00", "", regex=False).str.strip())


def has_debit(df: pd.DataFrame) -> pd.Series:
    """The canonical has-debit predicate: odd_rows.has_debit over `Debit?`."""
    col = df.get("Debit?")
    if col is None:
        return pd.Series(False, index=df.index)
    return _flag_yes_series(col)


def is_business(df: pd.DataFrame) -> pd.Series:
    """odd_rows.is_business over `Business?`: Yes is business, No is personal, blank is neither."""
    col = df.get("Business?")
    if col is None:
        return pd.Series(False, index=df.index)
    return _business_class_series(col).eq("business")


@dataclass
class FunnelStage:
    label: str
    count: int
    pct_of_total: float
    dropoff_pct: float


@dataclass
class Subsets:
    """Named denominators. All are views on the same frame."""

    total: pd.DataFrame
    open_accounts: pd.DataFrame
    eligible: pd.DataFrame
    eligible_personal: pd.DataFrame
    eligible_business: pd.DataFrame
    eligible_with_debit: pd.DataFrame          # eligible ∩ debit (all)
    personal_with_debit: pd.DataFrame          # eligible personal ∩ debit -- Reg E base
    l12m_open: pd.DataFrame
    l12m_eligible: pd.DataFrame
    responders: pd.DataFrame                   # eligible ∩ ≥1 response
    non_responders: pd.DataFrame               # eligible ∩ mailed ∩ 0 responses

    anchor: Month = None
    l12m_start: pd.Timestamp = None
    funnel: list[FunnelStage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def named(self, label: str) -> pd.DataFrame:
        """Look a base up by its denominator-law label."""
        mapping = {
            "Total": self.total,
            "Open": self.open_accounts,
            "Eligible": self.eligible,
            "Eligible Personal": self.eligible_personal,
            "Eligible Business": self.eligible_business,
            "Eligible w/Debit": self.eligible_with_debit,
            "Eligible Personal w/Debit": self.personal_with_debit,
            "Eligible L12M": self.l12m_eligible,
        }
        if label not in mapping:
            raise KeyError(f"unknown denominator {label!r}; "
                           f"one of {sorted(mapping)}")
        return mapping[label]

    def sizes(self) -> dict[str, int]:
        return {
            "n_total": len(self.total),
            "n_open": len(self.open_accounts),
            "n_eligible": len(self.eligible),
            "n_eligible_personal": len(self.eligible_personal),
            "n_eligible_business": len(self.eligible_business),
            "n_eligible_with_debit": len(self.eligible_with_debit),
            "n_personal_with_debit": len(self.personal_with_debit),
            "n_l12m_open": len(self.l12m_open),
            "n_l12m_eligible": len(self.l12m_eligible),
            "n_responders": len(self.responders),
            "n_non_responders": len(self.non_responders),
        }


def build_subsets(df: pd.DataFrame, config: dict, anchor: Month) -> Subsets:
    """Apply the client's config to derive every denominator."""
    warnings: list[str] = []

    stat = norm(df.get("Stat Code"))
    prod = norm(df.get("Prod Code"))
    closed = pd.to_datetime(df.get("Date Closed"), errors="coerce") \
        if "Date Closed" in df.columns else None
    opened = pd.to_datetime(df.get("Date Opened"), errors="coerce") \
        if "Date Opened" in df.columns else None

    # ---- Open ---------------------------------------------------------
    if closed is not None:
        is_open = closed.isna()
    elif stat is not None:
        is_open = stat.str.upper().str.startswith("O")
        warnings.append("no Date Closed; open = Stat Code starts with O")
    else:
        is_open = pd.Series(True, index=df.index)
        warnings.append("no Date Closed or Stat Code; all accounts treated as open")
    open_accounts = df[is_open]

    # ---- Eligible, as a funnel so drop-off is visible ------------------
    elig_stat = {str(s).strip().upper() for s in config.get("EligibleStatusCodes", [])}
    elig_prod = {str(p).strip().upper() for p in config.get("EligibleProductCodes", [])}
    mail_ok = str(config.get("EligibleMailCode", "")).strip().upper()

    funnel: list[FunnelStage] = []
    total_n = len(df)

    def stage(label: str, count: int, prev: int | None) -> None:
        funnel.append(FunnelStage(
            label=label,
            count=count,
            pct_of_total=round(100 * count / total_n, 1) if total_n else 0.0,
            dropoff_pct=round(100 * (prev - count) / prev, 1)
            if prev else 0.0,
        ))

    stage("Total", total_n, None)
    stage("Open", len(open_accounts), total_n)

    mask = is_open
    if elig_stat and stat is not None:
        mask = mask & stat.str.upper().isin(elig_stat)
        stage("+ Eligible status", int(mask.sum()), len(open_accounts))
    elif not elig_stat:
        warnings.append("config has no EligibleStatusCodes; status filter skipped")

    if elig_prod and prod is not None:
        prev = int(mask.sum())
        mask = mask & prod.str.upper().isin(elig_prod)
        stage("+ Eligible product", int(mask.sum()), prev)
    elif not elig_prod:
        warnings.append("config has no EligibleProductCodes; product filter skipped")

    mailable = norm(df.get("Mailable?"))
    if mail_ok and mailable is not None:
        prev = int(mask.sum())
        mask = mask & mailable.str.upper().eq(mail_ok)
        stage("+ Mailable", int(mask.sum()), prev)

    eligible = df[mask]
    if not len(eligible):
        warnings.append("eligible set is empty; check status and product codes "
                        "against the values actually present in the file")

    # ---- Personal / business ------------------------------------------
    biz = is_business(df)
    eligible_personal = eligible[~biz.reindex(eligible.index, fill_value=False)]
    eligible_business = eligible[biz.reindex(eligible.index, fill_value=False)]

    # ---- Debit ---------------------------------------------------------
    debit = has_debit(df)
    eligible_with_debit = eligible[debit.reindex(eligible.index, fill_value=False)]
    personal_with_debit = eligible_personal[
        debit.reindex(eligible_personal.index, fill_value=False)]

    # ---- L12M, relative to the anchor (never to today) -----------------
    start = anchor.shift(-11)
    l12m_start = pd.Timestamp(start.year, start.month, 1)
    if opened is not None:
        recent = opened >= l12m_start
        l12m_open = open_accounts[recent.reindex(open_accounts.index, fill_value=False)]
        l12m_eligible = eligible[recent.reindex(eligible.index, fill_value=False)]
    else:
        warnings.append("no Date Opened; L12M subsets fall back to full sets")
        l12m_open, l12m_eligible = open_accounts, eligible

    # ---- Responders ----------------------------------------------------
    if "# of Responses" in df.columns:
        responded = df["# of Responses"] > 0
        offered = df["# of Offers"] > 0
        responders = eligible[responded.reindex(eligible.index, fill_value=False)]
        non_responders = eligible[
            (offered & ~responded).reindex(eligible.index, fill_value=False)]
    else:
        warnings.append("frame is not enriched; responder subsets are empty")
        responders = eligible.iloc[0:0]
        non_responders = eligible.iloc[0:0]

    return Subsets(
        total=df, open_accounts=open_accounts, eligible=eligible,
        eligible_personal=eligible_personal, eligible_business=eligible_business,
        eligible_with_debit=eligible_with_debit,
        personal_with_debit=personal_with_debit,
        l12m_open=l12m_open, l12m_eligible=l12m_eligible,
        responders=responders, non_responders=non_responders,
        anchor=anchor, l12m_start=l12m_start,
        funnel=funnel, warnings=warnings,
    )


def num_col(df, *names):
    """First present column coerced to numeric, else None.

    The pd.to_numeric(df.get("Col")) pattern is a trap: on an absent column
    df.get returns None, to_numeric turns it into a float nan, and the next
    .notna()/.fillna() raises AttributeError -- which the section wrapper
    swallows into one warning line. This helper keeps the is-None guards
    genuinely live.
    """
    import pandas as _pd
    for name in names:
        if name in df.columns:
            return _pd.to_numeric(df[name], errors="coerce")
    return None


def branch_names(series, mapping: dict):
    """The display name per row: mapped when the code is in
    BranchMapping, the raw value otherwise, '(blank)' for empty.

    Branch tables must group by THIS, never by the raw code: when
    several codes share one display name (1226 maps 14 keys onto fewer
    names), grouping by code produces duplicate rows and every surface
    that keys the table by name collapses them arbitrarily -- the #47
    full-book run blocked 1226's deck exactly that way.
    """
    mapping = mapping or {}
    return series.map(lambda c: mapping.get(str(c), str(c) or "(blank)"))
