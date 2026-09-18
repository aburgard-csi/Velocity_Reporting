"""Value: what a debit card and a Reg E opt-in are each worth over 12 months.

Revenue has TWO components and both belong in both comparisons:

    interchange = 12-month spend x ICRate
    NSF/OD fees = 12-month items x NSF_OD_Fee
    total       = interchange + NSF/OD

A cardholder swipes and overdrafts; an opted-in account overdrafts at the
point of sale and therefore also swipes more. Counting only interchange for
the card and only fees for the opt-in understates each of them, which is what
an earlier version of this module did.

The windows come from the transform's `last 12-mon spend` / `Last 12-mon
Items` columns -- a true trailing twelve months rather than a partial window
scaled up, so the figure means what it says.

Requires ICRate and NSF_OD_Fee. A client missing them cannot produce these
numbers, and reporting $0 would be worse than reporting nothing.
"""

from __future__ import annotations

import pandas as pd

from ..core.periods import columns_for
from ..core.subsets import Subsets, has_debit, num_col

# Fine bands around years 2-4: the question "does value step up at year 3?"
# cannot be answered by a 1-2 / 3-5 / 5-10 grid.
TENURE_BANDS = [(0, 1, "< 1 yr"), (1, 2, "1-2 yr"), (2, 3, "2-3 yr"),
                (3, 4, "3-4 yr"), (4, 5, "4-5 yr"), (5, 7, "5-7 yr"),
                (7, 10, "7-10 yr"), (10, 200, "10+ yr")]
MIN_CELL = 50

SPEND_12 = "last 12-mon spend"
ITEMS_12 = "Last 12-mon Items"
SWIPES_12 = "last 12-mon swipes"


def _rate(config: dict, key: str) -> float | None:
    raw = str(config.get(key, "")).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _twelve_month(df: pd.DataFrame, direct: str, suffix: str,
                  warn, label: str) -> pd.Series | None:
    """The trailing-12 column, or a fallback summed from monthly columns."""
    if direct in df.columns:
        return pd.to_numeric(df[direct], errors="coerce").fillna(0)
    cols = columns_for(df.columns, suffix)[-12:]
    if not cols:
        warn(f"no {label} data; value section cannot compute it")
        return None
    if len(cols) < 12:
        warn(f"only {len(cols)} months of {label}; the 12-month value is "
             f"scaled up from a shorter window")
    values = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
    return values * (12 / len(cols))


def _revenue(df: pd.DataFrame, ic_rate: float, nsf_fee: float,
             warn) -> tuple[pd.Series, pd.Series] | None:
    spend = _twelve_month(df, SPEND_12, "Spend", warn, "spend")
    items = _twelve_month(df, ITEMS_12, "MTD", warn, "NSF/OD items")
    if spend is None and items is None:
        return None
    if spend is None:
        spend = pd.Series(0.0, index=df.index)
    if items is None:
        items = pd.Series(0.0, index=df.index)
    return spend * ic_rate, items * nsf_fee


def _compare(df: pd.DataFrame, mask: pd.Series, interchange: pd.Series,
             fees: pd.Series, prefix: str) -> dict:
    """Per-account revenue for the group that has the thing vs the group
    that does not, split into components."""
    total = interchange + fees
    with_n = int(mask.sum())
    without_n = int((~mask).sum())
    if not with_n or not without_n:
        return {}

    def per(series, m):
        return round(float(series[m].sum()) / int(m.sum()), 2)

    out = {
        f"{prefix}_n_with": with_n,
        f"{prefix}_n_without": without_n,
        f"{prefix}_ic_with": per(interchange, mask),
        f"{prefix}_ic_without": per(interchange, ~mask),
        f"{prefix}_nsf_with": per(fees, mask),
        f"{prefix}_nsf_without": per(fees, ~mask),
        f"{prefix}_total_with": per(total, mask),
        f"{prefix}_total_without": per(total, ~mask),
    }
    out[f"{prefix}_delta_ic"] = round(
        out[f"{prefix}_ic_with"] - out[f"{prefix}_ic_without"], 2)
    out[f"{prefix}_delta_nsf"] = round(
        out[f"{prefix}_nsf_with"] - out[f"{prefix}_nsf_without"], 2)
    out[f"{prefix}_delta"] = round(
        out[f"{prefix}_total_with"] - out[f"{prefix}_total_without"], 2)
    out[f"{prefix}_current_revenue"] = round(float(total.sum()))
    return out


def compute(subsets: Subsets, config: dict, warn) -> dict:
    ic_rate = _rate(config, "ICRate")
    nsf_fee = _rate(config, "NSF_OD_Fee")
    if ic_rate is None or nsf_fee is None:
        missing = [k for k, v in (("ICRate", ic_rate), ("NSF_OD_Fee", nsf_fee))
                   if v is None]
        warn(f"value section skipped: {', '.join(missing)} missing from config. "
             f"Reporting $0 would be worse than reporting nothing.")
        return {}

    out: dict = {"value_ic_rate": ic_rate, "value_nsf_fee": nsf_fee,
                 "value_window_months": 12}

    # ---- A11.1: value of a debit card -----------------------------------
    # Base is eligible personal: business card economics differ and would
    # blur the per-account figure.
    base = subsets.eligible_personal
    revenue = _revenue(base, ic_rate, nsf_fee, warn)
    if revenue is None:
        warn("no spend or NSF item columns; debit card value skipped")
    else:
        interchange, fees = revenue
        carded = has_debit(base)
        result = _compare(base, carded, interchange, fees, "value_debit")
        if not result:
            warn("need both carded and non-carded accounts for debit value")
        else:
            out.update(result)
            delta = result["value_debit_delta"]
            without_n = result["value_debit_n_without"]

            # Convert the non-carded population at three observable rates.
            hist = (len(subsets.eligible_with_debit) / len(subsets.eligible) * 100) \
                if len(subsets.eligible) else 0.0
            l12m = float(has_debit(subsets.l12m_eligible).mean() * 100) \
                if len(subsets.l12m_eligible) else 0.0
            out.update({
                "value_debit_hist_rate": round(hist, 1),
                "value_debit_l12m_rate": round(l12m, 1),
                "value_debit_pot_hist": round(without_n * delta * hist / 100),
                "value_debit_pot_l12m": round(without_n * delta * l12m / 100),
                "value_debit_pot_full": round(without_n * delta),
            })
            out["value_per_card"] = delta

        # ---- value by account age and branch -------------------------
        # an empty base (1780: zero eligible accounts) declines here --
        # everything below divides by n_all (#47 run 2 crash)
        total_rev = interchange + fees
        n_all = len(base)
        if not n_all:
            warn("eligible personal base is empty; value cuts and the "
                 "Reg E value skipped")
            return out
        port = (
            100 * int(carded.sum()) / n_all,
            float(total_rev[carded].sum()) / max(1, int(carded.sum())),
            float(total_rev[~carded].sum()) / max(1, int((~carded).sum())),
        )
        out["value_portfolio_take"] = round(port[0], 1)
        out["value_portfolio_per_acct"] = round(float(total_rev.sum()) / n_all, 2)

        age = num_col(base, "Account Age")
        if age is not None and age.notna().any():
            labels = [(label, age.between(low, high - 0.0001))
                      for low, high, label in TENURE_BANDS]
            rows = _cut(base, carded, interchange, fees, None, labels, port, warn)
            out["value_by_account_age"] = rows
            step = _biggest_step(rows)
            if step:
                out["value_age_biggest_step"] = step
        else:
            warn("no Account Age; value by tenure not computed")

        # ---- value by mailer status ----------------------------------
        # Two cuts on purpose. Responding to a debit challenge REQUIRES a
        # card, so responders are near-saturated on penetration and a raw
        # comparison partly measures the thing being measured. The carded-only
        # cut removes that and isolates intensity.
        if "# of Responses" in base.columns:
            responded = base["# of Responses"] > 0
            offered = base["# of Offers"] > 0
            groups = [
                ("Responder", offered & responded),
                ("Mailed non-responder", offered & ~responded),
                ("Not mailed", ~offered),
            ]
            rows = _cut(base, carded, interchange, fees, None, groups, port,
                        warn, min_cell=25)
            out["value_by_response"] = rows

            # Carded only: penetration is held at 100% for every group, so
            # any gap is per-account behaviour.
            carded_base = base[carded]
            if len(carded_base) >= 50:
                ic_c = interchange[carded]
                fee_c = fees[carded]
                total_c = ic_c + fee_c
                n_c = len(carded_base)
                port_c = float(total_c.sum()) / n_c
                carded_rows = []
                for label, mask in groups:
                    sub = mask[carded]
                    n = int(sub.sum())
                    if n < 25:
                        continue
                    carded_rows.append({
                        "group": label, "n": n,
                        "ic_per_acct": round(float(ic_c[sub].sum()) / n, 2),
                        "nsf_per_acct": round(float(fee_c[sub].sum()) / n, 2),
                        "value_per_acct": round(float(total_c[sub].sum()) / n, 2),
                        "gap": round(float(total_c[sub].sum()) / n - port_c, 2),
                    })
                out["value_by_response_carded"] = carded_rows
                out["value_carded_portfolio_per_acct"] = round(port_c, 2)
                resp = next((r for r in carded_rows
                             if r["group"] == "Responder"), None)
                non = next((r for r in carded_rows
                            if r["group"] == "Mailed non-responder"), None)
                if resp and non:
                    out["value_responder_premium"] = round(
                        resp["value_per_acct"] - non["value_per_acct"], 2)
                    out["value_responder_premium_ic"] = round(
                        resp["ic_per_acct"] - non["ic_per_acct"], 2)
                    out["value_responder_premium_nsf"] = round(
                        resp["nsf_per_acct"] - non["nsf_per_acct"], 2)

        branch = base.get("Branch")
        if branch is not None:
            mapping = config.get("BranchMapping", {}) or {}
            codes = branch.fillna("").astype(str).str.strip()
            labels = [(mapping.get(code, code or "(blank)"), codes == code)
                      for code in sorted(codes.unique()) if code or True]
            rows = _cut(base, carded, interchange, fees, None, labels, port, warn)
            rows.sort(key=lambda r: -r["value_per_acct"])
            out["value_by_branch"] = rows
            if len(rows) >= 2:
                out["value_branch_best"] = rows[0]
                out["value_branch_worst"] = rows[-1]
                out["value_branch_spread"] = round(
                    rows[0]["value_per_acct"] - rows[-1]["value_per_acct"], 2)
                # Which lever explains the spread?
                driven = [r for r in rows
                          if abs(r["gap"]) > 0.01]
                if driven:
                    pen = sum(abs(r["from_penetration"]) for r in driven)
                    inten = sum(abs(r["from_intensity"]) for r in driven)
                    out["value_branch_penetration_share"] = round(
                        100 * pen / (pen + inten), 1) if (pen + inten) else None
        else:
            warn("no Branch column; value by branch not computed")

    # ---- A11.2: value of a Reg E opt-in ----------------------------------
    rege_base = subsets.personal_with_debit
    revenue = _revenue(rege_base, ic_rate, nsf_fee, warn)
    if revenue is None or not len(rege_base):
        warn("no Reg E base or no revenue columns; Reg E value skipped")
        return out

    from .rege import OPT_IN, _column_of_record, classify

    column = _column_of_record(subsets.total, subsets.anchor, lambda _m: None)
    if column is None:
        warn("no Reg E column; Reg E value skipped")
        return out

    interchange, fees = revenue
    states = classify(rege_base[column], config, lambda _m: None)
    opted = states == OPT_IN

    result = _compare(rege_base, opted, interchange, fees, "value_rege")
    if not result:
        warn("need both opted-in and not-opted accounts for Reg E value")
        return out
    out.update(result)

    delta = result["value_rege_delta"]
    without_n = result["value_rege_n_without"]
    current = float(opted.mean() * 100) if len(rege_base) else 0.0

    # Opt-in among accounts that made ANY election is the honest ceiling:
    # the default bucket has not refused, it has not been asked.
    elected = states.isin([OPT_IN, "Opt Out"])
    elected_rate = (float((states[elected] == OPT_IN).mean() * 100)
                    if int(elected.sum()) else current)

    out.update({
        "value_rege_current_rate": round(current, 1),
        "value_rege_elected_rate": round(elected_rate, 1),
        "value_rege_pot_current": round(without_n * delta * current / 100),
        "value_rege_pot_elected": round(without_n * delta * elected_rate / 100),
        "value_rege_pot_full": round(without_n * delta),
        "value_per_optin": delta,
    })
    return out


def _decompose(actual_take: float, actual_with: float, actual_without: float,
               port_take: float, port_with: float, port_without: float) -> dict:
    """Split a group's value gap into penetration and intensity.

        value = take x rev_with + (1 - take) x rev_without

    penetration = (take_g - take_p) x (rev_with_p - rev_without_p)
        what the group gains purely by having more of them carded/opted in,
        holding per-account revenue at the portfolio level.

    intensity   = take_g x (with_g - with_p) + (1 - take_g) x (without_g - without_p)
        what it gains because ITS accounts generate more, holding penetration.

    The two sum exactly to the total gap. Penetration is what a branch can
    act on; intensity is mostly the customer base it draws.
    """
    t_g, t_p = actual_take / 100, port_take / 100
    value_g = t_g * actual_with + (1 - t_g) * actual_without
    value_p = t_p * port_with + (1 - t_p) * port_without
    penetration = (t_g - t_p) * (port_with - port_without)
    intensity = (t_g * (actual_with - port_with)
                 + (1 - t_g) * (actual_without - port_without))
    return {
        "value_per_acct": round(value_g, 2),
        "gap": round(value_g - value_p, 2),
        "from_penetration": round(penetration, 2),
        "from_intensity": round(intensity, 2),
    }


def _cut(base, mask_has, interchange, fees, grouper, labels, port, warn,
         min_cell=MIN_CELL) -> list[dict]:
    """Per-group value, penetration, and the decomposition."""
    total = interchange + fees
    rows = []
    for label, mask in labels:
        n = int(mask.sum())
        if n < min_cell:
            continue
        has = mask & mask_has
        without = mask & ~mask_has
        n_has, n_without = int(has.sum()), int(without.sum())
        if not n_has or not n_without:
            continue
        take = 100 * n_has / n
        rev_with = float(total[has].sum()) / n_has
        rev_without = float(total[without].sum()) / n_without
        row = {
            "group": label, "n": n, "take_rate": round(take, 1),
            "rev_with": round(rev_with, 2), "rev_without": round(rev_without, 2),
            "delta": round(rev_with - rev_without, 2),
            "ic_per_acct": round(float(interchange[mask].sum()) / n, 2),
            "nsf_per_acct": round(float(fees[mask].sum()) / n, 2),
        }
        row.update(_decompose(take, rev_with, rev_without, *port))
        rows.append(row)
    return rows


def _biggest_step(rows: list[dict]) -> dict | None:
    """Largest jump between adjacent bands -- answers 'where does it step up?'"""
    best = None
    for a, b in zip(rows, rows[1:]):
        step = b["value_per_acct"] - a["value_per_acct"]
        pct = (100 * step / a["value_per_acct"]) if a["value_per_acct"] else 0.0
        if best is None or step > best["step"]:
            best = {"from": a["group"], "to": b["group"],
                    "step": round(step, 2), "step_pct": round(pct, 1)}
    return best


def apply_to_leaks(metrics: dict) -> dict:
    """Price the leak table, and separate attributable value from selection."""
    out: dict = {}

    # The observed responder premium mixes two things: the mailer's effect and
    # the fact that responders were already heavier spenders. The cohort
    # section's difference-in-differences isolates the first. Reporting the
    # split keeps the attributable number from being overstated.
    # value_responder_attributable + selection split RETIRED (James,
    # issue #17, 2026-08-21): "never something I calculated and
    # confusing -- remove it altogether." The DiD lift keeps carrying
    # the control-honest story; the derived $/yr attribution does not
    # render anywhere and is no longer emitted.

    per_card = metrics.get("value_per_card")
    if per_card:
        leaks = metrics.get("dctr_leaks") or []
        if leaks:
            out["dctr_leaks_value"] = [
                {**leak, "annual_value": round(leak["accounts_lost"] * per_card)}
                for leak in leaks
            ]
        if metrics.get("dctr_leak_total"):
            out["dctr_leak_value"] = round(metrics["dctr_leak_total"] * per_card)
        gap = metrics.get("dctr_business_gap")
        if gap:
            out["dctr_business_value"] = round(gap["accounts_lost"] * per_card)

    per_optin = metrics.get("value_per_optin")
    if per_optin:
        leaks = metrics.get("rege_leaks") or []
        if leaks:
            out["rege_leaks_value"] = [
                {**leak, "annual_value": round(leak["accounts_lost"] * per_optin)}
                for leak in leaks
            ]
        if metrics.get("rege_leak_total"):
            out["rege_leak_value"] = round(metrics["rege_leak_total"] * per_optin)
        opp = metrics.get("rege_default_opportunity")
        if opp:
            out["rege_default_value"] = round(opp["at_elected_rate"] * per_optin)

    return out
