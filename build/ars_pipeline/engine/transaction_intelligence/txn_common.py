import re

import pandas as pd
ACCT_KEY_CANDIDATES = ("Acct Number", " Acct Number", "Acct ID")
HASH_LEN = 32          # a hashed account id is at least this long; a number never is
_HEX = re.compile(r"[0-9A-Fa-f]{32,}")


def norm_accounts(values) -> pd.Series:
    """ONE reading of an account id, on the transaction side and the ODD side alike: text,
    trimmed, no float tail ("123.0"), and no leading zeros when it is a number. A hash keeps
    every character. 1441 (2026-09-29): 10.9M rows read and 0 of them joined the ODD because
    the two sides spelled the same account differently."""
    t = pd.Series(values).astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    numeric = t.str.fullmatch(r"\d+")
    stripped = t.str.lstrip("0")
    stripped = stripped.where(stripped != "", "0")
    return t.where(~numeric.fillna(False), stripped)


def odd_account_key(odd: pd.DataFrame, txn_accounts=None, warn=None):
    """-> (key, ids, info). The ODD column the transaction accounts join on, chosen ONCE and
    used by every chapter (portfolio, lenses, leakage). Candidates are Acct Number / Acct ID
    plus, when the transaction accounts are hashes, any column whose values are hashes.
    With `txn_accounts` the candidate matching the most of them wins (ties: the first);
    without, the first candidate present. `ids` is that column, normalised, aligned to
    `odd.index`. `info` carries the per-candidate match counts for the report."""
    cands = [c for c in ACCT_KEY_CANDIDATES if c in odd.columns]
    tk = None
    if txn_accounts is not None:
        tk = norm_accounts(pd.Series(list(txn_accounts)).drop_duplicates())
        if len(tk) and (tk.str.len() >= HASH_LEN).mean() > 0.5:
            for c in odd.columns:
                if c in cands or not (odd[c].dtype == object or pd.api.types.is_string_dtype(odd[c])):
                    continue
                sample = odd[c].dropna().astype(str).head(50)
                if len(sample) and sample.str.fullmatch(_HEX).mean() > 0.9:
                    cands.append(c)
    scored = []
    for c in cands:
        ids = norm_accounts(odd[c]); ids.index = odd.index
        matched = int(tk.isin(set(ids)).sum()) if tk is not None else None
        scored.append((c, ids, matched))
    info = {"txn_odd_join_candidates": [[c, m] for c, _, m in scored]}
    if not scored:
        if warn:
            warn("ODD has no Acct Number / Acct ID column; the transaction file cannot be joined")
        return None, None, info
    if tk is None:
        key, ids, _ = scored[0]
    else:
        key, ids, _ = max(scored, key=lambda x: (x[2], -cands.index(x[0])))
        best = max(m for _, _, m in scored)
        if warn and best == 0:
            warn("no transaction account matches any ODD id column "
                 + ", ".join(f"{c} ({m})" for c, _, m in scored)
                 + "; the two files spell accounts differently")
    return key, ids, info


def ranked(counts, ascending: bool = False):
    """A ranking whose ties break the same way on every machine.

    pandas' default sort is quicksort, which is NOT stable, so rows with equal
    counts come out in an arbitrary order that differs between platforms and
    numpy versions. On the work PC that made three metric keys disagree with
    the same run on macOS -- SHELL and UBER both on 798 accounts, AMEX and
    FIDELITY both on 1,969 transactions -- which means a deck could name a
    different "top merchant" for identical data.

    Sorting the index first and then sorting by value with a STABLE kind
    breaks every tie alphabetically, which is both reproducible and defensible
    on a slide.
    """
    return counts.sort_index().sort_values(ascending=ascending, kind="mergesort")
