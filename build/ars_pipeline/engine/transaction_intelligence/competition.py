"""Competition: which named institutions hold relationships with our members.

financial_services answers "what products leave, to which provider in each
category". This section turns the same rows around: per INSTITUTION across
every product -- who Chase, Capital One or the local bank has, how many of
our members are multi-banked, how deep each relationship is, where it is
growing, and how that differs for responders, at-risk and new accounts.

Detection is name-based against 0_Config/competitors.json (universal
institutions in tiers) plus the CSM's LocalCompetitors from clients_config.
Matching runs on the cleaned merchant core over the DISTINCT strings, once.
Product mix comes from the financial_services classification of the same
rows (passed in), so the two sections never disagree about a counterparty.

Kinds (from the tier):
    competitor  counted in penetration and dollars, on both rails
    adjacency   payment ecosystems (Venmo, Zelle, PayPal transfers, BNPL);
                reported apart, counted only on ACH / check -- a PayPal card
                purchase stays merchant spend
"""

from __future__ import annotations

from .txn_common import ranked

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .financial_services import _pct, _recency_tier, _token_regex, classify_strings
from .lens import Lenses
from .merchant import merchant_core

LOCAL_TIER = "Local Bank / CU"
REGIONAL_TIER = "Regional Bank"
OTHER_PRODUCT = "Transfer / other"
# The finserv dictionary names this bucket for its own context; here the lender IS known.
PRODUCT_RELABEL = {"Other Loans (lender unknown)": "Loan (type unspecified)"}
TOP_INSTITUTIONS = 25
TOP_PRODUCTS = 3
REVIEW_QUEUE = 25
MIN_MONTHS_FOR_STOPPED = 3
MULTI_BANKED_AT = 2
MIN_ACCOUNTS_FOR_BRANCH = 50   # a branch row swings too hard below this
TOP_INSTITUTIONS_PER_LENS = 5  # who each group pays, not the whole field


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def load_config(config_dir: Path, client_config: dict | None = None) -> dict:
    """competitors.json + the client's LocalCompetitors (a list of names or
    {name: [aliases]}), every local name its own institution in LOCAL_TIER."""
    spec = json.loads((config_dir / "competitors.json").read_text(encoding="utf-8"))
    spec["institutions"] = {n: dict(i) for n, i in spec["institutions"].items()}
    local = (client_config or {}).get("LocalCompetitors") or {}
    if isinstance(local, list):
        local = {str(n): [str(n)] for n in local}
    for name, aliases in local.items():
        pats = {str(a).upper().strip() for a in (aliases or [])} | {str(name).upper().strip()}
        spec["institutions"][str(name)] = {"tier": LOCAL_TIER, "patterns": sorted(p for p in pats if p),
                                           "local": True}
    spec["local_names"] = [str(n) for n in local]
    regional = (client_config or {}).get("RegionalCompetitors") or {}
    if isinstance(regional, list):
        regional = {str(n): [str(n)] for n in regional}
    for name, aliases in regional.items():
        pats = {str(a).upper().strip() for a in (aliases or [])} | {str(name).upper().strip()}
        spec["institutions"][str(name)] = {"tier": REGIONAL_TIER,
                                           "patterns": sorted(p for p in pats if p)}
    spec["regional_names"] = [str(n) for n in regional]
    fin = config_dir / "financial_services_patterns.json"
    if fin.exists():
        extra = json.loads(fin.read_text(encoding="utf-8")).get("false_positives", [])
        spec["false_positives"] = sorted(set(spec.get("false_positives", [])) | set(extra))
    # The client's own names are not competitors; internal transfers are
    # excluded from matching and from the review queue.
    self_names = [str(n).upper().strip() for n in (client_config or {}).get("SelfNames") or []]
    if self_names:
        spec["false_positives"] = sorted(set(spec["false_positives"]) | set(self_names))
        spec["review_ignore"] = self_names
    return spec


def _as_category_spec(spec: dict) -> dict:
    """financial_services.classify_strings shape: one 'category' per institution."""
    tiers = spec.get("tiers", {})
    cats = {}
    for name, inst in spec["institutions"].items():
        kind = tiers.get(inst.get("tier"), {}).get("kind", "competitor")
        cats[name] = {"kind": kind, "patterns": inst.get("patterns", [])}
    return {"categories": cats, "false_positives": spec.get("false_positives", [])}


def _classify(distinct: pd.Index, spec: dict) -> pd.DataFrame:
    """~100 institutions x ~130k distinct cores: one combined regex picks the
    candidates, the per-institution longest-match pass runs on those only."""
    cspec = _as_category_spec(spec)
    any_rx = _token_regex([p for c in cspec["categories"].values() for p in c["patterns"]])
    cand = pd.Index([s for s in distinct if s and any_rx.search(s)])
    return classify_strings(cand, cspec).reindex(distinct)


# ---------------------------------------------------------------------------
# compute
# ---------------------------------------------------------------------------

def compute(df: pd.DataFrame, lenses: Lenses | None, spec: dict, fin_rows: pd.DataFrame | None,
            anchor_end: pd.Timestamp, lists_dir: Path | None, warn,
            account_filter: pd.Index | None = None, key_prefix: str = "comp_",
            base_label: str = "all accounts") -> tuple[dict, dict]:
    """Returns (metrics, outputs). outputs holds CSV paths. fin_rows is
    financial_services.classify_rows() for the same frame (product mix)."""
    out: dict = {}
    outputs: dict = {}
    if df.empty:
        return out, outputs
    K = key_prefix
    out[K + "base_label"] = base_label

    # A client with no LocalCompetitors still gets a full competition chapter
    # off the national and district layers, so an unconfigured local layer
    # reads as a quiet market rather than a missing input. Three clients are
    # in that state today (1214, 1763, 1795) and the bank across the street
    # is invisible for all of them.
    if not spec.get("local_names"):
        warn("competition: no LocalCompetitors configured -- only national "
             "and regional institutions can be named, so a nearby bank or "
             "credit union will not appear at any dollar value")

    if fin_rows is not None:
        core, is_card = fin_rows["core"], fin_rows["is_card"].to_numpy()
        product = fin_rows["category"]
    else:
        core = merchant_core(df["merchant_name"])
        is_card = df["transaction_type"].astype(str).str.upper().isin(["PIN", "SIG"]).to_numpy()
        product = pd.Series(None, index=df.index, dtype=object)
    is_transfer = ~is_card
    # nan_to_num: a blank amount is $0, never a NaN that poisons the
    # numpy sums (numpy does not skip NaN; round(nan) raises) -- 1585.
    amt = np.nan_to_num(df["amount"].abs().to_numpy())
    acct = df["primary_account_num"].astype(str)
    in_base = acct.isin(account_filter).to_numpy() if account_filter is not None \
        else np.ones(len(df), dtype=bool)

    table = _classify(pd.Index(core.unique()), spec)
    inst = core.map(table["category"])
    kind = core.map(table["kind"])
    adjacency_on_card = (kind == "adjacency").to_numpy() & is_card
    inst = inst.where(~adjacency_on_card)
    kind = kind.where(~adjacency_on_card)
    tier_of = {n: i.get("tier", "") for n, i in spec["institutions"].items()}
    is_comp = (kind == "competitor").to_numpy()
    is_eco = (kind == "adjacency").to_numpy()

    total_accounts = int(acct[in_base].nunique())
    transfer_dollars = float(amt[is_transfer & in_base].sum())
    out[K + "accounts_total"] = total_accounts
    out[K + "institutions_configured"] = len(spec["institutions"])
    out[K + "matched_rows"] = int((is_comp & in_base).sum())
    out[K + "competitor_dollars"] = round(float(amt[is_comp & in_base].sum()))
    out[K + "competitor_pct_of_transfer_dollars"] = _pct(float(amt[is_comp & is_transfer & in_base].sum()),
                                                         transfer_dollars)
    if not is_comp.any() and not is_eco.any():
        warn("competition: no transaction matched an institution")
        return out, outputs

    # ---- per account x institution (competitors) --------------------------
    hit = is_comp | is_eco
    m = pd.DataFrame({"acct": acct.to_numpy()[hit], "institution": inst.to_numpy()[hit],
                      "kind": kind.to_numpy()[hit], "amount": amt[hit],
                      "date": df["transaction_date"].to_numpy()[hit],
                      "product": product.to_numpy()[hit]})
    m["product"] = m["product"].fillna(OTHER_PRODUCT).replace(PRODUCT_RELABEL)
    m["tier"] = m["institution"].map(tier_of)
    g = m.groupby(["acct", "institution"], observed=True)
    ac = g.agg(kind=("kind", "first"), tier=("tier", "first"), txns=("amount", "size"),
               dollars=("amount", "sum"), first=("date", "min"), last=("date", "max"),
               months=("date", lambda s: s.dt.to_period("M").nunique())).reset_index()
    ac["recency_days"] = (anchor_end - ac["last"]).dt.days
    ac["recency"] = _recency_tier(ac["recency_days"], spec)
    ac["is_new"] = (anchor_end - ac["first"]).dt.days <= spec.get("new_days", 90)
    ac["is_stopped"] = (ac["recency_days"] > spec.get("stopped_after_days", 90)) & \
                       (ac["months"] >= MIN_MONTHS_FOR_STOPPED)
    ac_all = ac
    if account_filter is not None:
        ac = ac[ac["acct"].isin(account_filter)]
        m = m[m["acct"].isin(account_filter)]
    comp = ac[ac["kind"] == "competitor"]
    eco = ac[ac["kind"] == "adjacency"]

    # ---- 1. institutions and tiers ----------------------------------------------
    prod_by_inst = {}
    for name, grp in m[m["kind"] == "competitor"].groupby("institution", observed=True):
        pg = grp.groupby("product", observed=True)["acct"].nunique().sort_values(ascending=False)
        prod_by_inst[name] = [str(p) for p in pg.head(TOP_PRODUCTS).index]
    rows = []
    for name, grp in comp.groupby("institution", observed=True):
        n = int(grp["acct"].nunique())
        dollars = float(grp["dollars"].sum())
        rows.append([name, tier_of.get(name, ""), n, _pct(n, total_accounts), int(grp["txns"].sum()),
                     round(dollars), round(dollars / n) if n else 0, prod_by_inst.get(name, []),
                     int(grp["is_new"].sum()), int(grp["is_stopped"].sum())])
    rows.sort(key=lambda r: (-r[2], -r[5]))
    out[K + "institutions"] = rows[:TOP_INSTITUTIONS]
    out[K + "institutions_columns"] = ["institution", "tier", "accounts", "pct_of_accounts", "txns",
                                       "dollars", "dollars_per_acct", "products", "new_90d", "stopped"]
    out[K + "institutions_n"] = len(rows)
    tiers = []
    for tier, grp in comp.groupby("tier", observed=True):
        n = int(grp["acct"].nunique())
        tiers.append([tier, int(grp["institution"].nunique()), n, _pct(n, total_accounts),
                      round(float(grp["dollars"].sum()))])
    out[K + "by_tier"] = sorted(tiers, key=lambda r: -r[2])
    out[K + "by_tier_columns"] = ["tier", "institutions", "accounts", "pct_of_accounts", "dollars"]

    # ---- 2. penetration and multi-banked -----------------------------------------
    per_acct = comp.groupby("acct")["institution"].nunique()
    comp_ids = pd.Index(per_acct.index)
    out[K + "with_competitor"] = len(comp_ids)
    out[K + "with_competitor_pct"] = _pct(len(comp_ids), total_accounts)
    dist = per_acct.value_counts()
    out[K + "competitors_per_account"] = [[0, total_accounts - len(comp_ids)], [1, int(dist.get(1, 0))],
                                          [2, int(dist.get(2, 0))], [3, int(dist[dist.index >= 3].sum())]]
    out[K + "competitors_per_account_note"] = "last row is 3 or more"
    multi = per_acct[per_acct >= MULTI_BANKED_AT]
    out[K + "multi_banked"] = len(multi)
    # Conditional on having a competitor at all, unlike with_competitor_pct
    # just above, which is over the whole base. The two sit side by side on
    # the slide, so the base is published rather than left to be inferred.
    out[K + "multi_banked_pct"] = _pct(len(multi), len(comp_ids))
    out[K + "multi_banked_base"] = "accounts with at least one competitor"
    out[K + "with_competitor_base"] = base_label
    out[K + "mean_competitors_per_account"] = round(float(per_acct.mean()), 2) if len(per_acct) else 0.0

    # ---- 3. momentum: new vs stopped relationships per institution --------------
    mom = []
    for name, grp in comp.groupby("institution", observed=True):
        new, stopped = int(grp["is_new"].sum()), int(grp["is_stopped"].sum())
        if new or stopped:
            mom.append([name, new, stopped, new - stopped])
    out[K + "momentum"] = sorted(mom, key=lambda r: -r[3])
    out[K + "momentum_columns"] = ["institution", "new_90d", "stopped", "net"]

    # ---- 4. ecosystems, apart ---------------------------------------------------------
    eco_rows = []
    for name, grp in eco.groupby("institution", observed=True):
        n = int(grp["acct"].nunique())
        eco_rows.append([name, n, _pct(n, total_accounts), round(float(grp["dollars"].sum()))])
    out[K + "ecosystems"] = sorted(eco_rows, key=lambda r: -r[1])
    out[K + "ecosystem_accounts"] = int(eco["acct"].nunique())
    out[K + "ecosystem_dollars"] = round(float(eco["dollars"].sum()))

    # ---- 5. by lens; at-risk and new accounts x competitor -----------------------------
    txn_accounts = pd.Index(acct.unique())
    comp_all = ac_all[ac_all["kind"] == "competitor"]
    per_acct_all = comp_all.groupby("acct")["institution"].nunique()
    comp_ids_all = pd.Index(per_acct_all.index)
    if lenses is not None:
        by_lens = []
        per_lens_inst = []
        for ln in lenses.names():
            ids = lenses.ids(ln).intersection(txn_accounts)
            if not len(ids):
                continue
            with_ = comp_ids_all.intersection(ids)
            sub = comp_all[comp_all["acct"].isin(with_)]
            top = ranked(sub.groupby("institution")["acct"].nunique())
            by_lens.append([ln, lenses.label(ln), len(ids), len(with_), _pct(len(with_), len(ids)),
                            _pct(int((per_acct_all.loc[with_] >= MULTI_BANKED_AT).sum()), len(with_)),
                            round(float(sub["dollars"].sum()) / len(with_)) if len(with_) else 0,
                            str(top.index[0]) if len(top) else None])
            # WHICH institutions, not just the leader. The ranking is already
            # computed here and everything past position one was discarded, so
            # "who does ICS lose to, against the book" could not be asked --
            # only "how much". Referral and direct mail already differ on
            # every other measure; there is no reason to assume they lose to
            # the same names.
            if len(top):
                dollars_by_inst = sub.groupby("institution")["dollars"].sum()
                per_lens_inst.append([ln, lenses.label(ln)] + [
                    [str(inst), int(n_acct), _pct(int(n_acct), len(ids)),
                     round(float(dollars_by_inst.get(inst, 0.0)))]
                    for inst, n_acct in top.head(TOP_INSTITUTIONS_PER_LENS).items()])
        out[K + "by_lens"] = by_lens
        if per_lens_inst:
            out[K + "institutions_by_lens"] = per_lens_inst
            out[K + "institutions_by_lens_columns"] = [
                "lens", "label", "then up to "
                f"{TOP_INSTITUTIONS_PER_LENS} [institution, accounts, pct_of_lens, dollars]"]
            out[K + "institutions_by_lens_basis"] = (
                "the institutions each group actually pays, ranked by accounts "
                "reached; pct is of the whole group, not of its leakers")
        out[K + "by_lens_columns"] = ["lens", "label", "accounts", "with_competitor", "pct",
                                      "multi_banked_pct", "dollars_per_acct", "top_institution"]
        resp = next((r for r in by_lens if r[0] == "responders"), None)
        ctrl = next((r for r in by_lens if r[0] == "mailed_nonresp"), None)
        if resp and ctrl:
            out[K + "responder_gap_pp"] = round(resp[4] - ctrl[4], 1)
        for special, key in (("recently_inactive", K + "at_risk"), ("new_accounts", K + "new_accounts")):
            if special in lenses.masks:
                ids = lenses.ids(special).intersection(txn_accounts)
                with_ = comp_ids_all.intersection(ids)
                out[key] = {"accounts": len(ids), "with_competitor": len(with_), "pct": _pct(len(with_), len(ids))}
    else:
        warn("competition: no lenses; by-lens, at-risk and lists skipped")

    # ---- 5b. by branch ---------------------------------------------------------------------
    # Branch is the axis attrition already reports on (attrition_by_branch).
    # Nothing here ever cut by it, so the obvious question -- does the branch
    # we lose accounts at also leak money, and to whom -- could not be asked:
    # both halves were computed and never shared an axis.
    #
    # Leakage per account is taken over EVERY account at the branch, not just
    # those with a competitor, so branches are comparable to each other. The
    # by-lens block above divides by the competitor-carrying subset, which
    # answers a different question and is labelled differently.
    if lenses is not None:
        groups = lenses.family("branch")
        brows, skipped_n = [], 0
        for value, ids_all in groups.items():
            ids = ids_all.intersection(txn_accounts)
            if len(ids) < MIN_ACCOUNTS_FOR_BRANCH:
                skipped_n += len(ids)
                continue
            with_ = comp_ids_all.intersection(ids)
            sub = comp_all[comp_all["acct"].isin(with_)]
            top = sub.groupby("institution")["acct"].nunique().sort_values(ascending=False)
            dollars = float(sub["dollars"].sum())
            brows.append([str(value), len(ids), len(with_), _pct(len(with_), len(ids)),
                          round(dollars), round(dollars / len(ids)),
                          str(top.index[0]) if len(top) else None])
        brows.sort(key=lambda r: -(r[3] or 0))
        if brows:
            out[K + "by_branch"] = brows
            out[K + "by_branch_columns"] = ["branch", "accounts", "with_competitor",
                                            "pct", "dollars", "dollars_per_account",
                                            "top_institution"]
            out[K + "by_branch_basis"] = (
                "transacting accounts per branch; dollars per account is over "
                "every account at the branch, so branches compare like for like")
            if skipped_n:
                warn(f"competition by branch: {skipped_n:,} transacting "
                     f"account(s) sit at branches under "
                     f"{MIN_ACCOUNTS_FOR_BRANCH} and are in no branch row")
            worst = brows[0]
            out[K + "branch_worst"] = [worst[0], worst[3], worst[6]]
        elif groups:
            warn(f"competition by branch SUPPRESSED: no branch carries "
                 f"{MIN_ACCOUNTS_FOR_BRANCH} transacting accounts")
        else:
            warn("competition by branch unavailable: the ODD carries no Branch")

    # ---- 6. local competitors, review queue, lists ----------------------------------------
    local_names = spec.get("local_names", [])
    loc = comp[comp["tier"] == LOCAL_TIER]
    out[K + "local"] = {"configured": local_names, "accounts": int(loc["acct"].nunique()),
                        "pct": _pct(int(loc["acct"].nunique()), total_accounts),
                        "dollars": round(float(loc["dollars"].sum())),
                        "institutions": [[n, int(g_["acct"].nunique()), round(float(g_["dollars"].sum())),
                                          prod_by_inst.get(n, [])]
                                         for n, g_ in loc.groupby("institution", observed=True)]}
    tokens = spec.get("review_tokens", [])
    if tokens:
        rx = _token_regex(tokens)
        ignore = spec.get("review_ignore") or []
        irx = _token_regex(ignore) if ignore else None
        unmatched = pd.Index(core[inst.isna()].unique())
        cand = [s for s in unmatched if s and rx.search(s)
                and not (irx and irx.search(s))]
        if cand:
            mask = core.isin(cand) & pd.Series(is_transfer & in_base, index=core.index)
            q = pd.DataFrame({"core": core[mask], "amount": amt[mask.to_numpy()]}).groupby("core").agg(
                txns=("amount", "size"), dollars=("amount", "sum")).sort_values("dollars", ascending=False)
            out[K + "review_queue"] = [[s, int(r.txns), round(float(r.dollars))] for s, r in q.head(REVIEW_QUEUE).iterrows()]
            out[K + "review_queue_dollars"] = round(float(q["dollars"].sum()))

    if lists_dir is not None and lenses is not None and len(comp):
        outputs["competition_lists"] = _write_lists(comp, per_acct, lenses, lists_dir)
    # Private (popped before metrics.json): the whole-book per-account
    # competitor rows, for the deposit-flight overlay -- one derivation.
    out["_competitor_accounts"] = comp_all[["acct", "institution", "dollars"]]         .values.tolist()
    # Private, popped before metrics.json: competitor dollars per account per
    # MONTH, for the pre-closure leakage curve. Exported from this module's own
    # classification rather than re-derived downstream -- leakage.py must never
    # hold a second opinion about what counts as a competitor.
    monthly = m.assign(
        date=pd.to_datetime(m["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    ).groupby(["acct", "date"], observed=True, as_index=False)["amount"].sum()
    out["_competitor_monthly"] = monthly.rename(
        columns={"amount": "dollars"})[["acct", "date", "dollars"]]
    return out, outputs


def _write_lists(comp: pd.DataFrame, per_acct: pd.Series, lenses: Lenses, lists_dir: Path) -> dict:
    lists_dir.mkdir(parents=True, exist_ok=True)
    attrs = lenses.attrs
    summary = comp.groupby("acct").agg(
        institutions=("institution", lambda s: "; ".join(sorted(set(s)))),
        n_institutions=("institution", "nunique"), dollars=("dollars", "sum"),
        last=("last", "max")).join(attrs, how="left").sort_values("dollars", ascending=False)
    written = {}
    at_risk_ids = lenses.ids("recently_inactive") if "recently_inactive" in lenses.masks else pd.Index([])
    path = lists_dir / "competition_at_risk.csv"
    summary[summary.index.isin(at_risk_ids)].rename_axis("acct").to_csv(path)
    written["at_risk"] = str(path)
    path = lists_dir / "competition_multi_banked.csv"
    summary[summary["n_institutions"] >= MULTI_BANKED_AT].rename_axis("acct").to_csv(path)
    written["multi_banked"] = str(path)
    loc = comp[comp["tier"] == LOCAL_TIER]
    if len(loc):
        path = lists_dir / "competition_local.csv"
        cols = ["acct", "institution", "txns", "dollars", "first", "last", "recency", "months"]
        loc[cols].join(attrs, on="acct", how="left").sort_values(["institution", "dollars"],
                                                                ascending=[True, False]).to_csv(path, index=False)
        written["local"] = str(path)
    return written
