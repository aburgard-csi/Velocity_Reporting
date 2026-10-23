"""
odd_sections.py — the ODD sections of v5's monthly analysis that the cut carries, as functions of
the shared context (`ti/context.py`).

v5 (`ars/monthly_analysis/metrics.py`) runs every section as `compute(subsets, config, warn)` and
merges the result into `metrics.json`. Each function here makes that same call on the context, so
the build (the chapters' `compute`) and the parity check against v5's `metrics.json` run a section
exactly the same way. Each chapter's pull request adds its sections here and to `PARITY`.
"""


def _section(module):
    import importlib
    m = importlib.import_module(f"ti.monthly_analysis.{module}")
    return lambda ctx: m.compute(ctx.subsets, ctx.config, ctx.warn)


def retention(ctx):
    return _section("retention")(ctx)


def lifecycle(ctx):
    """v5 registers lifecycle_report.compute under the section name "lifecycle"."""
    return _section("lifecycle_report")(ctx)


# name -> (v5 figures file, compute(ctx) -> dict); merged into ti.parity.REGISTRY
PARITY = {
    "retention": ("metrics.json", retention),
    "lifecycle": ("metrics.json", lifecycle),
}
