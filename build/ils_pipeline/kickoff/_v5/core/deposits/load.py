# Ported from v5 02-Scripts/core/deposits/load.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
"""Reading the deposits file: discovery, header mapping, and the parquet cache.

Roughly eight million rows for a single client, so it is treated the way the
transaction loader treats its files and for the same reasons: never held as
text, read in chunks, cached once as parquet keyed on name + mtime + size, and
trimmed to the four columns the analysis needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# Below this share of the base matched to the file, no deposit figure is
# presentable: the slide gate refuses, the report prints READ THIS FIRST, and
# the transaction join warns. One name, so the three cannot disagree.
MIN_MATCH_PCT = 50.0

CACHE_VERSION = 1
CHUNK_ROWS = 250_000

# Header spellings seen in the wild, mapped to the names used downstream.
COLUMN_MAP = {
    "acct number": "acct", "account number": "acct", "acct nbr": "acct",
    "acct id": "acct", "account": "acct", "acct": "acct",
    # RALLY's extract keys on the HASHED account, which is what the ODD's
    # "Acct Number" carries and what the transaction files join on.
    "hashed account": "acct", "hashed acct": "acct", "account hash": "acct",
    "date": "date", "post date": "date", "posting date": "date",
    "deposit date": "date", "tran date": "date",
    "dep count": "dep_count", "deposit count": "dep_count",
    "count": "dep_count", "deposits": "dep_count",
    "dep amount": "dep_amount", "deposit amount": "dep_amount",
    "amount": "dep_amount", "dep amt": "dep_amount",
}
KEEP = ["acct", "date", "dep_count", "dep_amount"]

# Files are found by name, because the folder they land in has varied.
NAME_RE = re.compile(r"depos", re.I)
SEARCH_DIRS = ("ars_data", "ARS Data", "ARS", "Deposits", "deposits")


@dataclass
class LoadReport:
    path: str | None = None
    rows: int = 0
    accounts: int = 0
    months: int = 0
    cached: bool = False
    warnings: list[str] = field(default_factory=list)


def find_file(data_root: Path, client_id: str) -> Path | None:
    """The client's deposits file, wherever it landed.

    Searched by name rather than by an agreed path: the folder convention has
    moved before, and a file that exists but is not found reads exactly like a
    file that was never delivered.
    """
    root = Path(data_root)
    seen: list[Path] = []
    for name in SEARCH_DIRS:
        for base in (root / name, root / name / str(client_id)):
            if base.is_dir():
                seen.extend(p for p in base.rglob("*")
                            if p.is_file() and NAME_RE.search(p.name))
    if not seen:
        seen = [p for p in root.rglob("*")
                if p.is_file() and NAME_RE.search(p.name)
                and p.suffix.lower() in (".csv", ".txt", ".tsv")]
    if not seen:
        return None
    # Newest wins when a client has been re-sent.
    return max(seen, key=lambda p: p.stat().st_mtime)


def _cache_path(cache_dir: Path, path: Path) -> Path:
    st = path.stat()
    return (Path(cache_dir) /
            f"{path.stem}.{int(st.st_mtime)}.{st.st_size}.v{CACHE_VERSION}.parquet")


def _rename(columns) -> dict:
    out = {}
    for col in columns:
        # Underscores are separators too. RALLY ships DEPOSIT_AMOUNT and
        # DEPOSIT_DATE; normalising whitespace alone left both unmatched, the
        # file parsed to zero rows, and every deposit condition then defaulted
        # across the whole book.
        key = re.sub(r"[\s_]+", " ", str(col).strip().lower())
        if key in COLUMN_MAP:
            out[col] = COLUMN_MAP[key]
    return out


def load(path: Path, cache_dir: Path | None, report: LoadReport) -> pd.DataFrame:
    """One deposits file -> a trimmed frame, via the local parquet cache."""
    path = Path(path)
    report.path = str(path)
    cached = _cache_path(cache_dir, path) if cache_dir else None
    if cached is not None and cached.exists():
        frame = pd.read_parquet(cached)
        report.cached = True
    else:
        sep = "\t" if path.suffix.lower() in (".tsv", ".txt") else ","
        chunks = []
        for chunk in pd.read_csv(path, sep=sep, chunksize=CHUNK_ROWS,
                                 engine="c", dtype=str,
                                 on_bad_lines="skip"):
            chunk = chunk.rename(columns=_rename(chunk.columns))
            missing = [c for c in ("acct", "date", "dep_amount")
                       if c not in chunk.columns]
            if missing:
                report.warnings.append(
                    f"{path.name}: no column maps to {', '.join(missing)}; "
                    f"saw {list(chunk.columns)[:8]}")
                return pd.DataFrame(columns=KEEP)
            if "dep_count" not in chunk.columns:
                chunk["dep_count"] = 1
            chunks.append(chunk[KEEP])
        if not chunks:
            return pd.DataFrame(columns=KEEP)
        frame = pd.concat(chunks, ignore_index=True)
        frame["acct"] = frame["acct"].astype(str).str.strip() \
            .str.replace(r"\.0$", "", regex=True)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        for col in ("dep_count", "dep_amount"):
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame = frame[frame["date"].notna() & frame["dep_amount"].notna()]
        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            tmp = cached.with_suffix(".tmp.parquet")
            frame.to_parquet(tmp, index=False)
            tmp.replace(cached)

    report.rows = len(frame)
    report.accounts = int(frame["acct"].nunique()) if len(frame) else 0
    report.months = (int(frame["date"].dt.to_period("M").nunique())
                     if len(frame) else 0)
    return frame
