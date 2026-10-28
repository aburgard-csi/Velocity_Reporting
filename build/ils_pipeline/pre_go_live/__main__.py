# Ported from v5 02-Scripts/ils/pre_go_live/__main__.py at 7ba1e63. Logic unchanged; the one import reads ils_pipeline.core.layout; run as python -m ils_pipeline.pre_go_live from build/.
"""Terminal front for the PGL run -- the same engine the Desktop tools use.

    python -m ils.pre_go_live 1737
    python -m ils.pre_go_live 1737 --open-status O --od-eligible 003,005 \
        --rege-opt-in Y --rege-opt-out N --fee 27 --deck
"""

import argparse
import sys
from pathlib import Path

from . import report, run
from ils_pipeline.core import layout


def _gather(tokens):
    """Tokens from nargs="+" -> clean code list. Accepts comma-separated,
    space-separated, and Python-list-looking input (brackets/quotes stripped),
    so ["C", "X"] typed into PowerShell still works."""
    if not tokens:
        return None
    out = []
    for tok in tokens:
        for part in tok.split(","):
            part = part.strip().strip("[](){}\"'")
            if part:
                out.append(part)
    return out or None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ils.pre_go_live",
                                 description="ILS pre-go-live analysis")
    ap.add_argument("client_id")
    ap.add_argument("--open-status", nargs="+", help="open Account Status codes (spaces or commas)")
    ap.add_argument("--od-eligible", nargs="+", help="ILS-eligible OD Status codes (spaces or commas)")
    ap.add_argument("--rege-opt-in", nargs="+", help="opted-in Reg-E values")
    ap.add_argument("--rege-opt-out", nargs="+", help="opted-out Reg-E values")
    ap.add_argument("--fee", type=float, help="the client's CONFIRMED current NSF/OD fee")
    ap.add_argument("--deck", action="store_true", help="also build the board deck")
    ap.add_argument("--current-only", action="store_true",
                    help="deck: current-state story only; omit the what-changes-at-"
                         "go-live chapter (ILS proposed limits)")
    ap.add_argument("--include-deleted", action="store_true",
                    help="keep deletion-flagged rows in every base (default: excluded, reported)")
    ap.add_argument("--data-root", type=Path)
    ap.add_argument("--output-root", type=Path)
    a = ap.parse_args(argv)

    codes = None
    if any([a.open_status, a.od_eligible, a.rege_opt_in]):
        codes = {"open_status": _gather(a.open_status), "od_eligible": _gather(a.od_eligible),
                 "rege_opt_in": _gather(a.rege_opt_in), "rege_opt_out": _gather(a.rege_opt_out)}
    res = run(a.client_id, codes=codes, data_root=a.data_root,
              output_root=a.output_root, fee=a.fee, include_deleted=a.include_deleted)
    print(report(res))
    if a.deck and res.ok and res.status != "needs_codes":
        from .deck import build
        template = layout.TEMPLATE
        out_dir = Path(res.outputs["metrics"]).parent
        deck = build(res, template, out_dir / f"{a.client_id}_{out_dir.name}_ILS_PreGoLive.pptx",
                     include_golive=not a.current_only)
        print(f"\ndeck: {deck.path} ({deck.slides} slides, {deck.charts} charts"
              + (f"; skipped {deck.skipped}" if deck.skipped else "") + ")")
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
