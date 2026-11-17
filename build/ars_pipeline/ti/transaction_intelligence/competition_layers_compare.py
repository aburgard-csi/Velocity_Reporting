"""
competition_layers_compare.py — what changed in the layered competition figures since the prior month's pack,
and the one row a month adds to a portfolio benchmark.

New to RPE (not a v5 port). Both read only `cl_*` figures that are already in a pack: nothing is recomputed from
the transaction files, so a comparison costs a read of two small JSON files.

The prior pack is the previous month's `ti_pack.json` for the same client. Its window ends a month earlier, so
the two 12-month windows overlap by eleven months: a change here is what the newest month added and the oldest
dropped. Triggers fire on (defaults in `competition_layers.DEFAULTS`, overridable by `CompetitionLayers` in the
client config): an institution newly seen with `trigger_new_accounts` or more accounts, a tier's share of
accounts moving `trigger_share_points` points or more, and coverage under `coverage_floor` percent.
"""
from __future__ import annotations


def compare(cur: dict, prior: dict, cfg: dict, prior_label: str | None = None) -> dict:
    """{prior_period, tiers, institutions, triggers, coverage} from two packs' figures; {} when either has no layers."""
    if not (cur.get("cl_tiers") and prior.get("cl_tiers")):
        return {}
    pt = {r["tier"]: r for r in prior["cl_tiers"]}
    ct = {r["tier"]: r for r in cur["cl_tiers"]}
    tiers = []
    for t in list(ct) + [t for t in pt if t not in ct]:
        c, p = ct.get(t), pt.get(t)
        tiers.append({"tier": t, "accounts_now": c["accounts"] if c else 0, "accounts_prior": p["accounts"] if p else 0,
                      "pct_now": c["pct"] if c else 0.0, "pct_prior": p["pct"] if p else 0.0,
                      "change_points": round((c["pct"] if c else 0.0) - (p["pct"] if p else 0.0), 2),
                      "dollars_now": c["dollars"] if c else 0, "dollars_prior": p["dollars"] if p else 0})
    tiers.sort(key=lambda r: -abs(r["change_points"]))
    pi = {r["inst"]: r for r in prior.get("cl_institutions") or []}
    ci = {r["inst"]: r for r in cur.get("cl_institutions") or []}
    insts = []
    for n in list(ci) + [n for n in pi if n not in ci]:
        c, p = ci.get(n), pi.get(n)
        status = "new this month" if p is None else "not seen this month" if c is None else "continuing"
        insts.append({"inst": n, "tier": (c or p)["tier"], "accounts_now": c["accounts"] if c else 0, "accounts_prior": p["accounts"] if p else 0,
                      "change": (c["accounts"] if c else 0) - (p["accounts"] if p else 0), "status": status})
    insts.sort(key=lambda r: -abs(r["change"]))
    cov_now = (cur.get("cl_coverage") or {}).get("pct")
    cov_prior = (prior.get("cl_coverage") or {}).get("pct")
    triggers = []
    for r in insts:
        if r["status"] == "new this month" and r["accounts_now"] >= cfg["trigger_new_accounts"]:
            triggers.append({"trigger": "New institution over the threshold", "subject": r["inst"],
                             "detail": f"{r['accounts_now']:,} accounts (threshold {cfg['trigger_new_accounts']:g})"})
    for r in tiers:
        if abs(r["change_points"]) >= cfg["trigger_share_points"]:
            triggers.append({"trigger": "Tier share moved", "subject": r["tier"],
                             "detail": f"{r['change_points']:+.2f} points (threshold {cfg['trigger_share_points']:g})"})
    if cov_now is not None and cov_now < cfg["coverage_floor"]:
        triggers.append({"trigger": "Coverage below the floor", "subject": "coverage", "detail": f"{cov_now:.1f}% (floor {cfg['coverage_floor']:g}%)"})
    return {"prior_period": prior_label, "tiers": tiers, "institutions": insts, "triggers": triggers,
            "coverage": {"now": cov_now, "prior": cov_prior}}


def portfolio_row(figs: dict) -> dict:
    """The row one client-month adds to a portfolio benchmark: reach, dollars, institutions placed, coverage, the share
    of accounts paying each tier and each group. No client identifier: the writer of the ledger adds the client and period."""
    a, b = figs.get("cl_any"), figs.get("cl_base")
    if not a or not b:
        return {}
    row = {"accounts": b["accounts"], "any_pct": a["pct"], "any_dollars": a["dollars"],
           "institutions_placed": len(figs.get("cl_institutions") or []), "coverage_pct": (figs.get("cl_coverage") or {}).get("pct"),
           "client_type": (figs.get("cl_scope") or {}).get("client_type")}
    for r in figs.get("cl_tiers") or []:
        row["tier_pct_" + r["tier"].split(" (")[0].lower().replace(" ", "_")] = r["pct"]
    for g, v in (a.get("by_group") or {}).items():
        row["group_pct_" + g] = v["pct"]
    return row
