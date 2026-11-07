#!/usr/bin/env python3
"""ils_review_pack.py — turn a client's finished ILS Program Analysis review (PDF) into the pack Live Review reads.

    python scripts/ils_review_pack.py "<...>/1539-2026.07-ILS-Marine FCU ILS Review.pdf" [--client 1539] [--dry-run]

Writes `Build Artifacts/ils_analysis/review_packs/<id>_ils_review.json` (a newer review replaces the older pack).
Read-only on the PDF; a table that does not reconcile stops the read and nothing is written. Details and the list of
pages read: build/review_page/ils_review_pack.py.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "build"))

from review_page import ils_review_pack as R   # noqa: E402


def write_pack(pack, root=None):
    p = R.pack_path(pack["client_id"], root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(pack, indent=1), encoding="utf-8")
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pdf")
    ap.add_argument("--client", default=None, help="client number (default: the one at the start of the file name)")
    ap.add_argument("--dry-run", action="store_true", help="read and report, write nothing")
    a = ap.parse_args(argv)
    client = a.client or R.client_from_filename(a.pdf)
    if not client:
        print("Give --client: the file name does not start with <id>-<yyyy.mm>-ILS-.", file=sys.stderr)
        return 2
    try:
        pack = R.parse(R.read_pdf(a.pdf), Path(a.pdf).name, client)
    except R.ReviewReadError as e:
        print(f"Not written: {e}", file=sys.stderr)
        return 1
    print(f"{pack['client_name']} ({client}), review of {pack['review_date']}, {pack['page_count']} pages. Read:")
    for k, pg in pack["pages"].items():
        print(f"  {k:16s} page {pg}")
    if a.dry_run:
        return 0
    print("Wrote", write_pack(pack))
    return 0


if __name__ == "__main__":
    sys.exit(main())
