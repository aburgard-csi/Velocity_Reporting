"""What the dictionaries do not know yet.

Three reports, written beside the existing name review queues:

  ``map_unmapped_mcc``  every MCC reaching "Other", ranked by dollars, with
                        the merchant names carrying it -- this is what makes
                        the taxonomy repeatable per client instead of a
                        one-off, the same loop ``fin_review_queue`` already
                        runs for names.
  ``map_conflicts``     strings two dictionaries classify differently. The
                        178 finserv/competitor collisions are BY DESIGN (one
                        asks what product, the other asks who with); only a
                        genuine disagreement is reported.
  ``map_dead_patterns`` configured strings that matched nothing, so the
                        dictionaries can be pruned and not only grown.

Nothing here changes a number. It reports.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .merchants import OTHER, group_ranges

TOP_UNMAPPED = 25
NAMES_PER_CODE = 3

# The two name dictionaries answer different questions, so overlap is normal
# (178 strings on the shipped config). A conflict is only worth a human's
# time when they disagree about KIND -- whether the dollars count as leakage
# or are set aside as adjacency.
#
# One such disagreement is DELIBERATE and written down: SPEC-competition.md
# lines 72-74 keep digital banks as competitors even though financial_services
# files them under "Fintech / Neobanks" as adjacency -- "a neobank holding the
# member's checking is the clearest deposit competitor". Those are reported as
# documented so nobody "fixes" them; everything else is unreviewed.
DOCUMENTED_TIER = "Digital Bank / Fintech Lender"
DOCUMENTED_NOTE = "deliberate -- SPEC-competition.md:72"


def _mcc(card: pd.DataFrame) -> pd.Series:
    if "mcc_code" not in card.columns:
        return pd.Series(np.nan, index=card.index)
    return pd.to_numeric(card["mcc_code"], errors="coerce")


def unmapped_mcc(card: pd.DataFrame, cats: pd.Series, spec: dict,
                 amounts: pd.Series) -> list:
    """[[mcc, txns, dollars, "NAME · NAME · NAME"], ...] ranked by dollars."""
    mcc = _mcc(card)
    other = (cats == OTHER).to_numpy() & mcc.notna().to_numpy()
    if not other.any():
        return []
    frame = pd.DataFrame({"mcc": mcc[other].astype(int),
                          "amount": amounts[other],
                          "key": card.loc[other, "merchant_key"].astype(str)})
    rows = []
    for code, g in frame.groupby("mcc", observed=True):
        names = (g.groupby("key")["amount"].sum()
                 .sort_values(ascending=False).head(NAMES_PER_CODE).index)
        rows.append([int(code), int(len(g)), round(float(g["amount"].sum())),
                     " · ".join(names)])
    rows.sort(key=lambda r: -r[2])
    return rows[:TOP_UNMAPPED]


def conflicts(fin_spec: dict, comp_spec: dict, mch_spec: dict) -> list:
    """[[pattern, "finserv:X (kind)", "competitor:Y", "merchant:Z"], ...] --
    only where the two name dictionaries disagree about kind, or where all
    three claim the same string."""
    fin = {}
    for name, c in (fin_spec.get("categories") or {}).items():
        for p in c.get("patterns") or []:
            fin[str(p).upper()] = (name, c.get("kind", "leakage"))
    comp = {}
    for name, i in (comp_spec.get("institutions") or {}).items():
        tier = i.get("tier", "")
        for p in i.get("patterns") or []:
            comp[str(p).upper()] = (name, tier)
    mch = {}
    for name, entry in (mch_spec.get("keyword_buckets") or {}).items():
        words = entry["words"] if isinstance(entry, dict) else entry
        for w in words or []:
            mch[str(w).upper()] = name

    rows = []
    for pat in sorted(set(fin) & set(comp)):
        fin_cat, fin_kind = fin[pat]
        comp_name, comp_tier = comp[pat]
        # competition treats every non-ecosystem tier as a competitor, so
        # finserv calling the same string adjacency is a real disagreement
        adjacency_vs_competitor = (fin_kind == "adjacency"
                                   and comp_tier != "Payment Ecosystem")
        three_way = pat in mch
        if not (adjacency_vs_competitor or three_way):
            continue
        status = (DOCUMENTED_NOTE if comp_tier == DOCUMENTED_TIER
                  else "unreviewed")
        rows.append([pat, f"{fin_cat} ({fin_kind})",
                     f"{comp_name} / {comp_tier}",
                     mch.get(pat, "-"), status])
    # unreviewed first -- the documented ones are context, not a queue
    rows.sort(key=lambda r: (r[4] != "unreviewed", r[0]))
    return rows


def dead_patterns(fin_spec: dict, seen_providers: set) -> list:
    """Configured categories whose patterns never produced a provider."""
    out = []
    for name, c in (fin_spec.get("categories") or {}).items():
        pats = {str(p).upper() for p in (c.get("patterns") or [])}
        if pats and not (pats & seen_providers):
            out.append([name, len(pats)])
    out.sort(key=lambda r: -r[1])
    return out


def compute(card: pd.DataFrame, cats: pd.Series, amounts: pd.Series,
            fin_spec: dict, comp_spec: dict, mch_spec: dict,
            providers: pd.Series | None, warn) -> dict:
    out: dict = {}
    unmapped = unmapped_mcc(card, cats, mch_spec, amounts)
    if unmapped:
        total = float(amounts.sum()) or 1.0
        share = sum(r[2] for r in unmapped) / total * 100
        out["map_unmapped_mcc"] = unmapped
        out["map_unmapped_mcc_columns"] = ["mcc", "txns", "dollars",
                                           "top_merchants"]
        out["map_unmapped_mcc_pct"] = round(share, 1)
        if share > 10:
            warn(f"mapping: {share:.0f}% of card dollars sit on MCCs with no "
                 f"group; the top codes are in map_unmapped_mcc")
    rows = conflicts(fin_spec, comp_spec, mch_spec)
    if rows:
        out["map_conflicts"] = rows
        out["map_conflicts_columns"] = ["pattern", "financial_services",
                                        "competition", "merchant_bucket",
                                        "status"]
        out["map_conflicts_unreviewed"] = sum(1 for r in rows
                                              if r[4] == "unreviewed")
    if providers is not None:
        seen = {str(p).upper() for p in providers.dropna().unique()}
        dead = dead_patterns(fin_spec, seen)
        if dead:
            out["map_dead_categories"] = dead
            out["map_dead_categories_columns"] = ["category", "patterns"]
    return out
