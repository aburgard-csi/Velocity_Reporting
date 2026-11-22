"""
Reads the figures the peer comparison needs from OTHER ILS clients' own extracts, into one small table.

For each ILS client on the analysis share's `ILS Client Analysis` folder (READ-ONLY: nothing is ever written there),
the newest `DataPull_*` folder's ZAccounts extract is read for four columns only, per account type:

    open accounts (acctstatus O), NSF/OD items in 365 days (items365), collected fees in 365 days (CollectedFees365),
    NSF/OD users (an open account with items365 above zero).

and one row per client and account type is written to `<Build Artifacts>/ils_analysis/peers/ils_peer_metrics.csv`:
client_id, accttype, as_of, open_accounts, items365, fees365, users365, source. A client whose newest extract cannot be
found or read is left out and listed in the run's log, never guessed. The table carries CLIENT NUMBERS and figures only; it
is not copied into the repo.

    python -m ils_review.peer_pull [--limit N] [--since yyyymm] [--ids 1544,1568]

Import-safe: nothing touches a share until `pull` is called.
"""
from __future__ import annotations

import csv
import glob
import io
import os
import re
import sys
import zipfile

import pandas as pd

ANALYSIS_ROOT = r"\\ilsdbsrvr2.csi.corp\ClientAnalysis\ILS Client Analysis"
# Each column read, lower-case name -> the name ils_data uses, so a peer's frame goes through the same
# validate_zaccounts as the client's own.
CANON = {"acctid": "acctid", "acctstatus": "acctstatus", "accttype": "accttype", "items365": "items365",
         "collectedfees365": "CollectedFees365", "pd_365": "PD_365", "chargeoff_amt_365": "Chargeoff_Amt_365",
         "chargeoff_account": "Chargeoff_Account", "refund_amt_365": "Refund_Amt_365", "canoverdraft": "CanOverdraft",
         "regeoptinvalue": "RegEOptinvalue"}
COLS = tuple(CANON)
FIELDS = ["client_id", "accttype", "as_of", "open_accounts", "items365", "fees365", "users365", "pd365", "fees365_all",
          "co365_all", "refund365_all", "eligible", "rege_y", "source"]
NEW_FIELDS = ("pd365", "fees365_all", "co365_all", "refund365_all", "eligible", "rege_y")


def peers_dir():
    import rpe_env
    d = os.path.join(str(rpe_env.build_artifacts()), "ils_analysis", "peers")
    os.makedirs(d, exist_ok=True)
    return d


def metrics_path():
    return os.path.join(peers_dir(), "ils_peer_metrics.csv")


def client_id_of(folder):
    m = re.search(r"(\d{4})\D*$", folder)
    return m.group(1) if m else None


def _pull_date(name):
    """yyyymmdd from a folder or file name: 20260305, 2026.03, 2026_03_05 or a US date such as 04292024; '' if none."""
    m = re.search(r"(20\d{2})[._-]?(\d{2})(?:[._-]?(\d{2}))?", name)
    if m and 1 <= int(m.group(2)) <= 12:
        return m.group(1) + m.group(2) + (m.group(3) if m.group(3) and 1 <= int(m.group(3)) <= 31 else "01")
    m = re.search(r"(\d{2})(\d{2})(20\d{2})", name)
    if m and 1 <= int(m.group(1)) <= 12:
        return m.group(3) + m.group(1) + m.group(2)
    return ""


def _candidates(client_dir):
    """Every DataPull folder and DataPull zip of a client with its date, newest first."""
    out = []
    for d in os.listdir(client_dir):
        full = os.path.join(client_dir, d)
        low = d.lower()
        if not ("datapull" in low or "data pull" in low):
            continue
        if os.path.isdir(full) or low.endswith(".zip"):
            out.append((_pull_date(d), full))
    out.sort(reverse=True)
    return out


def newest_zaccounts(client_dir):
    """(ref, yyyymmdd) of the newest ZAccounts extract in a client's DataPull folders or zips, or (None, why).
    `ref` is a file path, or 'archive.zip::member' for a csv inside a zip."""
    for stamp, full in _candidates(client_dir):
        if os.path.isdir(full):
            files = [f for f in os.listdir(full) if "zaccounts" in f.lower() and f.lower().endswith((".csv", ".zip", ".txt"))]
            if files:
                files.sort(key=lambda f: (_pull_date(f), f))
                f = files[-1]
                return os.path.join(full, f), (_pull_date(f) or stamp)
            for f in sorted(os.listdir(full), reverse=True):             # a DataPull zip inside the folder
                if f.lower().endswith(".zip") and "pull" in f.lower():
                    try:
                        with zipfile.ZipFile(os.path.join(full, f)) as z:
                            names = [n for n in z.namelist() if "zaccounts" in n.lower() and n.lower().endswith((".csv", ".txt"))]
                    except (OSError, zipfile.BadZipFile):
                        continue
                    if names:
                        return os.path.join(full, f) + "::" + sorted(names)[-1], (_pull_date(f) or stamp)
        else:
            try:
                with zipfile.ZipFile(full) as z:
                    names = [n for n in z.namelist() if "zaccounts" in n.lower() and n.lower().endswith((".csv", ".txt"))]
            except (OSError, zipfile.BadZipFile):
                continue
            if names:
                return full + "::" + sorted(names)[-1], stamp
    return None, "no ZAccounts extract in any DataPull folder or zip"


def _read(ref):
    """The COLS columns, read through pandas with usecols."""
    want = set(COLS)

    def use(c):
        return c.strip().lower() in want
    if "::" in ref:
        zp, member = ref.split("::", 1)
        with zipfile.ZipFile(zp) as z, z.open(member) as fh:
            return pd.read_csv(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"), usecols=use, low_memory=False)
    if ref.lower().endswith(".zip"):
        with zipfile.ZipFile(ref) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(name) as fh:
                return pd.read_csv(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"), usecols=use, low_memory=False)
    return pd.read_csv(ref, usecols=use, low_memory=False, encoding="utf-8", encoding_errors="replace")

def metrics_from_frame(df, validated=False):
    """{accttype: figures} from a ZAccounts frame: the ONE calculation used for the client and for every peer.

    Open accounts: open_accounts, items365, fees365, users365, pd365 (paid items), eligible (CanOverdraft), rege_y
    (Reg E opt-in 'Y'). All accounts of the type, because charged-off accounts are closed: fees365_all, co365_all and
    refund365_all. A figure the extract cannot give is None, never 0: refunds when Refund_Amt_365 is blank on every
    account, charge-offs when the frame trips the same charge-off guard as the client (r_common: more than half the
    accounts flagged, or more charged off than every fee collected), Reg E when no account is coded 'Y'."""
    from . import ils_data as D
    from . import r_common as RC
    df = df.rename(columns={c: CANON.get(c.strip().lower(), c.strip()) for c in df.columns})
    need = {"acctstatus", "accttype", "items365", "CollectedFees365"}
    if not need <= set(df.columns):
        raise ValueError("missing columns: " + ", ".join(sorted(need - set(df.columns))))
    if not validated:
        if "acctid" not in df.columns:
            df = df.assign(acctid=range(len(df)))
        df, _ = D.validate_zaccounts(df)
    num = lambda c: pd.to_numeric(df[c], errors="coerce") if c in df.columns else pd.Series(float("nan"), index=df.index)
    items, fees, pdn = num("items365").fillna(0), num("CollectedFees365").fillna(0.0), num("PD_365")
    co, refund = num("Chargeoff_Amt_365").abs(), num("Refund_Amt_365")
    co_ok = co.notna().any()
    if co_ok:
        flags = RC._yes(df["Chargeoff_Account"]).mean() if "Chargeoff_Account" in df.columns else 0.0
        tot_fees = float(fees.sum())
        if flags > 0.5 or (tot_fees and float(co.fillna(0).sum()) / tot_fees > RC.LOSS_RATE_LIMIT):
            co_ok = False
    is_open = df["acctstatus"].astype(str).str.upper().str.strip() == "O"
    elig = RC._yes(df["CanOverdraft"]) if "CanOverdraft" in df.columns else None
    rege = df["RegEOptinvalue"].astype(str).str.strip().str.upper() == "Y" if "RegEOptinvalue" in df.columns else None
    out = {}
    types = df["accttype"].astype(str).str.strip()
    for t in ("Personal", "Business"):
        a = types == t
        o = a & is_open
        if not a.any():
            continue
        fa = float(fees[a].sum())
        out[t] = {"open_accounts": int(o.sum()), "items365": float(items[o].sum()), "fees365": float(fees[o].sum()),
                  "users365": int((items[o] > 0).sum()),
                  "pd365": float(pdn[o].sum()) if pdn[o].notna().any() else None,
                  "fees365_all": fa,
                  "co365_all": float(co[a].fillna(0).sum()) if co_ok else None,
                  "refund365_all": float(refund[a].fillna(0).sum()) if refund[a].notna().any() else None,
                  "eligible": int((elig & o).sum()) if elig is not None else None,
                  "rege_y": int((rege & o).sum()) if rege is not None and bool((rege & a).any()) else None}
    return out


def metrics_files():
    """Every peer metrics table: the main one and any shard written by a parallel pull."""
    return sorted(glob.glob(os.path.join(peers_dir(), "ils_peer_metrics*.csv")))


def pull(ids=None, since="202509", limit=None, say=print, root=ANALYSIS_ROOT, shard=None):
    """Write/extend the peer metrics table. Existing rows for a client at the same as_of are kept (idempotent).
    `shard` = (k, n): this process takes every n-th client folder and writes ils_peer_metrics_k.csv, so several pulls can
    run side by side without writing one file."""
    path = metrics_path() if not shard else os.path.join(peers_dir(), f"ils_peer_metrics_{shard[0]}.csv")
    have = {}
    for f in metrics_files():
        for r in csv.DictReader(open(f, encoding="utf-8")):
            have[(r["client_id"], r["accttype"])] = r
    mine = {}
    if os.path.isfile(path):
        for r in csv.DictReader(open(path, encoding="utf-8")):
            mine[(r["client_id"], r["accttype"])] = r
    seq = -1
    n_done = 0
    for folder in sorted(os.listdir(root)):
        full = os.path.join(root, folder)
        cid = client_id_of(folder)
        if not cid or not os.path.isdir(full) or (ids and cid not in ids):
            continue
        seq += 1
        if shard and seq % shard[1] != shard[0]:
            continue
        try:
            zp, stamp = newest_zaccounts(full)
        except OSError as exc:
            say(f"{cid}: not listed ({exc})")
            continue
        if zp is None:
            say(f"{cid}: {stamp}")
            continue
        if since and stamp[:6] < since:
            say(f"{cid}: newest extract {stamp} is older than {since}; left out")
            continue
        if any(have.get((cid, t), {}).get("as_of") == stamp and all(f in have[(cid, t)] for f in NEW_FIELDS)
               for t in ("Personal", "Business")):
            continue                                   # a row from before NEW_FIELDS is read again
        try:
            m = metrics_from_frame(_read(zp))
        except Exception as exc:                       # a client's file that cannot be read is reported, never guessed
            say(f"{cid}: could not read {os.path.basename(zp)} ({type(exc).__name__}: {exc})")
            continue
        for t, v in m.items():
            row = {"client_id": cid, "accttype": t, "as_of": stamp,
                   "source": os.path.basename(zp.split("::")[0]) + ("::" + zp.split("::")[1] if "::" in zp else "")}
            for k, x in v.items():
                row[k] = "" if x is None else (round(x, 2) if isinstance(x, float) else x)   # blank, never 0, when unknown
            mine[(cid, t)] = have[(cid, t)] = row
        say(f"{cid}: {stamp} {', '.join(f'{t} {v['open_accounts']:,}' for t, v in m.items())}")
        n_done += 1
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, restval="", extrasaction="ignore")
            w.writeheader()
            for k in sorted(mine):
                w.writerow(mine[k])
        if limit and n_done >= limit:
            break
    return path


if __name__ == "__main__":
    import argparse
    HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--since", default="202509")
    ap.add_argument("--ids", default="")
    ap.add_argument("--shard", default="")
    a = ap.parse_args()
    sh = tuple(int(x) for x in a.shard.split("/")) if a.shard else None
    p = pull([i for i in a.ids.split(",") if i] or None, a.since, a.limit, say=lambda m: print(m, flush=True), shard=sh)
    print("wrote", p)
