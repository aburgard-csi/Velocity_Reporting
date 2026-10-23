# Ported from ARS v5 02-Scripts/ars/monthly_analysis/ics_sources.py at a491b5c (James Gilmore); logic unchanged.
"""ICS source lists (#74): map the DM and referral lists onto the ODD.

James's workflow, verbatim: look at the accounts in the two ICS lists
(direct mail + referral), map each list's account hash to the ODD, stamp
the account's source (DM or REF), and the ICS analysis takes it from
there. The stamp lands in the 'DM-REF Source' column -- the documented
schema column ics.py has waited on since the legacy port.

The MRDB hash recipe is NOT assumed. Candidate recipes are computed over
the ODD's own account ids and the one that actually matches is used and
REPORTED (warn lines carry the recipe and the match rate per list).
Zero matches falls back to the DM list's account-mask (last 4) + open
date join, unique matches only, also reported. Unmatched list rows are
counted loudly -- a silent partial join would read as a smaller program.

Files live beside the ODD in 01-Data/{period}/{client}/; when neither
exists the frame passes through untouched and nothing prints.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd

_HEX40 = re.compile(r"^[0-9A-Fa-f]{40}$")

# A list that matches fewer than half its rows is the wrong file more often
# than a thin ODD; say so instead of passing quietly (#245).
LOW_MATCH_SHARE = 0.5

DM_TOKENS = ("ics", "direct mail")
REF_TOKENS = ("ics", "referral")


def find_files(folder: Path) -> dict:
    """{'DM': path|None, 'REF': path|None} -- case-insensitive token
    match over the folder's Excel files."""
    out = {"DM": None, "REF": None}
    if not Path(folder).is_dir():
        return out
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() not in (".xls", ".xlsx"):
            continue
        name = p.name.lower()
        if all(t in name for t in DM_TOKENS) and out["DM"] is None:
            out["DM"] = p
        elif all(t in name for t in REF_TOKENS) and out["REF"] is None:
            out["REF"] = p
    return out


def _hash_column(df: pd.DataFrame) -> pd.Series | None:
    """The column whose values are 40-hex hashes (majority vote)."""
    best, best_n = None, 0
    for col in df.columns:
        v = df[col].dropna().astype(str).str.strip()
        if not len(v):
            continue
        n = int(v.str.match(_HEX40).sum())
        if n > best_n:
            best, best_n = col, n
    if best is None or best_n == 0:
        return None
    v = df[best].dropna().astype(str).str.strip()
    return v[v.str.match(_HEX40)].str.upper()


def load_list(path: Path, warn) -> pd.DataFrame:
    """One ICS list as a frame with 'hash' (upper 40-hex) plus, when the
    file carries them, 'mask' (account mask) and 'open_date'. Header row
    is sniffed -- the DM export buries it under nine preamble rows."""
    raw = pd.read_excel(path, header=None)
    header_idx = None
    for i in range(min(len(raw), 25)):
        cells = {str(c).strip().lower() for c in raw.iloc[i].dropna()}
        if cells & {"account mask", "mrdb account hash", "account hash"}:
            header_idx = i
            break
    if header_idx is not None:
        df = raw.iloc[header_idx + 1:].copy()
        df.columns = [str(c).strip() if pd.notna(c) else f"col{j}"
                      for j, c in enumerate(raw.iloc[header_idx])]
    else:
        df = raw

    hashes = _hash_column(df)
    if hashes is None or hashes.empty:
        warn(f"ICS sources: no 40-hex hash column found in {path.name}; "
             f"file skipped")
        return pd.DataFrame(columns=["hash"])
    out = pd.DataFrame({"hash": hashes})

    cols = {str(c).strip().lower(): c for c in df.columns}
    if "account mask" in cols:
        out["mask"] = (df[cols["account mask"]].astype(str)
                       .str.strip().str[-4:]).reindex(out.index)
    for key in ("open date", "issue date"):
        if key in cols:
            out["open_date"] = pd.to_datetime(
                df[cols[key]], errors="coerce").reindex(out.index)
            break
    return out


def _clean_ids(series: pd.Series) -> pd.Series:
    return (series.astype(str).str.strip()
            .str.replace(r"\.0$", "", regex=True))


def _account_ids(frame: pd.DataFrame) -> pd.Series | None:
    cands = _id_candidates(frame)
    return next(iter(cands.values())) if cands else None


def _id_candidates(frame: pd.DataFrame) -> dict:
    """Every account-shaped column, preferred names first. 1615 proved
    the hashed number can live in a column OTHER than the primary id --
    the join scans them all and reports the winner. Preferred columns
    always qualify; extras need an id-ish token in the name (number /
    nbr / id / #) so 'Account Age' never masquerades as an id."""
    preferred = ("Acct ID", "Acct Number", " Acct Number", "Account Number")
    out = {}
    for c in preferred:
        if c in frame.columns:
            out[c] = _clean_ids(frame[c])
    for c in frame.columns:
        if c in out:
            continue
        name = str(c)
        lc = name.lower()
        if re.match(r"^[A-Z][a-z]{2}\d{2} ", name):     # monthly-tagged
            continue
        if not any(t in lc for t in ("acct", "account", "member", "card")):
            continue
        if not re.search(r"(number|nbr|\bno\b|\bid\b|#)", lc):
            continue
        if any(t in lc for t in ("age", "type", "code", "bal", "rate")):
            continue
        v = _clean_ids(frame[c])
        if v.str.contains(r"\d").mean() >= 0.5:
            out[c] = v
        if len(out) >= 8:
            break
    return out


def _recipes(ids: pd.Series) -> dict:
    """Candidate hash recipes over the ODD's own ids -- tried, never
    assumed. Each maps recipe name -> Series of upper 40-hex."""
    def sha1(s: pd.Series) -> pd.Series:
        return s.map(lambda v: hashlib.sha1(v.encode()).hexdigest().upper())
    digits = ids.str.replace(r"\D", "", regex=True)
    return {
        "sha1(acct)": sha1(ids),
        "sha1(acct, no leading zeros)": sha1(ids.str.lstrip("0")),
        "sha1(acct, zero-padded 10)": sha1(ids.str.zfill(10)),
        "sha1(acct, zero-padded 12)": sha1(ids.str.zfill(12)),
        "sha1(acct, zero-padded 16)": sha1(ids.str.zfill(16)),
        "sha1(acct, digits only)": sha1(digits),
        "sha1(acct, digits only, no leading zeros)":
            sha1(digits.str.lstrip("0")),
    }


def _odd_hash_column(frame: pd.DataFrame) -> tuple[str, pd.Series] | None:
    """A 40-hex column in the ODD itself (1615 carries the MRDB hash in
    column C): found by CONTENT whatever the header says. Direct
    hash-to-hash is the join of record when it exists."""
    for c in frame.columns:
        if re.match(r"^[A-Z][a-z]{2}\d{2} ", str(c)):    # monthly-tagged
            continue
        sample = frame[c].dropna().astype(str).str.strip().head(50)
        if len(sample) < 5:
            continue
        if sample.str.match(_HEX40).mean() >= 0.6:
            v = frame[c].astype(str).str.strip().str.upper()
            return str(c), v.where(v.str.match(_HEX40), "")
    return None


def _mask_date_join(ids: pd.Series, opened: pd.Series,
                    lst: pd.DataFrame) -> dict:
    """list row -> frame index via last-4 + open date within +-3 days.
    Unique last4+date pairs only on the ODD side."""
    last4 = ids.str[-4:]
    frame_key = {}
    counts = last4.value_counts()
    for i, (l4, od) in enumerate(zip(last4, opened)):
        if pd.isna(od):
            continue
        frame_key.setdefault(l4, []).append((od, last4.index[i]))
    out = {}
    for row, (mask, ld) in enumerate(zip(lst.get("mask"), lst.get("open_date"))):
        if pd.isna(ld) or not isinstance(mask, str):
            continue
        hits = [idx for od, idx in frame_key.get(mask[-4:], [])
                if abs((od - ld).days) <= 3]
        if len(hits) == 1:
            out[row] = hits[0]
    return out


def attach(frame: pd.DataFrame, folder: Path, warn,
           expected: bool = False) -> pd.DataFrame:
    """Stamp 'DM-REF Source' onto the frame from whatever ICS lists sit
    in the client's data folder.

    No folder and nothing expected -> frame untouched, silent (most
    clients have no ICS programme). A folder holding files that do not
    qualify, or an ICS client with no folder at all, says so and names
    the path -- a mistitled month folder cost a whole run before this
    (#245)."""
    folder = Path(folder)
    files = find_files(folder)
    if not files["DM"] and not files["REF"]:
        present = sorted(p.name for p in folder.iterdir()
                         if p.is_file()) if folder.is_dir() else []
        if present:
            warn(f"ICS sources: no list file qualified in {folder}; "
                 f"saw {present}. A list must be .xls/.xlsx and its name "
                 f"must contain 'ics' plus 'direct mail' or 'referral'")
        elif expected:
            warn(f"ICS: no list files in {folder}; the client is flagged "
                 f"for ICS, so the chapter will not appear until the "
                 f"direct-mail and referral lists are placed there")
        return frame

    lists = {}
    for source in ("DM", "REF"):
        if files[source] is not None:
            lists[source] = load_list(files[source], warn)

    candidates = _id_candidates(frame)
    if not candidates and _odd_hash_column(frame) is None:
        warn("ICS sources: no account id or hash column in the ODD; "
             "lists ignored")
        return frame

    all_hashes = set()
    for df in lists.values():
        all_hashes |= set(df["hash"])

    chosen, chosen_hashes, matched_n = None, None, 0
    direct = _odd_hash_column(frame)
    if direct is not None:
        col, hashes = direct
        n = int(hashes.isin(all_hashes).sum())
        if n > 0:
            chosen = f"the ODD's own hash column {col!r}"
            chosen_hashes, matched_n = hashes, n
    if chosen is None:
        for col, cand_ids in candidates.items():
            for name, hashed in _recipes(cand_ids).items():
                n = int(hashed.isin(all_hashes).sum())
                if n > matched_n:
                    chosen = f"{name} on {col!r}"
                    chosen_hashes, matched_n = hashed, n

    frame = frame.copy()
    src = pd.Series("", index=frame.index)

    if chosen is not None and matched_n > 0:
        # membership, not reindex: every ODD row whose id hashes into a
        # list stamps -- duplicate account ids stamp on all their rows
        for source, df in lists.items():
            hashes = set(df["hash"])
            mask = chosen_hashes.isin(hashes).to_numpy()
            src[mask] = src[mask].where(src[mask] == "",
                                        src[mask] + "+") + source
            hit_rows = int(df["hash"].isin(set(chosen_hashes)).sum())
            warn(f"ICS sources: {source} list matched {hit_rows} of "
                 f"{len(df)} rows via {chosen}")
            if len(df) and hit_rows / len(df) < LOW_MATCH_SHARE:
                warn(f"ICS sources: {source} list matched under half of "
                     f"its rows; the list may be the wrong period or the "
                     f"wrong institution, or the ODD is missing accounts")
    else:
        # unknown recipe: the DM list's mask+date join still identifies
        # accounts; unique matches only, and the method is named
        opened = pd.to_datetime(frame.get("Date Opened"), errors="coerce")
        for source, df in lists.items():
            if "mask" not in df.columns or "open_date" not in df.columns:
                warn(f"ICS sources: {source} list has no usable hash recipe "
                     f"and no mask+date columns; {len(df)} rows unmatched")
                continue
            best_col, best_idx = None, {}
            for col, cand_ids in candidates.items():
                idx_map = _mask_date_join(cand_ids, opened, df)
                if len(idx_map) > len(best_idx):
                    best_col, best_idx = col, idx_map
            if best_idx:
                idx = pd.Index(best_idx.values())
                src.loc[idx] = src.loc[idx].where(
                    src.loc[idx] == "", src.loc[idx] + "+") + source
            warn(f"ICS sources: no hash recipe matched; {source} list "
                 f"matched {len(best_idx)} of {len(df)} rows via account "
                 f"mask + open date (+-3 days, unique pairs, "
                 f"column {best_col!r})")

    stamped = int((src != "").sum())
    if stamped:
        frame["DM-REF Source"] = src
        total_rows = sum(len(df) for df in lists.values())
        warn(f"ICS sources: {stamped} ODD accounts stamped from "
             f"{total_rows} list rows "
             f"({', '.join(f'{k}: {len(v)}' for k, v in lists.items())})")
    else:
        warn("ICS sources: lists found but NOTHING matched the ODD -- "
             "the hash recipe is unknown and no mask+date join landed; "
             "paste a few raw list rows + ODD ids on #74")
    return frame


def _deep_candidates(frame: pd.DataFrame, cap: int = 25) -> dict:
    """--deep: EVERY column whose values are mostly digit-strings of a
    plausible id length -- the hashed field may hide under any name."""
    out = {}
    for c in frame.columns:
        if re.match(r"^[A-Z][a-z]{2}\d{2} ", str(c)):    # monthly-tagged
            continue
        v = _clean_ids(frame[c])
        digits = v.str.replace(r"\D", "", regex=True)
        ok = (digits.str.len().between(5, 20)).mean()
        if ok >= 0.5:
            out[str(c)] = v
        if len(out) >= cap:
            break
    return out


def _affix_recipes(ids: pd.Series) -> dict:
    """Composite candidates: single-letter application prefixes and
    suffixes some cores fold into the canonical account key."""
    def sha1(sr):
        return sr.map(lambda v: hashlib.sha1(v.encode()).hexdigest().upper())
    out = {}
    for affix in ("D", "S", "C"):
        out[f"sha1('{affix}'+acct)"] = sha1(affix + ids)
        out[f"sha1(acct+'{affix}')"] = sha1(ids + affix)
    return out


def probe(client: str, period: str, data_root: Path, output_root: Path,
          echo=print, deep: bool = False) -> None:
    """The #74 diagnostic: everything needed to see WHY a join matched
    or missed, with no account numbers or names printed -- truncated
    hashes and id shapes only. Paste the output on the issue."""
    ics_dir = Path(data_root) / "ICS" / period / client
    echo(f"ICS dir: {ics_dir}  (exists: {ics_dir.is_dir()})")
    files = find_files(ics_dir)
    for source, p in files.items():
        echo(f"  {source}: {p.name if p else 'NOT FOUND'}")

    lists = {}
    for source, p in files.items():
        if p is None:
            continue
        df = load_list(p, lambda msg: echo(f"  ! {msg}"))
        lists[source] = df
        sample = ", ".join(h[:10] + "…" for h in df["hash"].head(3))
        echo(f"  {source}: {len(df)} hashes; sample {sample}; "
             f"cols {list(df.columns)}")

    pq = Path(output_root) / period / client / "enriched.parquet"
    if not pq.exists():
        echo(f"no enriched frame at {pq} -- run the monthly analysis "
             f"first, then re-run this probe")
        return
    frame = pd.read_parquet(pq)
    candidates = _deep_candidates(frame) if deep else _id_candidates(frame)
    if not candidates:
        echo("ODD: no account-shaped column found")
        return
    all_hashes = set()
    for df in lists.values():
        all_hashes |= set(df["hash"])
    opened = pd.to_datetime(frame.get("Date Opened"), errors="coerce")
    dm = lists.get("DM")
    echo(f"ODD: {len(frame)} rows; {len(candidates)} candidate id "
         f"column(s); {len(all_hashes)} distinct list hashes")
    direct = _odd_hash_column(frame)
    if direct is not None:
        col, hashes = direct
        for source, df in lists.items():
            n = int(df["hash"].isin(set(hashes)).sum())
            echo(f"  ODD hash column {col!r}: {source} direct match "
                 f"{n} of {len(df)}")
    else:
        echo("  no 40-hex hash column detected in the ODD")
    for col, ids in candidates.items():
        lengths = ids.str.len().value_counts().sort_index()
        shape = ", ".join(f"{k}ch x {v}" for k, v in lengths.head(6).items())
        echo(f"  column {col!r}: lengths {shape}")
        recipes = dict(_recipes(ids))
        if deep:
            recipes.update(_affix_recipes(ids))
        for name, hashed in recipes.items():
            n = int(hashed.isin(all_hashes).sum())
            mark = "  <-- MATCH" if n else ""
            if n or not deep:
                echo(f"    {name:<44} {n} matches{mark}")
        if deep and not any(
                int(h.isin(all_hashes).sum()) for h in recipes.values()):
            echo(f"    (all {len(recipes)} recipes: 0 matches)")
        if dm is not None and "mask" in dm.columns \
                and "open_date" in dm.columns:
            hits = _mask_date_join(ids, opened, dm)
            echo(f"    mask+date (+-3 days, unique pairs)          "
                 f"{len(hits)} of {len(dm)} DM rows")


if __name__ == "__main__":
    import sys as _sys
    args = _sys.argv[1:]
    if len(args) < 2:
        print("usage: python -m ars.monthly_analysis.ics_sources "
              "{client} {period} [data_root] [output_root]")
        raise SystemExit(2)
    deep = "--deep" in args
    args = [a for a in args if a != "--deep"]
    root = Path(args[2]) if len(args) > 2 else Path("../01-Data")
    out = Path(args[3]) if len(args) > 3 else Path("../03-Output")
    probe(args[0], args[1], root, out, deep=deep)
