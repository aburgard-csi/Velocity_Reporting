"""
odd_sections.py — the ODD sections of v5's monthly analysis that the cut carries, as functions of
the shared context (`ti/context.py`).

v5 (`ars/monthly_analysis/metrics.py`) runs every section as `compute(subsets, config, warn)` and
merges the result into `metrics.json`. Each function here makes that same call on the context, so
the build (the chapters' `compute`) and the parity check against v5's `metrics.json` run a section
exactly the same way. Each chapter's pull request adds its sections here and to `PARITY`.
"""


def _deposits(ctx):
    """Make sure v5's deposit inputs are on the config before a section that reads them.

    A build has attached them already (ti/deposits_input.attach). The parity check has not: it
    attaches the rows v5's own run read, from v5's parquet cache, and ONLY when the file that run
    read was the client's own (v5 at a491b5c gave 1776 1100's file; those figures are no reference,
    and the check then runs without deposits and says so)."""
    if ctx.source_dir is None or "_deposit_raw" in ctx.config or ctx.shared.get("dep_tried"):
        return
    ctx.shared["dep_tried"] = True
    import glob
    import json
    import re
    from pathlib import Path
    import pandas as pd
    from ti.core import deposits as D
    run = Path(ctx.source_dir)
    cid = run.name
    manifests = glob.glob(str(run / "*_monthly_analysis.json"))
    src = (json.loads(Path(manifests[0]).read_text(encoding="utf-8")).get("outputs") or {}).get("deposits")         if manifests else None
    if not src:
        return
    own = re.compile(rf"(?<!\d){re.escape(cid)}(?!\d)")
    if not any(own.search(part) for part in Path(src).parts[-2:]):
        ctx.warn(f"parity: v5's run for {cid} read another client's deposits file ({Path(src).name}); "
                 f"its deposit figures are no reference, so this check runs without deposits")
        return
    hits = sorted(glob.glob(str(run.parents[1] / "_cache" / (glob.escape(Path(src).stem) + ".*.parquet"))))
    if not hits:
        ctx.warn(f"parity: no parquet of {Path(src).name} in v5's cache; deposits not attached")
        return
    raw = pd.read_parquet(hits[-1])
    ctx.config = dict(ctx.config, _deposit_raw=raw, _deposit_cadence=D.cadence(raw),
                      _deposit_monthly=D.monthly(raw))


def _section(module):
    import importlib
    m = importlib.import_module(f"ti.monthly_analysis.{module}")
    return lambda ctx: m.compute(ctx.subsets, ctx.config, ctx.warn)


def retention(ctx):
    return _section("retention")(ctx)


def lifecycle(ctx):
    """v5 registers lifecycle_report.compute under the section name "lifecycle"."""
    return _section("lifecycle_report")(ctx)


def attrition(ctx):
    return _section("attrition")(ctx)


def balance(ctx):
    _deposits(ctx)
    return _section("balance")(ctx)


def stressors(ctx):
    """v5's run pops the per-account stressor frame before writing metrics.json; it is kept on
    ctx.shared for the call-ready list, as v5 keeps it for lists/stressors.csv."""
    _deposits(ctx)
    out = _section("stressors")(ctx)
    ctx.shared["stress_frame"] = out.pop("_stress_frame", None)
    return out


# name -> (v5 figures file, compute(ctx) -> dict); merged into ti.parity.REGISTRY
PARITY = {
    "retention": ("metrics.json", retention),
    "lifecycle": ("metrics.json", lifecycle),
    "attrition": ("metrics.json", attrition),
    "balance": ("metrics.json", balance),
    "stressors": ("metrics.json", stressors),
}
