"""What MCCs does this client's card file actually carry?

    python -m ars.transaction_intelligence.mcc_dump 1776

Reads the parquet cache the loader already wrote -- no re-parse of the raw
files -- and prints every distinct MCC by dollars, with the merchant names
carrying it and the group it currently resolves to.

This is the seed for `0_Config/mcc_reference.json`: map the codes that
appear in real data, ranked by dollars, rather than the whole ISO 18245
space. Codes showing "-- unmapped --" are what the taxonomy is missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from .merchants import OTHER, group_ranges, load_categories

CARD_TYPES = ("PIN", "SIG")
NAMES_PER_CODE = 4


def _index(spec: dict) -> dict:
    out = {}
    for name, entry in (spec.get("mcc_groups") or {}).items():
        parent = entry["parent"] if isinstance(entry, dict) else ""
        for lo, hi in group_ranges(entry):
            for code in range(lo, hi + 1):
                out[code] = (name, parent)
    return out


def dump(client: str, root: Path) -> pd.DataFrame:
    cache = root / "03-Output/_cache/txn" / client
    files = sorted(cache.glob("*.parquet"))
    if not files:
        raise SystemExit(f"no parquet cache for {client} under {cache}")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    card = df[df["transaction_type"].astype(str).str.upper().isin(CARD_TYPES)]
    if not len(card):
        raise SystemExit(f"{client}: no PIN/SIG rows in the cache")

    mcc = pd.to_numeric(card["mcc_code"], errors="coerce")
    known = mcc.notna()
    print(f"{client}: {len(df):,} rows, {len(card):,} card, "
          f"MCC on {known.mean() * 100:.1f}%, "
          f"{int(mcc.nunique()):,} distinct codes")

    lookup = _index(load_categories(root / "0_Config"))
    frame = pd.DataFrame({"mcc": mcc[known].astype(int),
                          "amount": card.loc[known, "amount"].abs(),
                          "acct": card.loc[known, "primary_account_num"],
                          "key": card.loc[known, "merchant_key"].astype(str)})
    rows = []
    for code, g in frame.groupby("mcc", observed=True):
        names = (g.groupby("key")["amount"].sum()
                 .sort_values(ascending=False).head(NAMES_PER_CODE).index)
        group, parent = lookup.get(int(code), ("-- unmapped --", ""))
        rows.append({"mcc": int(code), "txns": len(g),
                     "accounts": g["acct"].nunique(),
                     "dollars": round(float(g["amount"].sum())),
                     "group": group, "parent": parent,
                     "top_merchants": " · ".join(names)})
    out = pd.DataFrame(rows).sort_values("dollars", ascending=False)
    total = out["dollars"].sum() or 1
    out["pct"] = (out["dollars"] / total * 100).round(2)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    root = Path(__file__).resolve().parents[3]
    out = dump(argv[1], root)
    unmapped = out[out["group"] == "-- unmapped --"]
    print(f"unmapped: {len(unmapped):,} codes, "
          f"{unmapped['pct'].sum():.1f}% of card dollars\n")
    cols = ["mcc", "txns", "accounts", "dollars", "pct", "group",
            "top_merchants"]
    with pd.option_context("display.max_colwidth", 52, "display.width", 200):
        print(out[cols].head(60).to_string(index=False))
    dest = root / "03-Output" / f"mcc_dump_{argv[1]}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest, index=False)
    print(f"\nfull table -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
