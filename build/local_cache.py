#!/usr/bin/env python3
"""local_cache.py — keeps Sheila's local caches from filling the disk.

Aaron, 2026-11-03: "my harddrive is nearly full. make sure sheila cleans up after herself." The one thing Sheila keeps
on the PC between builds is the Transaction Intelligence cache, `%LOCALAPPDATA%/RPE/ti_cache`: each client's transaction
files copied out of their zips once (`txn_raw/<id>`) and parsed once (`txn_parquet/<id>`), so the share, at about 3 MB/s,
is read once per new file. Nothing ever removed a client from it, so it grew by a client's worth every time a different
client was built (5.6 GB across three clients when it was noticed). Everything in it is rebuilt from `Inputs/Txn Files`
on the share, so it is safe to lose; losing it costs the next build for that client a re-read.

`trim_ti_cache` keeps it inside two limits, evicting a client at a time, least recently used first:

    MAX_AGE_DAYS  a client not built for this long goes, whatever the size
    MAX_GB        the whole cache stays under this, never counting the client being built

Override with TI_CACHE_MAX_GB and TI_CACHE_MAX_AGE_DAYS. It runs when Sheila starts, at the start of every Transaction
Intelligence stage (`ti/txn_stage.stage`), and by hand with `python scripts/ars_launcher_web.py --tidy`.

Import-safe and light: nothing here imports pandas or the TI package.
"""
import os
import shutil
import time
from pathlib import Path

MAX_GB = 3.0
MAX_AGE_DAYS = 21
SUBDIRS = ("txn_raw", "txn_parquet", "deposits_raw", "deposits_parquet")
USED = "used"                       # one tiny stamp file per client, touched whenever its files are staged


def ti_cache_root() -> Path:
    if os.environ.get("TI_CACHE_DIR"):
        return Path(os.environ["TI_CACHE_DIR"])
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "RPE" / "ti_cache" if base else Path.home() / ".rpe" / "ti_cache"


def _num(name, default):
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _tree(path: Path):
    """(bytes, newest modified time) of every file under `path`."""
    size, newest = 0, 0.0
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            try:
                st = os.stat(os.path.join(dp, f))
            except OSError:
                continue
            size += st.st_size
            newest = max(newest, st.st_mtime)
    return size, newest


def touch(client_id, root=None, now=None):
    """Record that this client's cache was just used (its stamp file's modified time is the 'last used')."""
    root = Path(root) if root else ti_cache_root()
    d = root / USED
    d.mkdir(parents=True, exist_ok=True)
    p = d / str(client_id)
    p.write_text("")
    t = now if now is not None else time.time()
    os.utime(p, (t, t))


def clients(root=None):
    """{client id: {"bytes", "last_used"}} for every client with files in the cache."""
    root = Path(root) if root else ti_cache_root()
    out = {}
    for sub in SUBDIRS:
        base = root / sub
        if not base.is_dir():
            continue
        for d in base.iterdir():
            if not d.is_dir():
                continue
            size, newest = _tree(d)
            ent = out.setdefault(d.name, {"bytes": 0, "last_used": 0.0})
            ent["bytes"] += size
            ent["last_used"] = max(ent["last_used"], newest)
    for cid, ent in out.items():
        stamp = root / USED / cid
        if stamp.is_file():
            ent["last_used"] = max(ent["last_used"], stamp.stat().st_mtime)
    return out


def _remove(root: Path, cid: str):
    freed = 0
    for sub in SUBDIRS:
        d = root / sub / cid
        if d.is_dir():
            freed += _tree(d)[0]
            shutil.rmtree(d, ignore_errors=True)
    try:
        (root / USED / cid).unlink()
    except OSError:
        pass
    return freed


def trim_ti_cache(keep=None, max_gb=None, max_age_days=None, root=None, now=None, log=None):
    """Evict clients from the cache until it is inside both limits. `keep` (the client being built) is never evicted.
    Returns {"removed": [client ids], "freed": bytes, "left": bytes}."""
    root = Path(root) if root else ti_cache_root()
    max_bytes = (max_gb if max_gb is not None else _num("TI_CACHE_MAX_GB", MAX_GB)) * 1e9
    max_age = (max_age_days if max_age_days is not None else _num("TI_CACHE_MAX_AGE_DAYS", MAX_AGE_DAYS)) * 86400
    now = now if now is not None else time.time()
    keep = str(keep) if keep is not None else None
    have = clients(root)
    removed, freed = [], 0
    for cid in sorted(have, key=lambda c: have[c]["last_used"]):              # least recently used first
        if cid == keep:
            continue
        total = sum(e["bytes"] for c, e in have.items() if c not in removed)
        too_old = now - have[cid]["last_used"] > max_age or not have[cid]["bytes"]       # an empty folder is leftover too
        if too_old or total > max_bytes:
            freed += _remove(root, cid)
            removed.append(cid)
            if log:
                why = ("empty" if not have[cid]["bytes"] else
                       f"not used for {int((now - have[cid]['last_used']) // 86400)} days" if too_old else "over the size limit")
                log(f"cleared the Transaction Intelligence cache for {cid} ({have[cid]['bytes'] / 1e9:.1f} GB, {why})")
    return {"removed": removed, "freed": freed, "left": sum(e["bytes"] for c, e in have.items() if c not in removed)}
