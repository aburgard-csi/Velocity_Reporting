"""
txn_stage.py — the client's transaction files, where v5's loader can read them.

RPE keeps each monthly transaction file zipped, one per zip, in `Inputs/Txn Files/<id>/` on the
share (a few the share refuses to hold zipped sit there raw; `rpe_env.txn_files` lists both). v5's
loader (`ti/transaction_intelligence/loader.py`, unchanged) reads plain files from a folder and
caches each as parquet keyed on the file's name, modified time and size.

So the files inside the window are copied out ONCE into a local staging folder, each given the
zip entry's own date as its modified time. The cache keys are then the same on every build: the
share (about 3 MB/s) is read once per new file, and every later build reads the local parquet.
Files that fall out of the window are removed from staging; the share copy is never touched.

The staging and cache root is `TI_CACHE_DIR`, else `%LOCALAPPDATA%/RPE/ti_cache` (the folder
the launcher already unpacks into), else `~/.rpe/ti_cache`. It is a CACHE kept between builds,
not build scratch, so it is never in the temp folder (tests/test_temp_cleanup.py).
"""
import os
import shutil
import time
import zipfile
from pathlib import Path

from ti.transaction_intelligence import loader


def cache_root() -> Path:
    if os.environ.get("TI_CACHE_DIR"):
        return Path(os.environ["TI_CACHE_DIR"])
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "RPE" / "ti_cache" if base else Path.home() / ".rpe" / "ti_cache"


def staged_dir(client_id) -> Path:
    return cache_root() / "txn_raw" / str(client_id)


def parquet_dir(client_id) -> Path:
    return cache_root() / "txn_parquet" / str(client_id)


def _is_txn_name(name: str) -> bool:
    """v5's own file rule (loader.discover): a .txt / .csv named like a transaction file."""
    p = Path(name)
    return (p.suffix.lower() in (".txt", ".csv") and bool(loader.TXN_NAME_RE.search(p.name))
            and not loader.NOT_TXN_RE.search(p.name) and not p.name.startswith("~$"))


def in_window(name: str, months: int, anchor) -> bool:
    """v5's window (loader.discover): a file dated in month M carries month M-1's data."""
    d = loader.file_date(Path(name))
    if d is None:
        return False
    if anchor is None:
        return True
    hi = anchor.year * 12 + anchor.month
    return hi - (months - 1) <= d.year * 12 + d.month - 1 <= hi


def _sources(client_id):
    """[(original file name, size, mtime epoch, opener)] for the client's files on hand."""
    import rpe_env
    out = []
    for p in rpe_env.txn_files(client_id):
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    stamp = time.mktime(info.date_time + (0, 0, -1))
                    out.append((Path(info.filename).name, info.file_size, stamp,
                                lambda p=p, n=info.filename: zipfile.ZipFile(p).open(n)))
        else:
            st = p.stat()
            out.append((p.name, st.st_size, st.st_mtime, lambda p=p: open(p, "rb")))
    return out


def stage(client_id, months: int = 12, anchor=None, log=print) -> Path:
    """The staging folder for the client, holding exactly the window's transaction files."""
    target = staged_dir(client_id)
    target.mkdir(parents=True, exist_ok=True)
    keep = set()
    for name, size, stamp, opener in _sources(client_id):
        if not (_is_txn_name(name) and in_window(name, months, anchor)):
            continue
        keep.add(name)
        dest = target / name
        if dest.is_file() and dest.stat().st_size == size and int(dest.stat().st_mtime) == int(stamp):
            continue
        part = dest.with_name(dest.name + ".part")
        with opener() as src, open(part, "wb") as fh:
            shutil.copyfileobj(src, fh, 1 << 20)
        os.utime(part, (stamp, stamp))
        os.replace(part, dest)
        log(f"staged {name} ({size / 1e6:,.0f} MB)")
    for old in target.iterdir():
        if old.is_file() and old.name not in keep:
            old.unlink()
    return target


def load(client_id, months: int = 12, anchor=None, log=print):
    """(frame, LoadReport) for the client's window, through v5's loader and its parquet cache."""
    folder = stage(client_id, months, anchor, log)
    return loader.load(folder, parquet_dir(client_id), months=months, anchor=anchor)
