#!/usr/bin/env python3
"""Check the Transaction Intelligence cut's ported analyses against a v5 run.

    python scripts/ti_parity.py <v5 run folder> --client 1100 --config <v5 clients_config.json>
                                [--only bases,attrition] [--json out.json]

<v5 run folder> is one client's v5 output folder (`03-Output/<period>/<id>/` in the v5 repo),
holding `enriched.parquet`, `metrics.json` and, after a transaction run, `txn_metrics.json`.
Every key a registered computation returns is compared with v5's (build/ars_pipeline/ti/parity.py).
Read-only: it writes nothing unless --json is given. Exit status is the number of keys that
differ, so a clean check exits 0.
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline")):
    if p not in sys.path:
        sys.path.insert(0, p)

from ti import parity  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("v5_dir")
    ap.add_argument("--client", required=True)
    ap.add_argument("--config", required=True, help="the v5 clients_config.json the run used")
    ap.add_argument("--only", default="", help="comma-separated registry names")
    ap.add_argument("--json", default=None, help="also write the full result here")
    a = ap.parse_args(argv)

    with open(a.config, encoding="utf-8-sig") as fh:
        config = json.load(fh).get(str(a.client))
    if not config:
        raise SystemExit(f"client {a.client} is not in {a.config}")
    names = [n.strip() for n in a.only.split(",") if n.strip()] or None
    result = parity.run(a.v5_dir, config, names, client_id=a.client)

    bad = 0
    for name, rows in result.items():
        n_bad = sum(1 for _k, st, _d in rows if st != "match")
        bad += n_bad
        print(f"{name}: {len(rows) - n_bad} of {len(rows)} keys match")
        for k, st, d in rows:
            if st != "match":
                print(f"   {st:<14} {d or k}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    return min(bad, 125)


if __name__ == "__main__":
    sys.exit(main())
