#!/usr/bin/env python3
"""
zip_txn_files.py — store the clients' transaction files zipped, one .zip per file.

    python scripts/zip_txn_files.py [--client 1441 ...] [--workers 4] [--dry-run]

`Inputs/Txn Files/<id>/` holds each client's monthly debit-card transaction files, raw text of
10 MB to 830 MB apiece and about 48 GB in all (2026-09-17). Over the share, reading the raw
text is the slow part, and the text compresses to a fraction of its size, so the files are
kept zipped (Aaron, 2026-09-17). Readers go through `rpe_env.txn_files()` /
`rpe_env.open_txn()`, which take either form.

Each file becomes `<original name>.zip` beside it, holding one member under the original name
with its original timestamp. The original is deleted only after the zip checks out: it is
written as `.zip.part` and renamed, its member's size and CRC match what was read from the
original, the member decompresses to that CRC, and the original was not modified while it was
being read. If the mount refuses the delete, the original is left in place and reported.

Safe to re-run: a file already zipped is skipped, and a zip left beside its original by an
interrupted run is checked and finished rather than written again. Anything under
`rpe_env.TXN_SKIP_DIRS` (analysis output) and empty files are left alone.
"""
import argparse
import os
import sys
import time
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "build"))
import rpe_env as R                                              # noqa: E402

CHUNK = 16 * 1024 * 1024
COMPRESSLEVEL = 6


def txn_root() -> Path:
    return R.inputs() / R.INPUT_KIND_DIRS["Txn"]


def plan(root, clients=None) -> list:
    """The raw transaction files under `root` still to be zipped."""
    root = Path(root)
    out = []
    for p in R.txn_files(root=root):
        if clients and p.relative_to(root).parts[0] not in clients:
            continue
        if p.suffix.lower() != ".zip":
            out.append(p)
            continue
        # txn_files lists a file with its zip beside it as the zip: an interrupted run,
        # whose zip still has to be checked and original removed.
        orig = p.with_name(p.name[:-4])
        if orig.is_file() and orig.stat().st_size > 0:
            out.append(orig)
    return out


def _check(zip_path: Path, name: str, size: int, crc: int) -> None:
    """Raise unless the zip holds exactly `name`, `size` bytes, decompressing to `crc`."""
    with zipfile.ZipFile(zip_path) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) != 1 or infos[0].filename != name:
            raise ValueError(f"expected one member {name!r}, found {[i.filename for i in infos]}")
        info = infos[0]
        if info.file_size != size or info.CRC != crc:
            raise ValueError(f"member is {info.file_size:,} bytes CRC {info.CRC:08x}; "
                             f"original is {size:,} bytes CRC {crc:08x}")
        got = 0
        with z.open(info) as fh:                 # a CRC mismatch raises BadZipFile at EOF
            while True:
                b = fh.read(CHUNK)
                if not b:
                    break
                got = zlib.crc32(b, got)
        if got != crc:
            raise ValueError(f"member decompresses to CRC {got:08x}, expected {crc:08x}")


def _crc_of(path: Path) -> int:
    crc = 0
    with open(path, "rb") as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                return crc
            crc = zlib.crc32(b, crc)


def zip_one(path) -> dict:
    """Zip one file beside itself, verify, and remove the original. Returns a result row."""
    path = Path(path)
    st = path.stat()
    target = path.with_name(path.name + ".zip")
    part = path.with_name(path.name + ".zip.part")
    row = {"file": str(path), "size": st.st_size, "zip_size": None, "status": None, "error": None}
    try:
        if target.is_file():
            crc = _crc_of(path)
            _check(target, path.name, st.st_size, crc)          # an interrupted run's zip
        else:
            info = zipfile.ZipInfo.from_file(path, arcname=path.name)
            info.compress_type = zipfile.ZIP_DEFLATED
            crc = 0
            with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, compresslevel=COMPRESSLEVEL) as z, \
                    open(path, "rb") as src, z.open(info, "w") as dst:
                while True:
                    b = src.read(CHUNK)
                    if not b:
                        break
                    crc = zlib.crc32(b, crc)
                    dst.write(b)
            _check(part, path.name, st.st_size, crc)
            os.replace(part, target)
            os.utime(target, (st.st_atime, st.st_mtime))
        now = path.stat()
        if (now.st_size, now.st_mtime) != (st.st_size, st.st_mtime):
            raise ValueError("the original changed while it was being zipped; it was kept")
        row["zip_size"] = target.stat().st_size
        try:
            os.remove(path)
            row["status"] = "zipped"
        except OSError as e:
            row["status"] = "zipped, original kept"
            row["error"] = f"could not delete the original: {e}"
    except Exception as e:                                      # noqa: BLE001 — reported per file
        row["status"] = "FAILED"
        row["error"] = f"{type(e).__name__}: {e}"
        try:
            part.unlink()
        except OSError:
            pass
    return row


def _mb(n):
    return f"{n / 1_048_576:,.1f} MB"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--client", action="append", help="client id; repeat for several (default: all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--root", help="the Txn Files folder (default: Inputs/Txn Files under RPE_DATA_ROOT)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    root = Path(a.root) if a.root else txn_root()
    todo = plan(root, set(a.client) if a.client else None)
    total = sum(p.stat().st_size for p in todo)
    print(f"{len(todo)} transaction files to zip under {root}, {_mb(total)}", flush=True)
    if a.dry_run:
        for p in todo:
            print(f"  {p.relative_to(root)}  {_mb(p.stat().st_size)}")
        return 0

    t0 = time.time()
    done_in = done_out = 0
    failed = kept = 0
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        futs = [ex.submit(zip_one, p) for p in todo]
        for n, f in enumerate(as_completed(futs), 1):
            r = f.result()
            rel = Path(r["file"]).relative_to(root)
            if r["status"] == "FAILED":
                failed += 1
                print(f"[{n}/{len(todo)}] FAILED {rel}: {r['error']}", flush=True)
                continue
            kept += r["status"] != "zipped"
            done_in += r["size"]
            done_out += r["zip_size"]
            note = f" ({r['error']})" if r["error"] else ""
            print(f"[{n}/{len(todo)}] {r['status']} {rel}  {_mb(r['size'])} -> {_mb(r['zip_size'])}{note}",
                  flush=True)

    mins = (time.time() - t0) / 60
    ratio = f", {done_out / done_in:.0%} of the original" if done_in else ""
    print(f"\nZipped {_mb(done_in)} to {_mb(done_out)}{ratio} in {mins:.1f} min. "
          f"{failed} failed, {kept} originals could not be deleted.")
    return 1 if failed or kept else 0


if __name__ == "__main__":
    sys.exit(main())
