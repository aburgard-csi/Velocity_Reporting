# Ported from ARS v5 02-Scripts/ars/core/account_lenses.py at a491b5c (James Gilmore); logic unchanged.
"""Account lenses -- every cut that is a function of the ODD alone.

Both halves of the pipeline need the same answer to "is this an ICS
account". monthly_analysis runs first and holds the enriched frame;
transaction_intelligence runs after and re-indexes by account id. When each
half carried its own copy of the rule they drifted, and the transaction
chapter reported an ICS cut over zero accounts on every list-stamped client
(#104) -- ics.py read both flag columns, the transaction layer read only one.

The rules live here once. `masks_for` returns them on the frame's own index,
which is what monthly_analysis wants; `lens.build` re-indexes by account id
for the transaction side. Neither owns the definition.

Nothing here reads a transaction. Spend and swipe columns are ODD columns.
"""

from __future__ import annotations

import pandas as pd

from .periods import columns_for
from .subsets import is_business, norm

# Display order. STANDARD lenses exist for almost every client; EXTRA
# depend on a column or a program the client may not run.
STANDARD = ["all", "responders", "mailed_nonresp", "not_mailed",
            "business", "personal"]
EXTRA = ["new_accounts", "recently_inactive", "declining", "closed", "still_open",
         "ics", "ics_dm", "ics_ref", "mrpc"]

# The still-spending decliners (#245, legacy attrition_txn): recent three
# months under this share of the prior three, on spend OR swipes, and still
# spending. "Recently inactive" is the group that already went quiet; this is
# the group a win-back can still reach. Same rule as retention.classify_health.
DECLINE_MONTHS = 3
DECLINING_RATIO = 0.80

LABELS = {
    "all": "All accounts", "responders": "Responders",
    "mailed_nonresp": "Mailed non-responders", "not_mailed": "Not mailed",
    "business": "Business", "personal": "Personal",
    "new_accounts": "Opened last 12 mo", "recently_inactive": "Recently inactive",
    "declining": "Declining, still spending",
    "closed": "Closed accounts", "still_open": "Still open",
    "ics": "ICS accounts", "ics_dm": "ICS direct mail",
    "ics_ref": "ICS referral", "mrpc": "MRPC accounts",
}

YES_VALUES = {"Y", "YES", "1", "TRUE"}

# Simple program flags: ODD column -> the values meaning "yes".
PROGRAM_FLAGS = {"mrpc": ("MRPC", YES_VALUES)}

# ICS is stamped in one of two places and this layer accepts both: the
# documented "ICS Account" column, or "DM-REF Source" -- what
# monthly_analysis/ics_sources.py writes when it joins the direct-mail and
# referral lists onto the ODD (values "", "DM", "REF", "DM+REF").
ICS_FLAG_COLUMN = "ICS Account"
ICS_SOURCE_COLUMN = "DM-REF Source"

# Family name -> ODD columns tried in order. A family is a cut with many
# values (one per branch) rather than a yes/no mask.
# "Branch Name" is the mapped display name lens.build attaches when the
# client config carries a BranchMapping. It is tried FIRST: several codes can
# share one display name (1226 maps 14 keys onto fewer names), and grouping by
# raw code produces duplicate rows that every name-keyed surface then
# collapses arbitrarily -- the #47 full-book run blocked a deck exactly so.
FAMILY_COLUMNS = {"branch": ("Branch Name", "Branch"),
                  "product": ("Prod Desc", "Prod Code"),
                  "swipe_tier": ("SwipeCat3",)}

NEW_ACCOUNT_MONTHS = 12
# "recently inactive" needs a clean before/after: three silent months
# against the nine before them.
QUIET_MONTHS = 3
INACTIVE_LOOKBACK = 12


def ics_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    """The program-wide `ics` mask plus its `ics_dm` / `ics_ref` channels.

    An account on both lists counts in both channels -- it was reached
    twice, and that is a fact about acquisition, not a double count of the
    account. `ics_source_counts` in ics.py reports it the same way.
    """
    out: dict[str, pd.Series] = {}
    if ICS_FLAG_COLUMN in df.columns:
        out["ics"] = norm(df[ICS_FLAG_COLUMN]).str.upper().isin(YES_VALUES)
    if ICS_SOURCE_COLUMN in df.columns:
        values = norm(df[ICS_SOURCE_COLUMN]).str.upper()
        stamped = values.str.len() > 0
        out["ics"] = (out["ics"] | stamped) if "ics" in out else stamped
        out["ics_dm"] = values.str.contains("DM", regex=False)
        out["ics_ref"] = values.str.contains("REF", regex=False)
    return out


def masks_for(df: pd.DataFrame, anchor_end: pd.Timestamp,
              warn=lambda *_a: None) -> dict[str, pd.Series]:
    """Every account lens, as boolean Series on `df`'s own index.

    Absent columns drop their lens rather than raising: a client without a
    Date Closed simply has no `closed` lens, and the caller reports which
    lenses it got.
    """
    masks: dict[str, pd.Series] = {"all": pd.Series(True, index=df.index)}

    if "Response Grouping" in df.columns:
        grouping = norm(df["Response Grouping"])
        masks["responders"] = grouping.isin(["SO-SR", "MO-SR", "MR"])
        masks["mailed_nonresp"] = grouping == "Non-Responder"
        masks["not_mailed"] = grouping == "No Offer"
    else:
        warn("ODD enrichment has no Response Grouping; responder lenses "
             "unavailable")

    if "Business?" in df.columns:
        biz = is_business(df)
        masks["business"] = biz
        masks["personal"] = ~biz

    opened = (pd.to_datetime(df["Date Opened"], errors="coerce")
              if "Date Opened" in df.columns else None)
    if opened is not None and opened.notna().any():
        masks["new_accounts"] = opened >= (
            anchor_end - pd.DateOffset(months=NEW_ACCOUNT_MONTHS))

    # A closed account still transacted, still responded, still closed --
    # excluding it would undercount by dropping everyone who already left.
    closed = (pd.to_datetime(df["Date Closed"], errors="coerce")
              if "Date Closed" in df.columns else None)
    if closed is not None and closed.notna().any():
        masks["closed"] = closed.notna()
        masks["still_open"] = closed.isna()
    else:
        warn("ODD has no usable Date Closed; closed/still-open lenses "
             "unavailable, so any population built here is the book minus "
             "everyone who already left")

    spend_cols = columns_for(df.columns, "Spend")
    if len(spend_cols) >= INACTIVE_LOOKBACK:
        sp = df[spend_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
        recent = sp[spend_cols[-QUIET_MONTHS:]].sum(axis=1)
        prior = sp[spend_cols[-INACTIVE_LOOKBACK:-QUIET_MONTHS]].sum(axis=1)
        masks["recently_inactive"] = (recent == 0) & (prior > 0)
    if len(spend_cols) >= 2 * DECLINE_MONTHS:
        sp = df[spend_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
        rec = sp[spend_cols[-DECLINE_MONTHS:]].mean(axis=1)
        pri = sp[spend_cols[-2 * DECLINE_MONTHS:-DECLINE_MONTHS]].mean(axis=1)
        falling = (pri > 0) & (rec > 0) & (rec < pri * DECLINING_RATIO)
        swipe_cols = columns_for(df.columns, "Swipes")
        if len(swipe_cols) >= 2 * DECLINE_MONTHS:
            sw = df[swipe_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            s_rec = sw[swipe_cols[-DECLINE_MONTHS:]].mean(axis=1)
            s_pri = sw[swipe_cols[-2 * DECLINE_MONTHS:-DECLINE_MONTHS]].mean(axis=1)
            falling |= (pri > 0) & (rec > 0) & (s_pri > 0) & (s_rec < s_pri * DECLINING_RATIO)
        masks["declining"] = falling

    for name, (col, yes) in PROGRAM_FLAGS.items():
        if col in df.columns:
            masks[name] = norm(df[col]).str.upper().isin(yes)

    masks.update(ics_masks(df))
    return masks


def ordered_names(masks: dict) -> list[str]:
    """Present lenses in display order, not dict order."""
    return [n for n in STANDARD + EXTRA if n in masks]


def label(name: str) -> str:
    return LABELS.get(name, name)


def family_of(df: pd.DataFrame, family: str) -> dict[str, pd.Index]:
    """`{value: index}` for a many-valued cut (branch / product / swipe tier).

    Empty when the ODD carries none of the family's columns, so a caller can
    say the cut is unavailable rather than printing an empty chart.
    """
    for col in FAMILY_COLUMNS.get(family, ()):
        if col in df.columns:
            values = norm(df[col])
            return {str(v): values.index[(values == v).to_numpy()]
                    for v in values.dropna().unique() if str(v).strip()}
    return {}


def ics_warning(masks: dict) -> str | None:
    """What the run log should say about the ICS lens, or None."""
    if "ics" not in masks:
        return None
    n = int(masks["ics"].sum())
    if not n:
        return ("ICS flag column present but no account is stamped; the ICS "
                "lens carries no accounts")
    dm = int(masks.get("ics_dm", masks["ics"]).sum())
    ref = int(masks.get("ics_ref", masks["ics"]).sum())
    return (f"ICS lens active: {n:,} stamped accounts (DM {dm:,} / REF "
            f"{ref:,}) -- every section that takes a lens reports an ICS cut")
