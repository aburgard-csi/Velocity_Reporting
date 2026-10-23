"""
deposits_input.py — the client's deposits extract, where v5's deposits loader can read it.

`Inputs/Deposits/<id>_<Client>_ILSDeposits_<yyyy.mm>.zip`: one CSV per zip, rolling 365 days,
`hashed_account, deposit_date, deposit_amount` (the hashed account is what the ODD's Acct Number
carries). v5's loader (`ti/core/deposits/load.py`, unchanged) maps those headers and caches the
parsed rows as parquet keyed on the file's name, modified time and size.

A client only ever gets ITS OWN file: the file name must start with the client id as a whole
number. v5 at a491b5c had no such rule, and its 2026-09 run for 1776 read 1100 Rally's file and
joined 0% (the v5 fix came later the same day). The newest of the client's files wins.

As with the transaction files, the CSV is copied out of its zip ONCE into the local cache
(`ti_cache/deposits_raw/<id>/`, dated from the zip entry) so v5's cache key is stable between
builds and the share is read once per new file.
"""
import os
import re
import shutil
import time
import zipfile
from pathlib import Path

from ti.core import deposits as D
from ti.txn_stage import cache_root


def own_files(client_id):
    """The client's own deposits files in Inputs/Deposits, oldest first."""
    import rpe_env
    folder = rpe_env.input_dir("Deposits", create=False)
    if not folder.is_dir():
        return []
    own = re.compile(rf"^{re.escape(str(client_id))}(?!\d)")
    return sorted((p for p in folder.iterdir() if p.is_file() and own.match(p.name)
                   and p.suffix.lower() in (".zip", ".csv", ".txt", ".tsv")),
                  key=lambda p: (p.stat().st_mtime, p.name))


def stage(path: Path, client_id) -> Path:
    """The file's CSV in the local cache: copied once, dated from the zip entry."""
    if path.suffix.lower() != ".zip":
        return path
    target = cache_root() / "deposits_raw" / str(client_id)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        info = next((i for i in z.infolist() if not i.is_dir()
                     and i.filename.lower().endswith((".csv", ".txt", ".tsv"))), None)
        if info is None:
            raise ValueError(f"{path.name} holds no .csv / .txt member")
        dest = target / Path(info.filename).name
        stamp = time.mktime(info.date_time + (0, 0, -1))
        if not (dest.is_file() and dest.stat().st_size == info.file_size
                and int(dest.stat().st_mtime) == int(stamp)):
            part = dest.with_name(dest.name + ".part")
            with z.open(info) as src, open(part, "wb") as fh:
                shutil.copyfileobj(src, fh, 1 << 20)
            os.utime(part, (stamp, stamp))
            os.replace(part, dest)
    for old in target.iterdir():
        if old.is_file() and old != dest:
            old.unlink()
    return dest


def attach(config: dict, client_id, warn) -> dict:
    """The config with v5's deposit inputs added (`_deposit_raw`, `_deposit_cadence`,
    `_deposit_monthly`), as v5's run adds them; unchanged, with the reason stated, when the client
    has no file or the file parses to nothing."""
    files = own_files(client_id)
    if not files:
        warn(f"deposits: no file for client {client_id} in Inputs/Deposits. The deposit behaviour "
             f"chapter and the 'Deposits slowing' stressor are not built for this client.")
        return config
    src = files[-1]
    report = D.LoadReport()
    raw = D.load(stage(src, client_id), cache_root() / "deposits_parquet" / str(client_id), report)
    for message in report.warnings:
        warn(f"deposits: {message}")
    if not len(raw):
        warn(f"deposits: {src.name} was found but parsed to 0 rows -- headers did not map, or every "
             f"row failed date/amount parsing. Deposit conditions are NOT built; they would otherwise "
             f"flag the entire book.")
        return config
    return dict(config, _deposit_raw=raw, _deposit_cadence=D.cadence(raw),
                _deposit_monthly=D.monthly(raw), _deposit_source=src.name,
                _deposit_shape=f"{report.rows:,} rows, {report.accounts:,} accounts, {report.months} months")
