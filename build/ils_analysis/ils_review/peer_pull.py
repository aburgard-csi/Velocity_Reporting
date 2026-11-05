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
COLS = ("acctid", "acctstatus", "accttype", "items365", "collectedfees365")


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
    """The four columns, read through pandas with usecols."""
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

def metrics_from_frame(df):
    """{accttype: {open_accounts, items365, fees365, users365}} from a ZAccounts frame."""
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    if not {"acctstatus", "accttype", "items365", "collectedfees365"} <= set(df.columns):
        raise ValueError("missing columns: " + ", ".join(sorted({"acctstatus", "accttype", "items365", "collectedfees365"} - set(df.columns))))
    df = df[df["acctstatus"].astype(str).str.upper().str.strip() == "O"].copy()
    df["items365"] = pd.to_numeric(df["items365"], errors="coerce").fillna(0)
    df["collectedfees365"] = pd.to_numeric(df["collectedfees365"], errors="coerce").fillna(0.0)
    out = {}
    for t, g in df.groupby(df["accttype"].astype(str).str.strip()):
        if t not in ("Personal", "Business"):
            continue
        out[t] = {"open_accounts": int(len(g)), "items365": float(g["items365"].sum()), "fees365": float(g["collectedfees365"].sum()),
                  "users365": int((g["items365"] > 0).sum())}
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
        if any(have.get((cid, t), {}).get("as_of") == stamp for t in ("Personal", "Business")):
            continue
        try:
            m = metrics_from_frame(_read(zp))
        except Exception as exc:                       # a client's file that cannot be read is reported, never guessed
            say(f"{cid}: could not read {os.path.basename(zp)} ({type(exc).__name__}: {exc})")
            continue
        for t, v in m.items():
            mine[(cid, t)] = have[(cid, t)] = {"client_id": cid, "accttype": t, "as_of": stamp, "open_accounts": v["open_accounts"], "items365": round(v["items365"], 1),
                              "fees365": round(v["fees365"], 2), "users365": v["users365"], "source": os.path.basename(zp.split("::")[0]) + ("::" + zp.split("::")[1] if "::" in zp else "")}
        say(f"{cid}: {stamp} {', '.join(f'{t} {v['open_accounts']:,}' for t, v in m.items())}")
        n_done += 1
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["client_id", "accttype", "as_of", "open_accounts", "items365", "fees365", "users365", "source"])
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
