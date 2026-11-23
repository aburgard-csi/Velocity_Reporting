#!/usr/bin/env python3
"""land_ils_reviews.py — put each client's newest ILS Program Analysis review PDF on the share, and read it into the pack
Live Review's ILS section shows (Aaron, 2026-11-06: "put ILS review PDFs on the share").

    python scripts/land_ils_reviews.py --from "<...>\\Clients" [--client 1539 ...] [--dry-run] [--no-pack]

The finished reviews live in the Clients library, one folder per client, in `ILS Delivery` as
`<id>-<yyyy.mm>-ILS-<Client> ILS Review.pdf` (the .pptm / earlier-format files beside them are not reviews and are left
alone). The newest review per client, by the period in its name, is copied to
`Inputs/ILS Reviews/<id>/` on the share, then read into `Build Artifacts/ils_analysis/review_packs/<id>_ils_review.json`,
so a CSM's PC never parses a PDF: it reads the pack.

  * Copy-only. Nothing is deleted or overwritten: a file already on the share at the same size is "on hand"; one with the
    same name at another size is reported and left for a person to decide. An older review stays beside a newer one.
  * Written through a `.part` and verified by size before it takes its name, as the source watch does.
  * A review whose tables do not reconcile (or that does not look like a Program Analysis) is landed and reported, with
    no pack: the page then says the review is not on the share, never a figure that does not add up.
  * `--from` (or the env var RPE_ILS_CLIENTS_DIR) names the Clients library on THIS machine; it is never written into code.
  * Hand-run, like land_txn_files.py: not in the 08:00 watch, not in Sheila.

Import-safe: `plan`, `land`, `pack_client` are the pieces; `main` does the I/O.
"""
import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (HERE.parent / "build", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from review_page import ils_review_pack as R   # noqa: E402


def candidates(source):
    """Every review PDF under a Clients library: `<client folder>/ILS Delivery/*.pdf`, or PDFs straight in `source`."""
    src = Path(source)
    out = []
    for pattern in ("*/ILS Delivery/*.pdf", "*.pdf"):
        out += [p for p in src.glob(pattern) if R.review_period(p.name)]
    return out


def plan(source, clients=None):
    """{client id: newest review path} for the clients found (limited to `clients` when given)."""
    by_client = {}
    for p in candidates(source):
        cid = R.client_from_filename(p)
        if cid and (not clients or cid in clients):
            by_client.setdefault(cid, []).append(p)
    return {cid: R.newest(ps) for cid, ps in sorted(by_client.items())}


def land(src, dest_dir, dry_run=False):
    """Copy one PDF into `dest_dir`. Returns 'landed', 'on hand' or 'differs' (same name, another size: left alone)."""
    src, dest_dir = Path(src), Path(dest_dir)
    dest = dest_dir / src.name
    size = src.stat().st_size
    if dest.exists():
        return "on hand" if dest.stat().st_size == size else "differs"
    if dry_run:
        return "landed"
    dest_dir.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        with open(src, "rb") as fi, open(part, "wb") as fo:
            while True:
                chunk = fi.read(1 << 20)
                if not chunk:
                    break
                fo.write(chunk)
        if part.stat().st_size != size:
            raise OSError("size mismatch after copy: %d of %d bytes" % (part.stat().st_size, size))
        os.replace(part, dest)
    finally:
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass
    return "landed"


def pack_client(cid, dry_run=False, root=None):
    """Read the client's newest review on the share into its pack, unless the pack already comes from it.
    Returns (status, detail): 'packed', 'current', 'no review' or 'not read' (detail says why)."""
    import json
    pdf = R.newest_review(cid)
    if pdf is None:
        return "no review", "nothing in Inputs/ILS Reviews/%s" % cid
    pp = R.pack_path(cid, root)
    try:
        have = json.loads(pp.read_text(encoding="utf-8")) if pp.is_file() else None
    except (OSError, ValueError):
        have = None
    if have and have.get("source_file") == pdf.name and have.get("version") == R.PACK_VERSION:
        return "current", pdf.name
    try:
        pack = R.parse(R.read_pdf(pdf), pdf.name, cid)
    except R.ReviewReadError as e:
        return "not read", str(e)
    except Exception as e:                      # noqa: BLE001  (a damaged PDF is reported, never fatal to the batch)
        return "not read", "%s: %s" % (type(e).__name__, e)
    if not dry_run:
        pp.parent.mkdir(parents=True, exist_ok=True)
        pp.write_text(json.dumps(pack, indent=1), encoding="utf-8")
    return "packed", "%s, review of %s" % (pack["client_name"], pack["review_date"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from", dest="source", default=os.environ.get("RPE_ILS_CLIENTS_DIR"),
                    help="the Clients library on this machine (default: env RPE_ILS_CLIENTS_DIR)")
    ap.add_argument("--client", action="append", default=None, help="only this client number (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be landed and read; change nothing")
    ap.add_argument("--no-pack", action="store_true", help="land the PDFs only")
    a = ap.parse_args(argv)
    if not a.source or not Path(a.source).is_dir():
        print("Give --from <the Clients library> (or set RPE_ILS_CLIENTS_DIR); %r is not a folder." % a.source, file=sys.stderr)
        return 2
    found = plan(a.source, set(a.client) if a.client else None)
    if not found:
        print("No ILS review PDFs found under %s." % a.source)
        return 1
    counts = {}
    for cid, src in found.items():
        status = land(src, R.reviews_dir(cid, create=not a.dry_run), a.dry_run)
        counts[status] = counts.get(status, 0) + 1
        line = "%-5s %-8s %s" % (cid, status, Path(src).name)
        if status == "differs":
            line += "   (the share holds a file of this name at another size: left alone)"
        if not a.no_pack and status != "differs":
            pst, detail = pack_client(cid, a.dry_run) if not (a.dry_run and status == "landed") else ("would read", "")
            line += "  | pack: %s%s" % (pst, " (%s)" % detail if detail and pst in ("not read", "packed") else "")
            counts["pack " + pst] = counts.get("pack " + pst, 0) + 1
        print(line, flush=True)
    print("\n" + ", ".join("%s %d" % (k, v) for k, v in sorted(counts.items())) + (" (dry run: nothing changed)" if a.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
