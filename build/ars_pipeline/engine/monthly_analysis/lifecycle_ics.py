"""The ICS programme case, on the lifecycle curves.

Split from lifecycle_report.py because it is its own question -- does the
programme produce better accounts -- and because that module had grown past
the 300-line mark this repo holds itself to.

MATCHED ON VINTAGE, always. ICS accounts are recent because the programme is
young. Comparing their onboarding ramp against a book full of ten-year
accounts would credit ICS for being new, which is the easiest way to make a
programme look good and the least defensible.

Keys: life_ramp_ics, life_ramp_non, life_ramp_ics_lift_pct,
life_decline_ics, life_decline_non, life_divergence_month_ics / _non.
"""

from __future__ import annotations

import pandas as pd

from ..core.account_lenses import ics_masks
from . import lifecycle as L
from .lifecycle_report import MIN_CURVE_BASE, _curves


def compare(df, opened, closed, spend_cols, months, window, out, warn):
    """ICS against non-ICS, matched on vintage.

    Called BEFORE the pre-closure section, not after: the onboarding ramp
    needs no closures, and gating it behind the closure check made it
    unreachable on any book whose ODD carries none.
    """
    # MATCHED ON VINTAGE, always. ICS accounts are recent because the
    # programme is young; comparing their ramp against a book full of
    # ten-year accounts would credit ICS for being new. The non-ICS side is
    # therefore restricted to accounts opened in the same window as the ICS
    # cohort, so the only systematic difference left is the programme.
    masks = ics_masks(df)
    ics = masks.get("ics")
    if ics is None or not ics.any():
        return

    ics_opened = opened[ics & opened.notna()]
    if not len(ics_opened):
        warn("lifecycle: ICS accounts carry no open dates; ICS comparison "
             "skipped")
        return
    lo, hi = ics_opened.min(), ics_opened.max()
    same_vintage = opened.between(lo, hi)
    out["life_ics_vintage"] = [str(lo.date()), str(hi.date())]
    out["life_ics_vintage_note"] = (
        "the non-ICS side is restricted to accounts opened in the same window "
        "as the ICS cohort; without that the comparison credits ICS for being "
        "younger than the book")

    for name, mask in (("ics", ics & same_vintage),
                       ("non", ~ics & same_vintage)):
        n = int(mask.sum())
        out[f"life_{name}_n"] = n
        if n < MIN_CURVE_BASE:
            warn(f"lifecycle: {n} {name.upper()} account(s) in the shared "
                 f"vintage window, under {MIN_CURVE_BASE}; that side of the "
                 f"comparison is not drawn")
            continue
        ramp = _curves(df[mask], spend_cols, months, opened[mask], window,
                       "forward", MIN_CURVE_BASE)
        if ramp.get("spend"):
            out[f"life_ramp_{name}"] = ramp["spend"]

        band = closed.notna() & mask
        if int(band.sum()) >= MIN_CURVE_BASE:
            cur = _curves(df[band], spend_cols, months, closed[band], window,
                          "backward", MIN_CURVE_BASE)
            if cur.get("spend"):
                out[f"life_decline_{name}"] = cur["spend"]

    if out.get("life_ramp_ics") and out.get("life_ramp_non"):
        out["life_ramp_columns_ics"] = ["offset_months", "n", "mean", "total",
                                        "pct_active"]
        # The headline for the programme case: at the same months since
        # opening, does an ICS account spend more than a same-vintage one?
        gaps = []
        for a, b in zip(out["life_ramp_ics"], out["life_ramp_non"]):
            if a[2] is None or b[2] is None or not b[2]:
                gaps.append([a[0], None])
            else:
                gaps.append([a[0], round(100 * (a[2] - b[2]) / b[2], 1)])
        out["life_ramp_ics_lift_pct"] = gaps
        out["life_ramp_ics_lift_columns"] = ["offset_months", "ics_lift_pct"]

    if out.get("life_decline_ics") and out.get("life_decline_non"):
        # Whose fade starts earlier. A LATER divergence for ICS means those
        # accounts held on longer before they went.
        ics_div = L.divergence_month(out["life_decline_ics"],
                                     out.get("life_control") or [])
        non_div = L.divergence_month(out["life_decline_non"],
                                     out.get("life_control") or [])
        out["life_divergence_month_ics"] = ics_div
        out["life_divergence_month_non"] = non_div
    return
