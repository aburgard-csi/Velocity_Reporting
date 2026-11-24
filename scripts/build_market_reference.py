"""Build the FDIC / NCUA market reference store and put it in `Inputs/Market Reference` (Aaron, 2026-11-23).

The Transaction Intelligence competition-layers slides match every bank and credit union in a card file
against this store (`ti/txn_sections.competition_layers`). With no store they are skipped and the build
log says "the FDIC / NCUA reference store is not available", and since #181 the older Competition slides
they replaced are tossed, so the chapter comes out thin. The fetchers in `ti/core/market/sources.py`
existed, but nothing called them all: this is that call.

    python scripts/build_market_reference.py            # fetch, verify, land on the share
    python scripts/build_market_reference.py --check    # only check what is on the share

It holds public data only (FDIC institutions, branches and call reports; NCUA call-report tables; Census
ZIP centroids), no client data. It needs the internet for the fetch and the VPN for the share.

How it lands, so a cut-short run never leaves a half store on the share:
- every source is fetched into a local scratch folder first, and checked there: each file present, each
  above its row floor (`sources.MIN_ROWS`), and the whole store loaded as the builds load it (`load_book`);
- only then is each file copied to the share through a `.part` file, renamed over the old one and its
  size checked. Nothing else in the folder is touched or deleted.
`vintages.json` beside the files records the NCUA quarter, the Census year and each file's row count.

Refresh it each quarter, when NCUA publishes a new call-report quarter (`--quarter yyyy-mm`).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO / "build", REPO / "build" / "ars_pipeline"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ti.core.filed.join import REQUIRED_CACHE, require_cache   # noqa: E402
from ti.core.market import institutions, sources                 # noqa: E402

VINTAGES = "vintages.json"


def destination() -> Path:
    """Where the builds read the store: `TI_REFERENCE_DIR`, else `Inputs/Market Reference`."""
    from ti.txn_sections import reference_dir
    return Path(reference_dir())


def fetch(work: Path, quarter: str, year: str, since: str) -> None:
    """Every source, fresh, into `work`. Raises sources.SourceError on a failed or short download."""
    steps = (
        ("FDIC institutions", lambda: sources.fdic_institutions(work, refresh=True)),
        ("FDIC branch locations", lambda: sources.fdic_locations(work, refresh=True)),
        (f"FDIC call reports since {since}", lambda: sources.fdic_financials(work, refresh=True, since=since)),
        (f"NCUA call report {quarter}", lambda: sources.ncua(work, quarter=quarter, refresh=True)),
        (f"Census ZIP centroids {year}", lambda: sources.zip_centroids(work, year=year, refresh=True)),
    )
    for label, step in steps:
        t = time.perf_counter()
        print(f"  fetching {label} ...", flush=True)
        step()
        print(f"    done in {time.perf_counter() - t:,.0f} s", flush=True)


def check(folder: Path, quarter: str, year: str) -> dict:
    """The store in `folder` as the builds would read it: every file, every floor, the book loaded."""
    require_cache(folder)
    counts = {}
    for name in REQUIRED_CACHE:
        rows = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
        floor = sources.MIN_ROWS.get(name)
        if floor and len(rows) < floor:
            raise sources.SourceError(f"{name}: {len(rows):,} rows, expected at least {floor:,}")
        counts[name] = len(rows)
    book = institutions.load_book(folder, quarter=quarter, gazetteer_year=year)
    return {"row_counts": counts, "institutions": len(book.institutions), "branches": len(book.branches),
            "unplaced_branches": len(book.unplaced)}


def land(work: Path, dest: Path, names: list[str]) -> None:
    """Copy each file to `dest` through a .part and a rename, checking its size. Never deletes."""
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        src, tgt = work / name, dest / name
        part = tgt.with_name(tgt.name + ".part")
        shutil.copyfile(src, part)
        if part.stat().st_size != src.stat().st_size:
            part.unlink(missing_ok=True)
            raise OSError(f"{name}: size mismatch after copy to {dest}")
        os.replace(part, tgt)
        print(f"  landed {tgt} ({tgt.stat().st_size / 1e6:,.1f} MB)", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--quarter", default=sources.DEFAULT_NCUA_QUARTER,
                    help=f"NCUA call-report quarter, yyyy-mm (default {sources.DEFAULT_NCUA_QUARTER})")
    ap.add_argument("--year", default=sources.DEFAULT_GAZETTEER_YEAR,
                    help=f"Census gazetteer year (default {sources.DEFAULT_GAZETTEER_YEAR})")
    ap.add_argument("--since", default="20240101", help="first FDIC call-report date, yyyymmdd (default 20240101)")
    ap.add_argument("--dest", default=None, help="where to land it (default: the folder the builds read)")
    ap.add_argument("--check", action="store_true", help="only check the store already at the destination")
    a = ap.parse_args(argv)

    dest = Path(a.dest) if a.dest else destination()
    print(f"Market reference store: {dest}")
    if a.check:
        try:
            info = check(dest, a.quarter, a.year)
        except Exception as exc:
            print(f"NOT READY: {type(exc).__name__}: {exc}")
            return 1
        print(f"READY: {info['institutions']:,} institutions, {info['branches']:,} branches placed")
        return 0

    with tempfile.TemporaryDirectory(prefix="rpe_market_") as tmp:
        work = Path(tmp)
        print(f"Fetching into {work} (local scratch; the share is not written until every check passes)")
        try:
            fetch(work, a.quarter, a.year, a.since)
            info = check(work, a.quarter, a.year)
        except Exception as exc:
            print(f"\nStopped before touching the share: {type(exc).__name__}: {exc}")
            return 1
        info.update({"ncua_quarter": a.quarter, "gazetteer_year": a.year, "fdic_since": a.since,
                     "built": time.strftime("%Y-%m-%d %H:%M")})
        (work / VINTAGES).write_text(json.dumps(info, indent=1), encoding="utf-8")
        print(f"\nChecked: {info['institutions']:,} institutions, {info['branches']:,} branches placed, "
              f"{info['unplaced_branches']:,} could not be placed")
        try:
            land(work, dest, [f"{n}.json" for n in REQUIRED_CACHE] + [VINTAGES])
        except OSError as exc:
            print(f"\nCould not land on the share: {exc}. Is the VPN on?")
            return 1
    print(f"\nDone. The Transaction Intelligence builds will read it from {dest}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
