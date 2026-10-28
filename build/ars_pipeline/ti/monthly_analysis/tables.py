# Ported from ARS v5 02-Scripts/ars/monthly_analysis/tables.py at a491b5c (James Gilmore); logic unchanged.
"""The analyst table layer: every tabular metric as a CSV you can open.

The legacy toolkit printed 41 data frames. They never reached a deck, but
they were the working surface -- the place you went to check a number, or to
answer a question the slides did not anticipate. v5 went from the raw file
straight to finished slides with nothing in between, which is the structural
reason the output can feel thin even when every figure is present.

This is deliberately mechanical rather than curated. A metric that is a list
of rows AND declares its own column names is a table, so it is written. That
means new analysis shows up here the day it is computed, without anyone
remembering to register it -- and a section that has not named its columns is
visibly missing from the folder, which is the right nudge.

Rows are written exactly as the metric holds them. Nothing is recomputed,
rounded or re-ordered here, so a CSV can never disagree with the slide built
from the same key.
"""

from __future__ import annotations

import csv
from pathlib import Path

# Tables worth publishing that predate the columns convention. Anything new
# should declare `<key>_columns` instead of being added here.
LEGACY_COLUMNS = {
    "attrition_by_branch": ["branch", "at_risk", "closed", "rate_pct"],
    "attrition_by_tenure": ["tenure", "at_risk", "closed", "rate_pct"],
    "attrition_ars_vs_non": ["product_group", "at_risk", "closed", "rate_pct"],
    "attrition_first_year_by_branch": ["branch", "opened", "closed", "rate_pct"],
    "campaign_rates": ["wave", "mailed", "responded", "rate_pct"],
    "response_account_age": ["band", "mailed", "responded", "rate_pct"],
    "ics_cmp_balance_tiers": ["tier", "ics_pct", "non_ics_pct"],
    "ics_cmp_personas": ["persona", "ics_pct", "non_ics_pct"],
    "ics_cmp_tenure": ["band", "ics_pct", "non_ics_pct"],
    "ics_cmp_holder_age": ["band", "ics_pct", "non_ics_pct"],
    "ics_cmp_product": ["product", "ics_pct", "non_ics_pct"],
    "ics_cmp_source": ["channel", "accounts", "activated_m1_pct", "open_12mo_pct"],
    "ics_cohorts": ["month", "opened", "still_open", "activated_m1_pct",
                    "open_12mo_pct"],
}

MAX_CELL = 2000          # a stray blob is not a table cell


def _is_table(value) -> bool:
    return (isinstance(value, list) and value
            and all(isinstance(r, (list, tuple)) for r in value))


def _clean(cell) -> str:
    if cell is None:
        return ""
    text = str(cell)
    return text[:MAX_CELL]


def write(metrics: dict, out_dir: Path, warn) -> dict:
    """Write every declared table under `out_dir/tables`. Returns {key: path}."""
    tables_dir = Path(out_dir) / "tables"
    written: dict[str, str] = {}
    skipped: list[str] = []

    for key, value in sorted(metrics.items()):
        if key.endswith("_columns") or not _is_table(value):
            continue
        columns = metrics.get(f"{key}_columns") or LEGACY_COLUMNS.get(key)
        if not columns:
            skipped.append(key)
            continue
        width = max(len(r) for r in value)
        if len(columns) < width:
            # Better a table with honest placeholder headers than one whose
            # columns silently slide left of their data.
            columns = list(columns) + [f"col{i + 1}"
                                       for i in range(len(columns), width)]
        try:
            tables_dir.mkdir(parents=True, exist_ok=True)
            path = tables_dir / f"{key}.csv"
            # utf-8-sig, not utf-8. These files exist to be opened in Excel
            # on Windows, and without the BOM Excel reads them as the local
            # code page -- every accented merchant or institution name
            # garbles. The config reader already uses utf-8-sig for the same
            # reason. newline="" is csv's own requirement, and keeps Windows
            # from doubling the line endings.
            with path.open("w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh)
                w.writerow(columns[:width])
                for row in value:
                    w.writerow([_clean(c) for c in row])
            written[key] = str(path)
        except OSError as exc:
            warn(f"analyst tables: could not write {key}.csv: {exc}")

    if written:
        warn(f"analyst tables: {len(written)} table(s) written to "
             f"{tables_dir.name}/ -- the readable surface behind the slides")
    if skipped:
        warn(f"analyst tables: {len(skipped)} tabular metric(s) declare no "
             f"columns and were not written "
             f"({', '.join(sorted(skipped)[:6])}"
             f"{'...' if len(skipped) > 6 else ''})")
    return written
