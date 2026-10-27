# Ported from ARS v5 02-Scripts/ars/monthly_analysis/interchange.py at a491b5c (James Gilmore); logic unchanged.
"""Interchange: PIN vs signature routing, and what the mix is worth.

Signature transactions earn materially more interchange than PIN, so the
routing mix is a revenue lever that needs no new accounts and no new spend.

RATE CALIBRATION. The legacy analysis hardcoded PIN 0.25% / SIG 0.55%. Those
are generic Durbin-exempt figures and they contradict the per-client ICRate
in clients_config.json -- 1615's 0.79% is above the hardcoded SIG rate, so no
mix of the two could ever produce it. Two sections of one deck would then
report different interchange for the same client.

So the PREMIUM is kept (signature earns ~2.2x PIN) and the levels are solved
so the blended rate equals the client's actual ICRate:

    pin_rate = total_spend * ICRate / (pin_spend + premium * sig_spend)
    sig_rate = premium * pin_rate

Everything downstream then reconciles with the value section by construction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.periods import Month, columns_for
from ..core.subsets import Subsets, has_debit, is_business, norm

# Signature earns this multiple of the PIN rate. From the legacy 0.55/0.25.
DEFAULT_SIG_PREMIUM = 2.2
# Fallback levels, used only when the client has no ICRate.
FALLBACK_PIN_RATE = 0.0025
FALLBACK_SIG_RATE = 0.0055

PIN_HEAVY_THRESHOLD = 0.80
SIG_GOAL = 60.0
SIG_RISK = 40.0
SHIFT_SCENARIOS = (0.10, 0.25, 0.50, 1.00)

AGE_BANDS = [(18, 25, "18-24"), (25, 35, "25-34"), (35, 45, "35-44"),
             (45, 55, "45-54"), (55, 65, "55-64"), (65, 120, "65+")]


def _pct(n, d, digits=1) -> float:
    return round(100 * n / d, digits) if d else 0.0


def _sum_cols(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    if not cols:
        return pd.Series(0.0, index=df.index)
    return df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)


def calibrate_rates(pin_spend: float, sig_spend: float, config: dict,
                    warn) -> tuple[float, float, str]:
    """Solve PIN and SIG rates so the blended rate matches the client's."""
    premium = config.get("SigPinPremium")
    try:
        premium = float(premium) if premium else DEFAULT_SIG_PREMIUM
    except (TypeError, ValueError):
        premium = DEFAULT_SIG_PREMIUM

    raw = str(config.get("ICRate", "")).strip()
    total = pin_spend + sig_spend
    if not raw or not total:
        warn("no ICRate; interchange uses generic Durbin-exempt rates and will "
             "NOT reconcile with the value section")
        return FALLBACK_PIN_RATE, FALLBACK_SIG_RATE, "fallback"

    try:
        blended = float(raw)
    except ValueError:
        warn(f"ICRate {raw!r} is not numeric; using generic rates")
        return FALLBACK_PIN_RATE, FALLBACK_SIG_RATE, "fallback"

    denominator = pin_spend + premium * sig_spend
    if denominator <= 0:
        return FALLBACK_PIN_RATE, FALLBACK_SIG_RATE, "fallback"

    pin_rate = total * blended / denominator
    return pin_rate, pin_rate * premium, "calibrated"


def compute(subsets: Subsets, config: dict, warn) -> dict:
    base = subsets.eligible
    pin_d = columns_for(base.columns, "PIN $")
    sig_d = columns_for(base.columns, "Sig $")
    pin_c = columns_for(base.columns, "PIN #")
    sig_c = columns_for(base.columns, "Sig #")

    if not pin_d or not sig_d:
        warn("no PIN/Sig dollar columns; interchange section skipped")
        return {}

    months = [Month.from_tag(c.split()[0]) for c in pin_d]
    n_months = len(months)

    acct_pin_d = _sum_cols(base, pin_d)
    acct_sig_d = _sum_cols(base, sig_d)
    acct_pin_c = _sum_cols(base, pin_c)
    acct_sig_c = _sum_cols(base, sig_c)
    acct_total_d = acct_pin_d + acct_sig_d

    pin_spend = float(acct_pin_d.sum())
    sig_spend = float(acct_sig_d.sum())
    total_spend = pin_spend + sig_spend
    if total_spend <= 0:
        warn("no card spend in the eligible base; interchange section skipped")
        return {}

    if pin_spend <= 0 or sig_spend <= 0:
        missing = "PIN" if pin_spend <= 0 else "SIG"
        warn(
            f"{missing} dollars are zero for every month: this file does not "
            f"split card spend by routing, so PIN/SIG analysis does not apply "
            f"to this client. Total spend and interchange are still reported."
        )
        rate = None
        raw = str(config.get("ICRate", "")).strip()
        try:
            rate = float(raw) if raw else None
        except ValueError:
            rate = None
        result = {
            "ic_routing_available": False,
            "ic_months": n_months,
            "ic_window": [months[0].tag, months[-1].tag],
            "ic_total_spend": round(total_spend),
            "ic_pin_spend": round(pin_spend),
            "ic_sig_spend": round(sig_spend),
        }
        if rate:
            annual = 12.0 / n_months if n_months else 1.0
            result["ic_current_annual"] = round(total_spend * rate * annual)
        return result

    pin_rate, sig_rate, source = calibrate_rates(pin_spend, sig_spend, config, warn)
    annualize = 12.0 / n_months if n_months else 1.0

    current_ic = pin_spend * pin_rate + sig_spend * sig_rate
    out: dict = {
        "ic_routing_available": True,
        "ic_rate_source": source,
        "ic_pin_rate": round(pin_rate, 6),
        "ic_sig_rate": round(sig_rate, 6),
        "ic_sig_premium": round(sig_rate / pin_rate, 2) if pin_rate else None,
        "ic_months": n_months,
        "ic_window": [months[0].tag, months[-1].tag],
        "ic_pin_spend": round(pin_spend),
        "ic_sig_spend": round(sig_spend),
        "ic_total_spend": round(total_spend),
        "ic_sig_ratio": _pct(sig_spend, total_spend),
        "ic_current": round(current_ic),
        "ic_current_annual": round(current_ic * annualize),
        "ic_pin_component": round(pin_spend * pin_rate),
        "ic_sig_component": round(sig_spend * sig_rate),
    }

    # Average ticket -- signature tickets are usually larger, which is part of
    # why the mix matters.
    pin_count = float(acct_pin_c.sum())
    sig_count = float(acct_sig_c.sum())
    if pin_count:
        out["ic_pin_ticket"] = round(pin_spend / pin_count, 2)
    if sig_count:
        out["ic_sig_ticket"] = round(sig_spend / sig_count, 2)
    if pin_count + sig_count:
        out["ic_sig_share_of_swipes"] = _pct(sig_count, pin_count + sig_count)

    # ---- monthly trend --------------------------------------------------
    trend = []
    for i, month in enumerate(months):
        p = float(pd.to_numeric(base[pin_d[i]], errors="coerce").fillna(0).sum())
        s_col = f"{month.tag} Sig $"
        s = float(pd.to_numeric(base[s_col], errors="coerce").fillna(0).sum()) \
            if s_col in base.columns else 0.0
        total = p + s
        trend.append([month.tag, round(p), round(s), _pct(s, total),
                      round(p * pin_rate + s * sig_rate)])
    out["ic_monthly"] = trend

    ratios = [row[3] for row in trend]
    if len(ratios) >= 3:
        slope = float(np.polyfit(np.arange(len(ratios)), np.array(ratios), 1)[0])
        out["ic_sig_slope_pp_per_mo"] = round(slope, 3)
        early = float(np.mean(ratios[:3]))
        late = float(np.mean(ratios[-3:]))
        out["ic_sig_shift_pp"] = round(late - early, 1)
        out["ic_sig_direction"] = ("improving" if late - early > 1
                                   else "declining" if late - early < -1
                                   else "stable")
    out["ic_sig_vs_goal_pp"] = round(out["ic_sig_ratio"] - SIG_GOAL, 1)

    # ---- shift scenarios -------------------------------------------------
    scenarios = []
    for shift in SHIFT_SCENARIOS:
        new_pin = pin_spend * (1 - shift)
        new_sig = sig_spend + pin_spend * shift
        ic = (new_pin * pin_rate + new_sig * sig_rate) * annualize
        scenarios.append([
            f"{shift:.0%} of PIN to SIG", round(ic),
            round(ic - out["ic_current_annual"]),
            _pct(new_sig, total_spend),
        ])
    out["ic_scenarios"] = scenarios
    out["ic_max_opportunity"] = scenarios[-1][2]

    # ---- PIN-heavy accounts ---------------------------------------------
    active = acct_total_d > 0
    pin_ratio = pd.Series(0.0, index=base.index)
    pin_ratio[active] = acct_pin_d[active] / acct_total_d[active]
    heavy = active & (pin_ratio >= PIN_HEAVY_THRESHOLD)

    opportunity = (acct_total_d * sig_rate) - (acct_pin_d * pin_rate
                                               + acct_sig_d * sig_rate)
    out["ic_active_n"] = int(active.sum())
    out["ic_pin_heavy_n"] = int(heavy.sum())
    out["ic_pin_heavy_pct"] = _pct(int(heavy.sum()), int(active.sum()))
    out["ic_pin_heavy_spend"] = round(float(acct_total_d[heavy].sum()))
    out["ic_pin_heavy_opportunity"] = round(
        float(opportunity[heavy].sum()) * annualize)
    out["ic_total_opportunity"] = round(float(opportunity.sum()) * annualize)

    # ---- who routes PIN? -------------------------------------------------
    def ratio_for(mask: pd.Series) -> list:
        p = float(acct_pin_d[mask].sum())
        s = float(acct_sig_d[mask].sum())
        return [int(mask.sum()), _pct(s, p + s), round(p + s)]

    biz = is_business(base)
    out["ic_by_type"] = [
        ["Personal", *ratio_for(active & ~biz)],
        ["Business", *ratio_for(active & biz)],
    ]

    if "Account Holder Age" in base.columns:
        age = pd.to_numeric(base["Account Holder Age"], errors="coerce")
        rows = []
        for low, high, label in AGE_BANDS:
            mask = active & age.between(low, high - 0.001)
            if int(mask.sum()) >= 10:
                rows.append([label, *ratio_for(mask)])
        out["ic_by_age"] = rows

    prod = norm(base.get("Prod Desc"))
    if prod is None:
        prod = norm(base.get("Prod Code"))
    if prod is not None:
        rows = []
        for value, group in base.groupby(prod):
            mask = active & (prod == value)
            n = int(mask.sum())
            if n < 10:
                continue
            counts = ratio_for(mask)
            rows.append([str(value)[:30] or "(blank)", *counts,
                         round(float(opportunity[mask].sum()) * annualize)])
        rows.sort(key=lambda r: r[1], reverse=True)
        out["ic_by_product"] = rows[:15]
        # A product sitting far below the rest usually defaults to PIN.
        pin_default = [r for r in rows if r[2] < SIG_RISK]
        out["ic_pin_default_products"] = sorted(
            pin_default, key=lambda r: -r[4])[:5]

    # ---- tie to the ARS program -----------------------------------------
    if "# of Responses" in base.columns:
        responded = base["# of Responses"] > 0
        offered = base["# of Offers"] > 0
        out["ic_by_response"] = [
            ["Responder", *ratio_for(active & offered & responded)],
            ["Mailed non-responder", *ratio_for(active & offered & ~responded)],
            ["Not mailed", *ratio_for(active & ~offered)],
        ]
    return out
