# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/competition.py at a491b5c (James Gilmore); logic unchanged.
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

from .financial_services import (_pct, _recency_tier, _token_regex, classify_strings,
                                 normalize_core)
from .lens import Lenses
from .financial_services import marketplace_purchase
from .merchant import merchant_core, merchant_text

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
TOP_INSTITUTIONS_PER_LENS = 5
# The competition family (legacy 14-35, 66-67; #258). Engagement is the
# share of an account's TRANSACTIONS at a competitor; wallet share is the
# share of its DOLLARS. Winback needs enough accounts to be a campaign.
ENGAGEMENT_TIERS = (("light", 0, 20), ("moderate", 20, 50), ("heavy", 50, 101))
MIN_WALLET_ACCOUNTS = 10
MIN_WINBACK_ACCOUNTS = 25
TOP_WINBACK = 12
TOP_ENGAGEMENT = 12
TOP_WALLET = 15
RECENCY_BANDS = (("Last 30 days", 0, 30), ("31-90 days", 31, 90),
                 ("91-180 days", 91, 180), ("180+ days", 181, 10**6))
BREADTH_BANDS = (("1", 1, 1), ("2-3", 2, 3), ("4-5", 4, 5), ("6+", 6, 10**6))  # who each group pays, not the whole field


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

_CU_TAILS = ("FEDERAL CREDIT UNION", "CREDIT UNION", "FCU", "CU", "FEDERAL")
_BANK_TAILS = ("BANK & TRUST", "BANK AND TRUST", "BANK & TRUST CO", "BANK, NATIONAL ASSOCIATION",
               "BANK NATIONAL ASSOCIATION", "NATIONAL BANK", "BANK", "BK")
_CU_FORMS = ("{r} CU", "{r} FCU", "{r} CREDIT UNION", "{r} FEDERAL CREDIT UNION", "{r} FEDERAL")
_BANK_FORMS = ("{r} BANK", "{r} BK")
_MIN_STEM = 4


def depository_variants(name: str) -> set[str]:
    """The spellings a card descriptor can carry for one configured name.

    14 of 1776's 24 locals shipped a single spelling, so SCHOOLSFIRST CU,
    FIRST TECH CU, PATELCO FCU and MONTECITO BK matched nothing (#261). The
    root is the name with its depository tail removed; the family is the
    root with every tail an acquirer prints. The bare root is never a
    pattern: "SESLOC" alone is fine, "FIRST" alone claims half the world.
    """
    base = " ".join(str(name).upper().replace(".", "").split())
    if base.startswith("THE "):
        base = base[4:]
    out = {base}
    for tails, forms in ((_CU_TAILS, _CU_FORMS), (_BANK_TAILS, _BANK_FORMS)):
        for tail in sorted(tails, key=len, reverse=True):
            if base.endswith(" " + tail):
                root = base[: -len(tail) - 1].strip(" ,")
                if root and (len(root) >= _MIN_STEM or " " in root):
                    out.update(f.format(r=root) for f in forms)
                break
    for spelling in list(out):
        if " AND " in spelling:
            out.add(spelling.replace(" AND ", " & "))
        elif " & " in spelling:
            out.add(spelling.replace(" & ", " AND "))
    return {s for s in out if s}


def _patterns(name: str, aliases) -> list[str]:
    pats: set[str] = set()
    for spelling in [str(name)] + [str(a) for a in (aliases or [])]:
        pats |= depository_variants(spelling)
    return sorted(p for p in pats if p)


def load_config(config_dir: Path, client_config: dict | None = None) -> dict:
    """competitors.json + the client's LocalCompetitors (a list of names or
    {name: [aliases]}), every local name its own institution in LOCAL_TIER,
    with the depository variant family generated for every spelling."""
    spec = json.loads((config_dir / "competitors.json").read_text(encoding="utf-8"))
    spec["institutions"] = {n: dict(i) for n, i in spec["institutions"].items()}
    local = (client_config or {}).get("LocalCompetitors") or {}
    if isinstance(local, list):
        local = {str(n): [str(n)] for n in local}
    for name, aliases in local.items():
        spec["institutions"][str(name)] = {"tier": LOCAL_TIER, "patterns": _patterns(name, aliases),
                                           "local": True}
    spec["local_names"] = [str(n) for n in local]
    regional = (client_config or {}).get("RegionalCompetitors") or {}
    if isinstance(regional, list):
        regional = {str(n): [str(n)] for n in regional}
    for name, aliases in regional.items():
        spec["institutions"][str(name)] = {"tier": REGIONAL_TIER,
                                           "patterns": _patterns(name, aliases)}
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
    # the prefilter searches the normalised core, as classify_strings does
    cand = pd.Index([s for s in distinct if s and any_rx.search(normalize_core(s))])
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
        text = fin_rows["text"] if "text" in fin_rows else merchant_text(df["merchant_name"])
        product = fin_rows["category"]
    else:
        text = merchant_text(df["merchant_name"])
        core = merchant_core(df["merchant_name"])
        is_card = df["transaction_type"].astype(str).str.upper().isin(["PIN", "SIG"]).to_numpy()
        product = pd.Series(None, index=df.index, dtype=object)
    is_transfer = ~is_card
    # A feed with no transfer rail at all (1776, 1100: card only) has to be
    # read on the card rail or not at all. The review queue and the
    # unmatched lists take the rail the file carries.
    rail_ok = is_transfer if is_transfer.any() else np.ones(len(df), dtype=bool)
    # nan_to_num: a blank amount is $0, never a NaN that poisons the
    # numpy sums (numpy does not skip NaN; round(nan) raises) -- 1585.
    amt = np.nan_to_num(df["amount"].abs().to_numpy())
    acct = df["primary_account_num"].astype(str)
    in_base = acct.isin(account_filter).to_numpy() if account_filter is not None \
        else np.ones(len(df), dtype=bool)

    # Matched on the full text: the institution is found wherever it sits,
    # and a one-word city after it no longer costs the name its last word
    # (#261). Ecosystems are kept on every rail and reported apart; only a
    # PayPal marketplace purchase is cleared, since that is merchant spend.
    table = _classify(pd.Index(text.unique()), spec)
    inst = text.map(table["category"])
    kind = text.map(table["kind"])
    purchase = (kind == "adjacency").to_numpy() & marketplace_purchase(text)
    inst = inst.where(~purchase)
    kind = kind.where(~purchase)
    tier_of = {n: i.get("tier", "") for n, i in spec["institutions"].items()}
    is_comp = (kind == "competitor").to_numpy()
    is_eco = (kind == "adjacency").to_numpy()

    total_accounts = int(acct[in_base].nunique())
    transfer_dollars = float(amt[is_transfer & in_base].sum())
    out[K + "accounts_total"] = total_accounts
    out[K + "institutions_configured"] = len(spec["institutions"])
    out[K + "matched_rows"] = int((is_comp & in_base).sum())
    out[K + "competitor_dollars"] = round(float(amt[is_comp & in_base].sum()))
    out[K + "competitor_pct_of_transfer_dollars"] = (
        _pct(float(amt[is_comp & is_transfer & in_base].sum()), transfer_dollars)
        if transfer_dollars else None)      # no transfer rail -> no share (#245)
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

    # ---- 3b. share of wallet per account (legacy txn_analysis M6, #245) ---------
    # Competitor dollars over the account's own transaction dollars: Heavy
    # over half, Balanced a quarter to a half, CU-focused under a quarter.
    acct_total = pd.Series(amt[in_base]).groupby(acct[in_base].to_numpy()).sum()
    comp_by_acct = comp.groupby("acct")["dollars"].sum()
    share = (comp_by_acct / acct_total.reindex(comp_by_acct.index)).replace(
        [np.inf, -np.inf], np.nan).fillna(0).clip(upper=1.0) * 100
    wallet_rows = []
    for label, mask in (("Heavy (over 50%)", share > 50),
                        ("Balanced (25-50%)", (share > 25) & (share <= 50)),
                        ("CU-focused (under 25%)", share <= 25)):
        ids = share.index[mask]
        wallet_rows.append([label, int(len(ids)), _pct(int(len(ids)), int(len(share))),
                            round(float(comp_by_acct.reindex(ids).sum())),
                            round(float(share[mask].mean()), 1) if len(ids) else 0.0])
    out[K + "wallet_tiers"] = wallet_rows
    out[K + "wallet_tiers_columns"] = ["tier", "accounts", "pct_of_with_competitor",
                                       "competitor_dollars", "mean_share_pct"]

    # ---- 3c. threat score (legacy M6B-6, #245): 40% penetration, 30% spend,
    # 30% growth, each as a percentile rank across the institutions seen.
    # Growth is the last three months against the three before, in dollars.
    recent_from = anchor_end - pd.DateOffset(months=3)
    prior_from = anchor_end - pd.DateOffset(months=6)
    mc = m[m["kind"] == "competitor"]
    by_recent = mc[mc["date"] > recent_from].groupby("institution", observed=True)["amount"].sum()
    by_prior = mc[(mc["date"] > prior_from) & (mc["date"] <= recent_from)] \
        .groupby("institution", observed=True)["amount"].sum()
    if rows:
        frame = pd.DataFrame({"institution": [r[0] for r in rows],
                              "accounts": [r[2] for r in rows],
                              "dollars": [r[5] for r in rows]})
        rec = frame["institution"].map(by_recent).fillna(0.0)
        pri = frame["institution"].map(by_prior).fillna(0.0)
        frame["growth_pct"] = np.where(pri > 0, (rec - pri) / pri * 100, np.where(rec > 0, 100.0, 0.0))
        pr = lambda s: s.rank(pct=True) * 100  # noqa: E731
        frame["score"] = (0.4 * pr(frame["accounts"]) + 0.3 * pr(frame["dollars"])
                          + 0.3 * pr(frame["growth_pct"].clip(lower=0)))
        frame = frame.sort_values("score", ascending=False).head(10)
        out[K + "threat"] = [[r.institution, round(float(r.score), 1), int(r.accounts),
                              int(r.dollars), round(float(r.growth_pct), 1)]
                             for r in frame.itertuples()]
        out[K + "threat_columns"] = ["institution", "score", "accounts", "dollars", "growth_pct"]
        out[K + "threat_basis"] = ("40% penetration, 30% dollars, 30% growth (last 3 months vs "
                                   "the 3 before), each a percentile rank across institutions seen")

    # ---- 4. ecosystems, apart ---------------------------------------------------------
    eco_rows = []
    for name, grp in eco.groupby("institution", observed=True):
        n = int(grp["acct"].nunique())
        eco_rows.append([name, n, _pct(n, total_accounts), round(float(grp["dollars"].sum()))])
    out[K + "ecosystems"] = sorted(eco_rows, key=lambda r: -r[1])
    out[K + "ecosystem_accounts"] = int(eco["acct"].nunique())
    out[K + "ecosystem_dollars"] = round(float(eco["dollars"].sum()))

    # ---- 4b. the competition family (legacy 14-35, 66-67; #258) -----------------------
    window_months = max(int(df["transaction_date"].dt.to_period("M").nunique()), 1)
    _family(out, K, comp, eco, m, acct[in_base], amt[in_base], acct_total, total_accounts,
            by_recent, by_prior, recent_from, prior_from, anchor_end, spec, window_months)

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
        cand = [s for s in unmatched if s and rx.search(normalize_core(s))
                and not (irx and irx.search(normalize_core(s)))]
        if cand:
            mask = core.isin(cand) & pd.Series(rail_ok & in_base, index=core.index)
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
    # Named competitors only: m also holds the payment-app rows (Venmo, Cash
    # App ...), which are not competitors and must not lift the curve.
    mc_rows = m[m["kind"] == "competitor"]
    monthly = mc_rows.assign(
        date=pd.to_datetime(mc_rows["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
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
    # the still-spending decliners who pay a competitor, ranked by balance:
    # the legacy at-risk export (#245), on the group a win-back can reach
    if "declining" in lenses.masks:
        dec = summary[summary.index.isin(lenses.ids("declining"))]
        by = "Curr Bal" if "Curr Bal" in dec.columns else "dollars"
        path = lists_dir / "competition_declining.csv"
        dec.sort_values(by, ascending=False).rename_axis("acct").to_csv(path)
        written["declining"] = str(path)
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


# ---------------------------------------------------------------------------
# the competition family (legacy 14-35, 66-67; #258)
# ---------------------------------------------------------------------------

def _band(value, bands):
    for label, lo, hi in bands:
        if lo <= value <= hi:
            return label
    return bands[-1][0]


def _family(out: dict, K: str, comp: pd.DataFrame, eco: pd.DataFrame, m: pd.DataFrame,
            acct_in_base: pd.Series, amt_in_base, acct_total: pd.Series, total_accounts: int,
            by_recent: pd.Series, by_prior: pd.Series, recent_from, prior_from, anchor_end,
            spec: dict, months: int = 1) -> None:
    """Legacy 14-35 and 66-67 as metrics. Engagement depth is the share of an
    account's transactions at a competitor; wallet share per institution is
    the share of its dollars; recency and breadth read the account-competitor
    pairs; winback names the competitors whose volume fell; depth against
    growth feeds one quadrant; BNPL reads the flagged ecosystems. Ecosystems
    stay apart from competitors throughout."""
    acct_txns = pd.Series(acct_in_base.to_numpy()).value_counts()
    c = comp.copy()
    c["txn_share"] = (c["txns"] / c["acct"].map(acct_txns).replace(0, np.nan) * 100) \
        .fillna(0).clip(upper=100)
    c["dollar_share"] = (c["dollars"] / c["acct"].map(acct_total).replace(0, np.nan) * 100) \
        .replace([np.inf, -np.inf], np.nan).fillna(0).clip(upper=100)

    # 17 -- engagement depth: who owns the relationship
    eng = []
    for name, grp in c.groupby("institution", observed=True):
        s = grp["txn_share"]
        eng.append([name, int(grp["acct"].nunique()),
                    int((s < 20).sum()), int(((s >= 20) & (s < 50)).sum()), int((s >= 50).sum()),
                    round(float(s.mean()), 1)])
    eng.sort(key=lambda r: (-r[1], r[0]))
    out[K + "engagement"] = eng[:TOP_ENGAGEMENT]
    out[K + "engagement_columns"] = ["institution", "accounts", "light", "moderate", "heavy",
                                     "avg_share_pct"]
    out[K + "engagement_heavy_n"] = int(c.loc[c["txn_share"] >= 50, "acct"].nunique())
    out[K + "engagement_avg_share_pct"] = round(float(c["txn_share"].mean()), 1) if len(c) else 0.0

    # 20-22 -- wallet share per institution: how much of the wallet has left
    wal = []
    for name, grp in c.groupby("institution", observed=True):
        n = int(grp["acct"].nunique())
        if n < MIN_WALLET_ACCOUNTS:
            continue
        s = grp["dollar_share"]
        heavy = int((s > 50).sum())
        wal.append([name, n, int((s <= 25).sum()), int(((s > 25) & (s <= 50)).sum()), heavy,
                    _pct(heavy, n)])
    wal.sort(key=lambda r: (-r[1], r[0]))
    out[K + "wallet_by_institution"] = wal[:TOP_WALLET]
    out[K + "wallet_by_institution_columns"] = ["institution", "accounts", "cu_focused",
                                                "balanced", "heavy", "heavy_pct"]
    out[K + "wallet_min_accounts"] = MIN_WALLET_ACCOUNTS
    out[K + "wallet_high_exposure_n"] = int(sum(1 for r in wal if r[5] > 20))

    # 27 -- recency of every account-competitor pair: is the money still moving
    pairs = int(len(c))
    labels = (c["recency_days"].map(lambda d: _band(int(d), RECENCY_BANDS)) if pairs
              else pd.Series(dtype=str))
    counts = labels.value_counts()
    out[K + "recency_bands"] = [[label, int(counts.get(label, 0)),
                                 _pct(int(counts.get(label, 0)), pairs)]
                                for label, _, _ in RECENCY_BANDS]
    out[K + "recency_pairs"] = pairs
    out[K + "recency_active_pct"] = _pct(int(counts.get(RECENCY_BANDS[0][0], 0)), pairs)
    out[K + "recency_dormant_pairs"] = int(counts.get(RECENCY_BANDS[-1][0], 0))

    # 35 -- breadth: how many competitors each account uses, and who uses none
    per_acct = c.groupby("acct")["institution"].nunique() if pairs else pd.Series(dtype=int)
    active = int(len(per_acct))
    bl = per_acct.map(lambda n: _band(int(n), BREADTH_BANDS)).value_counts()
    out[K + "breadth_bands"] = [[label, int(bl.get(label, 0)), _pct(int(bl.get(label, 0)), active),
                                 _pct(int(bl.get(label, 0)), total_accounts)]
                                for label, _, _ in BREADTH_BANDS]
    out[K + "breadth_bands_columns"] = ["band", "accounts", "pct_of_active", "pct_of_book"]
    out[K + "breadth_no_competitor"] = max(total_accounts - active, 0)
    out[K + "breadth_no_competitor_pct"] = _pct(max(total_accounts - active, 0), total_accounts)
    out[K + "breadth_shopping"] = int((per_acct >= 2).sum())
    out[K + "breadth_deep"] = int((per_acct >= 6).sum())

    # 16 -- winback: competitors whose volume fell, last three months against the three before
    mc = m[m["kind"] == "competitor"]
    rec_n = mc[mc["date"] > recent_from].groupby("institution", observed=True).size()
    pri_n = mc[(mc["date"] > prior_from) & (mc["date"] <= recent_from)] \
        .groupby("institution", observed=True).size()
    accounts_by = c.groupby("institution", observed=True)["acct"].nunique()
    cand = []
    for name in accounts_by.index:
        r, p, n = int(rec_n.get(name, 0)), int(pri_n.get(name, 0)), int(accounts_by[name])
        if p > 0 and r > 0 and r < p and n >= MIN_WINBACK_ACCOUNTS:
            cand.append([name, n, r, p, round((r - p) / p * 100, 1)])
    if cand:
        max_pen = max(r[1] for r in cand) or 1
        max_fall = max(abs(r[4]) for r in cand) or 1
        for r in cand:
            r.append(round(r[1] / max_pen * 50 + abs(r[4]) / max_fall * 50, 1))
        cand.sort(key=lambda r: -r[5])
    out[K + "winback"] = cand[:TOP_WINBACK]
    out[K + "winback_columns"] = ["institution", "accounts", "recent_txns", "prior_txns",
                                  "txn_growth_pct", "score"]
    chosen = {r[0] for r in cand[:TOP_WINBACK]}
    out[K + "winback_accounts"] = int(c.loc[c["institution"].isin(chosen), "acct"].nunique())
    day = pd.Timedelta(days=1)
    out[K + "winback_window"] = (f"{(recent_from + day):%b%y} - {anchor_end:%b%y} against "
                                 f"{(prior_from + day):%b%y} - {recent_from:%b%y}")
    out[K + "winback_min_accounts"] = MIN_WINBACK_ACCOUNTS

    # 14 -- depth against growth: transactions per account, dollars now against then
    dg = []
    for name, grp in c.groupby("institution", observed=True):
        n = int(grp["acct"].nunique())
        rec, pri = float(by_recent.get(name, 0.0)), float(by_prior.get(name, 0.0))
        growth = (rec - pri) / pri * 100 if pri > 0 else (100.0 if rec > 0 else 0.0)
        dg.append([name, n, round(float(grp["txns"].sum()) / n, 1) if n else 0.0, round(growth, 1)])
    dg.sort(key=lambda r: (-r[1], r[0]))
    out[K + "depth_growth"] = dg[:10]
    out[K + "depth_growth_columns"] = ["institution", "accounts", "txns_per_acct", "growth_pct"]

    # 66-67 -- buy now, pay later: the flagged ecosystems, apart from the rest
    bnpl_names = {n for n, i in spec.get("institutions", {}).items() if i.get("bnpl")}
    eb = eco[eco["institution"].isin(bnpl_names)]
    n_b = int(eb["acct"].nunique())
    d_b = round(float(eb["dollars"].sum()))
    providers = []
    for name, grp in eb.groupby("institution", observed=True):
        n = int(grp["acct"].nunique())
        d = round(float(grp["dollars"].sum()))
        providers.append([name, n, _pct(n, total_accounts), d,
                          round(d / n / months, 2) if n else 0.0])
    providers.sort(key=lambda r: (-r[1], r[0]))
    out[K + "bnpl"] = {"accounts": n_b, "pct": _pct(n_b, total_accounts), "dollars": d_b,
                       "months": months,
                       "per_acct_month": round(d_b / n_b / months, 2) if n_b else 0.0,
                       "providers": providers,
                       "providers_columns": ["institution", "accounts", "pct_of_accounts",
                                             "dollars", "per_acct_month"]}
