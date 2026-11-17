"""The portfolio row: one line per client per data month, appended by every TI build (fs-06), so
benchmarks across the book accrue instead of being rebuilt (James, 2026-11: "peer benchmarking = a
table appended by every monthly TI run").

Financial-services columns today; the Competition columns are added to COLUMNS when that chapter's
registry lands. The table lives wherever `RPE_TI_PORTFOLIO` points; the build never picks a shared
location itself. With it unset, the row is written only beside the decks (`ti_portfolio_row.csv`).
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

KEY = ("client_id", "data_month")
COLUMNS = [
    "client_id", "client_name", "data_month", "computed",
    "fin_base_accounts", "fin_any_accounts", "fin_any_pct", "fin_any_dollars",
    "fin_addressable_accounts", "fin_addressable_pct", "fin_addressable_dollars",
    "fin_adjacency_pct", "fin_matched_rows_pct", "fin_matched_dollars_pct",
    "fin_review_queue_dollars", "fin_named_depository_accounts",
]


def row(pack: dict) -> dict:
    m = pack.get("metrics") or {}
    d = m.get("fin_definitions") or {}
    c = m.get("fin_coverage") or {}
    return {
        "client_id": pack.get("client_id"), "client_name": pack.get("client_name"),
        "data_month": pack.get("data_month"), "computed": pack.get("computed"),
        "fin_base_accounts": d.get("base_accounts"),
        "fin_any_accounts": (d.get("any") or {}).get("accounts"),
        "fin_any_pct": (d.get("any") or {}).get("pct"),
        "fin_any_dollars": (d.get("any") or {}).get("dollars"),
        "fin_addressable_accounts": (d.get("addressable") or {}).get("accounts"),
        "fin_addressable_pct": (d.get("addressable") or {}).get("pct"),
        "fin_addressable_dollars": (d.get("addressable") or {}).get("dollars"),
        "fin_adjacency_pct": (d.get("adjacency") or {}).get("pct"),
        "fin_matched_rows_pct": c.get("matched_rows_pct"),
        "fin_matched_dollars_pct": c.get("matched_dollars_pct"),
        "fin_review_queue_dollars": c.get("review_queue_dollars"),
        "fin_named_depository_accounts": m.get("fininst_named_accounts"),
    }


def upsert(path, new_row: dict) -> str:
    """Write `new_row` into the table at `path`, replacing the same client and month. Columns
    already in the table that this version does not know are kept, so a newer build's columns
    survive an older one's append."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows, cols = [], list(COLUMNS)
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols += [c for c in (reader.fieldnames or []) if c not in cols]
            rows = [r for r in reader
                    if tuple(str(r.get(k, "")) for k in KEY) != tuple(str(new_row.get(k, "")) for k in KEY)]
    rows.append({k: ("" if v is None else v) for k, v in new_row.items()})
    rows.sort(key=lambda r: (str(r.get("client_id", "")), str(r.get("data_month", ""))))
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    return str(path)


def shared_table() -> str | None:
    return os.environ.get("RPE_TI_PORTFOLIO") or None
