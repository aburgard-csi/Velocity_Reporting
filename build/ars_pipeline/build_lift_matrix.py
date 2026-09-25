#!/usr/bin/env python3
"""
build_lift_matrix.py — a client's ARS Lift Matrix file from the command line, without Sheila.

    python build/ars_pipeline/build_lift_matrix.py <ODDD.zip|.csv> <client id> "<client name>" <yyyy.mm> <out dir|.xlsx>
        [--workbook <ARS workbook>] [--ic-rate 0.006] [--nsf-fee 30] [--collection 0.8] [--winsor 0.99]

RETIRED AS A METHOD (Aaron, 2026-09-25: "retire build_lift_matrix.py and have it use lift_values").
This file used to carry its own valuation: a pickle from lift_extract.py, every card-holding eligible
account (business included), 12 months with no completeness check, an optional book-wide trim and a
100% collection default. CSM Sheila's Lift Matrix tab then got lift_values.py, and two valuations of
one matrix is the drift this repo keeps paying for. Everything here now comes from lift_values —
the accounts, window, segments, outlier caps, rates and the file layout — so a hand run and a Sheila
run of the same client give the same file. lift_extract.py was retired with it.

The rates default exactly as Sheila's do (lift_values.default_rates): the workbook's Interchange Rate
else 60 BP; the ODD's most common Fees1 per-item fee, else the workbook's NSF Fee; 100% collection.
With no NSF/OD fee from any source the run stops and asks for --nsf-fee rather than guess one.

Sheila records each export before its download; a hand run records nothing. Check the values
it prints against the client's current matrix before the file goes to Bradford.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lift_values as LV  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="A client's ARS Lift Matrix file, valued by lift_values.")
    ap.add_argument("odd", help="the client's ODDD extract (.zip or .csv)")
    ap.add_argument("client_id")
    ap.add_argument("client_name")
    ap.add_argument("period", help="yyyy.mm, for the file name")
    ap.add_argument("out", help="a folder (the standard file name is used) or an .xlsx path")
    ap.add_argument("--workbook", help="the client's ARS workbook, for its Interchange Rate and NSF Fee")
    ap.add_argument("--ic-rate", type=float, help="interchange rate as a fraction (0.006 = 60 BP)")
    ap.add_argument("--nsf-fee", type=float, help="NSF/OD fee per item, in dollars")
    ap.add_argument("--collection", type=float, help="OD collection rate as a fraction (default 1.0 = 100%%)")
    ap.add_argument("--winsor", type=float, choices=LV.WINSOR_OPTIONS,
                    help="outlier cap: each segment's percentile (default 0.99; 1 = no cap)")
    a = ap.parse_args(argv)

    scan = LV.scan(a.odd)
    book = LV.read_workbook(a.workbook) if a.workbook else {"assumptions": {}, "matrix": None}
    d = LV.default_rates(scan, book["assumptions"])
    ic = a.ic_rate if a.ic_rate is not None else d["ic_rate"]
    fee = a.nsf_fee if a.nsf_fee is not None else d["nsf_fee"]
    col = a.collection if a.collection is not None else d["collection"]
    cap = a.winsor if a.winsor is not None else d["winsor"]
    if fee is None:
        raise SystemExit("No NSF/OD fee: the ODD carries no Fees1 and no --workbook gave one. Pass --nsf-fee.")

    vals = LV.values(scan, ic, fee, col, cap)
    out = a.out if a.out.lower().endswith(".xlsx") else os.path.join(
        a.out, LV.out_name(a.client_id, a.period, a.client_name))
    LV.write_xlsx(vals, out)

    src = lambda given, key: "given" if given is not None else d[key]  # noqa: E731
    print(f"wrote {out}")
    print(f"  {scan['population']:,} ARS-eligible card-holding accounts (consumer and business), {scan['window_label']}, "
          f"from {scan['source_file']}")
    if scan["excluded_months"]:
        print(f"  {scan['excluded_months']}")
    print(f"  IC rate {ic:.4%} ({src(a.ic_rate, 'ic_source')}) | NSF/OD fee ${fee:.2f} "
          f"({src(a.nsf_fee, 'nsf_source')}) | collection {col:.0%} ({src(a.collection, 'collection_source')})"
          f" | outlier cap {LV.cap_label(cap)}")
    cur = (book["matrix"] or {}).get("segments", {})
    for r in vals["segments"]:
        now = (cur.get(r["segment"]) or {}).get("dda")
        print(f"    {r['segment']:8} dist {r['dist']:.4f}  DDA {r['dda']:7.2f}  n {r['n']:7,}"
              + (f"   current {now:7.2f}" if now is not None else "")
              + ("   (no card-less eligible accounts: NU's value)" if r.get("from_nu") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
