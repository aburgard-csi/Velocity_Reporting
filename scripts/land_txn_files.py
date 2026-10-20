#!/usr/bin/env python3
"""
land_txn_files.py — collect the clients' monthly debit-card transaction files from each CSM's
ODDD folder on the share into `Inputs/Txn Files/<id>/`, one zip per file.

    python scripts/land_txn_files.py [--since 2026.09] [--client 1441 ...] [--workers 2] [--dry-run]

The data team ships a client's monthly transaction file INSIDE the ODD extract: `<id>_ODDD.zip`
in the CSM's month folder holds the ODD member (the `-ODD ... _V2_1_1.csv` every deck reads) and,
beside it, the transaction file — `..._monthlytran.csv`, `..._debit_card_trans-....txt`, a name
per core. A few land unzipped, as a `<id>_ODDD/` folder holding both files. James Gilmore asked
for them to be collected automatically (issue #23, 2026-10-19: "TXN files are currently being
delivered in the monthly ODDD zips per CSM"), and Aaron: "The zip files of debit card
transactions should be in the folders with each CSM's ODDD. Collect those and move them to the
reporting input folder" (2026-10-20).

Every member of an extract that is not an ODD member (`watch_sources._odd_members`, the readers'
own rule) is a transaction file. It lands as `Inputs/Txn Files/<id>/<member name>.zip`, one
member under its original name and timestamp — the form `zip_txn_files.py` keeps the folder in,
read back by `rpe_env.txn_files()` / `open_txn()`. The source is never changed: the CSM folders
are the data team's originals and the backup (CLAUDE.md), so this copies out and leaves the
extract whole. A file already on hand — the zip, or the raw file not yet zipped — is skipped; one
whose on-hand copy is a different size is reported and left alone, never overwritten.

Safe to re-run: it lands only what `Inputs/Txn Files/` lacks. Each landing is written as
`.zip.part`, verified (member size and CRC, decompressed CRC, and the share did not empty it on
close — four files did that on 2026-09-17) and renamed into place; smallest files first, so a run
cut short still lands most of the month. `--since` is the oldest month folder to read, by the
period `deck_status.odd_folder_period` reads from each CSM's folder names; the default is last
month, so the two newest months are covered the way the morning watch covers them.

Not part of the 08:00 watch: that task has a 50-minute limit and a month's transaction files run
to about 10 GB, hours over this share. Run it by hand or from its own task.
"""
import argparse
import json
import os
import re
import sys
import time
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "build"))
sys.path.insert(0, str(REPO / "scripts"))
import rpe_env as R                                              # noqa: E402
import deck_status as DS                                         # noqa: E402
from watch_sources import _odd_members                           # noqa: E402
from zip_txn_files import CHUNK, COMPRESSLEVEL, _check, txn_root  # noqa: E402

ODDD_ZIP_RX = re.compile(r"^(\d{3,5})_ODDD\.zip$", re.I)
ODDD_DIR_RX = re.compile(r"^(\d{3,5})_ODDD$", re.I)
LOG_NAME = "txn_landings.json"
# The data team's exports open with a banner line, pipe-separated:
#   1121|9/1/2026 12:04:44 PM|August 2026|658|Monthly Account Data - Master File|6.0.6.0
#   1403|10/1/2026 9:01:49 AM||12087|Monthly Transaction File|1.0.0.0
# The fifth field names the file. A member whose banner names something other than a
# transaction file (1121's September extract carried its DDA master file) is not landed here,
# and the reason says what it was. A file with no banner is what the folder rule says it is.
BANNER_RX = re.compile(r"^(\d{3,5})\|[^|]*\|[^|]*\|[^|]*\|([^|]+)\|")
BANNER_BYTES = 512


def banner_type(head: bytes) -> str | None:
    """The file type the export's banner names, or None when there is no banner."""
    line = head.decode("utf-8", "replace").split("\n", 1)[0].strip("\r")
    m = BANNER_RX.match(line)
    return m.group(2).strip() if m else None


def is_transaction(ftype) -> bool:
    """"Monthly Transaction File", "Monthly Transaction File -- ARS", "Monthly Tran File" (1555)
    are transaction files; "Monthly Account Data - Master File" is not; no banner, the folder
    rule stands."""
    if ftype is None:
        return True
    low = ftype.lower()
    return "tran" in low and "account data" not in low and "master" not in low


def default_since(today=None) -> str:
    """Last month as YYYY.MM: the two newest months, as the watch scans them."""
    t = today or date.today()
    y, m = (t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)
    return f"{y}.{m:02d}"


def sources(since, spec=None, clients=None) -> list:
    """Every transaction file on the share in month folders of `since` or later.

    A row per file: {"csm", "period", "client", "src" (the extract zip or the raw file),
    "member" (the name inside the zip, or None), "name", "size", "mtime", "crc" (the zip's
    stored CRC, or None)}. The ODD member(s) are left out; so are empty files and `.part`s.
    """
    rows = []
    for csm, root in DS.odd_roots(spec):
        try:
            folders = sorted(os.listdir(root))
        except OSError:
            continue                                            # off VPN: reported by the caller
        for d in folders:
            per = DS.odd_folder_period(d)
            p = os.path.join(root, d)
            if not per or per < since or not os.path.isdir(p):
                continue
            try:
                names = sorted(os.listdir(p))
            except OSError:
                continue
            for n in names:
                fp = os.path.join(p, n)
                mz, md = ODDD_ZIP_RX.match(n), ODDD_DIR_RX.match(n)
                if mz and os.path.isfile(fp):
                    cid = mz.group(1)
                    if clients and cid not in clients:
                        continue
                    try:
                        with zipfile.ZipFile(fp) as z:
                            infos = [i for i in z.infolist() if not i.is_dir()]
                    except (OSError, zipfile.BadZipFile) as e:
                        rows.append({"csm": csm, "period": per, "client": cid, "src": fp,
                                     "member": None, "name": n, "size": 0, "mtime": None,
                                     "crc": None, "error": f"cannot read the extract: {e}"})
                        continue
                    odd = set(_odd_members([i.filename for i in infos]))
                    for i in infos:
                        if i.filename in odd or i.file_size == 0:
                            continue
                        try:
                            with zipfile.ZipFile(fp) as z, z.open(i) as fh:
                                ftype = banner_type(fh.read(BANNER_BYTES))
                        except (OSError, zipfile.BadZipFile) as e:
                            rows.append({"csm": csm, "period": per, "client": cid, "src": fp,
                                         "member": i.filename, "name": os.path.basename(i.filename),
                                         "size": i.file_size, "mtime": None, "crc": None,
                                         "error": f"cannot read the member: {e}"})
                            continue
                        rows.append({"csm": csm, "period": per, "client": cid, "src": fp,
                                     "member": i.filename, "name": os.path.basename(i.filename),
                                     "size": i.file_size, "mtime": _zip_mtime(i), "crc": i.CRC,
                                     "ftype": ftype})
                elif md and os.path.isdir(fp):
                    cid = md.group(1)
                    if clients and cid not in clients:
                        continue
                    try:
                        inner = sorted(os.listdir(fp))
                    except OSError:
                        continue
                    odd = set(_odd_members(inner))
                    for f in inner:
                        q = os.path.join(fp, f)
                        if f in odd or f.endswith(".part") or not os.path.isfile(q):
                            continue
                        st = os.stat(q)
                        if st.st_size == 0:
                            continue
                        try:
                            with open(q, "rb") as fh:
                                ftype = banner_type(fh.read(BANNER_BYTES))
                        except OSError as e:
                            rows.append({"csm": csm, "period": per, "client": cid, "src": q,
                                         "member": None, "name": f, "size": st.st_size,
                                         "mtime": None, "crc": None,
                                         "error": f"cannot read the file: {e}"})
                            continue
                        rows.append({"csm": csm, "period": per, "client": cid, "src": q,
                                     "member": None, "name": f, "size": st.st_size,
                                     "mtime": st.st_mtime, "crc": None, "ftype": ftype})
    return rows


def _zip_mtime(info):
    try:
        return datetime(*info.date_time).timestamp()
    except (ValueError, OverflowError):
        return None


def on_hand(row, root) -> str | None:
    """Why this file need not land: "on hand" (zip or raw present, same size), "differs"
    (present at another size — left alone, reported), or None when it is wanted."""
    d = Path(root) / row["client"]
    z, raw = d / (row["name"] + ".zip"), d / row["name"]
    if raw.is_file() and raw.stat().st_size > 0:
        return "on hand" if raw.stat().st_size == row["size"] else "differs"
    if z.is_file():
        try:
            with zipfile.ZipFile(z) as zf:
                infos = [i for i in zf.infolist() if not i.is_dir()]
        except (OSError, zipfile.BadZipFile):
            return "differs"
        if len(infos) == 1 and infos[0].file_size == row["size"]:
            return "on hand"
        return "differs"
    return None


def plan(rows, root) -> tuple:
    """(wanted, skipped): the rows to land, smallest first, and [(row, why)] for the rest.
    The same file in two CSMs' folders (a handover) is planned once."""
    wanted, skipped, seen = [], [], set()
    for row in sorted(rows, key=lambda r: (r["size"], r["client"], r["name"])):
        if row.get("error"):
            skipped.append((row, row["error"]))
            continue
        key = (row["client"], row["name"])
        if key in seen:
            skipped.append((row, "same file already planned"))
            continue
        if not is_transaction(row.get("ftype")):
            skipped.append((row, f"not a transaction file: {row['ftype']}"))
            continue
        why = on_hand(row, root)
        if why:
            skipped.append((row, why))
            continue
        seen.add(key)
        wanted.append(row)
    return wanted, skipped


def _open_source(row):
    if row["member"] is None:
        return open(row["src"], "rb"), None
    z = zipfile.ZipFile(row["src"])
    return z.open(row["member"]), z


def _land_raw(row, target: Path, part: Path, crc: int) -> None:
    """Land the file unzipped, through a `.part`, checked against `crc` and the source size."""
    got, size = 0, 0
    src, holder = _open_source(row)
    try:
        with open(part, "wb") as fp:
            while True:
                b = src.read(CHUNK)
                if not b:
                    break
                got = zlib.crc32(b, got)
                size += len(b)
                fp.write(b)
            fp.flush()
            os.fsync(fp.fileno())
    finally:
        src.close()
        if holder is not None:
            holder.close()
    if size != row["size"] or got != crc:
        part.unlink()
        raise ValueError(f"the raw copy read back as {size:,} bytes CRC {got:08x}, "
                         f"expected {row['size']:,} bytes CRC {crc:08x}")
    if os.path.getsize(part) != size:
        part.unlink()
        raise OSError(f"the share discarded the raw file too: {size:,} bytes written, "
                      f"{os.path.getsize(part):,} on close")
    os.replace(part, target)
    if row["mtime"]:
        os.utime(target, (row["mtime"], row["mtime"]))


def land_one(row, root) -> dict:
    """Land one transaction file as `<root>/<client>/<name>.zip`; verify; return a result row."""
    d = Path(root) / row["client"]
    target, part = d / (row["name"] + ".zip"), d / (row["name"] + ".zip.part")
    res = dict(row, zip_size=None, status=None, error=None)
    try:
        d.mkdir(parents=True, exist_ok=True)
        if part.exists():
            part.unlink()
        info = zipfile.ZipInfo(row["name"])
        if row["mtime"]:
            info.date_time = datetime.fromtimestamp(row["mtime"]).timetuple()[:6]
        info.compress_type = zipfile.ZIP_DEFLATED
        crc, size = 0, 0
        src, holder = _open_source(row)
        try:
            with open(part, "wb") as fp:
                with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED, compresslevel=COMPRESSLEVEL) as z, \
                        z.open(info, "w") as dst:
                    while True:
                        b = src.read(CHUNK)
                        if not b:
                            break
                        crc = zlib.crc32(b, crc)
                        size += len(b)
                        dst.write(b)
                fp.flush()
                os.fsync(fp.fileno())
                written = os.fstat(fp.fileno()).st_size
        finally:
            src.close()
            if holder is not None:
                holder.close()
        if size != row["size"]:
            raise ValueError(f"read {size:,} bytes from the source, expected {row['size']:,}")
        if row["crc"] is not None and crc != row["crc"]:
            raise ValueError(f"the source member read back as CRC {crc:08x}, "
                             f"its extract says {row['crc']:08x}")
        if os.path.getsize(part) == 0 < written:
            # The share's security agent empties a zip of some clients' transaction files the
            # moment it is closed (four of 404 on 2026-09-17; 1815 again on 2026-10-20). Those
            # files are kept raw — rpe_env.txn_files() / open_txn() read either form.
            part.unlink()
            _land_raw(row, d / row["name"], d / (row["name"] + ".part"), crc)
            res["zip_size"] = (d / row["name"]).stat().st_size
            res["status"] = "landed raw"
            res["error"] = "the share discards this file zipped; kept raw"
            return res
        _check(part, row["name"], row["size"], crc)
        os.replace(part, target)
        if row["mtime"]:
            os.utime(target, (row["mtime"], row["mtime"]))
        res["zip_size"] = target.stat().st_size
        res["status"] = "landed"
    except Exception as e:                                      # noqa: BLE001 — reported per file
        res["status"] = "FAILED"
        res["error"] = f"{type(e).__name__}: {e}"
        try:
            part.unlink()
        except OSError:
            pass
    return res


def _mb(n):
    return f"{n / 1_048_576:,.1f} MB"


def _record(results, log_path):
    """Append the landings to the run log (bookkeeping, in Build Artifacts)."""
    try:
        old = json.load(open(log_path, encoding="utf-8")) if os.path.exists(log_path) else []
    except (OSError, ValueError):
        old = []
    when = datetime.now().isoformat(timespec="seconds")
    for r in results:
        old.append({"when": when, "csm": r["csm"], "period": r["period"], "client": r["client"],
                    "name": r["name"], "size": r["size"], "zip_size": r["zip_size"],
                    "source": r["src"], "status": r["status"], "error": r["error"]})
    tmp = log_path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(old, fh, indent=1)
    os.replace(tmp, log_path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--since", help="oldest month folder to read, YYYY.MM (default: last month)")
    ap.add_argument("--client", action="append", help="client id; repeat for several (default: all)")
    ap.add_argument("--workers", type=int, default=2, help="files landed at once (default 2: the share is the limit)")
    ap.add_argument("--root", help="the Txn Files folder (default: Inputs/Txn Files under RPE_DATA_ROOT)")
    ap.add_argument("--source", help="CSM ODDD folders, as RPE_SRC_ODDD (default: deck_status.SRC_ODDD)")
    ap.add_argument("--log", help="run log (default: Build Artifacts/txn_landings.json)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    since = a.since or default_since()
    root = Path(a.root) if a.root else txn_root()
    roots = DS.odd_roots(a.source)
    down = [c for c, p in roots if not DS._reachable(p)]
    if down:
        print("unreachable (off VPN?): " + ", ".join(down), flush=True)
        if len(down) == len(roots):
            return 2
    rows = sources(since, a.source, set(a.client) if a.client else None)
    wanted, skipped = plan(rows, root)
    kinds = {}
    for _, why in skipped:
        kinds[why] = kinds.get(why, 0) + 1
    total = sum(r["size"] for r in wanted)
    print(f"{len(rows)} transaction files on the share since {since}; {len(wanted)} to land "
          f"({_mb(total)}) into {root}; skipped: "
          + (", ".join(f"{n} {k}" for k, n in sorted(kinds.items())) or "none"), flush=True)
    for row, why in skipped:
        if why not in ("on hand", "same file already planned"):
            print(f"  {why}: {row['client']} {row['name']} ({row['csm']}, {row['period']})")
    if a.dry_run or not wanted:
        for r in wanted:
            print(f"  {r['client']}/{r['name']}  {_mb(r['size'])}  ({r['csm']}, {r['period']})")
        return 0

    t0 = time.time()
    results, done_in, done_out, failed = [], 0, 0, 0
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        futs = [ex.submit(land_one, r, root) for r in wanted]
        for n, f in enumerate(as_completed(futs), 1):
            r = f.result()
            results.append(r)
            if r["status"] == "FAILED":
                failed += 1
                print(f"[{n}/{len(wanted)}] FAILED {r['client']}/{r['name']}: {r['error']}", flush=True)
                continue
            done_in += r["size"]
            done_out += r["zip_size"]
            note = f"  ({r['error']})" if r["error"] else ""
            print(f"[{n}/{len(wanted)}] {r['status']} {r['client']}/{r['name']}  "
                  f"{_mb(r['size'])} -> {_mb(r['zip_size'])}{note}", flush=True)
    log = a.log or str(R.build_artifacts() / LOG_NAME)
    _record(results, log)
    mins = (time.time() - t0) / 60
    print(f"\nLanded {len(results) - failed} files, {_mb(done_in)} as {_mb(done_out)}, "
          f"in {mins:.1f} min; {failed} failed. Log: {log}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
