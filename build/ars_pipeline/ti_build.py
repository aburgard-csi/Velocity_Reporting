#!/usr/bin/env python3
"""
ti_build.py — build one client's Transaction Intelligence cut: the figures once, then a deck
per lens.

    python ti_build.py <client id> <period yyyy.mm> <client name> <out dir> [--ics]

Called by `scripts/build_month.build_client` after the ARS deck, only when `RPE_TI=1`, with
<out dir> = the client's staging folder + `ti/`. The decks go there and nowhere else:
`promote_month.deliverable()` reads only the staging folder's own files, so a cut deck can
never be shipped in place of the ARS deck, and nothing here is passed to `assemble_combined`.

  1. the ODD, read as v5 reads it (`ti/odd.py`), and the client config (`ti/config.py`);
  2. with --ics (the client is on ICS in clients.md), the ICS lists joined onto the ODD;
  3. every chapter's `compute` on one shared context, merged into `ti_pack.json`;
  4. the ARS lens deck; with --ics, the ICS lens deck — unless the ICS lens has no accounts,
     which is stated here and in the pack, never rendered as an empty deck.

A chapter whose compute fails is stated in the pack's warnings and the build continues: one
analysis never takes the cut down. With no chapter ported yet there is nothing to build, and
this says so and exits 0.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (HERE.parent, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

REPO = HERE.parent.parent
TEMPLATE = REPO / "templates" / "ars_template.pptx"


def attach_txn(ctx, warnings, months=12):
    """The client's transaction window on the context: v5's loader over the staged files (window
    end = the ODD's data month, as in v5's run), and the account lenses keyed on the ODD's ids.
    A client with no transaction files on hand gets none, and the chapters that need them say so."""
    import pandas as pd
    import rpe_env
    from ti import txn_stage
    from ti.transaction_intelligence import lens as txn_lens
    if not rpe_env.txn_files(ctx.client_id):
        warnings.append(f"client {ctx.client_id}: no transaction files in Inputs/Txn Files; "
                        f"the transaction chapters are stated, not rendered")
        return ctx
    ctx.anchor_ts = pd.Timestamp(ctx.anchor.year, ctx.anchor.month, 1) + pd.offsets.MonthEnd(0)
    ctx.txn, ctx.txn_report = txn_stage.load(ctx.client_id, months, ctx.anchor_ts, log=lambda _m: None)
    warnings.extend(ctx.txn_report.warnings)
    if ctx.txn.empty:
        warnings.append(f"client {ctx.client_id}: no transaction rows in the window ending {ctx.anchor.iso}")
        ctx.txn = None
        return ctx
    ctx.lenses = txn_lens.build(ctx.frame, ctx.anchor_ts, warnings.append,
                                branch_map=ctx.config.get("BranchMapping"))
    return ctx


def compute_pack(client_id, period, name, ics=False):
    """The cut's data pack for one client: sources, data month, figures, and every warning."""
    import pandas as pd
    from ti import config, cut, lens, odd
    from ti.context import Ctx
    from ti.core.subsets import build_subsets

    warnings = []
    frame, report, source = odd.load_client(client_id)
    if report.errors:
        raise SystemExit(f"client {client_id}: the ODD transform failed: {'; '.join(report.errors)}")
    warnings += list(report.warnings)
    cfg = config.client_config(client_id, warn=warnings.append)
    from ti import deposits_input
    cfg = deposits_input.attach(cfg, client_id, warnings.append)
    # the workbook first, as in v5's run: its rates feed the value math (ti/workbook_input.py)
    from ti import workbook_input
    cfg, wb = workbook_input.attach(cfg, client_id, period, warnings.append)
    if ics:
        frame = lens.attach_ics(frame, client_id, warnings.append, expected=True)
    anchor = odd.frame_data_month(frame)
    if anchor is None:
        raise SystemExit(f"client {client_id}: no month-tagged transaction columns in the ODD")
    subsets = build_subsets(frame, cfg, anchor)
    warnings += list(subsets.warnings)
    ctx = Ctx(frame, cfg, anchor, subsets, client_id=str(client_id))
    metrics = {"data_month": anchor.iso, "anchor_tag": anchor.tag, **subsets.sizes(), **wb}
    attach_txn(ctx, warnings)
    if ctx.txn_report is not None:
        metrics.update({"txn_files_loaded": ctx.txn_report.files, "txn_rows": ctx.txn_report.rows,
                        "txn_anchor": anchor.iso})
    for ch in cut.CHAPTERS:
        try:
            metrics.update(ch.compute(ctx) or {})
        except Exception as exc:                      # one chapter, never the cut
            warnings.append(f"{ch.title}: figures not computed ({type(exc).__name__}: {exc})")
    warnings += ctx.warnings

    lenses = ["ars"] + (["ics"] if ics else [])
    unavailable = {}
    end = pd.Timestamp(report.anchor_date) if report.anchor_date is not None else None
    for key in lenses:
        try:
            lens.lens_masks(frame, key, end)
        except lens.LensUnavailable as exc:
            unavailable[key] = str(exc)
    return {"client_id": str(client_id), "client_name": name, "period": period,
            "data_month": anchor.tag, "sources": {"odd": source, "config": cfg.get("_source", "")},
            "lenses": [k for k in lenses if k not in unavailable], "lenses_unavailable": unavailable,
            "metrics": metrics, "warnings": warnings}


def build_decks(pack, out_dir, chapters=None):
    """A deck per available lens into out_dir; returns their paths."""
    from pptx import Presentation
    import build_ti_gen as G
    from ti import cut
    chapters = list(cut.CHAPTERS if chapters is None else chapters)
    made = []
    for key in pack["lenses"]:
        prs = Presentation(str(TEMPLATE))
        G.build(prs, pack, key, chapters, art_dir=str(Path(out_dir) / "art"))
        out = Path(out_dir) / cut.deck_name(pack["client_id"], pack["period"], pack["client_name"], key)
        G.save(prs, out)
        made.append(out)
    return made


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("client_id")
    ap.add_argument("period")
    ap.add_argument("client_name")
    ap.add_argument("out_dir")
    ap.add_argument("--ics", action="store_true", help="the client is on ICS: build the ICS lens too")
    a = ap.parse_args(argv)

    from ti import cut
    if not cut.CHAPTERS:
        print(f"{a.client_id}: no chapter of the {cut.CUT_NAME} cut is ported yet; nothing built")
        return 0
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pack = compute_pack(a.client_id, a.period, a.client_name, ics=a.ics)
    (out / "ti_pack.json").write_text(json.dumps(pack, indent=1, default=str), encoding="utf-8")
    for key, why in pack["lenses_unavailable"].items():
        print(f"{a.client_id}: {cut.lens(key).label} not built: {why}")
    for w in pack["warnings"]:
        print(f"{a.client_id}: {w}")
    # v5's own read-outs of the transaction figures, into the build log (never a deck)
    from ti.transaction_intelligence import competition_report, sections_report
    for line in competition_report.lines(pack["metrics"], {}) + sections_report.lines(pack["metrics"]):
        print(line)
    for p in build_decks(pack, out):
        print(f"built {p}")
    return 0


if __name__ == "__main__":
    from ti.compat import legacy_strings
    with legacy_strings():          # v5's pandas-2 string semantics, this process only
        sys.exit(main())
