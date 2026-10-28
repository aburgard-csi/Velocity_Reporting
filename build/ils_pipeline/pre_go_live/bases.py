# Ported from v5 02-Scripts/ils/pre_go_live/bases.py at 7ba1e63. Logic unchanged; copied whole.
"""Named bases -- the masks every section reports by. Replaces the
notebook's duplicated "(Eligible Only)" cells: build once, state the base.

Deleted rows (a date in Deleted) are dropped before any base is built and
the count reported; every later denominator excludes them."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .codes import Codes

ORDER = ["all", "personal", "business", "open", "eligible", "opted_in"]
LABELS = {"all": "All accounts", "personal": "Personal", "business": "Business",
          "open": "Open", "eligible": "Eligible (open, personal, OD-eligible)",
          "opted_in": "Reg-E opted in (open)"}


@dataclass
class Bases:
    masks: dict

    def names(self) -> list[str]:
        return [n for n in ORDER if n in self.masks]

    def label(self, name: str) -> str:
        return LABELS.get(name, name)

    def __getitem__(self, name: str) -> pd.Series:
        return self.masks[name]

    def counts(self) -> list[list]:
        return [[n, int(self.masks[n].sum()), self.label(n)] for n in self.names()]


def drop_deleted(df: pd.DataFrame, warn) -> pd.DataFrame:
    if "Deleted" in df.columns:
        deleted = df["Deleted"].notna()
        if deleted.any():
            warn(f"{int(deleted.sum())} deleted rows excluded from every base")
            return df[~deleted].copy()
    return df


def build(df: pd.DataFrame, codes: Codes, warn) -> Bases:
    masks: dict = {"all": pd.Series(True, index=df.index)}
    seg = df.get("Personal_Business")
    if seg is not None:
        masks["personal"] = (seg == "PERSONAL").fillna(False)
        masks["business"] = (seg == "BUSINESS").fillna(False)
        other = int((~masks["personal"] & ~masks["business"] & seg.notna()).sum())
        if other:
            warn(f"{other} rows with Personal_Business outside PERSONAL/BUSINESS")
    else:
        warn("no Personal_Business column; personal/business bases unavailable")
    status = df.get("Account Status Code")
    if status is not None and codes.open_status:
        masks["open"] = status.isin(codes.open_status).fillna(False)
        # Sanity guard: accounts opened recently should overwhelmingly sit in
        # the "open" codes. When they don't, the status legend is probably not
        # core account status (1737: recent openings are C, all ILS limits are
        # O -- the column looks like PROGRAM status, pending the vendor legend).
        opened = pd.to_datetime(df.get("Open Date"), errors="coerce") \
            if "Open Date" in df.columns else None
        if opened is not None and opened.notna().any():
            recent = opened >= (opened.max() - pd.DateOffset(months=12))
            n_recent = int(recent.sum())
            if n_recent >= 20:
                captured = int((recent & masks["open"]).sum())
                share = captured / n_recent
                if share < 0.3:
                    top = status[recent & ~masks["open"]].value_counts().head(3)
                    warn(f"open-status sanity check FAILED: only {captured} of "
                         f"{n_recent:,} accounts opened in the last 12 months fall in "
                         f"the confirmed open codes {codes.open_status} -- recent "
                         f"openings are mostly "
                         f"{', '.join(f'{k} ({v:,})' for k, v in top.items())}. "
                         f"This column may be PROGRAM status, not account status; "
                         f"confirm the legend with the client/vendor before "
                         f"trusting any base in this report.")
    od = df.get("OD Status Code (from Core)")
    if od is not None and codes.od_eligible and "open" in masks:
        masks["eligible"] = (masks["open"]
                             & masks.get("personal", pd.Series(True, index=df.index))
                             & od.isin(codes.od_eligible).fillna(False))
    rege = df.get("Reg-E Opt-In Value")
    if rege is not None and codes.rege_opt_in and "open" in masks:
        masks["opted_in"] = masks["open"] & rege.isin(codes.rege_opt_in).fillna(False)
    return Bases(masks=masks)
