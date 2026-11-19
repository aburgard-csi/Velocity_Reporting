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

Every step's time goes to the build log as it finishes (`[time] <step>: 12.3 s`) and into the pack's
`timings` (James Gilmore, 2026-10-29: "we obviously need to find a better, more efficient way to
review large txn files"; 1798's 23.6M rows took most of an hour, and nothing said where).

`--from-pack` draws the decks from the `ti_pack.json` already in <out dir> and computes nothing, for a
change to the slides alone (a layout fix redrew 1798 in minutes, not an hour). It refuses a pack for
another client or period, or one whose ODD extract or transaction files have changed since it was
written (`input_fingerprint`); the client config, workbook and trackers are not compared, so a change
to those needs a full build.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (HERE.parent, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

REPO = HERE.parent.parent
TEMPLATE = REPO / "templates" / "ars_template.pptx"


def attach_txn(ctx, warnings, months=12, period=None):
    """The client's transaction window on the context, and the account lenses keyed on the ODD's ids.

    The window is the last `months` COMPLETED months before the cycle `period` (ti/window.py):
    cycle 2026.11 runs through 31 Oct 2026, whatever the newest file or the ODD carries. Rows
    dated outside it are left out, and a month inside it with no rows is warned. With no period
    (an older caller), the cycle is the month after the ODD's data month, as v5's run had it.
    A client with no transaction files on hand gets none, and the chapters that need them say so."""
    import pandas as pd
    import rpe_env
    from ti import txn_stage, window
    from ti.transaction_intelligence import lens as txn_lens
    if not rpe_env.txn_files(ctx.client_id):
        warnings.append(f"client {ctx.client_id}: no transaction files in Inputs/Txn Files; "
                        f"the transaction chapters are stated, not rendered")
        return ctx
    if period is None:
        y, m = ctx.anchor.year, ctx.anchor.month
        period = f"{y + (m == 12)}.{m % 12 + 1:02d}"
    end = window.end_month(period)
    if (ctx.anchor.year, ctx.anchor.month) != (end.year, end.month):
        warnings.append(f"client {ctx.client_id}: the ODD runs to {ctx.anchor.iso} but the transaction "
                        f"window is the last {months} completed month(s) through {end:%b %Y}")
    ctx.anchor_ts = end + pd.offsets.MonthEnd(0)
    ctx.txn_window = window.describe(period, months)
    def staging(msg):                 # each copy from the share to the build log; a duplicated month to the pack too
        print(msg, flush=True)
        if "more than once" in msg:
            warnings.append(f"client {ctx.client_id}: {msg}")
    ctx.txn, ctx.txn_report = txn_stage.load(ctx.client_id, months, ctx.anchor_ts, log=staging)
    warnings.extend(ctx.txn_report.warnings)
    if not ctx.txn.empty:
        label = ctx.txn_window["txn_window_label"]
        start, stop = window.bounds(period, months)
        dates = pd.to_datetime(ctx.txn["transaction_date"], errors="coerce")
        inside = ((dates >= start) & (dates < stop)).to_numpy()
        if not inside.all():
            warnings.append(f"client {ctx.client_id}: {int((~inside).sum()):,} transaction row(s) dated "
                            f"outside the {label} window left out")
            ctx.txn = ctx.txn[inside]
            dates = dates[inside]
        have = set(dates.dt.to_period("M").astype(str))
        missing = [f"{s:%b %Y}" for s in window.month_starts(period, months)
                   if str(s.to_period("M")) not in have]
        if missing:
            warnings.append(f"client {ctx.client_id}: no transaction rows for {', '.join(missing)}; "
                            f"the {label} window is short by {len(missing)} month(s)")
        ctx.txn_window["txn_window_missing"] = missing
    if ctx.txn.empty:
        warnings.append(f"client {ctx.client_id}: no transaction rows in the window ending {end:%Y-%m}")
        ctx.txn = None
        return ctx
    ctx.lenses = txn_lens.build(ctx.frame, ctx.anchor_ts, warnings.append,
                                branch_map=ctx.config.get("BranchMapping"))
    return ctx


def input_fingerprint(client_id):
    """The ODD extract and every transaction file on hand, by name, size and modified time: what a
    pack's figures were computed from, compared before `--from-pack` reuses them."""
    import rpe_env
    from ti import odd

    def stamp(p):
        st = p.stat()
        return [p.name, st.st_size, int(st.st_mtime)]
    return {"odd": stamp(odd.odd_zip(client_id)), "txn": [stamp(p) for p in rpe_env.txn_files(client_id)]}


class _Clock:
    """Each step's seconds, printed to the build log as it finishes and kept for the pack."""

    def __init__(self):
        self.times, self._t = {}, time.perf_counter()

    def lap(self, step):
        now = time.perf_counter()
        self.times[step] = round(now - self._t, 1)
        self._t = now
        try:
            import psutil
            mem = f", {psutil.Process().memory_info().rss / 2**30:.1f} GB in use"
        except Exception:                         # psutil is optional; the time alone still says where
            mem = ""
        print(f"[time] {step}: {self.times[step]:,.1f} s{mem}", flush=True)


def compute_pack(client_id, period, name, ics=False, lists_dir=None, prior_pack=None):
    """The cut's data pack for one client: sources, data month, figures, and every warning."""
    import pandas as pd
    from ti import config, cut, lens, odd
    from ti.context import Ctx
    from ti.core.subsets import build_subsets

    clock = _Clock()
    fingerprint = input_fingerprint(client_id)
    warnings = []
    frame, report, source = odd.load_client(client_id)
    clock.lap("ODD extract read")
    if report.errors:
        raise SystemExit(f"client {client_id}: the ODD transform failed: {'; '.join(report.errors)}")
    warnings += list(report.warnings)
    cfg = config.client_config(client_id, warn=warnings.append)
    from ti import deposits_input
    cfg = deposits_input.attach(cfg, client_id, warnings.append)
    # the workbook first, as in v5's run: its rates feed the value math (ti/workbook_input.py)
    from ti import workbook_input
    cfg, wb = workbook_input.attach(cfg, client_id, period, warnings.append)
    # then the 2:1 deferral tracker: when it exists its math is the client's economics
    from ti import deferred_input
    gt = deferred_input.attach(client_id, warnings.append)
    if ics:
        frame = lens.attach_ics(frame, client_id, warnings.append, expected=True)
    clock.lap("config, workbook and trackers")
    anchor = odd.frame_data_month(frame)
    if anchor is None:
        raise SystemExit(f"client {client_id}: no month-tagged transaction columns in the ODD")
    subsets = build_subsets(frame, cfg, anchor)
    warnings += list(subsets.warnings)
    ctx = Ctx(frame, cfg, anchor, subsets, client_id=str(client_id))
    if lists_dir is not None:                         # the mail lists land beside the decks (fs-02)
        ctx.shared["lists_dir"] = Path(lists_dir)
    metrics = {"data_month": anchor.iso, "anchor_tag": anchor.tag, **subsets.sizes(), **wb, **gt}
    # v5's extract check first, as in v5's metrics.py: what shape the file is (months missing,
    # Swipes and Spend on different months, an account twice) before any figure is computed on it
    from ti.monthly_analysis import extract_check
    metrics.update(extract_check.compute(subsets, cfg, warnings.append))
    deferred_input.review(gt, wb, anchor.iso, warnings.append)
    clock.lap("account subsets")
    from ti import window
    try:
        months = window.months_for(cfg)
    except ValueError as exc:
        raise SystemExit(f"client {client_id}: {exc}")
    early = window.early_run_warning(period)
    if early:
        warnings.append(f"client {client_id}: {early}")
    attach_txn(ctx, warnings, months=months, period=period)
    clock.lap(f"transaction files loaded ({ctx.txn_report.rows:,} rows)" if ctx.txn_report is not None
              else "transaction files (none)")
    if ctx.txn_report is not None:
        metrics.update({"txn_files_loaded": ctx.txn_report.files, "txn_rows": ctx.txn_report.rows,
                        "txn_anchor": f"{ctx.anchor_ts:%Y-%m}", **(getattr(ctx, "txn_window", None) or {})})
    for ch in cut.CHAPTERS:
        try:
            metrics.update(ch.compute(ctx) or {})
        except Exception as exc:                      # one chapter, never the cut
            warnings.append(f"{ch.title}: figures not computed ({type(exc).__name__}: {exc})")
        clock.lap(f"chapter {ch.title}")
    warnings += ctx.warnings

    if prior_pack:
        # what changed in the layered competition figures since the previous month's pack (same client)
        try:
            from ti.transaction_intelligence import competition_layers as CL
            from ti.transaction_intelligence import competition_layers_compare as CLC
            prior = json.loads(Path(prior_pack).read_text(encoding="utf-8"))
            if prior.get("client_id") != str(client_id):
                warnings.append(f"competition layers: the prior pack {prior_pack} is for client {prior.get('client_id')}, "
                                f"not {client_id}; no comparison")
            else:
                chg = CLC.compare(metrics, prior.get("metrics") or {}, CL.settings(cfg), prior.get("period"))
                if chg:
                    metrics["cl_changes"] = chg
                else:
                    warnings.append("competition layers: this month's or the prior pack has no layered figures; no comparison")
        except Exception as exc:
            warnings.append(f"competition layers: the prior pack could not be compared ({type(exc).__name__}: {exc})")
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
            "metrics": metrics, "warnings": warnings, "inputs": fingerprint, "timings": clock.times,
            "computed": time.strftime("%Y-%m-%d %H:%M")}


def write_run_tables(pack, out):
    """The slide ledger and the portfolio row (fs-06). Both are beside the decks; the portfolio row is
    also upserted into the shared table when RPE_TI_PORTFOLIO names one. A failure here never costs the
    decks: it is printed and the build still succeeds."""
    try:
        from ti import ledger, portfolio
        rows = ledger.rows(pack)
        ledger.write(Path(out) / "ti_slide_ledger.csv", rows)
        print(f"{pack['client_id']}: slide ledger: {ledger.summary(rows)} ({Path(out) / 'ti_slide_ledger.csv'})")
        row = portfolio.row(pack)
        portfolio.upsert(Path(out) / "ti_portfolio_row.csv", row)
        shared = portfolio.shared_table()
        if shared:
            portfolio.upsert(shared, row)
            print(f"{pack['client_id']}: portfolio row upserted into {shared}")
    except Exception as exc:                          # never the decks
        print(f"{pack['client_id']}: slide ledger / portfolio row not written ({type(exc).__name__}: {exc})")


def pack_for_reuse(out, client_id, period):
    """The pack in `out` when it can be redrawn as it is, else SystemExit saying why."""
    f = Path(out) / "ti_pack.json"
    if not f.is_file():
        raise SystemExit(f"--from-pack: no ti_pack.json in {out}; run a full build first")
    pack = json.loads(f.read_text(encoding="utf-8"))
    if (pack.get("client_id"), pack.get("period")) != (str(client_id), period):
        raise SystemExit(f"--from-pack: the pack in {out} is client {pack.get('client_id')} "
                         f"{pack.get('period')}, not {client_id} {period}")
    if pack.get("inputs") != input_fingerprint(client_id):
        raise SystemExit("--from-pack: the ODD extract or the transaction files have changed since the pack "
                         "was computed (or it predates the check); run a full build")
    return pack


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
    ap.add_argument("--prior-pack", default=None,
                    help="the previous month's ti_pack.json for this client: adds 'this month's changes' to the "
                         "competition layers")
    ap.add_argument("--from-pack", action="store_true",
                    help="draw the decks from the ti_pack.json in <out dir>; compute nothing")
    a = ap.parse_args(argv)

    from ti import cut
    if not cut.CHAPTERS:
        print(f"{a.client_id}: no chapter of the {cut.CUT_NAME} cut is ported yet; nothing built")
        return 0
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if a.from_pack:
        pack = pack_for_reuse(out, a.client_id, a.period)
        print(f"figures from the pack computed {pack.get('computed')}: nothing recomputed", flush=True)
    else:
        pack = compute_pack(a.client_id, a.period, a.client_name, ics=a.ics, lists_dir=out / "lists",
                            prior_pack=a.prior_pack)
        # v5's analyst tables (ti/monthly_analysis/tables.py): every tabular figure that declares its
        # columns, as a CSV under out/tables, so a number on a slide can be checked row by row. The
        # names v5 never declared come from ti/table_columns.py, on the way in only (the pack is untouched).
        try:
            from ti import table_columns
            from ti.monthly_analysis import tables
            pack["tables"] = tables.write(table_columns.with_columns(pack["metrics"]), out,
                                          pack["warnings"].append)
        except Exception as exc:                      # the tables never take the build down
            pack["warnings"].append(f"analyst tables failed: {type(exc).__name__}: {exc}")
        # v5's consistency audit (ti/monthly_analysis/consistency.py): one concept, one number. The cut
        # holds the ODD and transaction figures in one dict, so it is passed as both of v5's arguments.
        from ti.monthly_analysis import consistency
        pack["consistency"] = consistency.audit(pack["metrics"], pack["metrics"])
        pack["warnings"] += [f"consistency: {msg}" for msg in pack["consistency"]]
        (out / "ti_pack.json").write_text(json.dumps(pack, indent=1, default=str), encoding="utf-8")
    for key, why in pack["lenses_unavailable"].items():
        print(f"{a.client_id}: {cut.lens(key).label} not built: {why}")
    for w in pack["warnings"]:
        print(f"{a.client_id}: {w}")
    # v5's own read-outs of the transaction figures, into the build log (never a deck)
    from ti.transaction_intelligence import competition_report, finserv_report, sections_report
    for line in (competition_report.lines(pack["metrics"], {}) + sections_report.lines(pack["metrics"])
                 + finserv_report.lines(pack["metrics"])):
        print(line)
    if pack.get("consistency"):
        # as v5's run.py: a deck whose slides contradict each other is worse than no deck
        print(f"{a.client_id}: decks not built: the consistency audit found {len(pack['consistency'])} "
              f"number(s) that disagree across slides (see 'consistency:' above)")
        return 0
    t = time.perf_counter()
    for p in build_decks(pack, out):
        print(f"built {p}")
    print(f"[time] decks drawn: {time.perf_counter() - t:,.1f} s", flush=True)
    write_run_tables(pack, out)
    return 0


if __name__ == "__main__":
    from ti.compat import legacy_strings
    with legacy_strings():          # v5's pandas-2 string semantics, this process only
        sys.exit(main())
