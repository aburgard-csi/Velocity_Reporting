"""
competition_layers.py — which banks and credit unions members and customers pay, by layer and by group.

New to RPE (not a v5 port): the layers section of the Competition chapter. It adds `cl_*` figures and
changes no existing `comp_*` figure; both stay in the pack and the overlap is a row in
docs/migration/DUPLICATES.md.

Scope. Depository institutions only: banks and credit unions. Lenders, auto captives, brokerages, payment
apps and buy-now-pay-later stay in the financial-services figures and are never counted here. Card rail
only (PIN and signature rows), so every dollar and account figure is a floor.

How an institution is found. Every FDIC bank and NCUA credit union is in a registry (`ti.core.market`),
each with its branches. A card description is matched to one of them on whole tokens, in the form
`financial_services.normalize_core` writes (FCU -> FED CU, BANK -> BK), after

  * the processor tag in front of it is dropped (`CU#`, `OBP*`, `SVL*`, `ACI*`, `PNM*`, `APF*`),
  * a card description cut near 22 characters is repaired (`CREDIT UNIO`, `FEDERAL CREDIT`),
  * a merchant that is not an institution is refused (`SQ *` and the other marketplace tags, a venue
    such as an arena or a stadium named after a bank).

A credit union is matched as its stem plus CU or FED CU, never as a bare stem; a bank needs two words
or the BK suffix. A name that fits several institutions is placed with the nearest one only when that
one is clearly nearer (more than 25 miles), else it is left "Unresolved (ambiguous)", never guessed.

Layers (a tier is assigned once per institution, most specific first):

  National            the universal list (competitors.json, National Bank tier), or branches in
                      `national_states` or more states
  Digital             the universal list's digital banks (no branches)
  Local               a branch within `local_miles` of any client branch
  Local (25-50 mi)    a branch within `market_miles`
  Regional (district) headquartered in the client's Fed district
  State               in the client's state
  Other               everywhere else
  Card-issuing banks  FDIC banks whose payments are card payments, shown apart for review

The thresholds are `DEFAULTS`, overridden per client by `CompetitionLayers` in the client config.
Groups come from the account lenses: responders / mailed non-response / no mail, with the near-responders
(NU 1-4 on a mailer's Resp column, below the response threshold) split out of the mailed non-response;
and, for an ICS client, ICS account / direct mail / referral / not ICS.

Inputs only through the callers (`ti/txn_sections.py`): the card rows and their classification, the
account lenses, the ODD frame, the client config and market record, and the registry book. No path, client
id or client name is written here.
"""
from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import pandas as pd

from .financial_services import normalize_core, _token_regex

NATIONAL, DIGITAL = "National", "Digital"
LOCAL, LOCAL_MARKET = "Local", "Local (25-50 mi)"
REGIONAL, STATE, OTHER = "Regional (district)", "State", "Other (outside district)"
CARD_ISSUER, UNRESOLVED = "Card-issuing banks (review)", "Unresolved (ambiguous)"
TIER_ORDER = [NATIONAL, DIGITAL, LOCAL, LOCAL_MARKET, REGIONAL, STATE, OTHER, CARD_ISSUER, UNRESOLVED]

DEFAULTS = {"local_miles": 25.0, "market_miles": 50.0, "scan_miles": 100.0, "national_states": 10,
            "ambiguity_gap_miles": 25.0, "review_rows": 60, "top_descriptors": 3}

# Fed district by state: each state takes its primary district, as a split state does in v5's competitor
# book; the Dallas district is Texas, Louisiana and New Mexico. The client's own district comes from its
# config (`FedDistrict`) when it has one.
FED_PRIMARY = {
    "CT": 1, "ME": 1, "MA": 1, "NH": 1, "RI": 1, "VT": 1, "NY": 2, "NJ": 2, "PA": 3, "DE": 3, "OH": 4, "KY": 4,
    "VA": 5, "MD": 5, "DC": 5, "NC": 5, "SC": 5, "GA": 6, "FL": 6, "AL": 6, "TN": 6, "MS": 6,
    "IL": 7, "IN": 7, "IA": 7, "MI": 7, "WI": 7, "AR": 8, "MO": 8, "MN": 9, "MT": 9, "ND": 9, "SD": 9,
    "KS": 10, "NE": 10, "OK": 10, "CO": 10, "WY": 10, "TX": 11, "LA": 11, "NM": 11,
    "CA": 12, "OR": 12, "WA": 12, "ID": 12, "UT": 12, "NV": 12, "AZ": 12, "AK": 12, "HI": 12}

DIGITAL_DEPOSITORY = {"Ally", "SoFi", "Chime", "Varo", "Current", "Dave", "Axos"}
CARD_ISSUING = re.compile(r"\b(CREDIT ONE|COMENITY|MERRICK|MEDALLION|CROSS RIVER|CRESCENT BK|HAPPEN|WFF NATL|"
                          r"SYNCHRONY|GOLDMAN|FIRST PREMIER|CELTIC|TOTAL CARD|MISSION LANE|BREAD)\b")
BANKISH = re.compile(r"\b(BANK|BK|BANCORP|BANKING|SAVINGS|FSB|CREDIT UNION|CREDIT UNIO|FCU|FEDERAL CU|FED CU|CU)\b")

_TAG = re.compile(r"^(?:CU#|OBP\*|SVL\*|ACI\*|PNM\*|APF\*|[A-Z]{2,4}#)\s*")
_NOT_INSTITUTION = re.compile(r"^(?:SQ\s*\*|TST\*|SP\s|PAYPAL\s*\*|PP\*|GOOGLE\s*\*|AMZN|AMAZON|DD\s*\*|PY\s*\*)")
_TRUNC = [(re.compile(r"\bFEDERAL CREDIT UNI?O?$"), "FEDERAL CREDIT UNION"),
          (re.compile(r"\bFEDERAL CREDIT$"), "FEDERAL CREDIT UNION"),
          (re.compile(r"\bFED CREDIT UNI?O?$"), "FEDERAL CREDIT UNION"),
          (re.compile(r"\bCREDIT UNI?O?$"), "CREDIT UNION"), (re.compile(r"\bCREDIT U$"), "CREDIT UNION")]
VENUE = {"ARENA", "CENTER", "CENTRE", "STADIUM", "CONC", "CONCESSIONS", "COLISEUM", "AMPHITHEATER", "PAVILION",
         "THEATER", "THEATRE", "BALLPARK", "MASH"}
_SUFFIX_DROP = (" NATL ASSOCIATION", " N A", " NA", " SSB", " FSB", " INC")


def norm(text) -> str:
    """A card description or an institution name in the one form both sides are compared in."""
    s = _TAG.sub("", str(text).upper().strip())
    for rx, rep in _TRUNC:
        s = rx.sub(rep, s)
    return normalize_core(s)


def settings(config) -> dict:
    out = dict(DEFAULTS)
    out.update((config or {}).get("CompetitionLayers") or {})
    return out


def district_of(config, state) -> str:
    """The client's Fed district: its config's, else its state's primary district, else ''."""
    d = str((config or {}).get("FedDistrict") or "").strip()
    if d:
        return d
    return str(FED_PRIMARY.get(str(state or "").upper(), ""))


def district_states(district) -> set:
    return {s for s, d in FED_PRIMARY.items() if str(d) == str(district)}


def name_variants(name, fi_type, credit_union="Credit Union") -> set:
    """The spellings of an institution a card description can carry, in `norm` form."""
    n = norm(name)
    base = {n}
    for sfx in _SUFFIX_DROP:
        if n.endswith(sfx):
            base.add(n[: -len(sfx)].strip())
    base = {v for v in base if v}
    if fi_type == credit_union:
        res = set()
        for v in base:
            stem = re.sub(r"\b(FED CU|CU)$", "", v).strip()
            if not stem:
                continue
            res |= {f"{stem} CU", f"{stem} FED CU"}
            if len(stem.split()) == 1 and stem.endswith("CU") and len(stem) >= 4:
                res.add(stem)                       # a name that is already an acronym ending in CU stands alone
        return res
    return {v for v in base if len(v.split()) >= 2 or v.endswith(" BK")}      # no bare one-word bank stems


# ------------------------------------------------------------------------------------------ registry
def build_registry(book, points, state, dist_states, cfg) -> dict:
    """{institution key: record} with each institution's footprint, distance from the client and tier."""
    near = book.index.nearest_by_key(points, cfg["scan_miles"], key=lambda b: b.inst_key) if points else {}
    local = defaultdict(set)
    for lat, lon in points:
        for b in book.index.near(lat, lon, cfg["local_miles"]):
            local[b.inst_key].add((round(b.lat, 5), round(b.lon, 5)))
    reg = {}
    for key, inst in book.institutions.items():
        states = {b.state for b in inst.branches}
        d = near.get(key, (None, None))[0]
        rec = {"key": key, "name": inst.name, "type": inst.fi_type, "hq_state": inst.state, "states": len(states),
               "in_state": bool(state) and (state in states or inst.state == state), "nearest_mi": d,
               "branches_local": len(local.get(key, ())), "configured": False}
        rec["tier"] = _tier(rec, dist_states, cfg)
        reg[key] = rec
    return reg


def _tier(rec, dist_states, cfg) -> str:
    if CARD_ISSUING.search(norm(rec["name"])):
        return CARD_ISSUER
    if rec["states"] >= cfg["national_states"]:
        return NATIONAL
    d = rec["nearest_mi"]
    if d is not None and d <= cfg["local_miles"]:
        return LOCAL
    if d is not None and d <= cfg["market_miles"]:
        return LOCAL_MARKET
    if rec["hq_state"] in dist_states:
        return REGIONAL
    if rec["in_state"]:
        return STATE
    return OTHER


def dictionary_names(spec) -> tuple[dict, dict]:
    """({pattern in norm form: (name, tier)}, {name: tier or reason it is out of scope})."""
    pats, out_of_scope = {}, {}
    for name, item in (spec.get("institutions") or {}).items():
        tier = item.get("tier")
        if tier == "National Bank":
            t = NATIONAL
        elif name in DIGITAL_DEPOSITORY:
            t = DIGITAL
        else:
            out_of_scope[name] = tier
            continue
        for p in item.get("patterns") or []:
            pats[norm(p)] = (name, t)
    return pats, out_of_scope


def dictionary_footprint(reg, dict_pats) -> dict:
    """The nearest client-branch distance and the widest footprint of each dictionary name, read from the
    registry institutions whose own name contains one of its patterns (Chase -> the registry's Chase bank)."""
    toks = {k: norm(r["name"]).split() for k, r in reg.items()}
    out = {}
    for p, (name, _t) in dict_pats.items():
        pt = tuple(p.split())
        n = len(pt)
        for k, tk in toks.items():
            if any(tuple(tk[i:i + n]) == pt for i in range(len(tk) - n + 1)):
                r = reg[k]
                cur = out.setdefault(name, {"nearest_mi": None, "states": 0})
                if r["nearest_mi"] is not None and (cur["nearest_mi"] is None or r["nearest_mi"] < cur["nearest_mi"]):
                    cur["nearest_mi"] = r["nearest_mi"]
                cur["states"] = max(cur["states"], r["states"])
    return out


def attach_configured(reg, patterns, names, tier, cfg) -> int:
    """The names the CSM typed into the client config (LocalCompetitors, RegionalCompetitors), a list or
    {name: [aliases]}: each is matched to a registry institution whose name contains it, and given its
    aliases; a name the registry does not know becomes an institution of its own in that tier."""
    if isinstance(names, list):
        names = {str(n): [str(n)] for n in names}
    added = 0
    by_norm = {norm(r["name"]): k for k, r in reg.items()}
    for name, aliases in (names or {}).items():
        spellings = {norm(a) for a in ([name] + list(aliases or [])) if a}
        key = by_norm.get(norm(name))
        if key is None:
            key = next((k for nm, k in by_norm.items() if norm(name) and norm(name) in nm), None)
        if key is None:
            key = f"cfg:{name}"
            reg[key] = {"key": key, "name": str(name), "type": "Bank", "hq_state": "", "states": 1, "in_state": True,
                        "nearest_mi": None, "branches_local": 0, "tier": tier, "configured": True}
            added += 1
        for s in spellings:
            if len(s.split()) >= 2 or s.endswith(" BK") or s.endswith("CU"):
                patterns[s].add(key)
    return added


class Matcher:
    """Card description -> (institution, tier, ambiguous) or None, on whole tokens, nearest-wins, never guessed."""

    def __init__(self, reg, patterns, dict_pats, false_positives, cfg, aliases=None):
        self.reg, self.cfg = reg, cfg
        self._exact, self._prefix = {}, defaultdict(list)
        for p, keys in patterns.items():
            for k in keys:
                self._add(p, ("reg", k))
        for p, (name, tier) in dict_pats.items():
            self._add(p, ("dict", name, tier))
        for alias, target in (aliases or {}).items():
            for k, r in reg.items():
                if r["name"] == target:
                    self._add(norm(alias), ("reg", k))
        self._maxn = max((len(t) for t in self._exact), default=1)
        self._fp = _token_regex(false_positives) if false_positives else None

    def _add(self, pattern, target):
        t = tuple(pattern.split())
        if not t:
            return
        self._exact.setdefault(t, []).append(target)
        if len(t) >= 2 and len(t[-1]) >= 3:
            self._prefix[t[:-1]].append((t[-1], target))

    def _resolve(self, targets):
        d = [t for t in targets if t[0] == "dict"]
        if d:
            return d[0], False
        gap = self.cfg["ambiguity_gap_miles"]
        keys = sorted({t[1] for t in targets}, key=lambda k: (self.reg[k]["nearest_mi"] is None,
                                                              self.reg[k]["nearest_mi"] or 1e9,
                                                              not self.reg[k]["in_state"]))
        if len(keys) == 1:
            return ("reg", keys[0]), False
        a, b = self.reg[keys[0]], self.reg[keys[1]]
        clear = a["nearest_mi"] is not None and (b["nearest_mi"] is None or a["nearest_mi"] + gap < b["nearest_mi"])
        return ("reg", keys[0]), not clear

    def match(self, core):
        """(name, tier, key or None, ambiguous) or None."""
        raw = str(core).upper().strip()
        s = norm(core)
        if not s or _NOT_INSTITUTION.match(raw):
            return None
        toks = s.split()
        if VENUE.intersection(toks) and not {"PMT", "PAYMENT", "LOAN"}.intersection(toks):
            return None
        if self._fp is not None and self._fp.search(s):
            return None
        best = None
        for i in range(len(toks)):
            for j in range(min(len(toks), i + self._maxn), i, -1):
                seg = tuple(toks[i:j])
                cand = self._exact.get(seg)
                if cand is None and j == len(toks) and len(seg) >= 2:          # a cut last token ("FEDERAL CREDIT UN")
                    last = seg[-1]
                    cand = [t for lt, t in self._prefix.get(seg[:-1], ()) if lt.startswith(last) and len(last) >= 4] or None
                if cand and (best is None or j - i > best[0]):
                    best = (j - i, cand)
            if best and best[0] >= 2:
                break
        if not best:
            return None
        target, ambiguous = self._resolve(best[1])
        if target[0] == "dict":
            return target[1], target[2], None, False
        r = self.reg[target[1]]
        return r["name"], (UNRESOLVED if ambiguous else r["tier"]), target[1], ambiguous


def build_matcher(book, record, config, dict_spec, cfg):
    """(registry, matcher, dictionary footprint, out-of-scope dictionary names, how many configured names had to be added)."""
    points = [(b["lat"], b["lon"]) for b in (record or {}).get("branches") or [] if b.get("lat") is not None]
    state = ((record or {}).get("profile") or {}).get("state") or ""
    district = district_of(config, state)
    reg = build_registry(book, points, state, district_states(district), cfg)
    patterns = defaultdict(set)
    for key, rec in reg.items():
        inst = book.institutions[key]
        for v in name_variants(inst.name, inst.fi_type):
            patterns[v].add(key)
    added = attach_configured(reg, patterns, (config or {}).get("LocalCompetitors"), LOCAL, cfg)
    added += attach_configured(reg, patterns, (config or {}).get("RegionalCompetitors"), REGIONAL, cfg)
    dict_pats, out_of_scope = dictionary_names(dict_spec)
    foot = dictionary_footprint(reg, dict_pats)
    own = {norm(n) for n in (config or {}).get("SelfNames") or []} | {norm(n) for n in (record or {}).get("self_names") or []}
    fps = sorted(set(dict_spec.get("false_positives") or []) | own)
    return reg, Matcher(reg, patterns, dict_pats, fps, cfg), foot, out_of_scope, added, points, district


# ------------------------------------------------------------------------------------------ figures
def _group_sets(lenses, frame, base_ids) -> tuple[dict, dict]:
    """{group key: set of account ids in the base}, {group key: label}. ARS groups, the near-responder
    split of the mailed non-response, and the ICS groups, each only when the lens has accounts."""
    labels = {"responders": "Responders", "mailed_nonresp": "Mailed, non-response",
              "mailed_nonresp_nu1_4": "Mailed, NU 1-4", "mailed_nonresp_none": "Mailed, no response",
              "not_mailed": "No mail", "ics": "ICS account", "ics_dm": "ICS direct mail",
              "ics_ref": "ICS referral", "not_ics": "Not ICS"}
    sets = {}
    names = set(lenses.names()) if lenses is not None else set()
    for g in ("responders", "mailed_nonresp", "not_mailed", "ics", "ics_dm", "ics_ref"):
        if g in names:
            ids = {str(a) for a in lenses.ids(g)} & base_ids
            if ids:
                sets[g] = ids
    if "mailed_nonresp" in sets and frame is not None and getattr(lenses, "key_column", None) in getattr(frame, "columns", []):
        rc = [c for c in frame.columns if str(c).endswith(" Resp")]
        if rc:
            near = set(frame.loc[frame[rc].astype(str).eq("NU 1-4").any(axis=1), lenses.key_column].astype(str))
            a, b = sets["mailed_nonresp"] & near, sets["mailed_nonresp"] - near
            if a:
                sets["mailed_nonresp_nu1_4"] = a
            if b:
                sets["mailed_nonresp_none"] = b
    if "ics" in sets:
        sets["not_ics"] = base_ids - sets["ics"]
    return sets, {k: labels[k] for k in sets}


def classify_cards(rows, df, base_ids, matcher):
    """The matched card rows of the base, one row per transaction: account, dollars, date, description,
    institution, tier, ambiguous; and the base's card rows, for the unmatched bank-like text."""
    is_card = rows["is_card"].to_numpy()
    acct = df["primary_account_num"].astype(str)
    mask = is_card & acct.isin(base_ids).to_numpy()
    sub = pd.DataFrame({"acct": acct[mask].to_numpy(), "amt": df["amount"].abs().fillna(0.0)[mask].to_numpy(),
                        "date": pd.to_datetime(df["transaction_date"][mask]).to_numpy(),
                        "core": rows["core"][mask].to_numpy(), "type": df["transaction_type"].astype(str).str.upper()[mask].to_numpy()})
    hits = {c: matcher.match(c) for c in pd.unique(sub["core"])}
    sub["inst"] = sub["core"].map(lambda c: hits[c][0] if hits[c] else None)
    sub["tier"] = sub["core"].map(lambda c: hits[c][1] if hits[c] else None)
    sub["key"] = sub["core"].map(lambda c: hits[c][2] if hits[c] else None)
    sub["ambig"] = sub["core"].map(lambda c: bool(hits[c][3]) if hits[c] else False)
    return sub


def _group_rows(frame_, key, sets):
    rows = []
    for k, g in frame_.groupby(key):
        by = {gk: {"accounts": int(g.loc[g["acct"].isin(ids), "acct"].nunique()),
                   "dollars": round(float(g.loc[g["acct"].isin(ids), "amt"].sum()))} for gk, ids in sets.items()}
        rows.append({"key": k, "accounts": int(g["acct"].nunique()), "dollars": round(float(g["amt"].sum())), "by_group": by})
    return sorted(rows, key=lambda r: -r["dollars"])


def _is_review_text(core) -> bool:
    """Bank-looking text nothing matched, worth a name in the review queue: not a marketplace tag and not a
    venue the matcher refused on purpose."""
    s = norm(core)
    if not BANKISH.search(s) or _NOT_INSTITUTION.match(str(core).upper().strip()):
        return False
    return not (VENUE.intersection(s.split()) and not {"PMT", "PAYMENT", "LOAN"}.intersection(s.split()))


def compute(df, rows, lenses, frame, config, anchor_ts, record, book, dict_spec, warn, base_ids,
            key_prefix="cl_") -> dict:
    """The layered competition figures for one client: tiers, groups, institutions, coverage, universe."""
    K = key_prefix
    cfg = settings(config)
    out: dict = {}
    if df is None or not len(df):
        return out
    if book is None:
        warn("competition layers: no FDIC/NCUA reference store; the layers are not computed")
        return out
    base_ids = {str(a) for a in base_ids} if base_ids is not None else set(df["primary_account_num"].astype(str))
    reg, matcher, foot, out_of_scope, added, points, district = build_matcher(book, record, config, dict_spec, cfg)
    if not points:
        warn("competition layers: no market record with branch coordinates for this client; the Local "
             "and Local (25-50 mi) tiers cannot be placed, and distances are not computed")
    if not district:
        warn("competition layers: no Fed district (no FedDistrict in the config and no state in the market record); "
             "the Regional tier is not placed")
    types = {str(t).upper() for t in pd.unique(df["transaction_type"].astype(str))}
    if types - {"PIN", "SIG"}:
        warn("competition layers: the file also carries " + ", ".join(sorted(types - {"PIN", "SIG"})) +
             " rows; the layers read the card rail (PIN, SIG) only, so transfers to institutions are not in them")
    sub = classify_cards(rows, df, base_ids, matcher)
    if not len(sub):
        warn("competition layers: no card rows in the base")
        return out
    sets, labels = _group_sets(lenses, frame, base_ids)
    active = set(sub["acct"].unique())
    base_n, total = len(active), float(sub["amt"].sum())
    matched = sub[sub["inst"].notna()]
    bank_like = sub[sub["inst"].isna() & sub["core"].map(_is_review_text)]
    placed, review = float(matched["amt"].sum()), float(bank_like["amt"].sum())
    denom = {k: len(ids & active) for k, ids in sets.items()}
    out[K + "scope"] = {"depository_only": True, "rail": "card (PIN, SIG)", "window_end": str(pd.Timestamp(anchor_ts).date()) if anchor_ts is not None else None,
                       "district": district, "points": len(points), "thresholds": cfg, "out_of_scope_names": len(out_of_scope)}
    out[K + "base"] = {"accounts": base_n, "dollars": round(total), "groups": denom, "group_labels": labels}
    by = {}
    for gk, ids in sets.items():
        m = matched[matched["acct"].isin(ids)]
        by[gk] = {"accounts": int(m["acct"].nunique()), "pct": round(m["acct"].nunique() / max(denom[gk], 1) * 100, 1),
                  "dollars": round(float(m["amt"].sum()))}
    out[K + "any"] = {"accounts": int(matched["acct"].nunique()), "pct": round(matched["acct"].nunique() / max(base_n, 1) * 100, 1),
                      "dollars": round(placed), "by_group": by}
    seen = matched.groupby("tier")["inst"].nunique()
    tiers_out = []
    for r in _group_rows(matched, "tier", sets):
        tiers_out.append({"tier": r["key"], "accounts": r["accounts"], "pct": round(r["accounts"] / max(base_n, 1) * 100, 1),
                          "dollars": r["dollars"], "institutions": int(seen.get(r["key"], 0)),
                          "by_group": {gk: dict(v, pct=round(v["accounts"] / max(denom[gk], 1) * 100, 1))
                                       for gk, v in r["by_group"].items()}})
    out[K + "tiers"] = tiers_out
    inst_rows = _group_rows(matched, "inst", sets)
    meta = matched.groupby("inst").agg(tier=("tier", "first"), ambiguous=("ambig", "max"), key=("key", "first"))
    top = (matched.groupby(["inst", "core"])["amt"].sum().reset_index().sort_values("amt", ascending=False)
           .groupby("inst").head(cfg["top_descriptors"]).groupby("inst")["core"].apply(list))
    for r in inst_rows:
        name = r.pop("key")
        m = meta.loc[name]
        rec = reg.get(m["key"]) if isinstance(m["key"], str) else None
        fp = foot.get(name)
        r.update({"inst": name, "tier": m["tier"], "ambiguous": bool(m["ambiguous"]),
                  "type": (rec["type"] if rec else "Bank"),
                  "nearest_mi": (round(rec["nearest_mi"], 1) if rec and rec["nearest_mi"] is not None
                                 else (round(fp["nearest_mi"], 1) if fp and fp["nearest_mi"] is not None else None)),
                  "pct": round(r["accounts"] / max(base_n, 1) * 100, 2), "descriptors": top.get(name, [])})
    out[K + "institutions"] = inst_rows
    rq = bank_like.groupby("core").agg(accounts=("acct", "nunique"), txns=("amt", "size"), dollars=("amt", "sum")).sort_values("dollars", ascending=False)
    out[K + "review_queue"] = [[str(c), int(r.accounts), int(r.txns), round(float(r.dollars))] for c, r in rq.head(cfg["review_rows"]).iterrows()]
    out[K + "coverage"] = {"placed_dollars": round(placed), "review_dollars": round(review),
                           "pct": round(placed / (placed + review) * 100, 1) if (placed + review) else None,
                           "ambiguous_dollars": round(float(matched.loc[matched["ambig"], "amt"].sum())),
                           "review_names": int(len(rq))}
    uni = defaultdict(lambda: {"registry": 0, "within_local": 0, "seen": 0})
    for r in reg.values():
        uni[r["tier"]]["registry"] += 1
        uni[r["tier"]]["within_local"] += 1 if r["branches_local"] else 0
    for t, n in seen.items():
        if t in uni:
            uni[t]["seen"] = int(n)
    out[K + "universe"] = [dict(tier=t, **uni[t]) for t in TIER_ORDER if t in uni]
    out["_cl_matched"] = matched                 # hand-off to the analysis modules (popped before the pack is written)
    out["_cl_active"] = active
    out["_cl_sets"] = sets
    out["_cl_sub"] = sub
    return out
