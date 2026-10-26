# Ported from ARS v5 02-Scripts/ars/monthly_analysis/ladder.py at a491b5c (James Gilmore); logic unchanged.
"""The response ladder.

Tier definitions are ported from the legacy analytics
(campaign/07_response_ladder.py) and are the authoritative rules:

    TH-##  -> tier ##      the threshold amount IS the tier
    NU 5+  -> tier 1       and NU 5 .. NU 10 written without the plus
    NU 1-4 -> tier 0       tracked, but NOT a response
    blank  -> tier 0       no response

Two things the legacy code gets right that a naive reading does not:

  * The tier is numeric, so TH-10 -> TH-25 is a move of 15, not "one step".
  * Movement is measured against the account's BEST PRIOR tier across every
    earlier wave, not against the immediately preceding wave. An account that
    hit TH-25, skipped two waves, then took TH-10 has moved DOWN.

Program rule (penalty box): after responding at a tier the account must move
up or down; the same tier cannot repeat until PENALTY_BOX_WAVES mailers have
passed.
"""

from __future__ import annotations

import re

import pandas as pd

PENALTY_BOX_WAVES = 3          # 3 mailers = 6 months

_TH_RE = re.compile(r"^TH[\s\-_]?(\d+)", re.I)
# NU 5+ / NU5+ / NU 5 .. NU 10 all count as a response; NU 1-4 does not.
_NU_SUCCESS = {"NU 5+", "NU5+", "NU 5", "NU 6", "NU 7", "NU 8", "NU 9", "NU 10"}
_NU_TRACKED = {"NU 1-4", "NU1-4"}


def normalize(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).replace("\x00", "").strip().upper()


def is_response(value) -> bool:
    """True when the value counts as a response to the offer."""
    v = normalize(value)
    if not v:
        return False
    if v.startswith("TH"):
        return True
    return v in _NU_SUCCESS


def is_tracked(value) -> bool:
    """NU 1-4: recorded activity that falls short of a response."""
    return normalize(value) in _NU_TRACKED


def tier(value) -> int:
    """Ladder position. TH-## -> ##, NU success -> 1, anything else -> 0."""
    v = normalize(value)
    if not v:
        return 0
    match = _TH_RE.match(v)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return 5
    if v in _NU_SUCCESS:
        return 1
    return 0


def group(value) -> str:
    """NU | TH | tracked | none -- the alternation rule works on groups."""
    v = normalize(value)
    if not v:
        return "none"
    if v.startswith("TH"):
        return "TH"
    if v in _NU_SUCCESS:
        return "NU"
    if v in _NU_TRACKED or v.startswith("NU"):
        return "tracked"
    return "none"


def series_is_response(series: pd.Series) -> pd.Series:
    return series.map(is_response)


def series_tier(series: pd.Series) -> pd.Series:
    return series.map(tier)


def build_history(df: pd.DataFrame, waves, resp_col) -> dict:
    """Per-wave response and tier matrices, aligned on the frame's index.

    Returns {"response": DataFrame, "tier": DataFrame} with one column per
    wave, in chronological order.
    """
    response = {}
    tiers = {}
    for wave in waves:
        col = resp_col(wave)
        if col not in df.columns:
            continue
        values = df[col]
        response[wave.tag] = series_is_response(values)
        tiers[wave.tag] = series_tier(values)
    return {
        "response": pd.DataFrame(response, index=df.index),
        "tier": pd.DataFrame(tiers, index=df.index),
    }


def ladder_movement(history: dict, wave_tags: list[str]) -> dict:
    """First-time vs repeat, and movement against each account's best prior.

    Aggregated across every wave from the second onward, which is how the
    legacy report frames it -- a per-wave view hides accounts that skip a
    wave and come back.
    """
    response = history["response"]
    tiers = history["tier"]
    available = [t for t in wave_tags if t in response.columns]
    if len(available) < 2:
        return {}

    first_time = 0
    repeat = 0
    moves = {"Up": 0, "Same": 0, "Down": 0}
    per_wave = []

    for i, tag in enumerate(available[1:], start=1):
        prior_tags = available[:i]
        current = response[tag]
        if not current.any():
            continue

        responded_before = response[prior_tags].any(axis=1)
        is_repeat = current & responded_before
        is_first = current & ~responded_before

        first_time += int(is_first.sum())
        repeat += int(is_repeat.sum())

        wave_moves = {"Up": 0, "Same": 0, "Down": 0}
        if is_repeat.any():
            # Best tier the account ever reached in a prior wave.
            prior_best = tiers[prior_tags].where(response[prior_tags]).max(axis=1)
            current_tier = tiers[tag]
            rows = is_repeat & prior_best.notna()
            wave_moves["Up"] = int((rows & (current_tier > prior_best)).sum())
            wave_moves["Same"] = int((rows & (current_tier == prior_best)).sum())
            wave_moves["Down"] = int((rows & (current_tier < prior_best)).sum())
            for key in moves:
                moves[key] += wave_moves[key]

        per_wave.append({
            "wave": tag,
            "responders": int(current.sum()),
            "first_time": int(is_first.sum()),
            "repeat": int(is_repeat.sum()),
            **wave_moves,
        })

    total = first_time + repeat
    return {
        "ladder_first_time": first_time,
        "ladder_repeat": repeat,
        "ladder_repeat_pct": round(100 * repeat / total, 1) if total else 0.0,
        "ladder_movement": [[k, v] for k, v in moves.items()],
        "ladder_by_wave": per_wave,
    }


def nu_conversion(df: pd.DataFrame, waves, resp_col) -> dict:
    """Do NU 1-4 accounts ever reach NU 5+ or a TH tier?

    NU 1-4 is activity that fell short. Whether those accounts convert later
    is the question that decides if partial engagement is worth anything.
    """
    partial_ever = pd.Series(False, index=df.index)
    success_ever = pd.Series(False, index=df.index)
    by_wave = []

    for wave in waves:
        col = resp_col(wave)
        if col not in df.columns:
            continue
        values = df[col]
        partial_now = values.map(is_tracked)
        success_now = values.map(is_response)

        converted = int((partial_ever & success_now).sum())
        by_wave.append({
            "wave": wave.tag,
            "nu_partial": int(partial_now.sum()),
            "nu_success": int(success_now.sum()),
            "prior_partial_converted": converted,
            "partial_pool": int(partial_ever.sum()),
        })
        partial_ever = partial_ever | partial_now
        success_ever = success_ever | success_now

    total_partial = int(partial_ever.sum())
    converted_ever = int((partial_ever & success_ever).sum())
    return {
        "nu_partial_ever": total_partial,
        "nu_success_ever": int(success_ever.sum()),
        "nu_converted_ever": converted_ever,
        "nu_conversion_pct": round(100 * converted_ever / total_partial, 1)
        if total_partial else 0.0,
        "nu_never_converted": total_partial - converted_ever,
        "nu_by_wave": by_wave,
    }


def penalty_box(history: dict, wave_tags: list[str]) -> dict:
    """Same-tier repeats inside the penalty-box window.

    The program forbids repeating a tier until PENALTY_BOX_WAVES mailers have
    passed, so a non-zero count is a data or suppression-rule problem rather
    than a finding about customers.
    """
    response = history["response"]
    tiers = history["tier"]
    available = [t for t in wave_tags if t in response.columns]
    if len(available) < 2:
        return {}

    violations = 0
    by_tier: dict[int, int] = {}
    for i, tag in enumerate(available):
        window = available[max(0, i - PENALTY_BOX_WAVES + 1):i]
        if not window:
            continue
        current = response[tag]
        current_tier = tiers[tag]
        for prior in window:
            same = current & response[prior] & (current_tier == tiers[prior]) \
                & (current_tier > 0)
            count = int(same.sum())
            if count:
                violations += count
                for value in current_tier[same].unique():
                    by_tier[int(value)] = by_tier.get(int(value), 0) + int(
                        (same & (current_tier == value)).sum())

    return {
        "penalty_box_waves": PENALTY_BOX_WAVES,
        "penalty_box_violations": violations,
        "penalty_box_by_tier": sorted(([k, v] for k, v in by_tier.items()),
                                      key=lambda r: -r[1]),
    }
