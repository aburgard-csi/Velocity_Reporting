#!/usr/bin/env python3
"""peer_tables.py — refresh the ICS revenue cache and show how many peers each comparison has.

    python scripts/peer_tables.py                     # refresh Build Artifacts/peer_tables/ics_revenue.json, list the tables
    python scripts/peer_tables.py --client 1539 --period 2026.10 [--program ARS ICS MRPC CP]
                                                      # the peer count behind each metric for one client (nothing is written)

Read-only on the share except for the cache file in Build Artifacts/peer_tables/ (or the folder RPE_PEER_TABLES_DIR names).
NOT part of the 08:00 source watch and not scheduled: a deck build or a Live Review run refreshes a stale entry itself, and
the first read of the ICS workbooks takes several minutes over the share (about 27 workbooks), which is why a hand run is the
way to warm the cache after new workbooks land. See build/peer_tables.py.
"""
import argparse
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--client")
    ap.add_argument("--period")
    ap.add_argument("--program", nargs="*", default=["ARS", "ICS", "MRPC", "CP"])
    a = ap.parse_args(argv)
    import peer_tables as PT
    import rpe_env
    if not a.client:
        rows = PT.ics_revenue_rows()
        print(f"ICS workbooks: {len(rows)} clients with a revenue-per-account row ({PT.cache_dir()})")
        ars = PT.ars_rows(rpe_env.build_artifacts(), a.period)
        print(f"ARS data packs: {len(ars)} clients with a response-rate row")
        return 0
    import peer_compare as PC
    for prog in a.program:
        ev = PC.for_deck(prog, a.client, period=a.period)
        print(f"{prog}: {ev['n_pool']} other clients on the program")
        for i in ev["items"]:
            print(f"  {i['spec']['label']}: {i['c']['n']} peers; {i['sentence']}")
        for l in ev["left"]:
            print(f"  left out: {l}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
