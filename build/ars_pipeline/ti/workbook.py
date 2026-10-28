# Ported from ARS v5 02-Scripts/ars/workbook.py at a491b5c (James Gilmore); logic unchanged.
"""ARS Workbook reader: program revenue, cost and profit -> wb_* metrics.

Field map confirmed against the real 1585 workbook (issue #11 attachment):
    Executive Financials MM   month + life-to-date P&L, months in program,
                              mailings to date
    Actuals MM                monthly revenue / program fee / profit series,
                              Key Assumptions (Interchange Rate, NSF Fee)
    Mailing {Mon YYYY}        per-wave mailed counts, response, cumulative
                              revenue (one sheet per wave)
    Lift Matrix MM            the current window's baseline-segment x swipe-
                              band rate card, and the window it is good for
The 'MM' sheets are the live ones; their template twins carry January 2007
stub dates and are skipped. 'Spot Mail ROI MM' ships with stale cached
formulas (#DIV/0!) -- ROI is computed here from the P&L, never read.
"""

from __future__ import annotations

import re
from pathlib import Path

from .core.periods import Month

WORKBOOK_GLOB = "*Workbook*.xls*"
# Lift Matrix MM: the anchor to scan for, the columns the bands occupy
# (C..H) and a generous row cap -- the block is found by SCANNING for the
# anchor, never by row number, because it slides between workbook versions.
LIFT_ANCHOR = "Baseline Segment"
LIFT_FIRST_COL, LIFT_LAST_COL = 2, 8
LIFT_MAX_ROWS = 12
LIFT_HEADER_LOOKBACK = 8
_STUB_MARK = "January 2007"
_MONTH_TAG = {"Jan": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr",
              "May": "May", "Jun": "Jun", "Jul": "Jul", "Aug": "Aug",
              "Sep": "Sep", "Oct": "Oct", "Nov": "Nov", "Dec": "Dec"}


# Bumped whenever the way a figure is READ changes, not when the workbook
# format does. It is stamped onto every result so "was this deck built
# before the Rev-to-date fix?" is answerable from the deck rather than from
# whoever remembers the merge date (#89).
#
#   1  original: last numeric on the Total Revenue: row, window capped at
#      column J -- landed on a mid-series month, or on Annualized
#   2  reads the To Date column by header (#88)
READER_VERSION = 2

# Sheets carry a rate at whatever precision the cell holds; config carries
# what someone typed. Half a percent apart is the same rate. A real fee
# change is orders of magnitude bigger (0.0062 to 0.0071 is 14%) (#115).
RATE_TOLERANCE = 0.005
RATE_PRECISION = 6


def rates_agree(config_value, sheet_value, rel_tol: float = RATE_TOLERANCE) -> bool:
    """True when a config rate and the sheet's rate differ by rounding only."""
    cfg, sheet = float(config_value), float(sheet_value)
    scale = max(abs(cfg), abs(sheet))
    return abs(cfg - sheet) <= rel_tol * scale


def find_workbook(data_root: Path, client_id: str, period: str) -> Path | None:
    """The client's workbook for the period, canonical layout first."""
    for base in (data_root / period / str(client_id),
                 data_root / "ARS" / period / str(client_id),
                 data_root / str(client_id)):
        if base.is_dir():
            hits = sorted(p for p in base.glob(WORKBOOK_GLOB)
                          if not p.name.startswith("~$"))
            if hits:
                return hits[-1]
    return None


def _rows(ws, max_row=160, max_col=60):
    return list(ws.iter_rows(min_row=1, max_row=min(max_row, ws.max_row),
                             max_col=min(max_col, ws.max_column),
                             values_only=True))


def _is_stub(rows) -> bool:
    return any(_STUB_MARK in str(c) for row in rows[:8] for c in row if c)


def _label_row(rows, prefix):
    """First row whose cells contain a label starting with `prefix`;
    returns the numeric cells that follow it."""
    for row in rows:
        for i, c in enumerate(row):
            if isinstance(c, str) and c.strip().startswith(prefix):
                nums = [v for v in row[i + 1:] if isinstance(v, (int, float))]
                return nums
    return []


def _cell_after(rows, label, last=False):
    """First (or last) numeric after a label cell. `last=True` for values
    that change over the program's life -- the NSF fee moved 27 -> 30 and
    the FIRST cell is three years stale."""
    for row in rows:
        for i, c in enumerate(row):
            if isinstance(c, str) and label in c:
                nums = [v for v in row[i + 1:] if isinstance(v, (int, float))]
                if nums:
                    return nums[-1] if last else nums[0]
    return None


_MONTH_LABEL = re.compile(r"([A-Za-z]{3,9})\s+(\d{4})")


def _as_month(value):
    """A date cell, or a 'July 2026' label, as a comparable ``(year,
    month)``. ``None`` when the cell is neither."""
    if hasattr(value, "year") and hasattr(value, "month"):
        return value.year, value.month
    mt = _MONTH_LABEL.fullmatch(str(value or "").strip())
    if not mt:
        return None
    abbr = mt.group(1)[:3].title()
    if abbr not in _MONTH_TAG:
        return None
    return int(mt.group(2)), list(_MONTH_TAG).index(abbr) + 1


def _month_label(pair) -> str:
    return f"{list(_MONTH_TAG)[pair[1] - 1]} {pair[0]}"


def _lift_matrix(rows) -> dict | None:
    """The CURRENT window's rate card on Lift Matrix MM: baseline segment
    down the side, swipe band across the top, the sheet's own rate in each
    cell.

    The first block under the anchor is the current window; older windows
    sit below it and are not what the deck quotes. Units are never
    asserted here -- the sheet's own caption is carried up instead, so a
    workbook that changes its basis cannot silently relabel the slide.
    """
    hdr = next((i for i, row in enumerate(rows)
                if len(row) > 1 and isinstance(row[1], str)
                and row[1].strip() == LIFT_ANCHOR), None)
    if hdr is None:
        return None
    cols = [str(c).strip()
            for c in rows[hdr][LIFT_FIRST_COL:LIFT_LAST_COL] if c]
    if not cols:
        return None

    body = []
    for row in rows[hdr + 1:hdr + 1 + LIFT_MAX_ROWS]:
        seg = row[1] if len(row) > 1 else None
        if not isinstance(seg, str) or not seg.strip():
            break                      # the block ends at the first gap
        cells = row[LIFT_FIRST_COL:LIFT_FIRST_COL + len(cols)]
        body.append([seg.strip()] + [round(v, 2)
                                     if isinstance(v, (int, float)) else None
                                     for v in cells])
    if not body:
        return None

    # written key by key, not as a dict literal: register.py's provenance
    # scan only sees out["key"] = assignments, and a slide whose keys read
    # "unmapped" cannot be traced back to the sheet that wrote them
    out: dict = {}
    out["wb_lift_cols"] = cols
    out["wb_lift_rows"] = body
    start = end = None
    for row in rows[max(0, hdr - LIFT_HEADER_LOOKBACK):hdr]:
        label = row[1] if len(row) > 1 else None
        value = row[2] if len(row) > 2 else None
        if not isinstance(label, str):
            continue
        if label.strip() == "Start Date":
            start = _as_month(value)
        elif label.strip() == "End Date":
            end = _as_month(value)

    # walk UP from the anchor: the nearest month label is the data month,
    # the nearest other prose is the caption that names the unit
    caption = data_month = None
    for row in reversed(rows[max(0, hdr - LIFT_HEADER_LOOKBACK):hdr]):
        cell = row[1] if len(row) > 1 else None
        if not isinstance(cell, str) or not cell.strip():
            continue
        text = cell.strip()
        if text in ("Start Date", "End Date"):
            continue
        if _as_month(text):
            data_month = data_month or _as_month(text)
        else:
            caption = caption or text

    if start and end:
        out["wb_lift_window"] = (f"{_month_label(start)} to "
                                 f"{_month_label(end)}")
    if caption:
        out["wb_lift_caption"] = caption
    if data_month:
        out["wb_lift_data_month"] = _month_label(data_month)
        if end:
            out["wb_lift_stale"] = data_month > end
    return out


def _rollup_sections(rows):
    """``{section label: {month: revenue}}`` for every block on All Months
    Rollup MM -- the ``Summary`` block and one per ``{Month Year} Mailing``.

    Each section carries its own month header row, with the figure on the
    ``Total Incremental Income`` row a few rows below it. A month with no
    cell had not happened for that wave yet: it is absent, never zero.
    """
    out: dict[str, dict[str, float]] = {}
    for i, row in enumerate(rows):
        label = row[1] if len(row) > 1 else None
        if not isinstance(label, str):
            continue
        label = label.strip()
        if label != "Summary" and not label.endswith("Mailing"):
            continue
        months = [(j, c) for j, c in enumerate(row) if hasattr(c, "year")]
        if not months:
            continue
        income = None
        for r in range(i + 1, min(i + 8, len(rows))):
            if any(isinstance(c, str) and "Total Incremental Income" in c
                   for c in rows[r] if c):
                income = rows[r]
                break
        if income is None:
            continue
        out[label] = {f"{c.year}-{c.month:02d}": income[j]
                      for j, c in months
                      if j < len(income)
                      and isinstance(income[j], (int, float))}
    return out


def _revenue_to_date(rows):
    """A wave's revenue to date, read from the Financial Summary block by
    COLUMN HEADER.

    The block is ``Financial Summary | ... | Annualized | To Date`` above a
    ``Total Revenue:`` row that opens with the monthly series. Taking the
    last numeric on that row is wrong two ways: on a long history To Date
    sits past the read window, so the last cell in range is a mid-series
    MONTH; on a sheet that ships no To Date column at all the last numeric
    is the ANNUALIZED projection, which is not revenue that happened.
    Match "Financial Summary" exactly -- "Threshold Financial Summary" is a
    different block, and the per-tier subtotals must never be summed.
    """
    for i, row in enumerate(rows):
        if not any(isinstance(c, str) and c.strip() == "Financial Summary"
                   for c in row if c):
            continue
        hdr = {c.strip(): j for j, c in enumerate(row) if isinstance(c, str)}
        td, ann = hdr.get("To Date"), hdr.get("Annualized")
        for vrow in rows[i:i + 4]:
            if not any(isinstance(c, str) and c.strip() == "Total Revenue:"
                       for c in vrow if c):
                continue
            if td is not None and td < len(vrow) \
                    and isinstance(vrow[td], (int, float)):
                return vrow[td]
            cut = ann if ann is not None else len(vrow)
            nums = [v for v in vrow[:cut] if isinstance(v, (int, float))]
            return sum(nums) if nums else None
    return None


def _tier_scan_start(rows) -> int:
    """First row of the canonical tier block.

    Some sheets repeat the tier counts in a summary panel ABOVE the Nonuser
    anchor (CoastHills Apr 2026). Scanning from row 0 counts both and
    doubles every responder figure -- and the response rate with it.
    """
    for i, row in enumerate(rows):
        for c in row:
            if isinstance(c, str) and (c.startswith("Nonuser (Zero swipes")
                                       or c.startswith("Threshold (")):
                return i
    return 0


def read(path: Path, warn) -> dict:
    """Parse one workbook into wb_* metrics. Declines loudly, never crashes
    the run -- callers wrap in the section try/except."""
    import openpyxl
    out: dict = {}
    tmp = None
    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except PermissionError:
        # Excel (or OneDrive sync) holds the file -- same situation as the
        # PowerPoint lock on save. Work from a temp copy when possible.
        import shutil
        try:
            # RPE: the copy goes in an rpe_env-managed scratch folder (removed at exit and swept
            # after a crash), never a bare tempfile (tests/test_temp_cleanup.py); v5 used mkstemp
            import rpe_env
            tmp = str(Path(rpe_env.temp_dir("ars_assets_")) / path.name)
            shutil.copyfile(path, tmp)
            wb = openpyxl.load_workbook(tmp, data_only=True, read_only=True)
            warn(f"workbook {path.name} is open in Excel/OneDrive -- read "
                 f"from a temp copy (numbers are the last SAVED state)")
        except Exception:
            warn(f"workbook {path.name} is locked (open in Excel, or "
                 f"OneDrive still syncing) -- close it and re-run; "
                 f"P&L slide skipped this run")
            return out
    try:
        # ---- Executive Financials MM: the P&L ---------------------------
        name = next((n for n in wb.sheetnames
                     if n.startswith("Executive Financials") and n.endswith("MM")),
                    None)
        if name:
            rows = _rows(wb[name], max_row=40, max_col=10)
            if not _is_stub(rows):
                rev = _label_row(rows, "Total Incremental Revenu")
                cost = _label_row(rows, "Total Costs")
                profit = _label_row(rows, "Incremental Profit")
                # columns: [month actual, month plan, LTD actual, LTD plan]
                out["wb_reader_version"] = READER_VERSION
                if len(rev) >= 3:
                    out["wb_revenue_month"] = round(rev[0])
                    out["wb_revenue_ltd"] = round(rev[2])
                if len(cost) >= 3:
                    out["wb_costs_ltd"] = round(cost[2])
                if len(profit) >= 3:
                    out["wb_profit_month"] = round(profit[0])
                    out["wb_profit_ltd"] = round(profit[2])
                mip = _cell_after(rows, "Months in the Program")
                mtd = _cell_after(rows, "Mailings to date")
                if mip:
                    out["wb_months_in_program"] = int(mip)
                if mtd:
                    out["wb_mailings_to_date"] = int(mtd)
                if out.get("wb_profit_ltd") is not None and out.get("wb_costs_ltd"):
                    out["wb_roi_ltd"] = round(
                        out["wb_profit_ltd"] / abs(out["wb_costs_ltd"]), 1)
                # A tab that carries no life-to-date figures at all (an SM workbook's Executive
                # Financials MM is a shell: 1075 Austin Bank read as "$0 of program profit in 1
                # months", 2026-10-28) is stated, never printed as zero.
                if not out.get("wb_revenue_ltd") and not out.get("wb_profit_ltd") \
                        and not out.get("wb_costs_ltd"):
                    for k in ("wb_revenue_month", "wb_revenue_ltd", "wb_costs_ltd", "wb_profit_month",
                              "wb_profit_ltd", "wb_months_in_program", "wb_mailings_to_date", "wb_roi_ltd"):
                        out.pop(k, None)
                    warn(f"workbook {path.name}: '{name}' carries no life-to-date revenue, costs or profit "
                         f"(an SM workbook's MM tab, or an unevaluated one); the economics are stated, not zero")

        # ---- Actuals MM: monthly series + the client's real economics ---
        name = next((n for n in wb.sheetnames if n == "Actuals MM"), None)
        if name:
            rows = _rows(wb[name], max_row=40)
            if not _is_stub(rows):
                months_row = next((r for r in rows
                                   if any(hasattr(c, "year") for c in r)), None)
                rev = _label_row(rows, "Total Marginal Revenue")
                cost = _label_row(rows, "Total Cost")
                profit = _label_row(rows, "Incremental Profit")
                if months_row and rev:
                    months = [c for c in months_row if hasattr(c, "year")]
                    series = []
                    for i, mth in enumerate(months):
                        series.append([
                            f"{mth.year}-{mth.month:02d}",
                            round(rev[i]) if i < len(rev) else None,
                            round(cost[i]) if i < len(cost) else None,
                            round(profit[i]) if i < len(profit) else None])
                    out["wb_monthly"] = series
                    out["wb_monthly_columns"] = ["month", "revenue", "cost",
                                                 "profit"]
                ic = _cell_after(rows, "Interchange Rate", last=True)
                nsf = _cell_after(rows, "NSF Fee", last=True)
                if ic:
                    out["wb_ic_rate"] = round(float(ic), RATE_PRECISION)
                if nsf:
                    out["wb_nsf_fee"] = round(float(nsf), 2)

        # ---- All Months Rollup MM: program-wide responders by month -----
        name = next((n for n in wb.sheetnames if n == "All Months Rollup MM"),
                    None)
        if name:
            rows = _rows(wb[name], max_row=200, max_col=50)
            if not _is_stub(rows):
                months_row = next((r for r in rows
                                   if any(hasattr(c, "year") for c in r)), None)
                resp_row = next((r for r in rows
                                 if any(isinstance(c, str)
                                        and c.strip() == "Number of Responders"
                                        for c in r if c)), None)
                if months_row and resp_row:
                    lab_i = next(i for i, c in enumerate(resp_row)
                                 if isinstance(c, str)
                                 and c.strip() == "Number of Responders")
                    series = []
                    for i, c in enumerate(months_row):
                        if hasattr(c, "year") and i > lab_i:
                            v = resp_row[i] if i < len(resp_row) else None
                            if isinstance(v, (int, float)):
                                series.append([f"{c.year}-{c.month:02d}",
                                               int(v)])
                    if series:
                        out["wb_responders_monthly"] = series
                        latest = next((x for x in reversed(series) if x[1]),
                                      None)
                        if latest:
                            out["wb_responders_latest"] = latest

                # ---- the wave x month matrix (the sheet's whole point) --
                sections = _rollup_sections(rows)
                summary = sections.pop("Summary", {})
                by_wave: dict[str, dict[str, float]] = {}
                for label, series in sections.items():
                    mth = Month.parse(label.replace("Mailing", "").strip())
                    if mth is None:
                        warn(f"workbook {path.name}: rollup section "
                             f"'{label}' is not a readable wave name; "
                             f"its revenue is not in the matrix")
                        continue
                    by_wave[mth.tag] = series
                if by_wave:
                    out["wb_wave_revenue"] = [
                        [tag, mth, round(v, 2)]
                        for tag, series in by_wave.items()
                        for mth, v in sorted(series.items())]
                    out["wb_wave_revenue_columns"] = ["wave", "month",
                                                      "revenue"]
                    out["wb_rollup_total_ltd"] = round(
                        sum(sum(s.values()) for s in by_wave.values()))
                    # the Summary row IS the sum of the wave rows; where it
                    # is not, a section was missed or the sheet is mid-edit
                    for mth, total in sorted(summary.items()):
                        rolled = sum(s.get(mth, 0) for s in by_wave.values())
                        if total and abs(rolled - total) > 0.005 * abs(total):
                            warn(f"workbook {path.name}: rollup {mth} wave "
                                 f"rows sum to {rolled:,.0f} but the "
                                 f"Summary row says {total:,.0f} -- a wave "
                                 f"section was missed, or the sheet is "
                                 f"mid-edit")

        # ---- per-wave Mailing sheets ------------------------------------
        waves = []
        for name in wb.sheetnames:
            mt = re.fullmatch(r"Mailing (\w{3}) (\d{4})", name)
            if not mt:
                continue
            rows = _rows(wb[name], max_row=120, max_col=40)
            if _is_stub(rows):
                continue
            tag = f"{mt.group(1)}{mt.group(2)[2:]}"
            mailed = [v for v in (
                _cell_after(rows, "Nonuser (Zero swipes"),
                _cell_after(rows, "Threshold (")) if v]
            # the workbook's own responder count: EVERY swipe-goal tier
            # (Nonuser 5+ and the Threshold goals 10/15/20/25...)
            goal_met = 0
            tiers: dict[str, int] = {}
            for row in rows[_tier_scan_start(rows):]:
                for i, c in enumerate(row):
                    if not isinstance(c, str):
                        continue
                    mt2 = re.fullmatch(r"Swipes:\s*(\d+)\+\s*", c)
                    if mt2:
                        nums = [v for v in row[i + 1:]
                                if isinstance(v, (int, float))]
                        if nums:
                            g = int(mt2.group(1))
                            key = "NU5" if g == 5 else f"TH{g}"
                            tiers[key] = tiers.get(key, 0) + int(nums[0])
                            goal_met += int(nums[0])
            cum_rev = _revenue_to_date(rows)
            if cum_rev is None:
                warn(f"workbook {path.name}: sheet '{name}' has no readable "
                     f"Financial Summary block -- revenue to date is blank "
                     f"for this wave (send the sheet if this is a new layout)")
            n_mailed = int(sum(mailed)) if mailed else None
            if tiers:
                out.setdefault("wb_wave_tiers", {})[tag] = tiers
            waves.append([tag, n_mailed,
                          round(100 * goal_met / n_mailed, 1)
                          if n_mailed and goal_met else None,
                          round(cum_rev) if cum_rev is not None else None,
                          goal_met or None])
        if waves:
            out["wb_waves"] = waves
            out["wb_waves_columns"] = ["wave", "mailed", "response_pct",
                                       "cumulative_revenue",
                                       "goal_met_responders"]
        # ---- Lift Matrix MM: the segment x band rate card ---------------
        name = next((n for n in wb.sheetnames if n == "Lift Matrix MM"), None)
        if name:
            rows = _rows(wb[name], max_row=40, max_col=12)
            if not _is_stub(rows):
                lift = _lift_matrix(rows)
                if lift is None:
                    warn(f"workbook {path.name}: 'Lift Matrix MM' carries no "
                         f"'{LIFT_ANCHOR}' block -- the rate card slide is "
                         f"skipped (send the sheet if this is a new layout)")
                else:
                    out.update(lift)
                    if lift.get("wb_lift_stale"):
                        warn(f"workbook {path.name}: the Lift Matrix window "
                             f"ends {lift.get('wb_lift_window', '')} but the "
                             f"sheet's data month is "
                             f"{lift.get('wb_lift_data_month')} -- the rate "
                             f"card is stale and the slide says so")

        # ---- three independent paths to the same money ------------------
        rolled_by_wave: dict[str, float] = {}
        for tag, _mth, val in (out.get("wb_wave_revenue") or []):
            rolled_by_wave[tag] = rolled_by_wave.get(tag, 0.0) + val
        for tag, _mailed, _resp, cum, *_ in (out.get("wb_waves") or []):
            rolled = rolled_by_wave.get(str(tag))
            if rolled and cum and abs(rolled - cum) > 0.01 * abs(rolled):
                warn(f"workbook {path.name}: wave {tag} rolls up to "
                     f"${rolled:,.0f} but its Mailing sheet To Date says "
                     f"${cum:,.0f} -- confirm which sheet is current")
        ltd, pnl_ltd = out.get("wb_rollup_total_ltd"), out.get("wb_revenue_ltd")
        if ltd and pnl_ltd and abs(ltd - pnl_ltd) > 0.01 * abs(pnl_ltd):
            warn(f"workbook {path.name}: the rollup totals ${ltd:,.0f} life "
                 f"to date but Executive Financials says ${pnl_ltd:,.0f}")

        if out:
            out["wb_source"] = path.name
        else:
            warn(f"workbook {path.name}: no recognisable sheets (template "
                 f"stub, or a new layout -- send the sheet list)")
    finally:
        wb.close()
        if tmp:
            try:
                Path(tmp).unlink()
            except OSError:
                pass
    return out
