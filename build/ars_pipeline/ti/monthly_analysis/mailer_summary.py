# Ported from ARS v5 02-Scripts/ars/monthly_analysis/mailer_summary.py at a491b5c (James Gilmore); logic unchanged.
"""The per-mailer summary -- James's legacy slide 1 (issue #80).

One record per completed wave: the mailed / responded / rate trio, the
response rate and share of every challenge tier, and the five fixed
"Inside the Numbers" stats. The tier rows add back up to the trio, which is
what made the legacy slide trustworthy at a glance.

Two of the five stats need history rather than a single wave: whether a
responder had ever responded before, and whether a repeat responder climbed
the ladder. Waves are walked oldest first so that history is measured, never
assumed.
"""

from __future__ import annotations

import pandas as pd

from . import rege
from .mailer import (_mailed, _pct, _responded, _wave_months,
                     challenge_segments, ladder_order)

NEW_ACCOUNT_YEARS = 2
SENIOR_AGE = 60
# a percentage taken over fewer accounts than this is noise, so the value is
# withheld and the denominator reported instead
MIN_DENOMINATOR = 10


def _share_of_responders(frame: pd.DataFrame, index, mask) -> float | None:
    if not len(index):
        return None
    return _pct(int(mask.sum()), len(index))


def _global_ladder(frame: pd.DataFrame, waves, config) -> dict[str, int]:
    """One ladder for the whole file, so a tier means the same thing in
    every wave. Built from the values that actually appear as responses."""
    seen: set[str] = set()
    for wave in waves:
        col = f"{wave.tag} Resp"
        if col not in frame.columns:
            continue
        responded = _responded(frame, wave)
        seen |= {v for v in frame.loc[responded, col].astype(str).str.strip()
                 if v and v.lower() != "nan"}
    return {tier: i for i, tier in enumerate(ladder_order(seen, config))}


def compute(subsets, config: dict, warn) -> dict:
    frame = subsets.total
    waves = _wave_months(frame)
    if not waves:
        return {}

    rank = _global_ladder(frame, waves, config)
    rege_col = rege._column_of_record(frame, subsets.anchor, lambda *_a: None)
    acct_age = pd.to_numeric(frame.get("Account Age"), errors="coerce") \
        if "Account Age" in frame.columns else None
    holder_age = pd.to_numeric(frame.get("Account Holder Age"), errors="coerce") \
        if "Account Holder Age" in frame.columns else None

    best_prior: dict = {}          # account -> best ladder rank so far
    summary: dict = {}
    # A running SUM across waves counts an account once per mailing, so it
    # reads as a headcount and is not one -- 1776 reported 52,999 that way.
    # Track the distinct accounts affected, and the worst single wave.
    untiered_accounts: set = set()
    worst_wave: tuple | None = None

    for wave in waves:
        mailed = _mailed(frame, wave)
        if not int(mailed.sum()):
            continue
        if not _responded(frame, wave).any():
            continue               # in flight -- no rate to report yet

        index = frame.index[mailed.to_numpy()]
        assign, tiers = challenge_segments(frame, index, wave, config)
        responded = _responded(frame, wave).loc[index]
        assigned = assign != ""
        untiered_accounts.update(index[(~assigned).to_numpy()])

        # The headline counts the WHOLE wave, exactly as the campaign table
        # does -- two slides in one deck must not disagree about how many
        # people were mailed. The tier rows account for the part that could
        # be placed in a challenge tier; the remainder is reported, not
        # hidden by shrinking the denominator to fit.
        n_mailed = len(index)
        n_assigned = int(assigned.sum())
        n_responded = int(responded.sum())
        if not n_mailed or not n_responded:
            continue

        by_tier = {}
        for tier in tiers:
            in_seg = assign == tier
            tier_mailed = int(in_seg.sum())
            tier_resp = int((in_seg & responded).sum())
            by_tier[tier] = {
                "mailed": tier_mailed,
                "responded": tier_resp,
                "rate": _pct(tier_resp, tier_mailed),
                "share": _pct(tier_resp, n_responded),
            }

        resp_index = index[responded.to_numpy()]
        resp_tiers = assign.loc[resp_index]

        first_time_mask = pd.Series(
            [acct not in best_prior for acct in resp_index], index=resp_index)
        repeat_mask = ~first_time_mask
        repeat_n = int(repeat_mask.sum())
        moved_up = sum(
            1 for acct in resp_index[repeat_mask.to_numpy()]
            if rank.get(resp_tiers[acct], -1) > best_prior[acct])

        inside = {
            "new_account_pct": (
                _share_of_responders(frame, resp_index,
                                     acct_age.loc[resp_index] < NEW_ACCOUNT_YEARS)
                if acct_age is not None else None),
            "age_60_plus_pct": (
                _share_of_responders(frame, resp_index,
                                     holder_age.loc[resp_index] >= SENIOR_AGE)
                if holder_age is not None else None),
            "rege_optin_pct": (
                _share_of_responders(
                    frame, resp_index,
                    rege.classify(frame.loc[resp_index, rege_col], config,
                                  lambda *_a: None) == rege.OPT_IN)
                if rege_col else None),
            "first_time_pct": _pct(int(first_time_mask.sum()), n_responded),
            "first_time_n": int(first_time_mask.sum()),
            "repeat_n": repeat_n,
            "moved_up_n": moved_up,
            "moved_up_denominator": repeat_n,
            "moved_up_pct": _pct(moved_up, repeat_n) if repeat_n else None,
        }

        if n_mailed - n_assigned:
            share = _pct(n_mailed - n_assigned, n_mailed)
            if worst_wave is None or share > worst_wave[1]:
                worst_wave = (wave.tag, share, n_mailed - n_assigned, n_mailed)

        summary[wave.tag] = {
            "mailed": n_mailed,
            "mailed_assigned": n_assigned,
            "mailed_unassigned": n_mailed - n_assigned,
            "responded": n_responded,
            "rate": _pct(n_responded, n_mailed),
            "tiers": tiers,
            "by_tier": by_tier,
            "inside": inside,
        }

        for acct in resp_index:
            this_rank = rank.get(resp_tiers[acct], -1)
            best_prior[acct] = max(best_prior.get(acct, -1), this_rank)

    if not summary:
        return {}
    if worst_wave:
        tag, share, missing, mailed = worst_wave
        warn(f"mailer summary: {tag} is the worst-covered mailing -- "
             f"{share:.0f}% of it carries no challenge tier "
             f"({missing:,} of {mailed:,} mailed); those accounts are counted "
             f"in the headline but in no tier row. Across all waves this "
             f"affects {len(untiered_accounts):,} distinct account(s). The "
             f"tier lives in the Mail column only where the file carries it; "
             f"if the share is high, it lives somewhere we have not found")
    return {"mailer_summary": summary}
