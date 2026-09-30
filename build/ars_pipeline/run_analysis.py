#!/usr/bin/env python3
"""
run_analysis.py — run the analysis engine on the ODD the deck build already reads.

    python3 run_analysis.py <odd.zip|odd.csv> <client id> <period YYYY.MM> [--workbook <xlsx>]
                            [--out <dir>] [--name "<Client>"] [--no-txn]

Reads the ODD extract through odd_rows.open_odd (the one zip-member rule), transforms it
once (engine.core.odd_transform), builds the client record from the code tables and the
workbook (engine_config), runs the transaction sections on Inputs/Txn Files/<id>/ through
rpe_env.open_txn, then the ODD sections behind engine.monthly_analysis.metrics.SECTIONS,
audits the result for one-concept-one-number consistency, and writes build EVIDENCE, not a
deliverable, to `Build Artifacts/analysis/<period>/<id>/`:

    metrics.json          every ODD section's figures, with denominators named
    txn_metrics.json      the transaction sections (when the client has files)
    enriched.parquet      the transformed frame
    report.md             the written report a CSM reads
    tables/, lists/       the analyst CSVs and the stressor roster
    <id>_<period>_analysis.json   the run manifest: status, warnings, outputs

The period is the delivery month (2026.08); the ODD's latest month is one before it, as
in the deck. Nothing here writes a slide. build_ars_gen calls `run()` under RPE_ANALYSIS=1
and fails the build when these figures do not reproduce the deck's own.
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from odd_rows import open_odd                                          # noqa: E402
import engine_config                                                   # noqa: E402
from engine.core.periods import Month, data_month                      # noqa: E402
from engine.core.odd_transform import transform_odd                    # noqa: E402
from engine.core.result import AnalysisResult, Timer                   # noqa: E402
from engine.core.env import write_text_atomic                          # noqa: E402

ANALYSIS = "unified_analysis"
HEADER_ANCHORS = ("Acct ID", "Acct Number", "Prod Code", "Stat Code", "Branch")
TXN_MONTHS = 12


def read_odd(path):
    """(raw DataFrame, source name, preamble rows). The header row is DETECTED: the ODD
    carries a preamble whose length is not fixed, and the deck's readers look for it too."""
    import pandas as pd
    fh, source = open_odd(path)
    with fh:
        rows = []
        for i, row in enumerate(csv.reader(line.replace("\x00", "") for line in fh)):
            if i >= 25:
                break
            rows.append(row)
    header_row = next((i for i, row in enumerate(rows)
                       if sum(a in {c.strip() for c in row} for a in HEADER_ANCHORS) >= 3), None)
    if header_row is None:
        raise ValueError(f"no header row in the first 25 lines of {source}")
    fh, _ = open_odd(path)
    with fh:
        df = pd.read_csv(fh, skiprows=header_row, low_memory=False)
    first = str(df.columns[0])
    if first.startswith("Unnamed") or not first.strip():
        df = df.drop(columns=df.columns[0])
    df = df.rename(columns=lambda c: str(c).strip())
    return df, source, header_row


def analysis_dir(period, client_id, root=None):
    """Build Artifacts/analysis/<YYYY.MM>/<id>/ — evidence, never a deliverable. The period is
    spelled the way the pipeline spells it everywhere (2026.09), not ISO."""
    if root is None:
        import rpe_env
        root = rpe_env.build_artifacts()
    d = Path(root) / "analysis" / str(period) / str(client_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


TRACKER_GLOB = "Deferred*.xls*"      # matched as <id>*Deferred*.xls*


def find_tracker(client_id, root=None):
    """The client's 2:1 guarantee deferral tracker under Inputs/Guarantee Trackers/, newest
    name last, Excel lock stubs ignored; None when there is none."""
    import rpe_env
    base = Path(root) if root is not None else rpe_env.input_dir("Guarantee", create=False)
    if not base.is_dir():
        return None
    hits = sorted(p for p in base.glob(f"{client_id}*{TRACKER_GLOB}") if not p.name.startswith("~$"))
    return hits[-1] if hits else None


def load_tracker(client_id, warn, path=None):
    """gt_* figures from the tracker, or {} with a warning. James's rule (v5 issues #42/#43):
    when the tracker exists its math IS the client's economics; when it does not, the
    workbook's billed figures stand, and the run says so."""
    from engine import guarantee as _gt
    p = Path(path) if path else find_tracker(client_id)
    if p is None:
        warn("no 2:1 guarantee deferral tracker for this client (Inputs/Guarantee Trackers/"
             f"{client_id}*Deferred*.xlsx); guarantee math skipped, the workbook's billed figures stand")
        return {}
    try:
        return _gt.read(p, warn)
    except Exception as exc:
        warn(f"deferral tracker read failed: {type(exc).__name__}: {exc}")
        return {}


def run(odd, client_id, period, workbook=None, out_dir=None, name=None, txn=True,
        txn_dirs=None, tables=None, overrides=None, tracker=None):
    """-> AnalysisResult. `tables` and `txn_dirs` are for the tests; the pipeline resolves
    both through rpe_env."""
    parsed = Month.parse(str(period))
    result = AnalysisResult(analysis=ANALYSIS, client_id=str(client_id),
                            period=parsed.iso if parsed else str(period))
    result.client_name = name
    with Timer(result):
        if parsed is None:
            result.fail(f"could not parse period {period!r}")
            return result
        out = Path(out_dir) if out_dir else analysis_dir(f"{parsed.year}.{parsed.month:02d}", client_id)
        out.mkdir(parents=True, exist_ok=True)   # the ODD-only path never created it (2026-09-30)

        # ---- the ODD, read once, transformed once -------------------------------------
        try:
            raw, source, preamble = read_odd(str(odd))
        except Exception as exc:
            result.fail(f"could not read {odd}: {type(exc).__name__}: {exc}")
            return result
        result.rows_in = len(raw)
        result.outputs["source"] = source
        frame, report = transform_odd(raw)
        result.warnings.extend(report.warnings)
        for err in report.errors:
            result.fail(err)
        if not result.ok:
            return result
        anchor = data_month(frame.columns)
        if anchor is None:
            result.fail("no month-tagged transaction columns in the ODD")
            return result
        result.data_month = anchor.iso
        if anchor != parsed.shift(-1):
            result.warn(f"data month {anchor.iso} is not one month before period {parsed.iso}")

        # ---- the client record: code tables + workbook -------------------------------
        wb_m = {}
        if workbook and Path(workbook).exists():
            from engine import workbook as _wb
            wb_m = _wb.read(Path(workbook), result.warn) or {}
            wb_m["wb_found"] = Path(workbook).name
        elif workbook:
            result.warn(f"workbook not found: {workbook}")
        if tables is None:
            try:
                tables = engine_config.load_tables()
            except Exception as exc:                                 # no data root in this process
                result.warn(f"code tables not read ({type(exc).__name__}); funnel stages skipped")
                tables = None
        config = engine_config.record_for(client_id, tables, wb_m, name=name,
                                          overrides=overrides, warn=result.warn)

        # ---- transactions, when the client has files ---------------------------------
        txn_metrics = None
        if txn:
            dirs = [Path(d) for d in txn_dirs] if txn_dirs else _txn_dirs(client_id)
            if dirs:
                from engine.transaction_intelligence.run import run as _txn_run
                t = _txn_run(str(client_id), parsed.iso, months=TXN_MONTHS, txn_dirs=dirs,
                             cache_dir=out / "_cache" / "txn", out_dir=out, odd=frame, client_cfg=config)
                for w in t.warnings:
                    result.warn(f"txn: {w}")
                if t.ok or t.metrics:
                    txn_metrics = t.metrics or None
                    result.outputs["txn_metrics"] = str(out / "txn_metrics.json")
                else:
                    result.warn("txn: " + "; ".join(t.errors))
            else:
                result.warn(f"no transaction files for {client_id}; the transaction sections are not built")

        # ---- the ODD sections ----------------------------------------------------------
        from engine.monthly_analysis.metrics import compute
        metrics, warnings = compute(frame, config, anchor=anchor, txn=txn_metrics)
        stress_frame = metrics.pop("_stress_frame", None)
        if wb_m:
            metrics.update({k: v for k, v in wb_m.items() if k.startswith("wb_")})
        metrics.update(load_tracker(client_id, result.warn, path=tracker))
        metrics["config_source"] = config.get("_config_source")
        for w in warnings:
            result.warn(w)
        from engine.monthly_analysis import consistency
        for msg in consistency.audit(metrics, txn_metrics):
            result.warn(f"consistency: {msg}")
        result.metrics = metrics
        if not metrics.get("n_eligible"):
            result.fail("eligible account count is zero")

        # ---- evidence ------------------------------------------------------------------
        try:
            frame.to_parquet(out / "enriched.parquet", index=False)
            result.outputs["enriched"] = str(out / "enriched.parquet")
        except Exception as exc:
            result.warn(f"parquet not written ({type(exc).__name__})")
        mj = out / "metrics.json"
        write_text_atomic(mj, json.dumps(metrics, indent=1, default=str))
        result.outputs["metrics"] = str(mj)
        if stress_frame is not None:
            from engine.monthly_analysis import stressors
            result.outputs["stressor_roster"] = stressors.write_roster(stress_frame, out / "lists")
        try:
            from engine.monthly_analysis import tables as _tables
            for key, path in _tables.write(metrics, out, result.warn).items():
                result.outputs[f"table_{key}"] = path
        except Exception as exc:
            result.warn(f"analyst tables failed: {type(exc).__name__}: {exc}")
        try:
            from engine.monthly_analysis.report import report as _report
            write_text_atomic(out / "report.md", _report(result))
            result.outputs["report"] = str(out / "report.md")
        except Exception as exc:
            result.warn(f"report failed: {type(exc).__name__}: {exc}")
        result.outputs["_manifest_dir"] = str(out)

    d = result.outputs.pop("_manifest_dir", None)
    if d:
        result.outputs["manifest"] = str(result.write_manifest(d))
    return result


# ---- reconciliation with the deck's own figures ------------------------------------------
# Only measures whose DEFINITIONS are identical on both sides can fail a build: the eligible
# base (the ODD flag, all rows) against the pack's funnel; eligible personal against
# metrics_gen's n_eligible (flag + Business? = No); the personal take rate against
# overall_take (cards / eligible personal). The rest are reported: their bases differ by
# design (his Reg E pool is open personal card holders; the engine's is eligible ones).
MUST_MATCH = (
    ("n_eligible", "pack funnel eligible", lambda E, M, O: (E.get("n_eligible"), (O.get("funnel") or {}).get("eligible")), 0),
    ("n_eligible_personal", "M n_eligible", lambda E, M, O: (E.get("n_eligible_personal"), M.get("n_eligible")), 0),
    ("dctr_personal", "M take_hist_pct", lambda E, M, O: (E.get("dctr_personal"), M.get("take_hist_pct")), 0.15),
)
REPORT_ONLY = (
    ("rege_pct", "M rege_pct", lambda E, M, O: (E.get("rege_pct"), M.get("rege_pct"))),
    ("n_responders", "M n_responders", lambda E, M, O: (E.get("n_responders"), M.get("n_responders"))),
)


def reconcile(engine_metrics, M, O):
    """-> (failures, report lines). A failure is a MUST_MATCH measure whose two values differ
    beyond its tolerance; a value missing on either side is reported, never a failure."""
    fails, lines = [], []
    for key, other, pick, tol in MUST_MATCH:
        a, b = pick(engine_metrics or {}, M or {}, O or {})
        if a is None or b is None:
            lines.append(f"  {key:<22} engine {a!s:>10}  deck {b!s:>10}  (not compared)")
            continue
        ok = abs(float(a) - float(b)) <= tol
        lines.append(f"  {key:<22} engine {a!s:>10}  deck {b!s:>10}  {'ok' if ok else 'DRIFT'} vs {other}")
        if not ok:
            fails.append(f"{key}: engine {a} vs {other} {b}")
    for key, other, pick in REPORT_ONLY:
        a, b = pick(engine_metrics or {}, M or {}, O or {})
        lines.append(f"  {key:<22} engine {a!s:>10}  deck {b!s:>10}  (bases differ; reported)")
    return fails, lines


def _txn_dirs(client_id):
    """Inputs/Txn Files/<id>/ when it holds files, else []. Resolved through rpe_env."""
    try:
        import rpe_env
        files = rpe_env.txn_files(client_id)
    except Exception:
        return []
    return sorted({f.parent for f in files}) if files else []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("odd")
    ap.add_argument("client_id")
    ap.add_argument("period")
    ap.add_argument("--workbook")
    ap.add_argument("--out")
    ap.add_argument("--name")
    ap.add_argument("--no-txn", action="store_true")
    a = ap.parse_args(argv)
    r = run(a.odd, a.client_id, a.period, workbook=a.workbook, out_dir=a.out, name=a.name, txn=not a.no_txn)
    print(r.summary())
    for w in r.warnings:
        print("  warn:", w)
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
